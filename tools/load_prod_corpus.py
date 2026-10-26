#!/usr/bin/env python3
"""load_prod_corpus.py - production gets the reference corpus the AI is built on, in production's own space (BRH-AC, 2026-10-26).

Read on production 2026-10-26: persona_knowledge 0 rows (local 434), industry_standards 10 rows with 0 embedded (local
41), industry_standards_chunks 0 (local 781), 5 of 10 voice journal entries never embedded, and the few knowledge rows
there were embedded with models nothing in production can query (nomic, a dead Voyage key). The corpora are built
locally by the ingest tools against the local stack; nothing ever carried them to production.

This carries them. Each row's text is composed exactly as its ingest tool composes it, embedded with production's
primary (EMBEDDING_PRIMARY=gemini: the same OpenAI-compatible gemini-embedding-001 request at 384 dims plus the L2
normalisation the edge applies - tools/ingest_persona_knowledge._batch_gemini mirrors it), and upserted on the
corpus's natural key, so a re-run replaces rather than duplicates:
  industry_standards         ON (standard_code)          text: code - title - notes
  industry_standards_chunks  ON (standard_id, chunk_num) standard_id re-read through standard_code (production's ids differ)
  persona_knowledge          ON (source, chunk_index)    text: context_header + newline + content; tagged gemini-embedding-001@384
  voice_journal_entries      re-embed every entry's transcript in place (the gateway's own rule: generateEmbedding(transcript))
  fault/pm/skill knowledge   rows in a foreign space are re-queued from their source rows; the outbox relay re-embeds them;
                             a row whose source is gone is re-embedded in place from its own fields ("stranded")

Production is written through the Management API's SQL endpoint with the token `supabase login` keeps (or
SUPABASE_ACCESS_TOKEN). Neither the token nor any row's text is printed.

    python tools/load_prod_corpus.py --dry-run          # counts and what would be written
    python tools/load_prod_corpus.py                    # load everything
    python tools/load_prod_corpus.py --only persona_knowledge
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from ingest_persona_knowledge import _batch_gemini, _envval  # noqa: E402  (the edge-exact Gemini request)

REF = "hzyvnjtisfgbksicrouu"
API = f"https://api.supabase.com/v1/projects/{REF}/database/query"
PROD_MODEL_TAG = "gemini-embedding-001@384"
BATCH = 50


def mgmt_token() -> str:
    tok = os.environ.get("SUPABASE_ACCESS_TOKEN", "").strip()
    if tok:
        return tok
    r = subprocess.run(["powershell", "-NoProfile", "-File", str(ROOT / "tools" / "supabase_cli_token.ps1")],
                       capture_output=True, text=True, timeout=60)
    return (r.stdout or "").strip()


def prod_sql(sql: str, token: str, retries: int = 3):
    body = json.dumps({"query": sql}).encode()
    for attempt in range(retries + 1):
        req = urllib.request.Request(API, data=body, method="POST",
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode() or "[]")
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            if e.code in (429, 502, 503, 504) and attempt < retries:
                time.sleep(5 * (attempt + 1))
                continue
            raise RuntimeError(f"production SQL {e.code}: {msg}") from None


def local_rows(sql: str) -> list[dict]:
    r = subprocess.run(["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-At", "-c", sql],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"local read failed: {r.stderr[:200]}")
    return json.loads(r.stdout.strip() or "[]")


def q(v) -> str:
    """A SQL literal for a JSON-decoded value."""
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, (list, dict)):
        return "'" + json.dumps(v).replace("'", "''") + "'::jsonb"
    return "'" + str(v).replace("'", "''") + "'"


def vec(v: list[float]) -> str:
    return "'[" + ",".join(f"{x:.7f}" for x in v) + "]'::vector"


def embed_all(texts: list[str], key: str, batch: int = BATCH) -> list[list[float]]:
    """Batches are sized to the free tier's per-MINUTE TOKEN cap, not its request cap: 50 standards chunks (avg 2.6K
    chars) are ~33K tokens, and that batch drew 429 until its retries ran out (2026-10-26). Long texts take smaller
    batches; each text is capped under gemini-embedding-001's 2,048-token input."""
    texts = [t[:6000] for t in texts]
    out: list[list[float]] = []
    for i in range(0, len(texts), batch):
        part = _batch_gemini(texts[i:i + batch], key)
        if not part or any(v is None for v in part):
            raise RuntimeError(f"gemini refused batch {i // batch + 1} - nothing from it was written")
        out.extend(part)
        print(f"    embedded {len(out)}/{len(texts)}", file=sys.stderr, flush=True)
        time.sleep(1.0)
    return out


