import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

class LLMClient:
    def __init__(self, llm_cfg):
        # 1. 현재 사용할 서비스 제공자(openai 또는 local) 결정
        provider = llm_cfg.provider
        cfg = llm_cfg[provider]

        # 2. 설정에 저장된 '환경 변수 이름'을 통해 실제 API 키 로드
        # 예: cfg.secret_key_name이 "OPENAI_API_KEY"라면 os.environ에서 해당 값을 가져옴
        key_name = cfg.secret_key_name
        api_key = os.environ.get(key_name)
        
        base_url = cfg.base_url
        model_name = cfg.model

        # 필수 설정값 검증
        if not all([api_key, base_url, model_name]):
            raise EnvironmentError(
                f"{provider} 설정이 누락되었습니다. (Key Name: {key_name}, URL: {base_url}, Model: {model_name})"
            )

        # 3. ChatOpenAI 객체 생성 (OpenAI 규격을 따르는 로컬 모델도 호환됨)
        self.model = ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            openai_api_base=base_url,
            temperature=cfg.temperature
            # JSON 모드 강제 설정 제거 (대화형 에이전트를 위해 마크다운 출력 허용)
            # model_kwargs={"response_format": {"type": "json_object"}}
        )

    def get_response(self, messages, callbacks=None):
        return self.model.invoke(messages, config={"callbacks": callbacks})