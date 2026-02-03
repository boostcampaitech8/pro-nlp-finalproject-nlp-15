# 📊 Financial Event Analysis Chatbot

주식 시장 뉴스 기반 사건 추출 및 심층 분석 AI 챗봇

## 🎯 프로젝트 개요

2017~2025년 뉴스 데이터를 기반으로 **"사건" 중심의 맥락**을 제공하고, RAG(검색 증강 생성)를 통해 근거 있는 금융 정보를 답변하는 대화형 분석 시스템입니다.

### 주요 기능

- 📈 **인터랙티브 차트**: 드래그하여 기간 선택, 실시간 데이터 업데이트
- 📰 **이벤트 타임라인**: 고변동성 날짜의 주요 뉴스 사건 자동 필터링
- 🤖 **AI 분석가**: 시장 데이터와 뉴스를 결합한 컨텍스트 기반 질의응답
- 🎨 **직관적 UI**: Streamlit 기반의 깔끔한 웹 인터페이스

---

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 저장소 클론
git clone <repository-url>
cd tilda_data

# UV 패키지 매니저 설치 (없는 경우)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 의존성 설치
uv sync
```

### 2. 환경 변수 설정

`.env` 파일을 생성하고 API 키를 설정합니다:

```bash
# LLM API Keys
GOOGLE_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key  # 선택

# Langfuse (프롬프트 관리)
LANGFUSE_PUBLIC_KEY=your_public_key
LANGFUSE_SECRET_KEY=your_secret_key
LANGFUSE_HOST=https://cloud.langfuse.com
```

### 3. 데이터 준비

다음 구조로 데이터를 배치합니다:

```
data/
├── prices/          # 주가 CSV 파일
│   └── copper_price.csv
├── events/          # 사건 JSON/JSONL 파일
│   └── copper_silver.jsonl
└── articles/        # 기사 CSV 파일
    └── copper_silver.csv
```

### 4. 실행

```bash
uv run streamlit run app/chatbot_app.py
```

브라우저에서 `http://localhost:8501` 접속

---

## 🏗️ 프로젝트 구조

```
.
├── app/                      # 🎨 UI Layer
│   └── chatbot_app.py       # Streamlit 메인 애플리케이션
├── chatbot/                  # 🧠 Intelligence & Action Layer
│   ├── bot/                 # 챗봇 핵심 로직
│   │   ├── agent.py        # FinancialAgent (오케스트레이션)
│   │   ├── llm_client.py   # LLM 호출 추상화
│   │   └── prompt.py       # Langfuse 프롬프트 관리
│   └── tools/               # 에이전트 도구
│       ├── get_summary.py  # 가격 통계 요약
│       └── search_events.py # 이벤트 검색
├── db/                       # 💾 Data Layer
│   ├── stock_api.py         # 주가 데이터 조회
│   ├── news_repo.py         # 뉴스/사건 조회
│   └── vector_store.py      # 벡터 검색 (예정)
├── config/                   # ⚙️ Configuration
│   ├── chatbot.yaml         # 챗봇 설정
│   └── llm/                 # LLM 제공자별 설정
└── data/                     # 📁 Data Files
```

---

## 🛠️ 기술 스택

### Core
- **UI**: Streamlit
- **LLM**: Gemini 2.0 Flash / OpenAI GPT
- **LLM Framework**: LangChain
- **Configuration**: Hydra
- **Observability**: Langfuse

### Data & Visualization
- **Data Processing**: Pandas
- **Charts**: Plotly
- **State Management**: Streamlit Session State + Query Params

### Future
- **Vector DB**: Qdrant (계획)
- **API**: FastAPI (계획)

---

## 📚 아키텍처

### 4계층 구조

```
┌─────────────────────────────────────┐
│  UI Layer (app/)                    │  ← 사용자 인터페이스
├─────────────────────────────────────┤
│  Intelligence Layer (chatbot/bot/)  │  ← LLM 호출 & 에이전트
├─────────────────────────────────────┤
│  Action Layer (chatbot/tools/)      │  ← 도구 실행
├─────────────────────────────────────┤
│  Data Layer (db/)                   │  ← 데이터 조회 & 캐싱
└─────────────────────────────────────┘
```

