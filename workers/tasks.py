import asyncio
import uuid

from loguru import logger
from sqlalchemy import update

from db.models import Carousel, Task
from db.session import async_session_maker
from workers.broker import broker


@broker.task
async def run_carousel_pipeline(carousel_id: str, tenant_id: str, task_id: str) -> dict[str, str]:
    """
    Background task to process carousel generation.
    Currently a stub that simulates work.
    LangGraph Actor-Critic integration happens in Phase 4.
    """
    logger.info({
        "event": "pipeline_started", 
        "carousel_id": carousel_id, 
        "task_id": task_id
    })

    # Simulate long-running processing time
    await asyncio.sleep(5)

    # Update DB status directly using the async session factory
    async with async_session_maker() as session:
        # Mark Task as COMPLETED
        stmt_task = (
            update(Task)
            .where(Task.id == uuid.UUID(task_id))
            .values(status="COMPLETED", result_json='{"message": "success"}')
        )
        await session.execute(stmt_task)

        # Mark Carousel as GENERATED (Ready for UI)
        stmt_carousel = (
            update(Carousel)
            .where(Carousel.id == uuid.UUID(carousel_id))
            .values(status="GENERATED")
        )
        await session.execute(stmt_carousel)

        await session.commit()

    logger.info({
        "event": "pipeline_finished", 
        "carousel_id": carousel_id, 
        "task_id": task_id
    })
    
    return {"status": "success", "task_id": task_id}
