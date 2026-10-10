# TelemetryScope Architecture

## 1. Overview

TelemetryScope is a cloud-native observability and log analytics platform comprising three primary application microservices, a demo workload, and supporting infrastructure.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        TelemetryScope Platform                         │
│                                                                        │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────┐ │
│  │  Demo     │───▶│  Ingestion   │───▶│  Processing  │───▶│PostgreSQL│ │
│  │  Workload │    │  Service     │    │  Service     │    │          │ │
│  └──────────┘    └──────────────┘    └──────────────┘    └────┬─────┘ │
│                         ▲                    │                 │       │
│                         │              ┌─────▼─────┐          │       │
│                    ┌────┴────┐         │  Lambda    │    ┌─────▼─────┐ │
│                    │  k6 /   │         │  (async)   │    │  Query &  │ │
│                    │  EC2    │         └───────────┘    │  Control  │ │
│                    └─────────┘                          └─────┬─────┘ │
│                                                               │       │
│                                                         ┌─────▼─────┐ │
│                                                         │  React    │ │
│                                                         │  Dashboard│ │
│                                                         └───────────┘ │
│                                                                        │
│  ┌──────────┐    ┌──────────┐                                         │
│  │Prometheus│───▶│ Grafana  │                                         │
│  └──────────┘    └──────────┘                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Service Boundaries

### 2.1 Ingestion Service

**Purpose**: The front door of TelemetryScope. Accepts structured telemetry from any source, validates it, normalizes mandatory fields, and forwards accepted events to the Processing Service.

**Why it exists**: Separating ingestion from processing creates a clear boundary between external-facing validation and internal business logic. The Ingestion Service is the primary HPA target because it directly receives external traffic load.

**Responsibilities**:
- Accept telemetry via `POST /api/v1/logs` and `POST /api/v1/logs/batch`
- Validate payload structure, field types, and size limits
- Reject malformed data with descriptive errors
- Generate `request_id` when absent
- Preserve `trace_id` when supplied
- Normalize mandatory fields (timestamp format, severity)
- Forward accepted events to Processing Service via `POST /internal/process`
- Expose `/health`, `/ready`, `/metrics`, `/version`
- Produce structured JSON logs

**Does NOT**:
- Persist data to PostgreSQL
- Evaluate alert rules
- Compute error fingerprints
- Serve frontend queries

---

### 2.2 Processing Service

**Purpose**: Receives validated events from Ingestion, performs deep normalization and enrichment, computes error fingerprints, persists telemetry to PostgreSQL, maintains error groups, and evaluates alert rules.

**Why it exists**: Processing is computationally heavier than validation. Separating it allows independent scaling decisions and isolates database write operations.

**Responsibilities**:
- Receive events from Ingestion via `POST /internal/process`
- Normalize timestamps to UTC
- Normalize severity to canonical levels
- Sanitize bounded metadata
- Extract HTTP/status/endpoint/duration fields
- Calculate deterministic error fingerprints
- Persist telemetry into PostgreSQL
- Maintain error-group aggregates
- Evaluate simple alert rules (error rate, repeated errors, P95 latency)
- Trigger asynchronous Lambda for alert notifications
- Expose `/health`, `/ready`, `/metrics`, `/version`

**Does NOT**:
- Accept external traffic
- Serve frontend APIs
- Handle query/search operations

---

### 2.3 Query & Control Service

**Purpose**: Serves the React dashboard with APIs for log searching, analytics, error investigation, alert state, service health, and controlled demo operations.

**Why it exists**: Read-heavy operations have different scaling characteristics than write-heavy ingestion/processing. Separating queries avoids coupling frontend latency to ingestion throughput.

**Responsibilities**:
- Log querying with pagination, filtering, and text search
- Overview analytics (logs/min, error rate, P95 latency, etc.)
- Timeline analytics (traffic over time, error trends)
- Error group retrieval and investigation
- Alert state display
- Service health aggregation
- Deployment information
- Infrastructure summary (via Prometheus, not K8s admin API)
- Controlled demo operations (inject errors, slow requests, traffic, reset)
- Demo cleanup/purge operations
- Expose `/health`, `/ready`, `/metrics`, `/version`

