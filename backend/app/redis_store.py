"""Redis storage layer for race snapshots."""
import json
from typing import Optional

import redis.asyncio as redis

from app.config import REDIS_URL

# Redis key for the live snapshot
SNAPSHOT_KEY = "live:snapshot"

# Global client (initialized on first use)
_client: Optional[redis.Redis] = None


async def get_client() -> redis.Redis:
    """Get or create the Redis client."""
    global _client
    if _client is None:
        _client = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
    return _client


async def close_client() -> None:
    """Close the Redis client."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None


async def ping() -> bool:
    """Check Redis connectivity."""
    try:
        client = await get_client()
        await client.ping()
        return True
    except Exception:
        return False


async def set_snapshot(snapshot: dict) -> None:
    """Write snapshot to Redis."""
    client = await get_client()
    await client.set(SNAPSHOT_KEY, json.dumps(snapshot))


async def get_snapshot() -> Optional[dict]:
    """Read snapshot from Redis."""
    client = await get_client()
    data = await client.get(SNAPSHOT_KEY)
    if data is None:
        return None
    return json.loads(data)
