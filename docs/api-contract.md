# TelemetryScope API Contract

## Overview

This document defines all HTTP endpoints across TelemetryScope services, including request/response schemas, status codes, and behavioral contracts. All services follow consistent patterns for health, metrics, versioning, and error responses.

---

## Common Conventions

### Base URLs (Local Development)

| Service | Base URL |
|---------|----------|
| Ingestion Service | `http://localhost:8001` |
| Processing Service | `http://localhost:8002` |
| Query & Control Service | `http://localhost:8003` |
| Demo Workload | `http://localhost:8080` |

### Standard Response Envelope

All API responses use a consistent envelope:

```json
{
  "status": "success" | "error",
  "data": { ... },
  "meta": {
    "request_id": "req-a1b2c3d4",
    "timestamp": "2024-01-15T10:30:00.000Z"
  }
}
```

### Error Response

```json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable error description",
    "details": [ ... ]
  },
  "meta": {
    "request_id": "req-a1b2c3d4",
    "timestamp": "2024-01-15T10:30:00.000Z"
  }
}
```

### Standard Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid payload, missing required fields |
| `PAYLOAD_TOO_LARGE` | 413 | Request body exceeds size limit |
| `RATE_LIMITED` | 429 | Too many requests |
| `NOT_FOUND` | 404 | Resource not found |
| `INTERNAL_ERROR` | 500 | Unexpected server error |
| `SERVICE_UNAVAILABLE` | 503 | Dependency unavailable (readiness failure) |

### Pagination

All list endpoints support:

```
?page=1&page_size=50
```

Response includes:

```json
{
  "meta": {
    "pagination": {
      "page": 1,
      "page_size": 50,
      "total_items": 1234,
      "total_pages": 25,
      "has_next": true,
      "has_prev": false
    }
  }
}
```

Default `page_size`: 50. Max `page_size`: 200.

---

## Operational Endpoints (All Services)

### GET /health

Liveness check. Returns 200 if the process is alive.

**Response 200**:
```json
{
  "status": "healthy",
  "service": "telemetryscope-ingestion",
  "uptime_seconds": 3600
}
```

**Does NOT check dependencies** — this is a liveness probe.

---

### GET /ready

Readiness check. Returns 200 only if the service is ready to accept traffic.

**Response 200**:
```json
{
  "status": "ready",
  "service": "telemetryscope-ingestion",
  "checks": {
    "processing_service": "reachable",
    "database": "connected"
  }
}
```

**Response 503** (not ready):
```json
{
  "status": "not_ready",
  "service": "telemetryscope-ingestion",
  "checks": {
    "processing_service": "unreachable"
  }
}
```

Each service checks its critical dependencies:
- **Ingestion**: Processing Service reachability
- **Processing**: PostgreSQL connectivity
- **Query**: PostgreSQL connectivity

---

### GET /metrics

Prometheus-format metrics. Returns `text/plain` with Prometheus exposition format.

---

### GET /version

**Response 200**:
```json
{
  "service": "telemetryscope-ingestion",
  "version": "1.0.0",
  "commit_sha": "abc1234def",
  "environment": "production-demo",
  "build_time": "2024-01-15T10:00:00Z"
}
```

---

## Ingestion Service Endpoints

### POST /api/v1/logs

Accept a single telemetry event.

**Request Headers**:
```
Content-Type: application/json
X-Request-ID: req-a1b2c3d4  (optional, generated if absent)
```

**Request Body**:
```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "service": "demo-api",
  "environment": "production",
  "severity": "ERROR",
  "message": "Database connection timeout after 5000ms",
  "request_id": "req-a1b2c3d4",
  "trace_id": "trace-x1y2z3",
  "endpoint": "/api/users/123",
  "status_code": 500,
  "duration_ms": 5023,
  "metadata": {
    "exception_type": "ConnectionTimeout",
    "database": "users_db",
    "retry_count": 3
  }
}
```

**Required Fields**: `service`, `message`

