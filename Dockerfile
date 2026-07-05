FROM python:3.14-slim

WORKDIR /app

# Install system deps (scipy needs build deps on slim images)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY backend/ backend/
COPY frontend/ frontend/

# Hugging Face Spaces sets PORT env var
EXPOSE 7860
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-7860}
