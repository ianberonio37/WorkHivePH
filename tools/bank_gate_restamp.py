#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Re-stamp STALE gate-backed rows after their gate has re-proven green against the CURRENT files.

WHY. A gate-kind row goes stale on R4 (a depends_on file changed since the stamp) even though the
claim is carried by the GATE, not by that one afternoon's file state — "a gate-backed row is
re-earned by RUNNING the gate" (bank_marketplace_gate.py). Measured 2026-08-21: 1,263 stale rows
were gate-kind; read_idempotency had already re-run green that morning and its 81 rows stayed stale
because nothing re-anchored their sha. This tool is that re-anchor, and nothing more.

WHAT IT REFUSES (the honesty rails):
  · a row whose staleness is R7 (mis-declared deps) — those need re-anchoring to the right
    artifacts, not a fresh stamp on the wrong ones;
  · a gate whose report file is OLDER than the newest dep mtime of the row — a stale report cannot
    testify about the current files;
  · a re-stamped row the gate's own classify() would not call green — same rail as every banker.

USAGE  python tools/bank_gate_restamp.py --gate <gate-id> --report <report.json> [--apply]
       (run the gate green FIRST; this tool checks recency, not verdicts — pair it with the run.)
"""
import argparse
import glob
import importlib.util
import io
import json
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GREEN, RED, YEL, DIM, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


def _gate():
    spec = importlib.util.spec_from_file_location(
        "_vlmb", os.path.join(ROOT, "tools", "validate_live_mcp_bank.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", required=True, help="gate id as evidence refs name it (after 'gate:'), "
                    "or with --kind psql: a substring the psql ref must contain (the harness path)")
    ap.add_argument("--report", required=True, help="the gate's report file — must be newer than the deps")
    ap.add_argument("--kind", default="gate", choices=["gate", "psql"],
                    help="psql: re-stamp psql-kind rows whose ref NAMES this harness, after the "
                         "harness re-ran green and wrote a fresh artifact (added 2026-08-21 for "
                         "verify_money_lifecycle rows)")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)

    V = _gate()
    report_path = os.path.join(ROOT, a.report)
    if not os.path.exists(report_path):
        print(f"{RED}REFUSING{RST} — report {a.report} does not exist; run the gate first")
        return 1
    report_mtime = os.path.getmtime(report_path)

    banks = sorted(glob.glob(os.path.join(ROOT, "banks", "*_live_mcp_bank.json")))
    banks.append(os.path.join(ROOT, "live_mcp_registry.json"))
    total_restamped = total_refused = 0
    for bank_path in banks:
        try:
            reg = json.load(open(bank_path, encoding="utf-8"))
        except Exception:
            continue
        rows = reg.get("scenarios") if isinstance(reg, dict) else reg
        if not rows:
            continue
        gates, urls = V.gate_ids(), V.surface_urls(reg)
        restamped = refused = 0
        for row in rows:
            ev = row.get("evidence")
            if not isinstance(ev, dict) or ev.get("kind") != a.kind:
                continue
            if a.kind == "gate":
                gid = str(ev.get("ref") or "").split("gate:")[-1].strip()
                if gid != a.gate:
                    continue
            else:
                if a.gate not in str(ev.get("ref") or ""):
                    continue
            state, why = V.classify(row, gates, urls)
            if state != "stale":
                continue
            if why.startswith("R7"):
                refused += 1        # mis-declared deps: a fresh stamp on the wrong anchor is the bug
                continue
            deps = ev.get("depends_on") or []
            newest_dep = max((os.path.getmtime(os.path.join(ROOT, d))
                              for d in deps if os.path.exists(os.path.join(ROOT, d))), default=0)
            if report_mtime < newest_dep:
                refused += 1        # the gate has not seen the current file — its word is stale too
                continue
            before = (ev.get("sha"), ev.get("fn_digests"), ev.get("restamped_at"))
            ev["sha"] = V.sha_of(deps)
            ev["fn_digests"] = V.fn_digests(deps)
            ev["restamped_at"] = (f"{date.today().isoformat()} — {'gate' if a.kind == 'gate' else 'harness'} "
                                  f"{a.gate} re-ran green against the current state ({a.report}); "
                                  f"sha re-anchored, claim unchanged")
            st2, why2 = V.classify(row, gates, urls)
            if st2 != "green":
                ev["sha"], ev["fn_digests"], _ = before
                if before[2] is None:
                    ev.pop("restamped_at", None)
                refused += 1
                continue
            restamped += 1
        if restamped and a.apply:
            json.dump(reg, open(bank_path, "w", encoding="utf-8"), indent=1)
        if restamped or refused:
            print(f"  {os.path.basename(bank_path):44s} {GREEN}{restamped} re-stamped{RST} · "
                  f"{YEL}{refused} refused{RST}")
        total_restamped += restamped
        total_refused += refused

    print(f"\n  {GREEN}{total_restamped} row(s) re-stamped{RST} · {YEL}{total_refused} refused{RST}"
          + ("" if a.apply else f"   {YEL}dry run — pass --apply to write{RST}"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
