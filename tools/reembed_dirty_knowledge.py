#!/usr/bin/env python3
"""reembed_dirty_knowledge.py - SELF-HEALING re-embed sweep for the OWN-EMBEDDER (2026-07-12).

The hands-free keystone (Ian's OWN-EMBEDDER vision): a user's own activity embeds their data
on-write via the local bge-local server (embed-entry). But if bge-local was DOWN at write time,
that row was embedded in a foreign space (voyage) or left NULL - a "dirty" vector that pollutes
retrieval. This sweep RE-HEALS the corpus: it finds every DIRTY row (NULL embedding OR a stamp
that isn't the canonical bge-local model) across every knowledge corpus and re-embeds it via the
now-running local model - putting the whole corpus back in ONE lockstep space.

IDEMPOTENT: when everything is already in bge-local space it is a cheap no-op (0 dirty rows), so it
is safe to run on a schedule. That schedule is what makes it hands-free - the founder never runs a
manual backfill; the platform re-heals itself after any embedder outage.

Wire it hands-free (any ONE):
  • host cron / Task Scheduler: `python tools/reembed_dirty_knowledge.py` every ~15 min
  • or call from a scheduled-agent tick after a bge-local health check

Run:  python tools/reembed_dirty_knowledge.py            # all hives, all corpora
      python tools/reembed_dirty_knowledge.py --hive <uuid>
Needs: the local embed_server on :8901 (python tools/embed_server.py 8901).
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import urllib.request

import psycopg2

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

# Env-configurable so the SAME sweep runs from the host (defaults: DB host-port 54322, embedder
# host-port 8901) OR from inside the embedder container on the supabase network (WH_DB_DSN points at
# supabase_db_workhive:5432, WH_EMBED_URL at localhost:8901). That is what lets the robust container
# self-heal its own corpus hands-free.
DSN = os.environ.get("WH_DB_DSN", "host=127.0.0.1 port=54322 dbname=postgres user=postgres password=postgres")
EMBED_URL = os.environ.get("WH_EMBED_URL", "http://127.0.0.1:8901/embed")
HEALTH_URL = os.environ.get("WH_EMBED_HEALTH_URL", EMBED_URL.replace("/embed", "/health"))
MODEL_TAG = "bge-small-en-v1.5-local"

# Per-corpus: the text-composition columns (in priority order). Only rows whose embedding is NULL
# or whose embedding_model != MODEL_TAG are swept - that is the "dirty" definition.
CORPORA = {
    "fault_knowledge": ["machine", "problem", "root_cause", "action", "knowledge"],
    "pm_knowledge":    ["asset_name", "category", "health_summary"],
    "skill_knowledge": ["skill_name", "summary", "detail"],
}


def _compose(row: dict, cols: list[str]) -> str:
    parts = [str(row[c]) for c in cols if row.get(c) and str(row[c]).strip()]
    return " ".join(parts).strip() or "entry"


def _embed_batch(texts: list[str]) -> list[list[float]]:
    req = urllib.request.Request(EMBED_URL, data=json.dumps({"texts": texts}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=120).read())["embeddings"]


def _table_columns(cur, table: str) -> set[str]:
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s AND table_schema='public'", (table,))
    return {r[0] for r in cur.fetchall()}


def sweep_corpus(cur, conn, table: str, text_cols: list[str], hive: str | None, batch: int) -> tuple[int, int]:
    """Returns (dirty_found, re_embedded)."""
    have = _table_columns(cur, table)
    if not have or "embedding" not in have:
        return (0, 0)
    cols = [c for c in text_cols if c in have]
    if not cols:
        return (0, 0)
    sel = ", ".join(["id"] + cols)
    where = ["(embedding IS NULL OR embedding_model IS DISTINCT FROM %s)"]
    params: list = [MODEL_TAG]
    if hive and "hive_id" in have:
        where.append("hive_id = %s")
        params.append(hive)
    cur.execute(f"SELECT {sel} FROM {table} WHERE {' AND '.join(where)} ORDER BY id", params)
    names = [d[0] for d in cur.description]
    rows = [dict(zip(names, r)) for r in cur.fetchall()]
    if not rows:
        return (0, 0)
    done = 0
    for i in range(0, len(rows), batch):
        chunk = rows[i:i + batch]
        vecs = _embed_batch([_compose(r, cols) for r in chunk])
        for r, v in zip(chunk, vecs):
            if len(v) != 384:
                continue
            cur.execute(f"UPDATE {table} SET embedding = %s::vector, embedding_model = %s WHERE id = %s",
                        ("[" + ",".join(repr(float(x)) for x in v) + "]", MODEL_TAG, r["id"]))
            done += 1
        conn.commit()
    return (len(rows), done)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hive", default=None)
    ap.add_argument("--batch", type=int, default=64)
    args = ap.parse_args()

    # Recovery gate: only heal when the canonical embedder is actually up - else a run would
    # re-dirty everything via a fallback space. No embedder ⇒ nothing to heal yet (clean exit).
    try:
        urllib.request.urlopen(HEALTH_URL, timeout=10)
    except Exception as e:
        print(f"  bge-local not reachable on :8901 ({type(e).__name__}) - self-heal skipped (nothing to do until it recovers)")
        return 0

    conn = psycopg2.connect(DSN)
    conn.autocommit = False
    cur = conn.cursor()
    total_dirty = total_healed = 0
    for table, text_cols in CORPORA.items():
        dirty, healed = sweep_corpus(cur, conn, table, text_cols, args.hive, args.batch)
        total_dirty += dirty
        total_healed += healed
        if dirty:
            print(f"  {table}: {dirty} dirty → {healed} re-embedded in {MODEL_TAG}")
        else:
            print(f"  {table}: clean (0 dirty)")
    cur.close(); conn.close()
    print(f"  SELF-HEAL DONE: {total_healed}/{total_dirty} dirty rows re-embedded into one bge-local space"
          if total_dirty else "  SELF-HEAL: corpus already in lockstep (0 dirty) - no-op")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
