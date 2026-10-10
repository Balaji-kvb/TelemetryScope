"""
TelemetryScope — Ingestion Service
Prometheus metrics definitions.
"""

from prometheus_client import Counter, Histogram, Gauge, Info


# Request metrics
REQUEST_COUNT = Counter(
    "telemetryscope_ingestion_requests_total",
    "Total ingestion requests",
    ["method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "telemetryscope_ingestion_request_duration_seconds",
    "Request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

# Telemetry-specific metrics
EVENTS_ACCEPTED = Counter(
    "telemetryscope_ingestion_events_accepted_total",
    "Total accepted telemetry events",
    ["service", "severity"],
)

EVENTS_REJECTED = Counter(
    "telemetryscope_ingestion_events_rejected_total",
    "Total rejected telemetry events",
    ["reason"],
)

EVENTS_FORWARDED = Counter(
    "telemetryscope_ingestion_events_forwarded_total",
    "Total events forwarded to Processing Service",
)

FORWARD_ERRORS = Counter(
    "telemetryscope_ingestion_forward_errors_total",
    "Errors forwarding to Processing Service",
)

FORWARD_LATENCY = Histogram(
    "telemetryscope_ingestion_forward_duration_seconds",
    "Latency of forwarding to Processing Service",
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

# Batch metrics
BATCH_SIZE = Histogram(
    "telemetryscope_ingestion_batch_size",
    "Number of events per batch request",
    buckets=[1, 5, 10, 25, 50, 100],
)

# Service info
SERVICE_INFO = Info(
    "telemetryscope_ingestion",
    "Ingestion service information",
)
