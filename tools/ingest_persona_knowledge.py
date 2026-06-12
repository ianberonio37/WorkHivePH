#!/usr/bin/env python3
"""ingest_persona_knowledge.py — L08 Persona-Knowledge ingestion (companion wiring W6 + W10 channels).

Curate -> contextual-chunk -> embed (384-dim) -> persona-scoped upsert into
persona_knowledge. The personas' own SKILL.md files become a retrievable DOMAIN
corpus: maintenance-expert -> Hezekiah (technical scope), analytics-engineer ->
Zaniah (strategic scope); a small set of public maintenance definitions -> shared.

Anthropic Contextual Retrieval: every chunk gets a one-line CONTEXT HEADER prepended
BEFORE embedding (situates the chunk in its source/section), which the research shows
cuts retrieval failures ~35-67%. The header is stored separately AND embedded with the
content so the vector carries the context.

Embedding mirrors the edge embedding-chain.ts EXACTLY (the W7 trap): Voyage
`voyage-3.5-lite` (output_dimension 512 -> sliced to 384, input_type=document) is the
edge's primary, Jina `jina-embeddings-v3` (dimensions=384) the fallback. Same MODEL not
just same dim, or cosine retrieval is silent noise. See embed_384().

W10 CHANNELS — the SAME chunk->embed->scope->upsert pipeline now accepts 4 inputs;
only the loader differs (the engine is source-agnostic):
  - SKILL.md          (W6)  your accumulated skills                 source_type=skill_md
  - drop-folder       (O15) persona_corpus/{hezekiah|zaniah|shared}/*.md|.txt|.pdf
                            — the FOLDER sets the scope             source_type=external_standard|pdf
  - PDF               (O13) a handbook/manual/standard (pdfplumber) source_type=pdf
  - URL               (O14) an open doc (crawl4ai -> markdown,
                            requests+bs4 fallback)                  source_type=url

Idempotent (O5): upsert keyed on (source, chunk_index); a row is REPLACED only when its
content_hash changed (a source edit supersedes), otherwise left untouched (no dup).

TWO-PLANES guardrail (locked 2026-06-12): persona_knowledge has NO hive_id = GLOBAL.
Only the persona BRAIN goes in (skills + platform METHODOLOGY/definitions + external).
NEVER ingest live tenant data (a hive's logbook/assets) or raw code — that is the
per-tenant RLS plane (L01-L07 + asset-brain). Folder/scope = brain, not tenant.

Usage:
  python tools/ingest_persona_knowledge.py --source all                  # skills + external + drop-folder
  python tools/ingest_persona_knowledge.py --source drop-folder          # only persona_corpus/**
  python tools/ingest_persona_knowledge.py --source maintenance-expert --dry-run
  python tools/ingest_persona_knowledge.py --pdf c:/path/handbook.pdf --scope technical --max-chunks 8
  python tools/ingest_persona_knowledge.py --url https://example.org/doc --scope strategic --label "RCM primer"
"""
from __future__ import annotations
import argparse
import hashlib
import os
import re
import sys
import time
from pathlib import Path

import psycopg2
import requests

# Windows console is cp1252 by default -> the '·' separator and any crawl4ai banner
# emoji raise UnicodeEncodeError. Force utf-8 so output is clean on every platform.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = Path(os.path.expanduser("~")) / ".claude" / "skills"
CORPUS_DIR = ROOT / "persona_corpus"  # the W10 drop-folder (in-repo so W12's CI can trigger on it)
DB_DSN = "host=127.0.0.1 port=54322 dbname=postgres user=postgres password=postgres"
JINA_MODEL = "jina-embeddings-v3"
TARGET_DIM = 384
MAX_CHARS = 1500  # ~per-chunk budget

# persona <-> SKILL.md <-> scope mapping (the curate step).
CURATE = {
    "maintenance-expert": {"scope": "technical", "persona": "hezekiah"},
    "analytics-engineer": {"scope": "strategic", "persona": "zaniah"},
}

# drop-folder name -> persona_scope (O15: the FOLDER sets the scope, no per-file tagging).
# hezekiah = the technical expert, zaniah = the strategist, shared = both.
FOLDER_SCOPE = {"hezekiah": "technical", "zaniah": "strategic", "shared": "shared"}
TEXT_EXTS = {".md", ".txt", ".pdf"}

# A tiny SHARED-scope external corpus (public maintenance definitions, paraphrased —
# license-free) so both personas can ground core vocabulary (proves O3).
EXTERNAL_SHARED = [
    ("ISO-14224", "Reliability terms", "MTBF (Mean Time Between Failures) is the average operating time between two consecutive failures of a repairable item, computed as total operating time divided by the number of failures. It measures reliability, not availability."),
    ("ISO-14224", "Maintainability terms", "MTTR (Mean Time To Repair) is the average time to restore a failed item to operating condition, including diagnosis, repair, and verification. Lower MTTR means faster recovery and higher availability."),
    ("ISO-22400", "OEE definition", "OEE (Overall Equipment Effectiveness) is Availability x Performance x Quality. A world-class benchmark is around 85%. It is a productivity measure and must not be confused with reliability availability."),
]


