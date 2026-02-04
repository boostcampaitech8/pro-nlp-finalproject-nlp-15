from langfuse import Langfuse

class PromptManager:
    def __init__(self, cfg):
        self.langfuse = Langfuse()
        self.cfg = cfg
    
    def get_system_prompt(self):
        prompt_name = self.cfg.prompts.system_prompt
        return self.langfuse.get_prompt(prompt_name)