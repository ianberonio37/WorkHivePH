""" -*- coding: utf-8 -*-
Surface what the RECORDER provers found, because nothing else does (T129, 2026-08-28).

Six live provers on this platform are recorders, not gates: they walk real surfaces, reach real
verdicts, write a report — and exit 0 whatever they find. That is the correct shape for what they
measure (a lens that reports five availability conditions per page has no single pass/fail to
give), but it left a REPORTING gap that looked exactly like a coverage gap:

    prove_session_expiry            session_expiry_report.json
    prove_session_expiry_registry   session_expiry_walk_report.json
    prove_availability_pages        availability_pages_report.json
    prove_market_attribution        market_attribution_report.json
    prove_component_states_scoped   component_states_scoped_report.json
    prove_view_inputs               view_inputs_report.json

★THE DISTINCTION THIS TOOL EXISTS TO PRESERVE. The board must not register a recorder as a gate:
its exit code is 0 on findings (their only process.exit(1) sits in run().catch(), so they signal a
CRASH, never a result), and a gate that cannot go red is a permanent false green — worse than no
gate, because it occupies the slot where a real check would have been noticed missing. So the
answer is not to gate them. It is to READ them.

★AND IT READS THE ARTIFACTS RATHER THAN RE-RUNNING. Re-running the six costs about fifteen minutes
(session_expiry alone is 475s), which is why nobody did it twice and why their reports went stale
in place. Reading is instant, so this can run every time anyone looks.

It reports STALENESS as loudly as findings: a report older than the code it describes is a claim
about a platform that no longer exists, and a recorder nobody re-runs decays into exactly that.

USAGE:  python tools/read_recorder_findings.py [--max-age-days N]
Exit code is always 0 — this is a READER. It refuses to become the gate it is reporting on.
"""
from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RECORDERS = [
    ("session_expiry_report.json",          "prove_session_expiry",          "the session dies BETWEEN typing and submitting"),
    ("session_expiry_walk_report.json",     "prove_session_expiry_registry", "the session-expiry target registry"),
    ("availability_pages_report.json",      "prove_availability_pages",      "five availability conditions across the product roster"),
    ("market_attribution_report.json",      "prove_market_attribution",      "marketplace attribution holds"),
    ("component_states_scoped_report.json", "prove_component_states_scoped", "component states, page-scoped"),
    ("view_inputs_report.json",             "prove_view_inputs",             "view inputs"),
    ("jargon_glossed_report.json",          "prove_jargon_is_glossed",       "domain acronyms a worker meets are explained"),
]

# keys a report might use for its verdict rows, in the order we try them
ROW_KEYS = ("targets", "results", "pages", "rows", "probes", "findings")


def _summarise(doc) -> tuple:
    """(total, failing, note) or (None, None, reason) when the shape is not understood.

    ★A READER THAT CANNOT PARSE MUST SAY SO, NOT PRINT ZERO. The first cut returned (0, 0,
    "unrecognised shape") for four of the six reports and rendered them as "ok - 0 flagged": this
    tool reproduced, on its first run, the exact false-green it was written to prevent. Two shapes
    were missing - `checks` as a list beside explicit pass/fail integers, and `pages` as a DICT
    rather than a list - and a third bug hid them: the fail-count branch only fired when fail was
    TRUTHY, so a clean `fail: 0` fell through to the unrecognised path and then reported zero for
    the wrong reason. A zero that means "nothing wrong" and a zero that means "I could not look"
    must never render the same.
    """
    if not isinstance(doc, (dict, list)):
        return (None, None, "not an object or array")
    if isinstance(doc, list):
        return (len(doc), 0, "list")

    # explicit tallies win when present - note the `is not None` test, not truthiness
    if isinstance(doc.get("fail"), int) and isinstance(doc.get("pass"), int):
        checks = doc.get("checks")
        total = len(checks) if isinstance(checks, list) else doc["pass"] + doc["fail"]
        return (total, doc["fail"], "pass/fail tally")
    for k in ("dead", "owed", "failing"):
        if isinstance(doc.get(k), int):
            return (doc.get("probes") or doc.get("total") or 0, doc[k], k)

    for k in ROW_KEYS:
        rows = doc.get(k)
        if isinstance(rows, list):
            bad = 0
            for r in rows:
                if not isinstance(r, dict):
                    continue
                v = str(r.get("verdict") or r.get("status") or r.get("shape") or "")
                # ★A ROW CAN CARRY ITS FINDINGS IN A LIST RATHER THAN A VERDICT. The jargon recorder
                # reports {page, present:[...], bare:[KPI]} - no status field at all - and this
                # summariser scored it 0-flagged on its first read, under-reporting a real finding
                # inside the very tool built to stop recorders going unread. A recorder's shape is
                # whatever its author chose; the reader has to learn each one, and "no verdict
                # field" must never silently mean "nothing found".
                listed = any(isinstance(r.get(f), list) and r.get(f)
                             for f in ("bare", "findings", "issues", "dead", "problems"))
                if r.get("ok") is False or listed or v.upper() in ("FAIL", "DEAD", "RED", "BROKEN"):
                    bad += 1
            return (len(rows), bad, k)
        if isinstance(rows, dict):                      # e.g. pages keyed by page name
            bad = 0
            for r in rows.values():
                if isinstance(r, dict) and (r.get("ok") is False
                                            or str(r.get("verdict") or "").upper() in ("FAIL", "DEAD", "RED")):
                    bad += 1
            return (len(rows), bad, k + " (dict)")
    return (None, None, "no recognised rows or tally")


def main() -> int:
    max_age = 14
    if "--max-age-days" in sys.argv:
        try:
            max_age = int(sys.argv[sys.argv.index("--max-age-days") + 1])
        except Exception:  # noqa: BLE001
            pass

    print("recorder findings - six provers that measure honestly and gate nothing")
    print(f"  (reading artifacts, not re-running: the six cost ~15 min together)\n")
    missing, stale, flagged, unparsed = 0, 0, 0, 0
    for fname, prover, what in RECORDERS:
        p = ROOT / fname
        if not p.exists():
            missing += 1
            print(f"  NEVER RUN  {fname:<38} {prover}")
            print(f"             {what} - no report on disk, so this lens has produced nothing to read")
            continue
        age_days = (time.time() - p.stat().st_mtime) / 86400.0
        try:
            doc = json.load(io.open(p, encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"  UNREADABLE {fname:<38} {e}")
            continue
        total, bad, note = _summarise(doc)
        if total is None:
            unparsed += 1
            print(f"  UNPARSED   {fname:<38} {age_days:.1f}d old  [{note}]")
            print(f"             this reader cannot judge that shape, which is NOT the same as finding "
                  f"nothing - teach _summarise the shape rather than reading this as clean")
            continue
        mark = "FINDINGS " if bad else ("STALE     " if age_days > max_age else "ok        ")
        if bad:
            flagged += 1
        elif age_days > max_age:
            stale += 1
        print(f"  {mark} {fname:<38} {total} rows, {bad} flagged, {age_days:.1f}d old  [{note}]")
        if age_days > max_age:
            print(f"             a report older than the code it describes is a claim about a platform "
                  f"that no longer exists - re-run {prover}")
    print("")
    print(f"  {len(RECORDERS)} recorders | {flagged} with findings | {stale} stale (>{max_age}d) | {missing} never run | {unparsed} unparsed")
    print("  exit 0 by design: this is a READER, not the gate it reports on.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
