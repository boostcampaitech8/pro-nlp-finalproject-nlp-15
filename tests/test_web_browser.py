import pandas as pd
import sys
import os
import random
from pathlib import Path
from tqdm import tqdm

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chatbot.tools.web_browser import extract_url_content

def run_benchmark():
    csv_path = Path("data/articles/gold_future.csv")
    if not csv_path.exists():
        print(f"Error: {csv_path} not found.")
        return

    print(f"Loading data from {csv_path}...")
    df = pd.read_csv(csv_path)
    
    # Filter for rows with URLs
    df_with_urls = df[df['doc_url'].notna() & (df['doc_url'] != "")]
    
    if len(df_with_urls) < 100:
        sample_size = len(df_with_urls)
    else:
        sample_size = 100
        
    print(f"Randomly selecting {sample_size} articles for benchmarking...")
    sample = df_with_urls.sample(sample_size, random_state=42)
    
    success_count = 0
    results = []
    
    for _, row in tqdm(sample.iterrows(), total=sample_size):
        url = row['doc_url']
        title = row['title']
        
        # print(f"\nProcessing: {title} ({url})")
        content = extract_url_content.run(url)
        
        is_success = False
        if isinstance(content, str) and not content.startswith("Error:") and not content.startswith("HTTP Error:") and not content.startswith("Network Error:"):
            # Also check if it's just a generic "enable JS" message or similar
            if len(content) > 200: # Threshold for "meaningful" content
                success_count += 1
                is_success = True
        
        results.append({
            "title": title,
            "url": url,
            "success": is_success,
            "length": len(content) if isinstance(content, str) else 0,
            "preview": content[:100] if isinstance(content, str) else str(content)
        })

    for i, res in enumerate(results, 1):
        status = "✅ SUCCESS" if res['success'] else "❌ FAILURE"
        print(f"{i}. [{status}] {res['title']}")
        if not res['success']:
             print(f"   Reason/Preview: {res['preview']}")

    print("\n" + "="*50)
    print("BENCHMARK RESULTS")
    print("="*50)
    print(f"Total Attempted: {sample_size}")
    print(f"Successful: {success_count}")
    success_rate = (success_count / sample_size) * 100
    print(f"Success Rate: {success_rate:.1f}%")
    print("="*50)

if __name__ == "__main__":
    run_benchmark()