**Optional Fields**: All others. Defaults applied:
- `timestamp`: current UTC time
- `severity`: `INFO`
- `environment`: `development`
- `request_id`: auto-generated `req-{hex8}`

**Validation Rules**:
| Field | Rule |
|-------|------|
| `service` | Required, 1-100 chars, alphanumeric + hyphens |
| `message` | Required, 1-5000 chars |
| `severity` | Must be valid level (see schema) |
| `timestamp` | ISO 8601 format if provided |
| `status_code` | Integer 100-599 if provided |
| `duration_ms` | Non-negative number if provided |
| `metadata` | Object, max 10 keys, max 1KB total |
| Total payload | Max 64KB |

**Response 202** (Accepted):
```json
{
  "status": "success",
  "data": {
    "request_id": "req-a1b2c3d4",
    "accepted": true
  },
  "meta": {
    "request_id": "req-a1b2c3d4",
    "timestamp": "2024-01-15T10:30:00.123Z"
  }
}
```

**Response 400** (Validation Error):
```json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Payload validation failed",
    "details": [
      { "field": "service", "error": "Required field missing" },
      { "field": "severity", "error": "Invalid severity level: WARN. Use WARNING" }
    ]
  }
}
```

**Response 413** (Payload Too Large):
```json
{
  "status": "error",
  "error": {
    "code": "PAYLOAD_TOO_LARGE",
    "message": "Request body exceeds 64KB limit"
  }
}
```

**Response 429** (Rate Limited):
```json
{
  "status": "error",
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many requests. Retry after 1 second"
  }
}
```

---

### POST /api/v1/logs/batch

Accept multiple telemetry events.

**Request Body**:
```json
{
  "events": [
    { "service": "demo-api", "message": "Request processed", ... },
    { "service": "demo-api", "message": "Cache miss", ... }
  ]
}
```

**Validation**:
- Max 100 events per batch
- Total batch payload max 1MB
- Each event validated individually
- Partial acceptance: valid events accepted, invalid events listed in response

**Response 202**:
```json
{
  "status": "success",
  "data": {
    "accepted": 8,
    "rejected": 2,
    "errors": [
      { "index": 3, "error": "Missing required field: service" },
      { "index": 7, "error": "Invalid severity: WARN" }
    ]
  }
}
```

---

## Processing Service Endpoints

### POST /internal/process

**Internal only** — not exposed through Ingress.

**Request Body**:
```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "received_at": "2024-01-15T10:30:00.123Z",
  "service": "demo-api",
  "environment": "production",
  "severity": "ERROR",
  "message": "Database connection timeout after 5000ms",
  "request_id": "req-a1b2c3d4",
  "trace_id": "trace-x1y2z3",
  "endpoint": "/api/users/123",
  "status_code": 500,
  "duration_ms": 5023,
  "metadata": {
    "exception_type": "ConnectionTimeout"
  }
}
```

**Response 200**:
```json
{
  "status": "success",
  "data": {
    "id": "evt-uuid-1234",
    "fingerprint": "fp-sha256-hex-16",
    "processed": true
  }
}
```

**Response 503** (Database unavailable):
```json
{
  "status": "error",
  "error": {
    "code": "SERVICE_UNAVAILABLE",
    "message": "Database connection unavailable"
  }
}
```

---

## Query & Control Service Endpoints

### GET /api/v1/logs

Search and list log events.

**Query Parameters**:

| Param | Type | Description |
|-------|------|-------------|
| `page` | int | Page number (default: 1) |
| `page_size` | int | Items per page (default: 50, max: 200) |
| `service` | string | Filter by service name |
| `severity` | string | Filter by severity level |
| `environment` | string | Filter by environment |
| `start_time` | ISO 8601 | Start of time range |
| `end_time` | ISO 8601 | End of time range |
| `search` | string | Full-text search in message |
| `request_id` | string | Filter by request ID |
| `trace_id` | string | Filter by trace ID |
| `status_code` | int | Filter by HTTP status code |
| `sort` | string | Sort field (default: `timestamp`) |
| `order` | string | Sort order: `asc` or `desc` (default: `desc`) |

