from typing import List, Dict, Any

from app.config import settings
from app.gemini_service import GeminiService
from app.embedding_service import EmbeddingService
from app.vector_store import VectorStore
from app.prompt_template import RAG_PROMPT_TEMPLATE


AI_ERROR_MESSAGES = [
    "dịch vụ AI đang quá tải",
    "vượt giới hạn sử dụng",
    "tạm thời không phản hồi",
    "chưa tạo được câu trả lời",
]


def is_ai_error_answer(answer: str) -> bool:
    if not answer:
        return True

    answer_lower = answer.lower()

    return any(message.lower() in answer_lower for message in AI_ERROR_MESSAGES)


def expand_history_query(question: str) -> str:
    """
    Mở rộng nhẹ câu hỏi bằng một số từ khóa lịch sử phổ biến.
    Lưu ý: phần này chỉ hỗ trợ vector search, không quyết định có trả lời hay không.
    """
    lower_question = question.lower()

    expansions = {
        # =========================
        # Thời tiền sử
        # =========================
        "thời tiền sử": "Việt Nam thời tiền sử đồ đá cũ đồ đá mới công cụ đá văn hóa Hòa Bình Sơn Vi Thần Sa cư dân cổ khảo cổ",
        "tiền sử": "Việt Nam thời tiền sử đồ đá cũ đồ đá mới công cụ đá văn hóa Hòa Bình Sơn Vi Thần Sa cư dân cổ khảo cổ",
        "văn hóa hòa bình": "Việt Nam thời tiền sử văn hóa Hòa Bình đồ đá công cụ đá cư dân cổ khảo cổ",

        # =========================
        # Bắc thuộc - Ngô Quyền
        # =========================
        "ngô quyền": "Bạch Đằng năm 938 quân Nam Hán Kiều Công Tiễn Dương Đình Nghệ thời Bắc thuộc độc lập dân tộc kỷ nguyên độc lập",
        "bạch đằng": "Ngô Quyền Trần Hưng Đạo sông Bạch Đằng năm 938 năm 1288 quân Nam Hán quân Nguyên chiến thắng chống ngoại xâm",

        # =========================
        # Nhà Lý
        # =========================
        "lý công uẩn": "Lý Thái Tổ Chiếu dời đô Thăng Long Hoa Lư Đại La nhà Lý",
        "lý thái tổ": "Lý Công Uẩn Chiếu dời đô Thăng Long Hoa Lư Đại La nhà Lý",
        "lý thường kiệt": "Nam quốc sơn hà kháng chiến chống Tống sông Như Nguyệt nhà Lý",
        "nam quốc sơn hà": "Lý Thường Kiệt sông Như Nguyệt kháng chiến chống Tống nhà Lý bài thơ thần tuyên ngôn độc lập đầu tiên chủ quyền dân tộc",
        "sông như nguyệt": "Nam quốc sơn hà Lý Thường Kiệt kháng chiến chống Tống nhà Lý phòng tuyến Như Nguyệt",

        # =========================
        # Nhà Trần
        # =========================
        "trần hưng đạo": "Trần Quốc Tuấn Hịch tướng sĩ quân Mông Nguyên Bạch Đằng 1288 nhà Trần",
        "trần quốc tuấn": "Trần Hưng Đạo Hịch tướng sĩ quân Mông Nguyên Bạch Đằng 1288 nhà Trần",
        "hịch tướng sĩ": "Trần Hưng Đạo Trần Quốc Tuấn kháng chiến chống Mông Nguyên nhà Trần tinh thần yêu nước",

        # =========================
        # Nhà Hồ
        # =========================
        "hồ quý ly": "Nhà Hồ Đại Ngu cải cách cuối thế kỷ XIV đầu thế kỷ XV Thành nhà Hồ",
        "nhà hồ": "Hồ Quý Ly Đại Ngu cải cách tiền giấy hạn điền hạn nô Thành nhà Hồ chống quân Minh",

        # =========================
        # Lê sơ
        # =========================
        "lê lợi": "Lê Thái Tổ khởi nghĩa Lam Sơn chống quân Minh Bình Ngô đại cáo nhà Lê sơ",
        "lê thái tổ": "Lê Lợi khởi nghĩa Lam Sơn chống quân Minh Bình Ngô đại cáo nhà Lê sơ",
        "nguyễn trãi": "Bình Ngô đại cáo khởi nghĩa Lam Sơn Lê Lợi quân Minh nhà Lê sơ",
        "bình ngô đại cáo": "Nguyễn Trãi Lê Lợi khởi nghĩa Lam Sơn chống quân Minh tuyên ngôn độc lập nhà Lê sơ",
        "lê thánh tông": "Luật Hồng Đức nhà Lê sơ Đại Việt văn trị võ công giáo dục thi cử",
        "luật hồng đức": "Lê Thánh Tông Quốc triều hình luật nhà Lê sơ pháp luật Đại Việt",

        # =========================
        # Tây Sơn
        # =========================
        "quang trung": "Nguyễn Huệ Tây Sơn Ngọc Hồi Đống Đa quân Thanh năm 1789",
        "nguyễn huệ": "Quang Trung Tây Sơn Ngọc Hồi Đống Đa quân Thanh năm 1789",
        "ngọc hồi": "Quang Trung Nguyễn Huệ Tây Sơn đại phá quân Thanh năm 1789 Đống Đa",
        "đống đa": "Quang Trung Nguyễn Huệ Tây Sơn Ngọc Hồi đại phá quân Thanh năm 1789",

        # =========================
        # Hồ Chí Minh
        # Không dùng keyword 'bác' vì quá rộng, dễ gây nhiễu.
        # =========================
        "hồ chí minh": "Bác Hồ Chủ tịch Hồ Chí Minh Nguyễn Sinh Cung Nguyễn Tất Thành Nguyễn Ái Quốc sinh ngày 19/5/1890 quê Nghệ An Tuyên ngôn Độc lập",
        "bác hồ": "Hồ Chí Minh Chủ tịch Hồ Chí Minh Nguyễn Sinh Cung Nguyễn Tất Thành Nguyễn Ái Quốc sinh ngày 19/5/1890 quê Nghệ An",
        "chủ tịch hồ chí minh": "Bác Hồ Hồ Chí Minh Nguyễn Sinh Cung Nguyễn Tất Thành Nguyễn Ái Quốc Tuyên ngôn Độc lập",
        "nguyễn ái quốc": "Hồ Chí Minh Bác Hồ Chủ tịch Hồ Chí Minh Nguyễn Sinh Cung Nguyễn Tất Thành",

        # =========================
        # Hiện đại
        # =========================
        "võ nguyên giáp": "Đại tướng Điện Biên Phủ Quân đội nhân dân Việt Nam kháng chiến chống Pháp",
        "điện biên phủ": "Võ Nguyên Giáp kháng chiến chống Pháp năm 1954 Hiệp định Genève",
        "chiến dịch hồ chí minh": "Đại thắng mùa Xuân 1975 giải phóng miền Nam thống nhất đất nước Văn Tiến Dũng",
        "cách mạng tháng tám": "năm 1945 Tổng khởi nghĩa Hồ Chí Minh Tuyên ngôn Độc lập Việt Nam Dân chủ Cộng hòa",
        "đổi mới": "Đại hội VI năm 1986 công cuộc Đổi mới phát triển kinh tế xã hội",
    }

    expanded_question = question

    for keyword, extra_keywords in expansions.items():
        if keyword in lower_question:
            expanded_question += " " + extra_keywords

    return expanded_question


