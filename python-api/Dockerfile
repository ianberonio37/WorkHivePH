# Engineering Calc Python API — Docker image
# Deploys to Railway or Render (free tier supports this image size)

FROM python:3.11-slim

# System dependencies for CoolProp compilation (if needed) and general build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer caching: only re-runs when
# requirements.txt changes, not on every code change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Railway and Render inject PORT env var — uvicorn reads it
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
