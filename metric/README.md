# Event extraction evaluation

이벤트 추출 결과(`data/events/*.jsonl`)를 뉴스 기사(`data/articles/*.csv`)와 매칭해 다음 지표를 계산합니다.

- **Event-level topic coherence** (C_V)
- **Intra-event similarity**
- **Inter-event similarity**
- **Fragmentation rate** (singleton)
- **Fragmentation by similarity**
- **Merging error rate**

지표 정의: `metrics_design.md`

## 설치

```bash
pip install -e ".[metric]"
# 또는
pip install -r metric/requirements-metric.txt
```

## 실행

`main` 프로젝트 루트(현재 `metric` 디렉토리의 상위)에서:

```bash
# 모든 매칭되는 (events + articles) 데이터셋에 대해 평가
python -m metric.event_evaluation

# 단일 데이터셋만
python -m metric.event_evaluation --dataset national_agricultural_statistics_service

# per-event 지표 CSV 저장 (마지막 행에 overall 요약 포함)
python -m metric.event_evaluation --dataset national_agricultural_statistics_service --output results/national_agricultural_statistics_service_metrics.csv
# 또는 디렉터리 지정 시 {디렉터리}/{데이터셋명}_event_metrics.csv 로 저장
python -m metric.event_evaluation --output results/

# overall 행 제외하고 CSV 저장
python -m metric.event_evaluation --dataset X --output out.csv --no-overall-row

# 옵션
python -m metric.event_evaluation --help
```

출력: 이벤트 단위 지표 테이블 + 전체 평균.

## 지표 해석

| 지표 | 의미 | 해석 (높을수록/낮을수록) |
|------|------|---------------------------|
| **Coherence (C_V)** | 이벤트 내 상위 단어들이 하나의 주제로 얼마나 잘 묶이는지 | 높을수록 좋음 (0.5~0.6: 보통, 0.6+ 양호) |
| **Intra-event similarity** | 같은 이벤트에 속한 기사들 간 유사도 | 높을수록 좋음 (군집 응집도) |
| **Inter-event similarity** | 서로 다른 이벤트(centroid) 간 유사도 | 낮을수록 좋음 (이벤트 구분이 잘 됨) |
| **Fragmentation rate (singleton)** | 싱글톤 이벤트(기사 1개) 비율 | 낮을수록 좋음 (대리 지표, 직접적이지 않음) |
| **Fragmentation by similarity** | 다른 이벤트와 매우 비슷한 이벤트 비율 (병합 후보) | 낮을수록 좋음 (**같은 사건이 쪼개진 경우**에 가깝게 반영) |
| **Merging error rate** | 이벤트 내부 유사도가 낮은 이벤트 비율 (서로 다른 주제가 섞인 의심) | 낮을수록 좋음 |

예: Coherence 0.57, Intra 0.96, Inter 0.19, Fragmentation 0.74, Merging 0.01  
→ 이벤트 내부는 매우 일관되고(Intra 높음), 이벤트 간 구분도 양호(Inter 낮음). 다만 이벤트의 약 74%가 기사 1개뿐(Fragmentation 높음). 병합 오류는 거의 없음(Merging 매우 낮음).

## 지표별 코드 구현

### 1. Coherence (C_V)

- **의미**: 이벤트 내 상위 단어들이 하나의 주제로 얼마나 잘 묶이는지.
- **구현** (`coherence_cv`, `get_top_words_per_event`):
  1. 각 이벤트에 속한 기사들의 `title+description`을 소문자·정규식으로 토큰화(`tokenize`)한 뒤, **해당 이벤트 내에서 빈도 상위 top-k(기본 15개) 단어**를 뽑는다.
  2. 그 top-k 단어 각각을 **sentence-transformer로 임베딩**한다(단어 하나를 문장처럼 인코딩).
  3. 이벤트별로 단어 벡터의 **평균(centroid)**을 구하고 L2 정규화한다.
  4. **C_V = 해당 이벤트의 top-k 단어 벡터 각각과 centroid 간 cosine 유사도의 평균.**  
     → 한 단어라도 centroid와 멀면 coherence가 낮아진다.
- **코드 위치**: `get_top_words_per_event` → `coherence_cv` (L224~L229: `cosines = vecs @ centroid`, `np.mean(cosines)`).

