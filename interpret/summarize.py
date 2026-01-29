"""사건 및 뉴스 요약 모듈"""

from omegaconf import DictConfig

from .core import send_llmapi, get_news


def get_summarize(
    event: str,
    news_ids: list[int],
    cfg: DictConfig,
    news_fetcher: callable | None = None,
) -> str:
    """
    사건과 기사들에 대한 요약을 생성합니다.
    
    Args:
        event: 사건 설명 (string)
        news_ids: 뉴스 ID 리스트 (list[int])
        cfg: Hydra config 객체
        news_fetcher: 뉴스 조회 함수 (테스트 시 주입, 기본값은 get_news)
    
    Returns:
        요약 문자열
    """
    # 뉴스 조회 함수 결정 (DI for testing)
    fetch_fn = news_fetcher if news_fetcher else lambda nid: get_news(nid, cfg)
    
    # 뉴스 ID로부터 뉴스 본문 가져오기
    news_list = []
    for news_id in news_ids:
        news_content = fetch_fn(news_id)
        news_list.append(f"[뉴스 {news_id}]\n{news_content}")
    
    news_text = "\n\n".join(news_list)
    
    # 프롬프트 생성
    system_prompt = cfg.prompts.summarize_system
    user_prompt = cfg.prompts.summarize_user.format(
        event=event,
        news_list=news_text,
    )
    
    # LLM API 호출
    summary = send_llmapi(
        prompt=user_prompt,
        cfg=cfg,
        system_prompt=system_prompt,
    )
    
    return summary
