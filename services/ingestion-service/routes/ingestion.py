"""
TelemetryScope — Ingestion Service
Telemetry ingestion routes: single event and batch event endpoints.
"""

import uuid
import time
import logging
import requests
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, current_app

from validators.payload import (
    validate_event,
    validate_batch,
    MAX_PAYLOAD_SIZE,
    MAX_BATCH_PAYLOAD_SIZE,
)
from metrics import (
    REQUEST_COUNT,
    REQUEST_LATENCY,
    EVENTS_ACCEPTED,
    EVENTS_REJECTED,
    EVENTS_FORWARDED,
    FORWARD_ERRORS,
    FORWARD_LATENCY,
    BATCH_SIZE,
)

logger = logging.getLogger("telemetryscope-ingestion")

ingestion_bp = Blueprint("ingestion", __name__)


def generate_request_id():
    """Generate a unique request ID."""
    return f"req-{uuid.uuid4().hex[:8]}"


def make_response_envelope(status, data=None, error=None, request_id=None):
    """Create a consistent response envelope."""
    response = {
        "status": status,
        "meta": {
            "request_id": request_id or "unknown",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }
    if data is not None:
        response["data"] = data
    if error is not None:
        response["error"] = error
    return response


def forward_to_processing(event_data, request_id):
    """Forward a validated event to the Processing Service.
    Non-blocking: if Processing fails, log the error but don't fail the request.
    """
    processing_url = current_app.config.get(
        "PROCESSING_SERVICE_URL", "http://localhost:8002"
    )
    url = f"{processing_url}/internal/process"

    start = time.time()
    try:
        resp = requests.post(
            url,
            json=event_data,
            headers={"X-Request-ID": request_id},
            timeout=5.0,
        )
        duration = time.time() - start
        FORWARD_LATENCY.observe(duration)

        if resp.status_code == 200:
            EVENTS_FORWARDED.inc()
            return True
        else:
            FORWARD_ERRORS.inc()
            logger.error(
                "Processing service returned error",
                extra={
                    "request_id": request_id,
                    "status_code": resp.status_code,
                    "response": resp.text[:500],
                },
            )
            return False
    except requests.exceptions.RequestException as e:
        duration = time.time() - start
        FORWARD_LATENCY.observe(duration)
        FORWARD_ERRORS.inc()
        logger.error(
            "Failed to forward to Processing Service",
            extra={"request_id": request_id, "error": str(e)},
        )
        return False


@ingestion_bp.route("/api/v1/logs", methods=["POST"])
def ingest_single():
    """Accept a single telemetry event."""
    start_time = time.time()

    # Check payload size
    content_length = request.content_length or 0
    if content_length > MAX_PAYLOAD_SIZE:
        REQUEST_COUNT.labels(method="POST", endpoint="/api/v1/logs", status="413").inc()
        EVENTS_REJECTED.labels(reason="payload_too_large").inc()
        return jsonify(make_response_envelope(
            "error",
            error={
                "code": "PAYLOAD_TOO_LARGE",
                "message": f"Request body exceeds {MAX_PAYLOAD_SIZE // 1024}KB limit",
            },
        )), 413

    # Parse JSON
    try:
        payload = request.get_json(force=True)
    except Exception:
        REQUEST_COUNT.labels(method="POST", endpoint="/api/v1/logs", status="400").inc()
        EVENTS_REJECTED.labels(reason="invalid_json").inc()
        return jsonify(make_response_envelope(
            "error",
            error={
                "code": "VALIDATION_ERROR",
                "message": "Invalid JSON payload",
            },
        )), 400

    if payload is None:
        REQUEST_COUNT.labels(method="POST", endpoint="/api/v1/logs", status="400").inc()
        EVENTS_REJECTED.labels(reason="empty_payload").inc()
        return jsonify(make_response_envelope(
            "error",
            error={
                "code": "VALIDATION_ERROR",
                "message": "Empty or invalid JSON payload",
            },
        )), 400

    # Generate or use provided request_id
    req_id = (
        request.headers.get("X-Request-ID")
        or payload.get("request_id")
        or generate_request_id()
    )

    # Validate
    validated, errors = validate_event(payload)

    if errors:
        REQUEST_COUNT.labels(method="POST", endpoint="/api/v1/logs", status="400").inc()
        EVENTS_REJECTED.labels(reason="validation_error").inc()
        duration = time.time() - start_time
        REQUEST_LATENCY.labels(method="POST", endpoint="/api/v1/logs").observe(duration)

        return jsonify(make_response_envelope(
            "error",
            error={
                "code": "VALIDATION_ERROR",
                "message": "Payload validation failed",
                "details": [e.to_dict() for e in errors],
            },
            request_id=req_id,
        )), 400

    # Attach server-generated fields
    received_at = datetime.now(timezone.utc).isoformat()
    validated["received_at"] = received_at
    validated["request_id"] = validated.get("request_id") or req_id

    # Forward to Processing Service
    forwarded = forward_to_processing(validated, req_id)

    # Track accepted event
    EVENTS_ACCEPTED.labels(
        service=validated.get("service", "unknown"),
        severity=validated.get("severity", "INFO"),
    ).inc()

    duration = time.time() - start_time
    REQUEST_LATENCY.labels(method="POST", endpoint="/api/v1/logs").observe(duration)
    REQUEST_COUNT.labels(method="POST", endpoint="/api/v1/logs", status="202").inc()

    logger.info(
        "Event accepted",
        extra={
            "request_id": req_id,
            "service": validated.get("service"),
            "severity": validated.get("severity"),
            "forwarded": forwarded,
            "duration_ms": round(duration * 1000, 2),
        },
    )

    return jsonify(make_response_envelope(
        "success",
        data={
            "request_id": req_id,
            "accepted": True,
            "forwarded": forwarded,
        },
        request_id=req_id,
    )), 202


@ingestion_bp.route("/api/v1/logs/batch", methods=["POST"])
def ingest_batch():
    """Accept a batch of telemetry events."""
    start_time = time.time()

    # Check payload size
    content_length = request.content_length or 0
    if content_length > MAX_BATCH_PAYLOAD_SIZE:
        REQUEST_COUNT.labels(method="POST", endpoint="/api/v1/logs/batch", status="413").inc()
        EVENTS_REJECTED.labels(reason="batch_too_large").inc()
        return jsonify(make_response_envelope(
            "error",
            error={
                "code": "PAYLOAD_TOO_LARGE",
                "message": f"Batch payload exceeds {MAX_BATCH_PAYLOAD_SIZE // (1024*1024)}MB limit",
            },
        )), 413

    # Parse JSON
    try:
        payload = request.get_json(force=True)
    except Exception:
        REQUEST_COUNT.labels(method="POST", endpoint="/api/v1/logs/batch", status="400").inc()
        return jsonify(make_response_envelope(
            "error",
            error={"code": "VALIDATION_ERROR", "message": "Invalid JSON payload"},
        )), 400

    req_id = request.headers.get("X-Request-ID") or generate_request_id()

    # Validate batch
    validated_events, batch_errors = validate_batch(payload)

    BATCH_SIZE.observe(len(validated_events) + len(batch_errors))

    # Forward accepted events
    received_at = datetime.now(timezone.utc).isoformat()
    forwarded_count = 0
    for event in validated_events:
        event["received_at"] = received_at
        event["request_id"] = event.get("request_id") or generate_request_id()
        if forward_to_processing(event, event["request_id"]):
            forwarded_count += 1
        EVENTS_ACCEPTED.labels(
            service=event.get("service", "unknown"),
            severity=event.get("severity", "INFO"),
        ).inc()

    for err in batch_errors:
        EVENTS_REJECTED.labels(reason="validation_error").inc()

    duration = time.time() - start_time
    REQUEST_LATENCY.labels(method="POST", endpoint="/api/v1/logs/batch").observe(duration)
    REQUEST_COUNT.labels(method="POST", endpoint="/api/v1/logs/batch", status="202").inc()

    logger.info(
        "Batch processed",
        extra={
            "request_id": req_id,
            "accepted": len(validated_events),
            "rejected": len(batch_errors),
            "forwarded": forwarded_count,
            "duration_ms": round(duration * 1000, 2),
        },
    )

    return jsonify(make_response_envelope(
        "success",
        data={
            "accepted": len(validated_events),
            "rejected": len(batch_errors),
            "forwarded": forwarded_count,
            "errors": batch_errors if batch_errors else [],
        },
        request_id=req_id,
    )), 202
