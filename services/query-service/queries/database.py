"""
TelemetryScope — Query Service
Database connection and query operations.
"""

import os
import time
import logging
import psycopg2
import psycopg2.pool
import psycopg2.extras
from contextlib import contextmanager

from metrics import DB_QUERY_DURATION, DB_ERRORS, ROWS_RETURNED

logger = logging.getLogger("telemetryscope-query")

_pool = None


def get_pool():
    global _pool
    if _pool is None:
        db_url = os.environ.get(
            "DATABASE_URL",
            "postgresql://telemetryscope_reader:reader_password@localhost:5432/telemetryscope"
        )
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=20,
            dsn=db_url,
        )
        logger.info("Database connection pool created for Query Service")
    return _pool


def check_db_connection():
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
    pool = get_pool()
    conn = pool.getconn()
    try:
        # Read-only service, so no need for strict commits, but good practice
        yield conn
    finally:
        pool.putconn(conn)


def get_logs(filters, page=1, page_size=50):
    """Query logs with filters and pagination."""
    start_time = time.time()
    query_type = "get_logs"

    where_clauses = []
    params = []

    if filters.get("service"):
        where_clauses.append("service = %s")
        params.append(filters["service"])

    if filters.get("severity"):
        where_clauses.append("severity = %s")
        params.append(filters["severity"])

    if filters.get("environment"):
        where_clauses.append("environment = %s")
        params.append(filters["environment"])

    if filters.get("request_id"):
        where_clauses.append("request_id = %s")
        params.append(filters["request_id"])

    if filters.get("trace_id"):
        where_clauses.append("trace_id = %s")
        params.append(filters["trace_id"])

    if filters.get("status_code"):
        where_clauses.append("status_code = %s")
        params.append(filters["status_code"])

    if filters.get("search"):
        where_clauses.append("message ILIKE %s")
        params.append(f"%{filters['search']}%")

    if filters.get("start_time"):
        where_clauses.append("timestamp >= %s")
        params.append(filters["start_time"])

    if filters.get("end_time"):
        where_clauses.append("timestamp <= %s")
        params.append(filters["end_time"])

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Sort
    sort_field = "timestamp" if filters.get("sort") not in ("timestamp", "duration_ms", "status_code") else filters.get("sort")
    sort_order = "DESC" if filters.get("order", "desc").lower() == "desc" else "ASC"

    # Pagination
    offset = (page - 1) * page_size

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Get total count (can be expensive, might want to limit or estimate in real prod)
                count_sql = f"SELECT COUNT(*) FROM logs WHERE {where_sql}"
                cur.execute(count_sql, params)
                total_items = cur.fetchone()['count']

                # Get data
                sql = f"""
                    SELECT id, timestamp, received_at, service, environment,
                           severity, message, request_id, trace_id, endpoint,
                           status_code, duration_ms, fingerprint, metadata
                    FROM logs
                    WHERE {where_sql}
                    ORDER BY {sort_field} {sort_order}
                    LIMIT %s OFFSET %s
                """
                cur.execute(sql, params + [page_size, offset])
                rows = cur.fetchall()

                duration = time.time() - start_time
                DB_QUERY_DURATION.labels(query_type=query_type).observe(duration)
                ROWS_RETURNED.labels(query_type=query_type).observe(len(rows))

                return {
                    "data": [dict(r) for r in rows],
                    "meta": {
                        "pagination": {
                            "page": page,
                            "page_size": page_size,
                            "total_items": total_items,
                            "total_pages": (total_items + page_size - 1) // page_size,
                            "has_next": offset + len(rows) < total_items,
                            "has_prev": page > 1
                        }
                    }
                }
    except Exception as e:
        DB_ERRORS.labels(query_type=query_type).inc()
        logger.error(f"Error querying logs: {e}", exc_info=True)
        raise


def get_log_by_id(log_id):
    query_type = "get_log_by_id"
    start_time = time.time()
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM logs WHERE id = %s", (log_id,))
                row = cur.fetchone()
                duration = time.time() - start_time
                DB_QUERY_DURATION.labels(query_type=query_type).observe(duration)
                return dict(row) if row else None
    except Exception as e:
        DB_ERRORS.labels(query_type=query_type).inc()
        logger.error(f"Error getting log {log_id}: {e}", exc_info=True)
        raise


