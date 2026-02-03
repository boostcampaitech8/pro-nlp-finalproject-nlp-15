---
trigger: always_on
---

## 1. Project Overview

본 프로젝트는 **주식 시장 뉴스 기반 사건 추출 및 심층 분석 챗봇** 개발입니다. 사용자가 특정 종목과 기간을 선택하면, 뉴스 데이터를 기반으로 추출된 '사건(Event)'을 요약하여 보여주며, 추가적인 질의응답을 수행하는 **Chatbot**을 구현합니다.

- **Core Goal:** 2017~2025년 뉴스 데이터를 바탕으로 "사건" 중심의 맥락을 제공하고, RAG(검색 증강 생성)를 통해 근거 있는 금융 정보를 답변합니다.
- **Current Phase:**

## 2. Tech Stack & style

### 2.1 Tack Stacks

- **Package Manager**: UVㄴ
- **LLM**: `Gemini-3.0-flash`
- **LLM 프레임워크**: LangChain (OpenAI 호출 및 도구 바인딩)
- **설정 및 로그 관리**: Hydra (전역 설정 및 로깅 표준화)
- **관측성 및 프롬프트 관리**: Langfuse (LLM 트레이싱 및 프롬프트 버저닝)
- **UI 레이어**: Streamlit (app/chatbot_app.py)
- **서빙 레이어**: FastAPI (추후 도입 예정)
- **Backend:** FastAPI (API Endpoints, User Session)

### 2.2 Coding Conventions

- **Type Hinting:** 모든 함수와 메서드에 Python Type Hinting을 필수적으로 사용합니다. (Pydantic 모델 적극 활용)
- **Docstrings:** 모든 Tool 함수는 LLM이 이해할 수 있도록 상세한 Docstring(Google Style)을 작성해야 합니다.

## 3. Architecture

### 3.1. 프로젝트 구조

챗봇의 핵심 로직은 `/chatbot` 폴더에 캡슐화하고, 설정은 루트의 `/config`에서 관리하며 데이터 조회는 공용 `/db` 레이어를 사용합니다.

- /root
  - /app
    - chatbot_app.py # Streamlit UI (호출 전담)
  - /chatbot # 챗봇 모듈 (캡슐화)
    - /bot
      - llm_client.py # LangChain 기반 순수 API 호출
      - agent.py # 몸통 (Hydra 설정 주입, Tool 바인딩, 흐름 제어)
      - prompt.py # Langfuse 기반 프롬프트 관리
    - /tools # 에이전트 전용 도구 (db 레이어 호출)
      - tool_function1.py (예시)
      - tool_function2.py
  - /config # 전역 설정 (Hydra 관리)
    - /llm # local.yaml, gemini.yaml, openai.yaml
    - chatbot.yaml # 챗봇 비즈니스 설정
  - /db # 공유 데이터 조회 레이어 (Data Source)
    - stock_api.py # 주가 데이터 조회
    - news_repo.py # 뉴스/사건 목록 조회
    - vector_store.py # 사건 벡터 검색
  - /api # 추후 FastAPI 도입 시 사용

### 3.2 계층화 전략

상위 계층은 하위 계층을 알지만, 하위 계층은 상위 환경(UI 등)으로부터 독립적이어야 합니다.

1. **Intelligence Layer (/chatbot/bot)**: Hydra로 설정을 주입받고 LangChain으로 에이전트를 구성합니다. 모든 실행 로그는 Langfuse로 트래킹합니다.
2. **Action Layer (/chatbot/tools)**: 에이전트가 사용하는 기능 단위입니다. 실제 데이터가 필요하면 `/db` 레이어를 호출합니다.
3. **Data Layer (/db)**: 데이터 조회를 전담합니다. 초기에는 실제 DB 연결 없이 파일 입력이나 메모리 기반의 더미 함수로 구현합니다.
4. **UI Layer (/app)**: Streamlit으로 구현하며, 사용자와의 입출력만 담당하고 로직은 챗봇 모듈에 위임합니다.

## 4. Implementation Guidelines

### 4.1. Prompt Management (Langfuse)

- **Human-Driven Development:** 프롬프트 개발 및 개선은 개발자가 Langfuse Web UI에서 직접 수행.

### 4.2. Tool Development Rules

`chatbot/tools/` 디렉토리 내의 개발은 다음 규칙을 따릅니다.

- **1 File 1 Function:** 하나의 파이썬 스크립트는 하나의 도구 함수만 정의합니다.
- **Schema Definition:** Pydantic을 사용하여 입력 매개변수의 타입을 명확히 정의합니다.
- **Current Tools:**
  1. `get_summary_by_period`: 기간 내 주요 사건 및 가격 통계.
  2. `get_original_article`: 기사 ID로 원문 본문 조회.
  3. `search_relative_events`: Qdrant Vector DB Semantic Search.
  4. `web_search`: (Optional) 금융/경제 텍스트북 RAG.

## 5. 프로토타입 개발 및 확장 방안

- **초기 단계**: `app/chatbot_app.py`를 실행하여 UI를 확인합니다. `/db` 레이어에 더미 함수를 만들어 데이터 흐름을 먼저 검증합니다.
- **확장 단계**: 서비스 규모 확대 시 `app/` 대신 `api/` 폴더를 통해 FastAPI로 서빙합니다. 이때 `/chatbot` 모듈의 코드는 수정 없이 그대로 재사용합니다.
- **데이터 전환**: 시스템 안정화 후 `/db` 내부의 더미 로직만 실제 DB 쿼리나 외부 API 연결 코드로 교체합니다.
