# TelemetryScope Telemetry Schema

## Overview

This document defines the telemetry event schema used throughout TelemetryScope. The schema is defined **before** business logic implementation and serves as the contract between all services.

---

## Core Concepts

### Timestamp Semantics

| Field | Meaning | Set By |
|-------|---------|--------|
| `timestamp` | When the original event happened at the source | Client / Demo Workload |
| `received_at` | When TelemetryScope received the event | Ingestion Service |
| `created_at` | When the record was persisted to PostgreSQL | Processing Service |

**Derived field**:
```
ingestion_delay = received_at - timestamp
```

This measures pipeline latency — the gap between when an event occurred and when TelemetryScope received it.

---

## Event Schema

### Client-Provided Fields

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| `timestamp` | ISO 8601 string | No | Current UTC | Must be valid datetime; not more than 24h in future |
| `service` | string | **Yes** | — | 1-100 chars; `[a-zA-Z0-9_-]` |
| `environment` | string | No | `development` | One of: `development`, `staging`, `production`, `demo` |
| `severity` | string | No | `INFO` | See severity levels below |
| `message` | string | **Yes** | — | 1-5000 chars |
| `request_id` | string | No | Auto-generated | Format: `req-{hex8}` |
| `trace_id` | string | No | `null` | Reserved for future OTel; preserved if supplied |
| `endpoint` | string | No | `null` | Max 500 chars; e.g., `/api/users/123` |
| `status_code` | integer | No | `null` | 100-599 |
| `duration_ms` | float | No | `null` | Non-negative |
| `metadata` | object | No | `{}` | Max 10 keys; max 1KB total; bounded |

### Server-Generated Fields

| Field | Type | Set By | Description |
|-------|------|--------|-------------|
| `id` | UUID | Processing Service | Unique event identifier |
| `received_at` | ISO 8601 | Ingestion Service | When TelemetryScope received the event |
| `fingerprint` | string | Processing Service | Deterministic error group hash |
| `created_at` | ISO 8601 | PostgreSQL (default) | When the record was inserted |

---

## Severity Levels

Canonical severity levels (case-insensitive input, stored uppercase):

| Level | Numeric | Description |
|-------|---------|-------------|
| `DEBUG` | 10 | Diagnostic information |
| `INFO` | 20 | Normal operational events |
| `WARNING` | 30 | Potential issues, degraded state |
| `ERROR` | 40 | Failed operations, exceptions |
| `CRITICAL` | 50 | System-level failures, outages |

### Severity Normalization

The Ingestion Service normalizes common severity aliases:

| Input | Normalized |
|-------|-----------|
| `debug`, `DEBUG`, `Debug` | `DEBUG` |
| `info`, `INFO`, `Info`, `information` | `INFO` |
| `warn`, `WARN`, `warning`, `WARNING` | `WARNING` |
| `error`, `ERROR`, `Error`, `err` | `ERROR` |
| `critical`, `CRITICAL`, `fatal`, `FATAL`, `crit` | `CRITICAL` |

Unknown values → reject with 400.

---

## Metadata Constraints

The `metadata` field is a bounded JSON object:

| Constraint | Value |
|-----------|-------|
| Max keys | 10 |
| Max total size | 1 KB |
| Key format | String, 1-50 chars, `[a-zA-Z0-9_]` |
| Value types | string, number, boolean |
| Nested objects | Not allowed |
| Arrays | Not allowed |

### Forbidden Metadata Keys

The following keys are rejected during validation:

```
password, secret, token, authorization, api_key, access_key,
secret_key, private_key, credential, ssn, credit_card
```

---

## Correlation

### request_id

- **Format**: `req-{8 hex chars}` (e.g., `req-a1b2c3d4`)
- **Behavior**: If not provided by the client, Ingestion Service generates one
- **Propagation**: Attached to all internal service calls
- **Storage**: Persisted with the event; searchable and filterable
- **Important**: NEVER used as a Prometheus label (unbounded cardinality)

### trace_id

- **Format**: Free-form string (reserved for OpenTelemetry compatibility)
- **Behavior**: If provided, preserved as-is; not auto-generated in MVP
- **Future**: Will enable trace-to-log correlation with OTel

### span_id

- **Reserved** for future use
- Not implemented in MVP

---

## Error Fingerprinting

### Purpose

Group identical logical errors even when variable values differ.

### Algorithm

```python
def compute_fingerprint(event):
    normalized = normalize_message(event['message'])
    components = [
        event.get('service', ''),
        event.get('severity', ''),
        event.get('metadata', {}).get('exception_type', ''),
        normalized,
        event.get('endpoint', '')
    ]
    raw = '|'.join(components)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
```

