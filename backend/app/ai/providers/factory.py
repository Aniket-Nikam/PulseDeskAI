from __future__ import annotations

from app.ai.providers.base import AIProvider
from app.ai.providers.groq_provider import GroqProvider


def get_active_provider() -> AIProvider:
    # Groq is the only active provider today.
    # Factory exists so future providers can be added without changing route/service code.
    return GroqProvider()

