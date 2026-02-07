import streamlit as st
import pandas as pd
import os, sys
import typing
from dotenv import load_dotenv

load_dotenv()

import plotly.graph_objects as go
from hydra import initialize, compose
from hydra.core.global_hydra import GlobalHydra
from langchain_community.chat_message_histories import StreamlitChatMessageHistory

# --- New Module Imports ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chatbot.bot.agent import FinancialAgent
from db.price_repo import PriceRepository
from db.event_repo import EventRepository
from db.database import get_engine
from chatbot.multi_agent.arena import Arena

# --- Hydra Init ---
@st.cache_resource
def load_config():
    """Load configuration once and cache it."""
    if GlobalHydra.instance().is_initialized():
        GlobalHydra.instance().clear()
    with initialize(version_base=None, config_path="../config"):
        return compose(config_name="chatbot")

cfg = load_config()

st.set_page_config(page_title="AI Financial Intelligence", layout="wide")

# --- Style / CSS ---
st.markdown("""
    <style>
    /* Premium Font & Theme */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap');
    
    * { font-family: 'Outfit', sans-serif; }
    
    .stApp {
        background: radial-gradient(circle at top left, #0e1117, #1a1c24);
    }
    
    /* Top Bar / Header */
    .top-bar {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(15px);
        border-radius: 15px;
        padding: 1.5rem;
        margin-bottom: 2rem;
        border: 1px solid rgba(255, 255, 255, 0.05);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
    }
    
    .main-title {
        background: linear-gradient(90deg, #007AFF, #00C7BE);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 700;
        font-size: 2.2rem;
        margin-bottom: 1rem;
    }
    
    /* Metric Card Styling */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 600;
        color: #007AFF;
    }
    
    /* Sidebar removal hack */
    [data-testid="stSidebar"] {
        display: none;
    }
    
    /* Widget Styling */
    .stSelectbox label, .stDateInput label {
        color: #888 !important;
        font-size: 0.8rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Button Animation */
    button[kind="primary"] {
        background: linear-gradient(90deg, #007AFF, #0051FF) !important;
        border: none !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease !important;
    }
    button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(0, 122, 255, 0.4);
    }
    </style>
""", unsafe_allow_html=True)

# === PERFORMANCE OPTIMIZATION: Cache expensive resources ===
# VectorStore loads 2 embedding models (~3-5 seconds EACH TIME without caching)

@st.cache_resource
def get_shared_engine():
    """Cache the SQLAlchemy engine with central config."""
    db_cfg = cfg.get('database', {})
    return get_engine(db_cfg)

@st.cache_resource
def init_stock_api():
    """Cache StockAPI - avoid repeated CSV file scans."""
    return PriceRepository(get_shared_engine())

@st.cache_resource
def init_news_repo():
    """Cache NewsRepository - avoid repeated JSONL file reads."""
    return EventRepository(get_shared_engine())

@st.cache_resource
def init_financial_agent():
    """Cache FinancialAgent - CRITICAL for performance."""
    return FinancialAgent(cfg)

@st.cache_resource
def init_multi_agent_arena():
    """Cache Multi-Agent Arena."""
    llm_client = init_financial_agent().client
    return Arena(cfg, llm_client)

# === EAGER LOADING: Preload ALL resources at startup ===
if "resources_loaded" not in st.session_state:
    with st.spinner("⚡ Initializing Analysis Engine (Loading Models)..."):
        init_financial_agent()
        st.session_state.resources_loaded = True

# --- Chat Fragment (Isolates UI Reruns) ---
@st.fragment
def chat_interface(asset_name: str, start_date: typing.Any, end_date: typing.Any):
    """
    Renders the chat interface in an isolated fragment.
    This prevents the main chart and timeline from re-rendering on every message.
    """
    msgs = StreamlitChatMessageHistory(key="chat_messages")
    
    # History Sync (Asset change check)
    if "last_asset_fragment" not in st.session_state or st.session_state.last_asset_fragment != asset_name:
        msgs.clear()
        st.session_state.last_asset_fragment = asset_name

    # Chat UI container
    chat_box = st.container(height=750)
    for msg in msgs.messages:
        chat_box.chat_message(msg.type).write(msg.content)

    if query := st.chat_input("Ask about market drivers..."):
        # 1. Immediately show user message
        with chat_box:
            st.chat_message("user").write(query)
        
        # 2. Assistant response
        with chat_box.chat_message("assistant"):
            agent = init_financial_agent()
            status_placeholder = st.empty()
            
            # Stream the response
            def stream_content():
                has_content = False
                for chunk in agent.analyze_stream_agentic(
                    asset_name, 
                    str(query), 
                    start_date, 
                    end_date, 
                    msgs.messages
                ):
                    if hasattr(chunk, "content") and chunk.content:
                        # Clear the "Analyzing" spinner as soon as we get the first chunk of text
                        if not has_content:
                            status_placeholder.empty()
                            has_content = True
                        yield str(chunk.content)
            
            # Use st.spinner for a cleaner "Analyzing" look
            with status_placeholder:
                with st.spinner("Analyzing market data..."):
                    response = st.write_stream(stream_content())
            
            full_ans = str(response) if response else ""
            
        # History is now managed INTERNALLY by the agent 
        # to ensure correct turn order for Gemini.

