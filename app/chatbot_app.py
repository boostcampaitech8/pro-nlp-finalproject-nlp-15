import streamlit as st
import pandas as pd
import os, sys
from dotenv import load_dotenv

load_dotenv()

import plotly.graph_objects as go
import plotly.graph_objects as go
from hydra import initialize, compose
from hydra.core.global_hydra import GlobalHydra
from langchain_community.chat_message_histories import StreamlitChatMessageHistory

# --- New Module Imports ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chatbot.bot.agent import FinancialAgent
from db.stock_api import StockAPI
from db.news_repo import NewsRepository

# --- Hydra Init ---
if "cfg" not in st.session_state:
    if GlobalHydra.instance().is_initialized(): GlobalHydra.instance().clear()
    with initialize(version_base=None, config_path="../config"):
        st.session_state.cfg = compose(config_name="chatbot")

cfg = st.session_state.cfg

st.set_page_config(page_title="AI Financial Intelligence", layout="wide")

# --- Dependencies for UI (Chart) ---
# StockAPI is used here only for UI/Chart rendering. 
# The Agent has its own instance for context generation.
stock_api = StockAPI(cfg.data.dir_path)
news_repo = NewsRepository(cfg.data.event_result_path)

# --- Initial State & Date Handling ---
# 1. Initialize Asset & Date Range from Query Params or Defaults
if "init_done" not in st.session_state:
    st.session_state.start_date = None
    st.session_state.end_date = None
    st.session_state.init_done = True

# 2. Support Chart Selection (Box/Drag) at the very top
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
                    st.toast(f"🏆 Range Selected: {new_start} ~ {new_end}")
                    st.rerun()
            except Exception: pass

# --- Sidebar ---
with st.sidebar:
    st.title("🛡️ Analysis Settings")
    
    # Asset Selection
    csv_files = stock_api.get_all_files()
    selected_file = st.selectbox("Select Asset", csv_files)
    asset_name = selected_file.replace("_price.csv", "") if selected_file else "Unknown"

    # Data Load (for UI Chart)
    df = stock_api.get_price_data(asset_name)
    
    if not df.empty:
        # Load dates from Query Params (Source of Truth)
        q_start = st.query_params.get("start_date")
        q_end = st.query_params.get("end_date")
        
        if q_start and q_end:
            st.session_state.start_date = pd.to_datetime(q_start).date()
            st.session_state.end_date = pd.to_datetime(q_end).date()
        else:
            # First time load or clear case
            st.session_state.start_date = df['time'].min().date()
            st.session_state.end_date = df['time'].max().date()
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
             st.session_state.start_date = df['time'].min().date()
             st.session_state.end_date = df['time'].max().date()
             st.query_params["start_date"] = str(st.session_state.start_date)
             st.query_params["end_date"] = str(st.session_state.end_date)
             st.rerun()

    # Event Selection
    st.divider()
    st.subheader("📂 Event Files")
    all_event_files = news_repo.get_all_files()
    default_matches = [f for f in all_event_files if asset_name in f]
    selected_event_files = st.multiselect("Choose Event Source", all_event_files, default=default_matches)
    
    # Agent Mode Selection
    st.divider()
    st.subheader("🤖 Agent Mode")
    use_agentic = st.toggle("🔧 Agentic Tool Calling", value=True, 
                            help="When ON: LLM decides which tools to use.\\nWhen OFF: All context is pre-injected.")
    if use_agentic:
        st.caption("✅ LLM will select tools dynamically")
    else:
        st.caption("📋 Using legacy pre-injected context")


# --- Main Page ---
if df.empty:
    st.error("No data found for selected asset.")
