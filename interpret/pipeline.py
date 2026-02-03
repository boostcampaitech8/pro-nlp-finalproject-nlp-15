"""
이벤트 기반 요약 및 가격 예측 파이프라인 (멀티스레드 버전, 100개 동시 요청)

사용법:
    uv run python interpret/pipeline.py --events data/events/gold_future.jsonl --articles data/articles/gold_future.csv
    uv run python interpret/pipeline.py --events data/events/gold_future.jsonl --articles data/articles/gold_future.csv --limit 10
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

from hydra import compose, initialize_config_dir
from omegaconf import DictConfig
from tqdm import tqdm

# 프로젝트 루트를 path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from interpret.core import ArticleLoader, EventLoader, get_commodity_name, send_llmapi

# 스레드 안전한 결과 저장을 위한 Lock
results_lock = threading.Lock()


def extract_direction(prediction_text: str) -> str:
    """
    예측 결과 텍스트에서 방향(up/down)만 추출
    
    COT 분석 결과에서 최종 결론만 추출합니다.
    
    Args:
        prediction_text: LLM의 전체 예측 응답
        
    Returns:
        "up" 또는 "down"
    """
    text_lower = prediction_text.lower()
    
    # 마지막 줄에서 최종 결론 찾기
    lines = prediction_text.strip().split('\n')
    last_lines = '\n'.join(lines[-3:]).lower()  # 마지막 3줄 검사
    
    # 패턴 매칭: 최종 결론 형식
    # [최종] up, 결론: up, 예측: 상승, etc.
    patterns = [
        r'\[최종\]\s*(up|down)',
        r'최종[:\s]*(up|down)',
        r'결론[:\s]*(up|down)',
        r'예측[:\s]*(up|down)',
        r'\*\*(up|down)\*\*',
        r'(up|down)$',  # 마지막 단어
    ]
    
    for pattern in patterns:
        match = re.search(pattern, last_lines)
        if match:
            return match.group(1)
    
    # 상승/하락 키워드 기반 판단
    if '상승' in prediction_text or '호재' in prediction_text:
        if '하락' not in prediction_text[-100:]:  # 마지막 100자에 하락이 없으면
            return 'up'
    if '하락' in prediction_text or '악재' in prediction_text:
        if '상승' not in prediction_text[-100:]:
            return 'down'
    
    # 전체 텍스트에서 up/down 빈도로 판단
    up_count = text_lower.count('up') + text_lower.count('상승') + text_lower.count('호재')
    down_count = text_lower.count('down') + text_lower.count('하락') + text_lower.count('악재')
    
    return 'up' if up_count >= down_count else 'down'


def get_summarize_from_articles(
    event: dict,
    articles: list[dict],
    cfg: DictConfig,
) -> str:
    """
    이벤트와 관련 기사들로부터 요약 생성
    
    Args:
        event: 이벤트 dict (title, description 등)
        articles: 관련 기사 리스트
        cfg: Hydra config
        
    Returns:
        요약 문자열
    """
    # 기사 텍스트 구성
    news_texts = []
    for i, article in enumerate(articles, 1):
        article_text = f"[기사 {i}] {article.get('title', '')}\n{article.get('description', '')}"
        news_texts.append(article_text)
    
    news_list = "\n\n".join(news_texts)
    
    # 이벤트 정보
    event_info = f"{event.get('title', '')}: {event.get('description', '')}"
    
    # 프롬프트 생성
    system_prompt = cfg.prompts.summarize_system
    user_prompt = cfg.prompts.summarize_user.format(
        event=event_info,
        news_list=news_list,
    )
    
    # LLM API 호출
    summary = send_llmapi(
        prompt=user_prompt,
        cfg=cfg,
        system_prompt=system_prompt,
    )
    
    return summary


def estimate_updown_cot(
    event: dict,
    summary: str,
    cfg: DictConfig,
) -> tuple[str, str]:
    """
    요약으로부터 가격 방향 예측 (COT 방식)
    
    Args:
        event: 이벤트 dict
        summary: 요약 텍스트
        cfg: Hydra config
        
    Returns:
        (direction, reasoning): 방향(up/down)과 COT 분석 내용
    """
    event_info = f"{event.get('title', '')}: {event.get('description', '')}"
    
    # COT 프롬프트
    system_prompt = cfg.prompts.predict_system
    user_prompt = cfg.prompts.predict_user.format(
        event=event_info,
        summary=summary,
    )
    
    # LLM API 호출
    prediction = send_llmapi(
        prompt=user_prompt,
        cfg=cfg,
        system_prompt=system_prompt,
    )
    
    # 방향 추출
    direction = extract_direction(prediction)
    
    return direction, prediction


def process_single_event(
    event: dict,
    article_loader: ArticleLoader,
    cfg: DictConfig,
) -> dict | None:
    """
    단일 이벤트 처리 (스레드에서 실행)
    
    Args:
        event: 이벤트 dict
        article_loader: 기사 로더
        cfg: Hydra config
        
    Returns:
        결과 dict 또는 None (실패 시)
    """
    event_id = event.get('event_id', '')
    source_ids = event.get('source', [])
    
    # 관련 기사 조회
    articles = article_loader.get_articles(source_ids)
    
    if not articles:
        return None
    
    try:
        # Step 1: 요약 생성
        summary = get_summarize_from_articles(event, articles, cfg)
        
        # Step 2: 가격 방향 예측
        direction, reasoning = estimate_updown_cot(event, summary, cfg)
        
        # 결과 반환
        return {
            'event_id': event_id,
            'title': event.get('title', ''),
            'description': event.get('description', ''),
            'start_date': event.get('start_date', ''),
            'end_date': event.get('end_date', ''),
            'window_start': event.get('window_start', ''),
            'source_ids': ','.join(source_ids),  # SQL 호환: 리스트를 문자열로
            'source_count': len(source_ids),
            'summary': summary,
            'direction': direction,  # up 또는 down
            'created_at': datetime.now().isoformat(),
        }
        
    except Exception as e:
        # 에러는 상위에서 처리
        raise e


# 동시 요청 수 (하드코딩)
MAX_WORKERS = 100


def process_events(
    events_path: str | Path,
    articles_path: str | Path,
    output_dir: str | Path,
    cfg: DictConfig,
    limit: int | None = None,
) -> Path:
    """
    이벤트들을 멀티스레드로 처리하여 CSV로 저장
    
    Args:
        events_path: 이벤트 JSONL 파일 경로
        articles_path: 기사 CSV 파일 경로
        output_dir: 출력 디렉토리
        cfg: Hydra config
        limit: 처리할 이벤트 수 제한 (None이면 전체)
        
    Returns:
        생성된 CSV 파일 경로
    """
    # 로더 초기화
    event_loader = EventLoader(events_path)
    article_loader = ArticleLoader(articles_path)
    
    # 원자재 이름 추출
    commodity = get_commodity_name(events_path)
    
    # 출력 디렉토리 생성
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 출력 파일 경로
    output_path = output_dir / f"{commodity}.csv"
    
    # 이벤트 로드 (limit 적용)
    all_events = event_loader.load_all()
    if limit:
        all_events = all_events[:limit]
    
    total_events = len(all_events)
    
    print(f"\n[Pipeline] 처리 시작: {commodity}")
    print(f"  - 이벤트 파일: {events_path}")
    print(f"  - 기사 파일: {articles_path}")
    print(f"  - 출력 파일: {output_path}")
    print(f"  - 처리 대상: {total_events}개 이벤트")
    print(f"  - 동시 요청 수: {MAX_WORKERS}개 스레드")
    print()
    
    # 결과 저장
    results = []
    errors = []
    
    # 멀티스레드 처리
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Future 객체 생성
        future_to_event = {
            executor.submit(process_single_event, event, article_loader, cfg): event
            for event in all_events
        }
        
        # tqdm으로 진행 상황 표시
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
                
                # 진행 상황 업데이트
                pbar.update(1)
                pbar.set_postfix({
                    'success': len(results),
                    'errors': len(errors),
                })
    
    # 결과 정렬 (event_id 순서대로)
    results.sort(key=lambda x: x['event_id'])
    
    # CSV 저장
    if results:
        save_results_to_csv(results, output_path)
        print(f"\n[Pipeline] 완료!")
        print(f"  - 성공: {len(results)}개")
        print(f"  - 실패: {len(errors)}개")
        print(f"  - 저장: {output_path}")
    else:
        print("\n[Pipeline] 처리된 결과가 없습니다.")
    
    # 에러 요약 출력 (처음 5개만)
    if errors:
        print(f"\n[Errors] 처음 5개 에러:")
        for err in errors[:5]:
            print(f"  - {err}")
        if len(errors) > 5:
            print(f"  ... 그 외 {len(errors) - 5}개 에러")
    
    return output_path


def save_results_to_csv(results: list[dict], output_path: Path) -> None:
    """
    결과를 SQL 친화적 CSV로 저장
    
    CSV 컬럼 (SQL 테이블 스키마와 일치):
        - event_id: VARCHAR(32) PRIMARY KEY
        - title: TEXT
        - description: TEXT
        - start_date: DATE
        - end_date: DATE
        - window_start: DATE
        - source_ids: TEXT (쉼표 구분 ID 리스트)
        - source_count: INTEGER
        - summary: TEXT
        - direction: VARCHAR(4) CHECK (direction IN ('up', 'down'))
        - created_at: TIMESTAMP
    """
    fieldnames = [
        'event_id',
        'title', 
        'description',
        'start_date',
        'end_date',
        'window_start',
        'source_ids',
        'source_count',
        'summary',
        'direction',
        'created_at',
    ]
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(results)


def generate_sql_schema(commodity: str) -> str:
    """
    SQL 테이블 생성 스키마 생성 (PostgreSQL 기준)
    
    Args:
        commodity: 원자재 이름
        
    Returns:
        CREATE TABLE SQL 문
    """
    return f"""
