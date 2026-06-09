from typing import List, Dict, Any
from app.config import settings
from app.gemini_service import GeminiService
from app.embedding_service import EmbeddingService
from app.vector_store import VectorStore
from app.prompt_template import RAG_PROMPT_TEMPLATE


def expand_history_query(question: str) -> str:
    """
    Mở rộng câu hỏi ngắn bằng các từ khóa lịch sử liên quan.
    Giúp ChromaDB tìm đúng tài liệu hơn.
    """
    lower_question = question.lower()

    expansions = {
        "ngô quyền": "Bạch Đằng năm 938 quân Nam Hán Kiều Công Tiễn Dương Đình Nghệ thời Bắc thuộc độc lập dân tộc kỷ nguyên độc lập",
        "bạch đằng": "Ngô Quyền năm 938 quân Nam Hán sông Bạch Đằng chiến thắng chống Bắc thuộc độc lập dân tộc",
        "lý công uẩn": "Lý Thái Tổ Chiếu dời đô Thăng Long Hoa Lư Đại La nhà Lý",
        "lý thái tổ": "Lý Công Uẩn Chiếu dời đô Thăng Long Hoa Lư Đại La nhà Lý",
        "lý thường kiệt": "Nam quốc sơn hà kháng chiến chống Tống sông Như Nguyệt nhà Lý",
        "trần hưng đạo": "Trần Quốc Tuấn Hịch tướng sĩ quân Mông Nguyên Bạch Đằng 1288 nhà Trần",
        "trần quốc tuấn": "Trần Hưng Đạo Hịch tướng sĩ quân Mông Nguyên Bạch Đằng 1288 nhà Trần",
        "lê lợi": "Lê Thái Tổ khởi nghĩa Lam Sơn chống quân Minh Bình Ngô đại cáo nhà Lê sơ",
        "nguyễn trãi": "Bình Ngô đại cáo khởi nghĩa Lam Sơn Lê Lợi quân Minh nhà Lê sơ",
        "lê thánh tông": "Luật Hồng Đức nhà Lê sơ Đại Việt văn trị võ công",
        "hồ quý ly": "Nhà Hồ Đại Ngu cải cách cuối thế kỷ XIV đầu thế kỷ XV Thành nhà Hồ",
        "quang trung": "Nguyễn Huệ Tây Sơn Ngọc Hồi Đống Đa quân Thanh năm 1789",
        "nguyễn huệ": "Quang Trung Tây Sơn Ngọc Hồi Đống Đa quân Thanh năm 1789",
        "hồ chí minh": "Bác Hồ Chủ tịch Hồ Chí Minh Nguyễn Sinh Cung Nguyễn Tất Thành Nguyễn Ái Quốc",
        "bác hồ": "Hồ Chí Minh Chủ tịch Hồ Chí Minh Nguyễn Sinh Cung Nguyễn Tất Thành Nguyễn Ái Quốc",
        "bác": "Hồ Chí Minh Bác Hồ Chủ tịch Hồ Chí Minh Nguyễn Sinh Cung Nguyễn Tất Thành Nguyễn Ái Quốc",
        "chủ tịch hồ chí minh": "Bác Hồ Hồ Chí Minh Nguyễn Sinh Cung Nguyễn Tất Thành Nguyễn Ái Quốc",
        "nguyễn ái quốc": "Hồ Chí Minh Bác Hồ Chủ tịch Hồ Chí Minh Nguyễn Sinh Cung Nguyễn Tất Thành",
        "võ nguyên giáp": "Đại tướng Điện Biên Phủ Quân đội nhân dân Việt Nam kháng chiến chống Pháp",
        "điện biên phủ": "Võ Nguyên Giáp kháng chiến chống Pháp năm 1954 Hiệp định Genève",
        "chiến dịch hồ chí minh": "Đại thắng mùa Xuân 1975 giải phóng miền Nam thống nhất đất nước",
        "cách mạng tháng tám": "năm 1945 Tổng khởi nghĩa Hồ Chí Minh Tuyên ngôn Độc lập",
        "đổi mới": "Đại hội VI năm 1986 công cuộc Đổi mới phát triển kinh tế xã hội",
    }

    expanded_question = question

    for keyword, extra_keywords in expansions.items():
        if keyword in lower_question:
            expanded_question += " " + extra_keywords

    return expanded_question


