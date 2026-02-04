---
trigger: always_on
---

## 1. Project Overview

본 프로젝트는 **주식 시장 뉴스 기반 사건 추출 및 심층 분석 챗봇** 개발입니다. 사용자가 특정 종목과 기간을 선택하면, 뉴스 데이터를 기반으로 추출된 '사건(Event)'을 요약하여 보여주며, 추가적인 질의응답을 수행하는 **Chatbot**을 구현합니다.

- **Core Goal:** 2017~2025년 뉴스 데이터를 바탕으로 "사건" 중심의 맥락을 제공하고, RAG(검색 증강 생성) 및 Qdrant 하이브리드 검색을 통해 근거 있는 금융 정보를 답변합니다.
- **Current Phase:** 사건(Event) 및 기사(Article) 데이터의 Qdrant 인덱싱이 완료되었으며, 날짜 필터링이 포함된 하이브리드 검색(Dense+Sparse) 기능이 에이전트에 통합된 상태입니다.

## 2. Tech Stack & style

### 2.1 Tech Stacks

- **Package Manager**: UV
- **LLM**: `Gemini-3.5-flash` (혹은 `Gemini-3.0-flash`)
- **LLM 프레임워크**: LangChain (OpenAI 호환 레이어 사용)
- **설정 및 로그 관리**: Hydra (전역 설정 및 로깅 표준화)
- **관측성 및 프롬프트 관리**: Langfuse (LLM 트레이싱 및 프롬프트 버저닝 v3 적용)
- **Vector DB**: Qdrant (Hybrid Search: PIXIE-Rune + PIXIE-Splade)
- **UI 레이어**: Streamlit (app/chatbot_app.py)
- **Backend:** FastAPI (추후 도입 예정)

### 2.2 Coding Conventions

- **Type Hinting:** 모든 함수와 메서드에 Python Type Hinting을 필수적으로 사용합니다. (Pydantic 모델 적극 활용)
- **Docstrings:** 모든 Tool 함수는 LLM이 이해할 수 있도록 상세한 Docstring(Google Style)을 작성해야 합니다.
- **Tool Invocation:** 에이전트 내부에서 도구 호출 시 `.run()` 메서드를 사용하여 일관성을 유지합니다.

## 3. Architecture

### 3.1. 프로젝트 구조

- /root
  - /app
    - chatbot_app.py # Streamlit UI (호출 전담)
  - /chatbot # 챗봇 모듈 (캡슐화)
    - /bot
      - agent.py # FinancialAgent (Hydra 설정 주입, Tool 바인딩, 흐름 제어)
      - llm_client.py # LangChain 기반 API 및 도구 바인딩 관리
      - prompt.py # Langfuse 연동 프롬프트 관리자
    - /tools # @tool 데코레이터 기반 에이전트 도구
      - get_price_summary.py # 가격 통계 및 요약
      - search_events.py # 변동성 기반 사건 검색 (Legacy/NewsRepo)
      - vector_search.py # Qdrant 기반 시맨틱 검색 (Articles & Events)
      - get_original_article.py # ID 기반 기사 원문 조회
  - /config # Hydra 기반 전역 설정
  - /db # 데이터 조회 및 저장 레이어
    - stock_api.py # 주가 데이터 (CSV) 조회
    - news_repo.py # 뉴스/사건 로컬 파일 조회 및 캐싱
    - vector_store.py # Qdrant 연동 (Hybrid Search, Date Filtering)
    - /scripts # 데이터 전처리 및 인덱싱 스크립트 (ingest_articles.py, ingest_events.py)
  - /prompts # 시스템 프롬프트 관리 (system_prompt_v3.md 등)
  - /preprocess # 데이터 가공 파이프라인 (upsert_reports.py 등)
  - /data # 원천 데이터 (articles/, events/, prices/)

### 3.2 계층화 전략

1. **Intelligence Layer (/chatbot/bot)**: 에이전트의 사고 흐름과 도구 선택을 담당합니다.
2. **Action Layer (/chatbot/tools)**: 구체적인 기능 단위로, Pydantic으로 입력을 검증하고 Data Layer를 호출합니다.
3. **Data Layer (/db)**: 로컬 파일(CSV/JSONL) 및 Vector DB(Qdrant)와의 통신을 전담합니다.
4. **UI Layer (/app)**: 사용자와의 인터페이스를 담당하며 비즈니스 로직과는 분리됩니다.

## 4. Implementation Guidelines

### 4.1. Prompt Management (Langfuse)

- **Version 3 (v3)**: 정교한 페르소나 설정(Educator vs Partner)과 Chain-of-Thought 추론 프레임워크가 적용되었습니다.
- **Prompt Backup**: `prompts/` 디렉토리에 로컬 작업용 프롬프트 파일을 유지합니다.

### 4.2. Tool Development Rules

- **Current Active Tools:**
  1. `get_price_summary`: 특정 기간의 자산 가격 통계 및 요약 제공.
  2. `search_volatility_events`: 가격 변동성이 큰 날짜의 뉴스/사건을 NewsRepository에서 검색.
  3. `search_similar_articles`: 사용자의 질의와 시맨틱하게 유사한 뉴스 기사를 Qdrant에서 검색 (날짜 필터 지원).
  4. `search_similar_events`: 추출된 '사건' 단위의 데이터를 Qdrant에서 검색 (날짜 필터 지원).
  5. `get_original_article`: 기사 ID를 사용하여 원문 전체 내용을 조회.

## 5. 프로토타입 개발 및 확장 방안

- **서빙 레이어**: 현재 Streamlit 기반으로 동작하며, 추후 `api/` 폴더의 FastAPI를 통해 프로덕션 환경으로 전환할 예정입니다.
- **데이터 처리**: `db/scripts`와 `preprocess/`를 통해 데이터 인계 및 벡터 라이징 프로세스를 자동화합니다.
