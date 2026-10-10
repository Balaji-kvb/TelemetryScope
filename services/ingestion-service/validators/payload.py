"""
TelemetryScope — Ingestion Service
Payload validation for incoming telemetry events.
"""

import re
import json
from datetime import datetime, timezone, timedelta
from dateutil import parser as date_parser


# --- Constants ---
MAX_PAYLOAD_SIZE = 64 * 1024  # 64 KB
MAX_BATCH_SIZE = 100
MAX_BATCH_PAYLOAD_SIZE = 1024 * 1024  # 1 MB
MAX_MESSAGE_LENGTH = 5000
MAX_SERVICE_LENGTH = 100
MAX_ENDPOINT_LENGTH = 500
MAX_METADATA_KEYS = 10
MAX_METADATA_SIZE = 1024  # 1 KB
MAX_FUTURE_HOURS = 24

SERVICE_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

VALID_SEVERITIES = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

SEVERITY_ALIASES = {
    "debug": "DEBUG",
    "info": "INFO",
    "information": "INFO",
    "warn": "WARNING",
    "warning": "WARNING",
    "error": "ERROR",
    "err": "ERROR",
    "critical": "CRITICAL",
    "fatal": "CRITICAL",
    "crit": "CRITICAL",
}

VALID_ENVIRONMENTS = {"development", "staging", "production", "demo"}

FORBIDDEN_METADATA_KEYS = {
    "password", "secret", "token", "authorization", "api_key",
    "access_key", "secret_key", "private_key", "credential",
    "ssn", "credit_card",
}

METADATA_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_]+$")


class ValidationError:
    """Represents a single field validation error."""

    def __init__(self, field, error):
        self.field = field
        self.error = error

    def to_dict(self):
        return {"field": self.field, "error": self.error}


def normalize_severity(severity_input):
    """Normalize severity string to canonical level.
    Returns (normalized, error_message).
    """
    if severity_input is None:
        return "INFO", None

    if not isinstance(severity_input, str):
        return None, f"Severity must be a string, got {type(severity_input).__name__}"

    normalized = SEVERITY_ALIASES.get(severity_input.lower().strip())
    if normalized:
        return normalized, None

    upper = severity_input.upper().strip()
    if upper in VALID_SEVERITIES:
        return upper, None

    return None, f"Invalid severity level: '{severity_input}'. Valid: {', '.join(sorted(VALID_SEVERITIES))}"


def normalize_timestamp(ts_input):
    """Parse and normalize a timestamp to UTC ISO format.
    Returns (datetime_obj, error_message).
    """
    if ts_input is None:
        return datetime.now(timezone.utc), None

    if not isinstance(ts_input, str):
        return None, f"Timestamp must be a string, got {type(ts_input).__name__}"

    try:
        parsed = date_parser.isoparse(ts_input)
        # Ensure timezone aware
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        # Convert to UTC
        parsed = parsed.astimezone(timezone.utc)

        # Reject timestamps too far in the future
        now = datetime.now(timezone.utc)
        if parsed > now + timedelta(hours=MAX_FUTURE_HOURS):
            return None, f"Timestamp is more than {MAX_FUTURE_HOURS}h in the future"

        return parsed, None
    except (ValueError, OverflowError) as e:
        return None, f"Invalid timestamp format: {str(e)}"


def validate_metadata(metadata):
    """Validate bounded metadata object.
    Returns list of ValidationErrors.
    """
    errors = []

    if metadata is None:
        return errors

    if not isinstance(metadata, dict):
        errors.append(ValidationError("metadata", f"Must be an object, got {type(metadata).__name__}"))
        return errors

    # Check key count
    if len(metadata) > MAX_METADATA_KEYS:
        errors.append(ValidationError("metadata", f"Too many keys: {len(metadata)} (max {MAX_METADATA_KEYS})"))

    # Check total size
    try:
        metadata_str = json.dumps(metadata)
        if len(metadata_str.encode("utf-8")) > MAX_METADATA_SIZE:
            errors.append(ValidationError("metadata", f"Total size exceeds {MAX_METADATA_SIZE} bytes"))
    except (TypeError, ValueError):
        errors.append(ValidationError("metadata", "Contains non-serializable values"))
        return errors

    for key, value in metadata.items():
        # Check key format
        if not isinstance(key, str) or not METADATA_KEY_PATTERN.match(key):
            errors.append(ValidationError(f"metadata.{key}", "Key must match [a-zA-Z0-9_]"))

        # Check key length
        if isinstance(key, str) and len(key) > 50:
            errors.append(ValidationError(f"metadata.{key}", "Key exceeds 50 character limit"))

        # Check forbidden keys
        if isinstance(key, str) and key.lower() in FORBIDDEN_METADATA_KEYS:
            errors.append(ValidationError(f"metadata.{key}", f"Forbidden metadata key: '{key}'"))

        # Check value types (no nested objects or arrays)
        if not isinstance(value, (str, int, float, bool)):
            errors.append(ValidationError(
                f"metadata.{key}",
                f"Value must be string, number, or boolean. Got {type(value).__name__}"
            ))

    return errors


