from loguru import logger
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import FieldCondition, Filter, MatchValue
from sentence_transformers import SentenceTransformer

from api.config import settings


class StyleRetriever:
    def __init__(self) -> None:
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.qdrant = AsyncQdrantClient(
            host=settings.qdrant_host, port=settings.qdrant_port
        )

    async def get_similar_posts(
        self, query_text: str, tenant_id: str, top_k: int = 3
    ) -> list[str]:
        """Retrieves similar posts strictly isolated by tenant_id."""
        collection_name = f"posts_{tenant_id}"

        try:
            exists = await self.qdrant.collection_exists(
                collection_name=collection_name
            )
            if not exists:
                logger.warning(
                    {"event": "collection_not_found", "tenant_id": tenant_id}
                )
                return []

            vector = self.model.encode(query_text).tolist()

            search_result = await self.qdrant.search(
                collection_name=collection_name,
                query_vector=vector,  # type: ignore
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="tenant_id", match=MatchValue(value=tenant_id)
                        )
                    ]
                ),
                limit=top_k,
            )

            return [
                str(hit.payload["text"])
                for hit in search_result
                if hit.payload and "text" in hit.payload
            ]

        except Exception as e:
            logger.error(
                {
                    "event": "qdrant_search_failed",
                    "error": str(e),
                    "tenant_id": tenant_id,
                }
            )
            return []
