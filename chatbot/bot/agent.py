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
from chatbot.tools.vector_search import search_similar_articles, search_similar_events, set_vector_store
from chatbot.tools.get_original_article import get_original_article

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
        self.vector_store = VectorStore()
        
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
        """
        # === 1. 도구 의존성 설정 ===
        set_events_deps(self.news_repo, self.stock_api, target_files)
        
        # === 2. 시스템 프롬프트 준비 ===
        # Langfuse에서 금융 분석가 페르소나 프롬프트 가져오기
        persona_prompt = self.prompt_manager.get_system_prompt()
        persona_text = persona_prompt.compile() if hasattr(persona_prompt, "compile") else str(persona_prompt)
        
        # === 3. 컨텍스트 정보 준비 (User Message에 포함될 prefix) ===
        # 실제 asset의 가격 데이터에서 범위 계산
        df = self.stock_api.get_price_data(asset_name)
        if not df.empty:
            actual_data_start = df['time'].min().strftime("%Y-%m-%d")
            actual_data_end = df['time'].max().strftime("%Y-%m-%d")
        else:
            # Fallback to config
            actual_data_start = self.cfg.system.data_range.start
            actual_data_end = self.cfg.system.data_range.end
        
        # 컨텍스트를 자연어로 구성 (유저 메시지 prefix로 사용)
        context_prefix = f"[현재 분석 중: {asset_name.upper()}, {start_date}~{end_date}]\n\n"
        
        # === 3. 도구 바인딩 ===
        tools = [
            get_price_summary, 
            search_volatility_events, 
            search_similar_articles, 
            search_similar_events, 
            get_original_article
        ]
        llm_with_tools = self.client.bind_tools(tools)
        
        # === 5. 메시지 구성 ===
        # System: 페르소나와 규칙만
        # User: [컨텍스트] + 실제 질문
        messages: list[SystemMessage | HumanMessage | AIMessage | ToolMessage] = list([
            SystemMessage(content=persona_text)
        ] + chat_history + [
            HumanMessage(content=context_prefix + user_query)
        ])
        
        # === 5. Tool Calling 루프 ===
        trace_handler = CallbackHandler()
        max_iterations = 5
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            full_response = None
            
            for chunk in llm_with_tools.stream(messages, config={"callbacks": [trace_handler]}):
                if full_response is None:
                    full_response = chunk
                else:
                    full_response += chunk
                
                if hasattr(chunk, 'content') and chunk.content:
                    # Content extraction logic (simplified but same effect)
                    content = chunk.content
                    if isinstance(content, list):
                        content_text = ''.join([item.get('text', str(item)) if isinstance(item, dict) else str(item) for item in content])
                    elif isinstance(content, dict):
                        content_text = content.get('text', str(content))
                    else:
                        content_text = str(content)
                    
                    if content_text:
                        yield AIMessageChunk(content=content_text)
            
            if full_response and hasattr(full_response, 'tool_calls') and full_response.tool_calls:
                messages.append(AIMessage(content=full_response.content or "", tool_calls=full_response.tool_calls))
                
                tool_map = {
                    'get_price_summary': get_price_summary,
                    'search_volatility_events': search_volatility_events,
                    'search_similar_articles': search_similar_articles,
                    'search_similar_events': search_similar_events,
                    'get_original_article': get_original_article
                }
                
                for tool_call in full_response.tool_calls:
                    tool_name = tool_call['name']
                    tool_args = tool_call['args']
                    
                    if tool_name in tool_map:
                        try:
                            tool_result = tool_map[tool_name].run(tool_args)
                            messages.append(ToolMessage(content=str(tool_result), tool_call_id=tool_call['id']))
                        except Exception as e:
                            messages.append(ToolMessage(content=f"Error: {str(e)}", tool_call_id=tool_call['id']))
                continue
            else:
                break
    
    def analyze_stream(self, asset_name, user_query, start_date, end_date, chat_history, target_files=None):
        """
        📋 Legacy 모드: 모든 컨텍스트를 미리 주입 (Tool Calling 없음)
        """
        # 도구 의존성 설정
        set_events_deps(self.news_repo, self.stock_api, target_files)
        
        # === 1. 모든 도구를 미리 실행 ===
        # --- NEW: Invoke tools directly for legacy mode ---
        price_context = get_price_summary.run({
            "asset_name": asset_name,
            "start_date": str(start_date),
            "end_date": str(end_date)
        })
        event_context = search_volatility_events.run({
            "asset_name": asset_name,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "top_k": 20
        })

        # --- NEW: Add Semantic Context if relevant to query ---
        semantic_context = ""
        if len(user_query) > 5:
            # Using articles search for legacy context enrichment
            rel_articles = search_similar_articles.run({
                "query": user_query, 
                "top_k": 5,
                "start_date": str(start_date),
                "end_date": str(end_date)
            })
            if rel_articles:
                semantic_context = "\n[Semantic Related Context]\n" + rel_articles

        # === 2. 프롬프트 가져오기 ===
        langfuse_prompt = self.prompt_manager.get_system_prompt()
        instruction_text = langfuse_prompt.compile() if hasattr(langfuse_prompt, "compile") else str(langfuse_prompt)
        
        
        # 데이터 컨텍스트를 직접 구성
        data_text = f"Asset: {asset_name}\nPrice Context: {price_context}\nEvents: {event_context}"

        # === 3. 메시지 구성 ===
        messages = [SystemMessage(content=instruction_text), SystemMessage(content=data_text)] + chat_history + [HumanMessage(content=user_query)]

        # === 4. LLM 스트리밍 ===
        trace_handler = CallbackHandler()
        return self.client.get_stream(messages, callbacks=[trace_handler])