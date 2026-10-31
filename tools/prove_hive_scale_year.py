#!/usr/bin/env python3
"""prove_hive_scale_year.py - Wave HS L4 "a year of the hive", held: every capped list read on the walked pages holds a
year of a thirty-member hive's work.

validate_list_caps_say_more.py sizes each capped read against the rows the database holds TODAY, so on a seeded hive it
passes reads a real plant outgrows in months. With a year laid (tools/hs_year_layer.py: 2,501 logbook entries, 301
machines, 601 parts, 2,241 PM completions, 4,501 trail entries, 300 synced work orders, 241 marketplace questions ...)
the same gate found 18 reads whose cap bit or sat past half, and the walk found every list that capped its search with
them (a register searched in its first 200, a trail searched in its newest 500, a queue counted by its length). This
harness lays the year, runs that gate against it, and removes the year again - so a new read that a year would cut is
refused before a hive grows into it.

  python tools/prove_hive_scale_year.py           # lay -> gate -> revert (leaves an already-laid year in place)

Mutates the thirty-member hive while it runs (seed-only, triggers off) - board-only, never beside a running walk.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / ".tmp" / "hs_year_layer_manifest.json"


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable] + args, cwd=ROOT, capture_output=True, text=True, timeout=1200)


def main() -> int:
    laid_here = not MANIFEST.exists() or not any(v for k, v in json.loads(MANIFEST.read_text(encoding="utf-8")).items()
                                                 if not k.startswith("_"))
    if laid_here:
        r = run(["tools/hs_year_layer.py", "--lay", "all"])
        print(r.stdout.strip())
        if r.returncode != 0 or "NOT laid" in r.stdout:
            print("FAIL hive-scale-year - the year could not be laid:\n" + (r.stderr or r.stdout)[-800:])
            run(["tools/hs_year_layer.py", "--revert"])
            return 1
    else:
        print("a year is already laid (.tmp/hs_year_layer_manifest.json) - gating against it and leaving it in place")
    try:
        g = run(["tools/validate_list_caps_say_more.py"])
        out = g.stdout.strip()
        print("\n".join(line for line in out.splitlines() if "FAIL" in line or "PASS" in line))
        verdict = g.returncode
    finally:
        if laid_here:
            rv = run(["tools/hs_year_layer.py", "--revert"])
            print(rv.stdout.strip().splitlines()[-1] if rv.stdout.strip() else rv.stderr.strip()[-300:])
    print(("PASS" if verdict == 0 else "FAIL") + " hive-scale-year - every capped list read holds a year of a thirty-member "
          "hive's work (paged, says more, or proven never to bite with the year laid)")
    return verdict


if __name__ == "__main__":
    sys.exit(main())
