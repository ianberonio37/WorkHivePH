# WorkHive embed-server — self-host bge-small-en-v1.5 (no rate limit)

Containerized form of `tools/embed_server.py`. Serves 384-dim `bge-small-en-v1.5`
embeddings over HTTP so the **persona-knowledge** corpus can be ingested AND queried
with the **same model** — one vector space, no per-request rate limit. This is the
production form of the host process used in local dev.

Why this exists: free embedding APIs (Voyage 3 RPM without a card, Gemini free-tier
429 on a burst) cannot serve many concurrent users. A self-hosted model has no cap.

## Build (from repo root)

```bash
docker build -f docker/embed-server/Dockerfile -t workhive-embed-server .
```

The bge-small model is downloaded and **baked into the image at build time**
(`FASTEMBED_CACHE_PATH=/app/models`), so the container starts instantly and needs no
network at runtime.

## Run

**Standalone (host-published port):**
```bash
docker run -d --name embed-server -p 8901:8901 workhive-embed-server
curl http://127.0.0.1:8901/health     # {"ok":true,"model":"bge-small-en-v1.5","dim":384}
```

**On the Supabase docker network (so the edge reaches it by service name):**
```bash
docker run -d --name embed-server --network supabase_network_<project> workhive-embed-server
```
Then the edge resolves it as `http://embed-server:8901/embed`.

## Wire the edge to it

The embedding model is pinned per corpus (see `_shared/embedding-chain.ts`). Point the
edge at this server and pin persona_knowledge to it:

| Env (edge / Supabase secret) | Value |
|---|---|
| `BGE_EMBED_URL` | `http://embed-server:8901/embed` (same network) or the deployed URL |
| `PERSONA_KNOWLEDGE_EMBED_MODEL` | `bge-local` |

Locally these have code-defaults gated to local (`host.docker.internal:8901`), so dev
needs no env. **In prod, set them explicitly** as Supabase Edge Function secrets, because
the local edge runtime is not passed `functions/.env`.

## Ingest in the same space

The ingest tool reuses this server automatically (HTTP to `127.0.0.1:8901`, falling back
to in-process fastembed):

```bash
python tools/ingest_persona_knowledge.py --source all --embed-model bge-local
```

Ingest and query hitting the same server guarantees identical vectors → coherent
retrieval. If you ever change the model, re-embed the whole corpus and flip the pin in
lock-step (validated by `tools/validate_embedding_chain_consistency.py`).

## Deploy targets

Small CPU image (no GPU, no torch) — runs on Railway / Render / Fly free or low tiers.
Expose port `8901` (or honor the platform's injected `$PORT`), then set `BGE_EMBED_URL`
to the public URL as an edge secret.

## Notes

- No `apt-get` system deps: fastembed uses onnxruntime CPU wheels (unlike the
  weasyprint-based `python-api`, which needs pango/cairo).
- Health: `GET /health`. Embed: `POST /embed {"texts":[...]}` → `{"embeddings":[[...384]],"model":"...","dim":384}`.
- Keep it running: if the server is down, the edge falls back to another provider, and
  the cross-space guard skips persona retrieval (graceful, but no domain knowledge).