@st.fragment
def multi_agent_interface(asset_name: str, start_date: typing.Any, end_date: typing.Any):
    """
    Renders the Multi-Agent Debate interface with refined UI/UX.
    """
    st.markdown(f"### ⚔️ AI Market Debate: {asset_name}")
    arena = init_multi_agent_arena()
    
    col_btn, col_opt = st.columns([0.7, 0.3])
    with col_opt:
        rounds = st.slider("Debate Rounds", min_value=1, max_value=5, value=1)
    
    if col_btn.button("🚀 Start Multi-Agent Debate", type="primary", use_container_width=True):
        st.session_state.debate_running = True
        st.session_state.debate_messages = []
        st.session_state.debate_rounds = rounds

    # Guide: Display below the button, but hide during debate
    if not st.session_state.get("debate_running", False):
        st.info("""
        **토론 구성 및 시스템 가이드**
        1. **Analyst (시장 분석관)**: 객관적인 데이터를 바탕으로 핵심 사건과 가격 동향을 조사하여 **Fact Book**을 작성합니다.
        2. **Bear Analyst (하락론자)**: 시장의 잠재적 리스크, 공급 과잉, 매도 압력 등 **부정적 요인**에 집중합니다.
        3. **Bull Strategist (상승론자)**: 시장의 호재, 수요 증가, 성장 잠재력 등 **긍정적 동인**을 중심으로 대응합니다.
        4. **Market Verdict (최종 판결)**: 양측의 논리를 객관적으로 평가하여 시장의 향후 방향성에 대한 **최종 결론**을 내립니다.
        """)
        
    if "debate_running" in st.session_state and st.session_state.debate_running:
        analytical_status = st.status("🔍 Initializing Market Research...", expanded=True)
        log_box = st.container(height=650)
        
        # Prepare data for debate
        with analytical_status:
            st.write("📡 Fetching historical events and price data...")
            event_data = news_repo.search_events(start_date, end_date, asset_symbol=asset_name)
            price_summary = stock_api.get_summary(asset_name, start_date, end_date)
        
        async def run_it():
            try:
                async for update in arena.run_debate_stream(
                    asset_name, 
                    str(end_date), 
                    event_data, 
                    price_summary,
                    rounds=st.session_state.get("debate_rounds", 1)
                ):
                    status = update.get("status")
                    
                    if status == "analyzing":
                        analytical_status.update(label=f"🕵️ {update.get('message')}", state="running")
                    
                    elif status == "fact_book":
                        analytical_status.update(label="✅ Fact Book Research Completed", state="complete", expanded=False)
                        with log_box:
                            with st.expander("📝 Market Case Brief (Fact Book)", expanded=True):
                                fb = update.get("content", {})
                                st.caption(f"**Target Asset**: {fb.get('asset')} | **Reference Date**: {fb.get('end_date')}")
                                
                                for i, item in enumerate(fb.get("critical_facts", []), 1):
                                    st.markdown(f"#### Fact #{i}")
                                    st.markdown(item.get("fact_summary"))
                                    st.markdown("---")
                    
                    elif status in ["bear_warning", "bull_argue", "judging"]:
                        # We don't need a status box update here as we're in the chat phase, 
                        # but we can optionally show a transient message or log it.
                        pass
                        
                    elif status == "bear_stream":
                        if not st.session_state.debate_messages or st.session_state.debate_messages[-1]["role"] != "bear":
                            st.session_state.debate_messages.append({"role": "bear", "content": ""})
                            with log_box:
                                col_bear, col_empty = st.columns([0.85, 0.15])
                                with col_bear.chat_message("Bear Analyst", avatar="app/static/bear_icon.png"):
                                    st.markdown("🔴 **Bear Analyst (하락론자)**")
                                    st.session_state.bear_placeholder = st.empty()
                        
                        st.session_state.debate_messages[-1]["content"] += update.get("chunk")
                        st.session_state.bear_placeholder.markdown(st.session_state.debate_messages[-1]["content"])

                    elif status == "bull_stream":
                        if not st.session_state.debate_messages or st.session_state.debate_messages[-1]["role"] != "bull":
                            st.session_state.debate_messages.append({"role": "bull", "content": ""})
                            with log_box:
                                col_empty, col_bull = st.columns([0.15, 0.85])
                                with col_bull.chat_message("Bull Strategist", avatar="app/static/bull_icon.png"):
                                    st.markdown("🟢 **Bull Strategist (상승론자)**")
                                    st.session_state.bull_placeholder = st.empty()
                        
                        st.session_state.debate_messages[-1]["content"] += update.get("chunk")
                        st.session_state.bull_placeholder.markdown(st.session_state.debate_messages[-1]["content"])

                    elif status == "verdict_stream":
                        if not st.session_state.debate_messages or st.session_state.debate_messages[-1]["role"] != "verdict":
                            st.session_state.debate_messages.append({"role": "verdict", "content": ""})
                            with log_box.chat_message("Market Verdict", avatar="app/static/verdict_icon.png"):
                                st.markdown("### ⚖️ Final Market Verdict")
                                st.session_state.verdict_placeholder = st.empty()
                        
                        st.session_state.debate_messages[-1]["content"] += update.get("chunk")
                        st.session_state.verdict_placeholder.markdown(st.session_state.debate_messages[-1]["content"])
            except Exception as e:
                st.error(f"⚠️ Debate Interrupted: {str(e)}")
            finally:
                st.session_state.debate_running = False

        import asyncio
        asyncio.run(run_it())

