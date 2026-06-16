import asyncio
from collections.abc import Sequence
from typing import Any, Protocol, cast

from loguru import logger
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import FieldCondition, Filter, MatchValue, ScoredPoint
from sentence_transformers import SentenceTransformer

from api.config import settings


class HasToList(Protocol):
    """Strict protocol to enforce type safety on external array-like outputs."""

    def tolist(self) -> list[float]: ...


class StrictTransformer(Protocol):
    """Enforces rigid boundary types for untyped third-party ML models."""

    def encode(self, inputs: str, **kwargs: object) -> HasToList: ...


class QdrantSearchCallable(Protocol):
    """Defines precise async signature for dynamic Qdrant client lookups."""

    async def __call__(
        self,
        collection_name: str,
        query_vector: Sequence[float] | list[float],
        query_filter: Filter | None = None,
        limit: int = 10,
    ) -> list[ScoredPoint]: ...


class StyleRetriever:
    def __init__(self) -> None:
        # Cast third-party initialization to a strict protocol boundary
        self.model: StrictTransformer = cast(
            StrictTransformer, SentenceTransformer("all-MiniLM-L6-v2")
        )
        self.qdrant: AsyncQdrantClient = AsyncQdrantClient(
            host=settings.QDRANT_HOST, port=settings.QDRANT_PORT
        )

    def _execute_embedding(self, text: str) -> list[float]:
        """Isolates untyped third-party Overloads from Pylance Strict Mode."""
        embeddings = self.model.encode(text)
        return embeddings.tolist()

    async def get_similar_posts(
        self, query_text: str, tenant_id: str, top_k: int = 3
    ) -> list[str]:
        """Retrieves similar posts strictly isolated by tenant_id."""
        import uuid

        try:
            # Hotfix: Validate proper UUID format allowing hyphens
            uuid.UUID(tenant_id)
        except ValueError:
            logger.error(
                {"event": "malicious_tenant_id_detected", "tenant_id": tenant_id}
            )
            return []

        collection_name: str = f"posts_{tenant_id}"

        try:
            exists: bool = await self.qdrant.collection_exists(
                collection_name=collection_name
            )
            if not exists:
                logger.warning(
                    {"event": "collection_not_found", "tenant_id": tenant_id}
                )
                return []

            # Offload heavy ML encoding to an isolated thread pool to prevent event loop blocking
            vector = await asyncio.to_thread(self._execute_embedding, query_text)

            # CRITICAL FIX: Type Masking pattern.
            # Temporarily cast client to Any to bypass strict attribute inspection,
            # then instantly bind the dynamic method to our strict Protocol.
            untyped_client = cast(Any, self.qdrant)
            search_fn = cast(QdrantSearchCallable, untyped_client.search)

            search_result = await search_fn(
                collection_name=collection_name,
                query_vector=vector,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="tenant_id", match=MatchValue(value=tenant_id)
                        )
                    ]
                ),
                limit=top_k,
            )

            posts: list[str] = []
            for hit in search_result:
                if hit.payload and "text" in hit.payload:
                    text_value = hit.payload["text"]
                    if isinstance(text_value, str):
                        posts.append(text_value)

            return posts

        except Exception:
            # Masking raw exception tracebacks to mitigate sensitive infrastructure data leaks
            logger.error(
                {
                    "event": "qdrant_search_failed",
                    "error": "Database read operation or vector inference failure",
                    "tenant_id": tenant_id,
                }
            )
            return []
