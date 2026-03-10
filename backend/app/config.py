"""Application configuration from environment variables."""
import os
import random as rand

# Redis Configuration
# Docker: redis://redis:6379/0
# Local: redis://localhost:6379/0
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Poller Configuration
# POLL_INTERVAL_SECONDS = float(os.getenv("POLL_INTERVAL_SECONDS", "1.25"))
POLL_INTERVAL_SECONDS = float(1.25 + rand.random()-0.5)

# Circuit SVG path for the dummy poller (arc-length parameterisation)
CIRCUIT_SVG_PATH = os.getenv("CIRCUIT_SVG_PATH", "")

# OpenF1 Configuration
OPENF1_USERNAME = os.getenv("OPENF1_USERNAME", "")
OPENF1_PASSWORD = os.getenv("OPENF1_PASSWORD", "")
MQTT_HOST = os.getenv("MQTT_HOST", "mqtt.openf1.org")
MQTT_PORT = int(os.getenv("MQTT_PORT", "8883"))