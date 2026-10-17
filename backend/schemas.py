from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class EvidenceFrame(BaseModel):
    timestamp_sec: float = Field(..., description="Временная отметка кадра в секундах от начала видео")
    image_base64: str = Field(..., description="Кадр в формате JPEG base64")

class ViolationItem(BaseModel):
    type: str = Field(..., description="Название типа нарушения")
    timecode_sec: float = Field(..., description="Таймкод события в секундах от начала видео")
    description: str = Field(..., description="Что видно на видео и почему это нарушение")
    evidence_frames: List[EvidenceFrame] = Field(
        ..., 
        description="1-3 кадра-доказательства в формате JPEG base64",
        min_length=1,
        max_length=3
    )

class JobResponse(BaseModel):
    job_id: str
    status: Literal["processing", "done", "failed"]
    verdict: Optional[Literal["violation", "no_violation"]] = None
    violations: List[ViolationItem] = Field(default_factory=list)
    error: Optional[str] = None

class AnalyzeInitResponse(BaseModel):
    job_id: str
