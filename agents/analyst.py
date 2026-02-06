# agents/analyst.py (최종 정리본)
import asyncio
import aiohttp
import trafilatura
import json
from core.db import DBManager
from core.llm import send_llmapi
from omegaconf import DictConfig

class AnalystAgent:
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        self.db_manager = DBManager(cfg)

    async def select_priority_events(self, commodity_name: str, events: list, limit: int = 3) -> list:
        """LLM 판단을 통해 가장 중요한 사건들만 골라냅니다."""
        if len(events) <= limit: return events
        
        event_list_str = "\n".join([
            f"- ID: {e['event_metadata']['event_id']} | 제목: {e['event_core']['title']}"
            for e in events
        ])

        prompt = self.cfg.prompts.analyst.screening_user.format(
            commodity_name=commodity_name, event_list=event_list_str, limit=limit
        )
        
        response = await send_llmapi(
            prompt=prompt, cfg=self.cfg, role="master", task_type="schema",
            system_prompt=self.cfg.prompts.analyst.screening_system.format(limit=limit, commodity_name=commodity_name)
        )

        try:
            selected_ids = json.loads(response).get("selected_event_ids", [])
            return [e for e in events if e['event_metadata']['event_id'] in selected_ids]
        except:
            return events[:limit] 

    async def _fetch_with_fallback(self, session, news_obj):
        """URL로부터 본문을 수집하여 news_obj['content_full']을 업데이트합니다."""
        url = news_obj.get('doc_url')
        if not url or not url.startswith('http'): return

        try:
            async with session.get(f"https://r.jina.ai/{url}", timeout=10) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    if len(text) > 300:
                        news_obj['content_full'] = text[:3000]
                        return
        except: pass

        try:
            loop = asyncio.get_event_loop()
            downloaded = await loop.run_in_executor(None, trafilatura.fetch_url, url)
            if downloaded:
                result = await loop.run_in_executor(None, trafilatura.extract, downloaded)
                if result: news_obj['content_full'] = result[:3000]
        except: pass

    async def generate_fact_summary(self, event: dict):
        """본문과 시세를 대조하여 'event_core.summary'를 팩트 위주로 재작성합니다."""
        raw_news = "\n".join([f"[{n['title']}]\n{n.get('content_full', n.get('description', ''))}" for n in event['news_evidence']])
        raw_price = str(event['market_evidence']['prices'])

        prompt = self.cfg.prompts.analyst.investigator_user.format(
            raw_news_data=raw_news[:4500], raw_price_data=raw_price
        )
        
        summary = await send_llmapi(
            prompt=prompt, cfg=self.cfg, role="master", task_type="analysis",
            system_prompt=self.cfg.prompts.analyst.investigator_system
        )
        event['event_core']['summary'] = summary

    async def create_enriched_fact_book(self, commodity_name: str, end_date: str, n_days: int = 30) -> dict:
        """[핵심] DB 데이터를 불러와 LLM으로 가공된 최종 팩트북을 생성합니다."""
        # 1. 원시 데이터 로드 (DBManager의 역할)
        fact_book = self.db_manager.get_batch_fact_book(commodity_name, end_date, n_days)
        all_events = fact_book.get('events', [])
        if not all_events: return fact_book

        # 2. 사건 선별 (Analyst의 지능적 역할)
        selected_events = await self.select_priority_events(commodity_name, all_events)
        
        # 3. 데이터 보강 (크롤링 및 요약)
        async with aiohttp.ClientSession() as session:
            tasks = [self._fetch_with_fallback(session, news) for ev in selected_events for news in ev.get('news_evidence', [])]
            if tasks: await asyncio.gather(*tasks)

        summary_tasks = [self.generate_fact_summary(ev) for ev in selected_events]
        await asyncio.gather(*summary_tasks)

        # 4. 최종 가공된 데이터로 업데이트
        fact_book['events'] = selected_events
        fact_book['analysis_metadata']['total_events_found'] = len(selected_events)
        return fact_book
