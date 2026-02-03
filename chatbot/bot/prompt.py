from langfuse import Langfuse

class PromptManager:
    def __init__(self, cfg):
        self.langfuse = Langfuse()
        self.cfg = cfg
    
    def get_persona_prompt(self):
        prompt_name = self.cfg.prompts.financial_analysis
        return self.langfuse.get_prompt(prompt_name)
    
    def get_context_prompt(self):
        prompt_name = self.cfg.prompts.financial_context
        return self.langfuse.get_prompt(prompt_name)