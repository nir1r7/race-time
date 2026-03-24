"""Tests for /api/health endpoint."""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


def test_health_redis_ok(client):
    """Test health endpoint returns ok when Redis is connected, heartbeat is fresh, and data is recent."""
    from datetime import datetime, timezone

    mock_snapshot = {"timestamp": datetime.now(timezone.utc).isoformat(), "positions": []}
    with patch("app.routes.redis_store") as mock_redis:
        mock_redis.ping = AsyncMock(return_value=True)
        mock_redis.get_heartbeat = AsyncMock(return_value=True)
        mock_redis.get_latest_snapshot = AsyncMock(return_value=mock_snapshot)
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["redis"] == "ok"


def test_health_redis_down(client):
    """Test health endpoint returns degraded when Redis is down."""
    with patch("app.routes.redis_store") as mock_redis:
        mock_redis.ping = AsyncMock(return_value=False)
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["redis"] == "down"
