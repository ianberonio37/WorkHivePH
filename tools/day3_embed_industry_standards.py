"""Day 3: Embed industry_standards rows into pgvector via Voyage->Jina chain.

Python replica of supabase/functions/_shared/embedding-chain.ts. Runs as a
one-shot batch (matches Azure $200 sprint doctrine: artifacts, not runtime
calls). Output: industry_standards.embedding column populated for every row.

Provider chain (free tier sustainability):
  1. Voyage AI voyage-3.5-lite (200M tokens/month free, output_dim=512 -> 384)
  2. Jina AI jina-embeddings-v3 (100M tokens/month free, dim=384 native)

Both yield 384-dim vectors compatible with the existing vector(384) schema.

Usage:
    python tools/day3_embed_industry_standards.py

Idempotent: only embeds rows where embedding IS NULL unless --reembed flag set.
"""
from __future__ import annotations

import os
import sys
import io
import time
import argparse
import json
from pathlib import Path
from typing import Optional

import requests
import psycopg2
from dotenv import load_dotenv

# Windows console UTF-8
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

TARGET_DIM = 384

# Project root for env files
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")  # VOYAGE_API_KEY, JINA_API_KEY


# ── Voyage AI ─────────────────────────────────────────────────────────────
def voyage_embed(text: str, api_key: str) -> list[float]:
    """voyage-3.5-lite native dims are {256, 512, 1024, 2048}; request 512 and
    truncate to 384. Matryoshka training means first 384 preserve quality."""
    res = requests.post(
        "https://api.voyageai.com/v1/embeddings",
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json={
            "input":             [text],
            "model":             "voyage-3.5-lite",
            "output_dimension":  512,
            "input_type":        "document",
        },
        timeout=30,
    )
    if not res.ok:
        raise RuntimeError(f"voyage {res.status_code}: {res.text[:160]}")
    data = res.json()
    vec = data.get("data", [{}])[0].get("embedding")
    if not isinstance(vec, list) or len(vec) < TARGET_DIM:
        raise RuntimeError(f"voyage returned bad shape: {type(vec).__name__}/{len(vec) if isinstance(vec, list) else 'n/a'}")
    return vec[:TARGET_DIM]


# ── Jina AI ───────────────────────────────────────────────────────────────
def jina_embed(text: str, api_key: str) -> list[float]:
    """jina-embeddings-v3 supports native dim=384."""
    res = requests.post(
        "https://api.jina.ai/v1/embeddings",
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json={
            "model":      "jina-embeddings-v3",
            "input":      [text],
            "task":       "retrieval.passage",
            "dimensions": TARGET_DIM,
        },
        timeout=30,
    )
    if not res.ok:
        raise RuntimeError(f"jina {res.status_code}: {res.text[:160]}")
    data = res.json()
    vec = data.get("data", [{}])[0].get("embedding")
    if not isinstance(vec, list) or len(vec) != TARGET_DIM:
        raise RuntimeError(f"jina returned bad shape: {type(vec).__name__}/{len(vec) if isinstance(vec, list) else 'n/a'}")
    return vec


# ── Provider chain ────────────────────────────────────────────────────────
PROVIDERS = [
    ("voyage", "VOYAGE_API_KEY", voyage_embed),
    ("jina",   "JINA_API_KEY",   jina_embed),
]


def generate_embedding(text: str) -> tuple[list[float], str]:
    """Returns (vector, provider_name). Tries each provider in order; raises
    if all fail or none are configured."""
    if not text or not text.strip():
        raise RuntimeError("Cannot embed empty text")

    errors: list[str] = []
    for name, env_key, call in PROVIDERS:
        api_key = os.getenv(env_key)
        if not api_key or api_key.startswith("PASTE_"):
            continue
        try:
            vec = call(text, api_key)
            return vec, name
        except Exception as e:
            errors.append(f"{name}: {e}")

    if not errors:
        raise RuntimeError("No embedding provider configured (set VOYAGE_API_KEY or JINA_API_KEY)")
    raise RuntimeError(f"All providers failed: {' | '.join(errors)}")


# ── Main batch ────────────────────────────────────────────────────────────
def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reembed", action="store_true",
                        help="Re-embed every row (default: skip rows with embedding)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Embed at most N rows this run")
    args = parser.parse_args(argv)

    print("=" * 70)
    print("DAY 3: EMBED industry_standards INTO pgvector")
    print("=" * 70)

    # Sanity-check providers configured
    voyage_set = bool(os.getenv("VOYAGE_API_KEY", "").strip())
    jina_set   = bool(os.getenv("JINA_API_KEY",   "").strip())
    print(f"Providers configured: voyage={voyage_set}, jina={jina_set}")
    if not (voyage_set or jina_set):
        print("[FAIL] Neither VOYAGE_API_KEY nor JINA_API_KEY is set in .env")
        return 1

    # Connect to local Postgres directly (faster + supports vector type for write)
    conn = psycopg2.connect(
        host="127.0.0.1", port=54322,
        user="postgres", password="postgres",
        database="postgres",
    )
    conn.autocommit = False
    cur = conn.cursor()

    # Pull rows
    where_clause = "" if args.reembed else "WHERE embedding IS NULL"
    limit_clause = f"LIMIT {int(args.limit)}" if args.limit else ""
    cur.execute(f"""
        SELECT id, standard_code, family, title, notes
          FROM public.industry_standards
          {where_clause}
          ORDER BY family, standard_code
          {limit_clause}
    """)
    rows = cur.fetchall()
    total_rows = len(rows)

    if not rows:
        print("\n[OK] No rows to embed (all already embedded). Use --reembed to refresh.")
        cur.close()
        conn.close()
        return 0

    print(f"\nRows to embed: {total_rows}")
    print("-" * 70)

    embedded   = 0
    by_provider: dict[str, int] = {}
    failed     = 0

    for i, (id_, code, family, title, notes) in enumerate(rows, start=1):
        # Build embedding text: code + title + notes (mirrors the column hint)
        text = " — ".join(filter(None, [code, title, notes or ""]))[:8000]
        print(f"[{i:3d}/{total_rows}] {code} ({family})")

        try:
            vec, provider = generate_embedding(text)
            by_provider[provider] = by_provider.get(provider, 0) + 1

            # pgvector expects a string in '[v1,v2,...]' format
            vec_literal = "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
            cur.execute(
                "UPDATE public.industry_standards "
                "   SET embedding = %s::vector, last_verified_at = NOW() "
                " WHERE id = %s",
                (vec_literal, id_),
            )
            conn.commit()
            embedded += 1
            print(f"           [OK] {provider} ({len(vec)} dims)")
        except Exception as e:
            conn.rollback()
            failed += 1
            print(f"           [FAIL] {e}")

        # Pace to be friendly to free-tier rate limits
        time.sleep(0.15)

    cur.close()
    conn.close()

    print("\n" + "=" * 70)
    print("RESULT")
    print("=" * 70)
    print(f"  embedded:  {embedded}")
    print(f"  failed:    {failed}")
    print(f"  providers: {dict(by_provider)}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