**Does NOT**:
- Receive external telemetry
- Write telemetry events to the database
- Have privileged Kubernetes admin access
- Manage infrastructure resources

---

### 2.4 Demo Workload (demo-api)

**Purpose**: Generates realistic telemetry to demonstrate TelemetryScope in action.

**Why it exists**: TelemetryScope must observe something meaningful. Seeded fake rows are insufficient — real telemetry must flow through the full pipeline.

**What it produces**:
1. Normal requests (low latency, success)
2. Slow responses (controlled delay)
3. Controlled 4xx/5xx errors
4. Repeated errors (same fingerprint)
5. Varying response durations
6. Request identifiers
7. Realistic structured logs

**Not counted** as a core TelemetryScope microservice.

---

## 3. Communication Patterns

### External → Internal

| Source | Target | Protocol | Endpoint |
|--------|--------|----------|----------|
| Demo Workload / k6 / Simulator | Ingestion Service | HTTP POST | `/api/v1/logs` |
| React Dashboard | Query Service | HTTP GET/POST | `/api/v1/*` |
| AWS ALB | K8s Ingress | HTTP/HTTPS | Path-based routing |

### Internal → Internal

| Source | Target | Protocol | Endpoint |
|--------|--------|----------|----------|
| Ingestion Service | Processing Service | HTTP POST | `/internal/process` |
| Processing Service | PostgreSQL | TCP | Port 5432 |
| Query Service | PostgreSQL | TCP | Port 5432 (read-only) |
| Processing Service | Lambda (async) | AWS SDK / HTTP | Invoke (async) |

### Observability

| Component | Prometheus Scrape |
|-----------|------------------|
| Ingestion Service | `/metrics` |
| Processing Service | `/metrics` |
| Query Service | `/metrics` |
| Demo Workload | `/metrics` (optional) |

---

## 4. Data Flow

### Primary Telemetry Flow

```
1. Demo Workload generates structured telemetry event
2. POST /api/v1/logs → Ingestion Service
3. Ingestion validates payload, generates request_id if absent
4. Ingestion normalizes mandatory fields
5. Ingestion forwards to POST /internal/process → Processing Service
6. Processing normalizes timestamps to UTC
7. Processing normalizes severity
8. Processing sanitizes metadata
9. Processing computes error fingerprint
10. Processing INSERTs into PostgreSQL (logs table)
11. Processing updates error_groups if applicable
12. Processing evaluates alert rules
13. If alert condition met → async Lambda invocation
14. Query Service reads from PostgreSQL
15. React Dashboard displays via REST API
```

### Alert Flow

```
Processing Service
    │ condition met
    ▼
INSERT into alerts table
    │
    ▼ (async, non-blocking)
Lambda alert-handler
    │
    ▼ (optional)
SNS notification
```

**Critical**: Lambda failure MUST NOT break telemetry ingestion.

---

## 5. Infrastructure Architecture

### Local Development

```
docker-compose.yml
├── telemetryscope-ingestion    (port 8001)
├── telemetryscope-processing   (port 8002)
├── telemetryscope-query        (port 8003)
├── telemetryscope-postgres     (port 5432)
├── telemetryscope-demo         (port 8080)
├── prometheus                  (port 9090)
└── grafana                     (port 3001)

Frontend dev server             (port 3000)
```

### Kubernetes (Local + EKS)

```
Namespace: telemetryscope
├── Deployments
│   ├── telemetryscope-ingestion
│   ├── telemetryscope-processing
│   ├── telemetryscope-query
│   ├── telemetryscope-frontend
│   └── telemetryscope-demo
├── StatefulSet / Deployment
│   └── telemetryscope-postgres
├── Monitoring
│   ├── telemetryscope-prometheus
│   └── telemetryscope-grafana
├── HPA
│   └── telemetryscope-ingestion-hpa
├── Ingress
│   └── telemetryscope-ingress (ALB in EKS)
├── NetworkPolicies
├── RBAC (ServiceAccounts, Roles)
└── PVC (PostgreSQL data)
```