def _envval(name: str) -> str | None:
    for envfile in (ROOT / "supabase" / "functions" / ".env", ROOT / ".env"):
        if envfile.exists():
            m = re.search(rf"^{name}=(.+)$", envfile.read_text(encoding="utf-8", errors="ignore"), re.M)
            if m:
                return m.group(1).strip()
    return os.getenv(name)


def load_keys() -> dict:
    return {
        "voyage":     _envval("VOYAGE_API_KEY"),
        "gemini":     _envval("GEMINI_API_KEY"),
        "jina":       _envval("JINA_API_KEY"),
        "cloudflare": _envval("CLOUDFLARE_API_TOKEN"),
    }


# Which provider to embed with. The edge embedding-chain is a PINNED-primary chain
# (the 2026-06-12 revamp): the embedding MODEL is a property of the CORPUS, and ingest
# MUST use the SAME model the edge queries that corpus with, or cosine is noise (the W7
# trap). EMBED_PREFER pins ONE provider so a whole corpus lands in one space; the
# upsert records the ACTUAL provider used (auditable). Default 'gemini' = the
# persona_knowledge model (PERSONA_KNOWLEDGE_EMBED_MODEL on the edge): generous free
# tier (1,500 req/day, 10M tok/min, no card), 384-dim, BATCH-capable — batching is
# what makes bulk ingest of hundreds of chunks practical.
EMBED_PREFER = "bge-local"  # gemini|voyage|jina|cloudflare|bge-local|auto — from --embed-model
                            # bge-local = self-host fastembed bge-small (NO rate limit), matches
                            # the edge's local PERSONA_KNOWLEDGE_EMBED_MODEL default
_MODEL_LABEL = {
    "voyage":     "voyage-3.5-lite@384",
    "gemini":     "gemini-embedding-001@384",
    "cloudflare": "cf-bge-small-en-v1.5@384",
    "bge-local":  "bge-small-en-v1.5-local@384",
    "jina":       "jina-v3@384",
}
EMBED_BATCH = 96                            # texts per provider API call (BIG batches = fewer
                                            # requests = dodge per-minute REQUEST caps on free tiers)
AUTO_ORDER = ["gemini", "voyage", "jina"]   # 'auto' failover order (384-compatible only)

# Free embedding tiers are ALL request-rate-limited (Voyage 3 RPM w/o card; Gemini
# free embeddings also 429 'exceeded quota' on a rapid burst). When pinned, wait out
# the 429 and retry so the corpus lands consistently in ONE space rather than silently
# degrading to NULL embeddings (dead rows). Big batches keep request COUNT low.
VOYAGE_429_WAIT = 22
VOYAGE_429_RETRIES = 4
GEMINI_429_WAIT = 30
GEMINI_429_RETRIES = 5


def _l2(vec: list[float]) -> list[float]:
    n = sum(x * x for x in vec) ** 0.5 or 1.0
    return [x / n for x in vec]


def _align(data: list, n: int) -> list:
    """OpenAI-shaped {data:[{index,embedding}]} -> list[vec] aligned to input order."""
    out: list = [None] * n
    for i, item in enumerate(data or []):
        idx = item.get("index", i) if isinstance(item, dict) else i
        emb = item.get("embedding") if isinstance(item, dict) else item
        if isinstance(idx, int) and 0 <= idx < n:
            out[idx] = emb
    return out


def _batch_voyage(texts: list[str], key: str, wait_on_429: bool = True) -> list | None:
    for attempt in range(VOYAGE_429_RETRIES + 1):
        r = requests.post(
            "https://api.voyageai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"input": texts, "model": "voyage-3.5-lite", "output_dimension": 512, "input_type": "document"},
            timeout=45,
        )
        if r.status_code == 200:
            vecs = _align(r.json().get("data") or [], len(texts))
            return [v[:TARGET_DIM] if isinstance(v, list) and len(v) >= TARGET_DIM else None for v in vecs]
        if r.status_code == 429 and wait_on_429 and attempt < VOYAGE_429_RETRIES:
            print(f"  voyage 429 — waiting {VOYAGE_429_WAIT}s then retry ({attempt + 1}/{VOYAGE_429_RETRIES})", file=sys.stderr)
            time.sleep(VOYAGE_429_WAIT)
            continue
        print(f"  voyage {r.status_code}: {r.text[:120]}", file=sys.stderr)
        return None
    return None


def _batch_jina(texts: list[str], key: str) -> list | None:
    r = requests.post(
        "https://api.jina.ai/v1/embeddings",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": JINA_MODEL, "input": texts, "task": "retrieval.passage", "dimensions": TARGET_DIM},
        timeout=45,
    )
    if r.status_code == 200:
        vecs = _align(r.json().get("data") or [], len(texts))
        return [v if isinstance(v, list) and len(v) == TARGET_DIM else None for v in vecs]
    print(f"  jina {r.status_code}: {r.text[:120]}", file=sys.stderr)
    return None


