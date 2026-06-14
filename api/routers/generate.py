# api/routers/generate.py

import uuid

from fastapi import APIRouter, Depends
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_tenant, get_db_session
from api.schemas.content import GenerateRequest, GenerateResponse
from db.models import Carousel, Task

router = APIRouter(prefix="/generate", tags=["Generation"])


@router.post("", response_model=GenerateResponse)
async def generate_carousel(
    request: GenerateRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db_session),
) -> GenerateResponse:
    """Initiates the generation pipeline. Returns task_id for tracking."""
    # 1. Create Carousel Draft
    new_carousel = Carousel(
        tenant_id=uuid.UUID(tenant_id), topic=request.topic, status="PENDING"
    )
    db.add(new_carousel)
    await db.flush()  # Flush to get new_carousel.id

    # 2. Create Background Task entry
    new_task = Task(carousel_id=new_carousel.id, status="PROCESSING")
    db.add(new_task)
    await db.commit()

    logger.info(
        {
            "event": "generation_started",
            "tenant_id": tenant_id,
            "carousel_id": str(new_carousel.id),
            "task_id": str(new_task.id),
        }
    )

    # Taskiq invocation will go here in Step 2.4

    return GenerateResponse(task_id=new_task.id, status="processing")
