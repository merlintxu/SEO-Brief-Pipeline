"""Centralized input validation for pipeline runtime parameters."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


class PipelineInput(BaseModel):
    keyword: str = Field(..., min_length=2, max_length=100)
    target_url: Optional[HttpUrl] = None
    related_limit: int = Field(default=30, ge=5, le=100)
    serp_num: int = Field(default=10, ge=1, le=50)
    top_competitors_count: int = Field(default=3, ge=1, le=20)
    gsc_months_back: int = Field(default=11, ge=1, le=36)

    @field_validator("keyword")
    @classmethod
    def _keyword_non_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("keyword cannot be empty or whitespace-only")
        return cleaned