else:
    st.subheader(f"Market Analysis: {asset_name.upper()}")
    
    col_chart, col_side = st.columns([2, 1])
    
    with col_chart:
        # 1. Prepare Data: Filter to selected range (Crop)
        visible_mask = (df['time'].dt.date >= st.session_state.start_date) & (df['time'].dt.date <= st.session_state.end_date)
        visible_data = df.loc[visible_mask]
        
        # --- Metrics Display ---
        if not visible_data.empty:
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            start_p = visible_data.iloc[0]['close']
            end_p = visible_data.iloc[-1]['close']
            ret = ((end_p - start_p) / start_p) * 100
            vol = visible_data['close'].pct_change().std() * (252**0.5) * 100
            
            m_col1.metric("Period Return", f"{ret:.2f}%", f"{end_p - start_p:.2f}")
            m_col2.metric("Volatility (Ann.)", f"{vol:.2f}%")
            m_col3.metric("Start Date", f"{st.session_state.start_date}")
            m_col4.metric("End Date", f"{st.session_state.end_date}")

        # 2. Chart Rendering (Cropped View)
        # Use visible_data directly. 
        # X-axis will auto-range to this data.
        if not visible_data.empty:
            fig = go.Figure(go.Scatter(x=visible_data['time'], y=visible_data['close'], mode='lines', line=dict(color='#007AFF')))
            
            # Dynamic Y-axis scaling
            y_min = visible_data['close'].min()
            y_max = visible_data['close'].max()
            padding = (y_max - y_min) * 0.05 if y_max != y_min else y_max * 0.01
            y_range = [y_min - padding, y_max + padding]

            fig.update_layout(
                height=600, 
                template="plotly_dark",
                dragmode="select", # Enable box selection
                xaxis=dict(
                    rangeslider=dict(visible=False) 
                    # Removed hardcoded range to allow auto-fit to cropped data
                ),
                yaxis=dict(
                    autorange=False,
                    range=y_range
                )
            )
            
            chart_result = st.plotly_chart(
                fig, 
                on_select="rerun", 
                selection_mode="box",
                key="main_chart"
            )

    # --- Side Panel (Timeline & Chat) ---
    with col_side:
        # Load events (cached in NewsRepository.get_events)
        display_events = news_repo.get_events(
            st.session_state.start_date, 
            st.session_state.end_date, 
            target_files=selected_event_files
        )
        
        tab_ev, tab_chat = st.tabs(["📅 Timeline", "🤖 AI Analyst"])
        
        # Tab 1: Timeline
        with tab_ev:
            # Header with refresh button
            col1, col2 = st.columns([3, 1])
            with col1:
                st.caption(f"📊 Found {len(display_events)} events")
                st.caption(f"📅 {st.session_state.start_date} ~ {st.session_state.end_date}")
            with col2:
                if st.button("🔄 Refresh", key="refresh_events", use_container_width=True):
                    # Clear NewsRepository cache and force reload
                    news_repo.get_events.clear()
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

        
        # Tab 2: Chat
        with tab_chat:
            msgs = StreamlitChatMessageHistory(key="chat_messages")
            
            # History Sync
            if "last_asset_name" in st.session_state and st.session_state.last_asset_name != asset_name:
                msgs.clear()
                st.toast(f"Asset changed to {asset_name}. Chat history cleared.", icon="🧹")
            st.session_state.last_asset_name = asset_name

            # Chat UI
            chat_box = st.container(height=800)
            for msg in msgs.messages:
                chat_box.chat_message(msg.type).write(msg.content)

            if query := st.chat_input("Ask about market drivers..."):
                # Type guard: query is guaranteed to be str (not None) inside this block
                assert isinstance(query, str)
                
                with chat_box:
                    st.chat_message("user").write(query)
                
                # Agent Init
                agent = FinancialAgent(cfg)
                
                # Capture query for nested function (type checker)
                user_query: str = query
                
                with chat_box.chat_message("assistant"):
                    # Stream response - Passing Metadata including file selection
                    start_d = st.session_state.start_date
                    end_d = st.session_state.end_date
                    
                    # Generator wrapper to extract content from chunks
                    def stream_content():
                        if use_agentic:
                            # Agentic mode: LLM decides which tools to call
                            for chunk in agent.analyze_stream_agentic(
                                asset_name, 
                                user_query,  # Use captured variable
                                start_d, 
                                end_d, 
                                msgs.messages, 
                                target_files=selected_event_files
                            ):
                                # Agent guarantees string content
                                if hasattr(chunk, "content") and chunk.content:
                                    yield str(chunk.content)
                        else:
                            # Legacy mode: Pre-inject all context
                            for chunk in agent.analyze_stream(
                                asset_name, 
                                user_query,  # Use captured variable
                                start_d, 
                                end_d, 
                                msgs.messages, 
                                target_files=selected_event_files
                            ):
                                if hasattr(chunk, "content") and chunk.content:
                                    yield str(chunk.content)
                    
                    # Use st.write_stream for smooth streaming
                    response = st.write_stream(stream_content())
                    # Ensure full_ans is a string (write_stream returns str or list)
                    full_ans = str(response) if response else ""
                    
                msgs.add_user_message(query)
                msgs.add_ai_message(full_ans)