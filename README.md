# SuViet AI Service

SuViet AI Service là dịch vụ AI hỗ trợ hỏi đáp kiến thức Lịch sử Việt Nam bằng mô hình RAG.
Hệ thống sử dụng dữ liệu lịch sử được thu thập từ các nguồn đáng tin cậy, sau đó lưu vào Vector Database để phục vụ việc truy xuất thông tin khi người dùng đặt câu hỏi.

## Công nghệ sử dụng

* Python
* FastAPI
* ChromaDB
* Sentence Transformers
* Gemini API
* BeautifulSoup
* Requests

## Cách hệ thống hoạt động

Luồng hoạt động của chatbot:

```text
Người dùng đặt câu hỏi
        ↓
AI Service tạo embedding cho câu hỏi
        ↓
Tìm kiếm tài liệu liên quan trong ChromaDB
        ↓
Lấy các đoạn nội dung phù hợp làm ngữ cảnh
        ↓
Gửi ngữ cảnh và câu hỏi cho Gemini
        ↓
Gemini sinh câu trả lời dựa trên tài liệu đã truy xuất
        ↓
Trả về câu trả lời kèm nguồn tham khảo
```

## Dữ liệu lịch sử

Dữ liệu được chia theo các giai đoạn lịch sử Việt Nam, ví dụ:

```text
01. Việt Nam thời tiền sử
02. Thời dựng nước đầu tiên
03. Bắc thuộc và chống Bắc thuộc
04. Triều Ngô, Đinh, Tiền Lê
05. Nhà Lý
06. Nhà Trần
07. Nhà Hồ
08. Nhà Lê sơ
09. Nam - Bắc triều, Trịnh - Nguyễn phân tranh
10. Phong trào Tây Sơn
11. Nhà Nguyễn
12. Việt Nam từ năm 1858 đến năm 1945
13. Việt Nam từ năm 1945 đến năm 1975
14. Việt Nam từ năm 1975 đến nay
15. Nhân vật lịch sử
```

Các nguồn dữ liệu chính gồm:

* Bảo tàng Lịch sử Quốc gia
* Trang thông tin về Chủ tịch Hồ Chí Minh
* Cổng thông tin Chính phủ
* Báo Quân đội nhân dân
* Tư liệu Văn kiện Đảng
* Bộ Giáo dục và Đào tạo

## Cách chạy dự án

### 1. Tạo môi trường ảo

```bash
python -m venv venv
```

Kích hoạt môi trường ảo trên Windows:

```bash
venv\Scripts\activate
```

### 2. Cài đặt thư viện

```bash
pip install -r requirements.txt
```

### 3. Tạo file `.env`

Tạo file `.env` tại thư mục gốc và cấu hình:

```env
GEMINI_API_KEY=your_gemini_api_key
GEMINI_CHAT_MODEL=gemini-2.0-flash

LOCAL_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

CHROMA_DB_PATH=./chroma_db
CHROMA_COLLECTION_NAME=suviet_history

TOP_K=5
SIMILARITY_THRESHOLD=1.2
```

### 4. Thu thập dữ liệu từ URL

```bash
python scripts/fetch_web_articles.py
```

Lệnh này đọc các URL trong thư mục:

```text
data/source_urls/
```

và lưu nội dung bài viết vào:

```text
data/periods/<ten_giai_doan>/raw/
```

### 5. Nạp dữ liệu vào ChromaDB

Nạp toàn bộ dữ liệu:

```bash
python scripts/ingest_documents.py
```

Hoặc nạp riêng một giai đoạn:

```bash
python scripts/ingest_documents.py 05_nha_ly
```

### 6. Chạy AI Service

```bash
uvicorn app.main:app --reload --port 8001
```

Sau khi chạy, mở Swagger API tại:

```text
http://127.0.0.1:8001/docs
```

## API chính

### Kiểm tra hệ thống

```http
GET /health
```

### Kiểm tra số lượng tài liệu đã nạp

```http
GET /documents
```

### Hỏi chatbot

```http
POST /chat
```

Request mẫu:

```json
{
  "question": "Ngô Quyền là ai?"
}
```

Response mẫu:

```json
{
  "answer": "Ngô Quyền là người lãnh đạo quân dân Việt Nam đánh thắng quân Nam Hán trên sông Bạch Đằng năm 938, mở ra thời kỳ độc lập tự chủ.",
  "sources": [
    {
      "title": "Ngô Quyền và chiến thắng Bạch Đằng năm 938",
      "source": "Bảo tàng Lịch sử Quốc gia",
      "period": "Bắc thuộc và chống Bắc thuộc",
      "url": "https://baotanglichsu.vn/..."
    }
  ]
}
```

## Ghi chú

Nếu thay đổi mô hình embedding hoặc muốn nạp lại dữ liệu từ đầu, cần xóa ChromaDB cũ rồi ingest lại:

```bash
rmdir /s /q chroma_db
python scripts/ingest_documents.py
```

Nếu chỉ thêm URL mới, chạy:

```bash
python scripts/fetch_web_articles.py
python scripts/ingest_documents.py <ten_giai_doan>
```

## Tác giả

Dự án được thực hiện trong khuôn khổ đồ án tốt nghiệp.

Sinh viên thực hiện: Lương Ngọc Tuân
Đề tài: Xây dựng website hỗ trợ học tập Lịch sử Việt Nam tích hợp chatbot AI sử dụng mô hình RAG.