-- 예측 결과 테이블: {commodity}
CREATE TABLE IF NOT EXISTS predict_summarize_{commodity} (
    event_id VARCHAR(32) PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    start_date DATE,
    end_date DATE,
    window_start DATE,
    source_ids TEXT,  -- 쉼표로 구분된 기사 ID 리스트
    source_count INTEGER DEFAULT 0,
    summary TEXT,
    direction VARCHAR(4) CHECK (direction IN ('up', 'down')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_{commodity}_direction ON predict_summarize_{commodity}(direction);
CREATE INDEX IF NOT EXISTS idx_{commodity}_start_date ON predict_summarize_{commodity}(start_date);
CREATE INDEX IF NOT EXISTS idx_{commodity}_window_start ON predict_summarize_{commodity}(window_start);
"""


def main():
    parser = argparse.ArgumentParser(description='이벤트 기반 요약 및 가격 예측 파이프라인')
    parser.add_argument('--events', required=True, help='이벤트 JSONL 파일 경로')
    parser.add_argument('--articles', required=True, help='기사 CSV 파일 경로')
    parser.add_argument('--output', default='data/predict_summarize', help='출력 디렉토리')
    parser.add_argument('--limit', type=int, default=None, help='처리할 이벤트 수 제한')
    parser.add_argument('--generate-sql', action='store_true', help='SQL 스키마 출력')
    
    args = parser.parse_args()
    
    # 원자재 이름
    commodity = get_commodity_name(args.events)
    
    # SQL 스키마만 출력하고 종료
    if args.generate_sql:
        print(generate_sql_schema(commodity))
        return
    
    # Hydra config 로드
    config_path = PROJECT_ROOT / "config"
    with initialize_config_dir(version_base=None, config_dir=str(config_path)):
        cfg = compose(config_name="config")
    
    # 파이프라인 실행
    process_events(
        events_path=args.events,
        articles_path=args.articles,
        output_dir=args.output,
        cfg=cfg,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
