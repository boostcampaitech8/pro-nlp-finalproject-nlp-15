import os
from typing import Any
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models.chat_models import BaseChatModel

class LLMClient:
    """
    LLM 클라이언트 추상화 레이어
    
    Gemini, OpenAI 등 다양한 LLM 제공자를 통합하여 관리
    """
    
    def __init__(self, llm_cfg: Any) -> None:
        """
        LLM 클라이언트 초기화
        
        Args:
            llm_cfg: Hydra 설정 객체 (llm 섹션)
        """
        # 1. Determine provider
        provider: str = llm_cfg.provider
        cfg = llm_cfg[provider]

        # 2. Get API Key
        key_name: str = cfg.secret_key_name
        api_key: str | None = os.environ.get(key_name)
        
        base_url: str = cfg.base_url
        model_name: str = cfg.model

        # Validation
        if not api_key:
             raise EnvironmentError(f"Missing API Key: {key_name} for provider {provider}")

        # 3. Create Instance
        self.model: BaseChatModel
        if provider == "gemini":
            self.model = ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=api_key,
                temperature=cfg.temperature,
                convert_system_message_to_human=True  # Gemini 호환성
            )
        else:
            # Local / OpenAI
            self.model = ChatOpenAI(
                model=model_name,
                openai_api_key=api_key,
                openai_api_base=base_url,
                temperature=cfg.temperature
            )
    
    def get_response(self, messages: list, callbacks: list | None = None) -> Any:
        """단일 응답 반환 (스트리밍 없음)"""
        return self.model.invoke(messages, config={"callbacks": callbacks})

    def get_stream(self, messages: list, callbacks: list | None = None) -> Any:
        """스트리밍 응답 반환"""
        return self.model.stream(messages, config={"callbacks": callbacks})
    
    def bind_tools(self, tools: list) -> Any:
        """
        도구를 LLM에 바인딩 (Tool Calling)
        
        Args:
            tools: LangChain @tool 데코레이터로 정의된 도구 함수 리스트
            
        Returns:
            도구가 바인딩된 LLM 인스턴스
        """
        return self.model.bind_tools(tools)