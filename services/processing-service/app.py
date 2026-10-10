"""
TelemetryScope — Processing Service
Main Flask application entry point.
"""

import os
import time
from flask import Flask, request, jsonify, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from logging_config import setup_logging
from metrics import (
    REQUEST_COUNT,
    REQUEST_LATENCY,
    EVENTS_PROCESSED,
    PROCESSING_DURATION,
    SERVICE_INFO
)
from fingerprint import compute_fingerprint
from processors.database import insert_log_event, upsert_error_group, check_db_connection
from processors.alerts import evaluate_rules_async

logger = setup_logging("telemetryscope-processing")

# Service info
_start_time = time.time()
_version = os.environ.get("TELEMETRYSCOPE_VERSION", "0.1.0")
_commit_sha = os.environ.get("TELEMETRYSCOPE_COMMIT_SHA", "development")
_environment = os.environ.get("TELEMETRYSCOPE_ENV", "development")

SERVICE_INFO.info({
    "version": _version,
    "commit_sha": _commit_sha,
    "environment": _environment,
})


def create_app():
    app = Flask(__name__)

    @app.route("/health")
    def health():
        return jsonify({
            "status": "healthy",
            "service": "telemetryscope-processing",
            "uptime_seconds": round(time.time() - _start_time, 1),
        }), 200

    @app.route("/ready")
    def ready():
        db_ready = check_db_connection()
        status_code = 200 if db_ready else 503
        return jsonify({
            "status": "ready" if db_ready else "not_ready",
            "service": "telemetryscope-processing",
            "checks": {
                "database": "connected" if db_ready else "unreachable"
            },
        }), status_code

    @app.route("/version")
    def version():
        return jsonify({
            "service": "telemetryscope-processing",
            "version": _version,
            "commit_sha": _commit_sha,
            "environment": _environment,
        }), 200

    @app.route("/metrics")
    def metrics():
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

    @app.route("/internal/process", methods=["POST"])
    def process_event():
        start_time = time.time()
        
        try:
            event = request.get_json(force=True)
            if not event:
                return jsonify({"status": "error", "message": "Invalid JSON"}), 400
        except Exception:
            REQUEST_COUNT.labels(method="POST", endpoint="/internal/process", status="400").inc()
            return jsonify({"status": "error", "message": "Invalid JSON"}), 400

        req_id = request.headers.get("X-Request-ID") or event.get("request_id", "unknown")
        
        try:
            # 1. Compute fingerprint for grouping
            fingerprint = compute_fingerprint(event)
            event["fingerprint"] = fingerprint

            # 2. Persist log event
            event_id = insert_log_event(event)

            # 3. Update error groups if applicable
            upsert_error_group(event)
            
            # 4. Evaluate alerts asynchronously
            evaluate_rules_async(event)

            # Metrics
            duration = time.time() - start_time
            PROCESSING_DURATION.observe(duration)
            REQUEST_LATENCY.labels(method="POST", endpoint="/internal/process").observe(duration)
            REQUEST_COUNT.labels(method="POST", endpoint="/internal/process", status="200").inc()
            
            EVENTS_PROCESSED.labels(
                service=event.get("service", "unknown"),
                severity=event.get("severity", "INFO"),
            ).inc()

            return jsonify({
                "status": "success",
                "data": {
                    "id": event_id,
                    "fingerprint": fingerprint,
                    "processed": True
                }
            }), 200

        except Exception as e:
            logger.error("Error processing event", exc_info=True, extra={"request_id": req_id})
            duration = time.time() - start_time
            REQUEST_LATENCY.labels(method="POST", endpoint="/internal/process").observe(duration)
            REQUEST_COUNT.labels(method="POST", endpoint="/internal/process", status="500").inc()
            return jsonify({
                "status": "error",
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }), 500

    logger.info("Processing Service started", extra={"environment": _environment})
    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 8002))
    app.run(host="0.0.0.0", port=port, debug=False)