def keyword_score(question: str, document: str, metadata: Dict[str, Any]) -> int:
    """
    Chấm điểm đơn giản theo từ khóa xuất hiện trong document và metadata.
    Dùng để đẩy tài liệu liên quan lên trên.
    """
    question_lower = question.lower()
    doc_lower = document.lower()

    title = str(metadata.get("title", "")).lower()
    period = str(metadata.get("period", "")).lower()
    file_name = str(metadata.get("file_name", "")).lower()

    searchable_text = f"{doc_lower} {title} {period} {file_name}"

    score = 0

    important_keywords = [
        "ngô quyền",
        "bạch đằng",
        "nam hán",
        "kiều công tiễn",
        "dương đình nghệ",
        "lý công uẩn",
        "lý thái tổ",
        "lý thường kiệt",
        "thăng long",
        "chiếu dời đô",
        "trần hưng đạo",
        "trần quốc tuấn",
        "mông nguyên",
        "hịch tướng sĩ",
        "lê lợi",
        "nguyễn trãi",
        "lê thánh tông",
        "hồ quý ly",
        "quang trung",
        "nguyễn huệ",
        "tây sơn",
        "hồ chí minh",
        "nguyễn ái quốc",
        "võ nguyên giáp",
        "điện biên phủ",
        "chiến dịch hồ chí minh",
        "cách mạng tháng tám",
        "đổi mới",
    ]

    for keyword in important_keywords:
        if keyword in question_lower and keyword in searchable_text:
            score += 10

    # Chấm thêm theo các từ trong câu hỏi
    for word in question_lower.split():
        if len(word) >= 3 and word in searchable_text:
            score += 1

    return score


def rerank_results(
    question: str,
    documents: List[str],
    metadatas: List[Dict[str, Any]],
    distances: List[float],
    top_k: int,
):
    """
    Sắp xếp lại kết quả theo:
    1. Keyword score cao hơn
    2. Distance nhỏ hơn
    """
    combined = []

    for index, doc in enumerate(documents):
        metadata = metadatas[index]
        distance = distances[index] if index < len(distances) else 999

        score = keyword_score(question, doc, metadata)

        combined.append(
            {
                "document": doc,
                "metadata": metadata,
                "distance": distance,
                "score": score,
            }
        )

    combined.sort(key=lambda item: (-item["score"], item["distance"]))

    selected = combined[:top_k]

    reranked_documents = [item["document"] for item in selected]
    reranked_metadatas = [item["metadata"] for item in selected]
    reranked_distances = [item["distance"] for item in selected]

    return reranked_documents, reranked_metadatas, reranked_distances


