"""
fact_book JSON을 Phase 2/3 에이전트가 받을 수 있는 형태로 변환하는 유틸.
"""
import json


def schema_for_prompt(schema) -> str:
    """schema가 dict면 summary 또는 JSON 문자열로, 아니면 str(schema). 프롬프트용."""
    if isinstance(schema, dict):
        return schema.get("summary", json.dumps(schema, ensure_ascii=False, indent=2))
    return str(schema)


# 프롬프트가 너무 길면 API 타임아웃/컨텍스트 초과 가능 → 기본 상한
DEFAULT_MAX_CONTEXT_CHARS = 35_000
DEFAULT_MAX_EVENTS_FOR_CONTEXT = 15


def fact_book_to_arena_input(
    fact_book: dict,
    max_events: int | None = DEFAULT_MAX_EVENTS_FOR_CONTEXT,
    max_context_chars: int | None = DEFAULT_MAX_CONTEXT_CHARS,
) -> tuple[dict, str]:
    """
    get_batch_fact_book() 결과(fact_book)를
    run_automated_arena(schema, news_content, ...) 및 Phase 3에 넘길 형태로 변환합니다.

    fact_book이 크면 프롬프트가 길어져 API 타임아웃이 날 수 있으므로
    max_events(사건 수), max_context_chars(총 글자 수)로 맥락을 제한합니다.

    Returns:
        schema: dict. initial_bias용 "result" 및 프롬프트용 "summary" 포함.
        news_content: str. 에이전트에게 전달할 맥락 텍스트(상한 적용됨).
    """
    meta = fact_book.get("analysis_metadata", {})
    events = fact_book.get("events", [])

    # 맥락에 넣을 이벤트만 선택 (앞에서부터)
    if max_events is not None and len(events) > max_events:
        events_for_context = events[:max_events]
    else:
        events_for_context = events

    # 스키마: initial_bias는 schema.get("result") 사용. 요약은 프롬프트용.
    summary_parts = [
        f"[종목] {meta.get('commodity', '')}",
        f"[기간] {meta.get('period', {})}",
        f"[수집 사건 수] {len(events)}건",
    ]
    for i, ev in enumerate(events_for_context, 1):
        core = ev.get("event_core", {})
        summary_parts.append(f"  {i}. {core.get('title', '')} — {core.get('summary', '')[:200]}...")
    if len(events) > len(events_for_context):
        summary_parts.append(f"  ... 외 {len(events) - len(events_for_context)}건 (맥락 생략)")
    summary_str = "\n".join(summary_parts)

    schema = {
        "result": "",
        "summary": summary_str,
        "commodity": meta.get("commodity"),
        "period": meta.get("period"),
        "events_count": len(events),
    }

    # 에이전트에게 전달할 맥락: 사건별 제목/요약 + 뉴스 증거 요약
    context_parts = [f"# 팩트북 요약\n{summary_str}\n\n# 사건별 상세"]
    for i, ev in enumerate(events_for_context, 1):
        core = ev.get("event_core", {})
        context_parts.append(f"\n## 사건 {i}: {core.get('title', '')}")
        context_parts.append(core.get("summary", ""))
        for j, news in enumerate(ev.get("news_evidence", [])[:5], 1):
            context_parts.append(f"  - [{j}] {news.get('title', '')}: {news.get('description', '')[:150]}...")
    news_content = "\n".join(context_parts)

    if max_context_chars is not None and len(news_content) > max_context_chars:
        news_content = news_content[:max_context_chars] + "\n\n... (맥락 길이 제한으로 생략됨)"

    return schema, news_content
