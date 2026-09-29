#!/usr/bin/env python3
"""bank_mcp_navhub_walk.py - bank ONE nav-hub row from the walk just made through the Playwright MCP (2026-09-15).

The walk itself is `browser_run_code_unsafe { filename: 'tools/w4_navhub_walk.js' }` with its parameters in
`.tmp/w4_args.json`. It returns its verdict to the conversation and POSTs the full per-step ledger to the seeder,
which writes `.tmp/w4_steps/<id>.json`. This tool turns THAT file into the receipt the ledger reads
(tools/record_mcp_walk.py, instrument playwright-mcp, the axis and the hub-controls count from the walk) and banks
the row through bank_journey_walk.py under the axis gate. One row per call - the plan banks per page, serially.

★A RECEIPT IS WRITTEN ONLY FROM THE WALK IT NAMES. It refuses when the steps file carries another id, when the
walk reported problems, when fewer than 11 control groups were exercised, or when a step has no overlap record.
The verdict fields (problems, controls) are read from the steps file when the walker wrote them there; the
`--controls` / `--problems` flags exist only for a file written before the walker carried them (2026-09-15 08:00),
and the note records which source was used.

  python tools/bank_mcp_navhub_walk.py --id W41366 --axis "phone-390 en" --cast "Christine Dizon"
  python tools/bank_mcp_navhub_walk.py --id W41366 --axis "phone-390 en" --cast "Christine Dizon" --dry-run
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# ★A TOOL THAT SUCCEEDS AND THEN CRASHES PRINTING ABOUT IT IS REPORTED AS A FAILURE (2026-09-16).
# The basis sentences carry U+00B7 and the walk's output carries U+FFFD; on a cp1252 console the
# final print raised UnicodeEncodeError AFTER the row was already banked, so the caller
# (bank_navhub_axis.py, which classifies on returncode) recorded "banked 0 row(s); 30 FAILED" for
# 30 rows that had every one of them been banked. Set before the first print, including the refusals.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
GATES = {"phone-390 en": "w4-nav-hub", "narrow-320 en": "w4-nav-hub-320-en", "phone-390 fil": "w4-nav-hub-390-fil"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--axis", required=True, choices=sorted(GATES))
    ap.add_argument("--cast", required=True)
    ap.add_argument("--controls", type=int, default=-1, help="hub control groups exercised (only when the steps file lacks it)")
    ap.add_argument("--problems", default=None, help="JSON list of the walk's problems (only when the steps file lacks it)")
    ap.add_argument("--note", default="")
    ap.add_argument("--status", default="locking")
    ap.add_argument("--pct", default="60")
    # a CONFUSION row (kind confusion) is walked with the same nav-hub walker on its host page - 4 pages, fit on every
    # step - plus its predicate verified live through the MCP (carried in --note); it banks under the confusion gate
    ap.add_argument("--gate", default="", help="override the axis gate (e.g. w4-confusions for a confusion row)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    src = ROOT / ".tmp" / "w4_steps" / f"{a.id}.json"
    if not src.exists():
        print(f"REFUSED: no steps file at {src} - the MCP walk writes it via the seeder's POST /api/w4/steps")
        return 2
    d = json.loads(src.read_text(encoding="utf-8"))
    if isinstance(d, list):
        # the seeder wrote the bare step list under the id it was posted with (the file's name IS the id)
        d = {"id": a.id, "steps": d}
    if d.get("id") != a.id:
        print(f"REFUSED: {src} names {d.get('id')!r}, not {a.id}")
        return 2
    steps = d.get("steps") or []
    # the host step carries the hub's own ledger; its controls_exercised is the walk's count, not a typed one
    if "controls" not in d and steps and isinstance(steps[0].get("hub"), dict) and "controls_exercised" in steps[0]["hub"]:
        d["controls"] = steps[0]["hub"]["controls_exercised"]
    # since 2026-09-15 08:05 the walker puts its problems list on the host step (the seeder stores only `steps`)
    if "problems" not in d and steps and isinstance(steps[0].get("problems"), list):
        d["problems"] = steps[0]["problems"]
    if "problems" in d:
        problems, psrc = list(d.get("problems") or []), "steps file"
    elif a.problems is not None:
        problems, psrc = json.loads(a.problems), "the MCP reply, passed by hand"
    else:
        print("REFUSED: the steps file carries no problems list and none was passed - the verdict must come from the walk")
        return 2
    if "controls" in d:
        controls, csrc = int(d.get("controls") or 0), "steps file"
    elif a.controls >= 0:
        controls, csrc = a.controls, "the MCP reply, passed by hand"
    else:
        print("REFUSED: the steps file carries no controls count and none was passed")
        return 2
    if problems:
        print(f"REFUSED: the walk reported {len(problems)} problem(s); a nav-hub row is banked only from a clean walk:")
        for p in problems:
            print("   -", str(p)[:160])
        return 2
    if controls < 11:
        print(f"REFUSED: {controls} of 11 hub control groups exercised")
        return 2
    thin = [s.get("page") for s in steps if not isinstance(s.get("fit"), dict)]
    if thin or len(steps) < 4:
        print(f"REFUSED: {len(steps)} steps, without an overlap record on {thin}")
        return 2

    compact = []
    for s in steps:
        f = s.get("fit") or {}
        compact.append({"page": s.get("page"), "chars": s.get("chars"), "identityKept": s.get("identityKept", True),
                        "loadError": s.get("loadError") or None, "lang": s.get("lang"),
                        "fit": {"findings": f.get("findings") or 0, "occlusion": (f.get("occlusion") or [])[:4],
                                "overflowEl": (f.get("overflowEl") or [])[:2], "wrapped": (f.get("wrapped") or [])[:2]}})
    findings = sum(int(c["fit"]["findings"]) for c in compact)

    # ★THE ARRIVALS ARE THE ONE STATE THIS GATE'S CLAIM DOES NOT DEPEND ON (2026-09-16).
    # The walker writes TWO files: <id>.json holds the 4 page ARRIVALS (at rest, no panel open) and
    # <id>.records.json holds the ~24 INTERACTIONS - hub opened, companion opened, feedback opened,
    # filter typed, panel closed. Only the first was ever read, so a walk that reported
    # "#wh-fb-body covered by #wh-update-notice (fixed, z 2147483000)" banked as "0 overlap finding(s)".
    # A panel cannot occlude anything while it is still closed; the interactions are where the gate's
    # sentence - "no control occluded at any step" - is either true or false.
    rec_path = ROOT / ".tmp" / "w4_steps" / f"{a.id}.records.json"
    rec_findings, rec_steps, rec_src = 0, [], "no records file (walk predates the split)"
    if rec_path.exists():
        try:
            recs = json.loads(rec_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"REFUSED: {rec_path.name} is unreadable ({e}); an unread record is not a clean one")
            return 2
        rec_src = f"{len(recs)} interaction record(s)"
        for r in recs:
            n = int(r.get("findings") or 0)
            if n:
                rec_findings += n
                rec_steps.append((r.get("step"), (r.get("occlusion") or [""])[0][:120]))

    if rec_findings:
        print(f"REFUSED: the walk found {rec_findings} occlusion(s) in the INTERACTIVE states, which is "
              f"what this gate's own sentence - 'no control occluded at any step' - is about:")
        for step, occ in rec_steps[:6]:
            print(f"   - {step}: {occ}")
        print("   Fix the occlusion, or disposition it, then re-walk. Banking it green would make the "
              "board's claim false for every row that shares the chrome.")
        return 2
    out = ROOT / ".tmp" / "w4_steps" / f"{a.id}.steps.json"
    out.write_text(json.dumps(compact, ensure_ascii=False, indent=1), encoding="utf-8")
    note = (f"Walked through the Playwright MCP as {a.cast} at {a.axis}: the whole nav-hub on {compact[0]['page']} "
            f"({controls}/11 control groups, from the {csrc}; problems from the {psrc}), then "
            f"{' -> '.join(c['page'] for c in compact[1:])}; {findings} overlap finding(s) across "
            f"{len(compact)} page arrivals and 0 across {rec_src}. "
            + a.note).strip()
    rec = [sys.executable, "tools/record_mcp_walk.py", "--id", a.id, "--instrument", "playwright-mcp", "--cast", a.cast,
           "--axis", a.axis, "--hub-controls", str(controls), "--note", note, "--steps", str(out)]
    bank = [sys.executable, "tools/bank_journey_walk.py", str(ROOT / ".tmp" / "mcp_walks" / f"{a.id}.json"),
            "--status", a.status, "--pct", a.pct, "--gate", a.gate or GATES[a.axis]]
    print(f"{a.id} @ {a.axis}: {len(compact)} steps, controls {controls}, findings {findings}, problems 0")
    if a.dry_run:
        print("  would run:", " ".join(rec[:6]), "...\n  then:", " ".join(bank[1:]))
        return 0
    for cmd in (rec, bank):
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        tail = (r.stdout or "").strip().splitlines()[-2:] + (r.stderr or "").strip().splitlines()[-2:]
        print("  " + " | ".join(t.strip()[:160] for t in tail if t.strip()))
        if r.returncode != 0:
            print(f"  FAILED ({r.returncode}): {Path(cmd[1]).name}")
            return r.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
