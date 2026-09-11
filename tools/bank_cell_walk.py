#!/usr/bin/env python3
"""bank_cell_walk.py - bank a lifecycle-cell walk (W3-LC/AR/PG/DF) or a shared-component walk (W3-SC).

Two provers, two ways of naming what they measured, one set of rules about what may be written down:

  tools/prove_lifecycle_cells.mjs  walks a seeded ROW and returns that row's own id, so a verdict names its
                                   trajectory directly.
  tools/prove_shared_components.mjs walks a shared FILE on three hosts and returns four lens verdicts against
                                   the file name, so a verdict is matched to the row whose title ends in it.

★FOUR VERDICTS, FOUR FATES - and the two that are not pass-or-fail are the ones that keep the record honest:

  ok   -> banked.
  BAD  -> HELD. The row keeps its finding and stays open. Its siblings still bank: a component that is named
          identically everywhere but overflows a phone has one true claim and one false one.
  n/a  -> NOT banked and NOT failed, and the reason is recorded. A piece that persists nothing owes no
          storage-ownership answer; a cell whose page bounced to the sign-in door was never reached. Grading
          the door and calling it the page is how twenty-four pages once shared one verdict.
  skeleton/unreadable -> NOT banked. A page still rendering is not a page that failed; it is a page nobody
          has read yet, and it is re-walked on a quiet host rather than written down.

  python tools/bank_cell_walk.py .tmp/lifecycle_cells.json --dry-run
  python tools/bank_cell_walk.py .tmp/shared_components.json --gate shared-components --pct 60
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "trajectory_registry.json"


def sc_index() -> dict:
    """(file name, dimension) -> row id, for the shared-component wave.

    The seeded title ends in the file it is about ('... - asset-qr.js'), which is how a row is recognised
    without re-typing sentences that are allowed to be re-worded.
    """
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    out = {}
    for t in reg["trajectories"]:
        # W3-SC2 is the same wave in every way that matters here - it exists only because the seeder's
        # roster capped at 14 while the prover walks 19, and because the validator's ids are positional,
        # so twenty more rows inside the SC block would renumber everything after it
        if t.get("wave") not in ("W3-SC", "W3-SC2"):
            continue
        title = (t.get("title") or "").strip()
        dim = (t.get("ufai") or [None])[0]
        if " - " not in title or not dim:
            continue
        js = title.rsplit(" - ", 1)[1].strip()
        if js.endswith(".js"):
            out[(js, dim)] = t["id"]
    return out


BATCH = []


def advance(rid, status, pct, gate, basis, dry):
    """Collect the entry; the whole wave is written in ONE pass by flush() below.

    ★ONE PASS, NOT ONE PER ROW. advance_trajectory.py re-runs the scoreboard generator AND the whole registry
    validator on every call - measured at 30 SECONDS per banked row against a 7.7 MB registry, so a 176-row
    wave regenerated the roadmap 176 times to answer one question each, about four hours for a night's rows.
    """
    if dry:
        return True
    BATCH.append({"id": rid, "status": status, "pct": pct, "gate": [gate], "basis": basis})
    return True


def flush(name: str) -> int:
    if not BATCH:
        return 0
    Path(".tmp").mkdir(exist_ok=True)
    bf = Path(f".tmp/bank_{name}_batch.json")
    bf.write_text(json.dumps(BATCH, ensure_ascii=False, indent=1), encoding="utf-8")
    p = subprocess.run([sys.executable, str(ROOT / "tools" / "advance_trajectory.py"), "--batch", str(bf)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print((p.stdout or p.stderr).strip()[-400:])
    if p.returncode:
        print("    the batch was REFUSED, so nothing was written - fix the entries and re-run")
        return 0
    return len(BATCH)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--status", default="locking")
    ap.add_argument("--pct", default="60")
    ap.add_argument("--gate", default="lifecycle-cells")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    doc = json.loads(Path(a.results).read_text(encoding="utf-8"))
    prover = "prove_shared_components.mjs" if any("js" in r for r in doc.get("results", [])) else "prove_lifecycle_cells.mjs"
    idx = sc_index()
    banked = held = na = unmatched = 0
    stamp = date.today().isoformat()

    def settle(rid, subject, lens, verdict, line):
        nonlocal banked, held, na
        line = (line or "").strip()
        if verdict == "ok":
            basis = f"pct -> {a.pct}. WALKED LIVE {stamp} via tools/{prover} - {lens} on {subject}: {line}"
            if advance(rid, a.status, a.pct, a.gate, basis, a.dry_run):
                banked += 1
                if a.dry_run:
                    print(f"    bank {rid:<8} {lens} {subject[:26]:28} {line[:66]}")
        elif verdict == "n/a":
            na += 1
            print(f"    open {rid:<8} {lens} {subject[:26]:28} not this lens's to answer: {line[:56]}")
        else:
            held += 1
            print(f"    hold {rid:<8} {lens} {subject[:26]:28} {line[:66]}")

    for r in doc.get("results", []):
        if r.get("js"):                      # shared component: four lenses against one file
            for lens in ("U", "F", "A", "I"):
                v = r.get(lens)
                if not v:
                    continue
                rid = idx.get((r["js"], lens))
                if not rid:
                    unmatched += 1
                    print(f"    no row  {r['js'][:30]:32} {lens}")
                    continue
                settle(rid, r["js"], lens, v.get("verdict"), v.get("line"))
        elif r.get("id"):                    # lifecycle cell: the row named itself
            settle(r["id"], (r.get("page") or "")[:26] or r["id"], (r.get("wave") or "").replace("W3-", ""),
                   r.get("verdict"), r.get("line"))
        else:
            unmatched += 1

    if not a.dry_run:
        written = flush("sc" if prover.endswith("shared_components.mjs") else "cells")
        if written != banked:
            print(f"    NOTE: {banked} were bankable but {written} were written")
            banked = written
    print(f"\n  {banked} bankable · {held} held (each keeps its finding) · {na} left open "
          f"(no lens could answer them) · {unmatched} verdict(s) matched no seeded row")
    return 0


if __name__ == "__main__":
    sys.exit(main())
