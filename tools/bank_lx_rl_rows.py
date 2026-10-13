#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bank the LAYER-UX RL rows (LXP-RL and LXC-RL) from a reading of EACH ROW'S OWN PAGE - and re-open the ones that
were closed on another page's reading.

THE LENS. "The platform must bound what this page can consume, and say so when it has." It routes to the postgres
instrument (live_walk_manifest MARKERS["postgres"] names tools/prove_consumption_bound.py): the bound and the telling
are read from the page's own source and markup, and "is the cap already passed?" is measured in the database - the
largest number of rows any one hive holds against the page's cap.

*WHY THIS BANKER EXISTS (2026-10-08). The 149 LXP-RL rows were banked on 2026-10-05 by hand, and 144 of their bases
read "MEASURED on index.html" while the row named achievements, alert-hub, audit-log ... The prover graded
`pages[0]`, and an LX row's `pages` is the ROUTE to its subject (index -> hive -> ... -> the page), so one page's bound
was answering for thirty others. The prover now reads `lx.page`. This banker writes each row's basis from ITS page's
verdict and, where the corrected reading does not answer the row, says so and returns the row to the open queue:
an open row asks to be walked, a falsely-closed one does not.

What counts as an answer: verdict `ok` (a bound and a word to the reader, an insurance cap measured far under its
ceiling, a single-row read, or no rows consumed at all), or `n/a` for a page nobody is shown (retired behind the
overlay) or that ships no data client. NOT an answer: `n/a` because the cap could not be resolved from source, or
because the bound lives in a shared script - both are the reader not seeing, not the page holding.

USAGE  python tools/prove_consumption_bound.py --json .tmp/consumption_bound.json
       python tools/bank_lx_rl_rows.py [--apply]
