# api/schemas.py
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class BriefingRequest(BaseModel):
    """Request schema for briefing generation with strict validation."""

    keyword: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="SEO keyword to generate briefing for (2-100 chars)",
    )
    target_url: Optional[str] = Field(
        None,
        description="Optional target URL to analyze",
    )
    upload_to_sheets: bool = Field(
        default=True,
        description="Upload result to Google Sheets",
    )
    related_limit: int = Field(
        default=30,
        ge=5,
        le=100,
        description="Max related keywords to fetch (5-100)",
    )
    serp_num: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of SERP results to analyze (1-50)",
    )

    @field_validator("keyword")
    @classmethod
    def validate_keyword(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Keyword cannot be empty or whitespace-only")
        return v.strip()


class BriefingResponse(BaseModel):
    run_id: str
    keyword: str
    status: str = "completed"
    output_dir: str
    files: dict[str, str]


class JobsCleanupRequest(BaseModel):
    max_age_days: int = Field(default=30, ge=1, le=3650)
    statuses: list[str] = Field(default_factory=lambda: ["done", "failed"], min_length=1, max_length=2)

    @field_validator("statuses")
    @classmethod
    def validate_statuses(cls, value: list[str]) -> list[str]:
        allowed = {"done", "failed"}
        normalized = [item.strip().lower() for item in value]
        invalid = [item for item in normalized if item not in allowed]
        if invalid:
            raise ValueError("statuses only allows terminal states: done, failed")
        if len(set(normalized)) != len(normalized):
            raise ValueError("statuses must not contain duplicates")
        return normalized


class JobResponse(BaseModel):
    run_id: str
    keyword: str
    status: str
    step: str
    message: str
    error_category: str | None = None
    output_dir: str
    source_run_id: str | None = None
    created_at: str
    updated_at: str


class JobEventResponse(BaseModel):
    id: int
    run_id: str
    status: str
    step: str
    message: str
    error_category: str | None = None
    created_at: str


class JobsListResponse(BaseModel):
    items: list[JobResponse]
    count: int
    next_cursor: int | None = None


class JobEventsListResponse(BaseModel):
    items: list[JobEventResponse]
    count: int
    next_cursor: int | None = None


class OperatorAuditEventRequest(BaseModel):
    action: str = Field(..., min_length=1, max_length=64)
    result: str = Field(..., min_length=1, max_length=32)
    run_id: str | None = Field(default=None, max_length=100)
    metadata: str | None = Field(default=None, max_length=500)

    @field_validator("action", "result")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value cannot be empty or whitespace-only")
        return stripped

    @field_validator("run_id", "metadata")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class OperatorAuditEventResponse(BaseModel):
    id: int
    action: str
    result: str
    run_id: str | None = None
    metadata: str | None = None
    created_at: str


class OperatorAuditEventsListResponse(BaseModel):
    items: list[OperatorAuditEventResponse]
    count: int
    next_cursor: int | None = None


class JobDetailResponse(BaseModel):
    job: JobResponse
    status_file: dict | None = None
    events: list[JobEventResponse] = Field(default_factory=list)


class JobDeleteResponse(BaseModel):
    deleted: bool
    run_id: str


class JobsCleanupResponse(BaseModel):
    deleted_count: int
    max_age_days: int
    statuses: list[str]


class JobRetryResponse(BaseModel):
    source_run_id: str
    run_id: str
    status: str


class JobCancelResponse(BaseModel):
    run_id: str
    status: str
    step: str
