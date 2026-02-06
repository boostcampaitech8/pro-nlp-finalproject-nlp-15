# interpret/agents/verdict.py
import json
from omegaconf import DictConfig
from core.llm import send_llmapi

class VerdictAgent:
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        # config/prompts/verdict.yaml의 계층 구조 반영
        self.system_prompt = cfg.prompts.verdict.system

    async def judge(self, commodity_name, end_date, fact_book, debate_results):
        """
        팩트북(10년 추세 + 뉴스)과 토론 로그를 결합하여 내일의 가격을 예측합니다.
        """
        # 1. 토론 로그 정리 (리스트/딕셔너리 대응)
        debate_text = ""
        for res in debate_results:
            if isinstance(res, dict):
                # 제목과 Bull/Bear의 핵심 주장을 결합
                title = res.get('title') or res.get('event_title', '주요 사건')
                debate_text += f"\n[사건: {title}]\n- Bull: {res.get('bull_arg')}\n- Bear: {res.get('bear_arg')}\n"
            else:
                debate_text += f"\n{res}\n"

        # 2. 팩트북 전체를 JSON 문자열로 변환 (EMA, Volume 등 기술적 지표 포함 필수)
        fact_book_str = json.dumps(fact_book, indent=2, ensure_ascii=False)

        # 3. YAML(verdict.yaml)의 변수명 {end_date}, {fact_book}, {debate_results}와 일치
        user_prompt = self.cfg.prompts.verdict.judge_user.format(
            end_date=end_date,
            fact_book=fact_book_str,
            debate_results=debate_text
        )

        return await send_llmapi(
            prompt=user_prompt,
            cfg=self.cfg,
            role="master",    
            task_type="verdict", 
            system_prompt=self.system_prompt
        )