def validate_event(payload):
    """Validate a single telemetry event payload.
    Returns (validated_data, list_of_errors).
    """
    errors = []

    if not isinstance(payload, dict):
        return None, [ValidationError("payload", "Must be a JSON object")]

    # --- Required: service ---
    service = payload.get("service")
    if not service:
        errors.append(ValidationError("service", "Required field missing"))
    elif not isinstance(service, str):
        errors.append(ValidationError("service", f"Must be a string, got {type(service).__name__}"))
    elif len(service) > MAX_SERVICE_LENGTH:
        errors.append(ValidationError("service", f"Exceeds {MAX_SERVICE_LENGTH} character limit"))
    elif not SERVICE_PATTERN.match(service):
        errors.append(ValidationError("service", "Must contain only alphanumeric, hyphens, and underscores"))

    # --- Required: message ---
    message = payload.get("message")
    if not message:
        errors.append(ValidationError("message", "Required field missing"))
    elif not isinstance(message, str):
        errors.append(ValidationError("message", f"Must be a string, got {type(message).__name__}"))
    elif len(message) > MAX_MESSAGE_LENGTH:
        errors.append(ValidationError("message", f"Exceeds {MAX_MESSAGE_LENGTH} character limit"))

    # --- Optional: severity ---
    severity, sev_error = normalize_severity(payload.get("severity"))
    if sev_error:
        errors.append(ValidationError("severity", sev_error))

    # --- Optional: timestamp ---
    timestamp, ts_error = normalize_timestamp(payload.get("timestamp"))
    if ts_error:
        errors.append(ValidationError("timestamp", ts_error))

    # --- Optional: environment ---
    environment = payload.get("environment", "development")
    if not isinstance(environment, str):
        errors.append(ValidationError("environment", f"Must be a string"))
    elif environment.lower() not in VALID_ENVIRONMENTS:
        errors.append(ValidationError(
            "environment",
            f"Invalid environment: '{environment}'. Valid: {', '.join(sorted(VALID_ENVIRONMENTS))}"
        ))
    else:
        environment = environment.lower()

    # --- Optional: endpoint ---
    endpoint = payload.get("endpoint")
    if endpoint is not None:
        if not isinstance(endpoint, str):
            errors.append(ValidationError("endpoint", "Must be a string"))
        elif len(endpoint) > MAX_ENDPOINT_LENGTH:
            errors.append(ValidationError("endpoint", f"Exceeds {MAX_ENDPOINT_LENGTH} character limit"))

    # --- Optional: status_code ---
    status_code = payload.get("status_code")
    if status_code is not None:
        if not isinstance(status_code, int):
            errors.append(ValidationError("status_code", "Must be an integer"))
        elif not (100 <= status_code <= 599):
            errors.append(ValidationError("status_code", "Must be between 100 and 599"))

    # --- Optional: duration_ms ---
    duration_ms = payload.get("duration_ms")
    if duration_ms is not None:
        if not isinstance(duration_ms, (int, float)):
            errors.append(ValidationError("duration_ms", "Must be a number"))
        elif duration_ms < 0:
            errors.append(ValidationError("duration_ms", "Must be non-negative"))

    # --- Optional: metadata ---
    metadata_errors = validate_metadata(payload.get("metadata"))
    errors.extend(metadata_errors)

    # --- Optional: request_id, trace_id ---
    request_id = payload.get("request_id")
    if request_id is not None and not isinstance(request_id, str):
        errors.append(ValidationError("request_id", "Must be a string"))

    trace_id = payload.get("trace_id")
    if trace_id is not None and not isinstance(trace_id, str):
        errors.append(ValidationError("trace_id", "Must be a string"))

    if errors:
        return None, errors

    # Build validated data
    validated = {
        "timestamp": timestamp.isoformat() if timestamp else datetime.now(timezone.utc).isoformat(),
        "service": service.strip(),
        "environment": environment,
        "severity": severity or "INFO",
        "message": message.strip(),
        "request_id": request_id,
        "trace_id": trace_id,
        "endpoint": endpoint.strip() if endpoint else None,
        "status_code": status_code,
        "duration_ms": float(duration_ms) if duration_ms is not None else None,
        "metadata": payload.get("metadata", {}),
    }

    return validated, []


def validate_batch(payload):
    """Validate a batch payload.
    Returns (list_of_validated, list_of_errors_with_index).
    """
    if not isinstance(payload, dict):
        return [], [{"index": -1, "error": "Payload must be a JSON object"}]

    events = payload.get("events")
    if not isinstance(events, list):
        return [], [{"index": -1, "error": "'events' must be an array"}]

    if len(events) == 0:
        return [], [{"index": -1, "error": "'events' array is empty"}]

    if len(events) > MAX_BATCH_SIZE:
        return [], [{"index": -1, "error": f"Batch exceeds {MAX_BATCH_SIZE} events"}]

    validated_events = []
    batch_errors = []

    for i, event in enumerate(events):
        validated, errors = validate_event(event)
        if errors:
            batch_errors.append({
                "index": i,
                "error": "; ".join(e.error for e in errors)
            })
        else:
            validated_events.append(validated)

    return validated_events, batch_errors
