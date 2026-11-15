#!/usr/bin/env python3
"""vx_lm_step.py - one step of the Wave VX-L walk loop (2026-11-15): bank the row just walked, then write the args
for the next open VX-L row. The walk itself is the Playwright MCP running tools/lm_walk.js (the instrument the LM
banker accepts), so it cannot run from here; this keeps each row to two calls: this step, then the MCP walk.

    python tools/vx_lm_step.py [--bank VX2755] [--next]

--bank reads the postgres witness itself (ai_audit_log and logbook rows by the cast since the walk began) and passes
the gate PASS summary of the sub-layer's gates, which run_platform_checks.py --only must have passed this session
(.tmp/vx_lm_gates.json, written by --gates).
"""
from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
GATES_FILE = ROOT / ".tmp" / "vx_lm_gates.json"
DB = "supabase_db_workhive"
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def psql(sql: str) -> str:
    r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-tAq", "-c", sql],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "").strip()


def bank(rid: str) -> int:
    recs = json.loads((ROOT / ".tmp" / "w4_steps" / f"{rid}.records.json").read_text(encoding="utf-8"))
    res, P = recs.get("result") or {}, recs.get("args") or {}
    # ★AN ASK THAT SENT NOTHING PROVES NOTHING (VX2936, 2026-11-15): the 1280 page loaded half (893 chars) and sent no
    # request, and the walker still said ok. A width with sent=0 is re-walked, never banked.
    if any(" sent=0 " in f" {s} " for s in (res.get("steps") or [])):
        print(f"{rid}: NOT banked - a width sent no request ({'; '.join(s for s in res['steps'] if 'sent=0' in s)}); re-walk it")
        return 1
    cast, started = (P.get("castName") or "").replace("'", "''"), res.get("started")
    ai = psql(f"select count(*) from ai_audit_log where worker_name='{cast}' and created_at > '{started}'")
    lb = psql(f"select count(*) from logbook where worker_name='{cast}' and created_at > '{started}'")
    pg = (f"postgres read via docker psql (the postgres-mcp witness query): ai_audit_log and logbook rows by {P.get('castName')} "
          f"since the walk began ({started}) = {ai} and {lb}")
    gates = json.loads(GATES_FILE.read_text(encoding="utf-8")) if GATES_FILE.exists() else {}
    sub = P.get("sublayer")
    if sub not in gates:
        print(f"{rid}: the {sub} gates have not passed this session - run with --gates first")
        return 1
    if ai != "0" or lb != "0":
        print(f"{rid}: NOT banked - the walk wrote {ai} AI and {lb} logbook row(s)")
        return 1
    import os
    r = subprocess.run([sys.executable, "tools/bank_lm_walk.py", rid, "--pg", pg, "--gates-ok", gates[sub]],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT),
                       env=dict(os.environ, LM_BANK_BATCH="1"))
    print(((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-1][:220])
    return r.returncode


PENDING = ROOT / ".tmp" / "lm_bank_pending.jsonl"
SKIP = ROOT / ".tmp" / "vx_lm_skip.txt"
OPEN = ROOT / ".tmp" / "vx_lm_open.json"


def _queued() -> set:
    done = set(SKIP.read_text(encoding="utf-8").split()) if SKIP.exists() else set()
    if PENDING.exists():
        done |= {json.loads(l)["id"] for l in PENDING.read_text(encoding="utf-8").splitlines() if l.strip()}
    return done


def next_row() -> str | None:
    """The next open VX-L row, from a cached list (reading the 75 MB union per row cost minutes)."""
    if not OPEN.exists():
        from registry_io import load_doc
        OPEN.write_text(json.dumps([[t["id"], t["vx"]["cell"].get("mode")] for t in load_doc()["trajectories"]
                                    if (t.get("vx") or {}).get("family") == "VX-L" and t.get("status") == "specced"]),
                        encoding="utf-8")
    done = _queued()
    # --x-only: while the free model chain is rate-limited, walk only the rows whose model calls are stubbed
    x_only = "--x-only" in sys.argv
    for item in json.loads(OPEN.read_text(encoding="utf-8")):
        i, mode = (item if isinstance(item, list) else [item, None])
        if i in done:
            continue
        if x_only and mode in ("grounded-answer", "no-data"):
            continue
        return i
    return None


def flush() -> int:
    """Apply every queued bank in ONE load, ONE save and ONE manifest build."""
    if not PENDING.exists():
        print("nothing queued"); return 0
    ups = {}
    for l in PENDING.read_text(encoding="utf-8").splitlines():
        if l.strip():
            u = json.loads(l); ups[u["id"]] = u
    from registry_io import load_doc, save_doc
    reg = load_doc()
    hit = 0
    for t in reg["trajectories"]:
        u = ups.get(t["id"])
        if not u:
            continue
        locked = t.get("status") == "locked"
        st, pct = ("locked", 100) if locked else ("locking", 60)
        t["status"], t["pct"] = st, pct
        t["basis"] = f"[{u['today']}] pct -> {pct}. {u['basis_tail']}"
        arts = t.setdefault("artifacts", {})
        arts["gates"] = sorted(set(arts.get("gates") or []) | set(u["gates"]))
        hit += 1
    save_doc(reg)
    import live_walk_manifest as lm
    bm = lm.build(); rows = bm["rows"] if isinstance(bm, dict) else bm
    closed = sum(1 for x in rows if x["id"] in ups and lm.row_closed(x))
    PENDING.unlink()
    OPEN.unlink(missing_ok=True)
    print(f"flushed {hit} row(s); CLOSED {closed}/{len(ups)}")
    return 0 if closed == len(ups) else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank")
    ap.add_argument("--next", action="store_true")
    ap.add_argument("--x-only", action="store_true", help="skip G rows (live model) while the free chain is rate-limited")
    ap.add_argument("--flush", action="store_true", help="apply every queued bank in one registry write")
    ap.add_argument("--gates", action="store_true", help="run the G and X gates and record their PASS lines")
    a = ap.parse_args()
    if a.gates:
        out = {}
        for sub, ids in {"G": "grounding_contract,ai-render-provenance,ai_retrieval_isolation",
                         "X": "ai_prompt_injection,ai_retrieval_isolation,edge-fn-auth-gate,client_hive_is_proven"}.items():
            r = subprocess.run([sys.executable, "run_platform_checks.py", "--only", ids], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", cwd=str(ROOT))
            if "ALL PASS" in (r.stdout or ""):
                out[sub] = f"{ids.replace(',', ' PASS, ')} PASS (run_platform_checks --only, this session)"
        GATES_FILE.write_text(json.dumps(out), encoding="utf-8")
        print("gates passed:", ", ".join(out) or "none")
    rc = 0
    if a.flush:
        return flush()
    if a.bank:
        rc = bank(a.bank)
        if rc:
            with io.open(SKIP, "a", encoding="utf-8") as f:
                f.write(a.bank + "\n")
    if a.next:
        rid = next_row()
        if not rid:
            print("no open VX-L row")
            return rc
        r = subprocess.run([sys.executable, "tools/lm_walk_args.py", rid], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", cwd=str(ROOT))
        print("NEXT", ((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-1][:200])
        # ★EACH WALK STARTS WITH NO COMPANION MEMORY (2026-11-15). The companion keeps the last turns per person in
        # agent_memory; walk after walk asked the same cast about ZQX 9471, and it began answering "you're asking about
        # ZQX 9471 again" - a reading of the walk's own history, not of the page. The cast's local memory is cleared here.
        try:
            user = json.loads((ROOT / ".tmp" / "lm_args.json").read_text(encoding="utf-8")).get("user") or ""
            if user:
                n = psql(f"with d as (delete from agent_memory where auth_uid in (select id from auth.users where "
                         f"split_part(email,'@',1)='{user}') returning 1) select count(*) from d")
                print(f"cleared {n} companion memory row(s) for {user}")
        except Exception as e:  # the walk can still run; its receipt will show any carried memory
            print(f"memory not cleared: {e}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