def filter_relevant_results(
    question: str,
    documents: List[str],
    metadatas: List[Dict[str, Any]],
    distances: List[float],
):
    """
    Lọc bỏ các tài liệu không liên quan trực tiếp đến chủ đề câu hỏi.
    Ví dụ hỏi Ngô Quyền thì chỉ giữ tài liệu có Ngô Quyền, Bạch Đằng, Nam Hán...
    """
    question_lower = question.lower()

    topic_keywords_map = {
        "ngô quyền": [
            "ngô quyền",
            "bạch đằng",
            "nam hán",
            "kiều công tiễn",
            "dương đình nghệ",
            "938",
        ],
        "bạch đằng": [
            "bạch đằng",
            "ngô quyền",
            "nam hán",
            "trần hưng đạo",
            "1288",
            "938",
        ],
        "lý công uẩn": [
            "lý công uẩn",
            "lý thái tổ",
            "chiếu dời đô",
            "thăng long",
            "hoa lư",
            "đại la",
        ],
        "lý thái tổ": [
            "lý công uẩn",
            "lý thái tổ",
            "chiếu dời đô",
            "thăng long",
            "hoa lư",
            "đại la",
        ],
        "lý thường kiệt": [
            "lý thường kiệt",
            "nam quốc sơn hà",
            "sông như nguyệt",
            "chống tống",
        ],
        "trần hưng đạo": [
            "trần hưng đạo",
            "trần quốc tuấn",
            "hịch tướng sĩ",
            "mông",
            "nguyên",
            "bạch đằng 1288",
        ],
        "trần quốc tuấn": [
            "trần hưng đạo",
            "trần quốc tuấn",
            "hịch tướng sĩ",
            "mông",
            "nguyên",
        ],
        "lê lợi": ["lê lợi", "lê thái tổ", "lam sơn", "quân minh", "bình ngô"],
        "nguyễn trãi": ["nguyễn trãi", "bình ngô", "lam sơn", "lê lợi", "quân minh"],
        "lê thánh tông": ["lê thánh tông", "hồng đức", "lê sơ", "đại việt"],
        "hồ quý ly": ["hồ quý ly", "nhà hồ", "đại ngu", "cải cách", "thành nhà hồ"],
        "quang trung": [
            "quang trung",
            "nguyễn huệ",
            "tây sơn",
            "ngọc hồi",
            "đống đa",
            "quân thanh",
        ],
        "nguyễn huệ": [
            "quang trung",
            "nguyễn huệ",
            "tây sơn",
            "ngọc hồi",
            "đống đa",
            "quân thanh",
        ],
        "hồ chí minh": [
            "hồ chí minh",
            "nguyễn ái quốc",
            "tuyên ngôn độc lập",
            "2/9/1945",
            "việt nam dân chủ cộng hòa",
        ],
        "nguyễn ái quốc": [
            "hồ chí minh",
            "nguyễn ái quốc",
            "tuyên ngôn độc lập",
            "cách mạng tháng tám",
        ],
        "võ nguyên giáp": [
            "võ nguyên giáp",
            "điện biên phủ",
            "đại tướng",
            "quân đội nhân dân",
        ],
        "điện biên phủ": [
            "điện biên phủ",
            "võ nguyên giáp",
            "1954",
            "hiệp định genève",
        ],
        "chiến dịch hồ chí minh": [
            "chiến dịch hồ chí minh",
            "đại thắng mùa xuân",
            "1975",
            "giải phóng miền nam",
            "thống nhất đất nước",
        ],
        "cách mạng tháng tám": [
            "cách mạng tháng tám",
            "tổng khởi nghĩa",
            "1945",
            "hồ chí minh",
            "tuyên ngôn độc lập",
        ],
        "đổi mới": ["đổi mới", "đại hội vi", "1986", "kinh tế xã hội"],
    }

    active_keywords = []

    for topic, keywords in topic_keywords_map.items():
        if topic in question_lower:
            active_keywords = keywords
            break

    # Nếu không nhận diện được chủ đề cụ thể thì giữ nguyên kết quả
    if not active_keywords:
        return documents, metadatas, distances

    filtered_documents = []
    filtered_metadatas = []
    filtered_distances = []

    for index, doc in enumerate(documents):
        metadata = metadatas[index]
        distance = distances[index] if index < len(distances) else 999

        searchable_text = " ".join(
            [
                doc.lower(),
                str(metadata.get("title", "")).lower(),
                str(metadata.get("period", "")).lower(),
                str(metadata.get("file_name", "")).lower(),
            ]
        )

        if any(keyword in searchable_text for keyword in active_keywords):
            filtered_documents.append(doc)
            filtered_metadatas.append(metadata)
            filtered_distances.append(distance)

    # Nếu lọc xong không còn gì thì dùng lại kết quả cũ để tránh mất hoàn toàn context
    if not filtered_documents:
        return documents, metadatas, distances

    return filtered_documents, filtered_metadatas, filtered_distances


