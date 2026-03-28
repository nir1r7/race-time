# RaceTime

A full-stack "live race day" F1 application that displays real-time race data, car positions, and leaderboards.

## Overview

RaceTime sources data from [OpenF1](https://openf1.org) and provides:
- Live track view with car positions and movement trails
- Real-time leaderboard (P1-P20) with gap, team, and tyre compound
- Smooth car movement via a client-side adaptive playback buffer
- Countdown screen to the next scheduled race

The app supports two ingest modes. During development, a **dummy poller** generates fake race data using the full 22-driver 2026 season grid. With a premium (sponsor) OpenF1 subscription, an **MQTT worker** connects to OpenF1's MQTT broker for true real-time GPS data.

In both modes the downstream contract is identical: a Redis queue of the 15 most recent snapshots, consumed by stateless API replicas, interpolated server-side for smooth animation, and streamed to the browser via SSE.

## Architecture

### Services

- `api` (replicas=3): Stateless FastAPI service. Reads snapshots from Redis, runs them through a spline interpolation layer, and streams interpolated frames to connected browsers via SSE (`/api/live/stream`). Also exposes `/api/health`, `/api/drivers`, and `/api/schedule`. Polls Redis on each SSE tick.
- `frontend`: React Vite SPA. On load, fetches driver colours (`/api/drivers`) and next race info (`/api/schedule`). Before a live session, shows a countdown to the next race. When live, opens an `EventSource` connection to the SSE endpoint, buffers received snapshots in an adaptive local playback queue, and renders them oldest-first for smooth car movement. Supports 22 circuits (full 2026 calendar).
- `redis`: Shared cache and source of truth. Stores a rolling queue of the **15 most recent snapshots** (`LPUSH` + `LTRIM`). Acts as the handoff point between the ingest worker and the API, and provides reconnection resilience — new clients receive the last 15 snapshots immediately on connect. Also caches the schedule (`static:schedule`, 12h TTL) and a heartbeat key (`live:heartbeat`, 10s TTL).

**Ingest (one of):**

- `poller` (replicas=1) — **Dev mode** (`--profile dev`): Generates fake race data for the 22-driver 2026 F1 grid every 1.25s and pushes to the Redis snapshot queue. Reads a circuit SVG to map lap progress to normalized coordinates; includes a 6-position trail per driver.
- `mqtt-worker` (replicas=1) — **Premium tier** (`--profile premium`): Subscribes to OpenF1's MQTT broker, assembles race state from GPS location messages, normalizes coordinates using pre-built circuit bounds, and flushes a snapshot to Redis at up to 2 Hz. Enabled via `docker-compose --profile premium up`.

**Interpolator:**

- `interpolator.py` — Lives inside the API process. Sits between the Redis snapshot queue and the SSE output. Buffers a rolling window of 8 snapshots and fits a natural cubic spline per driver using numpy. Emits interpolated frames at ~0.24s intervals (~4 fps effective output), smoothing the ~2 Hz ingest rate into fluid browser animation.

**REST Client:**

- `openf1.py` — Thin async HTTP client (httpx) used by `mqtt_worker.py` during its REST bootstrap phase to fetch the current session, drivers, positions, and laps from the OpenF1 REST API before MQTT deltas start arriving.

### Data Flow

```
DATA SOURCE
  [dev]     dummy poller  →  fake positions every 1.25s  (22 drivers, trail included)
  [premium] OpenF1 MQTT broker (mqtt.openf1.org:8883)
            ~3.7 Hz GPS per car  →  mqtt_worker.py normalizes & assembles
                      │ flush capped at 2 Hz (SNAPSHOT_INTERVAL = 0.5s)
                      ▼ LPUSH + LTRIM
              ┌──────────────
              │     REDIS
              │  live:snapshots  (list, last 15)
              │  live:heartbeat  (string, 10s TTL)
              │  static:schedule (string, 12h TTL)
              │  • Decouples ingest from API
              │  • Survives API restarts
              │  • Single source of truth for
              │    all API replicas
              └──────────────
                      │ read on each SSE tick
                      ▼
              interpolator.py  (inside API process)
              • Buffers 8-snapshot rolling window
              • Fits natural cubic spline per driver
              • Emits frames at ~0.24s intervals
                      │
                      ▼
              FastAPI  GET /api/live/stream
              (SSE — long-lived HTTP, server pushes)
                      │ text/event-stream
                      ▼
              Browser  EventSource
              • Receives interpolated snapshots
              • Adaptive playback queue (target depth: 15)
              • Adjusts frame rate 220–280ms to drain queue
              • Renders oldest-first → smooth animation
              • Auto-reconnects on drop
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Redis connectivity, heartbeat freshness, snapshot staleness → `{status, redis, heartbeat}` |
| `GET` | `/api/live/stream` | SSE stream of interpolated snapshots (`text/event-stream`) |
| `GET` | `/api/drivers` | Current driver list with team name and colour |
| `GET` | `/api/schedule` | Next race info: circuit, date, session name, is_live flag |

**Premium switchover:**
```bash
docker-compose --profile premium up
```
Everything downstream (Redis → interpolator → SSE → browser) is untouched.

## Premium Architecture

When running with a premium OpenF1 subscription, the `mqtt-worker` replaces the dummy poller and follows this pipeline:

### 1. Authentication

- Reads `OPENF1_USERNAME` and `OPENF1_PASSWORD` from environment / secrets
- POSTs via `openf1.py` to `https://api.openf1.org/token` to obtain an access token and expiry (typically 3600s)
- Refreshes at ~55 minutes; retries with exponential backoff on failure; falls back to full re-auth on token rejection

### 2. REST Bootstrap

On startup (and on restart), the worker performs a one-time REST fetch via `openf1.py` of:
- Current session metadata
- Driver list
- Latest positions and lap data

This ensures the in-memory state has a valid base before MQTT deltas arrive.

### 3. MQTT Ingest

- Connects to `mqtt.openf1.org:8883` (MQTT over TLS)
- Authenticates with `OPENF1_USERNAME` as username and the OAuth2 token as MQTT password
- Subscribes to live topics: `v1/location`, `v1/laps`, `v1/sessions`, `v1/drivers`
- Reconnects with exponential backoff and re-subscribes on every reconnect

### 4. In-Memory State Assembly

The worker maintains a current race state map:
- Latest position per driver (from `v1/location`)
- Latest lap/position data per driver (from `v1/laps`)
- Current session metadata (from `v1/sessions`)
- Driver metadata (from `v1/drivers`)

### 5. Snapshot Flush

On `v1/location` messages, the worker assembles a `Snapshot` and pushes it to the Redis list (`LPUSH live:snapshots` + `LTRIM` to keep last 15). Flushes are **rate-limited to 2 Hz** (0.5s minimum interval). The snapshot contains:
- `timestamp`
- `session` (circuit, name, session_key)
- `positions` — per driver: `driver_number`, `driver_code`, `x_norm`, `y_norm`, plus a `trail` of the last 6 normalized positions (oldest → newest)
- `leaderboard` — position, gap, team, tyre compound per driver

### 6. Health Signals

- Writes `live:heartbeat` to Redis with a 10s TTL on each healthy flush cycle
- `/api/health` checks Redis connectivity, heartbeat freshness, and snapshot staleness → `{status: "ok"|"stale"|"degraded", redis: "ok"|"down", heartbeat: "ok"|"missing"}`
- During periods with no active F1 session, the worker writes an explicit "no active session" status so the frontend can display an appropriate state rather than stale data

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Node.js (for frontend development)

### Local Development

1. Clone the repository
2. Start the services with the dev ingest worker:
   ```bash
   docker-compose --profile dev up
   ```
   > The default profile (`docker-compose up`) starts only `redis`, `api`, and `frontend` — no data will be generated without `--profile dev`.
3. Access the app at http://localhost:5173
4. Access the API at http://localhost:8000
5. Check health: http://localhost:8000/api/health

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
- [x] Update dummy poller to populate trail data
- [x] Docker Compose `premium` profile for `mqtt-worker` service

### Phase 4 — Kubernetes deployment
- [x] K8s manifests for all services
- [x] Traefik ingress routing

### Phase 5 — CI/CD pipeline
- [x] GitHub Actions workflows
- [x] Automated linting, testing, and Docker image builds
- [ ] GHCR push with semantic tagging

### Phase 6 — Monitoring
- [x] Prometheus metrics collection
- [x] Grafana dashboards

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
   # Health check (should return {"status":"ok","redis":"ok","heartbeat":"ok"})
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
- **Frontend:** React 19, Vite, TypeScript
- **Data Ingest:** MQTT (aiomqtt) for premium, circuit-path simulation for dev
- **Infrastructure:** Docker, Kubernetes (kind), Traefik
- **Monitoring:** Prometheus, Grafana
- **CI/CD:** GitHub Actions, GHCR
