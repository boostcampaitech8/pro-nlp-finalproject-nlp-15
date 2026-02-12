# Interpret 모듈

이벤트 기반 뉴스 요약 및 가격 예측 파이프라인

## 구조

```
interpret/
├── pipeline.py      # 메인 파이프라인 (요약 + 예측)
├── migrate.py       # DB 마이그레이션 스크립트
├── db.py            # MySQL 데이터베이스 연동
├── llm.py           # LLM API 호출
├── csv_loader.py    # CSV/JSONL 파일 로더
└── README.md
```

## 사용법

### 파이프라인 실행

```bash
# SQL 모드 (기본) - summarize/is_up이 NULL인 이벤트만 처리
uv run python interpret/pipeline.py
uv run python interpret/pipeline.py --limit 10

# SQL 전체 모드 - 모든 이벤트 재처리
uv run python interpret/pipeline.py --all

# CSV 모드 - JSONL/CSV 파일 사용 시
uv run python interpret/pipeline.py --events data/events/gold_future.jsonl --articles data/articles/gold_future.csv
```

### 마이그레이션

```bash
# event 테이블에 summarize, is_up 컬럼 추가
uv run python interpret/migrate.py

# SQL만 확인 (dry-run)
uv run python interpret/migrate.py --dry-run
```

## 모듈 설명

### pipeline.py

이벤트를 처리하여 요약(summarize)과 가격 방향 예측(is_up)을 생성합니다.

- 100개 동시 요청 (멀티스레드)
- SQL 모드: DB에서 이벤트 조회 → LLM 처리 → DB 즉시 업데이트
- CSV 모드: JSONL/CSV 파일 읽기 → LLM 처리 → CSV 파일 출력

### db.py

MySQL 데이터베이스 연동 모듈

- `DatabaseConnection`: 스레드 안전한 연결 관리
- `SQLArticleLoader`: 기사 데이터 로더 (캐싱 지원)
- `SQLEventLoader`: 이벤트 데이터 로더

### llm.py

OpenAI 호환 LLM API 호출

- Hydra config 기반 설정
- 시스템/사용자 프롬프트 지원

### csv_loader.py

파일 기반 데이터 로더

- `ArticleLoader`: CSV 파일에서 기사 로드 (lazy loading)
- `EventLoader`: JSONL 파일에서 이벤트 로드

## 설정

`config/config.yaml`에서 설정:

```yaml
llm:
  api_key: "your-api-key"
  base_url: "http://localhost:8000/v1"
  model: "model-name"
  temperature: 0.7
  max_tokens: 2048

db:
  host: localhost
  port: 3306
  database: your_db
  user: user
  password: password
  tables:
    events: event
    articles: article

prompts:
  summarize_system: "..."
  summarize_user: "..."
  predict_system: "..."
  predict_user: "..."
```
