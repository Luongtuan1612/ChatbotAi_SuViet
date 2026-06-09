from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.schemas import ChatRequest, ChatResponse, HealthResponse
from app.rag_service import RAGService
from app.vector_store import VectorStore

app = FastAPI(
    title="SuViet AI Service",
    description="AI Chatbot RAG hỗ trợ học lịch sử Việt Nam",
    version="1.0.0"
)

# Cho phép frontend/backend gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Khi deploy thật nên sửa thành domain frontend/backend của bạn
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rag_service = RAGService()
vector_store = VectorStore()


@app.get("/health", response_model=HealthResponse)
def health_check():
    return {
        "status": "ok",
        "message": "SuViet AI Service is running"
    }


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    result = rag_service.ask(request.question)

    return {
        "answer": result["answer"],
        "sources": result["sources"]
    }


@app.get("/documents")
def get_documents():
    count = vector_store.count_documents()

    return {
        "total_chunks": count,
        "message": "Danh sách chunk tài liệu đã được nạp vào Vector Database"
    }