"""Prometheus metrics definitions for RaceTime."""
from prometheus_client import Counter, Gauge, Histogram

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

active_sse_connections = Gauge(
    "active_sse_connections",
    "Number of active SSE stream connections",
)

snapshots_generated_total = Counter(
    "snapshots_generated_total",
    "Total snapshots written to Redis by the poller",
)

snapshot_generation_duration_seconds = Histogram(
    "snapshot_generation_duration_seconds",
    "Time to generate and write one snapshot in seconds",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)

redis_operations_total = Counter(
    "redis_operations_total",
    "Total Redis operations",
    ["operation"],
)

redis_operation_duration_seconds = Histogram(
    "redis_operation_duration_seconds",
    "Redis operation latency in seconds",
    ["operation"],
    buckets=[0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25],
)
