"""Day 7 (B): Fill the empty asset_embeddings table.

asset_embeddings (node_id, hive_id, summary, embedding) has 0 rows even
though 95 asset_nodes exist. Embed each asset's identity summary
(tag + name + manufacturer + model + serial_no + location + iso_class)
via the Voyage->Jina chain so semantic search across assets works.

Idempotent: skips rows already present unless --reembed passed.
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
    r = requests.post("https://api.voyageai.com/v1/embeddings",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        json={"input": [text], "model": "voyage-3.5-lite", "output_dimension": 512, "input_type": "document"},
        timeout=30)
    if not r.ok: raise RuntimeError(f"voyage {r.status_code}: {r.text[:160]}")
    vec = r.json().get("data", [{}])[0].get("embedding")
    if not isinstance(vec, list) or len(vec) < TARGET_DIM:
        raise RuntimeError(f"voyage bad shape")
    return vec[:TARGET_DIM]


def jina_embed(text: str, api_key: str) -> list[float]:
    r = requests.post("https://api.jina.ai/v1/embeddings",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        json={"model": "jina-embeddings-v3", "input": [text], "task": "retrieval.passage", "dimensions": TARGET_DIM},
        timeout=30)
    if not r.ok: raise RuntimeError(f"jina {r.status_code}: {r.text[:160]}")
    vec = r.json().get("data", [{}])[0].get("embedding")
    if not isinstance(vec, list) or len(vec) != TARGET_DIM:
        raise RuntimeError(f"jina bad shape")
    return vec


PROVIDERS = [("voyage", "VOYAGE_API_KEY", voyage_embed),
             ("jina",   "JINA_API_KEY",   jina_embed)]


def gen_embed(text: str) -> tuple[list[float], str]:
    errs = []
    for n, k, fn in PROVIDERS:
        key = os.getenv(k)
        if not key: continue
        try:
            return fn(text, key), n
        except Exception as e:
            errs.append(f"{n}: {e}")
    raise RuntimeError(f"all providers failed: {' | '.join(errs)}")


def build_summary(row: tuple) -> str:
    """Build canonical identity text per asset.
    Schema: tag, name, manufacturer, model, serial_no, location, iso_class, criticality"""
    tag, name, mfr, model, serial, loc, iso_cls, crit = row
    parts = []
    if tag:       parts.append(f"tag {tag}")
    if name:      parts.append(name)
    if mfr:       parts.append(mfr)
    if model:     parts.append(f"model {model}")
    if serial:    parts.append(f"S/N {serial}")
    if loc:       parts.append(f"at {loc}")
    if iso_cls:   parts.append(f"ISO class {iso_cls}")
    if crit:      parts.append(f"criticality {crit}")
    return " — ".join(parts) or "unnamed asset"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reembed", action="store_true")
    args = parser.parse_args(argv)

    print("=" * 70)
    print("FILL asset_embeddings via Voyage->Jina")
    print("=" * 70)

    if not (os.getenv("VOYAGE_API_KEY") or os.getenv("JINA_API_KEY")):
        print("[FAIL] No embedding keys"); return 1

    conn = psycopg2.connect(host="127.0.0.1", port=54322, user="postgres",
                            password="postgres", database="postgres")
    conn.autocommit = True
    cur = conn.cursor()

    if args.reembed:
        cur.execute("DELETE FROM asset_embeddings")
        print(f"  cleared {cur.rowcount} existing rows")

    cur.execute("""
        SELECT n.id, n.hive_id, n.tag, n.name, n.manufacturer, n.model,
               n.serial_no, n.location, n.iso_class, n.criticality
          FROM asset_nodes n
         WHERE NOT EXISTS (SELECT 1 FROM asset_embeddings e WHERE e.node_id = n.id)
         ORDER BY n.created_at
    """)
    rows = cur.fetchall()
    total = len(rows)
    print(f"Rows to embed: {total}\n")
    if not total:
        print("[OK] nothing to do"); return 0

    embedded = 0
    by_prov: dict[str, int] = {}
    fail = 0
    for i, r in enumerate(rows, start=1):
        nid, hive, *cols = r
        summary = build_summary(cols)
        try:
            vec, prov = gen_embed(summary)
            by_prov[prov] = by_prov.get(prov, 0) + 1
            vec_lit = "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
            cur.execute("""INSERT INTO asset_embeddings
                           (node_id, hive_id, summary, embedding, refreshed_at)
                           VALUES (%s, %s, %s, %s::vector, NOW())""",
                        (nid, hive, summary[:2000], vec_lit))
            embedded += 1
            if i % 20 == 0 or i == total:
                print(f"  [{i:3d}/{total}] {prov}  (running: voyage={by_prov.get('voyage', 0)} jina={by_prov.get('jina', 0)})")
        except Exception as e:
            fail += 1
            if fail <= 3:
                print(f"  [{i:3d}/{total}] FAIL: {e}")
        time.sleep(0.08)

    cur.execute("SELECT COUNT(*) FROM asset_embeddings")
    final = cur.fetchone()[0]
    print(f"\nRESULT: {embedded} embedded, {fail} failed. asset_embeddings now has {final} rows.")
    print(f"  Providers: {dict(by_prov)}")
    cur.close()
    conn.close()
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