### Message Normalization Rules

Before fingerprinting, variable portions of messages are replaced:

| Pattern | Replacement | Example |
|---------|-------------|---------|
| Integers / floats | `{N}` | `user 123` → `user {N}` |
| UUIDs | `{UUID}` | `req-a1b2c3d4-...` → `req-{UUID}` |
| Email addresses | `{EMAIL}` | `user@example.com` → `{EMAIL}` |
| IP addresses | `{IP}` | `192.168.1.1` → `{IP}` |
| Hex strings (8+ chars) | `{HEX}` | `deadbeef1234` → `{HEX}` |
| Quoted strings | `{STR}` | `"some value"` → `{STR}` |

### Example

```
Input:  "Database timeout for user 123 at 192.168.1.50"
Normal: "Database timeout for user {N} at {IP}"

Input:  "Database timeout for user 456 at 10.0.0.1"
Normal: "Database timeout for user {N} at {IP}"

→ Same normalized message → Same fingerprint → Same error group
```

---

## Database Schema

### logs table

```sql
CREATE TABLE logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp       TIMESTAMPTZ NOT NULL,
    received_at     TIMESTAMPTZ NOT NULL,
    service         VARCHAR(100) NOT NULL,
    environment     VARCHAR(50) NOT NULL DEFAULT 'development',
    severity        VARCHAR(20) NOT NULL DEFAULT 'INFO',
    message         TEXT NOT NULL,
    request_id      VARCHAR(100),
    trace_id        VARCHAR(100),
    endpoint        VARCHAR(500),
    status_code     SMALLINT,
    duration_ms     REAL,
    fingerprint     VARCHAR(64),
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Indexes

```sql
CREATE INDEX idx_logs_timestamp ON logs (timestamp DESC);
CREATE INDEX idx_logs_service ON logs (service);
CREATE INDEX idx_logs_severity ON logs (severity);
CREATE INDEX idx_logs_environment ON logs (environment);
CREATE INDEX idx_logs_fingerprint ON logs (fingerprint);
CREATE INDEX idx_logs_request_id ON logs (request_id);
CREATE INDEX idx_logs_service_timestamp ON logs (service, timestamp DESC);
CREATE INDEX idx_logs_severity_timestamp ON logs (severity, timestamp DESC);
```

### error_groups table

```sql
CREATE TABLE error_groups (
    fingerprint     VARCHAR(64) PRIMARY KEY,
    service         VARCHAR(100) NOT NULL,
    severity        VARCHAR(20) NOT NULL,
    example_message TEXT NOT NULL,
    first_seen      TIMESTAMPTZ NOT NULL,
    last_seen       TIMESTAMPTZ NOT NULL,
    occurrences     INTEGER NOT NULL DEFAULT 1,
    status          VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### alerts table

```sql
CREATE TABLE alerts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule                VARCHAR(50) NOT NULL,
    severity            VARCHAR(20) NOT NULL,
    current_value       REAL NOT NULL,
    threshold           REAL NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'active',
    message             TEXT,
    service             VARCHAR(100),
    triggered_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at         TIMESTAMPTZ,
    last_evaluated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notification_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_alerts_status ON alerts (status);
CREATE INDEX idx_alerts_rule ON alerts (rule);
CREATE INDEX idx_alerts_triggered_at ON alerts (triggered_at DESC);
```

### deployments table

```sql
CREATE TABLE deployments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service         VARCHAR(100) NOT NULL,
    version         VARCHAR(50) NOT NULL,
    commit_sha      VARCHAR(64) NOT NULL,
    environment     VARCHAR(50) NOT NULL,
    deployed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status          VARCHAR(20) NOT NULL DEFAULT 'successful',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_deployments_service ON deployments (service);
CREATE INDEX idx_deployments_deployed_at ON deployments (deployed_at DESC);
```

---

## Payload Examples

### Minimal Valid Payload

```json
{
  "service": "demo-api",
  "message": "Request completed"
}
```

### Full Payload

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

### Batch Payload

```json
{
  "events": [
    { "service": "demo-api", "severity": "INFO", "message": "GET /api/health 200 12ms" },
    { "service": "demo-api", "severity": "ERROR", "message": "POST /api/orders 500 5023ms" }
  ]
}
```

---

## Size Limits

| Limit | Value |
|-------|-------|
| Single event payload | 64 KB |
| Batch size | 100 events |
| Batch payload | 1 MB |
| Message field | 5000 chars |
| Metadata total | 1 KB |
| Metadata keys | 10 max |
| Service name | 100 chars |
| Endpoint | 500 chars |
