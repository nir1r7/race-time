#!/bin/bash
set -eu

echo "Starting RaceTime MQTT Worker..."
exec python -m app.mqtt_worker
