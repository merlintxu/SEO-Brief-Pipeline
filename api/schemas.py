# api/schemas.py
from pydantic import BaseModel, HttpUrl, Field, field_validator
from typing import Optional

class BriefingRequest(BaseModel):
    """Request schema for briefing generation with strict validation."""
    
    keyword: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="SEO keyword to generate briefing for (2-100 chars)"
    )
    target_url: Optional[str] = Field(
        None,
        description="Optional target URL to analyze"
    )
    upload_to_sheets: bool = Field(
        default=True,
        description="Upload result to Google Sheets"
    )
    related_limit: int = Field(
        default=30,
        ge=5,
        le=100,
        description="Max related keywords to fetch (5-100)"
    )
    serp_num: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of SERP results to analyze (1-50)"
    )
    
    @field_validator('keyword')
    @classmethod
    def validate_keyword(cls, v: str) -> str:
        """Ensure keyword is not just whitespace."""
        if not v.strip():
            raise ValueError("Keyword cannot be empty or whitespace-only")
        return v.strip()

class BriefingResponse(BaseModel):
    run_id: str
    keyword: str
    status: str = "completed"
    output_dir: str
    files: dict[str, str]  # formato → URL relativa