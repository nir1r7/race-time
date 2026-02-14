# RaceTime

A full-stack "live race day" F1 application that displays real-time race data, car positions, and leaderboards.

## Overview

RaceTime sources data from OpenF1 and provides:
- Live track view with car positions
- Real-time leaderboard (P1-P20)
- Near real-time updates via cached data

## Architecture

**Services:**
- `poller` (replicas=1): Background service that polls OpenF1 every 1-2 seconds and caches race snapshots in Redis
- `api` (replicas=3): FastAPI service that serves cached data to frontend clients
- `frontend`: React Vite SPA that displays race data
- `redis`: Shared cache for consistent API responses

**Data Flow:**
```
OpenF1 → poller → Redis → API (replicas) → frontend clients
```

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
4. Check health: http://localhost:8000/health

## Project Status

Phase 1 is complete. The following components are ready:
- [x] Snapshot schema (Pydantic models)
- [x] Redis snapshot caching
- [x] Live snapshot API endpoints (`/api/health`, `/api/live/snapshot`)
- [x] Dummy poller service (generates fake race data)
- [ ] React frontend with track visualization
- [ ] Kubernetes deployment configs
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Prometheus + Grafana monitoring

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
- **Frontend:** React, Vite
- **Infrastructure:** Docker, Kubernetes (kind), Traefik
- **Monitoring:** Prometheus, Grafana
- **CI/CD:** GitHub Actions, GHCR

