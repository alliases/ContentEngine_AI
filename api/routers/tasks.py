# api/routers/tasks.py
import asyncio
import uuid
from collections.abc import AsyncGenerator

import orjson
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_tenant, get_db_session
from db.models import Task

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("/{task_id}/stream")
async def stream_task_status(
    task_id: str,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """
    SSE endpoint for streaming task execution status.
    Uses strict tenant isolation and non-blocking asyncio delays.
    """
    try:
        task_uuid = uuid.UUID(task_id)
        tenant_uuid = uuid.UUID(tenant_id)
    except ValueError as e:
        # FIX: Ruff B904 - Raise from specific exception to maintain trace chain internally
        # FastAPI will handle HTTP 400 safely without exposing the stack trace to the client.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID format"
        ) from e

    # Initial strict verification
    stmt = select(Task).where(Task.id == task_uuid, Task.tenant_id == tenant_uuid)
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    # FIX: Pylance Strict Mode - AsyncGenerator[YieldType, SendType]
    async def event_generator() -> AsyncGenerator[str]:
        # Optimization: frozenset for O(1) immutable lookups
        terminal_statuses: frozenset[str] = frozenset(
            {"COMPLETED", "FAILED", "NEEDS_HUMAN_REVIEW"}
        )

        while True:
            # Re-fetch object within loop to get updated status
            res = await db.execute(
                select(Task).where(Task.id == task_uuid, Task.tenant_id == tenant_uuid)
            )
            current_task = res.scalar_one_or_none()

            # Strict check against None
            if current_task is None:
                error_payload = {"error": "Task unexpectedly deleted"}
                yield f"data: {orjson.dumps(error_payload).decode('utf-8')}\n\n"
                break

            payload = {
                "task_id": str(current_task.id),
                "status": current_task.status,
                "result": current_task.result_json,
                "error": current_task.error,
            }
            yield f"data: {orjson.dumps(payload).decode('utf-8')}\n\n"

            if current_task.status in terminal_statuses:
                break

            # Crucial: Prevent event loop blocking while waiting for next DB poll
            await asyncio.sleep(2.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
