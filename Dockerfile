# Use Python 3.13 to match your local version
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies needed for psycopg2 and compilation
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Ste timezone
ENV TZ=Europe/Athens
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy project structure
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY queries/ ./queries/
COPY media/ ./media/
COPY tests/ ./tests/

# Create necessary directories
RUN mkdir -p logs data

# Set Python to run in unbuffered mode (see logs in real-time)
ENV PYTHONUNBUFFERED=1

# Run with scheduling enabled by default
CMD ["python", "-m", "src.events_alerts"]

# Optional: Add healthcheck to monitor container
HEALTHCHECK --interval=1h --timeout=10s --start-period=30s --retries=3 \
    CMD test -f /app/logs/events_alerts.log && \
        test $(find /app/logs/events_alerts.log -mmin -$(( ${SCHEDULE_FREQUENCY:-1} * 60 + 10 )) | wc -l) -eq 1 || exit 1
