"""
TelemetryScope — Ingestion Service
Main Flask application entry point.
"""

import os
from flask import Flask
from flask_cors import CORS

from logging_config import setup_logging
from routes.health import health_bp
from routes.ingestion import ingestion_bp


def create_app():
    """Application factory for the Ingestion Service."""
    app = Flask(__name__)

    # Configuration
    app.config["PROCESSING_SERVICE_URL"] = os.environ.get(
        "PROCESSING_SERVICE_URL", "http://localhost:8002"
    )
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024  # 1MB absolute max

    # Enable CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Setup structured logging
    logger = setup_logging("telemetryscope-ingestion")

    # Register blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(ingestion_bp)

    logger.info(
        "Ingestion Service started",
        extra={
            "processing_url": app.config["PROCESSING_SERVICE_URL"],
            "environment": os.environ.get("TELEMETRYSCOPE_ENV", "development"),
        },
    )

    return app


if __name__ == "__main__":
    # Development only — use Gunicorn in production
    app = create_app()
    port = int(os.environ.get("PORT", 8001))
    app.run(host="0.0.0.0", port=port, debug=False)