### 핵심 컴포넌트

#### 🎨 UI Layer: `chatbot_app.py`
- 자산 선택, 날짜 범위 관리
- 인터랙티브 차트 (드래그로 기간 선택)
- 이벤트 타임라인 표시
- AI 챗봇 인터페이스

#### 🧠 Intelligence Layer: `FinancialAgent`
- 사용자 쿼리 처리
- 컨텍스트 생성 (가격 + 이벤트)
- LLM 응답 스트리밍

#### 🔧 Action Layer: Tools
- **GetSummaryTool**: 기간 수익률, 변동성 계산
- **SearchEventsTool**: 고변동성 날짜의 이벤트 필터링

#### 💾 Data Layer
- **StockAPI**: 주가 데이터 (캐싱)
- **NewsRepository**: 이벤트 + 기사 데이터 (캐싱)

---

## 💡 주요 기능 설명

### 1. 인터랙티브 차트 선택

차트에서 드래그하여 날짜 범위를 선택하면:
- 사이드바 날짜 입력이 **즉시 업데이트**
- 이벤트 타임라인이 해당 기간으로 **자동 필터링**
- URL Query Params에 상태 저장 (새로고침해도 유지)

**기술 포인트**:
- Query Params = 단일 진실 공급원 (URL 영속성)
- 동적 위젯 키 (`key=f"sdt_{date}"`)로 즉시 렌더링

### 2. 고변동성 이벤트 필터링

AI 챗봇은 단순히 모든 뉴스를 나열하지 않고:
1. 주가 데이터에서 **변동성 계산**
2. 가장 volatile한 날짜 추출
3. **해당 날짜의 이벤트만** 컨텍스트로 제공

→ 관련성 높은 정보만 LLM에 전달 (토큰 효율↑)

### 3. 프롬프트 버저닝 (Langfuse)

프롬프트는 코드가 아닌 **Langfuse Web UI**에서 관리:
- 버전 관리 및 A/B 테스트
- 프롬프트 변경 시 코드 재배포 불필요
- Human-Driven Development

---

## 🎨 사용 예시

### 1. 차트에서 급락 구간 드래그
```
사용자: 차트에서 2020년 3월 드래그
→ 사이드바 날짜: 2020-03-01 ~ 2020-03-31 자동 업데이트
→ 이벤트 타임라인: COVID-19 관련 뉴스 표시
```

### 2. AI에게 질문
```
사용자: "2020년 3월 급락 원인은?"
AI: "주요 원인은 COVID-19 팬데믹입니다. 
     - 3월 11일: WHO 팬데믹 선언 (종가 -8.2%)
     - 3월 16일: 연준 긴급 금리 인하 (종가 +5.1%)
     ..."
```

---

## ⚙️ 설정

### LLM 제공자 변경

`config/chatbot.yaml`:

```yaml
llm:
  provider: gemini  # gemini / openai / local 선택
```

### 프롬프트 관리

Langfuse Web UI에서:
1. `financial_analyst_v1`: 페르소나 프롬프트
2. `market_data_context_v1`: 데이터 컨텍스트 템플릿

프롬프트 변경 후 즉시 반영 (재배포 불필요)

---

## 🚧 개발 로드맵

- [ ] **Vector DB 통합**: Qdrant를 사용한 의미 검색
- [ ] **FastAPI 서빙**: REST API 제공
- [ ] **실시간 데이터**: 외부 API 연동
- [ ] **멀티 자산 분석**: 포트폴리오 비교 기능

---

## 📖 상세 문서

더 자세한 아키텍처 정보는 다음 문서를 참고하세요:
- [Architecture Documentation](docs/ARCHITECTURE.md)

---

## 🤝 기여

이슈 및 PR은 언제나 환영합니다!

## 📄 라이선스

MIT License
