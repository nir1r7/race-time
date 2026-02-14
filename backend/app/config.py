"""Application configuration from environment variables."""
import os

# Redis Configuration
# Docker: redis://redis:6379/0
# Local: redis://localhost:6379/0
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Poller Configuration
POLL_INTERVAL_SECONDS = float(os.getenv("POLL_INTERVAL_SECONDS", "1.0"))

# OpenF1 Configuration (Phase 2)
OPENF1_API_KEY = os.getenv("OPENF1_API_KEY", "")
