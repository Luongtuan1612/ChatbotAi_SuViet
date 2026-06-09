from typing import List
from google import genai
from app.config import settings


class GeminiService:
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise ValueError("Thiếu GEMINI_API_KEY trong file .env")

        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def generate_answer(self, prompt: str) -> str:
        """
        Gọi Gemini để sinh câu trả lời từ prompt.
        Có xử lý lỗi rõ ràng để tránh API bị 500 khi Gemini quá tải/quota.
        """
        try:
            response = self.client.models.generate_content(
                model=settings.GEMINI_CHAT_MODEL,
                contents=prompt
            )

            if not response.text:
                return "Xin lỗi, hệ thống chưa tạo được câu trả lời."

            return response.text.strip()

        except Exception as e:
            print("Lỗi khi gọi Gemini generate_answer:", repr(e))

            error_text = str(e).lower()

            if (
                "429" in error_text
                or "resource_exhausted" in error_text
                or "quota" in error_text
                or "rate limit" in error_text
            ):
                return (
                    "Hiện tại dịch vụ AI đang quá tải hoặc đã vượt giới hạn sử dụng. "
                    "Vui lòng thử lại sau ít phút."
                )

            if (
                "503" in error_text
                or "overloaded" in error_text
                or "unavailable" in error_text
            ):
                return (
                    "Hiện tại dịch vụ AI đang quá tải hoặc tạm thời không phản hồi. "
                    "Vui lòng thử lại sau ít phút."
                )

            return (
                "Hiện tại dịch vụ AI đang quá tải hoặc tạm thời không phản hồi. "
                "Vui lòng thử lại sau ít phút."
            )

    def create_embedding(self, text: str) -> List[float]:
        """
        Hàm này giữ lại để tương thích code cũ.
        Hiện tại hệ thống KHÔNG nên dùng Gemini để embedding nữa,
        vì dễ bị lỗi quota 429 khi ingest nhiều tài liệu.
        """
        try:
            response = self.client.models.embed_content(
                model=settings.GEMINI_EMBEDDING_MODEL,
                contents=text
            )

            return response.embeddings[0].values

        except Exception as e:
            print("Lỗi khi gọi Gemini create_embedding:", repr(e))
            raise