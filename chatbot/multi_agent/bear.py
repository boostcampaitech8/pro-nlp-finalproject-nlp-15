import json
from typing import Any
from omegaconf import DictConfig
from chatbot.bot.llm_client import LLMClient
from langchain_core.messages import SystemMessage, HumanMessage

class BearAgent:
    def __init__(self, cfg: DictConfig, llm_client: LLMClient):
        self.cfg = cfg
        self.llm_client = llm_client
        self.system_prompt = cfg.multi_agent_prompts.bear.system

    async def initial_warning(self, fact_book: dict[str, Any]) -> Any:
        """
        팩트북을 바탕으로 하락 리스크를 먼저 경고합니다 (Bear 선공 시).
        """
        fact_str = json.dumps(fact_book, ensure_ascii=False, indent=2)
        user_prompt = self.cfg.multi_agent_prompts.bear.initial_user.format(
            fact_book=fact_str
        )
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_prompt)
        ]
        return self.llm_client.get_stream(messages)

    async def counter_argue(self, fact_book: dict[str, Any], bull_argument: str) -> Any:
        """
        상승 논리의 허점을 반박합니다.
        """
        fact_str = json.dumps(fact_book, ensure_ascii=False, indent=2)
        user_prompt = self.cfg.multi_agent_prompts.bear.counter_user.format(
            fact_book=fact_str,
            bull_argument=bull_argument
        )
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_prompt)
        ]
        return self.llm_client.get_stream(messages)