# --- Dependencies ---
stock_api = init_stock_api()
news_repo = init_news_repo()


# --- Initial State & Date Handling ---
if "init_done" not in st.session_state:
    st.session_state.start_date = None
    st.session_state.end_date = None
    st.session_state.init_done = True

# --- Control Logic (Asset Mapping) ---
asset_map = stock_api.list_assets()
asset_ko_names = list(asset_map.keys())

# --- Main Layout Split ---
col_main_left, col_main_right = st.columns([2.5, 1], gap="large")

with col_main_left:
    st.markdown('<div class="main-title">Graph Insight</div>', unsafe_allow_html=True)
    
    # --- Top Bar Controls (Inside Left Column) ---
    with st.container():
        t_col1, t_col2, t_col3, t_col4 = st.columns([1.5, 1, 1, 1], gap="small")
        
        with t_col1:
            # Load selection from query if possible, otherwise first one
            selected_ko = st.selectbox("종목 선택", asset_ko_names)
            asset_name = asset_map.get(selected_ko, "Unknown")
            
        df = stock_api.get_prices(asset_name)
        
        if not df.empty:
            # Source of Truth: Query Params
            q_start = st.query_params.get("start_date")
            q_end = st.query_params.get("end_date")
            
            if q_start and q_end:
                st.session_state.start_date = pd.to_datetime(q_start).date()
                st.session_state.end_date = pd.to_datetime(q_end).date()
            else:
                st.session_state.start_date = pd.to_datetime(cfg.system.data_range.start).date()
                st.session_state.end_date = pd.to_datetime(cfg.system.data_range.end).date()
                st.query_params["start_date"] = str(st.session_state.start_date)
                st.query_params["end_date"] = str(st.session_state.end_date)

            with t_col2:
                new_start = st.date_input("시작일", key=f"sdt_{st.session_state.start_date}", value=st.session_state.start_date)
            with t_col3:
                new_end = st.date_input("종료일", key=f"edt_{st.session_state.end_date}", value=st.session_state.end_date)
            with t_col4:
                st.write("") # Adjust vertical alignment
                st.write("")
                if st.button("🔄 기간 초기화", use_container_width=True):
                     st.session_state.start_date = pd.to_datetime(cfg.system.data_range.start).date()
                     st.session_state.end_date = pd.to_datetime(cfg.system.data_range.end).date()
                     st.query_params["start_date"] = str(st.session_state.start_date)
                     st.query_params["end_date"] = str(st.session_state.end_date)
                     st.rerun()

            # Update State & Query Params
            if new_start != st.session_state.start_date:
                st.session_state.start_date = new_start
                st.query_params["start_date"] = str(new_start)
                st.rerun()
            if new_end != st.session_state.end_date:
                st.session_state.end_date = new_end
                st.query_params["end_date"] = str(new_end)
                st.rerun()

    # Chart Selection Sync
    def handle_chart_selection():
        if "main_chart" in st.session_state and st.session_state.main_chart:
            selected = st.session_state.main_chart
            if "selection" in selected and "box" in selected["selection"]:
                box = selected["selection"]["box"]
                if box and "x" in box[0]:
                    x_range = box[0]["x"]
                    try:
                        ns = pd.to_datetime(x_range[0]).date()
                        ne = pd.to_datetime(x_range[1]).date()
                        if str(ns) != st.query_params.get("start_date") or str(ne) != st.query_params.get("end_date"):
                            st.query_params["start_date"] = str(ns)
                            st.query_params["end_date"] = str(ne)
                            st.session_state.start_date = ns
                            st.session_state.end_date = ne
                            st.rerun()
                    except Exception: pass

    handle_chart_selection()
    st.markdown('<hr style="margin-top:0.5rem; margin-bottom:1.5rem; border:0; border-top:1px solid rgba(255,255,255,0.05);">', unsafe_allow_html=True)

    # Event/News filtering is now handled by the RDB many-to-many relationship
    # No need for manual file selection
    

    # --- Market Content (Left Column) ---
    if df.empty:
        st.error("데이터를 불러올 수 없습니다.")
    else:
        visible_mask = (df['time'].dt.date >= st.session_state.start_date) & (df['time'].dt.date <= st.session_state.end_date)
        v_data = df.loc[visible_mask]
        
        if v_data.empty: 
            st.warning("선택한 기간에 데이터가 없습니다.")
        else:
            # Metrics
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            start_p = v_data.iloc[0]['close']
            end_p = v_data.iloc[-1]['close']
            ret = ((end_p - start_p) / start_p) * 100
            vol = v_data['close'].pct_change().std() * (252**0.5) * 100
            
            m_col1.metric("수익률", f"{ret:.2f}%", f"{end_p - start_p:.2f}")
            m_col2.metric("변동성 (연율)", f"{vol:.2f}%")
            m_col3.metric("시작일", f"{st.session_state.start_date}")
            m_col4.metric("종료일", f"{st.session_state.end_date}")

            # Enhanced Chart
            fig = go.Figure(go.Scatter(
                x=v_data['time'], 
                y=v_data['close'], 
                mode='lines', 
                line=dict(color='#007AFF', width=3),
                fill='tozeroy',
                fillcolor='rgba(0, 122, 255, 0.1)'
            ))
            
            fig.update_layout(
                height=650,
                template="plotly_dark",
                dragmode="select",
                margin=dict(l=0, r=0, t=20, b=0),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(rangeslider=dict(visible=False), showgrid=False, color="#888"),
                yaxis=dict(autorange=True, showgrid=True, gridcolor="rgba(255,255,255,0.05)", color="#888"),
                hovermode="x unified"
            )
            
            st.plotly_chart(fig, on_select="rerun", selection_mode="box", key="main_chart", use_container_width=True)

