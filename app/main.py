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
    KnowledgeSourceListResponse,
    KnowledgeChunkListResponse,
    DeleteKnowledgeSourceResponse,
)

from app.rag_service import RAGService
from app.vector_store import VectorStore
from fastapi import FastAPI, HTTPException, Query

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],  
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
    - Mặc định nạp lại tài liệu để tránh trạng thái "thành công giả"
    - Trả về số chunk thực tế đã thêm vào ChromaDB
    """
    try:
        print("\n========== FASTAPI NHẬN YÊU CẦU INGEST =========", flush=True)
        print(f"File path nhận từ Spring Boot: {request.filePath}", flush=True)

        result = ingest_single_file(
            request.filePath,
            skip_existing=False,
            replace_existing=True,
        )

        print(f"Kết quả ingest: {result}", flush=True)
        print("================================================\n", flush=True)

        return {
            "success": True,
            "skipped": result.get("skipped", False),
            "message": result.get("message", "Đã xử lý file TXT."),
            "filePath": result["file_path"],
            "documentId": result.get("document_id", ""),
            "sourceUrl": result.get("source_url", ""),
            "chunksAdded": result["chunks_added"],
            "totalChunks": result["total_chunks"],
        }

    except Exception as exc:
        print(f"Lỗi nạp file vào ChromaDB: {type(exc).__name__}: {exc}", flush=True)

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
@app.get(
    "/admin/knowledge/sources",
    response_model=KnowledgeSourceListResponse,
)
def admin_list_knowledge_sources():
    """
    Liệt kê toàn bộ source_url đang tồn tại trong ChromaDB.
    """
    try:
        sources = vector_store.list_sources()

        return {
            "success": True,
            "totalSources": len(sources),
            "totalChunks": vector_store.count_documents(),
            "sources": sources,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Lỗi lấy danh sách source_url trong ChromaDB: {type(exc).__name__}: {exc}",
        )


@app.get(
    "/admin/knowledge/sources/chunks",
    response_model=KnowledgeChunkListResponse,
)
def admin_list_knowledge_chunks(sourceUrl: str = Query(..., min_length=1)):
    """
    Xem các chunk thuộc một source_url trong ChromaDB.
    """
    try:
        chunks = vector_store.get_chunks_by_source_url(sourceUrl)

        return {
            "success": True,
            "sourceUrl": sourceUrl,
            "totalChunks": len(chunks),
            "chunks": chunks,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Lỗi lấy chunk theo source_url: {type(exc).__name__}: {exc}",
        )


@app.delete(
    "/admin/knowledge/sources",
    response_model=DeleteKnowledgeSourceResponse,
)
def admin_delete_knowledge_source(sourceUrl: str = Query(..., min_length=1)):
    """
    Xóa toàn bộ chunk trong ChromaDB theo source_url.
    """
    try:
        result = vector_store.delete_by_source_url(sourceUrl)

        return {
            "success": True,
            "message": "Đã xử lý xóa source_url khỏi ChromaDB.",
            "sourceUrl": result["source_url"],
            "deleted": result["deleted"],
            "deletedCount": result["deleted_count"],
            "totalChunks": result["total_chunks"],
        }

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Lỗi xóa source_url khỏi ChromaDB: {type(exc).__name__}: {exc}",
        )