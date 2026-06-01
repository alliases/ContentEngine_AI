from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from loguru import logger

from db.session import engine
from api.routers import auth


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting up FastAPI and DB pool...")
    # Future scope: add async DB ping/healthcheck here
    yield

    logger.info("Shutting down DB pool...")
    try:
        await engine.dispose()
        logger.info("DB pool shut down successfully.")
    except Exception as e:
        # Do not expose raw traceback to potential external logging streams directly without formatting
        logger.error(f"Error during DB pool shutdown: {str(e)}")


app = FastAPI(
    title="ContentEngine AI",
    description="Multi-Agent SaaS for LinkedIn/Instagram carousels",
    version="0.1.0",
    lifespan=lifespan,
    # Security: Disable Swagger UI in production environments
    # docs_url=None if ENVIRONMENT == "production" else "/docs",
    # redoc_url=None if ENVIRONMENT == "production" else "/redoc",
)

@app.get("/health", tags=["System"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


# Include routers
app.include_router(auth.router, prefix="/api/v1")
