# 🌐 AI Financial Intelligence (Tilda Data)

본 프로젝트는 **주식/원자재 시장 뉴스 기반 사건 추출 및 심층 분석 챗봇**입니다. 2017~2025년 뉴스 데이터를 바탕으로 '사건(Event)' 중심의 맥락을 제공하고, RAG(검색 증강 생성) 및 Qdrant 하이브리드 검색을 통해 정교한 금융 도메인 질문에 답변합니다.

## 🚀 Quick Start

### 1. 환경 설정
본 프로젝트는 `uv`를 패키지 매니저로 사용합니다.

```bash
# 의존성 설치
uv sync

# 환경 변수 설정 (.env 파일 생성)
# GOOGLE_API_KEY, QDRANT_API_KEY, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY 등
cp .env.example .env
```

### 2. 애플리케이션 실행
```bash
uv run streamlit run app/chatbot_app.py
```

---

## 🛠️ Data Pipeline & Workflows

데이터 구축 및 인덱싱을 위한 워크플로우 가이드입니다.

### 1. RDB 데이터 임포트 (SQLite/MySQL)
기본적으로 SQLite를 로컬 모드로 사용합니다. 로컬 CSV/JSONL 데이터를 데이터베이스로 가져옵니다.
```bash
# 1. 인제스트 실행 (자동으로 sqlite/ 폴더에 DB 생성)
uv run python workflow/run_ingest_raw.py

# 2. (선택) DB 초기화 및 다시 구축 시
uv run python workflow/run_ingest_raw.py rebuild=true
```

### 2. 지식 베이스(KB) 인덱싱
PDF나 보고서 데이터를 청킹하고 Qdrant 벡터 DB로 업로드합니다.
```bash
# 청킹 (Chuncking)
uv run python workflow/run_kb_chunking.py resource_id=commodity_markets_2022

# 인덱싱 (Embedding & Upsert)
uv run python workflow/run_kb_indexing.py resource_id=commodity_markets_2022
```

### 3. 뉴스 사건(Event) 벡터 인덱싱
추출된 사건 데이터를 검색 가능하도록 Qdrant에 인덱싱합니다.
```bash
uv run python workflow/run_index_events.py
```

---

## 🏗️ Architecture & Configuration

프로젝트는 유지보수성과 확장성을 위해 **계층형 아키텍처(Layered Architecture)**를 채택하고 있습니다.

- **UI Layer (`app/`)**: Streamlit 기반 대시보드 및 챗봇 인터페이스.
- **Intelligence Layer (`chatbot/bot/`)**: `FinancialAgent`를 통한 사고 흐름 제어.
- **Action Layer (`chatbot/tools/`)**: 가격 요약, 사건 검색, 지식 베이스 검색 등 구체적 기능 단위 도구.
- **Data Layer (`db/`, `vector_db/`)**: 
  - **SQLite (Default)**: `sqlite/stockinfo.db`에서 가격, 사건, 기사 관리.
  - **MySQL**: 프로덕션용 데이터베이스 지원.
  - **Qdrant**: 하이브리드 검색을 위한 벡터 저장소.

상세 아키텍처는 [ARCHITECTURE.md](docs/ARCHITECTURE.md)를, 설정 방법은 [CONFIG_GUIDE.md](docs/CONFIG_GUIDE.md)를 참조하세요.

---

## 🔑 Key Features

- **Hybrid Search**: PIXIE-Rune(Dense) + PIXIE-Splade(Sparse) 모델 결합 검색.
- **Agentic Workflow**: LLM이 상황에 맞는 도구를 선택하여 실시간 시장 상황과 과거 지식을 결합.
- **Performance Optimization**: N+1 쿼리 해결 및 자산/기사 캐싱을 통한 빠른 UI 응답성.
- **Observability**: Langfuse 연동을 통한 모든 LLM 호출 트레이싱 및 프롬프트 관리.
- **Optimized Ingestion**: 벌크 인서트(Bulk Insert) 및 `tqdm` 진행도 표시를 통한 고속 데이터 로딩.
- **Path Modularity**: Hydra 설정을 통한 모든 경로 및 환경 설정의 유연한 관리.
- **Metadata Caching**: 자산 및 기사 조회 성능 최적화.

---

## 📝 License
Copyright (c) 2026. DeepMind Advanced Agentic Coding Team & Boostcamp NLP-15.
