#!/usr/bin/env python3
"""free_plan_evidence.py - the committed evidence behind BRH classes Z..AE (2026-10-21): the platform stays on the free
plans of both hosts.

Ian, 2026-10-21: *"you know that my platform always free, and also in vercel, why is it I am already at 70% where we
deploy only my platform is not that massive, also I am not upgrading to pro, can you just be proactive and do
appropriately what is needed for my platform."* The free plans are Vercel Hobby (10 GB of Deployment Storage, the
emails' subject) and Supabase Free (a 500 MB database, no daily backups, a project paused after a week of low
activity). This tool turns what was read into ONE committed JSON, so tools/bug_hunt_inventory.py measures the classes
from a file (deterministic, replayable) and never from a live connection:
  - every deployment Vercel's GitHub integration recorded on the public repository (GET /repos/.../deployments, no
    credential: the repository is public) - how many deployments each Vercel project has made, and when
  - production, read-only through the claude.ai Supabase connector: the database's size and its largest tables, the
    scheduled jobs and their run history, each table's insert and delete counters, the knowledge tables' rows and
    embeddings, the images stored inside rows, and the page-called functions production refuses a signed-in member
  - the local tree and database, read-only: the list reads that ship an inline photo column, and the reference corpora
    the AI is given locally
  - Vercel's own dashboard, signed in as the owner (2026-10-21, --dashboard): the projects that exist, the deployments
    stored and their aliases, the project's retention setting, and the Deployment Storage line by day. The repository's
    record is history - a project deleted in Vercel keeps its records there - so what Vercel STORES is read from Vercel.
    No credential is kept; a run without --dashboard carries the last dashboard read forward.
    python tools/free_plan_evidence.py --prod .tmp/mail/free_plan_prod.txt --deployments .tmp/gh_deployments_all.json \
        [--dashboard .tmp/vercel_dashboard.json] [--out free_plan_evidence.json]
How the production input was read (SELECT only; no credential leaves the connector):
  claude -p "<run these read-only queries on project hzyvnjtisfgbksicrouu>" --tools "" \
      --allowedTools mcp__claude_ai_Supabase__execute_sql --setting-sources user --no-session-persistence
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = "supabase_db_workhive"
# operational and telemetry tables: what the platform records about itself, not a person's work or an audit trail
# (audit trails keep their stated windows - Ian, 2026-09: "fix the words, not the data")
TELEMETRY = ("cron.job_run_details", "public.wh_traces", "public.analytics_events", "public.automation_log",
             "public.ai_cost_log", "public.client_errors")
# the reference corpora the AI is given (seeded, not written by people as they work)
CORPORA = ("industry_standards", "industry_standards_chunks", "persona_knowledge")


def blocks(text: str) -> dict:
    """{label: parsed JSON} for every '**Qn ...**' heading followed by a fenced JSON block in the connector output."""
    out = {}
    for m in re.finditer(r"\*\*(Q\d+b?)[^*]*\*\*\s*```[a-z]*\s*(.*?)```", text, re.S):
        try:
            out[m.group(1)] = json.loads(m.group(2))
        except json.JSONDecodeError:
            pass
    return out


def psql(sql: str) -> str:
    r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-At", "-f", "-"],
                       input=sql, capture_output=True, text=True, encoding="utf-8", timeout=120)
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[-200:])
    return r.stdout


def photo_reads() -> list[dict]:
    """List reads of logbook / inventory that ship the inline photo column (select * or naming photo)."""
    sys.path.insert(0, str(ROOT / "tools"))
    import validate_list_caps_say_more as g
    out = []
    pages = sorted(set(ROOT.glob("*.html")) | set(ROOT.glob("*/index.html")))
    for p in pages:
        src = g.blank_comments(p.read_text(encoding="utf-8", errors="replace"))
        for m in g.START.finditer(src):
            name = m.group(1) or ""
            if name not in ("logbook", "v_logbook_truth", "inventory_items", "v_inventory_items_truth"):
                continue
            stmt = src[m.start():g.chain_end(src, m)]
            if g.SINGLE.search(stmt):
                continue
            sel = re.search(r"\.select\(\s*(['\"`])(.*?)\1", stmt, re.S)
            cols = sel.group(2) if sel else "*"
            if cols.strip() == "*" or re.search(r"\bphoto\b", cols):
                out.append({"page": p.relative_to(ROOT).as_posix(), "line": src.count("\n", 0, m.start()) + 1, "src": name,
                            "cols": "*" if cols.strip() == "*" else "names photo"})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prod", required=True)
    ap.add_argument("--deployments", required=True)
    ap.add_argument("--dashboard", default=None)
    ap.add_argument("--out", default=str(ROOT / "free_plan_evidence.json"))
    a = ap.parse_args()
    q = blocks(Path(a.prod).read_text(encoding="utf-8"))
    deps = json.loads(Path(a.deployments).read_text(encoding="utf-8"))
    by_env = Counter(d.get("environment") or "?" for d in deps)
    projects = {}
    for env, n in by_env.items():
        ds = sorted(d["created_at"] for d in deps if (d.get("environment") or "?") == env)
        projects[env] = {"deployments": n, "first": ds[0][:10], "last": ds[-1][:10]}
    # the production builds by day: the cadence that, times what each build uploads, is what Vercel stores
    builds_per_day = dict(sorted(Counter(d["created_at"][:10] for d in deps if d.get("environment") == "Production").items()))
    if a.dashboard:
        dashboard = json.loads(Path(a.dashboard).read_text(encoding="utf-8"))
    else:
        prev = Path(a.out)
        dashboard = (json.loads(prev.read_text(encoding="utf-8")).get("vercel") or {}).get("dashboard") if prev.exists() else None
    q2 = {r["tbl"]: r for r in q.get("Q2", [])}
    growth = {r["tbl"]: r for r in q.get("Q13", [])}
    jobs = q.get("Q4", [])
    purged = {re.search(r"delete\s+from\s+(?:public\.)?([\w.]+)", j.get("command", ""), re.I).group(1)
              for j in jobs if re.search(r"delete\s+from\s+(?:public\.)?([\w.]+)", j.get("command", ""), re.I)}
    no_purge = []
    for t in TELEMETRY:
        if t == "cron.job_run_details":
            runs = (q.get("Q5") or [{}])[0]
            per_day = sum(int(r.get("runs_per_day") or 0) for r in q.get("Q15", []))
            no_purge.append({"table": t, "rows": runs.get("runs"), "since": str(runs.get("oldest") or "")[:10],
                             "bytes": (q2.get(t) or {}).get("bytes"), "per_day": per_day, "purged": t.split(".")[-1] in purged})
            continue
        g = growth.get(t) or {}
        no_purge.append({"table": t, "rows": g.get("live"), "inserted": g.get("inserted"), "deleted": g.get("deleted"),
                         "size": g.get("size"), "purged": t.split(".")[-1] in purged})
    emb = {r["t"]: r for r in q.get("Q8", [])}
    local = {}
    for line in psql("\n".join(f"select '{t}|' || count(*) || '|' || count(embedding) from public.{t};" for t in CORPORA)).splitlines():
        t, n, e = line.split("|")
        local[t] = {"rows": int(n), "embedded": int(e)}
    corpus = [{"table": t, "prod_rows": (emb.get(t) or {}).get("n"), "prod_embedded": (emb.get(t) or {}).get("filled"),
               "local_rows": local[t]["rows"]} for t in CORPORA]
    vj = emb.get("voice_journal_entries") or {}
    outbox = growth.get("public.embedding_outbox") or {}
    doc = {
        "_doc": "Committed evidence for BRH classes Z..AE (tools/free_plan_evidence.py). Re-read production and re-run to refresh.",
        "read": "2026-10-21",
        "vercel": {"plan": "Hobby", "allowance_gb": 10, "reported_use_pct": 70, "payload_mb_denylist": 612.7,
                   "payload_mb_allowlist": 19.7, "projects": projects, "builds_per_day": builds_per_day,
                   "dashboard": dashboard},
        "db": {"bytes": (q.get("Q1") or [{}])[0].get("bytes"), "free_limit_bytes": 500 * 1024 * 1024,
               "largest": [{"table": r["tbl"], "bytes": r["bytes"]} for r in q.get("Q2", [])[:8]]},
        "growth_no_purge": no_purge,
        "inline_photos": [{"column": r["col"], "rows": r["inline_rows"], "bytes": r["inline_bytes"]} for r in q.get("Q10", [])],
        "photo_reads": photo_reads(),
        "corpus": corpus,
        "outbox": {"queued": outbox.get("live"), "inserted": outbox.get("inserted"), "drained": outbox.get("deleted"),
                   "relay_job": any("embedding_outbox" in (j.get("command") or "") for j in jobs)},
        "voice_journal": {"rows": vj.get("n"), "embedded": vj.get("filled")},
        "refused": [{"function": r["proname"], "authenticated": r["auth_ok"], "anon": r["anon_ok"],
                     "pages": json.loads((ROOT / ".tmp" / "page_rpc_calls.json").read_text()).get(r["proname"], [])}
                    for r in (q.get("Q16") or [])] if (ROOT / ".tmp" / "page_rpc_calls.json").exists() else [],
        "plan_gaps": [
            {"key": "backups", "what": "the Free plan keeps no daily backups of the database"},
            {"key": "pausing", "what": "the Free plan pauses a project after 7 days of low activity"},
        ],
    }
    Path(a.out).write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {Path(a.out).name}: Z {len(projects)} project(s), {sum(p['deployments'] for p in projects.values())} deployments · "
          f"AA {len(no_purge)} tables · AB {len(doc['inline_photos'])} columns + {len(doc['photo_reads'])} reads · "
          f"AC {len(corpus)} corpora + outbox + voice journal · AD {len(doc['refused'])} · AE {len(doc['plan_gaps'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
