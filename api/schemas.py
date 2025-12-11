# api/schemas.py
from pydantic import BaseModel, HttpUrl
from typing import Optional

class BriefingRequest(BaseModel):
    keyword: str
    target_url: Optional[HttpUrl] = None
    upload_to_sheets: bool = True
    related_limit: int = 60
    serp_num: int = 12

class BriefingResponse(BaseModel):
    run_id: str
    keyword: str
    status: str = "completed"
    output_dir: str
    files: dict[str, str]  # formato → URL relativa