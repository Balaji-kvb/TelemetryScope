"""
TelemetryScope — Ingestion Service
Health, readiness, version, and metrics endpoints.
"""

import os
import time
import logging
import requests
from flask import Blueprint, jsonify, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from metrics import SERVICE_INFO

logger = logging.getLogger("telemetryscope-ingestion")

health_bp = Blueprint("health", __name__)

# Track service start time
_start_time = time.time()

# Service info
_version = os.environ.get("TELEMETRYSCOPE_VERSION", "0.1.0")
_commit_sha = os.environ.get("TELEMETRYSCOPE_COMMIT_SHA", "development")
_environment = os.environ.get("TELEMETRYSCOPE_ENV", "development")
_build_time = os.environ.get("TELEMETRYSCOPE_BUILD_TIME", "unknown")

SERVICE_INFO.info({
    "version": _version,
    "commit_sha": _commit_sha,
    "environment": _environment,
})


@health_bp.route("/health")
def health():
    """Liveness check — is the process alive?"""
    return jsonify({
        "status": "healthy",
        "service": "telemetryscope-ingestion",
        "uptime_seconds": round(time.time() - _start_time, 1),
    }), 200


@health_bp.route("/ready")
def ready():
    """Readiness check — can the service accept traffic?
    Checks if the Processing Service is reachable.
    """
    processing_url = os.environ.get(
        "PROCESSING_SERVICE_URL", "http://localhost:8002"
    )

    checks = {}
    is_ready = True

    # Check Processing Service
    try:
        resp = requests.get(f"{processing_url}/health", timeout=2.0)
        if resp.status_code == 200:
            checks["processing_service"] = "reachable"
        else:
            checks["processing_service"] = f"unhealthy (status {resp.status_code})"
            is_ready = False
    except requests.exceptions.RequestException:
        checks["processing_service"] = "unreachable"
        is_ready = False

    status_code = 200 if is_ready else 503
    return jsonify({
        "status": "ready" if is_ready else "not_ready",
        "service": "telemetryscope-ingestion",
        "checks": checks,
    }), status_code


@health_bp.route("/version")
def version():
    """Return service version information."""
    return jsonify({
        "service": "telemetryscope-ingestion",
        "version": _version,
        "commit_sha": _commit_sha,
        "environment": _environment,
        "build_time": _build_time,
    }), 200


@health_bp.route("/metrics")
def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        generate_latest(),
        mimetype=CONTENT_TYPE_LATEST,
    )
