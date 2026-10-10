"""
TelemetryScope — Ingestion Service
Structured logging configuration for consistent JSON output.
"""

import logging
import json
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Format log records as structured JSON."""

    def __init__(self, service_name="telemetryscope-ingestion"):
        super().__init__()
        self.service_name = service_name

    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add request context if available
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "trace_id"):
            log_entry["trace_id"] = record.trace_id

        # Add extra fields
        if hasattr(record, "endpoint"):
            log_entry["endpoint"] = record.endpoint
        if hasattr(record, "status_code"):
            log_entry["status_code"] = record.status_code
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms

        # Add exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
            }

        return json.dumps(log_entry)


def setup_logging(service_name="telemetryscope-ingestion", level=None):
    """Configure structured JSON logging for the service."""
    import os

    log_level = level or os.environ.get("TELEMETRYSCOPE_LOG_LEVEL", "INFO").upper()

    # Remove existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    # Create JSON handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter(service_name))
    handler.setLevel(getattr(logging, log_level, logging.INFO))

    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Reduce noise from third-party libraries
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    return logging.getLogger(service_name)
