## AI 투자 도슨트 시스템
---

### Phase 1: Fact Extraction  
### (마스터 스키마 추출)

- **주체 모델**: EXAONE-3.0-70B  
  *(현재 개발 단계에서는 로컬 환경의 EXAONE-3.0-7.8B로 대체 운용)*

- **Input**  
  - 금융 뉴스 원문  
  - 뉴스 메타데이터 (timestamp, source 등)

- **Core Logic**  
  - **Schema-based Information Extraction**
  - 사건을 감정·해석 이전의 **구성요건 단위**로 분해

- **Output**
  - **사건 스키마**
    - Date / Subject / Action / Object / Result / Scope
  - **기본 서사 리포트**
    - 가치 판단을 배제한 중립적 사건 요약

> 이 단계의 목적은 “해석”이 아니라  
> **토론 가능한 사실의 최소 단위**를 만드는 것입니다.

---

### Phase 2: Interactive Arena  
### (이해 중심의 적대적 토론)

- **주체 모델**: EXAONE-3.0-7.8B  
  - Bull Agent (긍정적 해석)
  - Bear Agent (부정적 해석)

- **Input**
  - Phase 1에서 추출된 사건 스키마
  - 원문 뉴스 텍스트

- **Interaction Loop**

  1. **Turn 1 – Position Declaration**  
     - 각 에이전트의 해석 프레임 제시  
     - *이해도 체크 ①*

  2. **Turn 2 – OBJECTION!**  
     - 상대 논리에 대한 합리적 의심 제기  
     - 리스크, 누락 가정, 과잉 추론 공격

  3. **Turn 3 – Final Argument**  
     - 반박을 반영한 보충 설명  
     - *이해도 체크 ②*

- **Key Feature**
  - 사용자의 이해 수준에 맞춰  
    **비유·예시·맥락 설명을 점진적으로 강화하는 도슨트 로직**

> 이 단계는 “누가 맞는가”가 아니라  
> **왜 의견이 갈릴 수 있는가**를 보여주는 구간입니다.

---

### Phase 3: Final Verdict  
### (논리적 최종 판결)

- **주체 모델**: EXAONE-3.0-70B  
  *(현재는 로컬 7.8B 모델로 기능 검증 단계)*

- **Input**
  - 사건 스키마
  - Bull / Bear 토론 로그
  - 사용자 피드백 (선택)

- **Reasoning Framework**  
  **Trichotomous Reasoning (3단 추론 구조)**

  1. **Offense (구성요건 해당성)**  
     - 사건의 실질적 발생 여부  
     - 시장에 미치는 객관적 규모

  2. **Unlawfulness (부당성 조각)**  
     - 리스크 요인 및 반대 논거의 타당성

  3. **Culpability (영향력 확정)**  
     - 가격 영향 가능성 평가  
     - 판단 유보 또는 조기 종료 결정

- **Output**
  - 통합 서사 리포트  
  - 조건부 가격 영향 시나리오

> 최종 결과는 “정답”이 아니라  
> **논리적으로 설명 가능한 결론**을 목표로 합니다.

---

## Current Development Status & Limitations

- **모델 서빙 환경**
  - 대형(70B) 모델 서버 활용 못한 상태
  - 7.8B 모델이 마스터 및 에이전트 역할을 수행 -> 70b(서사 요약) & 7b(arena) & 70b(요약 & 가격 예측)

- **데이터 소스**
  - 뉴스 원문 미적용
  - 프로젝트 멤버(예준) 제공 **JSONL 데이터셋** 기반
  - 특정 `event_id` 단위로 파이프라인 검증

- **프롬프트 관리**
  - 지시문 복창 및 역할 붕괴 방지를 위해  
    **YAML 기반 프롬프트 관리 시스템** 도입
  - 수정 필요

---

