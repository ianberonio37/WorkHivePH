#!/usr/bin/env python3
"""validate_fixture_hive_exists.py — a pinned test hive that no longer exists is a SILENT instrument.

FOUND 2026-07-30 while triaging `read-battery`, which reported six pages failing "DB empty -> empty-state
(no error)". Every one read `db=0`, and the reason was not the pages: the hive UUID hardcoded as the
battery's fallback — `636cf7e8-…` — **does not exist in the database at all**. A reseed removed it, and
every instrument still pinned to it started measuring an empty world.

That is the worst shape a test failure can take. It does not error, it does not skip; it renders six
plausible, specific, entirely fictional page defects and sends you to read page code that was never
wrong. This class has bitten before ([[feedback_stale_hive_fixture_mjs_mirror]], "3 stale UUIDs") and
had grown to EIGHT files by the time this gate was written.

WHAT IT CHECKS: every hive-shaped UUID pinned as a literal in a tool/test is looked up in the live DB.
A pinned id that resolves to no row FAILs — with the file and line, so the fix is a one-line edit
rather than an afternoon of triage. The all-zeros UUID is exempt: it is deliberately unresolvable, used
to prove a NEGATIVE (a caller with no tenancy).

WHY NOT JUST REPIN IT: a fresh literal rots on the next reseed exactly as this one did. The durable fix
is dynamic resolution, and this gate is what makes the rot LOUD in the meantime — it turns a silent
six-page phantom into one line naming the file.

Usage:  python tools/validate_fixture_hive_exists.py [--selftest]
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = "supabase_db_workhive"
GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

SCAN_DIRS = ["tools", "tests"]
SCAN_ROOT_FILES = [f for f in os.listdir(ROOT) if f.startswith("validate_") and f.endswith(".py")]
UUID = re.compile(r"['\"]([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})['\"]")
# Only lines that actually mean "a hive" — a probe's self-minted row ids are not fixtures to resolve.
HIVE_HINT = re.compile(r"hive", re.I)
ALL_ZERO = "00000000-0000-0000-0000-000000000000"


def psql(sql):
    try:
        r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres",
                            "-Atc", sql], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=30)
    except Exception:
        return None
    return (r.stdout or "").strip()


def pinned():
    """-> {uuid: [(file, line)]} for every hive-hinted literal."""
    # SCOPED TO INSTRUMENTS THE SUITE ACTUALLY RUNS. A scratch diagnostic pinning a dead hive is dead
    # code; a REGISTERED gate pinning one lies to the suite on every run, and only the second is worth
    # a red. Scanning everything returned 24 hits, most of them abandoned one-off probes — noise that
    # would train a reader to skim this gate.
    found: dict[str, list] = {}
    try:
        reg = open(os.path.join(ROOT, "run_platform_checks.py"), encoding="utf-8").read()
    except Exception:
        reg = ""
    files = []
    for d in SCAN_DIRS:
        dp = os.path.join(ROOT, d)
        if not os.path.isdir(dp):
            continue
        for f in os.listdir(dp):
            if not f.endswith((".py", ".mjs", ".ts", ".js")):
                continue
            # registered by name, referenced by a registered script, or a real spec
            if f in reg or f.endswith(".spec.ts"):
                files.append(os.path.join(dp, f))
    files += [os.path.join(ROOT, f) for f in SCAN_ROOT_FILES if f in reg]
    # .mjs helpers a registered python gate shells out to
    for d in SCAN_DIRS:
        dp = os.path.join(ROOT, d)
        if not os.path.isdir(dp):
            continue
        bodies = ""
        for fp in list(files):
            try: bodies += open(fp, encoding="utf-8", errors="replace").read()
            except Exception: pass
        for f in os.listdir(dp):
            if f.endswith(".mjs") and f in bodies:
                fp = os.path.join(dp, f)
                if fp not in files:
                    files.append(fp)
    for path in files:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                body = fh.read()
        except Exception:
            continue
        # A SELF-MINTED fixture is supposed not to exist. The rolled-back probes on this platform
        # create their own hive inside `begin; … rollback;` precisely so they borrow nothing — asking
        # the live DB for it would report every well-built probe as rot. My first cut did exactly that
        # and returned 37 "stale" hives, most of them correct code. If the file MINTS the id, the id
        # is not a seed reference and this gate has no business resolving it.
        minted = set(re.findall(
            r"insert\s+into[^;]{0,400}?['\"]([0-9a-f-]{36})['\"]", body, re.I | re.S))
        for n, line in enumerate(body.splitlines(), 1):
            if not HIVE_HINT.search(line):
                continue
            for u in UUID.findall(line):
                if u == ALL_ZERO or u in minted:
                    continue          # deliberately unresolvable, or created by this file itself
                found.setdefault(u, []).append((os.path.relpath(path, ROOT), n))
    return found


def main():
    if "--selftest" in sys.argv:
        return selftest()
    if psql("select 1;") is None:
        print("  SKIP: docker/psql unavailable")
        return 0
    found = pinned()
    if not found:
        print(f"  {GREEN}PASS{RST} — no hive UUID is pinned as a literal")
        return 0
    live = set((psql("select id::text from public.hives;") or "").splitlines())
    print("=" * 84)
    print(f"  {BOLD}Fixture hive existence — a pinned hive that is gone measures an empty world{RST}")
    print("=" * 84)
    dead = 0
    for u, sites in sorted(found.items()):
        ok = u in live
        if ok:
            print(f"  {GREEN}OK  {RST}  {u}  {DIM}pinned in {len(sites)} file(s){RST}")
        else:
            dead += 1
            print(f"  {RED}GONE{RST}  {u}  — pinned in {len(sites)} file(s) and NOT in public.hives:")
            for f, n in sites[:10]:
                print(f"          {f}:{n}")
    import json as _json
    bl = os.path.join(ROOT, "fixture_hive_baseline.json")
    base = 0
    if os.path.exists(bl):
        try: base = int(_json.load(open(bl, encoding="utf-8")).get("dead", 0))
        except Exception: base = 0
    print()
    if dead and dead <= base:
        print(f"{YEL}KNOWN{RST} — {dead} pinned hive(s) are already-recorded rot (baseline {base}). "
              f"Still printed every run so they cannot be forgotten; a NEW one FAILs. Repointing any "
              f"of them ratchets this down.")
        if dead < base:
            _json.dump({"dead": dead, "_doc": "forward-only: pinned hives that no longer resolve"},
                       open(bl, "w", encoding="utf-8"), indent=2)
            print(f"  {GREEN}ratcheted{RST} {base} -> {dead}")
        return 0
    if dead:
        print(f"{RED}FAIL{RST} — {dead} pinned hive(s) no longer exist. Every instrument using one is "
              f"measuring an EMPTY WORLD and will report plausible, specific, fictional page defects. "
              f"Repoint them, or better, resolve the hive dynamically.")
        return 1
    print(f"{GREEN}PASS{RST} — every pinned test hive resolves to a live row")
    return 0


def selftest():
    ok = True
    live = {"aaaaaaaa-0000-4000-8000-000000000001"}
    cases = [("aaaaaaaa-0000-4000-8000-000000000001", True, "a live pinned hive passes"),
             ("bbbbbbbb-0000-4000-8000-000000000002", False, "a vanished pinned hive is caught")]
    for u, want, label in cases:
        got = u in live
        if got != want:
            print(f"  {RED}FAIL{RST} {label}"); ok = False
        else:
            print(f"  {GREEN}PASS{RST} {label}")
    # The all-zeros id is a deliberate negative fixture and must never be reported as rot.
    if ALL_ZERO in pinned():
        print(f"  {RED}FAIL{RST} the all-zeros negative fixture was treated as a stale hive"); ok = False
    else:
        print(f"  {GREEN}PASS{RST} the all-zeros negative fixture is exempt")
    print(f"\n  SELFTEST: {GREEN + 'PASS' + RST if ok else RED + 'FAIL' + RST}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
