# RaceTime

A full-stack "live race day" F1 application that displays real-time race data, car positions, and leaderboards.

## Overview

RaceTime sources data from [OpenF1](https://openf1.org) and provides:
- Live track view with car positions
- Real-time leaderboard (P1-P20)
- Smooth car movement via a client-side playback buffer

The app supports two ingest modes. During development, a **dummy poller** generates fake race data. With a premium (sponsor) OpenF1 subscription, an **MQTT worker** connects to OpenF1's MQTT broker for true real-time GPS data at ~3.7 Hz per car.

In both modes the downstream contract is identical: a Redis queue of the 5 most recent snapshots, consumed by stateless API replicas and streamed to the browser via SSE.

## Architecture

### Services

- `api` (replicas=3): Stateless FastAPI service. Polls Redis every 100ms and streams snapshots to connected browsers via SSE (`/api/live/stream`).
- `frontend`: React Vite SPA. Opens an `EventSource` connection to the SSE endpoint, buffers received snapshots in a local playback queue, and renders them oldest-first for smooth car movement.
- `redis`: Shared cache and source of truth. Stores a rolling queue of the **5 most recent snapshots** (`LPUSH` + `LTRIM`). Acts as the handoff point between the ingest worker and the API, and provides reconnection resilience — new clients receive the last 5 snapshots immediately on connect.

**Ingest (one of):**

- `poller` (replicas=1) — **Dev / dummy**: Generates fake race data every 1s and pushes to the Redis snapshot queue.
- `mqtt-worker` (replicas=1) — **Premium tier**: Subscribes to OpenF1's MQTT broker, assembles race state from GPS location messages, normalizes coordinates using pre-built circuit bounds, and flushes a snapshot to Redis on every location update (~3.7 Hz). Enabled via `docker-compose --profile premium`.

### Data Flow

```
DATA SOURCE
  [dev]     dummy poller  →  fake positions every 1s
  [premium] OpenF1 MQTT broker (mqtt.openf1.org:8883)
            ~3.7 Hz GPS per car  →  mqtt_worker.py normalizes & assembles
                      │
                      ▼ LPUSH + LTRIM
              ┌──────────────
              │     REDIS    
              │  live:snapshots  (list, last 5)       
              │  • Decouples ingest from API          
              │  • Survives API restarts              
              │  • Single source of truth for         
              │    all API replicas                   
              └──────────────
                      │ poll every 100ms, push on change
                      ▼
              FastAPI  GET /api/live/stream
              (SSE — long-lived HTTP, server pushes)
                      │ text/event-stream
                      ▼
              Browser  EventSource
              • Receives individual snapshots
              • Buffers last N in playback queue
              • Renders oldest-first → smooth animation
              • Auto-reconnects on drop; receives last 5 immediately
```

**Premium switchover:**
```bash
MQTT_USERNAME=x MQTT_PASSWORD=y docker-compose --profile premium up
docker-compose stop poller
```
Everything downstream (Redis → SSE → browser) is untouched.

## Premium Architecture

When running with a premium OpenF1 subscription, the `mqtt-worker` replaces the dummy poller and follows this pipeline:

### 1. Authentication

- Reads `OPENF1_USERNAME` and `OPENF1_PASSWORD` from secrets
- POSTs to `https://api.openf1.org/token` to obtain an access token and expiry (typically 3600s)
- Refreshes at ~55 minutes; retries with exponential backoff on failure; falls back to full re-auth on token rejection

### 2. REST Bootstrap

On startup (and on restart), the worker performs a one-time REST fetch of:
- Current session metadata
- Driver list
- Latest positions and lap data

This ensures the in-memory state has a valid base before MQTT deltas arrive.

### 3. MQTT Ingest

- Connects to `mqtt.openf1.org:8883` (MQTT over TLS)
- Authenticates with the OAuth2 token as the MQTT password
- Subscribes to live topics: `v1/location`, `v1/laps`, `v1/sessions`, `v1/drivers`
- Reconnects with exponential backoff and re-subscribes on every reconnect

### 4. In-Memory State Assembly

The worker maintains a current race state map:
- Latest position per driver (from `v1/location`)
- Latest lap/position data per driver (from `v1/laps`)
- Current session metadata (from `v1/sessions`)
- Driver metadata (from `v1/drivers`)

MQTT messages include `_id` and `_key` fields for ordering and deduplication.

### 5. Snapshot Flush

On every `v1/location` message (~3.7 Hz), the worker assembles a `Snapshot` and pushes it to the Redis list (`LPUSH live:snapshots` + `LTRIM` to keep last 5). The snapshot contains:
- `timestamp`
- `session` (circuit, name, session_key)
- `positions` — per driver: `driver_number`, `driver_code`, `x_norm`, `y_norm`, plus a `trail` of the last 6 normalized positions (oldest → newest) for smooth frontend animation
- `leaderboard` — position, gap, team, tyre compound per driver

### 6. Health Signals

- Writes `live:heartbeat` to Redis with a short TTL on each healthy flush cycle
- `/api/health` checks Redis connectivity, heartbeat freshness, and snapshot staleness
- During periods with no active F1 session, the worker writes an explicit "no active session" status so the frontend can display an appropriate state rather than stale data

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Node.js (for frontend development)

### Local Development

1. Clone the repository
2. Start the services:
   ```bash
   docker-compose up
   ```
3. Access the API at http://localhost:8000
4. Check health: http://localhost:8000/api/health

## Roadmap

### Phase 1 — Backend foundation (complete)
- [x] Snapshot schema (Pydantic models)
- [x] Redis snapshot caching
- [x] Live snapshot API endpoints (`/api/health`, `/api/live/snapshot`)
- [x] Dummy poller service (generates fake race data)

### Phase 2 — React frontend (complete)
- [x] Track visualization component
- [x] Leaderboard component
- [x] API polling integration

### Phase 3 — Pre-premium architecture
- [x] Add `trail` field to `DriverPosition` schema (backend + frontend types)
- [x] `circuit_bounds.py` — GPS normalization using `scripts/output/bounds.json`
- [x] Redis snapshot queue (LPUSH + LTRIM, last 5) replacing single key
- [x] SSE endpoint `GET /api/live/stream` replacing polling
- [x] Frontend: swap `setInterval` → `EventSource` with client-side playback queue
- [x] `mqtt_worker.py` — full MQTT worker shell (ready for credentials)
- [ ] Update dummy poller to populate trail data
- [x] Docker Compose `premium` profile for `mqtt-worker` service

### Phase 4 — Kubernetes deployment
- [x] K8s manifests for all services
- [x] Traefik ingress routing

### Phase 5 — CI/CD pipeline
- [ ] GitHub Actions workflows
- [ ] Automated linting, testing, and Docker image builds
- [ ] GHCR push with semantic tagging

### Phase 6 — Monitoring
- [ ] Prometheus metrics collection
- [ ] Grafana dashboards

### Phase 7 — Premium OpenF1 (mqtt-worker)
- [x] Wire MQTT credentials into `mqtt_worker.py`
- [x] REST bootstrap on startup (session, drivers, positions)
- [x] MQTT ingest with reconnect logic
- [x] `live:heartbeat` key with TTL
- [x] Staleness and heartbeat checks in `/api/health`
- [x] No-active-session handling

## Phase 1 Manual Verification

### Prerequisites
- Redis running locally on `localhost:6379`
- Python 3.10+ with dependencies installed

### Quick Test

1. **Start Redis** (if not running):
   ```bash
   docker run -d -p 6379:6379 redis:7-alpine
   ```

2. **Install dependencies**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Start the API server**:
   ```bash
   cd backend
   PYTHONPATH=. python -m uvicorn app.main:app --port 8000
   ```

4. **Start the poller** (in a new terminal):
   ```bash
   cd backend
   PYTHONPATH=. python -m app.poller
   ```

5. **Verify endpoints**:
   ```bash
   # Health check (should return {"status":"ok","redis":"ok"})
   curl http://localhost:8000/api/health

   # Live snapshot (should return race data JSON)
   curl http://localhost:8000/api/live/snapshot
   ```

6. **Run tests**:
   ```bash
   cd backend
   PYTHONPATH=. python -m pytest tests/ -v
   ```

## Tech Stack

- **Backend:** FastAPI, Python 3.11, Redis
- **Frontend:** React, Vite, TypeScript
- **Data Ingest:** MQTT (aiomqtt) for premium, REST polling for free tier
- **Infrastructure:** Docker, Kubernetes (kind), Traefik
- **Monitoring:** Prometheus, Grafana
- **CI/CD:** GitHub Actions, GHCR
