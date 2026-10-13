"""
Unit tests for AWS Lambda Alert Notification Handler.
"""

import json
from index import lambda_handler


def test_direct_invocation():
    sample_alert = {
        "id": "alert-test-12345",
        "rule": "ERROR_RATE_HIGH",
        "severity": "CRITICAL",
        "service": "checkout-service",
        "current_value": 70,
        "threshold": 50,
        "message": "70 errors observed in 5-minute window",
    }
    response = lambda_handler(sample_alert, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "success"
    assert body["alert_id"] == "alert-test-12345"
    assert body["notification"]["rule"] == "ERROR_RATE_HIGH"
    print("Direct invocation test PASSED!")


def test_api_gateway_event():
    event = {
        "body": json.dumps({
            "id": "alert-test-67890",
            "rule": "REPEATED_ERROR",
            "severity": "WARNING",
            "service": "order-service",
            "current_value": 105,
            "threshold": 100,
            "message": "Error fingerprint fc781ce1efd0b768 repeated 105 times",
        })
    }
    response = lambda_handler(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "success"
    assert body["alert_id"] == "alert-test-67890"
    print("API Gateway webhook test PASSED!")


if __name__ == "__main__":
    test_direct_invocation()
    test_api_gateway_event()
    print("All Lambda handler unit tests PASSED!")
