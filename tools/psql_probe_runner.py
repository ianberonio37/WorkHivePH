#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run a psql probe file and judge it by its OWN declared expectations — the replay half of A16.C1.

The ~70 psql-kind bank rows were hand-walked once and left no recipe: their evidence narrates the
probe ("duplicate insert raised 23505, control accepted, re-counted after rollback") but nothing can
re-execute it, so every shared-file or migration edit turns each into a hand-reconstruction. This
runner + tools/psql_probes/*.sql makes each probe an executable RECIPE:

  probe file  = plain psql, BEGIN/ROLLBACK where it mutates, with header lines declaring the oracle:
      -- expect: <python regex the combined stdout+stderr MUST match>     (repeatable, ALL must hit)
      -- forbid: <regex that must NOT match>                              (optional, repeatable)
  A probe with no `-- expect:` is refused — output nobody asserts on is not evidence
  (the zero-failures-over-zero-measurements rail).

  runner      = executes the file via docker exec psql, checks every expectation, prints PASS/FAIL
  with the matched lines, and (with --results) APPENDS a bank_page_walk-shaped row to a results
  JSON, carrying kind=psql and replay=<this exact command>, so the row re-earns by running its own
  recipe from now on.

USAGE  python tools/psql_probe_runner.py tools/psql_probes/<page>__<oracle>.sql \
           [--id <bank-row-id>] [--results .tmp/page_walk_results.json]
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GREEN, RED, YEL, DIM, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

PSQL = ["docker", "exec", "-i", "supabase_db_workhive",
        "psql", "-U", "postgres", "-d", "postgres", "-v", "ON_ERROR_STOP=0"]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("probe")
    ap.add_argument("--id", help="bank row id this probe settles (required with --results)")
    ap.add_argument("--results", help="append a bank_page_walk-shaped row to this JSON")
    a = ap.parse_args(argv)

    path = os.path.join(ROOT, a.probe) if not os.path.isabs(a.probe) else a.probe
    src = open(path, encoding="utf-8").read()
    expects = re.findall(r"^--\s*expect:\s*(.+)$", src, re.M)
    forbids = re.findall(r"^--\s*forbid:\s*(.+)$", src, re.M)
    if not expects:
        print(f"{RED}REFUSED{RST} — {a.probe} declares no '-- expect:' line; output nobody asserts "
              "on is not evidence")
        return 1

    # encoding pinned: text=True alone encodes stdin with the LOCALE codepage (cp1252 on this
    # machine), and psql in the container reads UTF-8 — a probe containing any non-ASCII character
    # (an em dash in a comment) had that one STATEMENT die on 'invalid byte sequence' while the rest
    # ran, which surfaced as a single MISSING expectation with no error in sight (2026-08-21).
    proc = subprocess.run(PSQL, input=src, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120)
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")

    hits, misses = [], []
    for pat in expects:
        m = re.search(pat, out)
        (hits if m else misses).append((pat, m.group(0)[:120] if m else None))
    hit_forbid = [(p, re.search(p, out).group(0)[:120]) for p in forbids if re.search(p, out)]

    ok = not misses and not hit_forbid
    tag = f"{GREEN}PASS{RST}" if ok else f"{RED}FAIL{RST}"
    print(f"  {tag}  {os.path.basename(a.probe)}")
    for pat, got in hits:
        print(f"    {DIM}expect{RST} {pat}  ->  {got}")
    for pat, _ in misses:
        print(f"    {RED}MISSING{RST} {pat}")
    for pat, got in hit_forbid:
        print(f"    {RED}FORBIDDEN matched{RST} {pat}  ->  {got}")

    if a.results:
        if not a.id:
            print(f"{RED}--results needs --id{RST}")
            return 1
        rel = os.path.relpath(path, ROOT).replace("\\", "/")
        row = {
            "id": a.id,
            "ok": ok,
            "kind": "psql",
            "checked": ("probe re-executed from its recipe file; every declared expectation matched: "
                        + "; ".join(p for p, _ in hits))[:900] if ok else
                       ("probe FAILED its own expectations: " + "; ".join(p for p, _ in misses)),
            "value_checked": " | ".join(f"{got}" for _, got in hits if got)[:600],
            "replay": f"python tools/psql_probe_runner.py {rel} --id {a.id}",
        }
        rp = os.path.join(ROOT, a.results) if not os.path.isabs(a.results) else a.results
        try:
            arr = json.load(open(rp, encoding="utf-8"))
        except Exception:
            arr = []
        arr = [r for r in arr if r.get("id") != a.id] + [row]
        os.makedirs(os.path.dirname(rp), exist_ok=True)
        json.dump(arr, open(rp, "w", encoding="utf-8"), indent=1)
        print(f"  {DIM}appended to {a.results} ({len(arr)} row(s)){RST}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
