import os
import sys
import hashlib
from pathlib import Path

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

    Ví dụ:
    data/manual_documents/admin_sources/bach-dang.txt
    -> md5 cố định
    """
    normalized_path = file_path.replace("\\", "/").lower()
    return hashlib.md5(normalized_path.encode("utf-8")).hexdigest()


def is_document_already_ingested(
    document_id: str,
    vector_store: VectorStore,
) -> bool:
    """
    Kiểm tra tài liệu đã từng được nạp vào ChromaDB chưa.

    Khi ingest, chunk đầu tiên luôn có ID:
    {document_id}_chunk_0

    Nếu chunk_0 đã tồn tại thì coi như tài liệu này đã được nạp.
    Khi đó bỏ qua để tránh tạo embedding lại.
    """
    try:
        first_chunk_id = f"{document_id}_chunk_0"

        result = vector_store.collection.get(ids=[first_chunk_id])

        return bool(result.get("ids"))

    except Exception as e:
        print(f"Không kiểm tra được document_id {document_id}: {e}")
        return False


def extract_metadata_value(content: str, prefix: str) -> str:
    """
    Lấy giá trị metadata từ file txt.
    Ví dụ:
    TIÊU ĐỀ: ...
    NGUỒN: ...
    TÊN NGUỒN: ...
    GIAI ĐOẠN: ...
    """
    for line in content.splitlines():
        line = line.strip()

        if line.startswith(prefix):
            return line.replace(prefix, "", 1).strip()

    return ""


def extract_main_content(content: str) -> str:
    """
    Lấy phần nội dung chính sau dòng 'NỘI DUNG:'.
    Nếu không có dòng này thì dùng toàn bộ file.
    """
    marker = "NỘI DUNG:"

    if marker in content:
        return content.split(marker, 1)[1].strip()

    return content.strip()


def load_single_document(file_path: str) -> dict:
    """
    Đọc 1 file txt cụ thể để phục vụ chức năng Admin nạp từng nguồn vào AI.

    File do fetch_web_articles.py tạo thường có dạng:
    TIÊU ĐỀ: ...
    NGUỒN: ...
    TÊN NGUỒN: ...
    GIAI ĐOẠN: ...
    DANH MỤC: ...

    NỘI DUNG:
    ...
    """
    path = Path(file_path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {path}")

    if not path.is_file():
        raise ValueError(f"Đường dẫn không phải file: {path}")

    if path.suffix.lower() != ".txt":
        raise ValueError("Chỉ hỗ trợ ingest file .txt")

    with open(path, "r", encoding="utf-8") as file:
        raw_content = file.read()

    title = extract_metadata_value(raw_content, "TIÊU ĐỀ:")
    source_url = extract_metadata_value(raw_content, "NGUỒN:")
    source_name = extract_metadata_value(raw_content, "TÊN NGUỒN:")
    period = extract_metadata_value(raw_content, "GIAI ĐOẠN:")

    main_content = extract_main_content(raw_content)

    if not title:
        title = path.stem

    if not source_name:
        source_name = source_url

    if not period:
        period = "Nguồn do quản trị viên bổ sung"

    if not main_content:
        raise ValueError("File không có nội dung để ingest.")

    return {
        "title": title,
        "source": source_name,
        "period": period,
        "url": source_url,
        "file_name": path.name,
        "file_path": str(path),
        "content": main_content,
    }


def ingest_documents(
    documents: list[dict],
    embedding_service: EmbeddingService,
    vector_store: VectorStore,
    skip_existing: bool = True,
) -> int:
    """
    Hàm lõi dùng chung cho:
    - ingest_folder()
    - ingest_single_file()

    Nếu skip_existing=True:
    - File nào đã có document_id trong ChromaDB thì bỏ qua
    - Không tạo embedding lại
    - Không upsert lại
    """
    if not documents:
        return 0

    total_chunks = 0

    for doc in documents:
        print(f"\nĐang xử lý tài liệu: {doc['file_name']}")

        document_id = create_document_id(doc["file_path"])

        if skip_existing and is_document_already_ingested(document_id, vector_store):
            print(f"Bỏ qua vì tài liệu đã được nạp trước đó: {doc['file_name']}")
            continue

        chunks = split_text(doc["content"])

        if not chunks:
            print(f"Bỏ qua vì không tạo được chunk: {doc['file_name']}")
            continue

        ids = []
        chunk_texts = []
        embeddings = []
        metadatas = []

        for index, chunk in enumerate(chunks):
            chunk_id = f"{document_id}_chunk_{index}"

            try:
                embedding = embedding_service.create_embedding(chunk)
            except Exception as e:
                print(
                    f"Lỗi tạo embedding cho chunk {index} của file {doc['file_name']}: {e}"
                )
                continue

            ids.append(chunk_id)
            chunk_texts.append(chunk)
            embeddings.append(embedding)

            metadatas.append(
                {
                    "document_id": document_id,
                    "title": doc["title"],
                    "source": doc["source"],
                    "period": doc["period"],
                    "url": doc.get("url", ""),
                    "file_name": doc["file_name"],
                    "file_path": doc["file_path"],
                    "chunk_index": index,
                }
            )

        if not ids:
            print(f"Bỏ qua file vì không có chunk embedding hợp lệ: {doc['file_name']}")
            continue

        try:
            vector_store.add_documents(
                ids=ids,
                documents=chunk_texts,
                embeddings=embeddings,
                metadatas=metadatas,
            )

            total_chunks += len(ids)
            print(f"Đã nạp {len(ids)} chunks từ file {doc['file_name']}")

        except Exception as e:
            print(f"Lỗi khi nạp file {doc['file_name']} vào ChromaDB: {e}")

    return total_chunks


def ingest_folder(
    folder_path: str,
    embedding_service: EmbeddingService,
    vector_store: VectorStore,
    skip_existing: bool = True,
) -> int:
    """
    Nạp toàn bộ tài liệu trong một thư mục.
    Mặc định bỏ qua các tài liệu đã được nạp trước đó.
    """
    if not os.path.exists(folder_path):
        print(f"Bỏ qua vì không tồn tại thư mục: {folder_path}")
        return 0

    documents = load_documents_from_folder(folder_path)

    if not documents:
        print(f"Không tìm thấy tài liệu nào trong thư mục {folder_path}")
        return 0

    return ingest_documents(
        documents=documents,
        embedding_service=embedding_service,
        vector_store=vector_store,
        skip_existing=skip_existing,
    )


def get_total_chunks(vector_store: VectorStore) -> int:
    """
    Lấy tổng số chunk hiện có trong ChromaDB.
    """
    try:
        if hasattr(vector_store, "count_documents"):
            return vector_store.count_documents()

        if hasattr(vector_store, "collection"):
            return vector_store.collection.count()

        return 0
    except Exception:
        return 0


def ingest_single_file(
    file_path: str,
    skip_existing: bool = True,
) -> dict:
    """
    Hàm phục vụ Admin:
    - Nhận đường dẫn 1 file .txt
    - Kiểm tra đã nạp chưa
    - Nếu đã nạp rồi thì bỏ qua
    - Nếu chưa nạp thì chia chunk, tạo embedding và lưu vào ChromaDB

    Đây là hàm API /admin/knowledge/ingest-file sẽ gọi.
    """
    embedding_service = EmbeddingService()
    vector_store = VectorStore()

    document = load_single_document(file_path)
    document_id = create_document_id(document["file_path"])

    if skip_existing and is_document_already_ingested(document_id, vector_store):
        total_chunks = get_total_chunks(vector_store)

        print(f"Bỏ qua vì tài liệu đã được nạp trước đó: {document['file_name']}")

        return {
            "success": True,
            "skipped": True,
            "message": "Tài liệu đã được nạp trước đó, hệ thống đã bỏ qua.",
            "file_path": document["file_path"],
            "chunks_added": 0,
            "total_chunks": total_chunks,
        }

    chunks_added = ingest_documents(
        documents=[document],
        embedding_service=embedding_service,
        vector_store=vector_store,
        skip_existing=skip_existing,
    )

    total_chunks = get_total_chunks(vector_store)

    return {
        "success": True,
        "skipped": False,
        "message": "Đã nạp tài liệu vào ChromaDB.",
        "file_path": document["file_path"],
        "chunks_added": chunks_added,
        "total_chunks": total_chunks,
    }


def delete_single_file_from_knowledge(
    file_path: str,
    delete_file: bool = True,
) -> dict:
    """
    Hàm phục vụ Admin:
    - Xóa toàn bộ chunk của file khỏi ChromaDB
    - Xóa file TXT nếu delete_file=True
    """

    source_file = Path(file_path).resolve()

    document_id = create_document_id(str(source_file))

    vector_store = VectorStore()

    deleted_from_chroma = False
    deleted_file = False

    try:
        vector_store.delete_by_document_id(document_id)
        deleted_from_chroma = True
    except Exception as exc:
        raise RuntimeError(f"Lỗi khi xóa dữ liệu khỏi ChromaDB: {exc}") from exc

    if delete_file and source_file.exists():
        try:
            source_file.unlink()
            deleted_file = True
        except Exception as exc:
            raise RuntimeError(f"Lỗi khi xóa file TXT: {exc}") from exc

    total_chunks = get_total_chunks(vector_store)

    return {
        "success": True,
        "message": "Đã xóa dữ liệu nguồn khỏi AI Service.",
        "file_path": str(source_file),
        "document_id": document_id,
        "deleted_from_chroma": deleted_from_chroma,
        "deleted_file": deleted_file,
        "total_chunks": total_chunks,
    }


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
        return [BASE_PERIODS_FOLDER, MANUAL_DOCUMENTS_FOLDER]

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
        total_chunks += ingest_folder(
            folder_path=folder,
            embedding_service=embedding_service,
            vector_store=vector_store,
            skip_existing=True,
        )

    print(f"\nHoàn tất. Tổng số chunks mới đã nạp: {total_chunks}")


if __name__ == "__main__":
    ingest()
