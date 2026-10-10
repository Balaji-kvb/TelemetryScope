"""
TelemetryScope — Processing Service
Database connection pool and operations for telemetry persistence.
"""

import os
import time
import logging
import psycopg2
import psycopg2.pool
import psycopg2.extras
from contextlib import contextmanager

from metrics import DB_OPERATION_DURATION, DB_ERRORS

logger = logging.getLogger("telemetryscope-processing")

# Connection pool (initialized lazily)
_pool = None


def get_pool():
    """Get or create the database connection pool."""
    global _pool
    if _pool is None:
        db_url = os.environ.get(
            "DATABASE_URL",
            "postgresql://telemetryscope_writer:writer_password@localhost:5432/telemetryscope"
        )
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            dsn=db_url,
        )
        logger.info("Database connection pool created")
    return _pool


def check_db_connection():
    """Check if database is reachable. Returns True/False."""
    try:
        pool = get_pool()
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        finally:
            pool.putconn(conn)
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


@contextmanager
def get_connection():
    """Context manager for database connections from the pool."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def insert_log_event(event):
    """Insert a processed telemetry event into the logs table.
    Returns the generated event ID.
    """
    start = time.time()
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO logs (
                        timestamp, received_at, service, environment, severity,
                        message, request_id, trace_id, endpoint, status_code,
                        duration_ms, fingerprint, metadata
                    ) VALUES (
                        %(timestamp)s, %(received_at)s, %(service)s, %(environment)s,
                        %(severity)s, %(message)s, %(request_id)s, %(trace_id)s,
                        %(endpoint)s, %(status_code)s, %(duration_ms)s,
                        %(fingerprint)s, %(metadata)s::jsonb
                    ) RETURNING id
                    """,
                    {
                        "timestamp": event["timestamp"],
                        "received_at": event["received_at"],
                        "service": event["service"],
                        "environment": event.get("environment", "development"),
                        "severity": event.get("severity", "INFO"),
                        "message": event["message"],
                        "request_id": event.get("request_id"),
                        "trace_id": event.get("trace_id"),
                        "endpoint": event.get("endpoint"),
                        "status_code": event.get("status_code"),
                        "duration_ms": event.get("duration_ms"),
                        "fingerprint": event.get("fingerprint"),
                        "metadata": psycopg2.extras.Json(event.get("metadata", {})),
                    },
                )
                event_id = cur.fetchone()[0]
                duration = time.time() - start
                DB_OPERATION_DURATION.labels(operation="insert_log").observe(duration)
                return str(event_id)
    except Exception as e:
        duration = time.time() - start
        DB_OPERATION_DURATION.labels(operation="insert_log").observe(duration)
        DB_ERRORS.labels(operation="insert_log").inc()
        logger.error(f"Failed to insert log event: {e}", exc_info=True)
        raise


def upsert_error_group(event):
    """Create or update an error group based on fingerprint."""
    fingerprint = event.get("fingerprint")
    if not fingerprint:
        return

    # Only track errors (WARNING and above)
    severity = event.get("severity", "INFO")
    if severity not in ("WARNING", "ERROR", "CRITICAL"):
        return

    start = time.time()
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO error_groups (
                        fingerprint, service, severity, example_message,
                        first_seen, last_seen, occurrences
                    ) VALUES (
                        %(fingerprint)s, %(service)s, %(severity)s,
                        %(message)s, %(timestamp)s, %(timestamp)s, 1
                    )
                    ON CONFLICT (fingerprint) DO UPDATE SET
                        last_seen = EXCLUDED.last_seen,
                        occurrences = error_groups.occurrences + 1,
                        updated_at = NOW()
                    """,
                    {
                        "fingerprint": fingerprint,
                        "service": event["service"],
                        "severity": severity,
                        "message": event["message"][:500],
                        "timestamp": event["timestamp"],
                    },
                )
                duration = time.time() - start
                DB_OPERATION_DURATION.labels(operation="upsert_error_group").observe(duration)
    except Exception as e:
        duration = time.time() - start
        DB_OPERATION_DURATION.labels(operation="upsert_error_group").observe(duration)
        DB_ERRORS.labels(operation="upsert_error_group").inc()
        logger.error(f"Failed to upsert error group: {e}", exc_info=True)


def insert_alert(alert_data):
    """Insert a new alert record."""
    start = time.time()
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO alerts (
                        rule, severity, current_value, threshold,
                        status, message, service, notification_status
                    ) VALUES (
                        %(rule)s, %(severity)s, %(current_value)s, %(threshold)s,
                        'active', %(message)s, %(service)s, 'pending'
                    ) RETURNING id
                    """,
                    alert_data,
                )
                alert_id = cur.fetchone()[0]
                duration = time.time() - start
                DB_OPERATION_DURATION.labels(operation="insert_alert").observe(duration)
                return str(alert_id)
    except Exception as e:
        duration = time.time() - start
        DB_OPERATION_DURATION.labels(operation="insert_alert").observe(duration)
        DB_ERRORS.labels(operation="insert_alert").inc()
        logger.error(f"Failed to insert alert: {e}", exc_info=True)
        return None


def get_recent_error_count(service, window_minutes=5):
    """Get error count for a service in the last N minutes."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM logs
                    WHERE service = %s
                    AND severity IN ('ERROR', 'CRITICAL')
                    AND timestamp > NOW() - make_interval(mins => %s)
                    """,
                    (service, int(window_minutes)),
                )
                return cur.fetchone()[0]
    except Exception as e:
        logger.error(f"get_recent_error_count failed: {e}", exc_info=True)
        return 0


def get_error_group_occurrences(fingerprint):
    """Get total occurrences of an error group."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT occurrences FROM error_groups WHERE fingerprint = %s",
                    (fingerprint,),
                )
                row = cur.fetchone()
                return row[0] if row else 0
    except Exception:
        return 0


def get_p95_latency(service, window_minutes=5):
    """Get P95 latency for a service in the last N minutes."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms)
                    FROM logs
                    WHERE service = %s
                    AND duration_ms IS NOT NULL
                    AND timestamp > NOW() - make_interval(mins => %s)
                    """,
                    (service, int(window_minutes)),
                )
                row = cur.fetchone()
                return row[0] if row and row[0] else 0
    except Exception as e:
        logger.error(f"get_p95_latency failed: {e}", exc_info=True)
        return 0


def get_recent_alert_count(rule, service, cooldown_minutes=5):
    """Check if a similar alert was recently triggered (cooldown)."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM alerts
                    WHERE rule = %s
                    AND service = %s
                    AND triggered_at > NOW() - make_interval(mins => %s)
                    """,
                    (rule, service, int(cooldown_minutes)),
                )
                return cur.fetchone()[0]
    except Exception as e:
        logger.error(f"get_recent_alert_count failed: {e}", exc_info=True)
        return 0
