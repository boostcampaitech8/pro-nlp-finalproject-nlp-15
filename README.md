# 📊 Chart Insight - AI Financial Intelligence

금융 데이터를 분석하고 시장의 핵심 동인을 파악하는 AI 기반의 금융 분석 대시보드입니다.

## 🚀 배포 및 실행 가이드 (Docker)

이 프로젝트는 `uv` 패키지 매니저와 `Docker`를 사용하여 최적화된 배포 환경을 지원합니다. 임베딩 모델이 API로 분리되어 있어 경량화된 이미지로 어디서든 빠르게 실행할 수 있습니다.

### 1. 로컬에서 Docker 빌드
프로젝트 루트 디렉토리에서 아래 명령어를 실행하여 이미지를 빌드합니다.
```bash
docker build -t chart-insight .
```

### 2. 컨테이너 실행
`.env` 파일에 기록된 환경 변수들을 전달하며 컨테이너를 실행합니다.
```bash
docker run -p 8501:8501 --env-file .env chart-insight
```
실행 후 브라우저에서 `http://localhost:8501`로 접속할 수 있습니다.

### 3. 의존성 최적화 (Dependency Optimization)
이 프로젝트는 운영 환경의 경량화를 위해 의존성을 그룹화하여 관리합니다. 기본 `uv sync` 명령어는 `pyproject.toml`의 `dependencies` 항목(핵심 앱 실행용)만 설치합니다.

*   **기본 설치 (Core only)**:
    ```bash
    uv sync
    ```
*   **특정 기능 포함 설치 (--extra 옵션)**:
    - 로컬 모델 사용 시: `uv sync --extra local`
    - 전처리 도구 사용 시: `uv sync --extra preprocess`
    - 스크래퍼 사용 시: `uv sync --extra scraper`
*   **여러 그룹 동시 설치**:
    ```bash
    uv sync --extra local --extra scraper
    ```
*   **모든 의존성 설치 (개발 환경용)**:
    ```bash
    uv sync --all-extras
    ```

### 4. 클라우드 배포 (추천 환경)
임베딩 모델이 독립된 API 구조이므로 RAM 2~4GB 정도의 저사양 인스턴스에서도 원활하게 작동합니다.

*   **Google Cloud Run**: 서버리스 환경으로 배포하기에 가장 적합합니다. (가장 저렴하고 관리가 쉬움)
*   **AWS EC2 / Azure VM**: Docker가 설치된 소형 인스턴스(t3.medium 이상 권장)에서 실행 가능합니다.
*   **Streamlit Community Cloud**: GitHub 저장소를 직접 연결하여 무료로 배포할 수 있습니다. (Secrets 설정 필요)

---

## 🛠️ 주요 환경 변수 설정
배포 환경의 `Environment Variables` 또는 `.env` 파일에 다음 항목이 포함되어야 합니다.

| 변수명 | 설명 |
| :--- | :--- |
| `GEMINI_API_KEY` | 분석에 사용할 Google Gemini API 키 |
| `QDRANT_URL` | 벡터 데이터베이스(Qdrant) 서버 주소 |
| `QDRANT_API_KEY` | Qdrant 인증 키 |
| `DENSE_EMBEDDING_API_URL` | 독립된 Dense 임베딩 서버 API 주소 |
| `SPARSE_EMBEDDING_API_URL` | 독립된 Sparse 임베딩 서버 API 주소 |
| `MYSQL_HOST` | 금융 데이터 MySQL 호스트 |

---

## 🏗️ 아키텍처 요약
- **UI**: Streamlit (Python 3.13)
- **Agent**: LangChain + Gemini-1.5-Flash
- **Database**: MySQL (RDB) + Qdrant (Vector DB)
- **Package Manager**: UV (Astral)
