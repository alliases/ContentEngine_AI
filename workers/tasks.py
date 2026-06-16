# workers/tasks.py

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig
from loguru import logger
from sqlalchemy import select, update

from agents.graph import app
from agents.state import CarouselState, FewShotContext, RawNewsItem
from db.models import Carousel, Task
from db.session import async_session_maker
from workers.broker import broker


@broker.task
async def run_carousel_pipeline(
    carousel_id: str, tenant_id: str, task_id: str
) -> dict[str, str]:
    """
    Executes the full LangGraph pipeline securely in the background.
    """
    logger.info(
        {"event": "pipeline_started", "carousel_id": carousel_id, "task_id": task_id}
    )

    # 1. Fetch initial requirements from DB securely
    async with async_session_maker() as session:
        stmt = select(Carousel).where(
            Carousel.id == uuid.UUID(carousel_id),
            Carousel.tenant_id == uuid.UUID(tenant_id),
        )
        carousel = (await session.execute(stmt)).scalar_one_or_none()

        if not carousel:
            logger.error(
                {
                    "event": "pipeline_failed",
                    "error": "Carousel not found or tenant mismatch",
                }
            )
            return {"status": "error"}

        topic = carousel.topic

    # Mock Data injection (since Scout/RAG nodes are currently structural dummies)
    news = RawNewsItem(
        title=topic,
        text=f"Extensive overview and latest news regarding {topic}",
        source="SystemScout",
        url="https://contentengine.ai/internal",
        published_at=datetime.now(UTC),
        relevance_score=1.0,
    )
    context = FewShotContext(
        examples=["Example 1: Short, punchy, engaging."],
        similarity_scores=[0.95],
        brand_voice_summary="Professional, concise, actionable.",
    )

    initial_state: CarouselState = {
        "carousel_id": carousel_id,
        "tenant_id": tenant_id,
        "raw_news": news,
        "rag_context": context,
        "draft_slides": None,
        "feedback": None,
        "iteration_count": 0,
        "status": "WRITING",
        "error_message": None,
    }

    # 2. Execute Actor-Critic Graph
    # Require thread_id for Checkpointer
    config: RunnableConfig = {"configurable": {"thread_id": task_id}}

    try:
        final_state: dict[str, Any] = await app.ainvoke(initial_state, config=config)  # type: ignore[reportUnknownMemberType]
    except Exception as e:
        logger.error({"event": "graph_execution_failed", "error": str(e)})
        final_state: dict[str, Any] = {"status": "FALLBACK", "draft_slides": None}

    # 3. Process Results
    status = final_state.get("status")
    draft_slides = final_state.get("draft_slides")

    # Map LangGraph status to DB status
    db_status = "COMPLETED"

    # "REVIEWING" indicates the graph hit the interrupt_before=["reviewer_node"] breakpoint
    if status in ("FALLBACK", "NEEDS_REVISION", "error", "REVIEWING"):
        db_status = "NEEDS_HUMAN_REVIEW"
    elif status == "APPROVED_BY_AI":
        db_status = "GENERATED"

    result_payload = json.dumps({"slides": draft_slides}) if draft_slides else None

    # 4. Save results back to DB strictly isolated by tenant_id
    async with async_session_maker() as session:
        stmt_task = (
            update(Task)
            .where(
                Task.id == uuid.UUID(task_id),
                Task.tenant_id == uuid.UUID(tenant_id),
            )
            .values(status=db_status, result_json=result_payload)
        )
        await session.execute(stmt_task)

        stmt_carousel = (
            update(Carousel)
            .where(
                Carousel.id == uuid.UUID(carousel_id),
                Carousel.tenant_id == uuid.UUID(tenant_id),
            )
            .values(status=db_status)
        )
        await session.execute(stmt_carousel)
        await session.commit()

    logger.info({"event": "pipeline_finished", "final_db_status": db_status})
    return {"status": "success", "task_id": task_id}