def keyword_score(question: str, document: str, metadata: Dict[str, Any]) -> int:
    """
    Chấm điểm keyword để hỗ trợ rerank.
    Lưu ý: điểm này KHÔNG dùng để chặn câu trả lời.
    """
    question_lower = question.lower()
    doc_lower = document.lower()

    title = str(metadata.get("title", "")).lower()
    period = str(metadata.get("period", "")).lower()
    file_name = str(metadata.get("file_name", "")).lower()
    source = str(metadata.get("source", "")).lower()

    searchable_text = f"{doc_lower} {title} {period} {file_name} {source}"

    score = 0

    important_keywords = [
        # Thời tiền sử
        "thời tiền sử",
        "tiền sử",
        "đồ đá cũ",
        "đồ đá mới",
        "công cụ đá",
        "văn hóa hòa bình",
        "sơn vi",
        "thần sa",
        "khảo cổ",
        "cư dân cổ",

        # Bắc thuộc - chống Bắc thuộc
        "ngô quyền",
        "bạch đằng",
        "nam hán",
        "kiều công tiễn",
        "dương đình nghệ",

        # Nhà Lý
        "lý công uẩn",
        "lý thái tổ",
        "lý thường kiệt",
        "thăng long",
        "chiếu dời đô",
        "nam quốc sơn hà",
        "sông như nguyệt",
        "bài thơ thần",
        "tuyên ngôn độc lập đầu tiên",
        "chủ quyền dân tộc",

        # Nhà Trần
        "trần hưng đạo",
        "trần quốc tuấn",
        "mông nguyên",
        "hịch tướng sĩ",

        # Nhà Hồ
        "hồ quý ly",
        "nhà hồ",
        "đại ngu",
        "thành nhà hồ",

        # Lê sơ
        "lê lợi",
        "lê thái tổ",
        "nguyễn trãi",
        "bình ngô đại cáo",
        "lê thánh tông",
        "luật hồng đức",

        # Tây Sơn
        "quang trung",
        "nguyễn huệ",
        "tây sơn",
        "ngọc hồi",
        "đống đa",

        # Hiện đại
        "hồ chí minh",
        "bác hồ",
        "nguyễn ái quốc",
        "nguyễn sinh cung",
        "nguyễn tất thành",
        "võ nguyên giáp",
        "điện biên phủ",
        "chiến dịch hồ chí minh",
        "cách mạng tháng tám",
        "đổi mới",
    ]

    for keyword in important_keywords:
        if keyword in question_lower and keyword in searchable_text:
            score += 10

    # Chấm thêm theo từ trong câu hỏi.
    # Bỏ các từ quá chung để tránh nhiễu.
    stop_words = {
        "là", "gì", "của", "và", "có", "trong", "với", "cho",
        "một", "những", "các", "nào", "sao", "vì", "hãy",
        "phân", "tích", "trình", "bày", "ý", "nghĩa",
    }

    for word in question_lower.split():
        word = word.strip(".,?!:;()[]{}\"'")

        if len(word) >= 3 and word not in stop_words and word in searchable_text:
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
    Rerank kết quả:
    1. Ưu tiên keyword score cao hơn
    2. Nếu cùng score, ưu tiên distance nhỏ hơn

    Đây chỉ là hỗ trợ sắp xếp, không phải điều kiện chặn.
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

    return (
        [item["document"] for item in selected],
        [item["metadata"] for item in selected],
        [item["distance"] for item in selected],
    )


