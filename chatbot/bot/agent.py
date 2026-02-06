from typing import Any
from datetime import datetime
from typing import Any
from langfuse.langchain import CallbackHandler
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage, AIMessageChunk

from .llm_client import LLMClient
from .prompt import PromptManager
from db.price_repo import PriceRepository
from db.event_repo import EventRepository
from db.article_repo import ArticleRepository
from vector_db.vector_store import VectorStore
from db.database import get_engine

# 도구 함수 임포트 (LangChain @tool 데코레이터 사용)
from chatbot.tools.get_period_overview import get_period_overview, set_dependencies as set_overview_deps
from chatbot.tools.search_events_by_keyword import search_events_by_keyword, set_dependencies as set_event_deps
from chatbot.tools.search_knowledge_base import search_knowledge_base, set_vector_store as set_vector_store_docs
from chatbot.tools.web_browser import extract_url_content, web_search
from chatbot.tools.vector_search import search_similar_articles, search_similar_events, set_vector_store as set_vector_store_vs
from chatbot.tools.get_original_article import get_original_article

from omegaconf import DictConfig

class FinancialAgent:
    """
    금융 분석 에이전트
    
    두 가지 모드 지원:
    1. analyze_stream_agentic: LLM이 필요한 도구를 동적으로 선택 (Tool Calling)
    """
    
    def __init__(self, cfg: DictConfig):
        """
        에이전트 초기화
        
        Args:
            cfg: Hydra 설정 객체
        """
        self.cfg = cfg
        self.client = LLMClient(cfg.llm)
        self.prompt_manager = PromptManager(cfg)
        
        # 데이터 소스 초기화
        db_cfg = cfg.get('database', {})
        self.engine = get_engine(db_cfg)
        self.price_repo = PriceRepository(self.engine)
        self.event_repo = EventRepository(self.engine)
        self.article_repo = ArticleRepository(self.engine)
        
        # Initialize VectorStore (shared embedding engine)
        rag_cfg = cfg.get('rag', {})
        vector_db_cfg = rag_cfg.get('vector_db', {})
        self.vector_store = VectorStore(
            qdrant_url=vector_db_cfg.get('url')
        )
        
        self.kb_collection = vector_db_cfg.get('knowledge_base_collection', "knowledge_base")
        self.event_collection = vector_db_cfg.get('event_collection', "events")
        
        # 도구에 의존성 주입
        set_overview_deps(self.event_repo, self.price_repo)
        set_event_deps(self.vector_store, self.article_repo, collection_name=self.event_collection)
        set_vector_store_docs(self.vector_store, collection_name=self.kb_collection)
        set_vector_store_vs(self.vector_store)

    def analyze_stream_agentic(
        self, 
        asset_name: str, 
        user_query: str, 
        start_date: Any, 
        end_date: Any, 
        chat_history: list[Any]
    ):
        """
        🤖 Agentic 모드: LLM이 사용자 질문에 따라 필요한 도구만 선택하여 호출
        """
        # === 1. 도구 의존성 설정 ===
        # (get_period_overview uses news_repo and stock_api already set in __init__)
        
        # === 2. 시스템 프롬프트 준비 ===
        # Langfuse에서 금융 분석가 페르소나 프롬프트 가져오기
        persona_prompt = self.prompt_manager.get_system_prompt()
        persona_text = persona_prompt.compile() if hasattr(persona_prompt, "compile") else str(persona_prompt)
        
        # === 3. 컨텍스트 정보 준비 (User Message에 포함될 prefix) ===
        # 실제 asset의 가격 데이터에서 범위 계산
        df = self.price_repo.get_prices(asset_name)
        if not df.empty:
            actual_data_start = df['time'].min().strftime("%Y-%m-%d")
            actual_data_end = df['time'].max().strftime("%Y-%m-%d")
        else:
            # Fallback to config
            actual_data_start = self.cfg.system.data_range.start
            actual_data_end = self.cfg.system.data_range.end
        
        # Get today's date
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Construct context prefix with English labels
        context_prefix = (
            f"[Current date: {today}]\n"
            f"[Available data range: {asset_name.upper()}, {actual_data_start} ~ {actual_data_end}]\n"
            f"[User viewing range: {asset_name.upper()}, {start_date} ~ {end_date}]\n\n"
        )
        
        # === 4. 도구 바인딩 (Consolidated 3-tool set) ===
        tools = [
            get_period_overview,
            search_events_by_keyword,
            search_knowledge_base,
            extract_url_content,
            search_similar_articles,
            search_similar_events,
            get_original_article,
            web_search
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
        
        # === 5. Langfuse Tags 자동 생성 ===
        tags = [
            asset_name,
            f"{start_date}~{end_date}"
        ]
        
        # === 6. Tool Calling 루프 ===
        trace_handler = CallbackHandler()
        iteration_count = 0
        max_iterations = 10
        
        while iteration_count < max_iterations:
            iteration_count += 1
            full_response = None
            
            # config에 metadata={"langfuse_tags": tags} 추가하여 태그 전파
            # Remove blocking synchronous callback (trace_handler) for smooth streaming
            for chunk in llm_with_tools.stream(
                messages, 
                config={"metadata": {"langfuse_tags": tags}}
            ):
                if hasattr(chunk, "content") and chunk.content:
                    # Handle different content types
                    content = chunk.content
                    if isinstance(content, str):
                        content_text = content
                    elif isinstance(content, list):
                        # Extract text from list of content blocks
                        content_text = ''.join([
                            item.get('text', '') if isinstance(item, dict) else str(item)
                            for item in content
                        ])
                    elif isinstance(content, dict):
                        # Extract text field from dict
                        content_text = content.get('text', '')
                    else:
                        content_text = str(content)
                    
                    if content_text:
                        yield AIMessageChunk(content=content_text)
                
                if not full_response:
                    full_response = chunk
                else:
                    full_response = full_response + chunk
            
            if full_response and hasattr(full_response, 'tool_calls') and full_response.tool_calls:
                messages.append(AIMessage(content=full_response.content or "", tool_calls=full_response.tool_calls))
                # Map tool names to their functions
                tool_map = {
                    'get_period_overview': get_period_overview,
                    'search_events_by_keyword': search_events_by_keyword,
                    'search_knowledge_base': search_knowledge_base,
                    'extract_url_content': extract_url_content,
                    'search_similar_articles': search_similar_articles,
                    'search_similar_events': search_similar_events,
                    'get_original_article': get_original_article,
                    'web_search': web_search
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
                    else:
                        messages.append(ToolMessage(content=f"Tool {tool_name} not available", tool_call_id=tool_call['id']))
                continue
            else:
                break

        # === 7. History Persistence ===
        # Update the external chat_history with intermediate acts (Tools)
        # We assume chatbot_app.py adds the User(query) and Final AI(response).
        # We need to save the "Thought Process" (Tool Calls & Outputs) in between.
        
        # messages layout: [System, History..., User(Context), AI(Tool), Tool, ..., AI(Final)]
        new_msgs_start_idx = 1 + len(chat_history)
        
        if new_msgs_start_idx < len(messages):
            # new_interactions = [User(Context), AI(Tool), Tool, ..., AI(Final)]
            new_interactions = messages[new_msgs_start_idx:]
            
            # We want to keep ONLY the intermediate steps: [AI(Tool), Tool, ...]
            # Exclude first (User) and last (Final AI)
            if len(new_interactions) > 2:
                intermediate_steps = new_interactions[1:-1]
                
                # Append to mutable chat_history list
                if isinstance(chat_history, list):
                    chat_history.extend(intermediate_steps)