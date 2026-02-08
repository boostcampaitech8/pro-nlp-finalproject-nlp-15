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
    /* Sharp Premium Font & Theme */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;1,700&display=swap');
    
    * { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }
    
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
        color: #ffffff;
        font-weight: 700;
        font-size: 2.2rem;
        margin-bottom: 1rem;
        letter-spacing: -0.02em;
    }
    
    /* Metric Card Styling - Sophisticated Serif & White */
    [data-testid="stMetricValue"] {
        font-family: 'Playfair Display', serif !important;
        font-size: 2.4rem;
        font-weight: 700;
        color: #ffffff !important;
        letter-spacing: -0.01em;
        line-height: 1.2;
    }
    [data-testid="stMetricLabel"] {
        color: #888 !important;
        font-weight: 500 !important;
    }
    
    /* Sidebar removal hack */
    [data-testid="stSidebar"] {
        display: none;
    }
    
    /* Widget Styling */
    .stSelectbox label, .stDateInput label {
        color: #aaa !important;
        font-size: 0.8rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 1.2px;
    }
    
    /* Button Styling - Solid & Sharp */
    button[kind="primary"] {
        background: #007AFF !important;
        border: none !important;
        color: white !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        transition: all 0.2s ease !important;
    }
    button[kind="primary"]:hover {
        background: #0051FF !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 122, 255, 0.3);
    }
    button[kind="secondary"] {
        background: transparent !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        color: #fff !important;
        border-radius: 8px !important;
    }
    button[kind="secondary"]:hover {
        border-color: #fff !important;
        background: rgba(255, 255, 255, 0.05) !important;
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
    chat_box = st.container(height=850)
    
    # Default Greeting if empty
    if len(msgs.messages) == 0:
        msgs.add_ai_message(f"안녕하세요! {asset_name} 시장 분석 전문가 AI Analyst입니다. 특정 기간의 가격 변동 원인이나 주요 뉴스에 대해 무엇이든 물어보세요.")

    for msg in msgs.messages:
        # Only show Human and AI messages that have actual text content
        if msg.type in ("human", "ai"):
            if msg.content:
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
    
    is_debate_running = st.session_state.get("debate_running", False)
    if col_btn.button(
        "🚀 Start Multi-Agent Debate", 
        type="primary", 
        use_container_width=True, 
        disabled=is_debate_running
    ):
        st.session_state.debate_running = True
        st.session_state.debate_messages = []
        st.session_state.debate_rounds = rounds
        st.rerun() # Trigger a rerun to show the status and lock the button

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
        log_box = st.container(height=660)
        
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


if "init_done" not in st.session_state:
    st.session_state.start_date = None
    st.session_state.end_date = None
    st.session_state.timeline_page = 0 
    st.session_state.timeline_search = ""
    st.session_state.timeline_sort_by = "volatility" 
    st.session_state.timeline_sort_order = "desc"
    st.session_state.highlighted_events = {} 
    st.session_state.init_done = True

# --- Control Logic (Asset Mapping) ---
asset_map = stock_api.list_assets()
asset_ko_names = list(asset_map.keys())

# --- Main Layout Split ---
col_main_left, col_main_right = st.columns([2.5, 1], gap="large")

with col_main_left:
    st.markdown('<div class="main-title">차트 읽어주는 AI - Graph Insight</div>', unsafe_allow_html=True)
    
    # --- Top Bar Controls (Inside Left Column) ---
    with st.container():
        # Field columns (t_cols) and Button column (t_btn)
        t_cols, _, t_btn = st.columns([0.5, 0.25, 0.25], gap="large") 
        
        with t_cols:
            t_col1, t_col2, t_col3 = st.columns([1, 1, 1], gap="small")
            with t_col1:
                # Format labels as "Name (Symbol)"
                def format_asset_label(name_ko):
                    code = asset_map.get(name_ko, name_ko)
                    return f"{name_ko} ({code})"
                
                selected_ko = st.selectbox(
                    "종목 선택", 
                    options=asset_ko_names, 
                    format_func=format_asset_label
                )
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
            with t_btn:
                # Vertical alignment fix
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True) 
                # Equal width columns for buttons
                tc3, tc4 = st.columns([1, 1], gap="small")
                with tc3:
                    if st.button("🔄 기간 초기화", use_container_width=True):
                        st.session_state.start_date = pd.to_datetime(cfg.system.data_range.start).date()
                        st.session_state.end_date = pd.to_datetime(cfg.system.data_range.end).date()
                        st.session_state.highlighted_events = {} # Clear flags on full reset
                        st.query_params["start_date"] = str(st.session_state.start_date)
                        st.query_params["end_date"] = str(st.session_state.end_date)
                        st.rerun()
                with tc4:
                    has_flags = len(st.session_state.get("highlighted_events", {})) > 0
                    if st.button("🚫 모든 플래그 제거", key="global_clear_flag", help="차트의 모든 강조 표시를 지웁니다", disabled=not has_flags, use_container_width=True):
                        st.session_state.highlighted_events = {}
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
            
            diff = end_p - start_p
            m_col1.metric("수익률", f"{ret:+.2f}%", f"${diff:+,.2f}")
            m_col2.metric("시작 가격", f"${start_p:,.2f}")
            m_col3.metric("종료 가격", f"${end_p:,.2f}")
            m_col4.metric("변동성 (연율)", f"{vol:.2f}%")

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
            
            # --- Multi-Event Flagging (v-lines) ---
            highlighted = st.session_state.get("highlighted_events", {})
            for ev_id, info in highlighted.items():
                h_date = info.get("date")
                h_title = info.get("title")
                
                fig.add_vline(
                    x=h_date, 
                    line_width=2, 
                    line_dash="dash", 
                    line_color="#00C7BE",
                    layer="above"
                )
                fig.add_annotation(
                    x=h_date,
                    y=1,
                    yref="paper",
                    text=f"🚩 {h_title[:20]}..." if len(h_title) > 20 else f"🚩 {h_title}",
                    showarrow=False,
                    font=dict(color="#00C7BE", size=11),
                    bgcolor="rgba(0,0,0,0.7)",
                    bordercolor="#00C7BE",
                    borderwidth=1,
                    borderpad=4,
                    yshift=10,
                    xanchor="left" if pd.to_datetime(h_date).month < 6 else "right"
                )
                

            st.plotly_chart(fig, on_select="rerun", selection_mode="box", key="main_chart", use_container_width=True)

