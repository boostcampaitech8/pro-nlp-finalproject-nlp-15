import os
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

class LLMClient:
    def __init__(self, llm_cfg):
        # 1. Determine provider
        provider = llm_cfg.provider
        cfg = llm_cfg[provider]

        # 2. Get API Key
        key_name = cfg.secret_key_name
        api_key = os.environ.get(key_name)
        
        base_url = cfg.base_url
        model_name = cfg.model

        # Validation
        if not api_key:
             raise EnvironmentError(f"Missing API Key: {key_name} for provider {provider}")

        # 3. Create Instance
        if provider == "gemini":
            self.model = ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=api_key,
                temperature=cfg.temperature,
                convert_system_message_to_human=True # Often needed for Gemini compatibility
            )
        else:
            # Local / OpenAI
            self.model = ChatOpenAI(
                model=model_name,
                openai_api_key=api_key,
                openai_api_base=base_url,
                temperature=cfg.temperature
            )
    
    def get_response(self, messages, callbacks=None):
        return self.model.invoke(messages, config={"callbacks": callbacks})

    def get_stream(self, messages, callbacks=None):
        return self.model.stream(messages, config={"callbacks": callbacks})