def get_overview_stats(filters):
    query_type = "get_overview_stats"
    start_time = time.time()

    where_clauses = []
    params = []

    if filters.get("service"):
        where_clauses.append("service = %s")
        params.append(filters["service"])

    if filters.get("environment"):
        where_clauses.append("environment = %s")
        params.append(filters["environment"])

    if filters.get("start_time"):
        where_clauses.append("timestamp >= %s")
        params.append(filters["start_time"])

    if filters.get("end_time"):
        where_clauses.append("timestamp <= %s")
        params.append(filters["end_time"])

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Basic aggregations
                sql = f"""
                    SELECT
                        COUNT(*) as total_events,
                        COUNT(CASE WHEN severity IN ('ERROR', 'CRITICAL') THEN 1 END) as error_count,
                        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY duration_ms) as p50_latency_ms,
                        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_latency_ms,
                        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY duration_ms) as p99_latency_ms,
                        MIN(timestamp) as min_time,
                        MAX(timestamp) as max_time
                    FROM logs
                    WHERE {where_sql}
                """
                cur.execute(sql, params)
                stats = cur.fetchone()

                # Calculate rate
                events_per_minute = 0
                if stats['total_events'] > 0 and stats['min_time'] and stats['max_time']:
                    delta_minutes = (stats['max_time'] - stats['min_time']).total_seconds() / 60.0
                    if delta_minutes > 0:
                        events_per_minute = stats['total_events'] / delta_minutes

                error_rate = 0
                if stats['total_events'] > 0:
                    error_rate = stats['error_count'] / stats['total_events']

                # Severity distribution
                sev_sql = f"""
                    SELECT severity, COUNT(*) as count
                    FROM logs
                    WHERE {where_sql}
                    GROUP BY severity
                """
                cur.execute(sev_sql, params)
                sev_rows = cur.fetchall()
                sev_dist = {r['severity']: r['count'] for r in sev_rows}

                # Alerts
                cur.execute("SELECT COUNT(*) FROM alerts WHERE status = 'active'")
                active_alerts = cur.fetchone()['count']

                duration = time.time() - start_time
                DB_QUERY_DURATION.labels(query_type=query_type).observe(duration)

                return {
                    "total_events": stats['total_events'],
                    "events_per_minute": round(events_per_minute, 2),
                    "error_rate": round(error_rate, 4),
                    "error_count": stats['error_count'],
                    "p50_latency_ms": round(stats['p50_latency_ms'] or 0, 2),
                    "p95_latency_ms": round(stats['p95_latency_ms'] or 0, 2),
                    "p99_latency_ms": round(stats['p99_latency_ms'] or 0, 2),
                    "active_alerts": active_alerts,
                    "severity_distribution": sev_dist
                }
    except Exception as e:
        DB_ERRORS.labels(query_type=query_type).inc()
        logger.error(f"Error getting overview stats: {e}", exc_info=True)
        raise


def get_timeline_stats(filters, interval='1 minute'):
    query_type = "get_timeline_stats"
    start_time = time.time()

    where_clauses = []
    params = []

    if filters.get("service"):
        where_clauses.append("service = %s")
        params.append(filters["service"])

    if filters.get("start_time"):
        where_clauses.append("timestamp >= %s")
        params.append(filters["start_time"])

    if filters.get("end_time"):
        where_clauses.append("timestamp <= %s")
        params.append(filters["end_time"])

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # PostgreSQL time_bucket or date_trunc
                sql = f"""
                    SELECT
                        date_trunc('minute', timestamp) AS bucket,
                        COUNT(*) as total,
                        COUNT(CASE WHEN severity IN ('ERROR', 'CRITICAL') THEN 1 END) as errors,
                        AVG(duration_ms) as avg_duration_ms,
                        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_duration_ms
                    FROM logs
                    WHERE {where_sql}
                    GROUP BY bucket
                    ORDER BY bucket ASC
                """
                cur.execute(sql, params)
                rows = cur.fetchall()

                duration = time.time() - start_time
                DB_QUERY_DURATION.labels(query_type=query_type).observe(duration)

                points = []
                for r in rows:
                    points.append({
                        "timestamp": r['bucket'].isoformat(),
                        "total": r['total'],
                        "errors": r['errors'],
                        "avg_duration_ms": round(r['avg_duration_ms'] or 0, 2),
                        "p95_duration_ms": round(r['p95_duration_ms'] or 0, 2)
                    })

                return {
                    "interval": interval,
                    "points": points
                }
    except Exception as e:
        DB_ERRORS.labels(query_type=query_type).inc()
        logger.error(f"Error getting timeline stats: {e}", exc_info=True)
        raise


def get_error_groups(filters, page=1, page_size=50):
    query_type = "get_error_groups"
    start_time = time.time()

    where_clauses = []
    params = []

    if filters.get("service"):
        where_clauses.append("service = %s")
        params.append(filters["service"])

    if filters.get("severity"):
        where_clauses.append("severity = %s")
        params.append(filters["severity"])

    if filters.get("status"):
        where_clauses.append("status = %s")
        params.append(filters["status"])

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    sort_field = filters.get("sort", "last_seen")
    if sort_field not in ("last_seen", "occurrences", "first_seen"):
        sort_field = "last_seen"

    offset = (page - 1) * page_size

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                count_sql = f"SELECT COUNT(*) FROM error_groups WHERE {where_sql}"
                cur.execute(count_sql, params)
                total_items = cur.fetchone()['count']

                sql = f"""
                    SELECT * FROM error_groups
                    WHERE {where_sql}
                    ORDER BY {sort_field} DESC
                    LIMIT %s OFFSET %s
                """
                cur.execute(sql, params + [page_size, offset])
                rows = cur.fetchall()

                duration = time.time() - start_time
                DB_QUERY_DURATION.labels(query_type=query_type).observe(duration)

                return {
                    "data": [dict(r) for r in rows],
                    "meta": {
                        "pagination": {
                            "page": page,
                            "page_size": page_size,
                            "total_items": total_items,
                            "total_pages": (total_items + page_size - 1) // page_size
                        }
                    }
                }
    except Exception as e:
        DB_ERRORS.labels(query_type=query_type).inc()
        logger.error(f"Error getting error groups: {e}", exc_info=True)
        raise


