from crewai import LLM
import os
from typing import Optional

class LLMManager:
    """
    Manages LLM configuration for CrewAI agents.
    Supports OpenAI and Google Gemini.
    """
    
    @staticmethod
    def get_llm() -> Optional[LLM]:
        """
        Returns a configured LLM object based on environment variables.
        Priority:
        1. LLM_PROVIDER="gemini" -> Uses Google Gemini
        2. LLM_PROVIDER="openai" -> Uses OpenAI
        3. GEMINI_API_KEY present -> Defaults to Gemini
        4. OPENAI_API_KEY present -> Defaults to OpenAI
        """
        provider = os.getenv("LLM_PROVIDER", "").lower()
        model = os.getenv("LLM_MODEL", "")

        openai_key = os.getenv("OPENAI_API_KEY")
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

        if provider == "gemini" or gemini_key:
            if not model:
                model = "gemini/gemini-1.5-flash"
            elif not model.startswith("gemini/"):
                model = f"gemini/{model}"
            
            if gemini_key:
                 os.environ["GEMINI_API_KEY"] = gemini_key
            
            return LLM(model=model, api_key=gemini_key)

        elif provider == "openai" or openai_key:
            if not model:
                model = "gpt-4o-mini"
            
            return LLM(model=model, api_key=openai_key)
        
        else:
            print("❌ Warning: No valid LLM configuration (OpenAI/Gemini) found.")
            print("   Please set OPENAI_API_KEY or GEMINI_API_KEY in .env")
            return LLM(model="gpt-4o-mini")
