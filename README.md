# 📈 차트 읽어주는 AI

<img width="1024" height="559" alt="image (2) (1)" src="https://github.com/user-attachments/assets/6e31dc7f-2dba-45a1-b670-0749a9881231" />

{%preview http://confident-ais.site %}

> **그래프 위에서 핵심 사건을 탐색하고 챗봇과 대화하며 인사이트를 기르는 LLM 기반 선물 시장 금융 대시보드**



## 📌 프로젝트 개요

증권 차트를 보며 “이때 왜 올랐지?” 하고 무심코 검색창을 열어본 경험은 누구나 있을 겁니다. 
하지만 검색 결과를 보는 순간, 쏟아지는 정보와 중복된 기사 속에서 무엇이 실제 원인이었는지 파악하지 못한 채 헤매게 됩니다.

이 서비스는 그런 불편함에서 출발했습니다.
차트 위에서 과거 시장의 움직임을 그대로 복기하며, 가격 흐름과 함께 당시의 사건과 뉴스를 한 눈에 탐색할 수 있습니다.

궁금한 점은 분석 챗봇에게 바로 질문하며 맥락을 이해하고, 상승·하락 관점을 나눈 AI 토론을 관전하며 한쪽에 치우치지 않은 시각으로 사고할 수 있도록 돕습니다.


## 🎬 DEMO
<iframe width="560" height="315" src="https://www.youtube.com/embed/5Cz0nStLCY4?si=dgCtJd-0D3xxQz0J" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>



## ✨ 주요 기능

- **📰 사건 중심 뉴스 분석**
  - 중복된 뉴스 기사를 통합하고, 시장에 의미 있는 핵심 사건만을 추출합니다.
  - 각 사건이 가격 변동에 어떤 영향을 미쳤는지를 가격 데이터와 함께 한눈에 확인할 수 있도록 제공합니다.

- **🗨️ 맥락 기반 Q&A 챗봇**
  - 사용자가 선택한 기간의 차트와 뉴스 데이터를 기반으로 질의응답을 수행합니다.
  - 일반적인 지식이 아닌, **해당 시점의 실제 데이터와 사건**을 근거로 분석을 제공해 보다 정확한 이해를 돕습니다.

- **🆚 대립형 멀티 에이전트 분석**
  - 동일한 기간의 데이터를 바탕으로 상승 요인을 분석하는 **Bull Agent**와 하락 요인을 분석하는 **Bear Agent**가 각각의 논리를 전개합니다.
  - 두 관점의 교차 분석을 통해 특정 방향에 치우치지 않고, 시장을 입체적으로 이해할 수 있는 판단 구조를 제공합니다.

### 🏛️ System Architecture

<img width="2112" height="1206" alt="image (5)" src="https://github.com/user-attachments/assets/499926e9-6ed9-456f-b1be-d24cb9d6fea5" />


- 본 프로젝트는 배치 프로세스를 통해 특정 종목 및 기간에 대해, 원본 데이터로부터 사전에 추출된 사건 데이터를 기반으로 구동됩니다. 

#### 1. 사건 추출 아키텍처

<img width="2000" height="813" alt="image (6)" src="https://github.com/user-attachments/assets/8f991ba8-4ab1-4c53-82ee-410a8447b0f8" />

- 뉴스 기사 데이터를 발행일에 따라 정렬 후, **Tumbling Window**를 적용하여 분할합니다.
- 각 Window마다 **LLM (EXAONE)**을 통해 가격 시장에 영향을 주는 '사건'을 추출합니다.

#### 2. 맥락 기반 챗봇 아키텍처

<img width="3042" height="1180" alt="image (7)" src="https://github.com/user-attachments/assets/21a17712-241e-4d89-8075-964a97d84bbd" />

- 사용자의 입력값(종목, 기간) 및 질문을 입력받아 LLM이 문맥을 파악하고 적절한 도구를 선택적으로 호출합니다.
- **Langfuse**를 활용한 프롬프트 관리와 로깅, **Qdrant** 기반의 RAG, **Playwright·Tavily**를 이용한 실시간 검색 결과를 근거로 정확한 답변을 제공합니다.

#### 3. 멀티 에이전트 아키텍처

각 단계마다 특화된 페르소나를 가진 에이전트들이 상호작용합니다.

- **Step 1. Analyst Agent**: 수만 개의 원천 데이터 중 시장의 내러티브를 전환한 결정적 사건을 선별합니다. 각 사건에 고유 ID를 부여하고 3단계 서사(인과관계-시장 심리-객관적 요약)로 구성된 **마스터 팩트북**을 생성합니다.
- **Step 2. Arena Agents**: 팩트북의 ID를 근거로 상승(Bull)과 하락(Bear) 진영이 **N-Turn 적대적 토론**을 진행하여 확증 편향을 제거합니다.
- **Step 3. Verdict Agent**: 토론 로그를 영향력, 논리 검증, 현실 부합도의 3단계 심사 기준에 따라 분석하여 최종 승자를 선언하고 구체적인 투자 지침을 제공합니다.

### 🗓️ Project Timeline

<img width="1055" height="411" alt="다운로드" src="https://github.com/user-attachments/assets/12373e23-4727-4541-b7ca-f8f0fd98f284" />


## 💯 평가 지표 및 결과


## 🛠️ Tools and Technologies

<div align="center">

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![UV](https://img.shields.io/badge/uv-DE5FE4?style=for-the-badge)
![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)
![Gemini](https://img.shields.io/badge/Google%20Gemini-8E75B2?style=for-the-badge&logo=googlebard&logoColor=white)
![Langfuse](https://img.shields.io/badge/Langfuse-000000?style=for-the-badge&logo=langfuse&logoColor=white)
![Hydra](https://img.shields.io/badge/Hydra-9CA3AF?style=for-the-badge&logo=hydra&logoColor=white)
    
![MySQL](https://img.shields.io/badge/MySQL-4479A1?style=for-the-badge&logo=mysql&logoColor=white)
![Qdrant](https://img.shields.io/badge/Qdrant-WZ0057?style=for-the-badge)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)
    
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-3F4F75?style=for-the-badge&logo=plotly&logoColor=white)
![Tavily](https://img.shields.io/badge/Tavily-000000?style=for-the-badge)
![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)

    
</div>

## ⚙️ Quick Setup

### 1. Repository Clone

```bash
git clone https://github.com/boostcampaitech8/pro-nlp-finalproject-nlp-15.git
cd pro-nlp-finalproject-nlp-15
```

### 2. Environment Setup (using `uv`)

```bash
# uv 설치 (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 의존성 동기화
uv sync --all-extras
```

### 3. Configure Environment Variables

`.env.example` 파일을 복사하여 `.env`를 생성하고 API 키를 입력합니다.

```bash
cp .env.example .env
```

```ini
# .env file
GEMINI_API_KEY=your_key_here
QDRANT_URL=http://localhost:6333
MYSQL_HOST=localhost
...
```

### 4. Run Application

```bash
# Streamlit 앱 실행
uv run streamlit run app/chatbot_app.py
```

## 👥 Collaborators

<div align="center">

|                                                        팀원                                                         |             역할              |
| :-----------------------------------------------------------------------------------------------------------------: | :---------------------------: |
| <a href="https://github.com/kjsoo-1010"><img src="https://github.com/kjsoo-1010.png" width="100"></a><br>**강지수** |  데이터 EDA, 사건 추출 평가   |
|      <a href="https://github.com/LEE5J"><img src="https://github.com/LEE5J.png" width="100"></a><br>**이석진**      | LLM 서빙 및 파이프라인 최적화 |
|  <a href="https://github.com/lim010111"><img src="https://github.com/lim010111.png" width="100"></a><br>**임우현**  |  챗봇 개발 및 VectorDB 구성   |
|     <a href="https://github.com/Oknook"><img src="https://github.com/Oknook.png" width="100"></a><br>**전현철**     |   웹 프론트 및 백엔드 담당    |
|   <a href="https://github.com/joon2730"><img src="https://github.com/joon2730.png" width="100"></a><br>**정예준**   |           챗봇 및 사건 추출 개발           |
| <a href="https://github.com/Jihyunjune"><img src="https://github.com/Jihyunjune.png" width="100"></a><br>**지현준** |      멀티 에이전트 개발       |

</div>

## 🎬 영상 자료

### 발표 영상

[![Presentation](https://img.shields.io/badge/YouTube-Presentation-red?style=for-the-badge&logo=youtube)](https://youtu.be/tbQinetF33I)

### 시연 영상

[![Demo](https://img.shields.io/badge/YouTube-Demo-red?style=for-the-badge&logo=youtube)](https://youtu.be/5Cz0nStLCY4?si=LcG06qZ48eQKpIa9)

<br/>

> **Disclaimer**: 본 서비스가 제공하는 정보는 투자 권유가 아니며, 투자의 책임은 전적으로 사용자에게 있습니다.


