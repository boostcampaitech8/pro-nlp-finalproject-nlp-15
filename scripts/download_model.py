import os
from huggingface_hub import snapshot_download

def download_exaone():
    # 저장할 경로 설정
    repo_id = "LGAI-EXAONE/EXAONE-3.0-7.8B-Instruct"
    local_dir = "./models/EXAONE-3.0-7.8B-Instruct"
    
    print(f"🚀 {repo_id} 모델 다운로드를 시작합니다...")

    snapshot_download(
        repo_id=repo_id,
        local_dir=local_dir,
        local_dir_use_symlinks=False, 
        revision="main"
    )
    
    print(f"✅ 다운로드 완료! 경로: {os.path.abspath(local_dir)}")

if __name__ == "__main__":
    download_exaone()