from pydantic import BaseModel, Field
from typing import Optional, List

class SkymapNameUpdate(BaseModel):
    asterism_name: str = Field(..., max_length=255)
    asterism_meaning: Optional[str] = Field(None, max_length=500)

class MatchData(BaseModel):
    ra: float
    dec: float
    roll: float
    scale: float
    n_matched: int
    confidence_pct: float
    star_ids: Optional[List[int]] = None
    constellation: str
    asterism_name: Optional[str] = None
    asterism_meaning: Optional[str] = None
    story: Optional[str] = None
    discovered_on: Optional[str] = None
    star_pattern_url: Optional[str] = None

class SkymapResponse(BaseModel):
    id: int
    status: str
    message: Optional[str] = None
    match: Optional[MatchData] = None

class SkymapUpdateResponse(BaseModel):
    message: str
    story: str

class BuildIndexResponse(BaseModel):
    status: str
    task_id: str
    message: str
