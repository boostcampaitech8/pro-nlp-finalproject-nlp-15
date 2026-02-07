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

# --- Dependencies ---
stock_api = init_stock_api()
news_repo = init_news_repo()


# --- Initial State & Date Handling ---
# 1. Initialize Asset & Date Range from Query Params or Defaults
if "init_done" not in st.session_state:
    st.session_state.start_date = None
    st.session_state.end_date = None
    st.session_state.init_done = True

# 2. Support Chart Selection (Box/Drag) at the very top
def handle_chart_selection():
    if "main_chart" in st.session_state and st.session_state.main_chart:
        selected = st.session_state.main_chart
        if "selection" in selected and "box" in selected["selection"]:
            box = selected["selection"]["box"]
            if box and "x" in box[0]:
                x_range = box[0]["x"]
                try:
                    new_start = pd.to_datetime(x_range[0]).date()
                    new_end = pd.to_datetime(x_range[1]).date()
                    
                    # Check if selection is actually new to avoid infinite rerun
                    curr_start = st.query_params.get("start_date")
                    curr_end = st.query_params.get("end_date")
                    
                    if str(new_start) != curr_start or str(new_end) != curr_end:
                        st.query_params["start_date"] = str(new_start)
                        st.query_params["end_date"] = str(new_end)
                        st.session_state.start_date = new_start
                        st.session_state.end_date = new_end
                        st.toast(f"🏆 Period Selected: {new_start} ~ {new_end}")
                        st.rerun()
                except Exception: pass

handle_chart_selection()

# --- Sidebar ---
with st.sidebar:
    st.title("🛡️ Analysis Settings")
    
    # Asset Selection
    asset_map = stock_api.list_assets()
    asset_ko_names = list(asset_map.keys())
    selected_ko = st.selectbox("종목 선택", asset_ko_names)
    asset_name = asset_map.get(selected_ko, "Unknown")

    # Data Load (for UI Chart)
    df = stock_api.get_prices(asset_name)
    
    if not df.empty:
        # Load dates from Query Params (Source of Truth)
        q_start = st.query_params.get("start_date")
        q_end = st.query_params.get("end_date")
        
        if q_start and q_end:
            st.session_state.start_date = pd.to_datetime(q_start).date()
            st.session_state.end_date = pd.to_datetime(q_end).date()
        else:
            # First time load or clear case - Range from Config (Defaulting to 2017-11 to 2026-01-31)
            st.session_state.start_date = pd.to_datetime(cfg.system.data_range.start).date()
            st.session_state.end_date = pd.to_datetime(cfg.system.data_range.end).date()
            st.query_params["start_date"] = str(st.session_state.start_date)
            st.query_params["end_date"] = str(st.session_state.end_date)

        # --- Date Selection ---
        st.divider()
        st.subheader("📅 Date Range")
        
        # Dynamic keys based on current date values - forces widget recreation on date change
        new_start = st.date_input(
            "Start Date", 
            key=f"sdt_{st.session_state.start_date}",
            value=st.session_state.start_date
        )
        new_end = st.date_input(
            "End Date", 
            key=f"edt_{st.session_state.end_date}",
            value=st.session_state.end_date
        )
        
        # Update state and query params if user manually changes dates
        if new_start != st.session_state.start_date:
            st.session_state.start_date = new_start
            st.query_params["start_date"] = str(new_start)
            st.rerun()
        if new_end != st.session_state.end_date:
            st.session_state.end_date = new_end
            st.query_params["end_date"] = str(new_end)
            st.rerun()
        
        # Reset Button
        if st.button("🔄 Reset Range"):
             st.session_state.start_date = pd.to_datetime(cfg.system.data_range.start).date()
             st.session_state.end_date = pd.to_datetime(cfg.system.data_range.end).date()
             st.query_params["start_date"] = str(st.session_state.start_date)
             st.query_params["end_date"] = str(st.session_state.end_date)
             st.rerun()

    # Event/News filtering is now handled by the RDB many-to-many relationship
    # No need for manual file selection
    

