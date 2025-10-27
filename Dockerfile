# Use Python 3.13 to match your local version
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies needed for psycopg2 and compilation
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy project structure
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY queries/ ./queries/
COPY media/ ./media/

# Create necessary directories
RUN mkdir -p logs data

# Set Python to run in unbuffered mode (see logs in real-time)
ENV PYTHONUNBUFFERED=1

# Default command - runs the main script as a module
CMD ["python", "-m", "src.events_alerts"]
