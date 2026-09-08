from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from typing import List, Optional
from app.schemas.skymap import MatchData

class AnalysisCreate(BaseModel):
    upload_id: int
    
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

class PointUpdate(BaseModel):
    x: float
    y: float
    radius: float
    score: float
    source: str = "user_added"
    
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

class PointsPatch(BaseModel):
    points: List[PointUpdate]
    
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

class AnalysisCreateResponse(BaseModel):
    analysis_id: int
    status: str

class ConstellationItem(BaseModel):
    id: int
    asterism_name: Optional[str] = None
    discovered_on: Optional[str] = None
    ra: float
    dec: float

class ImageMeta(BaseModel):
    width: int
    height: int

class AnalysisResponse(BaseModel):
    analysis_id: int
    upload_id: int
    status: str
    image: Optional[ImageMeta] = None
    n_points: Optional[int] = None
    points: Optional[List[PointUpdate]] = None
    match: Optional[MatchData] = None

class PointsPatchResponse(BaseModel):
    message: str
    status: str

class UploadResponse(BaseModel):
    upload_id: int
    url: str
