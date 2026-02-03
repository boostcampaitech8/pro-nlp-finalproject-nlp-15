from langfuse import Langfuse
from langfuse.langchain import CallbackHandler
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from .llm_client import LLMClient
from .prompt import PromptManager
from db.stock_api import StockAPI
from db.news_repo import NewsRepository
from chatbot.tools.get_summary import GetSummaryTool
from chatbot.tools.search_events import SearchEventsTool

class FinancialAgent:
    def __init__(self, cfg):
        self.cfg = cfg
        self.client = LLMClient(cfg.llm)
        self.prompt_manager = PromptManager(cfg)
        
        # Initialize Tools internally
        # Initialize Tools internally
        self.stock_api = StockAPI(cfg.data.dir_path)
        self.news_repo = NewsRepository(cfg.data.event_result_path)
        self.summary_tool = GetSummaryTool(self.stock_api)
        self.events_tool = SearchEventsTool(self.news_repo, self.stock_api)

    def analyze_stream(self, asset_name, user_query, start_date, end_date, chat_history, target_files=None):
        # 0. Generate Context (Internal)
        price_context = self.summary_tool.run(asset_name, start_date, end_date)
        event_context = self.events_tool.run(asset_name, start_date, end_date, target_files=target_files, top_k=20)

        # 1. Fetch Instructions & Context Prompt
        langfuse_prompt = self.prompt_manager.get_persona_prompt()
        instruction_text = langfuse_prompt.compile() if hasattr(langfuse_prompt, "compile") else str(langfuse_prompt)
        
        context_prompt = self.prompt_manager.get_context_prompt()
        # Ensure context prompt has compile method or formatting
        if hasattr(context_prompt, "compile"):
             data_text = context_prompt.compile(
                asset_name=asset_name.upper(),
                price_context=price_context,
                event_context=event_context
            )
        else:
            data_text = f"Asset: {asset_name}\nPrice Code: {price_context}\nEvents: {event_context}"

        # 2. Build Messages
        persona_msg = SystemMessage(content=instruction_text)
        data_msg = SystemMessage(content=data_text)
        
        messages = [persona_msg, data_msg] + chat_history + [HumanMessage(content=user_query)]

        # 3. Stream Response
        # Use client.get_stream for abstraction
        trace_handler = CallbackHandler()
        return self.client.get_stream(messages, callbacks=[trace_handler])