"""RaceTime FastAPI application."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import redis_store
from app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    yield
    # Cleanup on shutdown
    await redis_store.close_client()


app = FastAPI(title="RaceTime", lifespan=lifespan)

# Include API routes
app.include_router(router)
