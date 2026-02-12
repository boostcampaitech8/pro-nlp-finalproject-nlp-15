"""이벤트 기반 요약 및 가격 예측 파이프라인"""

import argparse
import csv
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from hydra import compose, initialize_config_dir
from omegaconf import DictConfig
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from interpret.csv_loader import ArticleLoader, EventLoader, get_commodity_name
from interpret.llm import send_llmapi
from interpret.db import (
    SQLEventLoader,
    DatabaseConnection,
    ensure_event_columns,
    update_event_interpret,
    get_events_pending_count,
    get_articles_by_ids,
)

results_lock = threading.Lock()
MAX_WORKERS = 100


def extract_direction(prediction_text: str) -> str:
    """예측 텍스트에서 up/down 추출"""
    text_lower = prediction_text.lower()
    lines = prediction_text.strip().split('\n')
    last_lines = '\n'.join(lines[-3:]).lower()
    
    patterns = [
        r'\[최종\]\s*(up|down)',
        r'최종[:\s]*(up|down)',
        r'결론[:\s]*(up|down)',
        r'예측[:\s]*(up|down)',
        r'\*\*(up|down)\*\*',
        r'(up|down)$',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, last_lines)
        if match:
            return match.group(1)
    
    if '상승' in prediction_text or '호재' in prediction_text:
        if '하락' not in prediction_text[-100:]:
            return 'up'
    if '하락' in prediction_text or '악재' in prediction_text:
        if '상승' not in prediction_text[-100:]:
            return 'down'
    
    up_count = text_lower.count('up') + text_lower.count('상승') + text_lower.count('호재')
    down_count = text_lower.count('down') + text_lower.count('하락') + text_lower.count('악재')
    
    return 'up' if up_count >= down_count else 'down'


def get_summarize_from_articles(event: dict, articles: list[dict], cfg: DictConfig) -> str:
    """이벤트와 기사들로부터 요약 생성"""
    news_texts = []
    for i, article in enumerate(articles, 1):
        news_texts.append(f"[기사 {i}] {article.get('title', '')}\n{article.get('description', '')}")
    
    news_list = "\n\n".join(news_texts)
    event_info = f"{event.get('title', '')}: {event.get('description', '')}"
    
    user_prompt = cfg.prompts.summarize_user.format(event=event_info, news_list=news_list)
    return send_llmapi(prompt=user_prompt, cfg=cfg, system_prompt=cfg.prompts.summarize_system)


def estimate_updown_cot(event: dict, summary: str, cfg: DictConfig) -> tuple[str, str]:
    """요약으로부터 가격 방향 예측"""
    event_info = f"{event.get('title', '')}: {event.get('description', '')}"
    user_prompt = cfg.prompts.predict_user.format(event=event_info, summary=summary)
    
    prediction = send_llmapi(prompt=user_prompt, cfg=cfg, system_prompt=cfg.prompts.predict_system)
    direction = extract_direction(prediction)
    
    return direction, prediction


def process_single_event(event: dict, article_loader: ArticleLoader, cfg: DictConfig) -> dict | None:
    """단일 이벤트 처리 (CSV 모드)"""
    event_id = event.get('event_id', '')
    source_ids = event.get('source', [])
    
    articles = article_loader.get_articles(source_ids)
    if not articles:
        return None
    
    summary = get_summarize_from_articles(event, articles, cfg)
    direction, _ = estimate_updown_cot(event, summary, cfg)
    
    return {
        'event_id': event_id,
        'title': event.get('title', ''),
        'description': event.get('description', ''),
        'start_date': event.get('start_date', ''),
        'end_date': event.get('end_date', ''),
        'window_start': event.get('window_start', ''),
        'source_ids': ','.join(source_ids),
        'source_count': len(source_ids),
        'summary': summary,
        'direction': direction,
        'created_at': datetime.now().isoformat(),
    }


def process_events(events_path: str | Path, articles_path: str | Path, 
                   output_dir: str | Path, cfg: DictConfig, limit: int | None = None) -> Path:
    """CSV 모드: JSONL/CSV 파일 처리 → CSV 출력"""
    event_loader = EventLoader(events_path)
    article_loader = ArticleLoader(articles_path)
    commodity = get_commodity_name(events_path)
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{commodity}.csv"
    
    all_events = event_loader.load_all()
    if limit:
        all_events = all_events[:limit]
    
    total_events = len(all_events)
    print(f"\n[Pipeline] 처리 시작: {commodity}")
    print(f"  - 이벤트: {events_path}, 기사: {articles_path}")
    print(f"  - 처리 대상: {total_events}개, 동시 요청: {MAX_WORKERS}개")
    
    results, errors = [], []
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_event = {
            executor.submit(process_single_event, event, article_loader, cfg): event
            for event in all_events
        }
        
        with tqdm(total=total_events, desc="Processing", unit="event") as pbar:
            for future in as_completed(future_to_event):
                event = future_to_event[future]
                event_id = event.get('event_id', '')
                
                try:
                    result = future.result()
                    if result:
                        with results_lock:
                            results.append(result)
                    else:
                        errors.append(f"No articles: {event_id}")
                except Exception as e:
                    errors.append(f"{event_id}: {e}")
                
                pbar.update(1)
                pbar.set_postfix({'success': len(results), 'errors': len(errors)})
    
    results.sort(key=lambda x: x['event_id'])
    
    if results:
        save_results_to_csv(results, output_path)
        print(f"\n[Pipeline] 완료: 성공 {len(results)}개, 실패 {len(errors)}개")
    
    if errors:
        print(f"\n[Errors] 처음 5개:")
        for err in errors[:5]:
            print(f"  - {err}")
    
    return output_path


