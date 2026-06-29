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
        """
        self.collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def search(self, query_embedding: List[float], top_k: int = 5) -> Dict[str, Any]:
        """
        Tìm các chunk gần nhất với câu hỏi bằng vector search.
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

    def get_all_chunks_for_text_scan(self, limit: int = 20000) -> List[Dict[str, Any]]:
        """
        Lấy toàn bộ chunk trong ChromaDB để quét chữ trực tiếp.

        Mục đích:
        - Không phụ thuộc hoàn toàn vào vector search.
        - Dùng cho full-text scan toàn bộ kho tri thức.
        """
        results = self.collection.get(
            include=["documents", "metadatas"],
            limit=limit,
        )

        ids = results.get("ids") or []
        documents = results.get("documents") or []
        metadatas = results.get("metadatas") or []

        chunks = []

        for index, document in enumerate(documents):
            metadata = metadatas[index] if index < len(metadatas) else {}

            raw_chunk_index = metadata.get("chunk_index", index)

            try:
                chunk_index = int(raw_chunk_index)
            except (TypeError, ValueError):
                chunk_index = index

            chunks.append(
                {
                    "id": ids[index] if index < len(ids) else None,
                    "document": document or "",
                    "metadata": metadata or {},
                    "chunk_index": chunk_index,
                }
            )

        return chunks

    def get_chunks_by_document_metadata(
        self,
        metadata: Dict[str, Any],
        limit: int = 300,
    ) -> List[Dict[str, Any]]:
        """
        Lấy toàn bộ chunk thuộc cùng một tài liệu với chunk tốt nhất.

        Thứ tự ưu tiên gom nhóm:
        1. document_id
        2. file_path
        3. source_url
        4. url
        5. file_name
        """
        if not metadata:
            return []

        group_keys = [
            "document_id",
            "file_path",
            "source_url",
            "url",
            "file_name",
        ]

        where = None

        for key in group_keys:
            value = metadata.get(key)

            if value:
                where = {key: value}
                break

        if where is None:
            return []

        results = self.collection.get(
            where=where,
            include=["documents", "metadatas"],
            limit=limit,
        )

        ids = results.get("ids") or []
        documents = results.get("documents") or []
        metadatas = results.get("metadatas") or []

        chunks = []

        for index, document in enumerate(documents):
            chunk_metadata = metadatas[index] if index < len(metadatas) else {}

            raw_chunk_index = chunk_metadata.get("chunk_index", index)

            try:
                chunk_index = int(raw_chunk_index)
            except (TypeError, ValueError):
                chunk_index = index

            chunks.append(
                {
                    "id": ids[index] if index < len(ids) else None,
                    "document": document or "",
                    "metadata": chunk_metadata or {},
                    "chunk_index": chunk_index,
                }
            )

        chunks.sort(key=lambda item: item["chunk_index"])

        return chunks

    def delete_by_document_id(self, document_id: str) -> None:
        self.collection.delete(where={"document_id": document_id})

    def _metadata_source_url(self, metadata: Dict[str, Any]) -> str:
        """
        Lấy URL nguồn từ metadata.
        Hỗ trợ cả dữ liệu cũ dùng `url` và dữ liệu mới dùng `source_url`.
        """
        if not metadata:
            return ""

        return str(
            metadata.get("source_url")
            or metadata.get("url")
            or metadata.get("file_path")
            or metadata.get("document_id")
            or ""
        ).strip()

    def list_sources(self):
        """
        Liệt kê toàn bộ source_url hiện có trong ChromaDB.
        """
        results = self.collection.get(include=["metadatas"])

        ids = results.get("ids") or []
        metadatas = results.get("metadatas") or []

        source_map = {}

        for chunk_id, metadata in zip(ids, metadatas):
            metadata = metadata or {}
            source_url = self._metadata_source_url(metadata)

            if not source_url:
                continue

            if source_url not in source_map:
                source_map[source_url] = {
                    "source_url": source_url,
                    "source_title": metadata.get("source_title") or metadata.get("title") or "",
                    "source": metadata.get("source") or "",
                    "period": metadata.get("period") or "",
                    "category": metadata.get("category") or "",
                    "file_name": metadata.get("file_name") or "",
                    "file_path": metadata.get("file_path") or "",
                    "document_id": metadata.get("document_id") or "",
                    "chunk_count": 0,
                    "sample_chunk_id": chunk_id,
                }

            source_map[source_url]["chunk_count"] += 1

        return list(source_map.values())

    def get_chunks_by_source_url(self, source_url: str):
        """
        Lấy danh sách chunk theo source_url.
        """
        source_url = (source_url or "").strip()

        if not source_url:
            return []

        results = self.collection.get(include=["documents", "metadatas"])

        ids = results.get("ids") or []
        documents = results.get("documents") or []
        metadatas = results.get("metadatas") or []

        chunks = []

        for chunk_id, document, metadata in zip(ids, documents, metadatas):
            metadata = metadata or {}

            if self._metadata_source_url(metadata) != source_url:
                continue

            chunks.append(
                {
                    "id": chunk_id,
                    "chunk_index": metadata.get("chunk_index"),
                    "title": metadata.get("title") or metadata.get("source_title") or "",
                    "source_url": source_url,
                    "period": metadata.get("period") or "",
                    "category": metadata.get("category") or "",
                    "file_name": metadata.get("file_name") or "",
                    "document_preview": (document or "")[:500],
                }
            )

        return chunks

    def delete_by_source_url(self, source_url: str):
        """
        Xóa toàn bộ chunk trong ChromaDB theo source_url.
        """
        source_url = (source_url or "").strip()

        if not source_url:
            return {
                "deleted": False,
                "source_url": source_url,
                "deleted_count": 0,
                "total_chunks": self.count_documents(),
            }

        results = self.collection.get(include=["metadatas"])

        ids = results.get("ids") or []
        metadatas = results.get("metadatas") or []

        ids_to_delete = []

        for chunk_id, metadata in zip(ids, metadatas):
            metadata = metadata or {}

            if self._metadata_source_url(metadata) == source_url:
                ids_to_delete.append(chunk_id)

        if ids_to_delete:
            self.collection.delete(ids=ids_to_delete)

        return {
            "deleted": bool(ids_to_delete),
            "source_url": source_url,
            "deleted_count": len(ids_to_delete),
            "total_chunks": self.count_documents(),
        }