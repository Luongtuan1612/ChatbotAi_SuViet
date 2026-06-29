# SuViet AI Service

SuViet AI Service là dịch vụ AI hỗ trợ hỏi đáp kiến thức Lịch sử Việt Nam bằng mô hình RAG. Hệ thống sử dụng dữ liệu lịch sử đã được thu thập, lưu vào ChromaDB và truy xuất các đoạn nội dung phù hợp để Gemini sinh câu trả lời.

## Công nghệ sử dụng

- Python
- FastAPI
- ChromaDB
- Sentence Transformers
- Gemini API
- BeautifulSoup
- Requests

## Cách hoạt động

```text
Người dùng đặt câu hỏi
        ↓
AI Service tạo embedding cho câu hỏi
        ↓
Tìm kiếm tài liệu liên quan trong ChromaDB
        ↓
Lấy nội dung phù hợp làm ngữ cảnh
        ↓
Gửi ngữ cảnh và câu hỏi cho Gemini
        ↓
Trả về câu trả lời kèm nguồn tham khảo
Cài đặt và chạy dự án
1. Tạo môi trường ảo
python -m venv venv

Kích hoạt môi trường ảo trên Windows:

venv\Scripts\activate
2. Cài đặt thư viện
pip install -r requirements.txt
3. Tạo file .env

Tạo file .env tại thư mục gốc và cấu hình:

GEMINI_API_KEY=your_gemini_api_key
GEMINI_CHAT_MODEL=gemini-2.0-flash

LOCAL_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

CHROMA_DB_PATH=./chroma_db
CHROMA_COLLECTION_NAME=suviet_history

TOP_K=5
SIMILARITY_THRESHOLD=1.2
4. Thu thập dữ liệu từ URL
python scripts/fetch_web_articles.py
5. Nạp dữ liệu vào ChromaDB

Nạp toàn bộ dữ liệu:

python scripts/ingest_documents.py

Hoặc nạp riêng một giai đoạn:

python scripts/ingest_documents.py 05_nha_ly
6. Chạy AI Service
uvicorn app.main:app --reload --port 8001

Swagger API:

http://127.0.0.1:8001/docs
API chính
Kiểm tra hệ thống
GET /health
Kiểm tra số lượng tài liệu đã nạp
GET /documents
Hỏi chatbot
POST /chat

Request mẫu:

{
  "question": "Ngô Quyền là ai?"
}
Admin lấy nội dung từ URL
POST /admin/knowledge/fetch-url
Admin nạp file vào ChromaDB
POST /admin/knowledge/ingest-file
Admin xem danh sách nguồn
GET /admin/knowledge/sources