def get_error_group_details(fingerprint):
    query_type = "get_error_group_details"
    start_time = time.time()
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM error_groups WHERE fingerprint = %s", (fingerprint,))
                group = cur.fetchone()

                if not group:
                    return None

                # Fetch recent examples
                cur.execute(
                    """
                    SELECT id, timestamp, message, request_id, endpoint
                    FROM logs
                    WHERE fingerprint = %s
                    ORDER BY timestamp DESC LIMIT 10
                    """,
                    (fingerprint,)
                )
                recent_events = [dict(r) for r in cur.fetchall()]

                # Fetch affected endpoints
                cur.execute(
                    """
                    SELECT endpoint, COUNT(*) as count
                    FROM logs
                    WHERE fingerprint = %s AND endpoint IS NOT NULL
                    GROUP BY endpoint
                    ORDER BY count DESC LIMIT 5
                    """,
                    (fingerprint,)
                )
                affected_endpoints = [r['endpoint'] for r in cur.fetchall()]

                result = dict(group)
                result['recent_events'] = recent_events
                result['affected_endpoints'] = affected_endpoints

                duration = time.time() - start_time
                DB_QUERY_DURATION.labels(query_type=query_type).observe(duration)
                return result
    except Exception as e:
        DB_ERRORS.labels(query_type=query_type).inc()
        logger.error(f"Error getting error group details: {e}", exc_info=True)
        raise


def get_alerts(filters, page=1, page_size=50):
    query_type = "get_alerts"
    start_time = time.time()

    where_clauses = []
    params = []

    if filters.get("status") and filters.get("status") != "all":
        where_clauses.append("status = %s")
        params.append(filters["status"])

    if filters.get("severity"):
        where_clauses.append("severity = %s")
        params.append(filters["severity"])

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    offset = (page - 1) * page_size

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                count_sql = f"SELECT COUNT(*) FROM alerts WHERE {where_sql}"
                cur.execute(count_sql, params)
                total_items = cur.fetchone()['count']

                sql = f"""
                    SELECT * FROM alerts
                    WHERE {where_sql}
                    ORDER BY triggered_at DESC
                    LIMIT %s OFFSET %s
                """
                cur.execute(sql, params + [page_size, offset])
                rows = cur.fetchall()

                duration = time.time() - start_time
                DB_QUERY_DURATION.labels(query_type=query_type).observe(duration)

                return {
                    "data": [dict(r) for r in rows],
                    "meta": {
                        "pagination": {
                            "page": page,
                            "page_size": page_size,
                            "total_items": total_items,
                            "total_pages": (total_items + page_size - 1) // page_size
                        }
                    }
                }
    except Exception as e:
        DB_ERRORS.labels(query_type=query_type).inc()
        logger.error(f"Error getting alerts: {e}", exc_info=True)
        raise


def purge_demo_data(older_than_hours=24):
    """Purge demo data. Returns counts of deleted rows."""
    query_type = "purge_demo_data"
    start_time = time.time()
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Requires Writer or Admin role typically, but using whatever connection we have.
                # In a strict setup, Query Service might not be able to execute DELETE.
                # Assuming here the connection allows it for demo purposes, or we run this specifically.

                # Delete old logs
                cur.execute(
                    "DELETE FROM logs WHERE timestamp < NOW() - INTERVAL '%s hours'",
                    (older_than_hours,)
                )
                logs_deleted = cur.rowcount

                # Delete old resolved alerts
                cur.execute(
                    "DELETE FROM alerts WHERE status = 'resolved' AND triggered_at < NOW() - INTERVAL '%s hours'",
                    (older_than_hours,)
                )
                alerts_deleted = cur.rowcount

                conn.commit()

                duration = time.time() - start_time
                DB_QUERY_DURATION.labels(query_type=query_type).observe(duration)

                return {
                    "purged_events": logs_deleted,
                    "purged_alerts": alerts_deleted,
                    "purged_error_groups": 0 # Not deleting error groups to preserve history unless requested
                }
    except Exception as e:
        DB_ERRORS.labels(query_type=query_type).inc()
        logger.error(f"Error purging data: {e}", exc_info=True)
        raise

def get_deployments():
    """Get recent deployments"""
    query_type = "get_deployments"
    start_time = time.time()
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM deployments ORDER BY deployed_at DESC LIMIT 50"
                )
                rows = cur.fetchall()
                duration = time.time() - start_time
                DB_QUERY_DURATION.labels(query_type=query_type).observe(duration)
                return [dict(r) for r in rows]
    except Exception as e:
        DB_ERRORS.labels(query_type=query_type).inc()
        logger.error(f"Error getting deployments: {e}", exc_info=True)
        return []
