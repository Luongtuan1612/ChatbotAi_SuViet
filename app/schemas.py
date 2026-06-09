from typing import List, Optional
from pydantic import BaseModel


class ChatRequest(BaseModel):
    question: str


class SourceItem(BaseModel):
    title: Optional[str] = None
    source: Optional[str] = None
    period: Optional[str] = None
    url: Optional[str] = None
    file_name: Optional[str] = None
    chunk_index: Optional[int] = None


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceItem]


class HealthResponse(BaseModel):
    status: str
    message: str