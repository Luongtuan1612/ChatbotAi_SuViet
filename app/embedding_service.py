from typing import List
from sentence_transformers import SentenceTransformer
from app.config import settings


class EmbeddingService:
    def __init__(self):
        self.model = SentenceTransformer(settings.LOCAL_EMBEDDING_MODEL)

    def create_embedding(self, text: str) -> List[float]:
        embedding = self.model.encode(
            text,
            normalize_embeddings=True
        )

        return embedding.tolist()