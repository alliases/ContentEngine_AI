import asyncio
import uuid
from typing import Protocol, cast

from loguru import logger
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from api.config import settings


class HasToList(Protocol):
    """Strict protocol to enforce type safety on external array-like outputs."""

    def tolist(self) -> list[float]: ...


class StrictTransformer(Protocol):
    """Enforces rigid boundary types for untyped third-party ML models."""

    def encode(self, inputs: str, **kwargs: object) -> HasToList: ...


class PostEmbedder:
    def __init__(self) -> None:
        # Cast the external instance to a strict protocol boundary
        self.model: StrictTransformer = cast(
            StrictTransformer, SentenceTransformer("all-MiniLM-L6-v2")
        )
        self.qdrant: AsyncQdrantClient = AsyncQdrantClient(
            host=settings.QDRANT_HOST, port=settings.QDRANT_PORT
        )
        self.vector_size: int = 384

    async def init_collection(self, tenant_id: str) -> None:
        """Ensures isolated collection exists for the tenant."""
        if not tenant_id.isalnum():
            raise ValueError("Invalid tenant_id format: must be alphanumeric")

        collection_name: str = f"posts_{tenant_id}"
        exists: bool = await self.qdrant.collection_exists(
            collection_name=collection_name
        )
        if not exists:
            await self.qdrant.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size, distance=Distance.COSINE
                ),
            )
            logger.info(
                {"event": "qdrant_collection_created", "collection": collection_name}
            )

    async def embed_and_upsert(self, post_id: str, text: str, tenant_id: str) -> bool:
        """Generates embeddings and stores them in isolated Qdrant collection."""
        if not tenant_id.isalnum():
            logger.error(
                {"event": "malicious_tenant_id_detected", "tenant_id": tenant_id}
            )
            return False

        collection_name: str = f"posts_{tenant_id}"
        await self.init_collection(tenant_id)

        try:
            # Offload heavy CPU-bound ML tokenization to thread pool
            encoded_output = await asyncio.to_thread(self.model.encode, text)

            # Pylance safely evaluates this as list[float] via HasToList Protocol
            vector: list[float] = encoded_output.tolist()

            point: PointStruct = PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={"post_id": post_id, "tenant_id": tenant_id, "text": text},
            )
            await self.qdrant.upsert(collection_name=collection_name, points=[point])
            logger.info(
                {"event": "post_upserted", "post_id": post_id, "tenant_id": tenant_id}
            )
            return True
        except Exception:
            logger.error(
                {
                    "event": "qdrant_upsert_failed",
                    "error": "Database write operation or inference failure",
                    "tenant_id": tenant_id,
                }
            )
            return False
