import json
from typing import Any
from omegaconf import DictConfig
from chatbot.bot.llm_client import LLMClient
from langchain_core.messages import SystemMessage, HumanMessage

class AnalystAgent:
    def __init__(self, cfg: DictConfig, llm_client: LLMClient):
        self.cfg = cfg
        self.llm_client = llm_client

    async def create_fact_book(self, asset_name: str, end_date: str, event_data: list[dict[str, Any]], price_summary: str) -> dict[str, Any]:
        """
        원천 데이터를 바탕으로 Bull과 Bear가 토론할 수 있는 Fact Book을 생성합니다.
        (Stage 1: Screening -> Stage 2: Investigation)
        """
        # 1. 사건 선별 (Screening)
        event_list_str = "\n".join([f"- ID: {ev.get('id', 'N/A')}, Title: {ev.get('title', 'N/A')}" for ev in event_data])
        
        screening_system = self.cfg.multi_agent_prompts.analyst.screening_system
        screening_user = self.cfg.multi_agent_prompts.analyst.screening_user.format(
            commodity_name=asset_name,
            event_list=event_list_str,
            limit=5
        )

        screening_messages = [
            SystemMessage(content=screening_system),
            HumanMessage(content=screening_user)
        ]
        
        screening_response = self.llm_client.get_response(screening_messages)
        try:
            # JSON 형태로 ID 파싱 시도
            content = screening_response.content if hasattr(screening_response, 'content') else str(screening_response)
            # Remove markdown if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            selected_ids = json.loads(content).get("selected_event_ids", [])
        except Exception:
            # 파싱 실패 시 상위 5개 기본 선택
            selected_ids = [ev.get('id') for ev in event_data[:5]]

        selected_events = [ev for ev in event_data if ev.get('id') in selected_ids]
        if not selected_events:
            selected_events = event_data[:5]

        # 2. 데이터 보강 및 팩트 요약 (Investigation)
        investigator_system = self.cfg.multi_agent_prompts.analyst.investigator_system
        
        fact_summaries = []
        for ev in selected_events:
            investigator_user = self.cfg.multi_agent_prompts.analyst.investigator_user.format(
                raw_news_data=f"Title: {ev.get('title')}\nContent: {ev.get('content', ev.get('summary', ''))}",
                raw_price_data=price_summary
            )
            
            investigation_messages = [
                SystemMessage(content=investigator_system),
                HumanMessage(content=investigator_user)
            ]
            
            investigation_response = self.llm_client.get_response(investigation_messages)
            summary = investigation_response.content if hasattr(investigation_response, 'content') else str(investigation_response)
            fact_summaries.append({
                "id": ev.get('id'),
                "fact_summary": summary
            })

        fact_book = {
            "asset": asset_name,
            "end_date": end_date,
            "market_summary": price_summary,
            "critical_facts": fact_summaries
        }
        
        return fact_book
