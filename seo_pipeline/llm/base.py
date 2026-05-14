"""Shared contracts for LLM structured output adapters."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class StructuredGenerationRequest:
    system_prompt: str
    user_prompt: str
    model: str
    temperature: float


class StructuredLLMAdapter(Protocol):
    provider: str

    def generate_structured(self, request: StructuredGenerationRequest, response_model: type[T]) -> T: ...
