from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class AIProviderError(Exception):
    message: str
    retriable: bool = False
    cause: Optional[str] = None

    def __str__(self) -> str:
        return self.message


class AIProvider(Protocol):
    async def generate_text(
        self,
        messages: list[dict],
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.4,
        max_tokens: int = 800,
    ) -> str:
        ...
