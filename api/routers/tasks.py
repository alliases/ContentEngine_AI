# api/routers/tasks.py

import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import Protocol, cast

import orjson
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_tenant, get_db_session, get_redis_client
from db.models import Task

router = APIRouter(prefix="/tasks", tags=["Tasks"])


# --- Enterprise Standard: Strictly Typed Protocol for Untyped Third-Party Libs ---
class PubSubProtocol(Protocol):
    async def subscribe(self, channel: str) -> None: ...
    async def unsubscribe(self, channel: str) -> None: ...
    async def close(self) -> None: ...
    async def get_message(
        self, ignore_subscribe_messages: bool = ...
    ) -> dict[str, str | bytes] | None: ...


class RedisClientProtocol(Protocol):
    def pubsub(self) -> PubSubProtocol: ...


# ---------------------------------------------------------------------------------


@router.get("/stream")
async def stream_tenant_tasks(
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db_session),
    redis_client: Redis = Depends(get_redis_client),
) -> StreamingResponse:
    """
    Aggregated SSE endpoint for streaming all active task statuses for a tenant.
    Enforces tenant isolation, uses Redis Pub/Sub to prevent DB polling,
    and includes keep-alive heartbeat to prevent Nginx timeouts.
    """
    try:
        tenant_uuid = uuid.UUID(tenant_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant ID format"
        ) from e

    async def event_generator() -> AsyncGenerator[str]:
        # 1. Initial State Load (Invariant 4)
        stmt = select(Task).where(Task.tenant_id == tenant_uuid)
        result = await db.execute(stmt)
        tasks = result.scalars().all()

        initial_data = [
            {
                "task_id": str(t.id),
                "status": t.status,
                "result": t.result_json,
                "error": t.error,
            }
            for t in tasks
        ]

        yield f"data: {orjson.dumps({'type': 'initial', 'tasks': initial_data}).decode('utf-8')}\n\n"

        # 2. Redis Pub/Sub loop with Strict Typing (via Protocol)
        safe_redis = cast(RedisClientProtocol, redis_client)
        pubsub = safe_redis.pubsub()
        channel = f"tasks:{tenant_id}"

        await pubsub.subscribe(channel)

        try:
            while True:
                try:
                    # Type is now clearly dict[str, str | bytes] | None
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=15.0,
                    )

                    if message:
                        msg_type = message.get("type")
                        # Handle potential byte response depending on decode_responses flag
                        if msg_type == "message" or msg_type == b"message":
                            data = message.get("data")

                            if isinstance(data, bytes):
                                data = data.decode("utf-8")

                            if isinstance(data, str):
                                yield f"data: {data}\n\n"

                except TimeoutError:
                    # Nginx anti-drop heartbeat
                    yield ": ping\n\n"
                except asyncio.CancelledError:
                    # Client disconnected gracefully
                    break
        finally:
            # Crucial: Prevent Connection Leaks
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")