# --- Main Page ---
if df.empty:
    st.error("No data found for selected asset.")
else:
    st.subheader(f"📊 Market Analysis: {selected_ko} ({asset_name})")
    
    col_chart, col_side = st.columns([2, 1])
    
    with col_chart:
        # Filter data based on global state
        visible_mask = (df['time'].dt.date >= st.session_state.start_date) & (df['time'].dt.date <= st.session_state.end_date)
        v_data = df.loc[visible_mask]
        
        if v_data.empty: 
            st.warning("No data in selected range.")
        else:
            # --- Metrics Display ---
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            start_p = v_data.iloc[0]['close']
            end_p = v_data.iloc[-1]['close']
            ret = ((end_p - start_p) / start_p) * 100
            vol = v_data['close'].pct_change().std() * (252**0.5) * 100
            
            m_col1.metric("Period Return", f"{ret:.2f}%", f"{end_p - start_p:.2f}")
            m_col2.metric("Volatility (Ann.)", f"{vol:.2f}%")
            m_col3.metric("Start Date", f"{st.session_state.start_date}")
            m_col4.metric("End Date", f"{st.session_state.end_date}")

            # --- Chart (NOT nested in fragment to allow global date sync) ---
            fig = go.Figure(go.Scatter(x=v_data['time'], y=v_data['close'], mode='lines', line=dict(color='#007AFF', width=2)))
            
            fig.update_layout(
                height=550,
                template="plotly_dark",
                dragmode="select",  # Reverted to select to support 'Drag to Zoom' behavior
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis=dict(rangeslider=dict(visible=False), showgrid=False),
                yaxis=dict(autorange=True, showgrid=True, gridcolor="#333"),
                hovermode="x unified"
            )
            
            st.plotly_chart(
                fig, 
                on_select="rerun", 
                selection_mode="box", 
                key="main_chart", 
                width="stretch"
            )

    # --- Side Panel (Timeline & Chat) ---
    with col_side:
        tab_ev, tab_chat = st.tabs(["📅 Timeline", "🤖 AI Analyst"])
        
        # Tab 1: Timeline
        with tab_ev:
            @st.cache_data(ttl=3600)
            def get_cached_events(asset_name, start_date, end_date):
                return news_repo.search_events(
                    start_date, 
                    end_date,
                    asset_symbol=asset_name
                )

            @st.fragment
            def render_timeline(asset_name, start_date, end_date):
                # Load events using the app-level cache
                display_events = get_cached_events(asset_name, start_date, end_date)
                
                # Header with refresh button
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.caption(f"📊 Found {len(display_events)} events")
                    st.caption(f"📅 {start_date} ~ {end_date}")
                with col2:
                    if st.button("🔄 Refresh", key="refresh_events", width="stretch"):
                        get_cached_events.clear()
                        st.rerun()
                
                # Scrollable Container for Events
                with st.container(height=700):
                    for ev in display_events:
                        with st.container(border=True):
                            d = ev.get('start_date') or ev.get('date', 'Unknown')
                            t = ev.get('title', 'No Title')
                            desc = ev.get('description', '')
                            
                            # Header: Date & Title
                            st.markdown(f"**{d}** | **{t}**")
                            
                            # Body: Description
                            if desc:
                                st.markdown(f"{desc}")
                            
                            # Articles: Show linked article titles
                            articles = ev.get('articles', [])
                            if articles:
                                st.caption(f"📰 Related Articles ({len(articles)}):")
                                for art in articles[:3]:  # Limit to 3 for UI cleanliness
                                    art_title = art.get('title', 'Untitled')
                                    art_url = art.get('url', '')
                                    if art_url:
                                        st.markdown(f"- [{art_title}]({art_url})")
                                    else:
                                        st.markdown(f"- {art_title}")
            
            render_timeline(asset_name, st.session_state.start_date, st.session_state.end_date)

        
        # Tab 2: Chat
        with tab_chat:
            chat_interface(asset_name, st.session_state.start_date, st.session_state.end_date)