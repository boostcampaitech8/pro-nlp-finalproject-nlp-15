"""가격 상승/하락 예측 모듈"""

from omegaconf import DictConfig

from .core import send_llmapi


def estimate_updown(
    event: str,
    summary: str,
    news_ids: list[int],
    cfg: DictConfig,
) -> str:
    """
    요약과 사건으로부터 가격 상승/하락을 예측합니다.
    
    Args:
        event: 사건 설명 (string)
        summary: 사건 요약 (string)
        news_ids: 참조 뉴스 ID 리스트 (list[int])
        cfg: Hydra config 객체
    
    Returns:
        예측 결과 문자열 (상승/하락 + 근거)
    """
    # 프롬프트 생성
    system_prompt = cfg.prompts.predict_system
    user_prompt = cfg.prompts.predict_user.format(
        event=event,
        summary=summary,
    )
    
    # 참조 뉴스 ID 정보 추가 (추적용)
    user_prompt += f"\n\n참조 뉴스 ID: {news_ids}"
    
    # LLM API 호출
    prediction = send_llmapi(
        prompt=user_prompt,
        cfg=cfg,
        system_prompt=system_prompt,
    )
    
    return prediction
