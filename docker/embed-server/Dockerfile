# WorkHive self-host embedding server — bge-small-en-v1.5 (384-dim), NO rate limit.
# Serves tools/embed_server.py so the edge's persona-knowledge query and the ingest
# tool use the SAME model -> one vector space. The model is baked into the image at
# build time, so the container starts instantly and needs no network at runtime.
#
# Build (from repo root):
#   docker build -f docker/embed-server/Dockerfile -t workhive-embed-server .
# Run (standalone):
#   docker run -d --name embed-server -p 8901:8901 workhive-embed-server
# Run (on the Supabase network so the edge can reach it by name):
#   docker run -d --name embed-server --network <supabase_network> workhive-embed-server
#   -> edge sets BGE_EMBED_URL=http://embed-server:8901/embed
#
# Deploys to Railway / Render / Fly (small image; CPU inference is plenty for bge-small).

FROM python:3.11-slim

WORKDIR /app

# fastembed pulls onnxruntime (CPU) — no torch, no system libs needed beyond the base.
RUN pip install --no-cache-dir fastembed

# Cache the model INSIDE the image at build time so startup is instant + offline.
ENV FASTEMBED_CACHE_PATH=/app/models
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5'); print('bge-small baked into image')"

# The server (stdlib HTTP, binds 0.0.0.0:8901).
COPY tools/embed_server.py /app/embed_server.py

EXPOSE 8901

# Railway/Render inject PORT; embed_server takes the port as argv[1].
CMD ["sh", "-c", "python /app/embed_server.py ${PORT:-8901}"]