**Response 200**:
```json
{
  "status": "success",
  "data": [
    {
      "id": "evt-uuid-1234",
      "timestamp": "2024-01-15T10:30:00.000Z",
      "received_at": "2024-01-15T10:30:00.123Z",
      "service": "demo-api",
      "environment": "production",
      "severity": "ERROR",
      "message": "Database connection timeout",
      "request_id": "req-a1b2c3d4",
      "trace_id": null,
      "endpoint": "/api/users/123",
      "status_code": 500,
      "duration_ms": 5023,
      "fingerprint": "fp-abc123",
      "metadata": {}
    }
  ],
  "meta": {
    "pagination": { "page": 1, "page_size": 50, "total_items": 234 }
  }
}
```

---

### GET /api/v1/logs/{id}

Get a single log event by ID.

**Response 200**: Full event object.
**Response 404**: Event not found.

---

### GET /api/v1/logs/{id}/context

Get surrounding events (before/after) for investigation.

**Query Parameters**:
- `before`: int (default: 5) — events before
- `after`: int (default: 5) — events after

**Response 200**:
```json
{
  "status": "success",
  "data": {
    "target": { ... },
    "before": [ ... ],
    "after": [ ... ]
  }
}
```

---

### GET /api/v1/stats/overview

Dashboard overview statistics.

**Query Parameters**: `start_time`, `end_time`, `service`, `environment`

**Response 200**:
```json
{
  "status": "success",
  "data": {
    "total_events": 15234,
    "events_per_minute": 122.5,
    "error_rate": 0.032,
    "error_count": 487,
    "p50_latency_ms": 45.2,
    "p95_latency_ms": 234.7,
    "p99_latency_ms": 891.3,
    "active_alerts": 2,
    "services_healthy": 3,
    "services_total": 4,
    "severity_distribution": {
      "DEBUG": 1234,
      "INFO": 10500,
      "WARNING": 2013,
      "ERROR": 450,
      "CRITICAL": 37
    }
  }
}
```

---

### GET /api/v1/stats/timeline

Time-series data for dashboard charts.

**Query Parameters**: `start_time`, `end_time`, `interval` (default: `1m`), `service`

**Response 200**:
```json
{
  "status": "success",
  "data": {
    "interval": "1m",
    "points": [
      {
        "timestamp": "2024-01-15T10:30:00Z",
        "total": 145,
        "errors": 3,
        "avg_duration_ms": 67.3,
        "p95_duration_ms": 210.0
      }
    ]
  }
}
```

---

### GET /api/v1/errors

List error groups.

**Query Parameters**: `page`, `page_size`, `service`, `severity`, `status`, `sort`

**Response 200**:
```json
{
  "status": "success",
  "data": [
    {
      "fingerprint": "fp-abc123",
      "service": "demo-api",
      "severity": "ERROR",
      "example_message": "Database connection timeout after {N}ms",
      "first_seen": "2024-01-15T08:00:00Z",
      "last_seen": "2024-01-15T10:30:00Z",
      "occurrences": 47,
      "status": "active"
    }
  ]
}
```

---

### GET /api/v1/errors/{fingerprint}

Get error group details with representative events.

**Response 200**:
```json
{
  "status": "success",
  "data": {
    "fingerprint": "fp-abc123",
    "service": "demo-api",
    "severity": "ERROR",
    "example_message": "Database connection timeout",
    "first_seen": "2024-01-15T08:00:00Z",
    "last_seen": "2024-01-15T10:30:00Z",
    "occurrences": 47,
    "status": "active",
    "recent_events": [ ... ],
    "timeline": [ ... ],
    "affected_endpoints": ["/api/users/{id}", "/api/orders"],
    "related_alerts": [ ... ]
  }
}
```

