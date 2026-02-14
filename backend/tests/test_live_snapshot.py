"""Tests for /api/live/snapshot endpoint."""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


def test_live_snapshot_no_data(client):
    """Test snapshot endpoint returns 503 when no data exists."""
    with patch("app.routes.redis_store") as mock_redis:
        mock_redis.get_snapshot = AsyncMock(return_value=None)
        response = client.get("/api/live/snapshot")
        assert response.status_code == 503
        data = response.json()
        assert data["error"] == "no snapshot yet"


def test_live_snapshot_with_data(client):
    """Test snapshot endpoint returns data when available."""
    mock_snapshot = {
        "timestamp": "2024-01-01T12:00:00Z",
        "positions": [
            {"driver_number": 1, "driver_code": "VER", "x_norm": 0.5, "y_norm": 0.5}
        ],
        "leaderboard": [
            {"position": 1, "driver_number": 1, "driver_code": "VER"}
        ],
        "session": {"session_key": None, "name": "Race", "circuit": "Monaco"}
    }
    with patch("app.routes.redis_store") as mock_redis:
        mock_redis.get_snapshot = AsyncMock(return_value=mock_snapshot)
        response = client.get("/api/live/snapshot")
        assert response.status_code == 200
        data = response.json()
        assert data["timestamp"] == "2024-01-01T12:00:00Z"
        assert len(data["positions"]) == 1
        assert data["positions"][0]["driver_code"] == "VER"
        assert len(data["leaderboard"]) == 1
