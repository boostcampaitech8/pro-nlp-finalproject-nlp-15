"""메인 실행 파일 - Hydra를 통한 config 관리"""

import hydra
from omegaconf import DictConfig

from interpret import get_summarize, estimate_updown


@hydra.main(version_base=None, config_path="../config", config_name="config")
def main(cfg: DictConfig) -> None:
    """
    메인 함수 - MVP 실행
    
    사용법:
        uv run python interpret/main.py
        uv run python interpret/main.py llm.temperature=0.5
        uv run python interpret/main.py +db=rdb  # config group 선택
    """
    print("=" * 50)
    print("뉴스 요약 및 가격 예측 MVP")
    print("=" * 50)
    print("\n[Config 설정]")
    print(f"LLM Model: {cfg.llm.model}")
    print(f"LLM Base URL: {cfg.llm.base_url}")
    print(f"DB Host: {cfg.db.host}")
    print(f"Temperature: {cfg.llm.temperature}")
    print()
    
    # MVP: 사건 하나, 기사 ID 10개
    event = "삼성전자 반도체 사업 관련 주요 뉴스"
    news_ids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    
    print(f"[사건] {event}")
    print(f"[뉴스 ID] {news_ids}")
    print()
    
    # Step 1: 요약 생성
    print("[Step 1] 사건 요약 생성 중...")
    try:
        summary = get_summarize(event, news_ids, cfg)
        print(f"\n요약 결과:\n{summary}\n")
    except NotImplementedError as e:
        print(f"RDB 연동 필요: {e}")
        summary = "RDB 연동 대기 중 - 테스트용 더미 요약"
    except Exception as e:
        print(f"요약 생성 실패: {e}")
        summary = "요약 생성 실패 - 테스트용 더미 요약"
    
    print("-" * 50)
    
    # Step 2: 상승/하락 예측
    print("[Step 2] 가격 예측 중...")
    try:
        prediction = estimate_updown(event, summary, news_ids, cfg)
        print(f"\n예측 결과:\n{prediction}\n")
    except Exception as e:
        print(f"예측 실패: {e}")
    
    print("=" * 50)
    print("MVP 실행 완료")
    print("=" * 50)


if __name__ == "__main__":
    main()