### 2. Intra-event similarity

- **의미**: 같은 이벤트에 속한 기사들 간 유사도(군집 응집도).
- **구현** (`intra_event_similarity`):
  1. 모든 기사에 대해 **sentence-transformer로 문장 임베딩** 한 번 계산.
  2. 이벤트마다 해당 기사 인덱스로 임베딩을 묶어, L2 정규화한 뒤 **같은 이벤트 내 모든 기사 쌍의 cosine 유사도**를 구한다.
  3. **이벤트별 값 = 그 쌍들 유사도의 평균.**  
     - 기사가 1개뿐인 이벤트(싱글톤)는 쌍이 없으므로 **1.0**으로 둔다.
- **수식**: `(sub @ sub.T).sum() - n` 은 대각선 제외 합; 쌍 개수 `n*(n-1)`로 나누면 평균 pairwise cosine.
- **코드 위치**: L252~L257 (`sub = emb[indices]`, `sim = (sub @ sub.T).sum() - n` 등).

### 3. Inter-event similarity

- **의미**: 서로 다른 이벤트(centroid) 간 유사도. 낮을수록 이벤트 구분이 잘 된 것.
- **구현** (`inter_event_similarity`):
  1. 위와 동일한 기사 임베딩을 사용해, **이벤트별로 속한 기사 임베딩의 평균**을 구하고 L2 정규화 → 이벤트 **centroid**.
  2. 각 이벤트 \(i\)에 대해 **다른 모든 이벤트 centroid와의 cosine 유사도**를 구한 뒤 평균한다.
  3. **이벤트별 값 = “나(i)와 다른 이벤트들 간 유사도”의 평균.**  
     이벤트가 1개뿐이면 비교 대상이 없어 **NaN**.
- **코드 위치**: L275~L278 (centroid 계산), L285~L288 (다른 centroid와의 cosine 평균).

### 4. Fragmentation rate (singleton)

- **의미**: 싱글톤 이벤트(기사 1개만 있는 이벤트) 비율. **대리 지표**: “같은 사건이 쪼개졌는가”를 직접 반영하지는 못함.
- **구현** (`fragmentation_rate_per_event`):
  - 각 이벤트의 `source` 필드(기사 id 목록)를 **중복 제거한 뒤 개수**가 1이면 **1.0**, 아니면 **0.0**.
  - **전체** = 이 0/1 값들의 평균 (= 싱글톤 비율).
- **코드 위치**: L296~L303 (`fragmentation_rate_per_event`).

### 4'. Fragmentation by similarity

- **의미**: **다른 이벤트와 centroid 유사도가 threshold(기본 0.85) 이상인 이벤트** 비율. “같은 사건인데 여러 이벤트로 쪼개진 경우”를 더 잘 반영.
- **구현** (`fragmentation_by_similarity_per_event`):
  - 이벤트별 centroid 계산 후, 각 이벤트에 대해 **다른 이벤트와의 cosine 유사도 최댓값**을 구함.
  - 최댓값 ≥ threshold이면 **1**(병합 후보/분할 가능성), 아니면 **0**.
  - **전체** = 이 0/1 값들의 평균.
- **옵션**: `--fragmentation-similarity-threshold` (기본 0.85).
- **코드 위치**: L305~L332 (`fragmentation_by_similarity_per_event`).

### 5. Merging error rate

- **의미**: 이벤트 내부 유사도가 낮은 이벤트 비율(서로 다른 주제가 섞인 것으로 의심).
- **구현** (`merging_error_per_event`):
  - **Intra-event similarity**가 이미 이벤트별로 계산되어 있으므로,  
    **threshold(기본 0.4) 미만이면 1, 이상이면 0**으로 둔다.
  - `--merging-percentile`을 주면 threshold 대신 **전체 intra 분포의 해당 백분위수**를 threshold로 쓴다(예: 25 → 하위 25%를 merging error로 간주).
  - **전체 merging error rate** = 이 0/1 값들의 평균.  
    싱글톤은 intra=1.0이므로 항상 0(병합 오류로 안 셈).
- **코드 위치**: L335~L354 (threshold 또는 percentile로 cutoff 후 0/1 부여).