def _batch_gemini(texts: list[str], key: str) -> list | None:
    """Mirror the edge geminiEmbed EXACTLY: OpenAI-compat endpoint, dimensions=384,
    then L2-NORMALIZE (Gemini does not normalize <3072 dims — the edge normalizes, so
    ingest MUST too or the spaces diverge). Waits out the free-tier 429 quota burst."""
    for attempt in range(GEMINI_429_RETRIES + 1):
        r = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/openai/embeddings",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "gemini-embedding-001", "input": texts, "dimensions": TARGET_DIM},
            timeout=60,
        )
        if r.status_code == 200:
            vecs = _align(r.json().get("data") or [], len(texts))
            return [_l2(v) if isinstance(v, list) and len(v) == TARGET_DIM else None for v in vecs]
        if r.status_code == 429 and attempt < GEMINI_429_RETRIES:
            print(f"  gemini 429 (quota) — waiting {GEMINI_429_WAIT}s then retry ({attempt + 1}/{GEMINI_429_RETRIES})", file=sys.stderr)
            time.sleep(GEMINI_429_WAIT)
            continue
        print(f"  gemini {r.status_code}: {r.text[:120]}", file=sys.stderr)
        return None
    return None


def _batch_cloudflare(texts: list[str], token: str) -> list | None:
    """Cloudflare Workers AI bge-small-en-v1.5 (384-dim native). SAME model as the
    self-host bge-local path -> shared vector space. Needs CLOUDFLARE_ACCOUNT_ID."""
    acct = _envval("CLOUDFLARE_ACCOUNT_ID")
    if not acct:
        print("  cloudflare: CLOUDFLARE_ACCOUNT_ID not set", file=sys.stderr)
        return None
    r = requests.post(
        f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/@cf/baai/bge-small-en-v1.5",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"text": texts}, timeout=45,
    )
    if r.status_code == 200:
        data = (r.json().get("result") or {}).get("data") or []
        vecs = [_l2(v) if isinstance(v, list) and len(v) == TARGET_DIM else None for v in data]
        return vecs + [None] * (len(texts) - len(vecs))
    print(f"  cloudflare {r.status_code}: {r.text[:120]}", file=sys.stderr)
    return None


_BGE_LOCAL = None  # cached model handle (kind, model)
BGE_SERVER_URL = "http://127.0.0.1:8901/embed"  # the running embed_server (host-local)


def _batch_bge_local(texts: list[str]) -> list | None:
    """Self-host bge-small-en-v1.5 — UNLIMITED, free, no RPM (Ian's durable pick for
    bulk ingest). PREFERS the running embed_server (tools/embed_server.py) over HTTP — one
    model copy in RAM, shared with the edge, so ingest + query produce IDENTICAL vectors
    (memory-friendly on a tight box). Falls back to in-process fastembed / sentence-
    transformers if the server isn't up. 384-dim."""
    # 1. the running embed_server (same model the edge queries -> guaranteed same space)
    try:
        r = requests.post(BGE_SERVER_URL, json={"texts": texts}, timeout=90)
        if r.status_code == 200:
            embs = (r.json() or {}).get("embeddings")
            if embs and len(embs) == len(texts):
                return [_l2(v) if isinstance(v, list) and len(v) == TARGET_DIM else None for v in embs]
    except Exception:  # noqa: BLE001
        pass
    # 2. in-process fastembed / sentence-transformers fallback
    global _BGE_LOCAL
    if _BGE_LOCAL is None:
        try:
            from fastembed import TextEmbedding  # type: ignore
            _BGE_LOCAL = ("fastembed", TextEmbedding(model_name="BAAI/bge-small-en-v1.5"))
        except Exception:  # noqa: BLE001
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore
                _BGE_LOCAL = ("st", SentenceTransformer("BAAI/bge-small-en-v1.5"))
            except Exception as e:  # noqa: BLE001
                print(f"  bge-local unavailable ({e}) — `pip install fastembed` to enable", file=sys.stderr)
                return None
    kind, model = _BGE_LOCAL
    if kind == "fastembed":
        return [_l2(list(map(float, v))) for v in model.embed(texts)]
    return [_l2(list(map(float, v))) for v in model.encode(texts, normalize_embeddings=False)]


def _dispatch_batch(prov: str, texts: list[str], keys: dict) -> list | None:
    if prov == "gemini":     return _batch_gemini(texts, keys.get("gemini"))
    if prov == "voyage":     return _batch_voyage(texts, keys.get("voyage"))
    if prov == "jina":       return _batch_jina(texts, keys.get("jina"))
    if prov == "cloudflare": return _batch_cloudflare(texts, keys.get("cloudflare"))
    if prov == "bge-local":  return _batch_bge_local(texts)
    return None


