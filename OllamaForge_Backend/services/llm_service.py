from langchain_ollama import OllamaLLM

class LLMService:
    def __init__(self, model, temperature=0.5):
        self.llm = OllamaLLM(model=model, temperature=temperature)

    def invoke(self, prompt):
        return self.llm.invoke(prompt)

    def stream(self, prompt):
        return self.llm.stream(prompt)
