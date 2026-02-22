import uuid
from typing import Any
from datetime import datetime
from sqlalchemy.orm import Session
from langfuse.langchain import CallbackHandler
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage, AIMessageChunk

from .llm_client import LLMClient
from .prompt import PromptManager
from db.price_repo import PriceRepository
from db.event_repo import EventRepository
from db.article_repo import ArticleRepository
from vector_db.vector_store import VectorStore
from langfuse.types import TraceContext
from db.database import get_engine, Asset

# 도구 함수 임포트 (LangChain @tool 데코레이터 사용)
from chatbot.tools.get_period_overview import get_period_overview, set_dependencies as set_overview_deps
from chatbot.tools.search_events_by_keyword import search_events_by_keyword, set_dependencies as set_event_deps
from chatbot.tools.search_knowledge_base import search_knowledge_base, set_vector_store as set_vector_store_docs
from chatbot.tools.web_search import web_search
from chatbot.tools.extract_url_content import extract_url_content

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
            qdrant_url=vector_db_cfg.get('url'),
            embedding_cfg=rag_cfg.get('embedding')
        )
        
        self.kb_collection = vector_db_cfg.get('knowledge_base_collection', "knowledge_base")
        self.event_collection = vector_db_cfg.get('event_collection', "events")
        
        # 도구에 의존성 주입
        set_overview_deps(self.event_repo, self.price_repo)
        set_event_deps(self.vector_store, self.article_repo, collection_name=self.event_collection)
        set_vector_store_docs(self.vector_store, collection_name=self.kb_collection)

    def _sanitize_messages(self, messages: list[Any]) -> list[Any]:
        """
        Ensures strict turn order for Gemini: [Human, AI, Tool, AI, ...]
        Also merges consecutive Human messages and ensures System is only at the top.
        """
        sanitized = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                if not sanitized: sanitized.append(msg)
                continue
            
            # Stringify content to avoid JSON rendering issues
            if not isinstance(msg.content, str):
                msg.content = str(msg.content)
                
            if sanitized and isinstance(msg, HumanMessage) and isinstance(sanitized[-1], HumanMessage):
                # Merge consecutive Human messages
                sanitized[-1].content += "\n\n" + msg.content
            else:
                sanitized.append(msg)
        
        return sanitized

    def analyze_stream_agentic(
        self, 
        asset_name: str, 
        user_query: str, 
        start_date: Any, 
        end_date: Any, 
        chat_history: list[Any],
        system_prompt_override: str | None = None,
        tags: list[str] | None = None
    ):
        """
        🤖 Agentic 모드: LLM이 사용자 질문에 따라 필요한 도구만 선택하여 호출
        """
        # === 1. 시스템 프롬프트 준비 ===
        if system_prompt_override:
            persona_text = system_prompt_override
        else:
            persona_prompt = self.prompt_manager.get_system_prompt()
            persona_text = persona_prompt.compile() if hasattr(persona_prompt, "compile") else str(persona_prompt)
        
        # Data range from Config
        actual_data_start = self.cfg.system.data_range.start
        actual_data_end = self.cfg.system.data_range.end
        
        # Fetch asset full info for better grounding
        asset_info = "Unknown"
        with Session(self.engine) as session:
            asset_obj = session.query(Asset).filter(Asset.code == asset_name.upper()).first()
            if asset_obj:
                asset_info = f"{asset_obj.code} ({asset_obj.name_en or asset_obj.name_ko})"
        
        # Get today's date
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Construct context prefix
        context_prefix = (
            f"[Current date: {today}]\n"
            f"[Target Asset: {asset_info}]\n"
            f"[Ticker Symbol: {asset_name.upper()}]\n"
            f"[Available data range: {actual_data_start} ~ {actual_data_end}]\n"
            f"[User viewing range: {start_date} ~ {end_date}]\n\n"
        )
        
        # === 2. 도구 바인딩 ===
        tools = [
            get_period_overview,
            search_events_by_keyword,
            search_knowledge_base,
            extract_url_content,
            web_search
        ]
        llm_with_tools = self.client.bind_tools(tools)
        
        # === 3. 메시지 초기 구성 ===
        # Gemini is strict: Human -> AI -> Tool -> Human
        # chat_history usually contains [Human, AI, Human, AI...]
        messages: list[Any] = [SystemMessage(content=persona_text)]
        messages.extend(chat_history)
        
        # Add current request
        messages.append(HumanMessage(content=context_prefix + user_query))
        
        # Combine basic tags with custom tags
        base_tags = [asset_name, f"{start_date}~{end_date}"]
        if tags:
            base_tags.extend(tags)
            
        # Generate a unique trace ID for this entire agentic session
        trace_id = str(uuid.uuid4())
        
        # Initialize CallbackHandler ONCE with a trace context to group everything
        trace_handler = CallbackHandler(
            trace_context=TraceContext(trace_id=trace_id)
        )
        
        # We can also pass initial metadata to the trace via the first message's config or update_trace
        # However, for grouping, trace_id in trace_context is the primary mechanism.
        
        iteration_count = 0
        max_iterations = 10
        intermediate_steps: list[Any] = []
        
        while iteration_count < max_iterations:
            iteration_count += 1
            full_response = None
            
            # Sanitize before sending to API
            api_messages = self._sanitize_messages(messages)
            
            for chunk in llm_with_tools.stream(
                api_messages, 
                config={
                    "callbacks": [trace_handler],
                    "metadata": {
                        "langfuse_tags": base_tags,
                        "trace_name": "Financial Agent Analysis",
                        "asset": asset_name,
                        "query": user_query
                    }
                }
            ):
                if hasattr(chunk, "content") and chunk.content:
                    # Clean the content for streaming
                    c = chunk.content
                    text = ""
                    if isinstance(c, str): text = c
                    elif isinstance(c, list):
                        text = "".join(i.get("text", "") if isinstance(i, dict) else str(i) for i in c)
                    elif isinstance(c, dict): text = c.get("text", "")
                    
                    if text:
                        yield AIMessageChunk(content=text)
                
                if not full_response:
                    full_response = chunk
                else:
                    full_response = full_response + chunk
            
            if full_response and hasattr(full_response, 'tool_calls') and full_response.tool_calls:
                # Ensure AI message content is a string for history
                content_str = ""
                if full_response.content:
                    if isinstance(full_response.content, str): content_str = full_response.content
                    elif isinstance(full_response.content, list):
                        content_str = "".join(i.get("text", "") if isinstance(i, dict) else str(i) for i in full_response.content)
                
                ai_tool_msg = AIMessage(content=content_str, tool_calls=full_response.tool_calls)
                messages.append(ai_tool_msg)
                intermediate_steps.append(ai_tool_msg)
                
                tool_map = {
                    'get_period_overview': get_period_overview,
                    'search_events_by_keyword': search_events_by_keyword,
                    'search_knowledge_base': search_knowledge_base,
                    'extract_url_content': extract_url_content,
                    'web_search': web_search
                }
                
                for tool_call in full_response.tool_calls:
                    tool_name = tool_call['name']
                    if tool_name in tool_map:
                        try:
                            res = tool_map[tool_name].run(tool_call['args'], callbacks=[trace_handler])
                            res_msg = ToolMessage(content=str(res), tool_call_id=tool_call['id'])
                            # Yield tool result for logging/experimentation
                            yield {
                                "type": "tool_result",
                                "tool": tool_name,
                                "input": tool_call['args'],
                                "output": str(res)
                            }
                        except Exception as e:
                            res_msg = ToolMessage(content=f"Error: {str(e)}", tool_call_id=tool_call['id'])
                            yield {
                                "type": "tool_error",
                                "tool": tool_name,
                                "input": tool_call['args'],
                                "output": f"Error: {str(e)}"
                            }
                    else:
                        res_msg = ToolMessage(content=f"Tool {tool_name} not available", tool_call_id=tool_call['id'])
                    
                    messages.append(res_msg)
                    intermediate_steps.append(res_msg)
                continue
            else:
                break

        # === 4. History Persistence ===
        # Streamlit history is typically msgs.add_user_message and msgs.add_ai_message
        # We handle intermediate steps here by extending the list if possible.
        if isinstance(chat_history, list):
            # Convert internal human msg back to clean version (no context_prefix)
            chat_history.append(HumanMessage(content=user_query))
            chat_history.extend(intermediate_steps)
            
            if full_response:
                # Ensure final AI content is stringified
                f_content = full_response.content or ""
                if not isinstance(f_content, str):
                    if isinstance(f_content, list):
                        f_content = "".join(i.get("text", "") if isinstance(i, dict) else str(i) for i in f_content)
                    else:
                        f_content = str(f_content)
                chat_history.append(AIMessage(content=f_content))