"""API routes for RaceTime."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app import redis_store

router = APIRouter(prefix="/api")


@router.get("/health")
async def health():
    """
    Health check endpoint.
    Returns Redis connectivity status.
    """
    redis_ok = await redis_store.ping()
    return {
        "status": "ok" if redis_ok else "degraded",
        "redis": "ok" if redis_ok else "down",
    }


@router.get("/live/snapshot")
async def live_snapshot():
    """
    Get the latest race snapshot.
    Returns 503 if no snapshot available yet.
    """
    snapshot = await redis_store.get_snapshot()
    if snapshot is None:
        return JSONResponse(
            status_code=503,
            content={"error": "no snapshot yet"},
        )
    return snapshot
