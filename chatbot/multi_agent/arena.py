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
        
        # 2. Debate Rounds
        for i in range(rounds):
            round_no = i + 1
            
            # Bear 선공 (cfg에서 결정 가능하지만 여기선 고정 또는 로직 추가 가능)
            yield {"status": "bear_warning", "message": f"Round {round_no}: Bear의 하락 리스크 경고 중..."}
            bear_stream = await self.bear.initial_warning(fact_book)
            full_bear_msg = ""
            async for chunk in bear_stream:
                if hasattr(chunk, 'content'):
                    full_bear_msg += chunk.content
                    yield {"status": "bear_stream", "chunk": chunk.content}
            debate_log.append(f"BEAR: {full_bear_msg}")

            # Bull 반격
            yield {"status": "bull_argue", "message": f"Round {round_no}: Bull의 상승 시나리오 반격 중..."}
            bull_stream = await self.bull.argue(fact_book, opponent_arg=full_bear_msg)
            full_bull_msg = ""
            async for chunk in bull_stream:
                if hasattr(chunk, 'content'):
                    full_bull_msg += chunk.content
                    yield {"status": "bull_stream", "chunk": chunk.content}
            debate_log.append(f"BULL: {full_bull_msg}")

        # 3. Verdict: 최종 판결
        yield {"status": "judging", "message": "Verdict가 최종 판결문을 작성 중입니다..."}
        debate_results = "\n".join(debate_log)
        verdict_stream = await self.verdict.judge(end_date, fact_book, debate_results)
        async for chunk in verdict_stream:
            if hasattr(chunk, 'content'):
                yield {"status": "verdict_stream", "chunk": chunk.content}