def load_standards(token: str, key: str, dry: bool) -> dict:
    rows = local_rows("select coalesce(json_agg(to_jsonb(s) - 'embedding' - 'id' order by standard_code), '[]') "
                      "from public.industry_standards s")
    texts = [" — ".join(filter(None, [r["standard_code"], r["title"], r.get("notes") or ""]))[:8000] for r in rows]
    if dry:
        return {"industry_standards": len(rows)}
    vecs = embed_all(texts, key)
    cols = [c for c in rows[0].keys()]
    upd = ", ".join(f"{c} = excluded.{c}" for c in cols if c not in ("standard_code", "created_at"))
    for i in range(0, len(rows), BATCH):
        vals = ",\n".join("(" + ", ".join(q(r[c]) for c in cols) + ", " + vec(v) + ")"
                          for r, v in zip(rows[i:i + BATCH], vecs[i:i + BATCH]))
        prod_sql(f"insert into public.industry_standards ({', '.join(cols)}, embedding) values {vals} "
                 f"on conflict (standard_code) do update set {upd}, embedding = excluded.embedding;", token)
    return {"industry_standards": len(rows)}


def load_chunks(token: str, key: str, dry: bool, cap: int = 300) -> dict:
    rows = local_rows("select coalesce(json_agg(jsonb_build_object('code', s.standard_code, 'chunk_num', c.chunk_num, "
                      "'section', c.section, 'text', c.text, 'source_pdf', c.source_pdf) order by s.standard_code, c.chunk_num), '[]') "
                      "from public.industry_standards_chunks c join public.industry_standards s on s.id = c.standard_id")
    if dry:
        return {"industry_standards_chunks": len(rows)}
    # RESUMABLE, WRITTEN AS IT GOES (2026-10-26): the first run embedded 392 of 781 chunks, hit the free tier's per-minute
    # cap past its retries, and wrote nothing - every vector was held until the end. Chunks production already holds with
    # an embedding are skipped, each batch is written the moment it is embedded, and the pace stays near 80 inputs a minute.
    have = {(h["code"], h["chunk_num"]) for h in prod_sql(
        "select s.standard_code code, c.chunk_num from public.industry_standards_chunks c "
        "join public.industry_standards s on s.id = c.standard_id where c.embedding is not null", token)}
    # A DAILY BUDGET (2026-10-26): Gemini's free tier allows 1,000 embed requests a day, counted per TEXT, and that
    # one allowance is production's whole embedding budget - every logbook save and every assistant turn draw on it.
    # The first full load spent it and left production's retrieval falling through to another space for ~23 hours.
    # A run embeds at most `cap` chunks (default 300) and stops; the rest wait for the next day's allowance.
    todo = [r for r in rows if (r["code"], r["chunk_num"]) not in have][:cap]
    step = 8
    for i in range(0, len(todo), step):
        part = todo[i:i + step]
        vecs = embed_all([(r["text"] or "") for r in part], key, batch=step)
        vals = ",\n".join(f"({q(r['code'])}, {q(r['chunk_num'])}, {q(r['section'])}, {q(r['text'])}, {q(r['source_pdf'])}, {vec(v)})"
                          for r, v in zip(part, vecs))
        prod_sql("insert into public.industry_standards_chunks (standard_id, chunk_num, section, text, source_pdf, embedding) "
                 f"select s.id, v.chunk_num, v.section, v.text, v.source_pdf, v.embedding "
                 f"from (values {vals}) v(code, chunk_num, section, text, source_pdf, embedding) "
                 "join public.industry_standards s on s.standard_code = v.code "
                 "on conflict (standard_id, chunk_num) do update set section = excluded.section, text = excluded.text, "
                 "source_pdf = excluded.source_pdf, embedding = excluded.embedding;", token)
        print(f"    written {len(have) + i + len(part)}/{len(rows)}", file=sys.stderr, flush=True)
        time.sleep(5.0)
    return {"industry_standards_chunks": len(rows), "already_there": len(have), "written": len(todo)}


