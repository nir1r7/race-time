"""Redis storage layer for race snapshots."""
import json
from typing import Optional

import redis.asyncio as redis

from app.config import REDIS_URL

# Redis key for the live snapshot
SNAPSHOT_KEY = "live:snapshots"

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

    # use a pipe in case you want multiple commands processed by redis at the same time
    async with client.pipeline() as pipe:
        pipe.lpush(SNAPSHOT_KEY, json.dumps(snapshot))
        pipe.ltrim(SNAPSHOT_KEY, 0, 4)
        await pipe.execute()


async def get_snapshot() -> Optional[dict]:
    """Read snapshot from Redis."""
    client = await get_client()

    data = await client.lindex(SNAPSHOT_KEY, 0)
    if data is None:
        return None
    return json.loads(data)

async def get_recent(n: int) -> list[dict]:
    """Fetch the n most recent snapshots."""
    client = await get_client()

    snapshots = await client.lrange(SNAPSHOT_KEY, 0, n-1)

    if not snapshots:
        return []
    
    return [json.loads(s) for s in snapshots]