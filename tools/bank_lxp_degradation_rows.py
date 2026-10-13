#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bank the LXP-A rows whose OWN page was proven to render a FAILURE rather than an emptiness.

THE LENS. "The platform must keep this page working when the service behind it answers slowly or not at all."
128 LXP-A rows carry it across 32 pages, and on this platform it is the lens that matters most: the people it
is built for work through brownouts and 2G, so the difference between "this failed, here is what to do" and a
blank panel is the difference between a usable tool and a lie.

THE INSTRUMENT is tools/prove_failure_injection.mjs, which fails the page's reads four ways (500 / 401 /
timeout / offline), injected via addInitScript so the patch lands BEFORE the supabase client is constructed -
a late `window.fetch` override never fires, and `page.route` alone is bypassed by a warm service worker. Its
oracle is a DIFFERENCE: the healthy control versus the injected read. That is why the sign-in matters so much
here, and why this banker refuses a report whose control was unavailable.

*WHAT THIS BANKER REFUSES, and each refusal is a lesson already paid for:
  · a report with ZERO graded cells. The report on disk when this was written had 154 cells, every one
    `ok: null`, verdict "healthy control unavailable (sign-in failed)". A sweep that measured nothing must
    never bank a row - that is the precise shape of a fabricated reading.
  · a cell that is UNGRADED for its page. A zero-hit page means the injection never reached a read, so
    "the page said nothing about the error" is what a page with NO error would also say.
  · a report OLDER than the page it describes. A stale green cannot testify.
  · a row whose page has no cell at all. The row closes on ITS page's reading, never on the sweep's average.

*** THIS TOOL NO LONGER BANKS, AND THE REASON IS IAN'S OWN RULE (corrected 2026-10-05, before first use). ***

I wrote it to advance the 128 LXP-A rows from prove_failure_injection's report, then went to check the
instrument contract and found the rule it would have broken. On 2026-09-15 Ian retracted EVERY row banked on
a Playwright-LIBRARY prover - "I thought we are using relevant live MCPs?" - and the retraction is enforced in
code at tools/bank_w4_passers.py:RETRACTED_INSTRUMENTS, whose own note records the cost of leaving it to
memory: a single banker call once moved 144 action rows to `locking` on retracted evidence "without the walk
having recorded anything."

The rule, stated there exactly: **a prover may WALK to find defects and produce receipts - it may not BANK a
row reserved for an MCP walk.** Every LXP-A row demands `playwright-mcp + postgres-mcp`, and
`prove_failure_injection.mjs` is a library script that appears in NO marker list in live_walk_manifest.py. So
banking from it would have inflated the registry's `locking` count with evidence the ledger itself rejects -
the rows would have sat in the re-walk queue anyway, now wearing a basis that claimed otherwise. That is worse
than leaving them open, because an open row asks to be walked and a falsely-banked one does not.

What this tool does instead: it READS the sweep and reports what the degradation lens found, which is the half
a library prover is for. The findings are real and worth fixing; the closing of the rows needs the MCP walk.

