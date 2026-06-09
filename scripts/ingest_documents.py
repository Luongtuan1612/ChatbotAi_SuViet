import os
import sys
import hashlib

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.document_loader import load_documents_from_folder, split_text
from app.embedding_service import EmbeddingService
from app.vector_store import VectorStore


BASE_PERIODS_FOLDER = "data/periods"
MANUAL_DOCUMENTS_FOLDER = "data/manual_documents"


def create_document_id(file_path: str) -> str:
    """
    Tạo ID cố định theo đường dẫn file.
    Nếu cùng một file được nạp lại, ID sẽ không thay đổi.
    """
    normalized_path = file_path.replace("\\", "/").lower()
    return hashlib.md5(normalized_path.encode("utf-8")).hexdigest()


def ingest_folder(folder_path: str, embedding_service: EmbeddingService, vector_store: VectorStore) -> int:
    if not os.path.exists(folder_path):
        print(f"Bỏ qua vì không tồn tại thư mục: {folder_path}")
        return 0

    documents = load_documents_from_folder(folder_path)

    if not documents:
        print(f"Không tìm thấy tài liệu nào trong thư mục {folder_path}")
        return 0

    total_chunks = 0

    for doc in documents:
        print(f"\nĐang xử lý tài liệu: {doc['file_name']}")

        chunks = split_text(doc["content"])

        if not chunks:
            print(f"Bỏ qua vì không tạo được chunk: {doc['file_name']}")
            continue

        ids = []
        chunk_texts = []
        embeddings = []
        metadatas = []

        document_id = create_document_id(doc["file_path"])

        for index, chunk in enumerate(chunks):
            chunk_id = f"{document_id}_chunk_{index}"

            try:
                embedding = embedding_service.create_embedding(chunk)
            except Exception as e:
                print(f"Lỗi tạo embedding cho chunk {index} của file {doc['file_name']}: {e}")
                continue

            ids.append(chunk_id)
            chunk_texts.append(chunk)
            embeddings.append(embedding)

            metadatas.append({
                "document_id": document_id,
                "title": doc["title"],
                "source": doc["source"],
                "period": doc["period"],
                "url": doc.get("url", ""),
                "file_name": doc["file_name"],
                "file_path": doc["file_path"],
                "chunk_index": index
            })

        if not ids:
            print(f"Bỏ qua file vì không có chunk embedding hợp lệ: {doc['file_name']}")
            continue

        try:
            vector_store.add_documents(
                ids=ids,
                documents=chunk_texts,
                embeddings=embeddings,
                metadatas=metadatas
            )

            total_chunks += len(ids)
            print(f"Đã nạp {len(ids)} chunks từ file {doc['file_name']}")

        except Exception as e:
            print(f"Lỗi khi nạp file {doc['file_name']} vào ChromaDB: {e}")

    return total_chunks


def get_target_folders():
    """
    Cách chạy:

    1. Nạp toàn bộ:
       python scripts/ingest_documents.py

    2. Nạp một thời kỳ:
       python scripts/ingest_documents.py 05_nha_ly

    3. Nạp nhiều thời kỳ:
       python scripts/ingest_documents.py 01_thoi_tien_su 02_thoi_dung_nuoc

    4. Nạp tài liệu thủ công:
       python scripts/ingest_documents.py manual
    """
    args = sys.argv[1:]

    if not args:
        return [
            BASE_PERIODS_FOLDER,
            MANUAL_DOCUMENTS_FOLDER
        ]

    folders = []

    for arg in args:
        if arg.lower() == "manual":
            folders.append(MANUAL_DOCUMENTS_FOLDER)
        else:
            folders.append(os.path.join(BASE_PERIODS_FOLDER, arg))

    return folders


def ingest():
    embedding_service = EmbeddingService()
    vector_store = VectorStore()

    target_folders = get_target_folders()

    print("Các thư mục sẽ được nạp:")
    for folder in target_folders:
        print(f"- {folder}")

    total_chunks = 0

    for folder in target_folders:
        print(f"\nĐang nạp thư mục: {folder}")
        total_chunks += ingest_folder(folder, embedding_service, vector_store)

    print(f"\nHoàn tất. Tổng số chunks đã nạp: {total_chunks}")


if __name__ == "__main__":
    ingest()