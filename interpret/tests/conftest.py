"""pytest fixtures - 테스트용 더미 데이터 및 설정"""

import pytest
from omegaconf import OmegaConf


# 더미 뉴스 데이터
DUMMY_NEWS = {
    1: "삼성전자가 새로운 반도체 공장 건설을 발표했다. 투자 규모는 약 10조원으로 예상된다.",
    2: "미국 연준이 금리를 0.25% 인상했다. 이는 예상보다 높은 수준이다.",
    3: "중국의 경기 부양책 발표로 원자재 가격이 상승세를 보이고 있다.",
    4: "테슬라의 2분기 실적이 예상을 하회했다. 주가는 시간외 거래에서 5% 하락했다.",
    5: "애플이 AI 기능을 탑재한 새 아이폰을 공개했다. 시장 반응은 긍정적이다.",
    6: "유럽중앙은행이 금리 동결을 결정했다. 인플레이션 우려가 완화되고 있다.",
    7: "한국은행이 기준금리를 유지하기로 결정했다. 경기 둔화 우려가 반영되었다.",
    8: "OPEC+가 추가 감산을 발표했다. 유가는 3% 상승했다.",
    9: "미중 무역 협상이 결렬되었다. 관세 부과가 재개될 전망이다.",
    10: "엔비디아가 신형 GPU를 발표했다. AI 수요 증가로 실적 호조가 예상된다.",
}


@pytest.fixture
def dummy_news_fetcher():
    """더미 뉴스 조회 함수 - get_summarize에 주입"""
    def fetcher(news_id: int) -> str:
        if news_id in DUMMY_NEWS:
            return DUMMY_NEWS[news_id]
        return f"[뉴스 {news_id}] 해당 뉴스를 찾을 수 없습니다."
    return fetcher


@pytest.fixture
def test_config():
    """테스트용 config"""
    return OmegaConf.create({
        "llm": {
            "api_key": "EMPTY",
            "model": "local_model",
            "base_url": "http://localhost:8000/v1",
            "temperature": 0.7,
            "max_tokens": 2048,
        },
        "db": {
            "host": "localhost",
            "port": 5432,
            "database": "test_db",
            "user": "test_user",
            "password": "test_password",
        },
        "prompts": {
            "summarize_system": "테스트용 요약 시스템 프롬프트",
            "summarize_user": "사건: {event}\n뉴스: {news_list}",
            "predict_system": "테스트용 예측 시스템 프롬프트",
            "predict_user": "사건: {event}\n요약: {summary}",
        },
    })
