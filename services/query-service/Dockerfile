FROM python:3.11-slim

# Install postgres dependencies
RUN apt-get update && apt-get install -y libpq-dev && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Non-root user
RUN addgroup --system appgroup && adduser --system --group appuser

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Set permissions
RUN chown -R appuser:appgroup /app
USER appuser

# Expose port
EXPOSE 8003

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8003

# Run with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8003", "--workers", "4", "--threads", "4", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "app:create_app()"]