def embed_texts(texts: list[str], keys: dict,
                prefer: str | None = None) -> list[tuple[list[float] | None, str | None]]:
    """Batch-embed many texts. Pins to one provider (EMBED_PREFER/prefer); 'auto' fills
    any gaps from the next provider. Returns [(vec, actual_model_label)] aligned to
    input. Batching (EMBED_BATCH per API call) is the bulk-ingest throughput lever."""
    n = len(texts)
    out: list[tuple[list[float] | None, str | None]] = [(None, None)] * n
    mode = (prefer or EMBED_PREFER or "gemini").lower()
    order = AUTO_ORDER if mode == "auto" else [mode]
    pending = list(range(n))
    for prov in order:
        if not pending:
            break
        if prov != "bge-local" and not keys.get(prov):
            continue
        label = _MODEL_LABEL.get(prov)
        next_pending: list[int] = []
        for s in range(0, len(pending), EMBED_BATCH):
            idxs = pending[s:s + EMBED_BATCH]
            try:
                vecs = _dispatch_batch(prov, [texts[i][:8000] for i in idxs], keys)
            except Exception as e:  # noqa: BLE001
                print(f"  {prov} failed (non-fatal): {e}", file=sys.stderr)
                vecs = None
            for j, i in enumerate(idxs):
                v = vecs[j] if vecs and j < len(vecs) else None
                if v:
                    out[i] = (v, label)
                else:
                    next_pending.append(i)
        pending = next_pending
    return out


def embed_384(text: str, keys: dict, prefer: str | None = None) -> tuple[list[float] | None, str | None]:
    """Single-text convenience wrapper over embed_texts (used by single-row paths)."""
    return embed_texts([text], keys, prefer)[0]


def chunk_markdown(md: str) -> list[tuple[str, str]]:
    """Split a SKILL.md into (section_heading, chunk_text) pairs, bounded by MAX_CHARS."""
    # Split on ## / ### headings, keep the heading with its body.
    parts = re.split(r"(?m)^(#{2,3}\s+.+)$", md)
    chunks: list[tuple[str, str]] = []
    # parts = [pre, head1, body1, head2, body2, ...]
    pre = parts[0].strip()
    if pre:
        for piece in _split_len(pre):
            chunks.append(("(intro)", piece))
    for i in range(1, len(parts) - 1, 2):
        heading = re.sub(r"^#{2,3}\s+", "", parts[i]).strip()
        body = (parts[i + 1] or "").strip()
        if not body:
            continue
        for piece in _split_len(body):
            chunks.append((heading[:120], piece))
    return chunks


def _hard_wrap(p: str) -> list[str]:
    """Split an oversized block into <= MAX_CHARS pieces, preferring sentence boundaries
    (a monster sentence falls back to hard char slices). Prevents the truncation bug
    where a single >MAX_CHARS paragraph silently dropped everything past 1500 chars."""
    out, buf = [], ""
    for s in re.split(r"(?<=[.!?])\s+", p):
        if len(s) > MAX_CHARS:
            if buf:
                out.append(buf)
                buf = ""
            out.extend(s[i:i + MAX_CHARS] for i in range(0, len(s), MAX_CHARS))
            continue
        if len(buf) + len(s) + 1 <= MAX_CHARS:
            buf = f"{buf} {s}" if buf else s
        else:
            if buf:
                out.append(buf)
            buf = s
    if buf:
        out.append(buf)
    return out


def _split_len(text: str) -> list[str]:
    """Greedy paragraph-packing into <= MAX_CHARS pieces. A single paragraph longer than
    MAX_CHARS is HARD-WRAPPED into sub-pieces (never truncated)."""
    paras: list[str] = []
    for p in (p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()):
        paras.extend([p] if len(p) <= MAX_CHARS else _hard_wrap(p))
    out, buf = [], ""
    for p in paras:
        if len(buf) + len(p) + 2 <= MAX_CHARS:
            buf = f"{buf}\n\n{p}" if buf else p
        else:
            if buf:
                out.append(buf)
            buf = p
    if buf:
        out.append(buf)
    return out or [text[:MAX_CHARS]]


def context_header(source: str, section: str, content: str) -> str:
    """Anthropic Contextual Retrieval header — situate the chunk before embedding."""
    gist = re.sub(r"\s+", " ", content)[:90]
    return f"[{source} -> {section}] This excerpt covers: {gist}..."


def upsert(cur, *, scope, source, source_type, section, idx, header, content, embedding, model):
    chash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    emb_lit = "[" + ",".join(f"{x:.6f}" for x in embedding) + "]" if embedding else None
    cur.execute(
        """
        insert into persona_knowledge
          (persona_scope, source, source_type, section, chunk_index, context_header,
           content, content_hash, embedding, embedding_model, updated_at)
        values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
        on conflict (source, chunk_index) do update set
          persona_scope = excluded.persona_scope,
          section       = excluded.section,
          context_header= excluded.context_header,
          content       = excluded.content,
          content_hash  = excluded.content_hash,
          embedding     = excluded.embedding,
          embedding_model = excluded.embedding_model,
          updated_at    = now()
        where persona_knowledge.content_hash is distinct from excluded.content_hash
           or persona_knowledge.embedding is null   -- backfill a row left un-embedded by a 429
        returning (xmax = 0) as inserted
        """,
        (scope, source, source_type, section, idx, header, content, chash, emb_lit, model),
    )
    row = cur.fetchone()
    return ("inserted" if row and row[0] else "updated") if row else "unchanged"