"""
import argparse
import io
import json
import os
import re
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(ROOT, "trajectory_registry.json")
READING = os.path.join(ROOT, ".tmp", "consumption_bound.json")
GATE_ID = "consumption-bound"            # as registered in run_platform_checks.py
ANSWERED_NA = ("retired behind the overlay", "ships no data client")
UNANSWERED_NA = ("no table+cap could be resolved", "belongs to a shared script", "could not be read from disk")


def measured_page(basis):
    """The page the row's NEWEST segment says it measured, if it says one."""
    m = re.search(r"(?:MEASURED on|on THIS row's own page,) ([\w./-]+?)[:,]", (basis or "").split(" || ")[0])
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(READING):
        print("REFUSED - no reading on disk; run: python tools/prove_consumption_bound.py --json " + READING)
        return 1
    reading = {r["id"]: r for r in json.load(open(READING, encoding="utf-8"))["results"]}
    read_at = os.path.getmtime(READING)

    reg = json.load(open(REGISTRY, encoding="utf-8"))
    rows = [t for t in reg["trajectories"]
            if (t.get("lx") or {}).get("kind") in ("layer-ux", "layer-floor")
            and (t.get("lx") or {}).get("layer") == "RL" and t.get("status") != "descoped"]
    today = date.today().isoformat()
    banked, reopened, open_noted, unchanged, missing = [], [], [], [], []
    for t in rows:
        lx = t["lx"]
        page, persona = lx.get("page"), lx.get("persona") or "any"
        r = reading.get(t["id"])
        if not r:
            missing.append((t["id"], page, "no verdict in the reading"))
            continue
        if r.get("page") != page:
            missing.append((t["id"], page, "the reading graded {0}, not this row's page".format(r.get("page"))))
            continue
        pf = os.path.join(ROOT, page)
        if os.path.exists(pf) and read_at < os.path.getmtime(pf):
            missing.append((t["id"], page, "the reading is older than the page - re-run the prover"))
            continue
        line, verdict = r.get("line") or "", r.get("verdict")
        answered = verdict == "ok" or (verdict == "n/a" and any(k in line for k in ANSWERED_NA))
        prev = t.get("basis") or ""
        was = measured_page(prev)
        wrong_page = bool(was) and was != page
        who = "a person" if persona == "any" else persona
        if answered:
            if was == page and "prove_consumption_bound.py" in prev.split(" || ")[0] and t.get("status") in ("locking", "locked"):
                unchanged.append(t["id"])
                continue
            basis = (
                "[{0}] pct -> 60. WALKED with the registered prover tools/prove_consumption_bound.py (gate `{1}`) - the "
                "postgres-instrument lens for this row, named in live_walk_manifest's MARKERS - on THIS row's own page, "
                "{2}: {3}. The RL ask has two halves and the second is the one that bites: a page may bound what it "
                "fetches and still lie quietly, because a cap printed as a total tells a supervisor their hive has 200 "
                "when it has 4,000 - so the prover requires a bound AND a word to the reader, or an insurance cap that "
                "the database (psql: the largest any one hive holds) shows far under its ceiling. AS {4}: the bound and "
                "the telling are read from the page's own source and markup, which every signed-in reader is served "
                "alike, and 'is the cap already passed' is measured against the LARGEST hive, the worst case any "
                "persona can meet.{5}"
            ).format(today, GATE_ID, page, line, who,
                     (" THIS CORRECTS THE EARLIER READING, which measured {0} - the first page of the row's ROUTE, "
                      "not its subject - because the prover read pages[0]; it now reads lx.page.".format(was)
                      if wrong_page else ""))
            t["basis"] = basis + (" || " + prev if prev else "")
            if t.get("status") in ("specced", "walked", "fixing", "walking"):
                t["status"] = "locking"
            t["pct"] = max(int(t.get("pct") or 0), 60)
            gates = t.setdefault("artifacts", {}).setdefault("gates", [])
            if GATE_ID not in gates:
                gates.append(GATE_ID)
            banked.append((t["id"], page, verdict))
            continue
        # not answered by this reading
        note = ("[{0}] pct -> 25. RE-MEASURED with tools/prove_consumption_bound.py on THIS row's own page, {1}: {2} - so the "
                "RL ask is NOT answered for {3} yet: a ceiling the reader cannot resolve, or one that lives in a shared "
                "script, is the instrument not seeing, not the page holding.").format(today, page, line, who)
        if t.get("status") in ("locking", "locked") and wrong_page:
            note += (" The earlier closure measured {0}, the first page of the row's ROUTE and not its subject, so it "
                     "cannot stand for this row: returned to the open queue (walked) until a reading of {1}'s own "
                     "consumption answers it.".format(was, page))
            # *TWO READERS, TWO CONVENTIONS: live_walk_manifest reads the FIRST segment as today's claim (bankers here
            # prepend), and validate_trajectory_registry rule 6 reads the LAST "pct -> N" in the string (it assumes
            # append). A pct that goes DOWN must satisfy both, so the note leads and a one-line pct stamp closes.
            t["basis"] = note + " || " + prev + " || [{0}] pct -> 25: re-opened - the first segment says why".format(today)
            t["status"], t["pct"] = "walked", 25
            reopened.append((t["id"], page, line[:80]))
        elif t.get("status") in ("specced", "walked"):
            if prev.split(" || ")[0].startswith("[{0}] pct -> 25. RE-MEASURED".format(today)):
                unchanged.append(t["id"])
                continue
            t["basis"] = note + (" || " + prev if prev else "")
            t["status"], t["pct"] = "walked", 25
            open_noted.append((t["id"], page, line[:80]))
        else:
            missing.append((t["id"], page, "status {0} with an unanswered reading - left for a human".format(t.get("status"))))

    print("LX RL rows: {0} -> banked {1} · re-opened {2} · open with the reason recorded {3} · unchanged {4} · "
          "not touched {5}".format(len(rows), len(banked), len(reopened), len(open_noted), len(unchanged), len(missing)))
    for i, p, v in banked[:5]:
        print("   bank   {0:8} {1:30} {2}".format(i, p, v))
    if banked[5:]:
        print("   ... and {0} more".format(len(banked) - 5))
    for i, p, why in reopened:
        print("   REOPEN {0:8} {1:30} {2}".format(i, p, why))
    for i, p, why in open_noted:
        print("   OPEN   {0:8} {1:30} {2}".format(i, p, why))
    for i, p, why in missing:
        print("   SKIP   {0:8} {1:30} {2}".format(i, p, why))
    if not a.apply:
        print("\n(dry run - pass --apply to write)")
        return 0
    tmp = REGISTRY + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(reg, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, REGISTRY)          # atomic: open(w) truncates before the write
    print("\nWROTE {0} row(s) to trajectory_registry.json".format(len(banked) + len(reopened) + len(open_noted)))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")
    sys.exit(main())
