import os
import subprocess
from pathlib import Path

# --- 설정 ---
NUM_WORKERS = 5
# 현재 파일 위치: .../project/scripts/distribute_jobs.py
CURRENT_DIR = Path(__file__).resolve().parent
# 프로젝트 루트: .../project/
PROJECT_ROOT = CURRENT_DIR.parent 

# 데이터 경로 및 로그 경로
INPUT_DIR = PROJECT_ROOT / "data" / "by_keyword"
LOG_DIR = PROJECT_ROOT / "logs"
MODULE_PATH = "workflow.run_extract"
# ------------

def get_line_count(file_path):
    try:
        # wc 명령어가 없거나 에러 날 경우 대비
        if not file_path.exists(): return 0
        result = subprocess.run(['wc', '-l', str(file_path)], capture_output=True, text=True)
        return int(result.stdout.split()[0])
    except:
        return 0

def run_distribute():
    # 0. 사전 체크
    if not INPUT_DIR.exists():
        print(f"❌ 에러: 데이터 폴더를 찾을 수 없습니다.\n경로: {INPUT_DIR}")
        return
    
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 파일 목록 확인
    all_files = sorted([p for p in INPUT_DIR.glob("*.csv") if p.is_file() and p.name != "_manifest.csv"])
    if not all_files:
        print("❌ 처리할 CSV 파일이 없습니다.")
        return

    # 2. 라인 수 측정 및 정렬
    print(f"📂 프로젝트 루트: {PROJECT_ROOT}")
    print("데이터 분석 중...")
    
    file_info = []
    for f in all_files:
        count = get_line_count(f)
        file_info.append({'name': f.name, 'count': count})
    file_info.sort(key=lambda x: x['count'], reverse=True)

    # 3. 배정 (Greedy)
    worker_groups = [[] for _ in range(NUM_WORKERS)]
    worker_loads = [0] * NUM_WORKERS

    for info in file_info:
        min_load_idx = worker_loads.index(min(worker_loads))
        worker_groups[min_load_idx].append(info['name'])
        worker_loads[min_load_idx] += info['count']

    # 4. 실행
    print("\n" + "="*50)
    for i, chunk in enumerate(worker_groups):
        if not chunk: continue
        
        file_list_str = "[" + ",".join(chunk) + "]"
        log_path = LOG_DIR / f"worker_{i}.log"
        
        # [수정됨] 경로 앞뒤에 작은따옴표(')를 추가하여 공백이 있어도 인식되게 함
        command = [
            f"cd '{PROJECT_ROOT}'",   # <-- 여기에 따옴표 추가
            "&&",                 
            "nohup", "uv", "run", "-m", MODULE_PATH,
            f"extraction.files={file_list_str}",
            ">", f"'{log_path}'",     # <-- 여기에도 따옴표 추가
            "2>&1", "&"
        ]
        
        full_command = " ".join(command)
        
        print(f"🚀 Worker {i} 실행 명령:")
        print(f"   {full_command}") 
        
        os.system(full_command)

    print("="*50)
    print("✅ 실행 완료. 만약 로그가 여전히 안 생기면,")
    print("   위의 '실행 명령' 중 하나를 복사해서 터미널에 직접 붙여넣어 보세요.")

if __name__ == "__main__":
    run_distribute()