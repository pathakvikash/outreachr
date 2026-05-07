import os
from typing import Optional

from crewai import LLM


class LLMManager:
    """
    Manages LLM configuration for CrewAI agents.
    Supports OpenAI and Google Gemini.
    """

    @staticmethod
    def get_llm() -> Optional[LLM]:
        """
        Return a configured LLM based on environment variables.

        Priority:
        1. LLM_PROVIDER="gemini" uses Gemini and requires GEMINI_API_KEY or GOOGLE_API_KEY.
        2. LLM_PROVIDER="openai" uses OpenAI and requires OPENAI_API_KEY.
        3. GEMINI_API_KEY/GOOGLE_API_KEY present defaults to Gemini.
        4. OPENAI_API_KEY present defaults to OpenAI.
        """
        provider = os.getenv("LLM_PROVIDER", "").lower()
        model = os.getenv("LLM_MODEL", "")

        openai_key = os.getenv("OPENAI_API_KEY")
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

        if provider == "gemini":
            if not gemini_key:
                raise RuntimeError("LLM_PROVIDER=gemini requires GEMINI_API_KEY or GOOGLE_API_KEY.")
            return LLM(model=LLMManager._gemini_model(model), api_key=gemini_key)

        if provider == "openai":
            if not openai_key:
                raise RuntimeError("LLM_PROVIDER=openai requires OPENAI_API_KEY.")
            return LLM(model=model or "gpt-4o-mini", api_key=openai_key)

        if gemini_key:
            os.environ["GEMINI_API_KEY"] = gemini_key
            return LLM(model=LLMManager._gemini_model(model), api_key=gemini_key)

        if openai_key:
            return LLM(model=model or "gpt-4o-mini", api_key=openai_key)

        raise RuntimeError(
            "No valid LLM configuration found. Set OPENAI_API_KEY, GEMINI_API_KEY, or GOOGLE_API_KEY."
        )

    @staticmethod
    def _gemini_model(model: str) -> str:
        if not model:
            return "gemini/gemini-1.5-flash"
        if not model.startswith("gemini/"):
            return f"gemini/{model}"
        return model
