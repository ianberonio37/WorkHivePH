#!/usr/bin/env python3
"""cascade-confirm parity — T139's blast-radius oracle (2026-08-26).

A delete confirm is a CLAIM about consequences, and the FK graph is the truth.
When a table has ON DELETE CASCADE children, deleting one row silently destroys
rows on other surfaces — an asset's Weibull fits, a project's change orders, a PM
plan's completion history. If the confirm does not say so, the person approves a
consequence they were never shown.

WHAT IT DOES
  1. Reads the LIVE FK graph (psql): every table with ON DELETE CASCADE children.
  2. Finds every client delete site: `.from('<table>')` … `.delete()` in the HTML.
  3. Looks back for the nearest whConfirm/confirm text guarding that site.
  4. FAILs a site whose table cascades and whose confirm names NO consequence —
     no child-count, no "removes/deletes/cannot be undone" clause, or no confirm
     at all.

It checks that a consequence is STATED, not that the wording is perfect: prose
grading produces false reds, while "cascades silently, says nothing" is objective
and is the class that hurts. Forward-only against
tools/cascade_confirm_baseline.json.

SKIPs when psql is unreachable — the FK graph is the oracle, and a gate without
its oracle must say SKIP, never PASS.

Usage: python tools/validate_cascade_confirm_parity.py
"""
import glob
import io
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "tools" / "cascade_confirm_baseline.json"

FROM_RE = re.compile(r"\.from\(\s*['\"]([a-z_][a-z0-9_]*)['\"]\s*\)")
DELETE_RE = re.compile(r"\.delete\s*\(")
# Take the 400 chars FOLLOWING whConfirm( and search that for consequence vocabulary.
# A negated-character-class capture broke on the platform's real confirms, which are backtick
# templates containing double quotes (`Delete "${name}"? ...`): the class stopped at the first
# quote, the capture never reached its minimum length, and SIX correctly-worded confirms read
# as "no confirm found". Do not parse the literal; read the neighbourhood.
CONFIRM_RE = re.compile(r"whConfirm\s*\((.{10,400})", re.S)
# A confirm that actually names a consequence.
#
# ★THE ACTION VERB USED TO COUNT AS A CONSEQUENCE, AND THAT MADE THIS GATE VACUOUS. The pattern
# included `removes?\b` and `deletes?\b`, so "Remove this asset from the registry?" - four words
# naming only the action - matched on "Remove" and passed. Nearly every destructive confirm is
# phrased that way, so the gate was reporting 0 while asking nothing. Demonstrated against the
# pre-fix wording: the old pattern found 0 silent delete sites on cascade parents, this one finds
# the logbook asset delete, whose row CASCADES seven children (asset_edges, asset_embeddings,
# pf_intervals, rcm_fmea_modes, sensor_readings, sensor_topic_map, weibull_fits) and detaches five
# more. A consequence is what happens BESIDES the thing you just asked for; the verb is the ask.
#
# `\d+\s+\w+` is kept: a confirm that counts what it will take ("12 PM tasks, 84 log entries") is
# naming the radius, which is the strongest form of this. Tightening cost nothing - no other site
# on any cascade parent relies on the verb alone.
CONSEQUENCE_RE = re.compile(
    r"(cannot be undone|will be (removed|deleted|lost)|goes with it|are deleted|"
    r"stop(s)? being linked|\d+\s+\w+|permanent|along with|including|cascade)", re.I)


def cascade_parents() -> set:
    out = subprocess.run(
        ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-c",
         "SELECT DISTINCT confrelid::regclass::text FROM pg_constraint "
         "WHERE contype='f' AND confdeltype='c';"],
        capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")
    return {l.strip() for l in (out.stdout or "").splitlines() if l.strip()}


def scan(parents: set):
    silent = []
    for f in sorted(glob.glob(str(ROOT / "*.html"))):
        lines = io.open(f, encoding="utf-8", errors="replace").read().splitlines()
        for i, line in enumerate(lines):
            if not DELETE_RE.search(line):
                continue
            # the table is on this line or within the 3 lines above (chained builders)
            window = "\n".join(lines[max(0, i - 3): i + 1])
            m = FROM_RE.search(window)
            if not m:
                continue
            table = m.group(1)
            if table not in parents:
                continue                      # nothing cascades: no blast radius to name
            back = "\n".join(lines[max(0, i - 40): i])
            confirms = CONFIRM_RE.findall(back)
            text = confirms[-1] if confirms else ""
            if not text or not CONSEQUENCE_RE.search(text):
                silent.append((Path(f).name, i + 1, table, (text or "<no confirm found>")[:60]))
    return silent


def main() -> int:
    if not shutil.which("docker"):
        print("SKIP cascade-confirm-parity — docker not available (the FK graph is the oracle)")
        return 0
    parents = cascade_parents()
    if not parents:
        print("SKIP cascade-confirm-parity — could not read the FK graph from psql")
        return 0
    silent = scan(parents)
    count = len(silent)
    print(f"  cascade parents: {len(parents)} · client delete sites on them with no stated consequence: {count}")
    for f, ln, tbl, txt in silent[:10]:
        print(f"    {f}:{ln}  delete on {tbl}  confirm: {txt}")

    if not BASELINE.exists():
        BASELINE.write_text(json.dumps({"count": count, "established": "2026-08-26"}, indent=1), encoding="utf-8")
        print(f"BASELINE established: {count} (forward-only)")
        return 0
    base = json.loads(BASELINE.read_text(encoding="utf-8")).get("count", 0)
    if count > base:
        print(f"FAIL cascade-confirm-parity — silent cascading deletes GREW {base} -> {count}.")
        return 1
    if count < base:
        BASELINE.write_text(json.dumps({"count": count, "ratcheted": "auto"}, indent=1), encoding="utf-8")
        print(f"PASS cascade-confirm-parity — improved {base} -> {count}; ratchet lowered.")
        return 0
    print(f"PASS cascade-confirm-parity — held at {count} (baseline {base}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
