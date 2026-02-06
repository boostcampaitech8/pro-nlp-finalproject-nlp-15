import asyncio
import hydra
from omegaconf import DictConfig
from core.reasoning import ReasoningEngine

@hydra.main(version_base=None, config_path="config", config_name="config")
def main(cfg: DictConfig):
    asyncio.run(run_pipeline(cfg))

async def run_pipeline(cfg: DictConfig):
    print("\n" + "="*50 + "\n📈 AI 금융 분석 파이프라인 가동 (v2.1)\n" + "="*50)
    
    target = input("👉 종목(은/구리 등): ").strip()
    start = input("📅 시작일(YYYY-MM-DD): ").strip()
    end = input("📅 종료일(YYYY-MM-DD): ").strip()

    if not all([target, start, end]):
        print("❌ 입력을 확인해주세요."); return

    engine = ReasoningEngine(cfg)
    
    print(f"\n🚀 {target} 시장 분석 및 토론을 시작합니다...")
    report = await engine.run_full_analysis(target, start, end)
    
    print(f"\n⚖️ [최종 투자 리포트]\n{report}")
    print("\n" + "="*50 + "\n✅ 분석 완료\n" + "="*50)

if __name__ == "__main__":
    main()