"""
TelemetryScope — Processing Service
Alert rule evaluation and Lambda notification trigger.
"""

import os
import json
import logging
import threading
import requests
from botocore.exceptions import BotoCoreError, ClientError

from metrics import ALERTS_EVALUATED, ALERTS_TRIGGERED
from processors.database import (
    insert_alert,
    get_recent_error_count,
    get_error_group_occurrences,
    get_p95_latency,
    get_recent_alert_count,
)

logger = logging.getLogger("telemetryscope-processing")

# Simple in-memory config for MVP
ALERT_RULES = {
    "ERROR_RATE_HIGH": {
        "threshold": 50,  # 50 errors
        "window_minutes": 5,
        "cooldown_minutes": 15,
        "severity": "CRITICAL",
    },
    "REPEATED_ERROR": {
        "threshold": 100, # 100 occurrences of same fingerprint
        "cooldown_minutes": 60,
        "severity": "WARNING",
    },
    "P95_LATENCY_HIGH": {
        "threshold": 1000, # 1000ms
        "window_minutes": 5,
        "cooldown_minutes": 15,
        "severity": "WARNING",
    }
}


def evaluate_rules_async(event):
    """Evaluate alert rules asynchronously so ingestion is not blocked."""
    threading.Thread(target=_evaluate_rules, args=(event,), daemon=True).start()


def _evaluate_rules(event):
    """Core logic to evaluate rules against an event."""
    service = event.get("service")
    if not service:
        return

    # Evaluate REPEATED_ERROR
    _eval_repeated_error(event, service)
    
    # Evaluate ERROR_RATE_HIGH
    _eval_error_rate(service)
    
    # Evaluate P95_LATENCY_HIGH
    _eval_latency(event, service)


def _eval_repeated_error(event, service):
    rule = "REPEATED_ERROR"
    ALERTS_EVALUATED.labels(rule=rule).inc()
    
    fingerprint = event.get("fingerprint")
    if not fingerprint or event.get("severity") not in ("WARNING", "ERROR", "CRITICAL"):
        return
        
    config = ALERT_RULES[rule]
    occurrences = get_error_group_occurrences(fingerprint)
    
    if occurrences >= config["threshold"]:
        if get_recent_alert_count(rule, service, config["cooldown_minutes"]) == 0:
            _trigger_alert({
                "rule": rule,
                "severity": config["severity"],
                "current_value": occurrences,
                "threshold": config["threshold"],
                "message": f"Error group {fingerprint} occurred {occurrences} times",
                "service": service,
            })


def _eval_error_rate(service):
    rule = "ERROR_RATE_HIGH"
    ALERTS_EVALUATED.labels(rule=rule).inc()
    
    config = ALERT_RULES[rule]
    error_count = get_recent_error_count(service, config["window_minutes"])
    
    if error_count >= config["threshold"]:
        if get_recent_alert_count(rule, service, config["cooldown_minutes"]) == 0:
            _trigger_alert({
                "rule": rule,
                "severity": config["severity"],
                "current_value": error_count,
                "threshold": config["threshold"],
                "message": f"{error_count} errors in the last {config['window_minutes']} minutes",
                "service": service,
            })


def _eval_latency(event, service):
    rule = "P95_LATENCY_HIGH"
    ALERTS_EVALUATED.labels(rule=rule).inc()
    
    duration = event.get("duration_ms")
    if duration is None:
        return
        
    config = ALERT_RULES[rule]
    p95 = get_p95_latency(service, config["window_minutes"])
    
    if p95 >= config["threshold"]:
        if get_recent_alert_count(rule, service, config["cooldown_minutes"]) == 0:
            _trigger_alert({
                "rule": rule,
                "severity": config["severity"],
                "current_value": p95,
                "threshold": config["threshold"],
                "message": f"P95 latency reached {p95:.1f}ms",
                "service": service,
            })


def _trigger_alert(alert_data):
    """Record alert in DB and trigger async Lambda."""
    logger.info(f"Triggering alert {alert_data['rule']} for {alert_data['service']}")
    ALERTS_TRIGGERED.labels(rule=alert_data["rule"], severity=alert_data["severity"]).inc()
    
    # Persist to DB
    alert_id = insert_alert(alert_data)
    if not alert_id:
        return
        
    alert_data["id"] = alert_id
    
    # Trigger notification async
    threading.Thread(target=_notify_lambda, args=(alert_data,), daemon=True).start()


def _notify_lambda(alert_data):
    """Invoke the AWS Lambda function for alert notification."""
    lambda_url = os.environ.get("LAMBDA_WEBHOOK_URL")
    if lambda_url:
        try:
            resp = requests.post(lambda_url, json=alert_data, timeout=5.0)
            if resp.status_code == 200:
                logger.info(f"Lambda notification sent for alert {alert_data['id']}")
            else:
                logger.error(f"Lambda webhook failed: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.error(f"Failed to invoke Lambda webhook: {e}")
            
    # Also support direct boto3 invocation if configured that way
    lambda_function = os.environ.get("LAMBDA_FUNCTION_NAME")
    if lambda_function:
        try:
            import boto3
            client = boto3.client('lambda', region_name=os.environ.get("AWS_REGION", "us-east-1"))
            client.invoke(
                FunctionName=lambda_function,
                InvocationType='Event', # Asynchronous
                Payload=json.dumps(alert_data)
            )
            logger.info(f"Lambda {lambda_function} invoked for alert {alert_data['id']}")
        except (ImportError, BotoCoreError, ClientError) as e:
            logger.error(f"Failed to invoke Lambda via boto3: {e}")
