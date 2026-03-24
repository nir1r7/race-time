"""Tests for /api/live/stream SSE endpoint."""
import json
from unittest.mock import patch

import pytest
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


def test_live_stream_returns_event_stream(client):
    """SSE endpoint returns 200 with text/event-stream content-type."""
    async def _one_shot():
        yield "data: {}\n\n"

    with patch("app.routes.queue_generator", return_value=_one_shot()):
        response = client.get("/api/live/stream")
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]


def test_live_stream_sends_sse_events(client):
    """SSE events are formatted as 'data: <json>\\n\\n' and carry valid snapshot JSON."""
    mock_snapshot = {
        "timestamp": "2024-01-01T12:00:00Z",
        "positions": [],
        "leaderboard": [],
        "session": {"session_key": None, "name": "Race", "circuit": "Monaco"},
    }

    async def _one_shot():
        yield f"data: {json.dumps(mock_snapshot)}\n\n"

    with patch("app.routes.queue_generator", return_value=_one_shot()):
        response = client.get("/api/live/stream")
        first_line = response.text.splitlines()[0]
        assert first_line.startswith("data: ")
        payload = json.loads(first_line[len("data: "):])
        assert payload["timestamp"] == "2024-01-01T12:00:00Z"
