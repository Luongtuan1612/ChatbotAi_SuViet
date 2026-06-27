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
    documentId: Optional[str] = None
    sourceUrl: Optional[str] = None
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


class KnowledgeSourceItem(BaseModel):
    source_url: str
    source_title: Optional[str] = None
    source: Optional[str] = None
    period: Optional[str] = None
    category: Optional[str] = None
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    document_id: Optional[str] = None
    chunk_count: int = 0
    sample_chunk_id: Optional[str] = None


class KnowledgeSourceListResponse(BaseModel):
    success: bool
    totalSources: int
    totalChunks: int
    sources: List[KnowledgeSourceItem]


class KnowledgeChunkItem(BaseModel):
    id: str
    chunk_index: Optional[int] = None
    title: Optional[str] = None
    source_url: str
    period: Optional[str] = None
    category: Optional[str] = None
    file_name: Optional[str] = None
    document_preview: Optional[str] = None


class KnowledgeChunkListResponse(BaseModel):
    success: bool
    sourceUrl: str
    totalChunks: int
    chunks: List[KnowledgeChunkItem]


class DeleteKnowledgeSourceResponse(BaseModel):
    success: bool
    message: str
    sourceUrl: str
    deleted: bool
    deletedCount: int
    totalChunks: int