def save_results_to_csv(results: list[dict], output_path: Path) -> None:
    fieldnames = ['event_id', 'title', 'description', 'start_date', 'end_date', 
                  'window_start', 'source_ids', 'source_count', 'summary', 'direction', 'created_at']
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(results)


def process_single_event_sql(event: dict, cfg: DictConfig) -> bool:
    """단일 이벤트 처리 (SQL 모드)"""
    event_pk = event.get('id')
    
    source = event.get('source', '')
    if isinstance(source, str):
        source_ids = [s.strip() for s in source.split(',') if s.strip()]
    elif isinstance(source, list):
        source_ids = source
    else:
        source_ids = []
    
    articles = get_articles_by_ids(source_ids, cfg)
    if not articles:
        return False
    
    summary = get_summarize_from_articles(event, articles, cfg)
    direction, _ = estimate_updown_cot(event, summary, cfg)
    is_up = direction == 'up'
    
    update_event_interpret(event_pk, summary, is_up, cfg)
    return True


def run_batch_interpret(cfg: DictConfig, limit: int | None = None, process_all: bool = False) -> int:
    """SQL 모드: DB에서 이벤트 조회 → LLM 처리 → DB 업데이트"""
    print("\n[Batch] 테이블 스키마 확인 중...")
    ensure_event_columns(cfg)
    
    event_loader = SQLEventLoader(cfg, pending_only=not process_all)
    all_events = event_loader.load_all(limit=limit)
    total_events = len(all_events)
    
    if total_events == 0:
        print("\n[Batch] 처리할 이벤트가 없습니다.")
        DatabaseConnection.close_pool()
        return 0
    
    print(f"\n[Batch] 처리 시작")
    print(f"  - DB: {cfg.db.host}:{cfg.db.port}/{cfg.db.database}")
    print(f"  - 모드: {'전체 재처리' if process_all else 'NULL만 처리'}")
    print(f"  - 처리 대상: {total_events}개, 동시 요청: {MAX_WORKERS}개")
    
    success_count = 0
    errors = []
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_event = {
            executor.submit(process_single_event_sql, event, cfg): event
            for event in all_events
        }
        
        with tqdm(total=total_events, desc="Processing", unit="event") as pbar:
            for future in as_completed(future_to_event):
                event = future_to_event[future]
                event_id = event.get('event_id', '')
                event_pk = event.get('id', '')
                
                try:
                    if future.result():
                        with results_lock:
                            success_count += 1
                    else:
                        errors.append(f"No articles: {event_id} (pk={event_pk})")
                except Exception as e:
                    errors.append(f"{event_id} (pk={event_pk}): {e}")
                
                pbar.update(1)
                pbar.set_postfix({'success': success_count, 'errors': len(errors)})
    
    print(f"\n[Batch] 완료: 성공 {success_count}개, 실패 {len(errors)}개")
    
    if errors:
        print(f"\n[Errors] 처음 5개:")
        for err in errors[:5]:
            print(f"  - {err}")
    
    if not process_all:
        print(f"\n[Batch] 남은 pending: {get_events_pending_count(cfg)}개")
    
    DatabaseConnection.close_pool()
    return success_count


def main():
    parser = argparse.ArgumentParser(description='이벤트 기반 요약 및 가격 예측 파이프라인')
    parser.add_argument('--events', help='이벤트 JSONL 파일 경로 (CSV 모드)')
    parser.add_argument('--articles', help='기사 CSV 파일 경로 (CSV 모드)')
    parser.add_argument('--output', default='data/predict_summarize', help='출력 디렉토리 (CSV 모드)')
    parser.add_argument('--all', action='store_true', dest='process_all', help='모든 이벤트 재처리')
    parser.add_argument('--limit', type=int, default=None, help='처리할 이벤트 수 제한')
    
    args = parser.parse_args()
    
    config_path = PROJECT_ROOT / "config"
    with initialize_config_dir(version_base=None, config_dir=str(config_path)):
        cfg = compose(config_name="config")
    
    if args.events or args.articles:
        if not args.events or not args.articles:
            parser.error("CSV 모드에서는 --events와 --articles 둘 다 필요합니다")
        process_events(args.events, args.articles, args.output, cfg, args.limit)
    else:
        run_batch_interpret(cfg, args.limit, args.process_all)


if __name__ == "__main__":
    main()
