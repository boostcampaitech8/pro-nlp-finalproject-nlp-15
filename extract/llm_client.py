from __future__ import annotations

import json
import os
import logging
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from omegaconf import DictConfig
from langfuse.langchain import CallbackHandler
from langfuse import Langfuse
from langchain_core.messages import HumanMessage, SystemMessage

from extract.schema import normalize_event

logger = logging.getLogger(__name__)

def try_parse_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise

@dataclass(frozen=True)
class OpenAICompatConfig:
    base_url: str
    api_key: str
    model: str
    temperature: float = 0.0

class WindowEventExtractor:
    def __init__(self, cfg: OpenAICompatConfig):
        self.cfg = cfg
        load_dotenv()
        self._llm = self._make_llm()
        self.langfuse_handler = CallbackHandler()
        self.langfuse = Langfuse()

    @classmethod
    def from_hydra_config(cls, hydra_cfg: DictConfig = None) -> "WindowEventExtractor":
        load_dotenv()
        base_url = os.environ.get("CUSTOM_OPENAI_BASE_URL")
        api_key = os.environ.get("CUSTOM_OPENAI_API_KEY")
        
        model = hydra_cfg.llm.get("model") if hydra_cfg and "llm" in hydra_cfg else os.environ.get("CUSTOM_OPENAI_MODEL")
        temp = hydra_cfg.llm.get("temperature", 0.0) if hydra_cfg and "llm" in hydra_cfg else 0.0

        if not base_url or not api_key or not model:
            raise RuntimeError("Missing CUSTOM_OPENAI environment variables or Hydra config.")
            
        return cls(OpenAICompatConfig(base_url=base_url, api_key=api_key, model=model, temperature=temp))

    def _reinit_llm_session(self, retry_state):
        self._llm = self._make_llm()

    def _make_llm(self) -> Any:
        from langchain_openai import ChatOpenAI
        llm_kwargs = {
            "model": self.cfg.model,
            "temperature": self.cfg.temperature,
            "timeout": 300,
            "max_retries": 0,
            "top_p": 0.95,
            "presence_penalty": 0
        }
        try:
            return ChatOpenAI(api_key=self.cfg.api_key, base_url=self.cfg.base_url, **llm_kwargs)
        except TypeError:
            return ChatOpenAI(openai_api_key=self.cfg.api_key, openai_api_base=self.cfg.base_url, **llm_kwargs)

    def llm_text(self, messages: List[Any]) -> str:
        resp = self._llm.invoke(messages, config={"callbacks": [self.langfuse_handler]})
        return str(getattr(resp, "content", ""))

    def extract_window_events(
        self,
        *,
        window_context: str,
        items: List[Dict[str, Any]],
        output_dir: Optional[Path] = None,
        system_prompt: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        id_map, article_db, simplified_items = {}, {}, []
        
        for idx, item in enumerate(items, 1):
            id_map[idx] = item["id"]
            article_db[idx] = item
            simplified_items.append({
                "id": idx,
                "title": item.get("title"),
                "description": item.get("description"),
                "publish_date": item.get("publish_date")
            })

        from tenacity import Retrying, stop_after_attempt, wait_exponential
        for attempt in Retrying(
            stop=stop_after_attempt(4),
            wait=wait_exponential(multiplier=1, min=2, max=20),
            before_sleep=self._reinit_llm_session
        ):
            with attempt:
                try:
                    prompt_obj = self.langfuse.get_prompt("extract")
                    current_system_prompt = system_prompt or prompt_obj.compile()

                    input_json = json.dumps({"items": simplified_items}, ensure_ascii=False)
                    messages = [
                        SystemMessage(content=current_system_prompt),
                        HumanMessage(content=input_json),
                    ]
                    
                    raw = self.llm_text(messages)
                    parsed = try_parse_json(raw)
                    
                    raw_events = [e for e in parsed.get("events", []) if isinstance(e, dict)]
                    
                    normalized_results = []
                    for e in raw_events:
                        try:
                            norm_e = normalize_event(e, article_db, id_map)
                            normalized_results.append(norm_e)
                        except Exception as ex:
                            logger.warning(f"Event normalization failed: {ex}")
                            continue
                    
                    return normalized_results

                except Exception as e:
                    attempt_num = attempt.retry_state.attempt_number
                    logger.error(f"Attempt {attempt_num} Failed: {type(e).__name__} - {str(e)}")
                    
                    if output_dir:
                        err_jsonl = output_dir / "error.jsonl"
                        err_payload = {
                            "timestamp": dt.datetime.now().isoformat(),
                            "attempt": attempt_num,
                            "window": window_context,
                            "error_type": type(e).__name__,
                            "error_msg": str(e),
                            "raw_llm_output": raw[:2000] if 'raw' in locals() else None
                        }
                        with err_jsonl.open("a", encoding="utf-8") as f_err:
                            f_err.write(json.dumps(err_payload, ensure_ascii=False) + "\n")
                    
                    raise e