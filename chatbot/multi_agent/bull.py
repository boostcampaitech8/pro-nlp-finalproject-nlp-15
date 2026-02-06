import json
from typing import Any
from omegaconf import DictConfig
from chatbot.bot.llm_client import LLMClient
from langchain_core.messages import SystemMessage, HumanMessage

class BullAgent:
    def __init__(self, cfg: DictConfig, llm_client: LLMClient):
        self.cfg = cfg
        self.llm_client = llm_client
        self.system_prompt = cfg.multi_agent_prompts.bull.system

    async def argue(self, fact_book: dict[str, Any], opponent_arg: str = "") -> Any:
        """
        상승 시나리오를 주장하거나 상대방의 반론에 응답합니다.
        """
        fact_str = json.dumps(fact_book, ensure_ascii=False, indent=2)
        opp_text = opponent_arg if opponent_arg else "내일의 시장 상승 시나리오를 데이터 기반으로 제시하십시오."
        
        user_prompt = self.cfg.multi_agent_prompts.bull.argue_user.format(
            fact_book=fact_str,
            opponent_arg=opp_text
        )
        
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        return self.llm_client.get_stream(messages)