# --- Side Panel Content (Right Column - Starts from top) ---
with col_main_right:
    tab_ev, tab_chat, tab_multi = st.tabs(["📅 Timeline", "🤖 AI Analyst", "⚔️ AI Debate"])
    
    with tab_ev:
        @st.cache_data(ttl=3600)
        def get_cached_events(asset_name, start_date, end_date, keyword, page, sort_by="date", sort_order="desc", is_up_filter=None):
            limit = 100
            offset = page * limit
            return news_repo.search_events(
                start_date, 
                end_date, 
                asset_symbol=asset_name,
                keyword=keyword,
                limit=limit,
                offset=offset,
                sort_by=sort_by,
                sort_order=sort_order,
                is_up_filter=is_up_filter
            )

        @st.fragment
        def render_timeline(asset_name, start_date, end_date):
            # 1. Search, Sort & Refresh Controls
            sc1, sc2 = st.columns([1.5, 1])
            
            with sc1:
                search_query = st.text_input(
                    "Search Events", 
                    value=st.session_state.get("timeline_search", ""),
                    placeholder="Keywords...",
                    label_visibility="collapsed"
                )
            
            with sc2:
                # 1. Sort Options
                sort_options = {
                    "최신순": ("date", "desc"),
                    "과거순": ("date", "asc"),
                    "변동성 높은순": ("volatility", "desc"),
                }
                current_sort = (st.session_state.get("timeline_sort_by", "date"), st.session_state.get("timeline_sort_order", "desc"))
                default_idx = 0
                for i, (label, val) in enumerate(sort_options.items()):
                    if val == current_sort:
                        default_idx = i
                        break
                
                # 2. Impact Options
                impact_options = {"전체": None, "상승 요인": 1, "하락 요인": 0}
                current_impact = st.session_state.get("timeline_impact", None)
                default_impact_idx = list(impact_options.values()).index(current_impact) if current_impact in impact_options.values() else 0

                c1, c2 = st.columns([1, 1], gap="small")
                with c1:
                    selected_label = st.selectbox(
                        "Sort", options=list(sort_options.keys()), index=default_idx, label_visibility="collapsed"
                    )
                with c2:
                    selected_impact = st.selectbox(
                        "Impact", options=list(impact_options.keys()), index=default_impact_idx, label_visibility="collapsed"
                    )
                
                sort_by, sort_order = sort_options[selected_label]
                is_up_filter = impact_options[selected_impact]
            # with sc3:
            #     if st.button("🔄", key="ref_ev", help="Refresh Data", use_container_width=True):
            #         get_cached_events.clear()
            #         st.rerun()
            
            # Update state and reset page if search, sort, or impact changes
            if (search_query != st.session_state.get("timeline_search") or 
                sort_by != st.session_state.get("timeline_sort_by") or 
                sort_order != st.session_state.get("timeline_sort_order") or
                is_up_filter != st.session_state.get("timeline_impact")):
                st.session_state.timeline_search = search_query
                st.session_state.timeline_sort_by = sort_by
                st.session_state.timeline_sort_order = sort_order
                st.session_state.timeline_impact = is_up_filter
                st.session_state.timeline_page = 0
                st.rerun()

            # 2. Fetch Data
            sort_by = st.session_state.get("timeline_sort_by", "date")
            sort_order = st.session_state.get("timeline_sort_order", "desc")
            is_up_filter = st.session_state.get("timeline_impact", None)
            
            page = st.session_state.get("timeline_page", 0)
            display_events = get_cached_events(
                asset_name, 
                start_date, 
                end_date, 
                search_query,
                page,
                sort_by=sort_by,
                sort_order=sort_order,
                is_up_filter=is_up_filter
            )
            total_count = news_repo.count_events(
                start_date, 
                end_date, 
                asset_symbol=asset_name,
                keyword=st.session_state.timeline_search,
                is_up_filter=is_up_filter
            )
            
            # 3. Pagination & Status Header
            start_idx = page * 100 + 1
            end_idx = min((page + 1) * 100, total_count)
            st.caption(f"📊 {start_idx}-{end_idx} of {total_count} events found")
            
            # 4. Scrollable Container
            with st.container(height=750):
                if not display_events:
                    st.info("No events found matching your criteria.")
                else:
                    for ev in display_events:
                        with st.container(border=True):
                            d = ev.get('start_date') or ev.get('date', 'Unknown')
                            t = ev.get('title', 'No Title')
                            desc = ev.get('description', '')
                            summ = ev.get('summarize', '')
                            is_up = ev.get('is_up')
                            
                            # Header: Date & Impact Icon
                            impact_icon = "🟢" if is_up == 1 else "🔴" if is_up == 0 else "⚪"
                            st.markdown(f"<small style='color:#888;'>{impact_icon} &nbsp; {d}</small>", unsafe_allow_html=True)
                            st.markdown(f"#### {t}")
                            
                            if desc: 
                                st.markdown(f"<div style='margin-bottom:0.5rem; font-size:0.95rem;'>{desc}</div>", unsafe_allow_html=True)
                            
                            if summ:
                                with st.expander("📝 AI 인사이트", expanded=False):
                                    st.markdown(f"{summ}")
                            
                            articles = ev.get('articles', [])
                            if articles:
                                for art in articles[:2]:
                                    title = art.get('title', 'Untitled')
                                    url = art.get('url', '')
                                    if url: st.markdown(f"<small style='color:#007AFF'>[- {title}]({url})</small>", unsafe_allow_html=True)
                                    else: st.markdown(f"<small style='color:#666'>- {title}</small>", unsafe_allow_html=True)
                            
                            # Footer: Explicit Flag Toggle Button
                            st.write("") # Spacer
                            ev_id = ev.get('id')
                            is_highlighted = ev_id in st.session_state.get("highlighted_events", {})
                            
                            if is_highlighted:
                                if st.button("📍 그래프에서 제거하기", key=f"rm_{ev_id}", use_container_width=True, type="secondary"):
                                    del st.session_state.highlighted_events[ev_id]
                                    st.rerun()
                            else:
                                if st.button("📍 그래프에 배치하기", key=f"add_{ev_id}", use_container_width=True, type="primary"):
                                    st.session_state.highlighted_events[ev_id] = {"date": d, "title": t}
                                    st.rerun()
            
            # 5. Pagination Buttons
            p_col1, p_col2, p_col3 = st.columns([1, 2, 1])
            with p_col1:
                if st.button("⬅️ Previous", disabled=(page == 0), use_container_width=True):
                    st.session_state.timeline_page -= 1
                    st.rerun()
            with p_col2:
                st.write(f"<p style='text-align:center; margin-top:0.5rem;'>Page {page + 1}</p>", unsafe_allow_html=True)
            with p_col3:
                has_next = (page + 1) * 100 < total_count
                if st.button("Next ➡️", disabled=not has_next, use_container_width=True):
                    st.session_state.timeline_page += 1
                    st.rerun()
        
        render_timeline(asset_name, st.session_state.start_date, st.session_state.end_date)

    with tab_chat:
        chat_interface(asset_name, st.session_state.start_date, st.session_state.end_date)
        
    with tab_multi:
        multi_agent_interface(asset_name, st.session_state.start_date, st.session_state.end_date)