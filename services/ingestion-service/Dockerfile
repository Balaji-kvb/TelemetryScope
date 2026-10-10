FROM python:3.11-slim

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
EXPOSE 8001

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8001

# Run with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8001", "--workers", "4", "--threads", "2", "--timeout", "30", "--access-logfile", "-", "--error-logfile", "-", "app:create_app()"]
