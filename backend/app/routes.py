"""API routes for RaceTime."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app import redis_store
from app.openf1 import fetch_next_race, get_token, fetch_drivers
from app.interpolator import fit_splines, interpolate_snapshot, MIN_SNAPSHOTS, WINDOW_SIZE

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

    if not redis_ok:
        return {"status": "degraded", "redis": "down", "heartbeat": "unknown"}


    heart_ok = await redis_store.get_heartbeat()

    latest = await redis_store.get_latest_snapshot()
    stale = False

    if latest:
        try:
            snap_time = datetime.fromisoformat(latest["timestamp"])
            age_seconds = (datetime.now(timezone.utc) - snap_time).total_seconds()
            stale = age_seconds > 20
        except (KeyError, ValueError):
            stale = True

    if stale:
        status = "stale"
    elif not heart_ok:
        status = "degraded"
    else:
        status = "ok"

    return {
        "status": status,
        "redis": "ok",
        "heartbeat": "ok" if heart_ok else "missing",
    }


async def queue_generator():
    QUEUE_DEPTH = 15
    OUTPUT_INTERVAL = 0.2428
    POLL_SLEEP = 0.5
    MAX_CATCHUP_S = QUEUE_DEPTH*OUTPUT_INTERVAL

    # wait for the data
    while True:
        window = await redis_store.get_last_n_snapshots(WINDOW_SIZE)
        if len(window) >= MIN_SNAPSHOTS:
            break
        await asyncio.sleep(POLL_SLEEP)

    # backfill the queue
    fit = fit_splines(window)
    trail_state: dict = {}

    backfill_start = max(fit.safe_end - (QUEUE_DEPTH-1)*OUTPUT_INTERVAL, fit.safe_start)
    
    t = backfill_start
    while t <= fit.safe_end + 1e-9:
        snap = interpolate_snapshot(fit, t, trail_state)
        yield f"data: {json.dumps(snap)}\n\n"
        t += OUTPUT_INTERVAL

    output_t = fit.safe_end + OUTPUT_INTERVAL
    last_seen_ts = window[0]["timestamp"]

    try:
        while True:
            await asyncio.sleep(OUTPUT_INTERVAL)

            # has a new snapshot arrived?
            latest = await redis_store.get_latest_snapshot()
            if latest and latest["timestamp"] != last_seen_ts:
                last_seen_ts = latest["timestamp"]
                new_window = await redis_store.get_last_n_snapshots(WINDOW_SIZE)
                
                if len(new_window) >= MIN_SNAPSHOTS:
                    fit = fit_splines(new_window)

                # if output_t is too far behind skip ahead
                if fit.safe_end - output_t > MAX_CATCHUP_S:
                    output_t = fit.safe_end - MAX_CATCHUP_S

            # stall if output is caught up to safe boundary
            if output_t > fit.safe_end:
                continue
            
            snap = interpolate_snapshot(fit, output_t, trail_state)
            yield f"data: {json.dumps(snap)}\n\n"
            output_t += OUTPUT_INTERVAL

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