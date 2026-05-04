FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy necessary code
COPY worker/ ./worker/
COPY api/ ./api/
COPY shared/ ./shared/

ENV PYTHONPATH=/app

CMD ["python", "-m", "worker.main"]
