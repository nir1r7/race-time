#!/bin/bash

echo "Starting RaceTime in POLLER mode..."

# Build images
echo "Building images..."
docker build -t race-time/api:latest ./backend
docker build -t race-time/frontend:latest ./frontend

# Load into kind
echo "Loading images into kind..."
kind load docker-image race-time/api:latest --name racetime
kind load docker-image race-time/frontend:latest --name racetime

# Apply k8s manifests
echo "Applying Kubernetes manifests..."
kubectl apply -f k8s/

# Ensure correct ingest mode
echo "Switching to poller..."
kubectl scale deployment mqtt-worker --replicas=0
kubectl scale deployment poller --replicas=1

# Restart deployments
echo "Restarting deployments..."
kubectl rollout restart deployment api
kubectl rollout restart deployment poller
kubectl rollout restart deployment frontend

# Wait for rollout
echo "Waiting for pods..."
kubectl rollout status deployment/api
kubectl rollout status deployment/poller
kubectl rollout status deployment/frontend

echo "Poller mode is live"