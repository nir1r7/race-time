# RaceTime

A full-stack live F1 race viewer. Shows real-time car positions on track, a leaderboard with gaps and tyre compounds, and a countdown to the next race when nothing is live.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, Python 3.11 |
| Frontend | React 19, TypeScript, Vite |
| Cache / queue | Redis 7 |
| Real-time transport | Server-Sent Events (SSE) |
| Data source (dev) | Dummy poller — circuit SVG path simulation |
| Data source (premium) | OpenF1 MQTT broker (`mqtt.openf1.org:8883`) |
| Infrastructure | Docker Compose, Kubernetes + Traefik |
| Monitoring | Prometheus, Grafana |
| CI/CD | GitHub Actions |

## How It Works

### Data Pipeline

```
[dev]     poller.py  ──── fake positions every 1.25s (22-driver 2026 grid, Monaco SVG path)
[premium] OpenF1 MQTT broker (v1/location, v1/intervals, v1/laps, v1/drivers, v1/sessions)
          mqtt_worker.py normalizes raw GPS → (x_norm, y_norm) via pre-computed circuit bounds
          rate-limited to 2 Hz before writing
                   │
                   ▼  LPUSH + LTRIM(14)  [pipeline'd]
           Redis  live:snapshots  (list, newest-first, max 15 entries)
                   │
                   ▼  read on each SSE tick (~0.24s)
           interpolator.py  (runs inside the API process)
           • Pulls latest 8 snapshots from Redis
           • Fits a hand-rolled natural cubic spline per driver (x and y independently)
           • Emits interpolated frames at 0.2428s intervals with a 1-snapshot lag
           • Accumulates a 6-point position trail per driver
                   │
                   ▼  text/event-stream
           GET /api/live/stream  (FastAPI StreamingResponse)
                   │
                   ▼  EventSource
           Browser  App.tsx
           • Buffers received frames in a local queue (target depth: 15)
           • Waits until queue is full before starting playback
           • Adaptive drain rate: 220–280ms per frame, adjusted by ±2ms per
             item of deviation from target depth → smooths jitter without drift
           • On tab-hide/show, trims queue to last 15 to avoid stale buildup
```

### Coordinate Normalization

**Dev mode:** `circuit_path.py` samples points from a circuit SVG, then maps a driver's lap-progress `t ∈ [0,1)` to `(x_norm, y_norm)`.

**Premium mode:** `circuit_bounds.py` reads pre-computed per-circuit scale/offset values from `data/bounds.json`. Raw GPS `(x, y)` from OpenF1 is mapped to `[0, 1]` using those bounds.

### Schedule & Countdown

On load, the frontend calls `/api/schedule`, which fetches the next race from the OpenF1 REST API (cached in Redis for 12 hours, not cached if `is_live`). When a race is live, the frontend opens the SSE stream immediately. Otherwise it shows a countdown and auto-transitions to live mode when the start time arrives.

### Driver Colours

`/api/drivers` fetches team colours from OpenF1 (cached in Redis for 12 hours). The frontend uses these to colour each driver's leaderboard row and track dot.

## Services

| Service | Description |
|---------|-------------|
| `api` (×3 replicas) | FastAPI. Runs the interpolator, serves SSE stream and REST endpoints. |
| `frontend` | React SPA. Track view + leaderboard + countdown. |
| `redis` | Snapshot queue, heartbeat, schedule and driver caches. |
| `poller` | Dev-only. Generates fake race data from a circuit SVG. |
| `mqtt-worker` | Premium-only. Connects to OpenF1 MQTT, assembles and flushes snapshots. |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/live/stream` | SSE stream of interpolated snapshots |
| `GET` | `/api/drivers` | Driver list with team name and team colour hex |
| `GET` | `/api/schedule` | Next race info: circuit, start time, session name, `is_live` flag |
| `GET` | `/api/health` | Redis status, heartbeat freshness, snapshot staleness |
| `GET` | `/api/metrics` | Prometheus metrics |

## Running Locally

**Prerequisites:** Docker and Docker Compose.

```bash
# Dev mode — starts redis, api, frontend, and the dummy poller
docker-compose --profile dev up

# Premium mode — starts redis, api, frontend, and the MQTT worker
# Requires OPENF1_USERNAME and OPENF1_PASSWORD in .env
docker-compose --profile premium up
```

> Running `docker-compose up` without a profile starts only `redis`, `api`, and `frontend`. No data will appear without either `--profile dev` or `--profile premium`.

- App: http://localhost:5173  
- API: http://localhost:8000  
- Health: http://localhost:8000/api/health

## Kubernetes

Manifests are in `k8s/`. Traefik handles ingress routing. Prometheus scrapes `/api/metrics`; Grafana dashboards are defined in `k8s/grafana.yaml`.

## Environment Variables

| Variable | Used by | Description |
|----------|---------|-------------|
| `REDIS_URL` | api, poller, mqtt-worker | Redis connection URL |
| `OPENF1_USERNAME` | api, mqtt-worker | OpenF1 account username |
| `OPENF1_PASSWORD` | api, mqtt-worker | OpenF1 account password |
| `MQTT_HOST` | mqtt-worker | MQTT broker host (default: `mqtt.openf1.org`) |
| `MQTT_PORT` | mqtt-worker | MQTT broker port (default: `8883`) |
| `POLL_INTERVAL_SECONDS` | poller | Snapshot generation interval (default: `1.25`) |
| `CIRCUIT_SVG_PATH` | poller | Path to circuit SVG for coordinate mapping |
