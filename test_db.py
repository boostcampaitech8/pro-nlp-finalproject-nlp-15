import asyncio
import hydra
from omegaconf import DictConfig
from agents.analyst import AnalystAgent
import json

# 실제 비동기 로직을 담당할 함수
async def run_analyst_test(cfg: DictConfig):
    # 1. AnalystAgent 초기화
    analyst = AnalystAgent(cfg)
    
    print("\n--- [Step 1] DB 데이터 확인 및 테스트 기간 설정 ---")
    # DB에서 가장 최근 데이터 날짜를 자동으로 가져옵니다
    try:
        with analyst.db_manager.conn.cursor() as cursor:
            cursor.execute("SELECT start_date FROM event ORDER BY start_date DESC LIMIT 1")
            sample = cursor.fetchone()
            if not sample:
                print("❌ DB에 이벤트 데이터가 없습니다.")
                return
            test_date = str(sample['start_date'])
            print(f"📅 테스트 날짜: {test_date}")

        print(f"\n--- [Step 2] 크롤링 포함 팩트북 생성 시작 ---")
        # 비동기 크롤링이 포함된 핵심 메서드 호출
        fact_book = await analyst.create_enriched_fact_book("은", "2026-01-01", "2026-01-15")
        
        if fact_book and fact_book.get('events'):
            total = fact_book['analysis_metadata']['total_events_found']
            print(f"✅ 성공: 총 {total}개의 이벤트를 분석했습니다.")
            
            # 첫 번째 기사의 크롤링 결과 확인
            first_news = fact_book['events'][0]['news_evidence'][0]
            print(f"\n[크롤링 결과 샘플]")
            print(f"- 제목: {first_news['title']}")
            print(f"- URL: {first_news['doc_url']}")
            print(f"- 본문 길이: {len(first_news.get('content_full', ''))}자")
            print(f"- 본문 미리보기: {first_news.get('content_full', '')[:100]}...")
            
            # 파일 저장
            with open("fact_book_final.json", "w", encoding="utf-8") as f:
                json.dump(fact_book, f, indent=2, ensure_ascii=False)
            print("\n💾 'fact_book_final.json' 저장 완료.")
        else:
            print("❌ 추출된 이벤트가 없습니다.")
            
    except Exception as e:
        print(f"❌ 실행 중 오류 발생: {e}")

# Hydra 진입점은 일반 함수로 작성합니다.
@hydra.main(version_base=None, config_path="config", config_name="config")
def main(cfg: DictConfig):
    # 일반 함수 내부에서 비동기 루프를 실행합니다.
    asyncio.run(run_analyst_test(cfg))

if __name__ == "__main__":
    main()