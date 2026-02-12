import os
import sys
import yaml
import asyncio
import argparse
from datetime import datetime
from pathlib import Path
from hydra import initialize, compose
from hydra.core.global_hydra import GlobalHydra
from dotenv import load_dotenv

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from chatbot.bot.agent import FinancialAgent

load_dotenv()

def load_config():
    if GlobalHydra.instance().is_initialized():
        GlobalHydra.instance().clear()
    with initialize(version_base=None, config_path="../config"):
        return compose(config_name="chatbot")

def load_prompt(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def load_scenarios(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        return data.get("scenarios", [])

async def run_experiment(prompt_path: str, scenarios_path: str, tag: str = "experiments"):
    cfg = load_config()
    agent = FinancialAgent(cfg)
    
    system_prompt = load_prompt(prompt_path)
    scenarios = load_scenarios(scenarios_path)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(__file__).parent.parent / "outputs" / "experiments" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    
    summary_file = output_dir / "00_summary_report.md"
    
    print(f"🚀 Starting Prompt Experiment: {timestamp}")
    print(f"📂 Prompt: {prompt_path}")
    print(f"📊 Scenarios: {len(scenarios)}")
    print(f"🏷️ Tag: {tag}")
    print("-" * 50)
    
    with open(summary_file, "w", encoding="utf-8") as sf:
        sf.write(f"# Experiment Summary Report: {timestamp}\n\n")
        sf.write(f"- **Prompt Path**: `{prompt_path}`\n")
        sf.write(f"- **Scenarios**: `{scenarios_path}`\n\n")
        sf.write("## Scenario Index\n\n")
        
        for i, sc in enumerate(scenarios, 1):
            name = sc["name"]
            sf.write(f"{i}. [{name}](#{name.lower().replace(' ', '-')})\n")
        
        sf.write("\n---\n\n")
        
        for i, sc in enumerate(scenarios, 1):
            name = sc["name"]
            asset = sc["asset"]
            query = sc["query"]
            start = sc["start_date"]
            end = sc["end_date"]
            
            print(f"[{i}/{len(scenarios)}] Running: {name}...")
            
            sf.write(f"## {name}\n\n")
            sf.write(f"- **Asset**: {asset}\n")
            sf.write(f"- **Range**: {start} ~ {end}\n")
            sf.write(f"- **Query**: {query}\n\n")
            sf.write("### Response\n\n")
            
            # Individual result file
            output_file = output_dir / f"{i:02d}_{name.replace(' ', '_')}.md"
            
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(f"# Scenario: {name}\n\n{query}\n\n---\n\n")
                
                full_response = ""
                has_yielded_final = False
                try:
                    # analyze_stream_agentic returns a generator
                    for chunk in agent.analyze_stream_agentic(
                        asset_name=asset,
                        user_query=query,
                        start_date=start,
                        end_date=end,
                        chat_history=[],
                        system_prompt_override=system_prompt,
                        tags=[tag] # Pass the experiment tag
                    ):
                        if isinstance(chunk, dict) and chunk.get("type") in ["tool_result", "tool_error"]:
                            tool_name = chunk["tool"]
                            tool_input = chunk["input"]
                            tool_output = chunk["output"]
                            
                            is_error = chunk.get("type") == "tool_error"
                            status_icon = "❌" if is_error else "🛠️"
                            
                            log_entry = f"\n\n---\n\n### {status_icon} Tool Call: `{tool_name}`\n"
                            log_entry += f"**Input**: `{tool_input}`\n\n"
                            log_entry += f"**Output**:\n{tool_output}\n\n---\n\n"
                            
                            f.write(log_entry)
                            sf.write(log_entry)
                            f.flush()
                            sf.flush()

                        elif hasattr(chunk, "content") and chunk.content:
                            if not has_yielded_final:
                                header = "\n\n### 📝 Final Agent Response\n\n"
                                f.write(header)
                                sf.write(header)
                                has_yielded_final = True
                            
                            content = str(chunk.content)
                            full_response += content
                            f.write(content)
                            sf.write(content)
                            f.flush()
                            sf.flush()
                    
                    print(f"✅ Completed: {name}")
                except Exception as e:
                    print(f"❌ Error in {name}: {str(e)}")
                    f.write(f"\n\nERROR: {str(e)}")
                    sf.write(f"\n\n> [!ERROR]\n> {str(e)}")
            
            sf.write("\n\n---\n\n")
            print("-" * 30)

    print(f"\n✨ Experiment Finished!")
    print(f"📄 Summary: {summary_file}")
    print(f"📂 All files: {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run prompt experiments.")
    parser.add_argument("--prompt", type=str, default="prompts/system_prompt.md", help="Path to system prompt MD file")
    parser.add_argument("--scenarios", type=str, default="experiments/test_scenarios.yaml", help="Path to scenarios YAML file")
    parser.add_argument("--tag", type=str, default="experiments", help="Langfuse tag for this experiment")
    
    args = parser.parse_args()
        
    asyncio.run(run_experiment(args.prompt, args.scenarios, args.tag))