class RAGService:
    def __init__(self):
        # Gemini chỉ dùng để sinh câu trả lời
        self.gemini_service = GeminiService()

        # Embedding local dùng để tạo vector cho câu hỏi
        self.embedding_service = EmbeddingService()

        self.vector_store = VectorStore()

    def build_context(
        self, documents: List[str], metadatas: List[Dict[str, Any]]
    ) -> str:
        context_parts = []

        for index, doc in enumerate(documents):
            metadata = metadatas[index]

            title = metadata.get("title", "Không rõ tiêu đề")
            source = metadata.get("source", "Không rõ nguồn")
            period = metadata.get("period", "Không rõ giai đoạn")
            url = metadata.get("url", "")

            context_parts.append(f"""
[Tài liệu {index + 1}]
Tiêu đề: {title}
Nguồn: {source}
URL: {url}
Giai đoạn: {period}
Nội dung:
{doc}
""")

        return "\n".join(context_parts)

    def format_sources(self, metadatas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        sources = []
        seen = set()

        for metadata in metadatas:
            key = (
                metadata.get("title"),
                metadata.get("url"),
            )

            if key in seen:
                continue

            seen.add(key)

            sources.append(
                {
                    "title": metadata.get("title"),
                    "source": metadata.get("source"),
                    "period": metadata.get("period"),
                    "url": metadata.get("url"),
                    "file_name": metadata.get("file_name"),
                    "chunk_index": metadata.get("chunk_index"),
                }
            )

        return sources

    def ask(self, question: str) -> Dict[str, Any]:
        if not question or not question.strip():
            return {"answer": "Vui lòng nhập câu hỏi.", "sources": []}

        if self.vector_store.count_documents() == 0:
            return {
                "answer": "Hiện tại hệ thống chưa có dữ liệu lịch sử. Vui lòng nạp tài liệu trước.",
                "sources": [],
            }

        # 1. Mở rộng câu hỏi trước khi tạo embedding
        expanded_question = expand_history_query(question)

        # 2. Tạo embedding bằng câu hỏi đã mở rộng
        question_embedding = self.embedding_service.create_embedding(expanded_question)

        # 3. Lấy nhiều kết quả hơn TOP_K để có dữ liệu rerank
        search_top_k = max(settings.TOP_K * 4, 20)

        results = self.vector_store.search(
            query_embedding=question_embedding, top_k=search_top_k
        )

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        if not documents:
            return {
                "answer": "Hiện tại hệ thống chưa có đủ dữ liệu để trả lời chính xác câu hỏi này.",
                "sources": [],
            }

        # 4. Rerank kết quả để ưu tiên tài liệu có keyword liên quan
        documents, metadatas, distances = rerank_results(
            question=expanded_question,
            documents=documents,
            metadatas=metadatas,
            distances=distances,
            top_k=search_top_k,
        )

        # 5. Lọc bỏ tài liệu nhiễu theo chủ đề câu hỏi
        documents, metadatas, distances = filter_relevant_results(
            question=question,
            documents=documents,
            metadatas=metadatas,
            distances=distances,
        )

        # 6. Sau khi lọc, chỉ lấy một số tài liệu tốt nhất để tránh nhiễu context
        final_top_k = min(settings.TOP_K, 3)

        documents = documents[:final_top_k]
        metadatas = metadatas[:final_top_k]
        distances = distances[:final_top_k]

        if not documents:
            return {
                "answer": "Hiện tại hệ thống chưa có đủ dữ liệu để trả lời chính xác câu hỏi này.",
                "sources": [],
            }

        best_distance = distances[0] if distances else 999
        best_score = (
            keyword_score(expanded_question, documents[0], metadatas[0])
            if documents
            else 0
        )

        print("Câu hỏi gốc:", question)
        print("Câu hỏi mở rộng:", expanded_question)
        print("Best distance:", best_distance)
        print("Best keyword score:", best_score)
        print("Best title:", metadatas[0].get("title") if metadatas else None)

        # 7. Chỉ từ chối khi distance quá xa và không có keyword nào khớp
        if best_distance > settings.SIMILARITY_THRESHOLD and best_score <= 0:
            return {
                "answer": "Hiện tại hệ thống chưa có đủ dữ liệu để trả lời chính xác câu hỏi này.",
                "sources": [],
            }

        context = self.build_context(documents, metadatas)

        prompt = RAG_PROMPT_TEMPLATE.format(context=context, question=question)

        answer = self.gemini_service.generate_answer(prompt)

        # 8. Nếu Gemini tự kết luận không đủ dữ liệu thì không trả sources
        if "Hiện tại hệ thống chưa có đủ dữ liệu" in answer:
            return {"answer": answer, "sources": []}

        return {"answer": answer, "sources": self.format_sources(metadatas)}
