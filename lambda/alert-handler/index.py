"""
TelemetryScope — AWS Lambda Alert Notification Handler
Receives structured alert events triggered by the Processing Service,
formats operational incident notifications, and routes them to Amazon SNS.
"""

import json
import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SNS_TOPIC_ARN = os.environ.get("ALERT_SNS_TOPIC_ARN")


def lambda_handler(event, context):
    """
    AWS Lambda entrypoint.
    Handles direct invocation payloads and HTTP API Gateway / webhook events.
    """
    logger.info("Received alert event: %s", json.dumps(event))

    # Parse body if passed via API Gateway / webhook
    if "body" in event:
        try:
            payload = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
        except Exception as e:
            logger.error("Failed to parse event body JSON: %s", str(e))
            return {
                "statusCode": 400,
                "body": json.dumps({"status": "error", "message": "Invalid JSON payload"}),
            }
    else:
        payload = event

    alert_id = payload.get("id", "unknown-alert-id")
    rule = payload.get("rule", "UNKNOWN_RULE")
    severity = payload.get("severity", "WARNING")
    service = payload.get("service", "unknown-service")
    current_value = payload.get("current_value", "N/A")
    threshold = payload.get("threshold", "N/A")
    message = payload.get("message", "No message provided")
    timestamp = payload.get("timestamp", datetime.now(timezone.utc).isoformat())

    formatted_notification = {
        "title": f"[{severity}] TelemetryScope Alert: {rule} on {service}",
        "alert_id": alert_id,
        "service": service,
        "rule": rule,
        "severity": severity,
        "current_value": current_value,
        "threshold": threshold,
        "message": message,
        "timestamp": timestamp,
        "status": "DISPATCHED",
    }

    logger.info("Formatted notification: %s", json.dumps(formatted_notification))

    # Publish to SNS if configured
    sns_message_id = None
    if SNS_TOPIC_ARN:
        try:
            import boto3
            sns_client = boto3.client("sns")
            response = sns_client.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=formatted_notification["title"][:100],
                Message=json.dumps(formatted_notification, indent=2),
            )
            sns_message_id = response.get("MessageId")
            logger.info("Published to SNS topic %s (MessageId: %s)", SNS_TOPIC_ARN, sns_message_id)
        except Exception as e:
            logger.error("Failed to publish to SNS topic %s: %s", SNS_TOPIC_ARN, str(e))
    else:
        logger.info("No ALERT_SNS_TOPIC_ARN configured; skipping SNS dispatch")

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "status": "success",
            "alert_id": alert_id,
            "sns_message_id": sns_message_id,
            "notification": formatted_notification,
        }),
    }
