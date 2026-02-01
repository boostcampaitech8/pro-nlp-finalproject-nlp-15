import streamlit as st
import pandas as pd
import json
from pathlib import Path

# --- 페이지 설정 ---
st.set_page_config(page_title="WEE Timeline Viewer", layout="wide")
st.title("Timeline Event Explorer")

# --- 사이드바 설정 ---
st.sidebar.header("📁 Path Settings")
result_dir = st.sidebar.text_input("Result Directory", "outputs/events/v6_3d/result")
data_dir = st.sidebar.text_input("Raw Data Directory", "data/by_keyword")
sort_order = st.sidebar.radio("Sort Order", ["Descending (Newest first)", "Ascending (Oldest first)"])

res_path = Path(result_dir)
data_path = Path(data_dir)

if res_path.exists() and data_path.exists():
    # 1. 사용 가능한 파일 목록 확보
    jsonl_files = sorted(list(res_path.glob("*.jsonl")))
    csv_files = list(data_path.glob("*.csv"))

    if not jsonl_files:
        st.error(f"No JSONL files found in {result_dir}")
        st.stop()

    # --- 사이드바: 이벤트 파일 선택 섹션 ---
    st.sidebar.divider()
    st.sidebar.header("🎯 Select Event Files")
    
    # 전체 선택 / 해제 로직
    if "select_all" not in st.session_state:
        st.session_state.select_all = True

    def toggle_select_all():
        st.session_state.select_all = st.session_state._select_all

    st.sidebar.checkbox("Select All Files", value=st.session_state.select_all, 
                       key="_select_all", on_change=toggle_select_all)

    file_options = [f.name for f in jsonl_files]
    default_selection = file_options if st.session_state.select_all else []
    
    selected_filenames = st.sidebar.multiselect(
        "Choose files to display", 
        file_options, 
        default=default_selection
    )

    # 페이지네이션 설정
    items_per_page = st.sidebar.number_input("Items per page", min_value=5, max_value=100, value=10)

    # --- 데이터 로드 함수 ---
    @st.cache_data
    def load_selected_data(selected_files, all_jsonl_paths, csv_list):
        # 1. 모든 CSV 로드
        raw_dfs = []
        for f in csv_list:
            try: raw_dfs.append(pd.read_csv(f))
            except: continue
        df_raw = pd.concat(raw_dfs).drop_duplicates(subset=['id']) if raw_dfs else pd.DataFrame(columns=['id'])
        df_raw['id'] = df_raw['id'].astype(str)
        
        # 2. 선택된 이벤트 파일만 로드
        events = []
        target_paths = [p for p in all_jsonl_paths if p.name in selected_files]
        
        for f_path in target_paths:
            with open(f_path, "r", encoding="utf-8") as f:
                for line in f:
                    event_data = json.loads(line)
                    event_data['origin_file'] = f_path.name
                    events.append(event_data)
        
        return df_raw, pd.DataFrame(events)

    if not selected_filenames:
        st.warning("Please select at least one event file from the sidebar.")
        st.stop()

    df_raw, df_events = load_selected_data(selected_filenames, jsonl_files, csv_files)

    # --- 검색 및 필터링 ---
    search_query = st.text_input("🔍 Search within selected events (Title or Description)", "")
    df_display = df_events
    if search_query:
        df_display = df_events[
            df_events['title'].str.contains(search_query, case=False, na=False) |
            df_events['description'].str.contains(search_query, case=False, na=False)
        ]

    # 정렬
    is_ascending = (sort_order == "Ascending (Oldest first)")
    if not df_display.empty:
        df_display = df_display.sort_values("start_date", ascending=is_ascending)

    # --- 페이지네이션 및 렌더링 ---
    total_items = len(df_display)
    if total_items > 0:
        total_pages = (total_items // items_per_page) + (1 if total_items % items_per_page > 0 else 0)
        st.write(f"Showing **{total_items}** events from **{len(selected_filenames)}** files")
        
        page = st.select_slider("Select page", options=range(1, total_pages + 1), value=1)
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        current_page_data = df_display.iloc[start_idx:end_idx]

        for idx, event in current_page_data.iterrows():
            with st.container(border=True):
                col_date, col_content = st.columns([1, 5])
                with col_date:
                    # --- 날짜 표시 로직 수정 ---
                    start = event.get('start_date', 'N/A')
                    end = event.get('end_date')
                    
                    # 종료일이 시작일과 다르거나 존재할 때만 기간으로 표시
                    if end and end != start:
                        st.subheader(f"📅 {start}")
                        st.write(f"~ {end}")
                    else:
                        st.subheader(f"📅 {start}")
                    
                    st.caption(f"ID: {event['event_id']}")
                    st.caption(f"📁 {event['origin_file']}")
                
                with col_content:
                    st.markdown(f"### {event['title']}")
                    st.write(event['description'])
                    
                    source_ids = [str(s) for s in event['source']]
                    matched_articles = df_raw[df_raw['id'].isin(source_ids)]
                    
                    with st.expander(f"🔍 Evidence Articles ({len(matched_articles)})"):
                        for i, (_, article) in enumerate(matched_articles.iterrows()):
                            if i > 0: st.markdown("---")
                            st.markdown(f"**{article.get('publish_date', 'N/A')}** | `ID: {article['id']}`")
                            target_url = article.get('doc_url') or article.get('url')
                            if target_url:
                                st.markdown(f"**[{article['title']}]({target_url})**")
                            else:
                                st.markdown(f"**{article['title']}**")
                            st.write(article.get('description', 'No description.'))
        st.write(f"Page {page} of {total_pages}")
    else:
        st.warning("No events found matching the criteria.")
else:
    st.error("Check directory paths in the sidebar.")