from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    AdminFetchUrlRequest,
    AdminFetchUrlResponse,
    AdminIngestFileRequest,
    AdminIngestFileResponse,
    AdminDeleteKnowledgeRequest,
    AdminDeleteKnowledgeResponse,
)

from app.rag_service import RAGService
from app.vector_store import VectorStore

from scripts.fetch_web_articles import fetch_single_url_to_txt
from scripts.ingest_documents import (
    ingest_single_file,
    delete_single_file_from_knowledge,
)

app = FastAPI(
    title="SuViet AI Service",
    description="AI Chatbot RAG hỗ trợ học lịch sử Việt Nam",
    version="1.0.0",
)

# Cho phép frontend/backend gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],  # Khi deploy thật nên sửa thành domain frontend/backend của bạn
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rag_service = RAGService()
vector_store = VectorStore()


@app.get("/health", response_model=HealthResponse)
def health_check():
    return {"status": "ok", "message": "SuViet AI Service is running"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    result = rag_service.ask(request.question)

    return {"answer": result["answer"], "sources": result["sources"]}


@app.get("/documents")
def get_documents():
    count = vector_store.count_documents()

    return {
        "total_chunks": count,
        "message": "Danh sách chunk tài liệu đã được nạp vào Vector Database",
    }


@app.post("/admin/knowledge/fetch-url", response_model=AdminFetchUrlResponse)
def admin_fetch_url(request: AdminFetchUrlRequest):
    """
    API nội bộ cho chức năng Admin quản lý nguồn tri thức AI.

    Luồng xử lý:
    - Nhận URL từ Admin
    - Gọi lại fetch_single_url_to_txt()
    - Dùng thuật toán cũ trong fetch_web_articles.py để lấy nội dung
    - Lưu nội dung thành file .txt
    - Trả về đường dẫn file và nội dung xem trước
    """
    try:
        result = fetch_single_url_to_txt(
            url=request.url,
            title=request.title,
            period=request.period,
            category=request.category,
        )

        return {
            "success": True,
            "message": "Đã lấy nội dung từ URL và tạo file TXT.",
            "title": result["title"],
            "url": result["url"],
            "filePath": result["file_path"],
            "contentPreview": result["content_preview"],
            "contentLength": result["content_length"],
        }

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Lỗi lấy nội dung từ URL: {type(exc).__name__}: {exc}",
        )


@app.post("/admin/knowledge/ingest-file", response_model=AdminIngestFileResponse)
def admin_ingest_file(request: AdminIngestFileRequest):
    """
    API nội bộ cho chức năng Admin nạp nguồn tri thức vào ChromaDB.

    Luồng xử lý:
    - Nhận đường dẫn file .txt
    - Gọi lại ingest_single_file()
    - Nếu file đã nạp rồi thì bỏ qua
    - Nếu chưa nạp thì chia chunk, tạo embedding và lưu vào ChromaDB
    """
    try:
        result = ingest_single_file(request.filePath)

        return {
            "success": True,
            "skipped": result.get("skipped", False),
            "message": result.get("message", "Đã xử lý file TXT."),
            "filePath": result["file_path"],
            "chunksAdded": result["chunks_added"],
            "totalChunks": result["total_chunks"],
        }

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Lỗi nạp file vào ChromaDB: {type(exc).__name__}: {exc}",
        )


@app.post(
    "/admin/knowledge/delete-file",
    response_model=AdminDeleteKnowledgeResponse,
)
def admin_delete_file(request: AdminDeleteKnowledgeRequest):
    """
    API nội bộ:
    Xóa dữ liệu của một nguồn khỏi AI Service:
    - Xóa chunk trong ChromaDB
    - Xóa file TXT nếu deleteFile=True
    """

    try:
        result = delete_single_file_from_knowledge(
            file_path=request.filePath,
            delete_file=request.deleteFile,
        )

        return {
            "success": True,
            "message": result["message"],
            "filePath": result["file_path"],
            "documentId": result["document_id"],
            "deletedFromChroma": result["deleted_from_chroma"],
            "deletedFile": result["deleted_file"],
            "totalChunks": result["total_chunks"],
        }

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Lỗi xóa nguồn khỏi AI Service: {type(exc).__name__}: {exc}",
        )
