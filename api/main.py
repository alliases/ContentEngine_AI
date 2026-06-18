# api/main.py

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from api.config import settings
from api.routers import auth, carousels, generate, tasks
from db.session import engine
from workers.broker import broker


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    logger.info("Starting up FastAPI and DB pool...")

    # Prevent recursion: start broker only if running via Uvicorn, not Taskiq worker
    if not broker.is_worker_process:
        await broker.startup()
        logger.info("Taskiq broker started successfully.")

    yield

    logger.info("Shutting down Taskiq broker and DB pool...")

    if not broker.is_worker_process:
        await broker.shutdown()

    try:
        await engine.dispose()
        logger.info("DB pool shut down successfully.")
    except Exception as e:
        logger.error(f"Error during DB pool shutdown: {e!s}")


app = FastAPI(
    title="ContentEngine AI",
    description="Multi-Agent SaaS for LinkedIn/Instagram carousels",
    version="0.1.0",
    root_path="/ContentEngine",
    lifespan=lifespan,
)

# Configure CORS dynamically from .env
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(carousels.router, prefix="/api/v1")
app.include_router(generate.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
