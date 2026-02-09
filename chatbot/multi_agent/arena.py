from typing import Any, AsyncGenerator
from omegaconf import DictConfig
from chatbot.bot.llm_client import LLMClient
from chatbot.multi_agent.analyst import AnalystAgent
from chatbot.multi_agent.bull import BullAgent
from chatbot.multi_agent.bear import BearAgent
from chatbot.multi_agent.verdict import VerdictAgent

class Arena:
    def __init__(self, cfg: DictConfig, llm_client: LLMClient):
        self.cfg = cfg
        self.analyst = AnalystAgent(cfg, llm_client)
        self.bull = BullAgent(cfg, llm_client)
        self.bear = BearAgent(cfg, llm_client)
        self.verdict = VerdictAgent(cfg, llm_client)

    def _extract_text(self, content: Any) -> str:
        """AIMessageChunk.content에서 텍스트만 추출합니다."""
        if not content:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(i.get("text", "") if isinstance(i, dict) else str(i) for i in content)
        if isinstance(content, dict):
            return content.get("text", "")
        return str(content)

    async def run_debate_stream(
        self, 
        asset_name: str, 
        end_date: str, 
        event_data: list[dict[str, Any]], 
        price_summary: str,
        rounds: int = 1
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        토론 과정을 스트리밍 형식으로 생성합니다.
        """
        # 1. Analyst: Fact Book 생성
        yield {"status": "analyzing", "message": "Analyst가 팩트북을 작성 중입니다..."}
        fact_book = await self.analyst.create_fact_book(asset_name, end_date, event_data, price_summary)
        yield {"status": "fact_book", "content": fact_book}

        debate_log = []
        last_bull_msg = ""
        
        # 2. Debate Rounds
        for i in range(rounds):
            round_no = i + 1
            
            # 1) Bear's turn
            if round_no == 1:
                yield {"status": "bear_warning", "message": f"Round {round_no}: Bear의 하락 리스크 경고 중..."}
                bear_stream = await self.bear.initial_warning(fact_book)
            else:
                yield {"status": "bear_warning", "message": f"Round {round_no}: Bear가 Bull의 논리를 반박 중..."}
                bear_stream = await self.bear.counter_argue(fact_book, bull_argument=last_bull_msg)
            
            full_bear_msg = ""
            async for chunk in bear_stream:
                if hasattr(chunk, 'content'):
                    text = self._extract_text(chunk.content)
                    full_bear_msg += text
                    yield {"status": "bear_stream", "chunk": text}
            debate_log.append(f"BEAR: {full_bear_msg}")

            # 2) Bull's turn
            yield {"status": "bull_argue", "message": f"Round {round_no}: Bull이 Bear의 논리를 반격 중..."}
            bull_stream = await self.bull.argue(fact_book, opponent_arg=full_bear_msg)
            
            full_bull_msg = ""
            async for chunk in bull_stream:
                if hasattr(chunk, 'content'):
                    text = self._extract_text(chunk.content)
                    full_bull_msg += text
                    yield {"status": "bull_stream", "chunk": text}
            debate_log.append(f"BULL: {full_bull_msg}")
            last_bull_msg = full_bull_msg

        # 3. Verdict: 최종 판결
        yield {"status": "judging", "message": "Verdict가 최종 판결문을 작성 중입니다..."}
        debate_results = "\n".join(debate_log)
        verdict_stream = await self.verdict.judge(end_date, fact_book, debate_results)
        async for chunk in verdict_stream:
            if hasattr(chunk, 'content'):
                text = self._extract_text(chunk.content)
                yield {"status": "verdict_stream", "chunk": text}
