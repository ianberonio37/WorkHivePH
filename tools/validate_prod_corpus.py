#!/usr/bin/env python3
"""validate_prod_corpus.py - production's AI corpus is the one the AI is built on, in one space, and kept fed (BRH-AC, 2026-10-26).

Read on production 2026-10-26: 86 embedding jobs queued since August with 0 attempts (no relay ran there), persona_knowledge
0 of 434 rows, industry_standards 10 of 41 (none embedded), industry_standards_chunks 0 of 781, 5 of 10 voice journal
entries unembedded, the knowledge rows that existed in spaces nothing could query (nomic, a dead Voyage key), and every
logbook save answered 500 by embed-entry. The assistant deflected "what does MTBF measure?" with "none of my sources
returned anything".

LIVE (production, through the Management API - the token `supabase login` keeps, or SUPABASE_ACCESS_TOKEN):
  - persona_knowledge, industry_standards, industry_standards_chunks hold at least the local corpus's rows, all embedded
  - persona_knowledge sits in ONE space, production's (gemini-embedding-001@384)
  - fault / pm / skill knowledge: no row tagged with a model production cannot query
  - every voice journal entry with a transcript is embedded
  - the relay is scheduled and draining: no job left open more than an hour without an attempt
STATIC (the tree):
  - an embedding pin this environment cannot serve resolves to the environment's primary (embedding-chain.ts)
  - the relay sweeps orphans before it claims, waits a provider outage out (48 attempts) and probes a dead
    provider once a tick instead of sending its batch (20261026000011, 000014)
  Teeth (--self-test): both static facts fail on the tree as committed at 1045f447.

Without a way to ask production this SKIPs; --require-prod makes that a FAIL.

    python tools/validate_prod_corpus.py [--require-prod]
    python tools/validate_prod_corpus.py --self-test
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = "hzyvnjtisfgbksicrouu"
API = f"https://api.supabase.com/v1/projects/{REF}/database/query"
CHAIN = "supabase/functions/_shared/embedding-chain.ts"
RELAY = "supabase/migrations/20261026000014_the_relay_stops_hammering_a_dead_provider.sql"   # the relay's newest definition
PROD_TAGS = ("gemini", "gemini-embedding-001@384")
CORPORA = ("persona_knowledge", "industry_standards", "industry_standards_chunks")


def static_findings(chain: str, relay: str) -> list[str]:
    out = []
    if not re.search(r"providerConfigured\(asked\)\s*\?\s*asked\s*:\s*EMBEDDING_PRIMARY", chain):
        out.append("embedding-chain.ts: a pin this environment cannot serve does not resolve to its primary")
    if not (relay and "relay_embedding_outbox" in relay and "SWEEP orphans" in relay):
        out.append("no relay migration that sweeps orphans before it claims")
    # a provider outage is waited out (48 attempts, not 5) and a dead provider gets one probe a tick, not the batch
    elif not ("v_limit := CASE WHEN v_wait THEN 48" in relay and "breaker_open" in relay):
        out.append("the relay dead-letters a provider outage or keeps hammering a dead provider")
    return out


def token() -> str:
    t = os.environ.get("SUPABASE_ACCESS_TOKEN", "").strip()
    if t or sys.platform != "win32":
        return t
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-File", str(ROOT / "tools" / "supabase_cli_token.ps1")],
                           capture_output=True, text=True, timeout=60)
        return (r.stdout or "").strip()
    except Exception:
        return ""


def prod(sql: str, tok: str):
    req = urllib.request.Request(API, data=json.dumps({"query": sql}).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode() or "[]")


def local_counts() -> dict:
    sql = " union all ".join(f"select '{t}', count(*) from public.{t}" for t in CORPORA)
    r = subprocess.run(["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-At", "-F", "|", "-c", sql],
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return {}
    return {a: int(b) for a, b in (ln.split("|") for ln in r.stdout.split() if "|" in ln)}


def live_findings(tok: str) -> tuple[list[str], list[str]]:
    rows = prod("""
      select 'persona_knowledge' t, count(*) n, count(embedding) e, count(distinct embedding_model) m,
             string_agg(distinct embedding_model, ',') tags from public.persona_knowledge
      union all select 'industry_standards', count(*), count(embedding), null, null from public.industry_standards
      union all select 'industry_standards_chunks', count(*), count(embedding), null, null from public.industry_standards_chunks
      union all select 'foreign_knowledge', count(*), null, null, string_agg(distinct coalesce(embedding_model, '(none)'), ',') from (
        select embedding_model from public.fault_knowledge union all select embedding_model from public.pm_knowledge
        union all select embedding_model from public.skill_knowledge) k
        where coalesce(embedding_model, '') not in ('gemini', 'gemini-embedding-001@384')
      union all select 'journal_unembedded', count(*), null, null, null from public.voice_journal_entries
        where coalesce(btrim(transcript), '') <> '' and embedding is null
      union all select 'outbox_stalled', count(*), null, null, null from public.embedding_outbox
        where done_at is null and attempts = 0 and enqueued_at < now() - interval '1 hour'
      union all select 'outbox_dead', count(*), null, null, null from public.embedding_outbox where last_error like 'DEAD%'
      union all select 'relay_job', count(*), null, null, null from cron.job where jobname = 'embedding-outbox-relay' and active
    """, tok)
    got = {r["t"]: r for r in rows}
    want = local_counts()
    bad, notes = [], []
    for t in CORPORA:
        g = got.get(t) or {}
        n, e = int(g.get("n") or 0), int(g.get("e") or 0)
        notes.append(f"{t} {e}/{n} embedded (local {want.get(t, '?')})")
        if want and n < want.get(t, 0):
            bad.append(f"{t}: production holds {n}, the AI is built on {want[t]}")
        if e < n:
            bad.append(f"{t}: {n - e} of {n} rows have no embedding")
    p = got.get("persona_knowledge") or {}
    if int(p.get("m") or 0) > 1 or (p.get("tags") and p["tags"] not in PROD_TAGS):
        bad.append(f"persona_knowledge is not in production's one space: {p.get('tags')}")
    fk = got.get("foreign_knowledge") or {}
    if int(fk.get("n") or 0):
        bad.append(f"{fk['n']} fault/pm/skill knowledge rows sit in a space production cannot query ({fk.get('tags')})")
    if int((got.get("journal_unembedded") or {}).get("n") or 0):
        bad.append(f"{got['journal_unembedded']['n']} voice journal entries with a transcript are not embedded")
    if int((got.get("outbox_stalled") or {}).get("n") or 0):
        bad.append(f"{got['outbox_stalled']['n']} outbox jobs older than an hour were never attempted - nothing is draining")
    if not int((got.get("relay_job") or {}).get("n") or 0):
        bad.append("the embedding-outbox-relay cron job is not scheduled and active")
    notes.append(f"outbox dead-lettered {int((got.get('outbox_dead') or {}).get('n') or 0)}")
    return bad, notes


def self_test() -> int:
    cur = static_findings((ROOT / CHAIN).read_text(encoding="utf-8"), (ROOT / RELAY).read_text(encoding="utf-8")
                          if (ROOT / RELAY).exists() else "")
    old_chain = subprocess.run(["git", "show", f"1045f447:{CHAIN}"], cwd=ROOT, capture_output=True).stdout.decode("utf-8", "replace")
    old_relay = subprocess.run(["git", "show", f"1045f447:{RELAY}"], cwd=ROOT, capture_output=True).stdout.decode("utf-8", "replace")
    red = static_findings(old_chain, old_relay)
    print(f"  {'PASS' if not cur else 'FAIL'} the tree holds both static facts {cur or ''}")
    print(f"  {'PASS' if len(red) == 2 else 'FAIL'} teeth: the tree at 1045f447 fails {len(red)}/2")
    ok = not cur and len(red) == 2
    print(("PASS" if ok else "FAIL") + " prod-corpus self-test")
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    print("prod-corpus (BRH-AC): production's AI corpus is the one the AI is built on, in one space, and kept fed")
    bad = static_findings((ROOT / CHAIN).read_text(encoding="utf-8"),
                          (ROOT / RELAY).read_text(encoding="utf-8") if (ROOT / RELAY).exists() else "")
    tok = token()
    if not tok:
        print("  - production could not be asked (no `supabase login` token, no SUPABASE_ACCESS_TOKEN)")
        for b in bad:
            print(f"  - {b}")
        if "--require-prod" in sys.argv or bad:
            print("FAIL")
            return 1
        print("SKIP")
        return 0
    try:
        live, notes = live_findings(tok)
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"  - production read failed: {str(e)[:160]}")
        print("FAIL" if "--require-prod" in sys.argv else "SKIP")
        return 1 if "--require-prod" in sys.argv else 0
    for n in notes:
        print(f"  {n}")
    bad += live
    for b in bad:
        print(f"  - {b}")
    print("PASS" if not bad else "FAIL")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
