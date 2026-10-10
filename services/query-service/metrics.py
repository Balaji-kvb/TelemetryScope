"""
TelemetryScope — Query Service
Prometheus metrics definitions.
"""

from prometheus_client import Counter, Histogram, Gauge, Info

REQUEST_COUNT = Counter(
    "telemetryscope_query_requests_total",
    "Total query requests",
    ["method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "telemetryscope_query_request_duration_seconds",
    "Request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

DB_QUERY_DURATION = Histogram(
    "telemetryscope_query_db_duration_seconds",
    "Database query duration",
    ["query_type"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

DB_ERRORS = Counter(
    "telemetryscope_query_db_errors_total",
    "Database query errors",
    ["query_type"],
)

ROWS_RETURNED = Histogram(
    "telemetryscope_query_rows_returned",
    "Number of rows returned by query",
    ["query_type"],
    buckets=[0, 1, 10, 50, 100, 500, 1000],
)

SERVICE_INFO = Info(
    "telemetryscope_query",
    "Query service information",
)
