from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from api.routers import auth, carousels, generate
from db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    logger.info("Starting up FastAPI and DB pool...")
    # Future scope: add async DB ping/healthcheck here
    yield

    logger.info("Shutting down DB pool...")
    try:
        await engine.dispose()
        logger.info("DB pool shut down successfully.")
    except Exception as e:
        # Do not expose raw traceback to potential external logging streams directly without formatting
        logger.error(f"Error during DB pool shutdown: {e!s}")


app = FastAPI(
    title="ContentEngine AI",
    description="Multi-Agent SaaS for LinkedIn/Instagram carousels",
    version="0.1.0",
    root_path="/ContentEngine",
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
app.include_router(carousels.router, prefix="/api/v1")
app.include_router(generate.router, prefix="/api/v1")
