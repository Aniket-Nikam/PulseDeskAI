from __future__ import annotations

import asyncio
from typing import Optional

from groq import APIError, Groq, RateLimitError

from app.ai.providers.base import AIProviderError
from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("ai_groq_provider")


class GroqProvider:
    def __init__(self) -> None:
        self._client: Optional[Groq] = None
        self._model = settings.GROQ_MODEL
        self._timeout_seconds = max(1, int(settings.AI_REQUEST_TIMEOUT_SECONDS))

    def _get_client(self) -> Groq:
        api_key = (settings.GROQ_API_KEY or "").strip()
        if not api_key:
            raise AIProviderError("Groq API key is not configured")
        if self._client is None:
            self._client = Groq(api_key=api_key)
        return self._client

    def _sync_generate(
        self,
        messages: list[dict],
        *,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> str:
        client = self._get_client()

        request_messages = messages
        if system_prompt:
            request_messages = [{"role": "system", "content": system_prompt}, *messages]

        response = client.chat.completions.create(
            model=self._model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=request_messages,
        )
        text = response.choices[0].message.content if response.choices else None
        if not text:
            raise AIProviderError("Groq returned an empty response", retriable=True)
        return text

    async def generate_text(
        self,
        messages: list[dict],
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.4,
        max_tokens: int = 800,
    ) -> str:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self._sync_generate,
                    messages,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ),
                timeout=self._timeout_seconds,
            )
        except asyncio.TimeoutError:
            log.warning("groq_timeout", timeout_seconds=self._timeout_seconds)
            raise AIProviderError("Groq request timed out", retriable=True)
        except RateLimitError:
            log.warning("groq_rate_limited")
            raise AIProviderError("Groq rate limited", retriable=True)
        except APIError as e:
            log.error("groq_api_error", error_type=type(e).__name__)
            raise AIProviderError("Groq API error", retriable=True, cause=type(e).__name__)
        except AIProviderError:
            raise
        except Exception as e:
            log.error("groq_unknown_error", error_type=type(e).__name__)
            raise AIProviderError("Groq provider failure", retriable=True, cause=type(e).__name__)
