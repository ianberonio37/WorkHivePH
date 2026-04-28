# Engineering Calc Python API — Docker image
# Deploys to Railway or Render (free tier supports this image size)

FROM python:3.11-slim

# System dependencies for CoolProp compilation (if needed) and general build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libfreetype6-dev \
    libpng-dev \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer caching: only re-runs when
# requirements.txt changes, not on every code change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Railway injects PORT as an env var — app must bind to $PORT, not a hardcoded port
EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