---

### GET /api/v1/alerts

List alerts.

**Query Parameters**: `status` (`active`, `resolved`, `all`), `severity`, `page`, `page_size`

**Response 200**:
```json
{
  "status": "success",
  "data": [
    {
      "id": "alert-uuid-1234",
      "rule": "ERROR_RATE_HIGH",
      "severity": "critical",
      "current_value": 0.15,
      "threshold": 0.10,
      "status": "active",
      "triggered_at": "2024-01-15T10:25:00Z",
      "resolved_at": null,
      "notification_status": "sent",
      "message": "Error rate exceeded 10% threshold (current: 15%)"
    }
  ]
}
```

---

### GET /api/v1/services

List service health information.

**Response 200**:
```json
{
  "status": "success",
  "data": [
    {
      "name": "telemetryscope-ingestion",
      "status": "healthy",
      "requests_per_second": 122.5,
      "error_rate": 0.008,
      "p95_latency_ms": 84.2,
      "replicas_ready": 3,
      "replicas_desired": 3,
      "last_event": "2024-01-15T10:30:00Z"
    }
  ]
}
```

---

### GET /api/v1/system/status

System-wide infrastructure summary.

**Response 200**:
```json
{
  "status": "success",
  "data": {
    "environment": "production-demo",
    "version": "1.0.0",
    "commit_sha": "abc1234",
    "services": { ... },
    "database": { "status": "connected", "latency_ms": 2.1 },
    "uptime_seconds": 86400
  }
}
```

---

### GET /api/v1/deployments

List deployment records.

**Response 200**:
```json
{
  "status": "success",
  "data": [
    {
      "id": "deploy-uuid",
      "service": "telemetryscope-ingestion",
      "version": "1.2.0",
      "commit_sha": "abc1234",
      "environment": "production-demo",
      "deployed_at": "2024-01-15T10:00:00Z",
      "status": "successful"
    }
  ]
}
```

---

## Demo Control Endpoints (Query & Control Service)

### POST /api/v1/demo/error

Trigger controlled error injection.

**Request Body**:
```json
{
  "count": 10,
  "service": "demo-api",
  "error_type": "database_timeout",
  "severity": "ERROR"
}
```

**Response 200**: `{ "status": "success", "data": { "triggered": 10 } }`

---

### POST /api/v1/demo/slow

Trigger slow response injection.

**Request Body**:
```json
{
  "count": 5,
  "delay_ms": 3000,
  "service": "demo-api"
}
```

---

### POST /api/v1/demo/traffic

Generate burst traffic.

**Request Body**:
```json
{
  "duration_seconds": 60,
  "rate_per_second": 50
}
```

---

### POST /api/v1/demo/reset

Reset demo state (stop active simulations).

**Response 200**: `{ "status": "success", "data": { "reset": true } }`

---

### POST /api/v1/demo/purge

Purge demo telemetry data. Requires confirmation.

**Request Body**:
```json
{
  "confirm": true,
  "older_than_hours": 24
}
```

**Response 200**:
```json
{
  "status": "success",
  "data": {
    "purged_events": 15000,
    "purged_error_groups": 23,
    "purged_alerts": 5
  }
}
```

**Response 400** (no confirmation):
```json
{
  "status": "error",
  "error": {
    "code": "CONFIRMATION_REQUIRED",
    "message": "Set confirm=true to proceed with destructive purge"
  }
}
```

---

## Rate Limiting

| Endpoint | Limit |
|----------|-------|
| `POST /api/v1/logs` | 100 req/s per source |
| `POST /api/v1/logs/batch` | 20 req/s per source |
| `GET /api/v1/*` | 60 req/s |
| Demo endpoints | 10 req/s |

---

## Authentication

**MVP**: No authentication. All endpoints are open.

**Production would add**: API keys for ingestion, JWT/OAuth2 for dashboard.

Internal endpoints (`/internal/*`) are protected by network policy (not exposed through Ingress).