USAGE  python tools/bank_lxp_degradation_rows.py        # report the sweep's findings (never writes)
"""
import argparse
import io
import json
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(ROOT, "failure_injection_report.json")
REGISTRY = os.path.join(ROOT, "trajectory_registry.json")
MANIFEST = os.path.join(ROOT, "live_walk_manifest.json")
LENS = "The platform must keep this page working when the service"
GATE_ID = "cc_failure_injection"       # as registered in run_platform_checks.py


def main():
    ap = argparse.ArgumentParser()
    # --apply is kept ONLY so an old invocation fails loudly instead of looking like it worked.
    ap.add_argument("--apply", action="store_true",
                    help="REFUSED: a library prover may not bank an MCP-reserved row (see this file's header)")
    a = ap.parse_args()
    if a.apply:
        print("REFUSED --apply: every LXP-A row demands `playwright-mcp + postgres-mcp`, and "
              "prove_failure_injection.mjs is a library prover named in no marker list. Ian retracted every row "
              "banked this way on 2026-09-15 ('I thought we are using relevant live MCPs?'), and the same hole "
              "once advanced 144 action rows on evidence the ledger rejects. This tool reports findings; the "
              "rows close on an MCP walk.")
        return 1

    if not os.path.exists(REPORT):
        print("REFUSED - no failure_injection_report.json; run: node tools/prove_failure_injection.mjs")
        return 1
    rep = json.load(open(REPORT, encoding="utf-8"))
    cells = rep.get("cells") or []
    totals = rep.get("totals") or {}
    graded = [c for c in cells if c.get("ok") is not None]
    if not graded:
        print("REFUSED - the report has {0} cell(s) and NONE graded ({1}). A sweep that measured nothing "
              "cannot bank a row; the usual cause is a failed sign-in, which makes every auth-gated page "
              "look silent. Re-run the prover and check it signs in."
              .format(len(cells), (cells[0].get("verdict") if cells else "no cells")[:90]))
        return 1
    failing = [c for c in graded if c.get("ok") is False]
    print("  report: {0} cell(s) · {1} graded · {2} failing".format(len(cells), len(graded), len(failing)))

    # per page: every graded cell, and whether any of them failed
    by_page = {}
    for c in graded:
        by_page.setdefault(str(c.get("page")), []).append(c)

    reg = json.load(open(REGISTRY, encoding="utf-8"))
    byid = {t["id"]: t for t in reg["trajectories"]}
    man = json.load(open(MANIFEST, encoding="utf-8"))
    targets = [r for r in man["rows"]
               if r.get("needs_mcp_rewalk") and r["lens"].startswith(LENS)]

    rep_mtime = os.path.getmtime(REPORT)
    banked, skipped, fresh = [], [], []
    for t in targets:
        row = byid[t["id"]]
        page = (row.get("lx") or {}).get("page") or t["surface"]
        stem = page[:-5] if page.endswith(".html") else page
        mine = by_page.get(stem)
        if not mine:
            skipped.append((t["id"], page, "no graded cell for this page - not in the prover's roster, or "
                                           "every mode was ungraded (a zero-hit page is not a reading)"))
            continue
        bad = [c for c in mine if c.get("ok") is False]
        if bad:
            skipped.append((t["id"], page, "{0} of {1} mode(s) FAILED: {2}".format(
                len(bad), len(mine), (bad[0].get("verdict") or "")[:90])))
            continue
        pf = os.path.join(ROOT, page)
        if os.path.exists(pf) and rep_mtime < os.path.getmtime(pf):
            skipped.append((t["id"], page, "the report is older than the page - re-run the prover"))
            continue

        modes = ", ".join(sorted(str(c.get("mode")) for c in mine))
        basis = (
            "[{0}] pct -> 60. WALKED with the registered prover tools/prove_failure_injection.mjs (gate `{1}`): "
            "the page's own reads were FAILED four ways and it had to say so. MEASURED ON {2}: {3} mode(s) "
            "graded clean ({4}) - in each one the surface rendered a FAILURE a person can act on, not an "
            "emptiness and not a silent shrink. THE ORACLE IS A DIFFERENCE, not a keyword: each injected read "
            "is compared against a HEALTHY control load of the same page, so a surface that always looks empty "
            "cannot pass by looking empty again, and a page whose healthy load showed no rows is reported "
            "UNGRADED rather than judged. The injection lands via addInitScript, BEFORE the supabase client is "
            "constructed - a late window.fetch override never fires because the client captured fetch at "
            "construction, and page.route alone is bypassed by a warm service worker, so a probe that does "
            "neither measures nothing while reporting success. Calls are HIT-COUNTED, so a page the injection "
            "never reached is ungraded instead of credited. PLATFORM-WIDE IN THE SAME RUN: {5} of {6} cell(s) "
            "graded, {7} failing. This matters most on this platform specifically: its people work through "
            "brownouts and 2G, so a failed read that renders as a blank panel is not a cosmetic defect - it "
            "tells a technician there is nothing there when there is."
        ).format(date.today().isoformat(), GATE_ID, page, len(mine), modes,
                 totals.get("graded", len(graded)), totals.get("cells", len(cells)),
                 totals.get("failing", len(failing)))

        prev = row.get("basis") or ""
        if "prove_failure_injection.mjs" not in prev:
            row["basis"] = (basis + " || " + prev) if prev else basis
            fresh.append(t["id"])
        if row.get("status") in ("specced", "fixing"):
            row["status"] = "locking"
        row["pct"] = max(int(row.get("pct") or 0), 60)
        art = row.setdefault("artifacts", {})
        gates = art.setdefault("gates", [])
        if GATE_ID not in gates:
            gates.append(GATE_ID)
        banked.append((t["id"], page, len(mine)))

    print("  LXP-A degradation rows: {0}  ->  bankable {1} ({2} newly written) - left open {3}"
          .format(len(targets), len(banked), len(fresh), len(skipped)))
    for i, p, n in banked[:6]:
        print("     bank {0:8} {1:28} {2} graded mode(s)".format(i, p, n))
    if banked[6:]:
        print("     ... and {0} more".format(len(banked) - 6))
    seen = set()
    for i, p, why in skipped:
        if p in seen:
            continue
        seen.add(p)
        print("     OPEN {0:8} {1:28} {2}".format(i, p, why))
    if not a.apply:
        print("\n(dry run - pass --apply to write)")
        return 0
    tmp = REGISTRY + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(reg, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, REGISTRY)          # atomic: open(w) truncates before the write
    print("\nWROTE {0} row(s) to trajectory_registry.json".format(len(banked)))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")
    sys.exit(main())