# --- Side Panel Content (Right Column - Starts from top) ---
with col_main_right:
    tab_ev, tab_chat, tab_multi = st.tabs(["📅 Timeline", "🤖 AI Analyst", "⚔️ AI Debate"])
    
    with tab_ev:
        @st.cache_data(ttl=3600)
        def get_cached_events(asset_name, start_date, end_date):
            return news_repo.search_events(start_date, end_date, asset_symbol=asset_name)

        @st.fragment
        def render_timeline(asset_name, start_date, end_date):
            display_events = get_cached_events(asset_name, start_date, end_date)
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.caption(f"📊 {len(display_events)} 사건 발견")
            with col2:
                if st.button("🔄", key="refresh_events"):
                    get_cached_events.clear()
                    st.rerun()
            
            with st.container(height=800):
                for ev in display_events:
                    with st.container(border=True):
                        d = ev.get('start_date') or ev.get('date', 'Unknown')
                        t = ev.get('title', 'No Title')
                        desc = ev.get('description', '')
                        st.markdown(f"**{d}** | {t}")
                        if desc: st.markdown(f"<small style='color:#ccc'>{desc}</small>", unsafe_allow_html=True)
                        
                        articles = ev.get('articles', [])
                        if articles:
                            for art in articles[:2]:
                                title = art.get('title', 'Untitled')
                                url = art.get('url', '')
                                if url: st.markdown(f"<small>[- {title}]({url})</small>", unsafe_allow_html=True)
                                else: st.markdown(f"<small>- {title}</small>", unsafe_allow_html=True)
        
        render_timeline(asset_name, st.session_state.start_date, st.session_state.end_date)

    with tab_chat:
        chat_interface(asset_name, st.session_state.start_date, st.session_state.end_date)
        
    with tab_multi:
        multi_agent_interface(asset_name, st.session_state.start_date, st.session_state.end_date)