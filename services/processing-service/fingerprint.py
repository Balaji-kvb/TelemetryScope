"""
TelemetryScope — Processing Service
Deterministic error fingerprinting using normalized message hashing.
"""

import re
import hashlib


# Normalization patterns: compiled once for performance
_PATTERNS = [
    # UUIDs (various formats)
    (re.compile(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    ), "{UUID}"),
    # Email addresses
    (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "{EMAIL}"),
    # IP addresses (v4)
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "{IP}"),
    # Hex strings (8+ chars, standalone)
    (re.compile(r"\b[0-9a-fA-F]{8,}\b"), "{HEX}"),
    # Quoted strings
    (re.compile(r'"[^"]*"'), "{STR}"),
    (re.compile(r"'[^']*'"), "{STR}"),
    # Floats (before integers to avoid partial matching)
    (re.compile(r"\b\d+\.\d+\b"), "{N}"),
    # Integers
    (re.compile(r"\b\d+\b"), "{N}"),
]


def normalize_message(message):
    """Normalize variable portions of a message for consistent fingerprinting.

    Replaces:
    - UUIDs → {UUID}
    - Emails → {EMAIL}
    - IPs → {IP}
    - Hex strings → {HEX}
    - Quoted strings → {STR}
    - Numbers → {N}
    """
    if not message:
        return ""

    normalized = message
    for pattern, replacement in _PATTERNS:
        normalized = pattern.sub(replacement, normalized)

    # Collapse multiple spaces
    normalized = re.sub(r"\s+", " ", normalized).strip()

    return normalized


def compute_fingerprint(event):
    """Compute a deterministic fingerprint for error grouping.

    Inputs:
    - service
    - severity
    - exception_type (from metadata)
    - normalized message
    - endpoint

    Returns 16-character hex string (first 16 chars of SHA-256).
    """
    service = event.get("service", "")
    severity = event.get("severity", "")
    metadata = event.get("metadata", {})
    exception_type = metadata.get("exception_type", "") if isinstance(metadata, dict) else ""
    message = event.get("message", "")
    endpoint = event.get("endpoint", "")

    normalized_msg = normalize_message(message)

    components = [
        str(service).lower(),
        str(severity).upper(),
        str(exception_type).lower(),
        normalized_msg.lower(),
        str(endpoint).lower() if endpoint else "",
    ]

    raw = "|".join(components)
    fingerprint = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    return fingerprint
