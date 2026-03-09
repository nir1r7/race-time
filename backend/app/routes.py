"""API routes for RaceTime."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app import redis_store
from app.openf1 import fetch_next_race, get_token, fetch_drivers

import httpx
import json
import asyncio
from datetime import datetime, timezone, timedelta


router = APIRouter(prefix="/api")

_drivers_cache: list[dict] | None = None
_token: str | None = None
_token_expiry: datetime | None = None


async def _get_api_token() -> str:
    global _token, _token_expiry
    now = datetime.now(timezone.utc)
    if _token is None or _token_expiry is None or now >= _token_expiry - timedelta(seconds=60):
        _token, _token_expiry = await get_token()
    return _token


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


async def queue_generator():
    # backfill immediately with last 10 snapshots
    recent = await redis_store.get_last_n_snapshots(15)
    
    # oldest first
    for snapshot in reversed(recent):
        yield f"data: {json.dumps(snapshot)}\n\n"

    last_seen_timestamp = recent[0]["timestamp"] if recent else None

    try:
        while True:
            await asyncio.sleep(0.1) # 100ms

            latest = await redis_store.get_latest_snapshot()
            
            # nothing or nothing new
            if latest is None or latest["timestamp"] == last_seen_timestamp:
                continue

            last_seen_timestamp = latest["timestamp"]
            yield f"data: {json.dumps(latest)}\n\n"
    except asyncio.CancelledError:
        pass


@router.get("/live/stream")
async def live_stream(request: Request):
    last_id = request.headers.get("last-event-id")

    return StreamingResponse(
        queue_generator(),
        media_type = "text/event-stream",
        headers = {
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/drivers")
async def drivers():
    global _drivers_cache

    if _drivers_cache is not None:
        return _drivers_cache

    try:
        token = await _get_api_token()
        all_drivers = await fetch_drivers("latest", token)
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        return JSONResponse(status_code=503, content={"detail": "OpenF1 API unavailable", "error": str(e)})

    _drivers_cache = [
        {
            "driver_code": driver["name_acronym"],
            "team_name":   driver["team_name"],
            "team_colour": driver["team_colour"],
        }
        for driver in all_drivers if driver.get("name_acronym") and driver.get("team_colour")
    ]

    return _drivers_cache


@router.get("/schedule")
async def schedule():
    cached = await redis_store.get_schedule_cache()

    if cached is not None:
        return cached

    try:
        token = await _get_api_token()
        next_race = await fetch_next_race(token)
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        return JSONResponse(status_code=503, content={"detail": "OpenF1 API unavailable", "error": str(e)})

    if next_race is None:
        return None

    # Don't cache live sessions, state changes every few minutes
    if not next_race.get("is_live"):
        await redis_store.set_schedule_cache(next_race)
    return next_race