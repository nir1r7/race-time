# RaceTime — Production Deployment Plan

## Goal
Deploy RaceTime to production so users can access it via a public domain with a stable, scalable backend.

---

## Architecture (Production)
Users → Domain → Load Balancer → Traefik → Frontend + API
↓
Redis
↑
mqtt-worker / poller

---

## Phase 1 — Containerization & Registry

- Build production Docker images:
  - `backend` (used by api + poller + mqtt-worker)
  - `frontend`
- Push images to **GHCR** with immutable tags (Git SHA)
- Update k8s manifests to use:
  - registry images (not local)
  - `imagePullPolicy: IfNotPresent`

---

## Phase 2 — Infrastructure Setup

### Recommended
- Use **DigitalOcean Kubernetes (DOKS)**
- Create cluster (2–3 nodes)
- Install Traefik ingress

---

## Phase 3 — Domain & DNS

- Purchase domain (Cloudflare recommended)
- Configure DNS:
  - `racetime.<domain>` → load balancer / server IP
- Enable HTTPS (via Traefik + Let’s Encrypt)

---

## Phase 4 — Deploy Services

Deploy via Kubernetes manifests:

- `frontend` (public)
- `api` (replicas=3)
- `redis` (internal)
- `poller` OR `mqtt-worker` (replicas=1)
- `prometheus` (internal)
- `grafana` (internal)
- `traefik` (ingress)

---

## Phase 5 — Configuration & Secrets

- Store credentials in **Kubernetes Secrets**:
  - OpenF1 username/password
- Store config in **ConfigMaps**:
  - Redis URL
  - MQTT host/port
- Remove all hardcoded secrets

---

## Phase 6 — Monitoring

- Prometheus scrapes:
  - `/api/metrics`
- Grafana dashboards:
  - request rate
  - p95 latency
  - SSE connections
  - snapshot age
  - Redis performance

Access:
- internal only (port-forward or protected route)

---

## Phase 7 — Deployment Workflow

1. Push code to `main`
2. GitHub Actions:
   - lint + test
   - build Docker images
   - push to GHCR
3. Update image tag in k8s
4. Apply manifests:
   ```bash
   kubectl apply -f k8s/


## Using k8s

### port forwards

kubectl port-forward svc/api 8000:8000
kubectl port-forward svc/frontend 5173:5173
kubectl port-forward svc/grafana 3000:3000
kubectl port-forward svc/prometheus 9090:9090

### applying changes + testing

kubectl apply -f k8s/

docker build -t race-time/api:latest ./backend
docker build -t race-time/api:latest ./frontend

kind load docker-image race-time/api:latest --name racetime
kind load docker-image race-time/frontend:latest --name racetime

kubectl rollout restart deployment api
kubectl rollout restart deployment mqtt-worker
kubectl rollout restart deployment poller
kubectl rollout restart deployment frontend

kubectl get pods --watch

### poller to mqtt worker
kubectl scale deployment poller --replicas=0
kubectl scale deployment mqtt-worker --replicas=1

### mqqt worker to poller
kubectl scale deployment mqtt-worker --replicas=0
kubectl scale deployment poller --replicas=1