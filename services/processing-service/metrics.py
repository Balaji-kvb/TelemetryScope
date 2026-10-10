"""
TelemetryScope — Processing Service
Prometheus metrics definitions.
"""

from prometheus_client import Counter, Histogram, Gauge, Info

REQUEST_COUNT = Counter(
    "telemetryscope_processing_requests_total",
    "Total processing requests",
    ["method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "telemetryscope_processing_request_duration_seconds",
    "Request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

EVENTS_PROCESSED = Counter(
    "telemetryscope_processing_events_processed_total",
    "Total events processed and persisted",
    ["service", "severity"],
)

PROCESSING_DURATION = Histogram(
    "telemetryscope_processing_event_duration_seconds",
    "Event processing duration (normalization + persistence)",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
)

DB_OPERATION_DURATION = Histogram(
    "telemetryscope_processing_db_duration_seconds",
    "Database operation duration",
    ["operation"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

DB_ERRORS = Counter(
    "telemetryscope_processing_db_errors_total",
    "Database operation errors",
    ["operation"],
)

ERROR_GROUPS_UPDATED = Counter(
    "telemetryscope_processing_error_groups_updated_total",
    "Error groups created or updated",
)

ALERTS_EVALUATED = Counter(
    "telemetryscope_processing_alerts_evaluated_total",
    "Alert rules evaluated",
    ["rule"],
)

ALERTS_TRIGGERED = Counter(
    "telemetryscope_processing_alerts_triggered_total",
    "Alerts triggered",
    ["rule", "severity"],
)

SERVICE_INFO = Info(
    "telemetryscope_processing",
    "Processing service information",
)