### AWS Architecture

```
┌─ VPC ──────────────────────────────────────┐
│                                             │
│  ┌─ Public Subnets ─────────────────────┐  │
│  │  ALB (Application Load Balancer)     │  │
│  │  NAT Gateway                         │  │
│  │  EC2 (k6 load generator)            │  │
│  └──────────────────────────────────────┘  │
│                                             │
│  ┌─ Private Subnets ────────────────────┐  │
│  │  EKS Cluster                         │  │
│  │  ├── Ingestion Pods                  │  │
│  │  ├── Processing Pods                 │  │
│  │  ├── Query Pods                      │  │
│  │  ├── Frontend Pod                    │  │
│  │  ├── PostgreSQL Pod                  │  │
│  │  ├── Prometheus Pod                  │  │
│  │  └── Grafana Pod                     │  │
│  └──────────────────────────────────────┘  │
│                                             │
│  Lambda (alert-handler)                     │
│  ECR (container images)                     │
│  SNS (optional notifications)               │
│  Elastic Beanstalk (staging)                │
└─────────────────────────────────────────────┘
```

---

## 6. Correlation Model

Every incoming request gets a `request_id`:
- Format: `req-{uuid_hex_8}`
- If not provided by the caller, Ingestion Service generates one
- Propagated through all internal calls
- Stored with the event in PostgreSQL
- Searchable and filterable in the dashboard

`trace_id` is reserved for future OpenTelemetry integration:
- If supplied, preserved as-is
- Not generated automatically in MVP
- Future: enables trace-to-log correlation

---

## 7. Error Fingerprinting Model

Errors are grouped by deterministic fingerprint, NOT raw message text.

**Fingerprint inputs** (normalized before hashing):
- `service`
- `severity`
- `exception_type` (if present)
- `normalized_message` (variable identifiers stripped)
- `endpoint`

**Normalization rules**:
- Numbers → `{N}`
- UUIDs → `{UUID}`
- Email addresses → `{EMAIL}`
- IP addresses → `{IP}`

**Example**:
```
"Database timeout for user 123" → "Database timeout for user {N}"
"Database timeout for user 456" → "Database timeout for user {N}"
→ Same fingerprint → Same error group
```

---

## 8. Alert Model

MVP alert rules (configuration-driven, not CRUD-managed):

| Rule | Trigger |
|------|---------|
| `ERROR_RATE_HIGH` | Error count exceeds threshold in time window |
| `REPEATED_ERROR` | Same fingerprint exceeds occurrence threshold |
| `P95_LATENCY_HIGH` | 95th percentile latency exceeds threshold |

**Alert properties**: deduplication, cooldown period, severity levels, grouping.

**Anti-storm**: alerts have cooldown to prevent alert fatigue.

---

## 9. Deployment Model

Every successful deployment creates a record:

```json
{
  "service": "telemetryscope-ingestion",
  "version": "1.2.0",
  "commit_sha": "abc1234",
  "environment": "production-demo",
  "deployed_at": "2024-01-15T10:30:00Z",
  "status": "successful"
}
```

Displayed as markers in the dashboard timeline to correlate deployments with operational changes.

---

## 10. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| PostgreSQL over Elasticsearch | Simpler operations, adequate for student scale, SQL familiarity |
| No Kafka | Direct HTTP between services is sufficient; Kafka adds operational complexity without proportional benefit at this scale |
| Frontend is not a 4th microservice | It's a static SPA served by Nginx, not a backend service |
| Ingestion is HPA target | It receives external traffic directly; CPU correlates with request load |
| Lambda is asynchronous | Alert delivery must not block telemetry ingestion |
| No cluster-admin for Query Service | Infrastructure data comes from Prometheus, not privileged K8s API |
| Polling not WebSocket for live logs | Simpler to implement and debug; 2s polling is adequate for MVP |
| `request_id` not a Prometheus label | Unbounded cardinality would destroy Prometheus performance |
