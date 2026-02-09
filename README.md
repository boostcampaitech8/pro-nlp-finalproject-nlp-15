## 📂 Project Structure

```text
.
├── app/                    # UI 레이어 (Streamlit)
│   ├── chatbot_app.py      # 메인 대시보드 애플리케이션
│   └── static/             # 아이콘 및 정적 에셋
├── chatbot/                # 비즈니스 로직 및 에이전트
│   ├── bot/                # FinancialAgent 및 LLM 인터페이스
│   ├── multi_agent/        # 멀티 에이전트 협업 로직
│   └── tools/              # 에이전트 사용 도구 (검색, 추출 등)
├── config/                 # Hydra 설정 관리 (YAML)
│   ├── app/                # 애플리케이션/프롬프트 설정
│   └── infra/              # DB/RAG 인프라 설정
├── db/                     # 데이터 접근 계층 (SQLAlchemy)
│   ├── database.py         # DB 연결 및 스키마 정의
│   └── *_repo.py           # 가격/사건/기사 데이터 Repository
├── vector_db/              # 벡터 데이터베이스 연동 (Qdrant)
│   └── vector_store.py     # 하이브리드 검색 및 임베딩 관리
├── preprocess/             # 테이터 전처리 및 인덱싱 스크립트
├── prompts/                # 시스템 프롬프트 템플릿
├── Dockerfile              # 경량 배포용 설정
└── pyproject.toml          # uv 기반 의존성 관리
```

## 🚀 실행 가이드

### 1. 로컬 환경 실행 (Recommended: `uv`)
먼저 `uv`가 설치되어 있어야 합니다. ([설치 가이드](https://github.com/astral-sh/uv))

```bash
# 환경 변수 설정
cp .env.example .env
# .env 파일을 열어 실제 API 키와 DB 정보를 입력하세요.

# 의존성 설치 (선택 가능)
uv sync                       # 핵심 기능만 설치 (운영용)
uv sync --all-extras          # 로컬 모델 및 스크래퍼 포함 전체 설치 (개발용)

# 앱 실행
uv run streamlit run app/chatbot_app.py
```

### 2. Docker를 이용한 실행
운영 환경이나 리눅스 서버에서 격리된 환경으로 실행할 때 적합합니다.

```bash
# 이미지 빌드
docker build -t chart-insight .

# 컨테이너 실행
docker run -p 8501:8501 --env-file .env chart-insight
```

### 3. 의존성 최적화 (Dependency Optimization)
이 프로젝트는 의존성을 그룹화하여 관리합니다.

*   **Default**: 핵심 챗봇 앱 및 원격 API 연동용 (최소 크기)
*   **Extra: `local`**: 로컬에서 임베딩 모델을 직접 실행할 경우 (`torch`, `sentence-transformers` 포함)
*   **Extra: `preprocess`**: PDF 파싱 등 데이터 처리가 필요할 경우
*   **Extra: `scraper`**: Playwright 기반의 심층 웹 스크래핑이 필요할 경우

명령어 예시: `uv sync --extra local`

---

## 🛠️ 환경 변수 (.env) 설정
배포 전 반드시 아래 변수들이 설정되어야 합니다.

| 변수 | 설명 | 예시 |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | Google AI API 키 | `AIza...` |
| `QDRANT_URL` | Qdrant 벡터 서버 주소 | `https://...` |
| `QDRANT_API_KEY` | Qdrant 인증 토큰 | `...` |
| `DENSE_EMBEDDING_API_URL` | Dense 임베딩 API 엔드포인트 | `https://...` |
| `SPARSE_EMBEDDING_API_URL` | Sparse 임베딩 API 엔드포인트 | `https://...` |
| `MYSQL_HOST` | 데이터베이스 호스트 | `localhost` |
