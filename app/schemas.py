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


class AdminFetchUrlRequest(BaseModel):
    title: Optional[str] = None
    url: str
    period: Optional[str] = None
    category: Optional[str] = None


class AdminFetchUrlResponse(BaseModel):
    success: bool
    message: str
    title: str
    url: str
    filePath: str
    contentPreview: str
    contentLength: int


class AdminIngestFileRequest(BaseModel):
    filePath: str


class AdminIngestFileResponse(BaseModel):
    success: bool
    skipped: bool = False
    message: str
    filePath: str
    chunksAdded: int
    totalChunks: int


class AdminDeleteKnowledgeRequest(BaseModel):
    filePath: str
    deleteFile: bool = True


class AdminDeleteKnowledgeResponse(BaseModel):
    success: bool
    message: str
    filePath: str
    documentId: str
    deletedFromChroma: bool
    deletedFile: bool
    totalChunks: int
