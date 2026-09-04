#!/usr/bin/env python3
"""automation-log-status — T112: no writer may invent a status the schema forbids (2026-08-26).

THE BUG CLASS THIS CLOSES. automation_log carries a CHECK constraint on status.
Two edge functions wrote values that were not in it:

  resend-webhook-receiver  status: "failure"   (the word is "failed")
  send-report-email        status: "deferred"  (the breaker's own audit row)

Both inserts would be refused with 23514 — and NEITHER read the insert error
(`await db.from("automation_log").insert({...})`, no destructuring), so
supabase-js returned the error into the void and both functions carried on
reporting success. The bounce receiver would have answered Resend 200
"recorded" while storing nothing, leaving the sender-side bounce surface
permanently empty with every layer above it looking healthy; the circuit
breaker's trip would never appear in the log an operator reads precisely when
the breaker trips.

Neither had fired: the receiver fails closed without its signing secret, and the
breaker path needs Resend to be failing. They would have fired at the worst
possible moment — the first real bounce after the secret was set, and the first
email outage — which is exactly why a static gate is worth more here than a
smoke test that only exercises the happy path.

TWO ASSERTIONS:

  1. Every status literal written to automation_log is in the constraint's
     allowed set. The set is read from the MIGRATION (the declared truth) and,
     when docker is present, cross-checked against the LIVE constraint — because
     a repo that says one thing while the database enforces another is its own
     defect, and a gate anchored to only one of them cannot see it.
  2. The count of UNCHECKED automation_log inserts does not grow (forward-only
     ratchet). Not zero: 12 of 14 are unchecked today, and rewriting all of them
     in one pass to move a number would be a large unreviewed change to audit
     paths for no measured defect. What must not happen is a NEW one — because
     an unchecked insert is what turned both bugs above from a loud 23514 into
     silence.

Usage: python tools/validate_automation_log_status.py
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
BASELINE = ROOT / "tools" / "automation_log_unchecked_baseline.json"


def allowed_from_migrations():
    """The declared truth: the newest migration that defines the CHECK."""
    best = None
    for f in sorted(glob.glob(str(ROOT / "supabase" / "migrations" / "*.sql"))):
        src = io.open(f, encoding="utf-8", errors="replace").read()
        if "automation_log_status_check" not in src:
            continue
        m = re.search(r"automation_log_status_check\s*\n?\s*CHECK\s*\((.*?)\)\s*;", src, re.S)
        if not m:
            m = re.search(r"CHECK\s*\(\s*status\s*=\s*ANY\s*\(\s*ARRAY\s*\[(.*?)\]", src, re.S)
        if m:
            vals = set(re.findall(r"'([a-z_]+)'", m.group(1)))
            if vals:
                best = vals          # later files win — migrations apply in order
    return best


def allowed_from_db():
    if not shutil.which("docker"):
        return None
    try:
        r = subprocess.run(
            ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-c",
             "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='automation_log_status_check'"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45)
        if r.returncode != 0 or not r.stdout.strip():
            return None
        return set(re.findall(r"'([a-z_]+)'", r.stdout))
    except Exception:
        return None


def main() -> int:
    declared = allowed_from_migrations()
    if not declared:
        print("FAIL automation-log-status — no migration defines automation_log_status_check; "
              "the allowed set has no declared source.")
        return 1

    live = allowed_from_db()
    if live is not None and live != declared:
        print(f"FAIL automation-log-status — the migrations declare {sorted(declared)} but the live "
              f"database enforces {sorted(live)}. A repo that says one thing while the database "
              f"enforces another is its own defect: apply the migration, or fix it.")
        return 1
    print(f"  allowed: {sorted(declared)}" + ("  (live constraint agrees)" if live else "  (db not checked)"))

    fails, unchecked, total_inserts = [], [], 0
    for f in sorted(glob.glob(str(ROOT / "supabase" / "functions" / "*" / "index.ts"))):
        src = io.open(f, encoding="utf-8", errors="replace").read()
        name = Path(f).parent.name
        for m in re.finditer(r'from\(\s*"automation_log"\s*\)\s*\.insert\(', src):
            total_inserts += 1
            head = src[max(0, m.start() - 120): m.start()]
            if "const {" not in head and "const{" not in head:
                unchecked.append(name)
            body = src[m.end(): m.end() + 700]
            for sm in re.finditer(r'status:\s*([^,\n]+)', body[:body.find("});") + 1 if "});" in body else 400]):
                for lit in re.findall(r'"([a-z_]+)"', sm.group(1)):
                    if lit not in declared:
                        fails.append(f'{name}: writes status "{lit}", which the constraint forbids '
                                     f'({sorted(declared)}) — the row is refused with 23514')

    print(f"  automation_log inserts: {total_inserts} total, {len(unchecked)} of them unchecked")
    if fails:
        print("FAIL automation-log-status:")
        for x in sorted(set(fails)):
            print("    - " + x)
        return 1

    n = len(unchecked)
    if not BASELINE.exists():
        BASELINE.write_text(json.dumps({"unchecked": n, "established": "2026-08-26"}, indent=1), encoding="utf-8")
        print(f"BASELINE established: {n} unchecked automation_log inserts (forward-only)")
        return 0
    base = json.loads(BASELINE.read_text(encoding="utf-8")).get("unchecked", n)
    if n > base:
        print(f"FAIL automation-log-status — unchecked automation_log inserts GREW {base} -> {n}. "
              f"An unchecked insert is what turned two forbidden-status bugs into silence; read the "
              f"error on new ones.")
        return 1
    if n < base:
        BASELINE.write_text(json.dumps({"unchecked": n, "ratcheted": "auto"}, indent=1), encoding="utf-8")
        print(f"PASS automation-log-status — every status is allowed; unchecked inserts improved {base} -> {n}.")
        return 0
    print(f"PASS automation-log-status — every status literal is one the constraint allows; "
          f"unchecked inserts held at {n}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
