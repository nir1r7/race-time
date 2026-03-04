# RaceTime

A full-stack "live race day" F1 application that displays real-time race data, car positions, and leaderboards.

## Overview

RaceTime sources data from [OpenF1](https://openf1.org) and provides:
- Live track view with car positions
- Real-time leaderboard (P1-P20)
- Near real-time updates via cached data

The app supports two ingest modes. During development and on the free OpenF1 tier, a **dummy poller** generates fake race data. With a premium (sponsor) OpenF1 subscription, a **stream worker** connects to OpenF1's MQTT broker for true real-time data during live sessions.

In both modes the downstream contract is identical: a single `live:snapshot` key in Redis, read by stateless API replicas and polled by the frontend.

## Architecture

### Services

- `api` (replicas=3): Stateless FastAPI service that reads cached snapshots from Redis and serves them to frontend clients
- `frontend`: React Vite SPA that polls the API and renders track visualization + leaderboard
- `redis`: Shared cache and source of truth for snapshot data

**Ingest (one of):**

- `poller` (replicas=1) — **Dummy / free tier**: Generates fake race data (or polls OpenF1 REST) every 1s and writes `live:snapshot` to Redis
- `stream-worker` (replicas=1) — **Premium tier**: Authenticates via OAuth2, subscribes to OpenF1 MQTT topics, assembles race state in memory, and flushes `live:snapshot` to Redis every 500ms. Writes a `live:heartbeat` key with short TTL on each healthy cycle.

### Data Flow

**Dummy / free tier:**
```
Dummy data (or OpenF1 REST) → poller → Redis → API (replicas=3) → frontend clients
```

**Premium tier:**
```
OpenF1 MQTT → stream-worker → Redis → API (replicas=3) → frontend clients
```

## Premium Architecture

When running with a premium OpenF1 subscription, the stream worker replaces the poller and follows this pipeline:

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

Every 500ms the worker merges in-memory state into one compact `live:snapshot` JSON and writes it to Redis. The snapshot contains only what the UI needs:
- `timestamp`
- `session`
- `positions`
- `leaderboard`

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

### Phase 2 — React frontend
- [x] Track visualization component
- [x] Leaderboard component
- [x] API polling integration
- [ ] Stale-data and no-active-session UI states

### Phase 3 — Kubernetes deployment
- [ ] K8s manifests for all services
- [ ] Traefik ingress routing

### Phase 4 — CI/CD pipeline
- [ ] GitHub Actions workflows
- [ ] Automated linting, testing, and Docker image builds
- [ ] GHCR push with semantic tagging

### Phase 5 — Monitoring
- [ ] Prometheus metrics collection
- [ ] Grafana dashboards

### Phase 6 — Premium OpenF1 integration
- [ ] Replace `poller.py` with `stream_worker.py`
- [ ] OAuth2 token manager (auth, refresh, backoff)
- [ ] REST bootstrap on startup
- [ ] MQTT ingest with reconnect logic
- [ ] `live:heartbeat` key with TTL
- [ ] Staleness and heartbeat checks in `/api/health`
- [ ] No-active-session handling

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
