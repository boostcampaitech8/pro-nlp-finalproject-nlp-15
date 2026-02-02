import pandas as pd
import os
import json

def get_market_statistical_summary(df, asset_name):
    """방법 A: 통계적 요약 (토큰 효율적, 거시적 분석)"""
    if df.empty: return "No price data available."
    start_p, end_p = df.iloc[0]['close'], df.iloc[-1]['close']
    high_row = df.loc[df['close'].idxmax()]
    low_row = df.loc[df['close'].idxmin()]
    total_return = ((end_p - start_p) / start_p) * 100
    vol = df['close'].pct_change().std() * (252**0.5) * 100 

    return f"""
## Reference Data Market Statistics {asset_name.upper()}

### Period
{df['time'].min().date()} ~ {df['time'].max().date()}

### Return
{total_return:.2f}% (Price {start_p:,.2f} -> {end_p:,.2f})

### Extremes
High {high_row['close']:,.2f} on {high_row['time'].date()}
Low {low_row['close']:,.2f} on {low_row['time'].date()}

### Volatility Annualized
{vol:.2f}%
"""

def get_raw_markdown_table(df):
    """방법 B: Raw 마크다운 테이블 (상세 분석, 높은 정보 밀도)"""
    if df.empty: return "No price data available."
    display_df = df[['time', 'open', 'high', 'low', 'close']].copy()
    display_df['time'] = display_df['time'].dt.date
    return "### Raw Price Data Table\n" + display_df.to_markdown(index=False)

def get_causality_aware_events(events, df, cfg, max_count=20):
    """변동성 기반 사건 매핑 (Top N + 2% 임계값 태깅)"""
    threshold = cfg.limits.volatility_threshold
    df = df.copy()
    df['returns'] = df['close'].pct_change()
    df['abs_ret'] = df['returns'].abs()
    
    # 변동성 큰 순서로 추출 후 시간순 재정렬
    top_moves = df.dropna().sort_values('abs_ret', ascending=False).head(max_count)
    top_moves = top_moves.sort_values('time')
    
    context = f"## Reference Data Event Timeline ({len(top_moves)} significant days)\n\n"
    
    for _, row in top_moves.iterrows():
        date_str = row['time'].strftime('%Y-%m-%d')
        move = row['returns'] * 100
        tag = "SIGNIFICANT" if row['abs_ret'] >= threshold else "NORMAL"
        day_events = [e for e in events if e['start_date'] == date_str]
        
        context += f"### {date_str} {tag}\n"
        context += f"Change {move:.2f}%\n"
        
        if day_events:
            for ev in day_events:
                # 불렛, 볼드 제거. 단순 줄바꿈이나 들여쓰기 없음.
                context += f"Event {ev['title']} | {ev['description'][:150]}\n"
        else:
            context += f"No major news matched this price move.\n"
        context += "\n"
    return context

# 기존 파일 리스트 및 데이터 필터링 함수는 그대로 유지
def get_all_csv_files(directory):
    import glob
    return [os.path.basename(x) for x in glob.glob(f"{directory}/*.csv")]

def get_all_event_files(directory):
    import glob
    return [os.path.basename(x) for x in glob.glob(f"{directory}/*.jsonl")]

def load_and_filter_data(file_path, start_date, end_date):
    df = pd.read_csv(file_path)
    df['time'] = pd.to_datetime(df['time'])
    mask = (df['time'].dt.date >= start_date) & (df['time'].dt.date <= end_date)
    return df.loc[mask].sort_values('time')

def load_events_by_period(directory, start_date, end_date, keywords=None, target_files=None):
    from pathlib import Path
    events = []
    start_str, end_str = str(start_date), str(end_date)
    for f_path in Path(directory).glob("*.jsonl"):
        # 1. 사용자가 직접 파일을 선택한 경우
        if target_files is not None:
            if f_path.name not in target_files: continue
        
        # 2. 키워드 매칭 (target_files가 없을 때만)
        elif keywords:
            # 키워드 매칭 로직 완화: 파일명이나 키워드를 '_'로 분리하여 하나라도 겹치면 통과
            f_tokens = set(f_path.name.replace(".jsonl", "").split('_'))
            # 입력된 keywords가 리스트라고 가정 (예: ['copper_future'])
            k_tokens = set()
            for k in keywords:
                k_tokens.update(k.split('_'))
            
            if not f_tokens.intersection(k_tokens): continue
        with open(f_path, "r", encoding="utf-8") as f:
            for line in f:
                ev = json.loads(line)
                if start_str <= ev.get('start_date', '') <= end_str: events.append(ev)
    return sorted(events, key=lambda x: x.get('start_date', ''))