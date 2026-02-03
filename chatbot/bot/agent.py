from langfuse import Langfuse
from chatbot.llm_client import LLMClient
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

class FinancialAgent:
    def __init__(self, cfg):
        self.cfg = cfg
        self.client = LLMClient(cfg.llm)
        self.langfuse = Langfuse()

    def analyze_stream(self, asset_name, user_query, price_context, event_context, chat_history):
        # 1. 지침(Instruction) 로드 - 변수 주입 없이 순수 지침만 가져옴
        prompt_name = self.cfg.prompts.financial_analysis
        langfuse_prompt = self.langfuse.get_prompt(prompt_name)
        instruction_text = langfuse_prompt.compile() # 변수 없음
        
        # 2. 시스템 메시지 계층화 (Layering)
        # Layer 1: 페르소나 및 기본 지침
        persona_msg = SystemMessage(content=instruction_text)
        
        # Layer 2: 참조 데이터 (Reference Data)
        # System Message로 구성하여 대화 내역(History)과 분리된 '배경 지식'임을 명시
        # Langfuse에서 데이터 템플릿 로드
        context_prompt_name = self.cfg.prompts.financial_context
        context_prompt = self.langfuse.get_prompt(context_prompt_name)
        
        data_text = context_prompt.compile(
            asset_name=asset_name.upper(),
            price_context=price_context,
            event_context=event_context
        )
        data_msg = SystemMessage(content=data_text)

        # 3. 메시지 결합: [Persona] -> [Data] -> [History] -> [User Query]
        # Chat history is assumed to be a list of Langchain Message objects
        messages = [persona_msg, data_msg] + chat_history + [HumanMessage(content=user_query)]

        # 4. LLM 호출 (Langfuse Callback Handler 추가)
        # extract/llm_client.py의 패턴을 따름 (langfuse.langchain 모듈 사용)
        from langfuse.langchain import CallbackHandler
        trace_handler = CallbackHandler()
        
        return self.client.model.stream(messages, config={"callbacks": [trace_handler]})