#!/usr/bin/env python3
"""reembed_fault_knowledge.py — put the fault RAG corpus into ONE quota-free vector space.

THE STRUCTURAL FIX (Ian, 2026-06-21: "we can also improve the structure, like those you are
having a problem"). The fault_knowledge corpus was a mess that made live RAG retrieval flaky:
  • 551 rows, only 191 with a non-NULL embedding (360 UNSEARCHABLE).
  • all tagged embedding_model='nomic-embed-text-v1_5' — a model that is NOT in the live edge
    provider chain (voyage/gemini/cloudflare/jina/bge-local), so NO live query vector truly
    shares the stored space → near-random cosine matches, retrieval that returned 0 or 5
    depending on which free-tier provider happened to answer.

This re-embeds EVERY fault row with the self-hosted bge-small-en-v1.5 model (the local
embed_server on :8901, 384-dim, NO rate limit) and stamps embedding_model accordingly. Paired
with pinning the LOCAL edge query to bge-local (EMBEDDING_PRIMARY), ingest and query are then in
LOCKSTEP in one space — retrieval is deterministic, complete, and quota-free. (Per the lockstep
doctrine in _shared/embedding-chain.ts: "re-embed a corpus AND flip its pin together".)

Text composed exactly as the search context renders it (machine/problem/root_cause/action/knowledge),
so the query "high vibration" lands near the row that says high vibration.

Usage:  python tools/reembed_fault_knowledge.py            # all hives
        python tools/reembed_fault_knowledge.py --hive <uuid>
Needs:  embed_server.py running on :8901 (bge-small-en-v1.5), psycopg2.
Skills: ai-engineer (embedding lockstep), data-engineer (corpus backfill), qa (live RAG reliability).
"""
from __future__ import annotations
import argparse
import json
import sys
import urllib.request
from pathlib import Path

import psycopg2

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

DSN = "host=127.0.0.1 port=54322 dbname=postgres user=postgres password=postgres"
EMBED_URL = "http://127.0.0.1:8901/embed"
MODEL_TAG = "bge-small-en-v1.5-local"


def _compose(row: dict) -> str:
    parts = [row.get("machine"), row.get("problem"), row.get("root_cause"),
             row.get("action"), row.get("knowledge")]
    return " ".join(str(p) for p in parts if p and str(p).strip()).strip() or (row.get("machine") or "fault")


def _embed_batch(texts: list[str]) -> list[list[float]]:
    req = urllib.request.Request(EMBED_URL, data=json.dumps({"texts": texts}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    resp = json.loads(urllib.request.urlopen(req, timeout=120).read())
    return resp["embeddings"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hive", default=None)
    ap.add_argument("--batch", type=int, default=64)
    args = ap.parse_args()

    # embed server reachable?
    try:
        urllib.request.urlopen("http://127.0.0.1:8901/health", timeout=10)
    except Exception as e:
        print(f"  embed_server not reachable on :8901 ({type(e).__name__}) — start `python tools/embed_server.py 8901`")
        return 1

    conn = psycopg2.connect(DSN)
    conn.autocommit = False
    cur = conn.cursor()
    where = "WHERE hive_id = %s" if args.hive else ""
    params = (args.hive,) if args.hive else ()
    cur.execute(f"SELECT id, machine, problem, root_cause, action, knowledge FROM fault_knowledge {where} ORDER BY id", params)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    print(f"  fault_knowledge rows to re-embed: {len(rows)}  (model→{MODEL_TAG}, 384d, quota-free)")
    if not rows:
        print("  nothing to do")
        return 0

    done = 0
    for i in range(0, len(rows), args.batch):
        chunk = rows[i:i + args.batch]
        vecs = _embed_batch([_compose(r) for r in chunk])
        for r, v in zip(chunk, vecs):
            if len(v) != 384:
                print(f"  WARN row {r['id']} got {len(v)}-dim, skipping")
                continue
            cur.execute("UPDATE fault_knowledge SET embedding = %s::vector, embedding_model = %s WHERE id = %s",
                        ("[" + ",".join(repr(float(x)) for x in v) + "]", MODEL_TAG, r["id"]))
            done += 1
        conn.commit()
        print(f"  …{done}/{len(rows)}")
    cur.execute(f"SELECT count(*) total, count(embedding) emb FROM fault_knowledge {where}", params)
    total, emb = cur.fetchone()
    cur.close(); conn.close()
    print(f"  DONE: {done} re-embedded · coverage now {emb}/{total} embedded in {MODEL_TAG} space")
    return 0


if __name__ == "__main__":
    sys.exit(main())
