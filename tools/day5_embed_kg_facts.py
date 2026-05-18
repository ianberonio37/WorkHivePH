"""Day 5: Embed knowledge_graph_facts.embedding via Voyage->Jina chain.

The L5 extractor inserted 750 triples but left their embedding column NULL.
This script fills them so the platform can semantic-search the KG (mirrors
the pattern used for industry_standards + industry_standards_chunks).

Embedding text = claim_text (the LLM's plain-English statement of the triple).
If claim_text is empty/null, fall back to "{subject_ref} {predicate} {object_ref}".

Idempotent: skips rows where embedding IS NOT NULL unless --reembed passed.
"""
from __future__ import annotations

import os
import sys
import io
import time
import argparse
from pathlib import Path
from typing import Optional

import requests
import psycopg2
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

TARGET_DIM = 384


def voyage_embed(text: str, api_key: str) -> list[float]:
    res = requests.post(
        "https://api.voyageai.com/v1/embeddings",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        json={"input": [text], "model": "voyage-3.5-lite", "output_dimension": 512, "input_type": "document"},
        timeout=30,
    )
    if not res.ok:
        raise RuntimeError(f"voyage {res.status_code}: {res.text[:160]}")
    vec = res.json().get("data", [{}])[0].get("embedding")
    if not isinstance(vec, list) or len(vec) < TARGET_DIM:
        raise RuntimeError(f"voyage bad shape: {type(vec).__name__}")
    return vec[:TARGET_DIM]


def jina_embed(text: str, api_key: str) -> list[float]:
    res = requests.post(
        "https://api.jina.ai/v1/embeddings",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        json={"model": "jina-embeddings-v3", "input": [text], "task": "retrieval.passage", "dimensions": TARGET_DIM},
        timeout=30,
    )
    if not res.ok:
        raise RuntimeError(f"jina {res.status_code}: {res.text[:160]}")
    vec = res.json().get("data", [{}])[0].get("embedding")
    if not isinstance(vec, list) or len(vec) != TARGET_DIM:
        raise RuntimeError(f"jina bad shape: {type(vec).__name__}")
    return vec


PROVIDERS = [
    ("voyage", "VOYAGE_API_KEY", voyage_embed),
    ("jina",   "JINA_API_KEY",   jina_embed),
]


def generate_embedding(text: str) -> tuple[list[float], str]:
    errors: list[str] = []
    for name, env_key, call in PROVIDERS:
        api_key = os.getenv(env_key)
        if not api_key:
            continue
        try:
            return call(text, api_key), name
        except Exception as e:
            errors.append(f"{name}: {e}")
    raise RuntimeError(f"All providers failed: {' | '.join(errors)}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reembed", action="store_true",
                        help="Re-embed every row (default: skip rows with embedding)")
    args = parser.parse_args(argv)

    print("=" * 72)
    print("EMBED knowledge_graph_facts (Voyage -> Jina chain)")
    print("=" * 72)

    if not (os.getenv("VOYAGE_API_KEY") or os.getenv("JINA_API_KEY")):
        print("[FAIL] No embedding API keys")
        return 1

    # Reconnect every RECONNECT_EVERY rows — local Supabase Postgres has
    # dropped the connection under sustained UPDATE load. Fresh connection
    # avoids "server closed the connection unexpectedly".
    RECONNECT_EVERY = 50

    def open_conn():
        c = psycopg2.connect(host="127.0.0.1", port=54322,
                             user="postgres", password="postgres", database="postgres")
        c.autocommit = True
        return c

    conn = open_conn()
    cur = conn.cursor()

    where = "" if args.reembed else "WHERE embedding IS NULL AND active = true"
    cur.execute(f"""
        SELECT id, subject_ref, predicate, object_ref, claim_text
          FROM knowledge_graph_facts
          {where}
          ORDER BY created_at
    """)
    rows = cur.fetchall()
    total = len(rows)
    if not rows:
        print("[OK] Nothing to embed.")
        return 0

    print(f"Rows to embed: {total}")
    print(f"Reconnect every: {RECONNECT_EVERY} rows")
    print()

    embedded = 0
    by_provider: dict[str, int] = {}
    failed = 0

    for i, (id_, sub, pred, obj, claim) in enumerate(rows, start=1):
        text = (claim or f"{sub} {pred} {obj}").strip()[:8000]

        # Periodic reconnect to keep the DB connection fresh
        if i > 1 and i % RECONNECT_EVERY == 1:
            try:
                cur.close(); conn.close()
            except Exception:
                pass
            try:
                conn = open_conn()
                cur = conn.cursor()
            except Exception as e:
                print(f"  [{i:4d}/{total}] reconnect failed: {e}")
                time.sleep(5)
                conn = open_conn()
                cur = conn.cursor()

        try:
            vec, provider = generate_embedding(text)
            by_provider[provider] = by_provider.get(provider, 0) + 1
            vec_literal = "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
            cur.execute(
                "UPDATE knowledge_graph_facts SET embedding = %s::vector, updated_at = NOW() WHERE id = %s",
                (vec_literal, id_),
            )
            embedded += 1
            if i % 50 == 0 or i == total:
                print(f"  [{i:4d}/{total}] {provider} (running: voyage={by_provider.get('voyage', 0)} jina={by_provider.get('jina', 0)})")
        except psycopg2.Error as e:
            # DB dropped — reconnect and retry once
            try:
                cur.close(); conn.close()
            except Exception:
                pass
            time.sleep(2)
            try:
                conn = open_conn()
                cur = conn.cursor()
                cur.execute(
                    "UPDATE knowledge_graph_facts SET embedding = %s::vector, updated_at = NOW() WHERE id = %s",
                    (vec_literal, id_),
                )
                embedded += 1
            except Exception:
                failed += 1
                if failed <= 3:
                    print(f"  [{i:4d}/{total}] FAIL after reconnect: {e}")
        except Exception as e:
            failed += 1
            if failed <= 3:
                print(f"  [{i:4d}/{total}] FAIL: {e}")

        time.sleep(0.08)

    try:
        cur.close(); conn.close()
    except Exception:
        pass
    print(f"\n{'='*72}\nRESULT\n{'='*72}")
    print(f"  Embedded:  {embedded}/{total}")
    print(f"  Failed:    {failed}")
    print(f"  Providers: {dict(by_provider)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
