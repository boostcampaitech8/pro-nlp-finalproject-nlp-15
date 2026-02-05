"""
로컬 EXAONE 모델 다운로드 스크립트.
기본 실행 방식은 config/llm/local.yaml에 설정한 API를 사용합니다.
로컬에서 모델을 직접 돌리고 싶을 때만 이 스크립트로 다운로드 후
별도 서빙 설정이 필요합니다.
"""
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