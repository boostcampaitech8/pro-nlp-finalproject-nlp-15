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
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124'}

    async def select_priority_events(self, commodity_name: str, events: list, limit: int = 3) -> list:
        """LLM 판단을 통해 가장 중요한 사건들만 골라냅니다."""
        if len(events) <= limit: return events
        
        # 1. 후보 리스트 텍스트화 (토큰 절약을 위해 제목 위주로 구성)
        event_list_str = "\n".join([
            f"- ID: {e['event_metadata']['event_id']} | 제목: {e['event_core']['title']}"
            for e in events
        ])

        prompt = self.cfg.prompts.analyst.screening_user.format(
            commodity_name=commodity_name, event_list=event_list_str, limit=limit
        )
        
        # task_type="schema"로 낮은 온도(0.1) 적용
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
        """하이브리드 크롤링 (Jina -> Trafilatura)"""
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
        """수집된 원문과 시세를 바탕으로 최종 요약을 생성합니다."""
        # content_full이 없으면 description이라도 사용
        raw_news = "\n".join([f"[{n['title']}]\n{n.get('content_full', n.get('description', ''))}" for n in event['news_evidence']])
        raw_price = str(event['market_evidence']['prices'])

        prompt = self.cfg.prompts.analyst.investigator_user.format(
            raw_news_data=raw_news[:4500], raw_price_data=raw_price
        )
        
        # ⚠️ 오타 수정: task_type="analyis" -> "analysis"
        summary = await send_llmapi(
            prompt=prompt, cfg=self.cfg, role="master", task_type="analysis",
            system_prompt=self.cfg.prompts.analyst.investigator_system
        )
        event['event_core']['summary'] = summary

    async def create_enriched_fact_book(self, commodity_name: str, end_date: str, n_days: int = 30) -> dict:
        """예측을 위한 고농축 팩트북 생성 파이프라인"""
        # 1. ⚠️ DB 메서드 인자 수정: (commodity, start, end) -> (commodity, end, n_days)
        fact_book = self.db_manager.get_batch_fact_book(commodity_name, end_date, n_days)
        all_events = fact_book.get('events', [])
        if not all_events: return fact_book

        # 2. 핵심 사건 선별
        selected_events = await self.select_priority_events(commodity_name, all_events)
        
        # 3. 비동기 크롤링 (선별된 사건만)
        async with aiohttp.ClientSession() as session:
            tasks = []
            for ev in selected_events:
                for news in ev.get('news_evidence', []):
                    tasks.append(self._fetch_with_fallback(session, news))
            if tasks: await asyncio.gather(*tasks)

        # 4. 최종 팩트 요약 생성
        summary_tasks = [self.generate_fact_summary(ev) for ev in selected_events]
        await asyncio.gather(*summary_tasks)

        fact_book['events'] = selected_events
        fact_book['analysis_metadata']['total_events_found'] = len(selected_events)
        return fact_book