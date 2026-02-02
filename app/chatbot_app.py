import streamlit as st
import os, datetime, sys, json
import pandas as pd
import plotly.graph_objects as go
import tiktoken
from hydra import initialize, compose
from hydra.core.global_hydra import GlobalHydra
from langchain_community.chat_message_histories import StreamlitChatMessageHistory

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chatbot.utils import *
from chatbot.agent import FinancialAgent

def estimate_tokens(text, model):
    try: encoding = tiktoken.encoding_for_model(model)
    except: encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

# --- Hydra 및 세션 초기화 ---
if "cfg" not in st.session_state:
    if GlobalHydra.instance().is_initialized(): GlobalHydra.instance().clear()
    with initialize(version_base=None, config_path="../config"):
        st.session_state.cfg = compose(config_name="chatbot")

cfg = st.session_state.cfg
st.set_page_config(page_title="AI Financial Intelligence", layout="wide")

# --- 사이드바 및 자산 선택 ---
with st.sidebar:
    st.title("🛡️ Analysis Settings")
    csv_files = get_all_csv_files(cfg.data.dir_path)
    selected_file = st.selectbox("Select Asset", csv_files)
    asset_name = selected_file.replace("_price.csv", "")
    full_path = os.path.join(cfg.data.dir_path, selected_file)

    if "last_asset" not in st.session_state or st.session_state.last_asset != asset_name:
        temp_df = pd.read_csv(full_path)
        temp_df['time'] = pd.to_datetime(temp_df['time'])
        st.session_state.start_date, st.session_state.end_date = temp_df['time'].min().date(), temp_df['time'].max().date()
        st.session_state.last_asset = asset_name

    # st.date_input removed from here to fix StreamlitAPIException
    pass

# --- 데이터 로드 ---
# --- 데이터 로드 ---
# 1. 전체 데이터 로드 (차트용 / 날짜 범위 계산용)
df_metric = pd.read_csv(full_path)
df_metric['time'] = pd.to_datetime(df_metric['time'])

# 2. 선택된 기간으로 데이터 필터링 (AI 에이전트용)
mask = (df_metric['time'].dt.date >= st.session_state.start_date) & (df_metric['time'].dt.date <= st.session_state.end_date)
df = df_metric.loc[mask].sort_values('time')

# --- Event Selection (Manual) ---
all_event_files = get_all_event_files(cfg.data.event_result_path)
# 사용자 편의를 위해 자산명과 관련된 파일을 디폴트로 선택해줄 수는 있으나, 
# "스스로 선택하게 해줘"라는 요청에 따라 모든 리스트를 보여주고 선택하게 함.
# (기본값은 자동 매칭된 결과로 설정하여 편의성 제공)
default_matches = [f for f in all_event_files if asset_name in f]

with st.sidebar:
    st.divider()
    st.subheader("📂 Event Files")
    selected_event_files = st.multiselect(
        "Choose Event Source", 
        all_event_files, 
        default=default_matches
    )

# 선택된 파일이 없으면 (사용자가 다 껐다면) 빈 리스트 전달 -> 태스크 요청은 '스스로 선택'이므로 키워드 매칭 안함.
# target_files가 빈 리스트면 -> 아무것도 로드 안됨. None이면 -> 키워드 로직 탈텐데, 
# load_events_by_period 로직 상 target_files가 [] (empty list)여도 is not None 이므로 로직 1번을 타고 아무것도 반환 안함.
# 만약 사용자가 아무것도 선택 안했을 때 '전체'를 원할까? 아니면 '없음'을 원할까? 
# 문맥상 "스스로 선택"하고 싶다 했으니, 선택 안하면 없는게 맞음.
event_list = load_events_by_period(
    cfg.data.event_result_path, 
    st.session_state.start_date, 
    st.session_state.end_date, 
    keywords=None, # 매뉴얼 선택 모드에서는 자동 키워드 무시
    target_files=selected_event_files
)
selected_days = (st.session_state.end_date - st.session_state.start_date).days

# --- UI 레이아웃 ---
st.subheader(f"Market Analysis: {asset_name.upper()}")
col_chart, col_side = st.columns([2, 1])