def filter_by_distance(
    documents: List[str],
    metadatas: List[Dict[str, Any]],
    distances: List[float],
    max_distance: float,
):
    """
    Lọc nhẹ theo distance.
    Chỉ bỏ những chunk quá xa.
    Không phụ thuộc keyword.
    """
    filtered_documents = []
    filtered_metadatas = []
    filtered_distances = []

    for index, doc in enumerate(documents):
        distance = distances[index] if index < len(distances) else 999
        metadata = metadatas[index]

        if distance <= max_distance:
            filtered_documents.append(doc)
            filtered_metadatas.append(metadata)
            filtered_distances.append(distance)

    return filtered_documents, filtered_metadatas, filtered_distances


class RAGService:
    def __init__(self):
        # Gemini chỉ dùng để sinh câu trả lời
        self.gemini_service = GeminiService()

        # Embedding local dùng để tạo vector cho câu hỏi
        self.embedding_service = EmbeddingService()

        self.vector_store = VectorStore()

    def build_context(
        self,
        documents: List[str],
        metadatas: List[Dict[str, Any]]
    ) -> str:
        context_parts = []

        for index, doc in enumerate(documents):
            metadata = metadatas[index]

            title = metadata.get("title", "Không rõ tiêu đề")
            source = metadata.get("source", "Không rõ nguồn")
            period = metadata.get("period", "Không rõ giai đoạn")
            url = metadata.get("url", "")

            context_parts.append(
                f"""
[Tài liệu {index + 1}]
Tiêu đề: {title}
Nguồn: {source}
URL: {url}
Giai đoạn: {period}
Nội dung:
{doc}
"""
            )

        return "\n".join(context_parts)

    def format_sources(
        self,
        metadatas: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
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
            return {
                "answer": "Vui lòng nhập câu hỏi.",
                "sources": []
            }

        if self.vector_store.count_documents() == 0:
            return {
                "answer": "Hiện tại hệ thống chưa có dữ liệu lịch sử. Vui lòng nạp tài liệu trước.",
                "sources": []
            }

        # 1. Mở rộng nhẹ câu hỏi.
        # Đây chỉ là hỗ trợ vector search, không bắt buộc phải có keyword.
        expanded_question = expand_history_query(question)

        # 2. Vector search là chính.
        question_embedding = self.embedding_service.create_embedding(expanded_question)

        # Lấy nhiều kết quả để có cơ hội tìm đúng chunk.
        search_top_k = max(settings.TOP_K * 4, 20)

        results = self.vector_store.search(
            query_embedding=question_embedding,
            top_k=search_top_k
        )

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        if not documents:
            return {
                "answer": "Hiện tại hệ thống chưa có đủ dữ liệu để trả lời chính xác câu hỏi này.",
                "sources": []
            }

        # 3. Rerank chỉ để hỗ trợ, không dùng keyword để chặn.
        documents, metadatas, distances = rerank_results(
            question=expanded_question,
            documents=documents,
            metadatas=metadatas,
            distances=distances,
            top_k=search_top_k,
        )

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

        # 4. Chỉ dùng distance để quyết định có từ chối hay không.
        # Không dùng best_score để chặn nữa.
        if best_distance > settings.SIMILARITY_THRESHOLD:
            return {
                "answer": "Hiện tại hệ thống chưa có đủ dữ liệu để trả lời chính xác câu hỏi này.",
                "sources": []
            }

        # 5. Lọc nhẹ các chunk quá xa, nhưng không filter theo keyword.
        documents, metadatas, distances = filter_by_distance(
            documents=documents,
            metadatas=metadatas,
            distances=distances,
            max_distance=settings.SIMILARITY_THRESHOLD,
        )

        if not documents:
            return {
                "answer": "Hiện tại hệ thống chưa có đủ dữ liệu để trả lời chính xác câu hỏi này.",
                "sources": []
            }

        # 6. Chỉ lấy 3 tài liệu tốt nhất để tránh context quá dài/nhiễu.
        final_top_k = min(settings.TOP_K, 3)

        documents = documents[:final_top_k]
        metadatas = metadatas[:final_top_k]
        distances = distances[:final_top_k]

        context = self.build_context(documents, metadatas)

        prompt = RAG_PROMPT_TEMPLATE.format(
            context=context,
            question=question
        )

        answer = self.gemini_service.generate_answer(prompt)

        # 7. Nếu Gemini quá tải hoặc lỗi thì không trả sources.
        if is_ai_error_answer(answer):
            return {
                "answer": answer,
                "sources": []
            }

        # 8. Nếu Gemini tự kết luận không đủ dữ liệu thì không trả sources.
        if "Hiện tại hệ thống chưa có đủ dữ liệu" in answer:
            return {
                "answer": answer,
                "sources": []
            }

        return {
            "answer": answer,
            "sources": self.format_sources(metadatas)
        }