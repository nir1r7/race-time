"""Redis storage layer for race snapshots."""
import json
import time
from typing import Optional

import redis.asyncio as redis

from app.config import REDIS_URL
from app.metrics import redis_operation_duration_seconds, redis_operations_total

# Redis key for the live snapshot
SNAPSHOT_KEY = "live:snapshots"
SCHEDULE_KEY = "static:schedule"
DRIVERS_KEY = "static:drivers"
HEARTBEAT_KEY = "live:heartbeat"

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
    t0 = time.time()
    try:
        client = await get_client()
        await client.ping()
        return True
    except Exception:
        return False
    finally:
        redis_operations_total.labels(operation="ping").inc()
        redis_operation_duration_seconds.labels(operation="ping").observe(time.time() - t0)


async def clear_snapshots() -> None:
    """Delete all snapshots from Redis (called on poller startup to purge stale data)."""
    client = await get_client()
    await client.delete(SNAPSHOT_KEY)


async def set_snapshot(snapshot: dict) -> None:
    """Write snapshot to Redis."""
    client = await get_client()
    t0 = time.time()
    try:
        # use a pipe in case you want multiple commands processed by redis at the same time
        async with client.pipeline() as pipe:
            pipe.lpush(SNAPSHOT_KEY, json.dumps(snapshot))
            pipe.ltrim(SNAPSHOT_KEY, 0, 14)
            await pipe.execute()
    finally:
        redis_operations_total.labels(operation="set_snapshot").inc()
        redis_operation_duration_seconds.labels(operation="set_snapshot").observe(time.time() - t0)


async def get_latest_snapshot() -> Optional[dict]:
    """Read snapshot from Redis."""
    client = await get_client()
    t0 = time.time()
    try:
        data = await client.lindex(SNAPSHOT_KEY, 0)
        if data is None:
            return None
        return json.loads(data)
    finally:
        redis_operations_total.labels(operation="get_latest").inc()
        redis_operation_duration_seconds.labels(operation="get_latest").observe(time.time() - t0)

async def get_last_n_snapshots(n: int) -> list[dict]:
    """Fetch the n most recent snapshots."""
    client = await get_client()
    t0 = time.time()
    try:
        snapshots = await client.lrange(SNAPSHOT_KEY, 0, n-1)
        if not snapshots:
            return []
        return [json.loads(s) for s in snapshots]
    finally:
        redis_operations_total.labels(operation="get_last_n").inc()
        redis_operation_duration_seconds.labels(operation="get_last_n").observe(time.time() - t0)


async def get_schedule_cache() -> dict | None:
    client = await get_client()

    data = await client.get(SCHEDULE_KEY)
    if data is None:
        return None
    return json.loads(data)


async def set_schedule_cache(data: dict, ttl_seconds: int = 43200) -> None:
    client = await get_client()

    await client.set(SCHEDULE_KEY, json.dumps(data), ex=ttl_seconds)


async def get_drivers_cache() -> list | None:
    client = await get_client()

    data = await client.get(DRIVERS_KEY)
    if data is None:
        return None
    return json.loads(data)


async def set_drivers_cache(data: list, ttl_seconds: int = 43200) -> None:
    client = await get_client()

    await client.set(DRIVERS_KEY, json.dumps(data), ex=ttl_seconds)


async def get_heartbeat() -> bool:
    client = await get_client()

    data = await client.get(HEARTBEAT_KEY)
    return data is not None


async def set_heartbeat(ttl_seconds: int = 10) -> None:
    client = await get_client()
    await client.set(HEARTBEAT_KEY, "ok", ex=ttl_seconds)