def load_persona(token: str, key: str, dry: bool) -> dict:
    rows = local_rows("select coalesce(json_agg(to_jsonb(p) - 'embedding' - 'embedding_model' - 'created_at' - 'updated_at' "
                      "order by source, chunk_index), '[]') from public.persona_knowledge p")
    if dry:
        return {"persona_knowledge": len(rows)}
    vecs = embed_all([f"{r.get('context_header') or ''}\n{r.get('content') or ''}" for r in rows], key)
    cols = list(rows[0].keys())
    upd = ", ".join(f"{c} = excluded.{c}" for c in cols if c not in ("id", "source", "chunk_index"))
    for i in range(0, len(rows), BATCH):
        vals = ",\n".join("(" + ", ".join(q(r[c]) for c in cols) + f", {vec(v)}, {q(PROD_MODEL_TAG)}, now())"
                          for r, v in zip(rows[i:i + BATCH], vecs[i:i + BATCH]))
        prod_sql(f"insert into public.persona_knowledge ({', '.join(cols)}, embedding, embedding_model, updated_at) "
                 f"values {vals} on conflict (source, chunk_index) do update set {upd}, embedding = excluded.embedding, "
                 "embedding_model = excluded.embedding_model, updated_at = now();", token)
    return {"persona_knowledge": len(rows)}


def reembed_journal(token: str, key: str, dry: bool) -> dict:
    rows = prod_sql("select id, transcript from public.voice_journal_entries "
                    "where coalesce(btrim(transcript), '') <> '' order by created_at", token)
    if dry:
        return {"voice_journal_entries": len(rows)}
    vecs = embed_all([r["transcript"][:8000] for r in rows], key)
    for i in range(0, len(rows), BATCH):
        vals = ",\n".join(f"({q(r['id'])}::uuid, {vec(v)})" for r, v in zip(rows[i:i + BATCH], vecs[i:i + BATCH]))
        prod_sql(f"update public.voice_journal_entries j set embedding = v.e from (values {vals}) v(id, e) where j.id = v.id;", token)
    return {"voice_journal_entries": len(rows)}


COMPOSE = {
    # embed-entry's own text for each knowledge type (supabase/functions/embed-entry/index.ts), field for field
    "fault_knowledge": lambda r: ". ".join(x for x in [
        r.get("machine") and f"Equipment: {r['machine']}", r.get("problem") and f"Problem: {r['problem']}",
        r.get("root_cause") and f"Root cause: {r['root_cause']}", r.get("action") and f"Action taken: {r['action']}",
        r.get("knowledge") and f"Lesson learned: {r['knowledge']}", r.get("category") and f"Category: {r['category']}"] if x),
    "skill_knowledge": lambda r: ". ".join(x for x in [
        r.get("worker_name") and f"Technician: {r['worker_name']}", r.get("discipline") and f"Discipline: {r['discipline']}",
        r.get("level") and f"Skill level: {r['level']} out of 5", r.get("primary_skill") and f"Primary expertise: {r['primary_skill']}"] if x),
    "pm_knowledge": lambda r: ". ".join(x for x in [
        r.get("asset_name") and f"Asset: {r['asset_name']}", r.get("category") and f"Category: {r['category']}",
        r.get("health_summary")] if x),
}


