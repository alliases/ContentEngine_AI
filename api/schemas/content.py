import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class SlideResponse(BaseModel):
    id: uuid.UUID
    position: int
    text_content: str
    keywords: str | None = None
    file_path: str | None = None
    
    model_config = ConfigDict(from_attributes=True)

class CarouselResponse(BaseModel):
    id: uuid.UUID
    topic: str
    status: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class CarouselDetailResponse(CarouselResponse):
    slides: list[SlideResponse] = []

class GenerateRequest(BaseModel):
    topic: str
    
class GenerateResponse(BaseModel):
    task_id: uuid.UUID
    status: str
