"""
AIProvider abstraction. The rest of the app (agents) never talks to Ollama,
Groq, or any HTTP endpoint directly — only through this interface, so the
default (Ollama, local, free) can be swapped for Groq or any OpenAI-compatible
endpoint via one env var with zero code changes elsewhere.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AIGenerationResult:
    text: str
    raw_json: dict[str, Any] | None
    provider: str
    model: str
    tokens_used: int = 0
    latency_ms: float = 0.0


class AIProviderError(RuntimeError):
    pass


class AIProvider(ABC):
    name: str = "base"

    @abstractmethod
    def configured(self) -> bool:
        """Whether this provider has everything it needs to make a real call."""

    @abstractmethod
    def generate_json(self, *, system_prompt: str, user_prompt: str, schema_hint: str) -> AIGenerationResult:
        """Ask the model for a JSON object matching schema_hint. Callers are
        responsible for validating the returned raw_json against a Pydantic
        model — this layer does not guarantee schema conformance, only that
        it attempted to parse JSON out of the response."""

    @abstractmethod
    def generate_text(self, *, system_prompt: str, user_prompt: str) -> AIGenerationResult:
        """Free-form text generation (content drafts, outreach copy, etc.)."""
