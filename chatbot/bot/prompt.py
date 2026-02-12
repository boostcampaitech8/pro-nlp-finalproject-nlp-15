from langfuse import Langfuse

class PromptManager:
    def __init__(self, cfg):
        self.langfuse = Langfuse()
        self.cfg = cfg
    
    def get_system_prompt(self):
        try:
            prompt_name = self.cfg.prompts.system_prompt
            return self.langfuse.get_prompt(prompt_name)
        except Exception as e:
            # Fallback to local file
            import os
            local_path = os.path.join(os.path.dirname(__file__), "../../../prompts/system_prompt.md")
            if os.path.exists(local_path):
                with open(local_path, "r") as f:
                    return f.read()
            return "You are a helpful financial assistant. Please answer based on the tools provided."