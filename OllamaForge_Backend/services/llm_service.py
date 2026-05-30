from langchain_ollama import OllamaLLM
import os

class LLMService:
    def __init__(self, model, temperature=0.5):
        self.is_gemini = model.lower().startswith("gemini")
        
        if self.is_gemini:
            from langchain_google_genai import ChatGoogleGenerativeAI
            self.llm = ChatGoogleGenerativeAI(
                model=model, 
                temperature=temperature,
                max_retries=0
            )
        else:
            self.llm = OllamaLLM(model=model, temperature=temperature)

    def invoke(self, prompt):
        result = self.llm.invoke(prompt)
        if hasattr(result, "content"):
            return result.content
        return result

    def stream(self, prompt):
        for chunk in self.llm.stream(prompt):
            if hasattr(chunk, "content"):
                yield chunk.content
            else:
                yield chunk
