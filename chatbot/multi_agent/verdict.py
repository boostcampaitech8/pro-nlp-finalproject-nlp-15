import json
from typing import Any
from omegaconf import DictConfig
from chatbot.bot.llm_client import LLMClient
from langchain_core.messages import SystemMessage, HumanMessage

class VerdictAgent:
    def __init__(self, cfg: DictConfig, llm_client: LLMClient):
        self.cfg = cfg
        self.llm_client = llm_client
        self.system_prompt = cfg.multi_agent_prompts.verdict.system

    async def judge(self, end_date: str, fact_book: dict[str, Any], debate_results: str) -> Any:
        """
        최종 토론 결과를 바탕으로 판결을 내립니다.
        """
        fact_str = json.dumps(fact_book, ensure_ascii=False, indent=2)
        user_prompt = self.cfg.multi_agent_prompts.verdict.judge_user.format(
            end_date=end_date,
            fact_book=fact_str,
            debate_results=debate_results
        )
        
        # Verdict는 중요하므로 스트리밍으로 결과를 보여주는 것이 좋습니다.
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        return self.llm_client.get_astream(messages)
