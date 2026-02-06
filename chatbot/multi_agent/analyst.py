import json
from typing import Any
from omegaconf import DictConfig
from chatbot.bot.llm_client import LLMClient
from langchain_core.messages import SystemMessage, HumanMessage

class AnalystAgent:
    def __init__(self, cfg: DictConfig, llm_client: LLMClient):
        self.cfg = cfg
        self.llm_client = llm_client
        self.system_prompt = cfg.multi_agent_prompts.analyst.system

    async def create_fact_book(self, asset_name: str, end_date: str, event_data: list[dict[str, Any]], price_summary: str) -> dict[str, Any]:
        """
        원천 데이터를 바탕으로 Bull과 Bear가 토론할 수 있는 Fact Book을 생성합니다.
        """
        # 현재는 간단하게 event_data와 price_summary를 결합하여 반환하거나,
        # LLM을 통해 한 번 거른 뒤 팩트북으로 사용합니다.
        
        events_str = json.dumps(event_data, ensure_ascii=False, indent=2)
        user_prompt = self.cfg.multi_agent_prompts.analyst.select_user.format(
            events=events_str
        )
        
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        # 선별된 사건 리스트 요청
        response = self.llm_client.get_response(messages)
        selected_content = response.content if hasattr(response, 'content') else str(response)

        fact_book = {
            "asset": asset_name,
            "end_date": end_date,
            "market_summary": price_summary,
            "critical_events": selected_content
        }
        
        return fact_book
