#!/bin/bash
set -eu

echo "Starting RaceTime Poller..."
exec python -m app.poller
