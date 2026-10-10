"""
TelemetryScope — Demo Workload
Generates realistic telemetry to demonstrate the platform.
"""

import os
import time
import uuid
import random
import threading
import requests
from flask import Flask, request, jsonify, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter, Histogram

app = Flask(__name__)

INGESTION_URL = os.environ.get("INGESTION_URL", "http://localhost:8001/api/v1/logs")
SERVICE_NAME = "demo-api"

# Thread-safe state with lock
_state_lock = threading.Lock()
demo_state = {
    "error_mode": False,
    "error_type": None,
    "error_count_remaining": 0,
    "slow_mode": False,
    "delay_ms": 0,
    "slow_count_remaining": 0,
    "traffic_burst": False,
    "burst_end_time": 0,
    "burst_rate": 0,
    "active_simulations": [],
    "_stop_event": threading.Event(),
}

# Metrics
REQUESTS = Counter("demo_api_requests_total", "Total requests", ["endpoint", "status"])
LATENCY = Histogram("demo_api_request_duration_seconds", "Request latency", ["endpoint"])


def send_telemetry(severity, message, endpoint, status_code, duration_ms, exception_type=None):
    """Send telemetry to Ingestion Service."""
    payload = {
        "service": SERVICE_NAME,
        "environment": os.environ.get("TELEMETRYSCOPE_ENV", "demo"),
        "severity": severity,
        "message": message,
        "endpoint": endpoint,
        "status_code": status_code,
        "duration_ms": duration_ms,
        "metadata": {}
    }

    if exception_type:
        payload["metadata"]["exception_type"] = exception_type

    try:
        requests.post(INGESTION_URL, json=payload, timeout=2.0)
    except Exception as e:
        print(f"Failed to send telemetry: {e}")


def get_delay():
    with _state_lock:
        if demo_state["slow_mode"] and demo_state["slow_count_remaining"] > 0:
            demo_state["slow_count_remaining"] -= 1
            if demo_state["slow_count_remaining"] == 0:
                demo_state["slow_mode"] = False
            return demo_state["delay_ms"]
    return random.uniform(10, 50)


def handle_error_injection():
    with _state_lock:
        if demo_state["error_mode"] and demo_state["error_count_remaining"] > 0:
            demo_state["error_count_remaining"] -= 1
            if demo_state["error_count_remaining"] == 0:
                demo_state["error_mode"] = False

            error_type = demo_state["error_type"]
            if error_type == "database_timeout":
                return {
                    "severity": "ERROR",
                    "message": f"Database connection timeout for user {random.randint(1, 1000)} at {random.choice(['10.0.0.1', '192.168.1.50'])}",
                    "status_code": 500,
                    "exception": "ConnectionTimeout"
                }
            elif error_type == "payment_failed":
                return {
                    "severity": "WARNING",
                    "message": f"Payment gateway rejected card ending in {random.randint(1000, 9999)}",
                    "status_code": 402,
                    "exception": "PaymentDeclined"
                }
            else:
                return {
                    "severity": "ERROR",
                    "message": "Internal Server Error during processing",
                    "status_code": 500,
                    "exception": "InternalError"
                }
    return None


@app.route("/health")
def health():
    """Health check for Kubernetes liveness/readiness probes."""
    return jsonify({
        "status": "healthy",
        "service": "telemetryscope-demo",
        "uptime": "ok"
    }), 200


@app.route("/demo/normal")
def normal_request():
    start = time.time()

    err = handle_error_injection()
    delay = get_delay()
    time.sleep(delay / 1000.0)

    duration = (time.time() - start) * 1000

    if err:
        send_telemetry(err["severity"], err["message"], "/demo/normal", err["status_code"], duration, err["exception"])
        REQUESTS.labels(endpoint="/demo/normal", status=str(err["status_code"])).inc()
        LATENCY.labels(endpoint="/demo/normal").observe(duration / 1000.0)
        return jsonify({"error": err["exception"]}), err["status_code"]

    send_telemetry("INFO", "Normal request processed successfully", "/demo/normal", 200, duration)
    REQUESTS.labels(endpoint="/demo/normal", status="200").inc()
    LATENCY.labels(endpoint="/demo/normal").observe(duration / 1000.0)
    return jsonify({"status": "success", "delay_ms": round(duration, 2)})


# --- Self-executing simulation helpers ---

def _execute_error_simulation(error_type, count, stop_event):
    """Generate the specified number of error events immediately via the ingestion pipeline."""
    sim_id = f"error-{error_type}-{int(time.time())}"
    with _state_lock:
        demo_state["active_simulations"].append({"id": sim_id, "type": "error", "total": count, "remaining": count})

    for i in range(count):
        if stop_event.is_set():
            break

        start = time.time()
        # Simulate realistic request processing time
        delay_ms = random.uniform(50, 200)
        time.sleep(delay_ms / 1000.0)
        duration = (time.time() - start) * 1000

        if error_type == "database_timeout":
            send_telemetry(
                "ERROR",
                f"Database connection timeout for user {random.randint(1, 1000)} at {random.choice(['10.0.0.1', '192.168.1.50'])}",
                "/demo/normal", 500, duration, "ConnectionTimeout"
            )
        elif error_type == "payment_failed":
            send_telemetry(
                "WARNING",
                f"Payment gateway rejected card ending in {random.randint(1000, 9999)}",
                "/demo/normal", 402, duration, "PaymentDeclined"
            )
        else:
            send_telemetry(
                "ERROR",
                "Internal Server Error during processing",
                "/demo/normal", 500, duration, "InternalError"
            )

        with _state_lock:
            for sim in demo_state["active_simulations"]:
                if sim["id"] == sim_id:
                    sim["remaining"] = count - i - 1
                    break

    with _state_lock:
        demo_state["active_simulations"] = [s for s in demo_state["active_simulations"] if s["id"] != sim_id]


