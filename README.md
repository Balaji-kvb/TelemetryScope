# TelemetryScope — Cloud-Native Observability & Log Analytics Platform

[![CI](https://github.com/Balaji-kvb/TelemetryScope/actions/workflows/ci.yml/badge.svg)](https://github.com/Balaji-kvb/TelemetryScope/actions/workflows/ci.yml)

**TelemetryScope** is a lightweight cloud-native observability and log analytics platform built as an academic project for **INT378 – Advancements in Cloud & DevOps**.

The platform collects structured application telemetry, validates and normalizes it, groups recurring errors, detects operational anomalies, produces alerts, exposes service health, visualizes infrastructure behavior, and supports controlled high-load and failure demonstrations.

### What TelemetryScope Does

```
Generate telemetry → Ingest → Validate → Process → Normalize → Enrich
→ Store → Search → Investigate → Group errors → Alert → Monitor
→ Load test → Scale → Deploy → Verify → Correlate
```

### Primary Investigation Workflow

```
DETECT → INVESTIGATE → CORRELATE → ALERT → ACT
```

---

## Problem Statement

Modern distributed systems generate vast amounts of operational data. Engineers need tools to:

- **Detect** which service is failing and when the failure started
- **Investigate** specific requests using correlation IDs
- **Correlate** deployments with latency changes and error surges
- **Alert** on operational thresholds (error rate, latency, repeated errors)
- **Scale** infrastructure under load and verify autoscaling behavior
- **Deploy** safely with rollout verification and smoke testing

TelemetryScope demonstrates this complete lifecycle through one coherent working system.

---

## Architecture

TelemetryScope consists of **three primary application microservices**:

| Service | Responsibility |
|---------|---------------|
| **Ingestion Service** | Accept, validate, normalize, and forward structured telemetry |
| **Processing Service** | Enrich, fingerprint errors, persist to PostgreSQL, evaluate alerts |
| **Query & Control Service** | Serve frontend APIs, log search, analytics, alert state, demo controls |

### Data Flow

```
Demo Workload / k6 / Simulator
        │
        │ POST /api/v1/logs
        ▼
  Ingestion Service
        │
        │ POST /internal/process
        ▼
  Processing Service
        │
        │ INSERT
        ▼
     PostgreSQL
        ▲
        │
  Query & Control Service
        │
        │ REST API
        ▼
   React Dashboard
```

### Alert Flow

```
Processing Service ──(condition met)──▶ Database Insert ──▶ Optional External Webhook/Lambda
```

External Webhooks are configured via environment variables and are never a blocking dependency on the ingestion path.

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React + Vite + Tailwind CSS |
| Backend | Python + Flask + Gunicorn |
| Database | PostgreSQL |
| Containers | Docker |
| Orchestration | Kubernetes (Minikube) |
| Load Testing | k6 (local) |
| Metrics | Prometheus |
| Visualization | Grafana |

---

## Project Structure

```
TelemetryScope/
├── frontend/              # React + Vite dashboard
├── services/
│   ├── ingestion-service/  # Telemetry intake + validation
│   ├── processing-service/ # Normalization + enrichment + persistence
│   └── query-service/      # Frontend APIs + analytics + demo controls
├── demo-workload/          # Realistic telemetry generator
├── database/               # Migrations + seed data
├── kubernetes/             # K8s manifests (deployments, HPA, RBAC, etc.)
├── load-testing/           # k6 scripts (normal, spike, errors, latency)
├── docs/                   # Architecture, API contract, runbook, viva
├── docker-compose.yml      # Local development environment
├── Makefile                # Development shortcuts
├── SECURITY.md             # Security baseline documentation
└── README.md               # This file
```

---

## Local Setup

### Prerequisites

| Tool | Minimum Version |
|------|----------------|
| Python | 3.11+ |
| Node.js | 18+ |
| Docker | 24+ |
| Git | 2.30+ |
| kubectl | 1.28+ |
| Terraform | 1.5+ |
| Minikube | 1.32+ |

### Quick Start (Docker Compose)

```bash
# Clone (Replace with actual repository URL)
git clone https://github.com/Balaji-kvb/TelemetryScope.git
cd TelemetryScope

# Start all services
docker compose up --build

# Access
# Dashboard:  http://localhost:3000
# Ingestion:  http://localhost:8001
# Query API:  http://localhost:8003
# Grafana:    http://localhost:3001
```

### Local Development (without Docker)

```bash
# Backend services
cd services/ingestion-service
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py

# Frontend
cd frontend
npm install
npm run dev
```

---

## Docker

Each service has an independent Dockerfile with:
- Python slim base image
- Gunicorn production server
- Non-root user
- No debug mode
- `.dockerignore` for clean builds
- Health endpoint
- Git SHA image tagging

```bash
docker compose up --build    # Start
docker compose down          # Stop
# WARNING: DO NOT run 'docker compose down -v' unless you intend to destroy all historical recovery data.
```

---

## Kubernetes Deployment & Teardown

### 1. Restarting the Existing Minikube Recovery Environment

If you are resuming work on the existing local environment with recovered data:

```bash
# Start Minikube and use its context
minikube start --driver=docker
kubectl config use-context minikube

# Verify the recovery database and PVC are intact
kubectl get pvc -n telemetryscope
kubectl get pods -n telemetryscope -l app=telemetryscope-postgres-recovery

# Apply application updates individually (DO NOT apply recursively)
kubectl apply -f kubernetes/demo.yaml
kubectl apply -f kubernetes/frontend.yaml
kubectl apply -f kubernetes/ingestion/ingestion.yaml
kubectl apply -f kubernetes/processing/processing.yaml
kubectl apply -f kubernetes/query/query.yaml
```

### 2. Provisioning a New Environment from Scratch

If deploying to a completely fresh cluster:

```bash
# Initialize namespace and base persistent volumes
kubectl apply -f kubernetes/namespace.yaml

# Create the recovery database infrastructure
kubectl apply -f kubernetes/postgres/recovery-postgres.yaml
```

**Important Database Restoration Note:**
Applying `recovery-postgres.yaml` provisions the pod and volume structure but does *not* automatically restore historical data. A fresh cluster will remain empty until a separately protected PostgreSQL backup/WAL volume is manually mounted and verified. Never apply `kubernetes/postgres/postgres.yaml` in this sequence, as it conflicts with the recovery architecture.

```bash
# Only after the database is manually restored and verified, deploy the rest of the stack individually:
kubectl apply -f kubernetes/demo.yaml
kubectl apply -f kubernetes/frontend.yaml
kubectl apply -f kubernetes/ingestion/ingestion.yaml
kubectl apply -f kubernetes/processing/processing.yaml
kubectl apply -f kubernetes/query/query.yaml
```

### Shutting Down Safely (Data Preservation)

If you need to tear down the environment without data loss, **simply stop Minikube**:

```bash
# Safely stop the entire local cluster while preserving state
minikube stop
```

**WARNING:** Never run `kubectl delete deployments --all` or delete the PostgreSQL Persistent Volume Claims (PVC) if you intend to retain data.

### HPA (Horizontal Pod Autoscaler)

The **Ingestion Service** is the primary HPA target:
- `minReplicas: 1`
- `maxReplicas: 5`
- CPU target: ~60% (calibrated experimentally)

---

## Tests and Verification

- The project relies on end-to-end integration verifications and smoke checks.
- Run `curl -s http://127.0.0.1/api/v1/system/status` against the frontend Nginx proxy to execute an operational smoke check for all components including database connectivity.
- A synthetic load test mechanism is accessible via the UI or `demo-workload` API to generate realistic database load and test alert pipelines safely.
- Warning: Do not trigger purge operations (`/api/v1/demo/purge`) on production databases. Purge functionality is intentionally locked out via the `telemetryscope_reader` postgres role to prevent data destruction.

---

## Important Data Preservation Precautions

**CRITICAL:** TelemetryScope's current production database operates from a recovered Write-Ahead Log (WAL) state via the `telemetryscope-postgres-recovery` pod.

- **DO NOT** scale up the original `telemetryscope-postgres` deployment from zero.
- **DO NOT** delete the `postgres-pvc` or `postgres-recovery-pvc`.
- **DO NOT** run `minikube delete` or `docker compose down -v` unless you intend to irrecoverably wipe the entire historical dataset.
- The PostgreSQL WAL backups are vital for long-term recovery analysis and must be preserved.

---

## Demo Flow & Screenshots to Capture

See [docs/demo-runbook.md](docs/demo-runbook.md) for the complete demonstration sequence:

1. **Normal Operation** — healthy services, live telemetry, filtering
2. **Error Injection** — controlled errors, fingerprinting, alerts, Lambda
3. **Latency Injection** — P95 rise, request correlation, context
4. **High Traffic** — EC2 + k6, HPA scale-up, pod lifecycle
5. **Grafana** — RPS, CPU, latency, replicas, errors
6. **CI/CD** — commit → build → deploy → verify → deployment marker
7. **Staging** — Elastic Beanstalk secondary proof

*Recommended Screenshots during evaluation:* 
- Overview dashboard with active telemetry metrics.
- Alerts panel showing `ERROR_RATE_HIGH` successfully triggered.
- K8s terminal demonstrating successful rolling updates and `Running` pods.

---

## Known Limitations

- **WAL-Recovery state:** The database is currently running out of the recovery pod instead of a primary replica format.
- **Single PostgreSQL instance:** (academic scope limitations).
- **Polling-based live logs:** UI uses a 2s polling interval, not WebSocket/SSE.
- **CPU-based HPA only:** No custom metrics adapter in MVP.
- **No full distributed tracing:** `trace_id` reserved for future.
- **No Kafka/Elasticsearch:** Intentional decision—see viva.md for rationale.

---

## License

Academic project for INT378 – Advancements in Cloud & DevOps.

---

**TelemetryScope** — *See everything. Understand anything.*
