"""
TelemetryScope — Query Service
Main Flask application entry point.
"""

import os
import time
import requests
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from logging_config import setup_logging
from metrics import REQUEST_COUNT, REQUEST_LATENCY, SERVICE_INFO
from queries.database import (
    check_db_connection, get_logs, get_log_by_id, get_overview_stats,
    get_timeline_stats, get_error_groups, get_error_group_details,
    get_alerts, purge_demo_data, get_deployments
)

logger = setup_logging("telemetryscope-query")

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


def make_response_envelope(status, data=None, error=None):
    response = {
        "status": status,
        "meta": {}
    }
    if data is not None:
        if isinstance(data, dict) and "meta" in data:
            response["meta"] = data["meta"]
            response["data"] = data["data"]
        else:
            response["data"] = data
    if error is not None:
        response["error"] = error
    return response


def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    @app.before_request
    def before_request():
        request.start_time = time.time()

    @app.after_request
    def after_request(response):
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            endpoint = request.endpoint or request.path
            REQUEST_LATENCY.labels(method=request.method, endpoint=endpoint).observe(duration)
            REQUEST_COUNT.labels(method=request.method, endpoint=endpoint, status=response.status_code).inc()
        return response

    # --- Operational Endpoints ---

    @app.route("/health")
    def health():
        return jsonify({
            "status": "healthy",
            "service": "telemetryscope-query",
            "uptime_seconds": round(time.time() - _start_time, 1),
        }), 200

    @app.route("/ready")
    def ready():
        db_ready = check_db_connection()
        status_code = 200 if db_ready else 503
        return jsonify({
            "status": "ready" if db_ready else "not_ready",
            "service": "telemetryscope-query",
            "checks": {
                "database": "connected" if db_ready else "unreachable"
            },
        }), status_code

    @app.route("/version")
    def version():
        return jsonify({
            "service": "telemetryscope-query",
            "version": _version,
            "commit_sha": _commit_sha,
            "environment": _environment,
        }), 200

    @app.route("/metrics")
    def metrics():
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

    # --- API Endpoints ---

    @app.route("/api/v1/logs", methods=["GET"])
    def api_get_logs():
        try:
            page = int(request.args.get("page", 1))
            page_size = min(int(request.args.get("page_size", 50)), 200)

            filters = {
                "service": request.args.get("service"),
                "severity": request.args.get("severity"),
                "environment": request.args.get("environment"),
                "start_time": request.args.get("start_time"),
                "end_time": request.args.get("end_time"),
                "search": request.args.get("search"),
                "request_id": request.args.get("request_id"),
                "trace_id": request.args.get("trace_id"),
                "status_code": request.args.get("status_code"),
                "sort": request.args.get("sort", "timestamp"),
                "order": request.args.get("order", "desc"),
            }

            result = get_logs(filters, page, page_size)
            return jsonify(make_response_envelope("success", data=result))
        except Exception as e:
            logger.error(f"Error serving logs: {e}")
            return jsonify(make_response_envelope("error", error={"code": "INTERNAL_ERROR", "message": str(e)})), 500

    @app.route("/api/v1/logs/<log_id>", methods=["GET"])
    def api_get_log(log_id):
        try:
            log = get_log_by_id(log_id)
            if not log:
                return jsonify(make_response_envelope("error", error={"code": "NOT_FOUND", "message": "Log not found"})), 404
            return jsonify(make_response_envelope("success", data=log))
        except Exception as e:
            return jsonify(make_response_envelope("error", error={"code": "INTERNAL_ERROR", "message": str(e)})), 500

    @app.route("/api/v1/logs/<log_id>/context", methods=["GET"])
    def api_get_log_context(log_id):
        # Simplistic implementation: just return the log for MVP
        try:
            log = get_log_by_id(log_id)
            if not log:
                return jsonify(make_response_envelope("error", error={"code": "NOT_FOUND", "message": "Log not found"})), 404

            # TODO: implement before/after queries based on timestamp
            return jsonify(make_response_envelope("success", data={
                "target": log,
                "before": [],
                "after": []
            }))
        except Exception as e:
            return jsonify(make_response_envelope("error", error={"code": "INTERNAL_ERROR", "message": str(e)})), 500

    @app.route("/api/v1/stats/overview", methods=["GET"])
    def api_get_overview():
        try:
            filters = {
                "service": request.args.get("service"),
                "environment": request.args.get("environment"),
                "start_time": request.args.get("start_time"),
                "end_time": request.args.get("end_time"),
            }
            stats = get_overview_stats(filters)
            return jsonify(make_response_envelope("success", data=stats))
        except Exception as e:
            return jsonify(make_response_envelope("error", error={"code": "INTERNAL_ERROR", "message": str(e)})), 500

    @app.route("/api/v1/stats/timeline", methods=["GET"])
    def api_get_timeline():
        try:
            filters = {
                "service": request.args.get("service"),
                "start_time": request.args.get("start_time"),
                "end_time": request.args.get("end_time"),
            }
            interval = request.args.get("interval", "1 minute")
            timeline = get_timeline_stats(filters, interval)
            return jsonify(make_response_envelope("success", data=timeline))
        except Exception as e:
            return jsonify(make_response_envelope("error", error={"code": "INTERNAL_ERROR", "message": str(e)})), 500

    @app.route("/api/v1/errors", methods=["GET"])
    def api_get_errors():
        try:
            page = int(request.args.get("page", 1))
            page_size = min(int(request.args.get("page_size", 50)), 200)

            filters = {
                "service": request.args.get("service"),
                "severity": request.args.get("severity"),
                "status": request.args.get("status"),
                "sort": request.args.get("sort", "last_seen"),
            }

            result = get_error_groups(filters, page, page_size)
            return jsonify(make_response_envelope("success", data=result))
        except Exception as e:
            return jsonify(make_response_envelope("error", error={"code": "INTERNAL_ERROR", "message": str(e)})), 500

    @app.route("/api/v1/errors/<fingerprint>", methods=["GET"])
    def api_get_error_details(fingerprint):
        try:
            details = get_error_group_details(fingerprint)
            if not details:
                return jsonify(make_response_envelope("error", error={"code": "NOT_FOUND", "message": "Error group not found"})), 404
            return jsonify(make_response_envelope("success", data=details))
        except Exception as e:
            return jsonify(make_response_envelope("error", error={"code": "INTERNAL_ERROR", "message": str(e)})), 500

    @app.route("/api/v1/alerts", methods=["GET"])
    def api_get_alerts():
        try:
            page = int(request.args.get("page", 1))
            page_size = min(int(request.args.get("page_size", 50)), 200)

            filters = {
                "status": request.args.get("status", "active"),
                "severity": request.args.get("severity"),
            }

            result = get_alerts(filters, page, page_size)
            return jsonify(make_response_envelope("success", data=result))
        except Exception as e:
            return jsonify(make_response_envelope("error", error={"code": "INTERNAL_ERROR", "message": str(e)})), 500

    @app.route("/api/v1/services", methods=["GET"])
    def api_get_services():
        # Minimal mock/aggregation for MVP. Real K8s integration requires metrics-server.
        services = [
            {
                "name": "telemetryscope-ingestion",
                "status": "healthy",
                "requests_per_second": 0,
                "error_rate": 0,
                "p95_latency_ms": 0,
                "replicas_ready": 1,
                "replicas_desired": 1,
            },
            {
                "name": "telemetryscope-processing",
                "status": "healthy",
                "requests_per_second": 0,
                "error_rate": 0,
                "p95_latency_ms": 0,
                "replicas_ready": 1,
                "replicas_desired": 1,
            },
            {
                "name": "telemetryscope-query",
                "status": "healthy",
                "requests_per_second": 0,
                "error_rate": 0,
                "p95_latency_ms": 0,
                "replicas_ready": 1,
    "replicas_desired": 1,
},
        ]
        return jsonify(make_response_envelope("success", data=services))

    @app.route("/api/v1/system/status", methods=["GET"])
    def api_get_system_status():
        db_ready = check_db_connection()
        return jsonify(make_response_envelope("success", data={
            "environment": _environment,
            "version": _version,
            "commit_sha": _commit_sha,
            "database": {"status": "connected" if db_ready else "unreachable"},
            "uptime_seconds": round(time.time() - _start_time, 1)
        }))

    @app.route("/api/v1/deployments", methods=["GET"])
    def api_get_deployments():
        try:
            deps = get_deployments()
            return jsonify(make_response_envelope("success", data=deps))
        except Exception as e:
            return jsonify(make_response_envelope("error", error={"code": "INTERNAL_ERROR", "message": str(e)})), 500

    # --- Demo Endpoints ---
    # These just call the demo-workload service if it's available.

    DEMO_API_URL = os.environ.get("DEMO_API_URL", "http://localhost:8080")

    @app.route("/api/v1/demo/error", methods=["POST"])
    def demo_error():
        try:
            payload = request.get_json(force=True) if request.data else {}
            resp = requests.post(f"{DEMO_API_URL}/demo/error", json=payload, timeout=30.0)
            return jsonify(resp.json()), resp.status_code
        except Exception as e:
            logger.error(f"Demo workload error: {e}")
            return jsonify(make_response_envelope("error", error={"code": "DEMO_ERROR", "message": str(e)})), 500

    @app.route("/api/v1/demo/slow", methods=["POST"])
    def demo_slow():
        try:
            payload = request.get_json(force=True) if request.data else {}
            resp = requests.post(f"{DEMO_API_URL}/demo/slow", json=payload, timeout=30.0)
            return jsonify(resp.json()), resp.status_code
        except Exception as e:
            return jsonify(make_response_envelope("error", error={"code": "DEMO_ERROR", "message": str(e)})), 500

    @app.route("/api/v1/demo/traffic", methods=["POST"])
    def demo_traffic():
        try:
            payload = request.get_json(force=True) if request.data else {}
            resp = requests.post(f"{DEMO_API_URL}/demo/traffic", json=payload, timeout=30.0)
            return jsonify(resp.json()), resp.status_code
        except Exception as e:
            return jsonify(make_response_envelope("error", error={"code": "DEMO_ERROR", "message": str(e)})), 500

    @app.route("/api/v1/demo/reset", methods=["POST"])
    def demo_reset():
        try:
            resp = requests.post(f"{DEMO_API_URL}/demo/reset", timeout=30.0)
            return jsonify(resp.json()), resp.status_code
        except Exception as e:
            return jsonify(make_response_envelope("error", error={"code": "DEMO_ERROR", "message": str(e)})), 500

    @app.route("/api/v1/demo/purge", methods=["POST"])
    def demo_purge():
        try:
            payload = request.get_json(force=True) if request.data else {}
            if not payload.get("confirm"):
                return jsonify(make_response_envelope("error", error={"code": "CONFIRMATION_REQUIRED", "message": "Set confirm=true to proceed with destructive purge"})), 400

            older_than = payload.get("older_than_hours", 24)
            result = purge_demo_data(older_than)
            return jsonify(make_response_envelope("success", data=result))
        except Exception as e:
            return jsonify(make_response_envelope("error", error={"code": "INTERNAL_ERROR", "message": str(e)})), 500


    logger.info("Query Service started", extra={"environment": _environment})
    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 8003))
    app.run(host="0.0.0.0", port=port, debug=False)