def ingest_skill(cur, keys, slug, dry):
    spec = CURATE[slug]
    path = SKILLS_DIR / slug / "SKILL.md"
    if not path.exists():
        print(f"  SKIP {slug}: {path} not found")
        return {"inserted": 0, "updated": 0, "unchanged": 0, "embedded": 0}
    chunks = chunk_markdown(path.read_text(encoding="utf-8", errors="ignore"))
    source = f"{slug}/SKILL.md"
    stats = _ingest_chunks(cur, keys, scope=spec["scope"], source=source,
                           source_type="skill_md", chunks=chunks, dry=dry)
    print(f"  {slug} ({spec['scope']}): {len(chunks)} chunks -> "
          f"{stats['inserted']} ins / {stats['updated']} upd / {stats['unchanged']} same / {stats['embedded']} emb")
    return stats


def ingest_external(cur, keys, dry):
    # group by standard so a multi-chunk standard (ISO-14224 x2) gets sequential
    # chunk_index 0,1 under its own source (the unique upsert key).
    by_source: dict[str, list[tuple[str, str]]] = {}
    for std, section, content in EXTERNAL_SHARED:
        by_source.setdefault(f"external/{std}", []).append((section, content))
    stats = {"inserted": 0, "updated": 0, "unchanged": 0, "embedded": 0}
    for source, chunks in by_source.items():
        s = _ingest_chunks(cur, keys, scope="shared", source=source,
                           source_type="external_standard", chunks=chunks, dry=dry)
        for k in stats:
            stats[k] += s[k]
    print(f"  external (shared): {len(EXTERNAL_SHARED)} chunks -> "
          f"{stats['inserted']} ins / {stats['updated']} upd / {stats['embedded']} emb")
    return stats


# ---------------------------------------------------------------------------
# W10 channels — PDF / URL / drop-folder. All feed the SAME chunk->embed->scope
# ->upsert core (_ingest_chunks); only the loader (text extraction) differs.
# ---------------------------------------------------------------------------

def _ingest_chunks(cur, keys, *, scope, source, source_type, chunks, dry, max_chunks=0):
    """Header -> BATCH embed -> scoped upsert for a list of (section, content) chunks.
    Shared by EVERY channel (skills / external / drop-folder / pdf / url) so they can't
    drift apart, and so all embeds for a source go out in batches (EMBED_BATCH per API
    call) — the bulk-ingest throughput lever. max_chunks > 0 caps the count."""
    if max_chunks and max_chunks > 0:
        chunks = chunks[:max_chunks]
    stats = {"inserted": 0, "updated": 0, "unchanged": 0, "embedded": 0, "failed": 0}
    if dry or not chunks:
        return stats  # dry = chunk-count only (caller prints len(chunks)); no API calls
    headers = [context_header(source, sec, con) for sec, con in chunks]
    embedded = embed_texts([f"{h}\n{c}" for h, (_s, c) in zip(headers, chunks)], keys)
    for idx, ((section, content), header, (emb, model)) in enumerate(zip(chunks, headers, embedded)):
        if not emb:
            # don't persist a dead (un-embedded) row — a re-run backfills it (the upsert
            # also updates rows whose embedding is null). Keeps the corpus retrievable.
            stats["failed"] += 1
            continue
        stats["embedded"] += 1
        res = upsert(cur, scope=scope, source=source, source_type=source_type,
                     section=section, idx=idx, header=header, content=content,
                     embedding=emb, model=model)
        stats[res] = stats.get(res, 0) + 1
    return stats


def _pdf_text(path: Path) -> str:
    """Extract a PDF to plain text (reuses ingest_user_pdfs.py's pdfplumber approach,
    feeding THIS persona pipeline instead of the industry_standards/day4 chain — that
    chain targets the wrong substrate for a persona corpus)."""
    import pdfplumber  # local import: optional dep, only needed for the PDF channel
    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages:
            t = pg.extract_text() or ""
            if t.strip():
                pages.append(t)
    return "\n\n".join(pages)


