# TelemetryScope Security Baseline

## Overview

This document describes the security baseline for TelemetryScope. As an academic project, TelemetryScope implements reasonable security controls appropriate for a demonstration/learning environment while documenting where production-grade hardening would differ.

---

## Secrets Management

### What We Do
- **No secrets in source code** — all sensitive values use environment variables or Kubernetes Secrets
- **`.gitignore`** excludes `.env`, `*.tfstate`, credentials, and secret YAML files
- **Terraform state** is never committed to Git
- **Database credentials** are injected via environment variables / K8s Secrets

### What Production Would Add
- AWS Secrets Manager or HashiCorp Vault
- Secret rotation policies
- Encrypted Terraform state backend (S3 + DynamoDB)

---

## Container Security

| Control | Status |
|---------|--------|
| Non-root container user | ✅ Implemented |
| Python slim base image | ✅ Implemented |
| No debug mode in production | ✅ Implemented |
| `.dockerignore` for clean builds | ✅ Implemented |
| Immutable image tags (Git SHA) | ✅ Implemented |
| Read-only filesystem (where compatible) | ✅ Implemented |
| Security context in K8s | ✅ Implemented |

---

## Network Security

- **Kubernetes NetworkPolicies** restrict pod-to-pod communication
- **ClusterIP** for internal services (not exposed externally)
- **Ingress** through controlled ALB with defined path rules
- **No unnecessary ports** exposed

---

## Input Validation & Sanitization

- **Bounded payload size** — requests exceeding limits are rejected (413)
- **Bounded metadata** — metadata fields are size-limited
- **Schema validation** — telemetry payloads validated before processing
- **Basic rate limiting** — applied at ingestion endpoint
- **Sanitized logs** — no passwords, tokens, auth headers, or secrets logged

### Data That Must NEVER Be Logged

```
Authorization headers
Bearer tokens / API keys
Passwords
AWS credentials (access key, secret key, session tokens)
Database connection strings with credentials
Personal identification numbers
Credit card numbers
```

---

## Authentication & Authorization

### MVP Scope
- Internal service-to-service communication uses cluster networking (no auth tokens for MVP)
- Database uses separate reader/writer roles
- No public user authentication (academic scope)

### Production Would Add
- mTLS between services
- API key or JWT authentication for external APIs
- OAuth2 / OIDC for dashboard access

---

## IAM & Cloud Security

- **Least-privilege IAM roles** for EKS, Lambda, EC2, ECR
- **GitHub OIDC** preferred over long-lived AWS access keys (where feasible)
- **ServiceAccounts** in Kubernetes with minimal RBAC
- **Query Service** does NOT receive cluster-admin access
- **Infrastructure status** obtained through Prometheus, not privileged K8s API calls

---

## Database Security

| Control | Description |
|---------|-------------|
| Separate roles | `telemetryscope_writer`, `telemetryscope_reader`, `telemetryscope_migrator` |
| Reader is read-only | Cannot INSERT/UPDATE/DELETE |
| Connection pooling | Bounded connection limits |
| Query time limits | Prevents unbounded queries |
| No cross-service writes | Services don't modify each other's state via SQL |

---

## HTTPS

- **Production/demo**: HTTPS via AWS ALB with ACM certificate
- **Local development**: HTTP (acceptable for local-only traffic)

---

## Kubernetes Security

| Control | Status |
|---------|--------|
| Dedicated namespace (`telemetryscope`) | ✅ |
| NetworkPolicies | ✅ |
| Non-root SecurityContext | ✅ |
| Resource requests/limits | ✅ |
| Read-only root filesystem (where compatible) | ✅ |
| Least-privilege ServiceAccounts | ✅ |
| Secrets for sensitive config | ✅ |
| No `hostNetwork` / `hostPID` | ✅ |

---

## CI/CD Security

- **No secrets in workflow files** — use GitHub Secrets
- **Docker image scanning** — basic security checks in CI
- **Immutable deployments** — Git SHA tags, not mutable `latest`
- **Rollout verification** — health check after deployment
- **Smoke test** — functional verification post-deploy

---

## Reporting Security Issues

This is an academic project. If you discover a security concern, please reach out directly to the project maintainer.

---

## Limitations

This security baseline is appropriate for an academic demonstration. It is NOT sufficient for production systems handling real user data or operating at scale. Key gaps vs. production:

1. No user authentication/authorization on the dashboard
2. No mTLS between services
3. No secret rotation
4. No WAF in front of ALB
5. No audit logging
6. No penetration testing
7. Single-AZ database (no HA)

These are documented as known limitations, not oversights.
