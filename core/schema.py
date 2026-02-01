import json
import re
from omegaconf import DictConfig
from .llm import send_llmapi

async def extract_schema_and_narrative(news_content: str, cfg: DictConfig) -> dict:
    """
    뉴스 원문에서 Schema-based IE(구성요건)를 추출하고 초기 서사를 생성.
    """
    system_prompt = cfg.prompts.schema_system
    user_prompt = cfg.prompts.schema_user.format(news_content=news_content)

    # 2. 비동기 호출
    # task_type="schema"를 지정하여 가이드라인 온도(0.1~0.2)를 적용합니다.
    response = await send_llmapi(
        prompt=user_prompt,
        cfg=cfg,
        role="master",
        task_type="schema",
        system_prompt=system_prompt
    )

    # 3. JSON 데이터 파싱
    try:
        # 정규표현식을 통해 최외곽 중괄호 {} 블록을 찾습니다.
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            schema_data = json.loads(json_str)
            # JSON 부분을 제외한 나머지 텍스트를 서사(Narrative)로 취급합니다.
            narrative = response.replace(json_str, "").strip()
        else:
            schema_data = {}
            narrative = response
            
    except Exception as e:
        print(f"⚠️ [Schema Parsing Error]: {e}")
        schema_data = {}
        narrative = response

    return {
        "schema": schema_data,
        "narrative": narrative
    }