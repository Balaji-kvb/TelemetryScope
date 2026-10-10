-- TelemetryScope Database Schema
-- Migration: 001_initial_schema.sql
-- Purpose: Create core tables for telemetry storage, error groups, alerts, and deployments

-- ============================================================
-- ROLES (run as superuser if setting up roles)
-- ============================================================
-- These are created via init scripts; included here for documentation.
-- CREATE ROLE telemetryscope_writer WITH LOGIN PASSWORD 'writer_password';
-- CREATE ROLE telemetryscope_reader WITH LOGIN PASSWORD 'reader_password';
-- CREATE ROLE telemetryscope_migrator WITH LOGIN PASSWORD 'migrator_password';

-- ============================================================
-- EXTENSIONS
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- LOGS TABLE
-- ============================================================
-- Primary telemetry event storage.
-- Written by: Processing Service (telemetryscope_writer)
-- Read by: Query Service (telemetryscope_reader)
CREATE TABLE IF NOT EXISTS logs (
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

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_logs_service ON logs (service);
CREATE INDEX IF NOT EXISTS idx_logs_severity ON logs (severity);
CREATE INDEX IF NOT EXISTS idx_logs_environment ON logs (environment);
CREATE INDEX IF NOT EXISTS idx_logs_fingerprint ON logs (fingerprint);
CREATE INDEX IF NOT EXISTS idx_logs_request_id ON logs (request_id);
CREATE INDEX IF NOT EXISTS idx_logs_service_timestamp ON logs (service, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_logs_severity_timestamp ON logs (severity, timestamp DESC);

-- ============================================================
-- ERROR_GROUPS TABLE
-- ============================================================
-- Aggregated error groups based on deterministic fingerprints.
-- Written by: Processing Service
-- Read by: Query Service
CREATE TABLE IF NOT EXISTS error_groups (
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

CREATE INDEX IF NOT EXISTS idx_error_groups_service ON error_groups (service);
CREATE INDEX IF NOT EXISTS idx_error_groups_status ON error_groups (status);
CREATE INDEX IF NOT EXISTS idx_error_groups_last_seen ON error_groups (last_seen DESC);

-- ============================================================
-- ALERTS TABLE
-- ============================================================
-- Alert records triggered by rule evaluation.
-- Written by: Processing Service
-- Read by: Query Service
CREATE TABLE IF NOT EXISTS alerts (
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

CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts (status);
CREATE INDEX IF NOT EXISTS idx_alerts_rule ON alerts (rule);
CREATE INDEX IF NOT EXISTS idx_alerts_triggered_at ON alerts (triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_service ON alerts (service);

-- ============================================================
-- DEPLOYMENTS TABLE
-- ============================================================
-- Deployment records for correlation with operational changes.
-- Written by: CI/CD pipeline / Processing Service
-- Read by: Query Service
CREATE TABLE IF NOT EXISTS deployments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service         VARCHAR(100) NOT NULL,
    version         VARCHAR(50) NOT NULL,
    commit_sha      VARCHAR(64) NOT NULL,
    environment     VARCHAR(50) NOT NULL,
    deployed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status          VARCHAR(20) NOT NULL DEFAULT 'successful',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_deployments_service ON deployments (service);
CREATE INDEX IF NOT EXISTS idx_deployments_deployed_at ON deployments (deployed_at DESC);
CREATE INDEX IF NOT EXISTS idx_deployments_environment ON deployments (environment);

-- ============================================================
-- GRANTS
-- ============================================================
-- Writer role (Processing Service)
GRANT SELECT, INSERT, UPDATE ON logs TO telemetryscope_writer;
GRANT SELECT, INSERT, UPDATE ON error_groups TO telemetryscope_writer;
GRANT SELECT, INSERT, UPDATE ON alerts TO telemetryscope_writer;
GRANT SELECT, INSERT ON deployments TO telemetryscope_writer;

-- Reader role (Query Service) - READ ONLY
GRANT SELECT ON logs TO telemetryscope_reader;
GRANT SELECT ON error_groups TO telemetryscope_reader;
GRANT SELECT ON alerts TO telemetryscope_reader;
GRANT SELECT ON deployments TO telemetryscope_reader;
