#!/usr/bin/env python3
"""backfill_fault_knowledge.py - build the fault RAG corpus for logbook rows that never reached embed-entry.

FOUND BY THE FIRST LIVE GROUNDING WALK (LM109, 2026-10-07). Asked "What maintenance has been done on FLT 9004
recently?" on Dela Cruz Delivery Fleet's alert hub, the companion answered "I don't have the specific maintenance
history for FLT 9004". The hive has 3,666 logbook rows and FLT 9004 alone has 611 - but fault_knowledge, the corpus
the gateway's knowledge context retrieves from (search_all_knowledge), held ZERO rows for that hive. A real save
reaches it through embed-entry (or the embedding outbox); seeded rows were inserted straight into logbook and never
did. Measured per hive: Tan Delivery Vans 0/2,878, Ramos Jeepney Line 0/2,877, Dela Cruz 0/3,666, Manila 1,700/7,700,
Baguio 944/6,944, Lucena 1,170/7,170. A grounding walk against that would measure the seed, not the product.

This does for those rows exactly what embed-entry's "fault" branch does for a saved entry:
  - the same text: "Equipment: …. Problem: …. Root cause: …. Action taken: …. Lesson learned: …. Category: …"
  - the same content guard: under 50 characters is skipped (insufficient context for retrieval)
  - the same conflict key: logbook_id (unique), so a row embed-entry already wrote is never touched
  - the same vector space the local query is pinned to: bge-small-en-v1.5 on the local embed_server (:8901)
It writes only to the LOCAL database, and only rows that do not exist.

Usage:  python tools/backfill_fault_knowledge.py [--hive <uuid>] [--batch 64] [--limit N] [--dry-run]
Needs:  the embed-server container running (docker start embed-server), psycopg2.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request

import psycopg2

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

DSN = "host=127.0.0.1 port=54322 dbname=postgres user=postgres password=postgres"
EMBED_URL = "http://127.0.0.1:8901/embed"
MODEL_TAG = "bge-small-en-v1.5-local"


def compose(r: dict) -> str:
    parts = [r["machine"] and f"Equipment: {r['machine']}", r["problem"] and f"Problem: {r['problem']}",
             r["root_cause"] and f"Root cause: {r['root_cause']}", r["action"] and f"Action taken: {r['action']}",
             r["knowledge"] and f"Lesson learned: {r['knowledge']}", r["category"] and f"Category: {r['category']}"]
    return ". ".join(p for p in parts if p)


def embed(texts: list[str]) -> list[list[float]]:
    req = urllib.request.Request(EMBED_URL, data=json.dumps({"texts": texts}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read())
    vecs = d.get("embeddings") or d.get("data") or d
    if not isinstance(vecs, list) or len(vecs) != len(texts):
        raise RuntimeError(f"embed_server returned {type(vecs).__name__} of {len(vecs) if isinstance(vecs, list) else '?'}")
    return vecs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hive", default=None)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    con = psycopg2.connect(DSN)
    cur = con.cursor()
    # ANNOUNCED SYSTEM WRITE (check_daily_row_cap's own opt-in): a historical backfill is not one person writing 200
    # rows today, and the per-user daily cap stopped this at row 64 on 2026-10-07. Session-scoped, this connection only.
    cur.execute("set workhive.row_cap_system_write = 'on'")
    cur.execute("select column_name from information_schema.columns where table_schema='public' and table_name='fault_knowledge'")
    fk_cols = {c for (c,) in cur.fetchall()}
    q = ("select l.id, l.hive_id, l.machine, l.category, l.problem, l.root_cause, l.action, l.knowledge, l.worker_name, "
         "l.maintenance_type, l.auth_uid from logbook l where not exists (select 1 from fault_knowledge f where f.logbook_id = l.id)")
    args: list = []
    if a.hive:
        q += " and l.hive_id = %s"
        args.append(a.hive)
    q += " order by l.hive_id, l.id"
    if a.limit:
        q += f" limit {int(a.limit)}"
    cur.execute(q, args)
    keys = ["id", "hive_id", "machine", "category", "problem", "root_cause", "action", "knowledge", "worker_name",
            "maintenance_type", "auth_uid"]
    rows = [dict(zip(keys, r)) for r in cur.fetchall()]
    todo = [(r, compose(r)) for r in rows]
    short = [r for r, t in todo if len(t.strip()) < 50]
    todo = [(r, t) for r, t in todo if len(t.strip()) >= 50]
    print(f"logbook rows with no fault_knowledge: {len(rows)} · under 50 chars (skipped, as embed-entry does): {len(short)} "
          f"· to embed: {len(todo)}")
    if a.dry_run or not todo:
        return 0
    # no `source`: embed-entry's fault branch sets none, so the column default applies (a CHECK allows only
    # manual / ai_visual_capture / cmms_import - a 'backfill' label was refused, 2026-10-07)
    cols = ["hive_id", "logbook_id", "machine", "category", "problem", "root_cause", "action", "knowledge", "worker_name",
            "embedding", "embedding_model", "maintenance_type", "auth_uid"]
    cols = [c for c in cols if c in fk_cols]
    sql = (f"insert into fault_knowledge ({', '.join(cols)}) values ({', '.join(['%s'] * len(cols))}) "
           f"on conflict (logbook_id) do nothing")
    t0, done = time.time(), 0
    for i in range(0, len(todo), a.batch):
        chunk = todo[i:i + a.batch]
        vecs = embed([t for _, t in chunk])
        for (r, _), v in zip(chunk, vecs):
            val = {"hive_id": r["hive_id"], "logbook_id": r["id"], "machine": r["machine"], "category": r["category"],
                   "problem": r["problem"], "root_cause": r["root_cause"], "action": r["action"],
                   "knowledge": r["knowledge"], "worker_name": r["worker_name"],
                   "embedding": "[" + ",".join(f"{x:.7f}" for x in v) + "]", "embedding_model": MODEL_TAG,
                   "maintenance_type": r["maintenance_type"], "source": "backfill-logbook", "auth_uid": r["auth_uid"]}
            cur.execute(sql, [val[c] for c in cols])
        con.commit()
        done += len(chunk)
        if (i // a.batch) % 20 == 0:
            print(f"  {done}/{len(todo)} embedded ({time.time() - t0:.0f}s)")
    print(f"done: {done} fault_knowledge rows written in {time.time() - t0:.0f}s ({MODEL_TAG})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