def _execute_slow_simulation(count, delay_ms, stop_event):
    """Generate slow requests with high latency that traverse the full pipeline."""
    sim_id = f"slow-{delay_ms}ms-{int(time.time())}"
    with _state_lock:
        demo_state["active_simulations"].append({"id": sim_id, "type": "slow", "total": count, "remaining": count})

    for i in range(count):
        if stop_event.is_set():
            break

        start = time.time()
        time.sleep(delay_ms / 1000.0)
        duration = (time.time() - start) * 1000

        send_telemetry(
            "INFO",
            f"Slow request completed after {round(duration)}ms delay",
            "/demo/normal", 200, duration
        )

        with _state_lock:
            for sim in demo_state["active_simulations"]:
                if sim["id"] == sim_id:
                    sim["remaining"] = count - i - 1
                    break

    with _state_lock:
        demo_state["active_simulations"] = [s for s in demo_state["active_simulations"] if s["id"] != sim_id]


# --- Control Endpoints (called by Query Service) ---

@app.route("/demo/error", methods=["POST"])
def inject_error():
    data = request.json or {}
    count = data.get("count", 10)
    error_type = data.get("error_type", "database_timeout")

    # Also arm the flag for any manual /demo/normal requests
    with _state_lock:
        demo_state["error_mode"] = True
        demo_state["error_count_remaining"] = count
        demo_state["error_type"] = error_type

    # Self-execute: fire error events immediately in background
    stop_event = demo_state["_stop_event"]
    stop_event.clear()
    threading.Thread(
        target=_execute_error_simulation,
        args=(error_type, count, stop_event),
        daemon=True
    ).start()

    return jsonify({
        "status": "success",
        "data": {
            "triggered": count,
            "error_type": error_type,
            "mode": "self_executing",
            "message": f"Generating {count} {error_type} events in background"
        }
    })


@app.route("/demo/slow", methods=["POST"])
def inject_slow():
    data = request.json or {}
    count = data.get("count", 5)
    delay_ms = data.get("delay_ms", 3000)

    with _state_lock:
        demo_state["slow_mode"] = True
        demo_state["slow_count_remaining"] = count
        demo_state["delay_ms"] = delay_ms

    # Self-execute: fire slow events immediately in background
    stop_event = demo_state["_stop_event"]
    stop_event.clear()
    threading.Thread(
        target=_execute_slow_simulation,
        args=(count, delay_ms, stop_event),
        daemon=True
    ).start()

    return jsonify({
        "status": "success",
        "data": {
            "triggered": count,
            "delay_ms": delay_ms,
            "mode": "self_executing",
            "message": f"Generating {count} requests with {delay_ms}ms delay in background"
        }
    })


def background_traffic(stop_event):
    """Generate traffic at specified rate until burst_end_time or stop_event."""
    while time.time() < demo_state["burst_end_time"] and not stop_event.is_set():
        try:
            # Use localhost since we're inside the same pod/container
            requests.get("http://127.0.0.1:8080/demo/normal", timeout=5.0)
        except Exception:
            pass
        rate = demo_state["burst_rate"]
        if rate > 0:
            time.sleep(1.0 / rate)
        else:
            break
    with _state_lock:
        demo_state["traffic_burst"] = False
        demo_state["active_simulations"] = [s for s in demo_state["active_simulations"] if s["type"] != "traffic"]


@app.route("/demo/traffic", methods=["POST"])
def inject_traffic():
    data = request.json or {}
    duration = data.get("duration_seconds", 60)
    rate = data.get("rate_per_second", 50)

    stop_event = demo_state["_stop_event"]
    stop_event.clear()

    with _state_lock:
        demo_state["traffic_burst"] = True
        demo_state["burst_end_time"] = time.time() + duration
        demo_state["burst_rate"] = rate
        demo_state["active_simulations"].append({
            "id": f"traffic-{rate}rps-{int(time.time())}",
            "type": "traffic",
            "rate": rate,
            "duration": duration,
            "remaining_seconds": duration
        })

    threading.Thread(target=background_traffic, args=(stop_event,), daemon=True).start()
    return jsonify({
        "status": "success",
        "data": {
            "bursting": True,
            "duration": duration,
            "rate": rate,
            "message": f"Generating {rate} RPS for {duration}s in background"
        }
    })


@app.route("/demo/reset", methods=["POST"])
def reset_demo():
    with _state_lock:
        demo_state["error_mode"] = False
        demo_state["slow_mode"] = False
        demo_state["traffic_burst"] = False
        demo_state["burst_end_time"] = 0
        demo_state["error_count_remaining"] = 0
        demo_state["slow_count_remaining"] = 0
        demo_state["active_simulations"] = []
    # Signal all background threads to stop
    demo_state["_stop_event"].set()
    return jsonify({"status": "success", "data": {"reset": True, "message": "All injections stopped"}})


@app.route("/demo/status")
def status():
    with _state_lock:
        safe_state = {k: v for k, v in demo_state.items() if not k.startswith("_")}
    return jsonify(safe_state)


@app.route("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
