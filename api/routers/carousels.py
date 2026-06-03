import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from api.dependencies import get_db_session, get_current_tenant
from api.schemas.content import CarouselResponse, CarouselDetailResponse, SlideResponse
from db.models import Carousel, Slide

router = APIRouter(prefix="/carousels", tags=["Carousels"])

@router.get("", response_model=list[CarouselResponse])
async def list_carousels(
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db_session)
) -> list[Carousel]:
    """Retrieves all carousels for the current isolated tenant."""
    stmt = select(Carousel).where(Carousel.tenant_id == uuid.UUID(tenant_id))
    result = await db.execute(stmt)
    carousels = result.scalars().all()
    
    if not carousels:
        logger.info({"event": "empty_carousel_list", "tenant_id": tenant_id})
        return [] # Return valid empty object per resilience policy
        
    return list(carousels)

@router.get("/{carousel_id}", response_model=CarouselDetailResponse)
async def get_carousel(
    carousel_id: uuid.UUID,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db_session)
) -> CarouselDetailResponse | dict[str, str]:
    """Retrieves a specific carousel with its attached slides."""
    stmt_carousel = select(Carousel).where(
        Carousel.id == carousel_id,
        Carousel.tenant_id == uuid.UUID(tenant_id)
    )
    result_carousel = await db.execute(stmt_carousel)
    carousel = result_carousel.scalar_one_or_none()
    
    if not carousel:
        logger.error({"event": "carousel_not_found", "carousel_id": str(carousel_id)})
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carousel not found")
        
    stmt_slides = select(Slide).where(Slide.carousel_id == carousel.id).order_by(Slide.position)
    result_slides = await db.execute(stmt_slides)
    slides = result_slides.scalars().all()
    
    response = CarouselDetailResponse.model_validate(carousel)
    response.slides = [SlideResponse.model_validate(s) for s in slides]
    
    return response