def reembed_stranded(token: str, key: str, dry: bool) -> dict:
    """Knowledge rows in a space production cannot query whose SOURCE row is gone, so the relay has nothing to re-queue
    (2026-10-26: 30 skill rows from badges since replaced, 2 fault rows whose entries were deleted, 1 PM row - all in
    nomic or untagged). Each is re-embedded IN PLACE from its own fields, composed exactly as embed-entry composes it:
    the knowledge stays, and becomes findable."""
    out = {}
    for table, compose in COMPOSE.items():
        rows = prod_sql(f"select to_jsonb(k) - 'embedding' as r from public.{table} k "
                        "where coalesce(k.embedding_model, '') not in ('gemini', 'gemini-embedding-001@384')", token)
        rows = [x["r"] for x in rows]
        out[table] = len(rows)
        if dry or not rows:
            continue
        vecs = embed_all([compose(r) or "(empty)" for r in rows], key, batch=8)
        for i in range(0, len(rows), BATCH):
            vals = ",\n".join(f"({q(str(r['id']))}, {vec(v)})" for r, v in zip(rows[i:i + BATCH], vecs[i:i + BATCH]))
            prod_sql(f"update public.{table} k set embedding = v.e, embedding_model = 'gemini' "
                     f"from (values {vals}) v(id, e) where k.id::text = v.id;", token)
    return out


def requeue_foreign(token: str, dry: bool) -> dict:
    """Knowledge rows the relay writes, sitting in a space production cannot query: queue their source rows again."""
    sql = """
    with foreign_rows as (
      select 'logbook' st, fk.logbook_id::text rid from public.fault_knowledge fk
       where fk.logbook_id is not null and coalesce(fk.embedding_model, '') not in ('gemini', 'gemini-embedding-001@384')
      union
      select 'skill_badges', b.id::text from public.skill_badges b
      union
      select 'pm_completions', c.id::text from public.pm_completions c
       where not exists (select 1 from public.embedding_outbox o where o.source_table = 'pm_completions' and o.row_id = c.id::text)
    )
    %s"""
    if dry:
        return {"requeue": prod_sql(sql % "select st, count(*) n from foreign_rows group by st", token)}
    res = prod_sql(sql % "insert into public.embedding_outbox (source_table, row_id, op) "
                         "select st, rid, 'UPDATE' from foreign_rows on conflict do nothing returning source_table", token)
    return {"requeued": len(res)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", choices=["industry_standards", "industry_standards_chunks", "persona_knowledge",
                                       "voice_journal_entries", "requeue", "stranded"])
    ap.add_argument("--max", type=int, default=300, help="at most this many chunks embedded in one run (the daily budget)")
    a = ap.parse_args()
    token = mgmt_token()
    if not token:
        print("no Management API token: run `supabase login` or set SUPABASE_ACCESS_TOKEN")
        return 1
    key = _envval("GEMINI_API_KEY") or ""
    if not key and not a.dry_run:
        print("no GEMINI_API_KEY in .env")
        return 1
    steps = [("industry_standards", lambda: load_standards(token, key, a.dry_run)),
             ("industry_standards_chunks", lambda: load_chunks(token, key, a.dry_run, a.max)),
             ("persona_knowledge", lambda: load_persona(token, key, a.dry_run)),
             ("voice_journal_entries", lambda: reembed_journal(token, key, a.dry_run)),
             ("requeue", lambda: requeue_foreign(token, a.dry_run)),
             ("stranded", lambda: reembed_stranded(token, key, a.dry_run))]
    for name, fn in steps:
        if a.only and a.only != name:
            continue
        t0 = time.time()
        print(f"  {name}: {fn()} ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
