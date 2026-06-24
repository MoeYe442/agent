from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.dependencies import cleanup
from src.api.routes.events import router as events_router
from src.api.routes.evidence import router as evidence_router
from src.api.routes.reports import router as reports_router
from src.api.routes.tasks import router as tasks_router
from src.api.routes.tools import router as tools_router
from src.config import Settings
from src.utils.logging import get_logger, setup_logging

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging(level=settings.log_level)
    logger = get_logger("src.main")
    logger.info("server_starting")

    # Pre-initialize infrastructure
    try:
        from src.api.dependencies import get_llm, get_redis
        llm = get_llm()
        redis = await get_redis()
        logger.info("infrastructure_initialized")
    except Exception as exc:
        logger.warning("infrastructure_init_failed", error=str(exc))

    yield

    # Shutdown
    logger.info("server_shutting_down")
    await cleanup()
    logger.info("server_stopped")


app = FastAPI(
    title="CodeResearch Agent",
    version="0.1.0",
    description="Multi-agent research analysis platform for large code repositories",
    lifespan=lifespan,
)

# Register routes
app.include_router(tasks_router)
app.include_router(events_router)
app.include_router(reports_router)
app.include_router(evidence_router)
app.include_router(tools_router)


@app.get("/health")
async def health():
    """Health check with optional infrastructure status."""
    status = {"status": "ok"}
    try:
        from src.api.dependencies import get_redis
        redis = await get_redis()
        redis_ok = await redis.health_check()
        status["redis"] = "ok" if redis_ok else "unhealthy"
    except Exception:
        status["redis"] = "unavailable"
    return status
