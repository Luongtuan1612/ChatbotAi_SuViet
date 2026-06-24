from typing import List, Dict, Any
import chromadb
from app.config import settings


class VectorStore:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=settings.CHROMA_DB_PATH)

        self.collection = self.client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            metadata={"description": "Kho tri thức lịch sử Việt Nam cho SuViet"},
        )

    def add_documents(
        self,
        ids: List[str],
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
    ):
        """
        Thêm mới hoặc cập nhật chunk tài liệu vào ChromaDB.

        Nếu ID chưa tồn tại:
            -> thêm mới

        Nếu ID đã tồn tại:
            -> cập nhật lại

        Dùng upsert để khi chạy ingest lại không bị lỗi trùng ID.
        """
        self.collection.upsert(
            ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas
        )

    def search(self, query_embedding: List[float], top_k: int = 5) -> Dict[str, Any]:
        """
        Tìm các chunk gần nhất với câu hỏi.
        """
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        return results

    def count_documents(self) -> int:
        return self.collection.count()

    def get_all_documents(self):
        return self.collection.get()

    def delete_by_document_id(self, document_id: str) -> None:
        self.collection.delete(where={"document_id": document_id})
