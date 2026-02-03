from langfuse import Langfuse
from langfuse.langchain import CallbackHandler
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage, AIMessageChunk

from .llm_client import LLMClient
from .prompt import PromptManager
from db.stock_api import StockAPI
from db.news_repo import NewsRepository
from db.vector_store import VectorStore

# 도구 함수 임포트 (LangChain @tool 데코레이터 사용)
from chatbot.tools.get_summary import get_price_summary, set_stock_api
from chatbot.tools.search_events import search_volatility_events, set_dependencies as set_events_deps
from chatbot.tools.vector_search import search_similar_events, set_vector_store

class FinancialAgent:
    """
    금융 분석 에이전트
    
    두 가지 모드 지원:
    1. analyze_stream_agentic: LLM이 필요한 도구를 동적으로 선택 (Tool Calling)
    2. analyze_stream: 모든 컨텍스트를 미리 주입 (Legacy)
    """
    
    def __init__(self, cfg):
        """
        에이전트 초기화
        
        Args:
            cfg: Hydra 설정 객체
        """
        self.cfg = cfg
        self.client = LLMClient(cfg.llm)
        self.prompt_manager = PromptManager(cfg)
        
        # 데이터 소스 초기화
        self.stock_api = StockAPI(cfg.data.dir_path)
        self.news_repo = NewsRepository(cfg.data.event_result_path)
        self.vector_store = VectorStore()  # 현재는 Placeholder
        
        # 도구에 의존성 주입 (도구는 순수 함수지만 데이터 소스가 필요함)
        set_stock_api(self.stock_api)
        set_vector_store(self.vector_store)

    def analyze_stream_agentic(
        self, 
        asset_name: str, 
        user_query: str, 
        start_date, 
        end_date, 
        chat_history: list,
        target_files: list[str] | None = None
    ):
        """
        🤖 Agentic 모드: LLM이 사용자 질문에 따라 필요한 도구만 선택하여 호출
        
        동작 원리:
        1. LLM에게 사용 가능한 도구 목록 제공
        2. LLM이 질문을 분석하고 필요한 도구 선택
        3. 도구 실행 후 결과를 LLM에게 다시 전달
        4. LLM이 최종 답변 생성
        
        Args:
            asset_name: 자산 이름 (예: "copper")
            user_query: 사용자 질문
            start_date: 분석 시작일 (date 객체)
            end_date: 분석 종료일 (date 객체)
            chat_history: 이전 대화 기록 (Message 객체 리스트)
            target_files: 검색할 이벤트 파일 목록 (선택)
            
        Yields:
            AIMessageChunk: 스트리밍 응답 청크
        """
        # === 1. 도구 의존성 설정 ===
        # search_volatility_events 도구가 사용할 데이터 소스 주입
        set_events_deps(self.news_repo, self.stock_api, target_files)
        
        # === 2. 시스템 프롬프트 준비 ===
        # Langfuse에서 금융 분석가 페르소나 프롬프트 가져오기
        persona_prompt = self.prompt_manager.get_persona_prompt()
        persona_text = persona_prompt.compile() if hasattr(persona_prompt, "compile") else str(persona_prompt)
        
        # 현재 분석 컨텍스트 정보 (자산, 기간, 사용 가능한 도구)
        context_info = f"""
You are analyzing {asset_name.upper()} from {start_date} to {end_date}.

You have access to the following tools to fetch data:
- get_price_summary: Get price statistics (return, volatility)
- search_volatility_events: Find major events on volatile days
- search_similar_events: Search events by topic/theme

Use these tools ONLY when needed to answer the user's question.
If the user asks about prices or returns, use get_price_summary.
If they ask "why" or about specific events, use search_volatility_events.
For thematic searches, use search_similar_events.

IMPORTANT: The date parameters must be in YYYY-MM-DD format.
asset_name is: {asset_name}
start_date is: {start_date}
end_date is: {end_date}
"""
        
        # === 3. 도구 바인딩 ===
        # LLM에게 사용 가능한 도구 목록 제공
        tools = [get_price_summary, search_volatility_events, search_similar_events]
        llm_with_tools = self.client.bind_tools(tools)
        
        # === 4. 메시지 구성 ===
        # [시스템 프롬프트] + [대화 기록] + [사용자 질문]
        # messages는 다양한 메시지 타입을 담을 수 있음
        messages: list[SystemMessage | HumanMessage | AIMessage | ToolMessage] = list([
            SystemMessage(content=persona_text + "\n\n" + context_info)
        ] + chat_history + [
            HumanMessage(content=user_query)
        ])
        
        # === 5. Tool Calling 루프 ===
        trace_handler = CallbackHandler()  # Langfuse 트레이싱
        max_iterations = 5  # 무한 루프 방지
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # --- 5-1. LLM 호출 (스트리밍) ---
            # full_response는 청크들이 합쳐진 결과 (타입은 복잡하므로 Any 사용)
            from typing import Any
            full_response: Any = None  # 전체 응답 누적용
            
            for chunk in llm_with_tools.stream(messages, config={"callbacks": [trace_handler]}):
                # 청크를 누적하여 전체 응답 생성 (tool_calls 감지용)
                if full_response is None:
                    full_response = chunk
                else:
                    full_response += chunk
                    
                # 사용자에게 스트리밍할 텍스트 추출
                if hasattr(chunk, 'content') and chunk.content:
                    content = chunk.content
                    
                    # Gemini는 content를 리스트로 반환할 수 있음
                    # 예: [{"text": "안녕하세요"}, {"text": "..."}]
                    if isinstance(content, list):
                        text_parts = []
                        for item in content:
                            if isinstance(item, dict):
                                text_parts.append(item.get('text', ''))
                            elif isinstance(item, str):
                                text_parts.append(item)
                            else:
                                text_parts.append(str(item))
                        content_text = ''.join(text_parts)
                    elif isinstance(content, dict):
                        # content가 딕셔너리면 'text' 필드 추출
                        content_text = content.get('text', str(content))
                    else:
                        # 이미 문자열
                        content_text = str(content)
                    
                    # 실제 텍스트가 있을 때만 yield
                    if content_text:
                        yield AIMessageChunk(content=content_text)
            
            # --- 5-2. Tool Call 확인 ---
            # LLM이 도구를 호출하려는지 확인
            if full_response and hasattr(full_response, 'tool_calls') and full_response.tool_calls:
                # Tool call이 있음! 도구 실행 필요
                
                # LLM의 응답(도구 호출 요청)을 메시지 히스토리에 추가
                messages.append(AIMessage(
                    content=full_response.content or "", 
                    tool_calls=full_response.tool_calls
                ))
                
                # 각 도구 호출 실행
                for tool_call in full_response.tool_calls:
                    tool_name = tool_call['name']  # 예: "get_price_summary"
                    tool_args = tool_call['args']  # 예: {"asset_name": "copper", ...}
                    
                    # 도구 맵핑
                    tool_map = {
                        'get_price_summary': get_price_summary,
                        'search_volatility_events': search_volatility_events,
                        'search_similar_events': search_similar_events
                    }
                    
                    # 도구 실행
                    if tool_name in tool_map:
                        try:
                            # 도구 호출
                            tool_result = tool_map[tool_name].invoke(tool_args)
                            
                            # 도구 결과를 메시지 히스토리에 추가
                            messages.append(ToolMessage(
                                content=str(tool_result), 
                                tool_call_id=tool_call['id']
                            ))
                        except Exception as e:
                            # 도구 실행 오류 시 에러 메시지 추가
                            messages.append(ToolMessage(
                                content=f"Error: {str(e)}", 
                                tool_call_id=tool_call['id']
                            ))
                
                # --- 5-3. 다음 루프로 ---
                # messages에 도구 결과가 추가되었으므로
                # 다음 iteration에서 LLM이 이를 보고 최종 답변 생성
                continue
            else:
                # Tool call 없음 → LLM이 최종 답변을 생성했음 → 종료
                break
    
    def analyze_stream(
        self, 
        asset_name: str, 
        user_query: str, 
        start_date, 
        end_date, 
        chat_history: list,
        target_files: list[str] | None = None
    ):
        """
        📋 Legacy 모드: 모든 컨텍스트를 미리 주입 (Tool Calling 없음)
        
        동작 원리:
        1. 모든 도구를 미리 실행 (get_price_summary + search_volatility_events)
        2. 결과를 시스템 메시지로 주입
        3. LLM이 주입된 데이터만 보고 답변 생성
        
        장점: 빠름 (LLM 호출 1회)
        단점: 불필요한 데이터도 항상 로드 (토큰 낭비)
        """
        # 도구 의존성 설정
        set_events_deps(self.news_repo, self.stock_api, target_files)
        
        # === 1. 모든 도구를 미리 실행 ===
        price_context = get_price_summary.invoke({
            "asset_name": asset_name,
            "start_date": str(start_date),
            "end_date": str(end_date)
        })
        event_context = search_volatility_events.invoke({
            "asset_name": asset_name,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "top_k": 20
        })

        # === 2. 프롬프트 가져오기 ===
        langfuse_prompt = self.prompt_manager.get_persona_prompt()
        instruction_text = langfuse_prompt.compile() if hasattr(langfuse_prompt, "compile") else str(langfuse_prompt)
        
        # 데이터 컨텍스트 프롬프트 (Langfuse에서 관리)
        context_prompt = self.prompt_manager.get_context_prompt()
        if hasattr(context_prompt, "compile"):
             data_text = context_prompt.compile(
                asset_name=asset_name.upper(),
                price_context=price_context,
                event_context=event_context
            )
        else:
            # Fallback: 템플릿 없으면 직접 조합
            data_text = f"Asset: {asset_name}\nPrice Context: {price_context}\nEvents: {event_context}"

        # === 3. 메시지 구성 ===
        # [페르소나] + [데이터 컨텍스트] + [대화 기록] + [사용자 질문]
        persona_msg = SystemMessage(content=instruction_text)
        data_msg = SystemMessage(content=data_text)
        
        messages = [persona_msg, data_msg] + chat_history + [HumanMessage(content=user_query)]

        # === 4. LLM 스트리밍 (도구 호출 없음) ===
        trace_handler = CallbackHandler()
        return self.client.get_stream(messages, callbacks=[trace_handler])