def _url_markdown(url: str, use_crawl4ai: bool = False) -> str:
    """Fetch a URL as clean markdown for the O14 channel.

    Default = requests + bs4 strip: no headless browser, no asyncio, CI-safe (CI
    runners have no chromium). Pass use_crawl4ai=True (--crawl4ai) for crawl4ai's
    richer markdown when a chromium browser IS available locally."""
    # crawl4ai -> clean markdown (opt-in; needs a chromium browser, not CI-portable)
    if use_crawl4ai:
        try:
            import asyncio
            from crawl4ai import AsyncWebCrawler  # type: ignore

            async def _run() -> str:
                async with AsyncWebCrawler(verbose=False) as crawler:
                    res = await crawler.arun(url=url)
                    md = getattr(res, "markdown", None)
                    # crawl4ai >=0.3 returns a MarkdownGenerationResult on .markdown
                    return getattr(md, "raw_markdown", None) or (md if isinstance(md, str) else "") or ""

            md = asyncio.run(_run())
            if md and md.strip():
                return md
            print("  crawl4ai returned empty; falling back to requests+bs4", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print(f"  crawl4ai unavailable ({type(e).__name__}); falling back to requests+bs4", file=sys.stderr)
    # requests + bs4 strip (the default; clean enough for chunking)
    r = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0 (persona-corpus ingest)"})
    r.raise_for_status()
    return _html_text(r.text)


def _html_text(html: str) -> str:
    """Strip an HTML document to clean body text — shared by the URL channel (O14) and
    the platform-doc channel (W11). Drops chrome, then joins BLOCK elements with blank
    lines so the text has real paragraph breaks (get_text('\\n') alone yields one giant
    single-\\n blob that the chunker can't split — it would truncate to MAX_CHARS)."""
    from bs4 import BeautifulSoup  # type: ignore
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "noscript"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    blocks = []
    for el in main.find_all(["h1", "h2", "h3", "h4", "h5", "p", "li", "blockquote",
                             "td", "th", "dd", "dt", "figcaption"]):
        t = el.get_text(" ", strip=True)
        if t:
            blocks.append(t)
    text = "\n\n".join(blocks) if blocks else main.get_text("\n")
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()


def ingest_file(cur, keys, path: Path, scope: str, source_type: str, source: str, dry, max_chunks=0):
    """Ingest one local file (.md/.txt/.pdf) at an explicit scope+source label."""
    text = _pdf_text(path) if path.suffix.lower() == ".pdf" else path.read_text(encoding="utf-8", errors="ignore")
    chunks = chunk_markdown(text)
    if not chunks:
        print(f"  SKIP {source}: no extractable text")
        return {"inserted": 0, "updated": 0, "unchanged": 0, "embedded": 0}
    stats = _ingest_chunks(cur, keys, scope=scope, source=source, source_type=source_type,
                           chunks=chunks, dry=dry, max_chunks=max_chunks)
    shown = min(len(chunks), max_chunks) if max_chunks else len(chunks)
    print(f"  [{scope}] {source} ({source_type}): {shown} chunks -> "
          f"{stats['inserted']} ins / {stats['updated']} upd / {stats['unchanged']} same / {stats['embedded']} emb")
    return stats


def ingest_drop_folder(cur, keys, dry, only_scope=None, max_chunks=0):
    """Walk persona_corpus/{hezekiah|zaniah|shared}/ — the FOLDER sets the scope (O15).
    .pdf -> source_type=pdf (O13), .md/.txt -> external_standard."""
    if not CORPUS_DIR.exists():
        print(f"  drop-folder: {CORPUS_DIR} not present (create persona_corpus/{{hezekiah,zaniah,shared}}/ and drop files)")
        return
    total = 0
    for folder, scope in FOLDER_SCOPE.items():
        if only_scope and scope != only_scope:
            continue
        d = CORPUS_DIR / folder
        if not d.exists():
            continue
        for path in sorted(d.iterdir()):
            if not path.is_file() or path.suffix.lower() not in TEXT_EXTS:
                continue
            stype = "pdf" if path.suffix.lower() == ".pdf" else "external_standard"
            source = f"corpus/{folder}/{path.name}"
            ingest_file(cur, keys, path, scope, stype, source, dry, max_chunks=max_chunks)
            total += 1
    if total == 0:
        print(f"  drop-folder: no .md/.txt/.pdf files under {CORPUS_DIR}")


# ---------------------------------------------------------------------------
# W11 — YOUR OWN content (the goldmine). The 37 learn articles + 29 feature
# capabilities, already written + inventoried in platform_catalog.json but never
# RETRIEVED by the personas. source_type='platform_doc'. TWO-PLANES guardrail: these
# are PUBLIC learn/marketing pages = persona BRAIN (methodology/expertise), never live
# tenant data — a guard skips any chunk that looks tenant-keyed.
# ---------------------------------------------------------------------------

CATALOG = ROOT / "platform_catalog.json"

# topic -> scope (the curate step): reliability/engineering -> Hezekiah technical;
# KPI/strategy/economics -> Zaniah strategic; genuinely cross-cutting (safety, platform
# onboarding, definitions) -> shared. NOTE: PH-context ("philippine/iso/dole/peza") is a
# FLAVOUR, not a scope — it does NOT pull an article to shared (that mis-scoped technical
# reliability content as shared and blurred the O6 "deeper Hezekiah" proof).
_TECH_KW = ("engineering", "calc", "calculator", "fmea", "rcm", "vibration", "reliability",
            "asset register", "asset-register", "maintenance", "pump", "motor", "bearing",
            "lubrication", "predictive", "failure mode", "mtbf", "mttr", "equipment", "sap",
            "maximo", "cmms", "integration", "plc", "scada", "bms", "boiler", "compressor",
            "preventive", "logbook", "fault", "torque", "alignment", "spare part", "inventory",
            "power plant", "condition monitoring", "facilities")
_STRAT_KW = ("roi", "quality", "strategy", "benchmark", "oee", "kpi", "analytics", "report",
             "audit", "compliance", "maturity", "cost", "budget", "project planning",
             "supervisor", "manager", "dashboard", "downtime", "economics", "prioriti",
             "stage 2", "stage-2", "world-class", "world class", "shift handover",
             "day planner", "metrics")
# shared = genuinely cross-cutting topics BOTH personas should hold (not a fallthrough).
_SHARED_ONLY = ("safety", "loto", "lockout", "tagout", "permit-to-work", "permit to work",
                "getting started", "getting-started", "onboard", "glossary", "what is a ",
                "definition", "community", "marketplace", "resume", "joining", "grow your hive",
                "association", "iiee", "psme", "piche")


def classify_scope(text: str) -> str:
    """Deterministic topic->scope. A genuine cross-cutting topic (safety / platform
    onboarding / definitions) -> shared; otherwise the higher of technical vs strategic
    keyword hits; default shared only when there's NO domain signal (mirrors
    scopesForPersona's safe default — never technical/strategic without clear signal)."""
    t = (text or "").lower()
    if any(k in t for k in _SHARED_ONLY):
        return "shared"
    tech = sum(1 for k in _TECH_KW if k in t)
    strat = sum(1 for k in _STRAT_KW if k in t)
    if tech == 0 and strat == 0:
        return "shared"
    return "technical" if tech >= strat else "strategic"


# Two-planes guard: a global-table chunk must carry NO tenant DATA. The detectable
# signal is a real tenant identifier — a UUID (a specific hive/worker/asset id) — NOT
# the schema WORD "hive_id", which appears legitimately in skill/architecture docs
# ("...invoke(...,{body:{hive_id}})"). Flagging the word wrongly drops genuine brain
# content; a UUID in curated brain content is the actual red flag.
_TENANT_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
_BOILERPLATE_RE = re.compile(
    r"^(home|learn|/|·|by|published|updated|\d+\s*min read|workhive editorial team|share|back to)\b", re.I)


def _clean_article_text(text: str) -> str:
    """Drop breadcrumb/byline boilerplate lines so chunks are prose, not nav chrome."""
    keep = [ln for ln in text.splitlines() if ln.strip() and not _BOILERPLATE_RE.match(ln.strip())]
    return "\n".join(keep)


def ingest_platform_catalog(cur, keys, dry, max_chunks_per=0):
    """W11: ingest the 37 learn articles + feature capabilities from platform_catalog.json
    as persona BRAIN (source_type='platform_doc'), scoped by topic. The tenant-data guard
    keeps the global table brain-only."""
    if not CATALOG.exists():
        print(f"  platform: {CATALOG} not found (run tools/platform_catalog.py first)")
        return
    import json
    cat = json.loads(CATALOG.read_text(encoding="utf-8", errors="ignore"))
    skipped_tenant = 0

    def _scoped_chunks(raw_chunks, fallback_scope):
        nonlocal skipped_tenant
        clean = []
        for sec, con in raw_chunks:
            if _TENANT_RE.search(con):
                skipped_tenant += 1
                continue
            clean.append((sec, con))
        return clean

    # 1. Articles — learn/<slug>/index.html
    arts = cat.get("articles", [])
    n_art = 0
    for a in arts:
        slug = a.get("slug")
        path = ROOT / "learn" / slug / "index.html"
        if not slug or not path.exists():
            continue
        text = _clean_article_text(_html_text(path.read_text(encoding="utf-8", errors="ignore")))
        if not text.strip():
            continue
        # scope from title + slug + maps_to_label (the editorial topic)
        scope = classify_scope(" ".join(str(a.get(k, "")) for k in ("title", "slug", "maps_to_label")))
        chunks = _scoped_chunks(chunk_markdown(text), scope)
        if not chunks:
            continue
        st = _ingest_chunks(cur, keys, scope=scope, source=f"learn/{slug}",
                            source_type="platform_doc", chunks=chunks, dry=dry, max_chunks=max_chunks_per)
        n_art += 1
        if not dry:
            print(f"  [{scope}] learn/{slug}: {len(chunks)} chunks -> {st['inserted']} ins / {st['updated']} upd / {st['unchanged']} same / {st['embedded']} emb")

    # 2. Feature capabilities — one chunk per feature that has capability prose
    feats = [f for f in cat.get("features", []) if (f.get("capability") or "").strip()]
    fchunks_by_scope: dict[str, list] = {}
    for f in feats:
        body = f"{f.get('name', f.get('id'))} — {f.get('capability')}".strip()
        if _TENANT_RE.search(body):
            skipped_tenant += 1
            continue
        scope = classify_scope(f"{f.get('name','')} {f.get('capability','')} {f.get('nav_section','')}")
        # group all features of a scope under one source so chunk_index is stable
        fchunks_by_scope.setdefault(scope, []).append((f.get("id", "feature"), body))
    for scope, items in fchunks_by_scope.items():
        st = _ingest_chunks(cur, keys, scope=scope, source=f"platform/features-{scope}",
                            source_type="platform_doc", chunks=items, dry=dry)
        if not dry:
            print(f"  [{scope}] platform/features-{scope}: {len(items)} chunks -> "
                  f"{st['inserted']} ins / {st['updated']} upd / {st['unchanged']} same / {st['embedded']} emb")

    print(f"  platform: {n_art} articles + {len(feats)} feature-capabilities ingested"
          f"{f' | {skipped_tenant} chunks SKIPPED (tenant-keyed, two-planes guard)' if skipped_tenant else ''}")


def main() -> int:
    global EMBED_PREFER
    ap = argparse.ArgumentParser(description="L08 persona-knowledge ingestion (W6 + W10 channels)")
    ap.add_argument("--source", default="all",
                    choices=["all", "maintenance-expert", "analytics-engineer", "external",
                             "drop-folder", "platform"],
                    help="'all' = skills + external + drop-folder + platform (the complete brain); "
                         "'platform' = W11 own content (37 articles + features via platform_catalog.json)")
    ap.add_argument("--pdf", help="path to a PDF to ingest (requires --scope)")
    ap.add_argument("--url", help="URL to fetch (crawl4ai->markdown) and ingest (requires --scope)")
    ap.add_argument("--scope", choices=["technical", "strategic", "shared"],
                    help="persona scope for --pdf / --url")
    ap.add_argument("--label", help="override the source label for --pdf / --url (default: filename / URL)")
    ap.add_argument("--max-chunks", type=int, default=0,
                    help="cap chunks per source (0 = unlimited; bounds embed cost on fat PDFs/URLs)")
    ap.add_argument("--embed-model", default=EMBED_PREFER,
                    choices=["gemini", "voyage", "jina", "cloudflare", "bge-local", "auto"],
                    help="pin the embedding provider so the corpus stays in ONE vector space "
                         "(MUST match PERSONA_KNOWLEDGE_EMBED_MODEL on the edge). Default gemini "
                         "(free, no card, batch). 'cloudflare'/'bge-local' = bge-small-en-v1.5 "
                         "(same space); 'auto' = gemini->voyage->jina failover.")
    ap.add_argument("--crawl4ai", action="store_true",
                    help="for --url: use crawl4ai (needs a local chromium) instead of the "
                         "default requests+bs4 fetch (CI-safe)")
    ap.add_argument("--dry-run", action="store_true", help="chunk + embed count, no DB writes")
    args = ap.parse_args()

    if (args.pdf or args.url) and not args.scope:
        ap.error("--pdf / --url require --scope {technical|strategic|shared}")

    EMBED_PREFER = args.embed_model

    keys = load_keys()
    print("embed keys: " + " ".join(f"{p}={'y' if keys.get(p) else 'n'}" for p in
          ("gemini", "voyage", "jina", "cloudflare")) + f" | pin={EMBED_PREFER} | dim {TARGET_DIM}")

    conn = None if args.dry_run else psycopg2.connect(DB_DSN)
    cur = None if args.dry_run else conn.cursor()
    try:
        if args.pdf:
            path = Path(args.pdf)
            if not path.exists():
                print(f"  ERROR: {path} not found", file=sys.stderr)
                return 1
            ingest_file(cur, keys, path, args.scope, "pdf",
                        args.label or f"pdf/{path.name}", args.dry_run, max_chunks=args.max_chunks)
        elif args.url:
            md = _url_markdown(args.url, use_crawl4ai=args.crawl4ai)
            if not md.strip():
                print(f"  ERROR: fetched nothing usable from {args.url}", file=sys.stderr)
                return 1
            source = args.label or args.url
            chunks = chunk_markdown(md)
            st = _ingest_chunks(cur, keys, scope=args.scope, source=source, source_type="url",
                                chunks=chunks, dry=args.dry_run, max_chunks=args.max_chunks)
            shown = min(len(chunks), args.max_chunks) if args.max_chunks else len(chunks)
            print(f"  [{args.scope}] {source} (url): {shown} chunks -> "
                  f"{st['inserted']} ins / {st['updated']} upd / {st['unchanged']} same / {st['embedded']} emb")
        else:
            targets = ["maintenance-expert", "analytics-engineer"] if args.source == "all" else \
                      ([args.source] if args.source in CURATE else [])
            for slug in targets:
                ingest_skill(cur, keys, slug, args.dry_run)
            if args.source in ("all", "external"):
                ingest_external(cur, keys, args.dry_run)
            if args.source in ("all", "drop-folder"):
                ingest_drop_folder(cur, keys, args.dry_run, max_chunks=args.max_chunks)
            if args.source in ("all", "platform"):
                ingest_platform_catalog(cur, keys, args.dry_run, max_chunks_per=args.max_chunks)
        if conn:
            conn.commit()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
