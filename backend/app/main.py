"""RaceTime FastAPI application."""
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app import redis_store
from app.metrics import http_request_duration_seconds, http_requests_total
from app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    yield
    # Cleanup on shutdown
    await redis_store.close_client()


app = FastAPI(title="RaceTime", lifespan=lifespan)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    if request.url.path == "/api/metrics":
        return await call_next(request)
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    endpoint = request.url.path
    http_requests_total.labels(
        method=request.method,
        endpoint=endpoint,
        status=str(response.status_code),
    ).inc()
    # SSE streams are long-lived — duration histogram is not meaningful for them
    if endpoint != "/api/live/stream":
        http_request_duration_seconds.labels(endpoint=endpoint).observe(duration)
    return response


# Include API routes
app.include_router(router)