with col_chart:
    if selected_days > cfg.limits.max_days_range:
        st.warning(f"⚠️ Range exceeded ({selected_days} days). Please narrow down the chart.")
    
    # 전체 데이터를 차트에 표시하되, X축 범위(range)로 현재 선택된 구간을 보여줌
    fig = go.Figure(go.Scatter(x=df_metric['time'], y=df_metric['close'], mode='lines', line=dict(color='#007AFF')))
    
    # Y축 스케일 동적 조정 (현재 보이는 구간의 Min/Max 기준)
    # 전체 데이터가 아니라 '현재 X축 범위'에 해당하는 데이터만으로 Y축 범위를 계산해야 그래프가 Flat해지지 않음
    visible_mask = (df_metric['time'].dt.date >= st.session_state.start_date) & (df_metric['time'].dt.date <= st.session_state.end_date)
    visible_data = df_metric.loc[visible_mask]
    
    if not visible_data.empty:
        y_min = visible_data['close'].min()
        y_max = visible_data['close'].max()
        y_margin = (y_max - y_min) * 0.05 # 5% 여유
        y_range = [y_min - y_margin, y_max + y_margin]
    else:
        y_range = None # 데이터가 없으면 자동

    fig.update_layout(
        height=550, 
        template="plotly_dark", 
        dragmode="select", 
        xaxis=dict(
            rangeslider=dict(visible=True),
            # 현재 선택된 기간으로 줌 인 (Zoom In)
            range=[st.session_state.start_date, st.session_state.end_date]
        ),
        yaxis=dict(
            autorange=False if y_range else True,
            range=y_range
        )
    )
    
    # 사용자가 차트에서 Box Select를 하면 그 범위로 start_date/end_date 업데이트
    selected = st.plotly_chart(fig, use_container_width=True, on_select="rerun", selection_mode="box")
    if selected and "selection" in selected and "box" in selected["selection"]:
        box = selected["selection"]["box"]
        if box:
            new_start = pd.to_datetime(box[0]["x"][0]).date()
            new_end = pd.to_datetime(box[0]["x"][1]).date()
            if new_start != st.session_state.start_date or new_end != st.session_state.end_date:
                # 1. 메인 상태 업데이트
                st.session_state.start_date = new_start
                st.session_state.end_date = new_end
                # 2. 위젯 키 상태 동기화 (이게 없으면 위젯이 이전 값을 유지하여 리셋 현상 발생)
                st.session_state.start_date_input = new_start
                st.session_state.end_date_input = new_end
                st.rerun()

# --- Sidebar (Date Input) - Rendered AFTER chart to allow state updates ---
def update_dates():
    st.session_state.start_date = st.session_state.start_date_input
    st.session_state.end_date = st.session_state.end_date_input

with st.sidebar:
    st.date_input("Start Date", value=st.session_state.start_date, key="start_date_input", on_change=update_dates)
    st.date_input("End Date", value=st.session_state.end_date, key="end_date_input", on_change=update_dates)

with col_side:
    tab_ev, tab_chat = st.tabs(["Timeline", "AI Analyst"])
    with tab_ev:
        for ev in event_list[:30]:
            with st.container(border=True):
                st.caption(ev['start_date'])
                st.write(ev['title'])

    # --- Sidebar Option: Clear Chat ---
    if st.sidebar.button("🧹 Clear Chat History"):
        StreamlitChatMessageHistory(key="chat_messages").clear()
        
    with tab_chat:
        msgs = StreamlitChatMessageHistory(key="chat_messages")
        
        # --- Context Management (Caching & History Sync) ---
        # 1. 이전 설정과 현재 설정 비교
        current_config_state = {
            "start": st.session_state.start_date, 
            "end": st.session_state.end_date, 
            "asset": asset_name,
            "events": selected_event_files
        }
        
        # 2. 변경사항 감지 및 대화 내역 처리
        if "last_config" in st.session_state:
            last = st.session_state.last_config
            
            # 자산이 변경되면 문맥 혼동 방지를 위해 대화 초기화
            if last["asset"] != asset_name:
                msgs.clear()
                st.toast(f"Asset changed to {asset_name}. Chat history cleared.", icon="🧹")
            
            # 날짜만 변경된 경우, 대화 내역에 '변경 알림' 주입 (기억 유지)
            # 단, 데이터가 존재하는 유효한 범위("가능 범위")일 때만 알림
            elif (last["start"] != current_config_state["start"]) or (last["end"] != current_config_state["end"]):
                if not df.empty:
                    system_note = f"🔄 **System Notification**: Analysis period changed from {last['start']}~{last['end']} to {current_config_state['start']}~{current_config_state['end']}."
                    msgs.add_ai_message(system_note)

        # 3. 데이터 컨텍스트 갱신 (캐시가 없거나 설정이 바뀌었을 때)
        if "data_context" not in st.session_state or st.session_state.get("last_config") != current_config_state:
            with st.spinner("Generating analysis context..."):
                # Price Context
                price_context = get_market_statistical_summary(df, asset_name)
                # Event Context
                event_context = get_causality_aware_events(event_list, df, cfg, max_count=cfg.limits.max_event_count)
                
                # Cache update
                st.session_state.data_context = {"price": price_context, "event": event_context}
                st.session_state.last_config = current_config_state
        
        # 4. 캐시된 컨텍스트 사용
        price_val = st.session_state.data_context["price"]
        event_val = st.session_state.data_context["event"]
        
        # --- Token Density Calculation (Full Context) ---
        # Instruction(Prompt) + Data Context + History
        full_context_text = price_val + event_val
        tokens = estimate_tokens(full_context_text, cfg.llm[cfg.llm.provider].model)
        st.info(f"💾 Reference Data Size: {tokens:,} tokens (Cached)")

        agent = FinancialAgent(cfg)
        
        chat_box = st.container(height=450)
        for msg in msgs.messages: chat_box.chat_message(msg.type).write(msg.content)

        if query := st.chat_input("Ask about market drivers...", disabled=(selected_days > cfg.limits.max_days_range)):
            with chat_box: st.chat_message("user").write(query)
            with chat_box.chat_message("assistant"):
                res = st.empty(); full_ans = ""
                # agent.analyze_stream에 캐시된 컨텍스트 전달
                for p in agent.analyze_stream(asset_name, query, price_val, event_val, msgs.messages):
                    content = p.content if hasattr(p, "content") else str(p)
                    full_ans += content
                    res.markdown(full_ans + "▌")
                res.markdown(full_ans)
                msgs.add_user_message(query); msgs.add_ai_message(full_ans)