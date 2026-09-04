#!/usr/bin/env python3
"""validate_no_get_mutation.py — T377's lock: no edge function performs a WRITE on an HTTP GET, and mutating
functions are POST — so there is no state-changing GET a cross-site page could trigger. Combined with the
platform's bearer-token auth (the Authorization header, never an ambient cookie), this closes the CSRF
surface: a cross-site GET carries no credential and, even if it did, hits no mutating handler.

CSRF needs two things: an ambient credential the browser attaches automatically (a cookie), and a
state-changing request a foreign page can cause. WorkHive has neither — auth is a bearer JWT (a foreign page
cannot read or attach it) and mutations are POST. This gate holds the second half: it scans edge functions
and refuses any that BOTH branch on `method === 'GET'` AND mutate (.insert/.update/.delete/.upsert or a
write RPC) inside that file — a GET that writes.

Static source lock (browser-free). Read-only. Registered in run_platform_checks (Platform).
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FNDIR = ROOT / "supabase" / "functions"

CHECK_NAMES = ["no-get-mutation"]

_GET_BRANCH = re.compile(r"""method\s*===?\s*['"]GET['"]|['"]GET['"]\s*===?\s*\w*\.?method""")
_MUTATION = re.compile(r"\.(insert|update|delete|upsert)\s*\(")


def check_file(src: str) -> bool:
    """SAFE if it does not both branch on GET and mutate. (A file with no GET branch is safe; a GET-only
    read fn with no mutation is safe.)"""
    if not _GET_BRANCH.search(src):
        return True
    return not _MUTATION.search(src)


def scan() -> list[str]:
    problems: list[str] = []
    for idx in sorted(FNDIR.glob("*/index.ts")):
        src = idx.read_text(encoding="utf-8", errors="replace")
        if not check_file(src):
            problems.append(f"{idx.parent.name}: branches on method === 'GET' AND performs a table mutation "
                            f"(.insert/.update/.delete) — a state-changing GET is a CSRF surface; make the "
                            f"mutation POST-only.")
    return problems


def main() -> int:
    if not FNDIR.exists():
        print("SKIP no-get-mutation — supabase/functions not found."); return 0
    problems = scan()
    if problems:
        print("FAIL no-get-mutation — an edge fn mutates on a GET request (CSRF surface):")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS no-get-mutation — no edge function mutates on an HTTP GET; state changes are POST with a "
          "bearer JWT (no ambient-cookie CSRF surface).")
    return 0


def self_test() -> int:
    fails = []
    safe_read = 'if (req.method === "GET") { const {data} = await db.from("x").select("*"); return json(data); }'
    if not check_file(safe_read):
        fails.append("a GET that only READS should PASS")
    no_get = 'if (req.method !== "POST") return err(405); await db.from("x").insert(row);'
    if not check_file(no_get):
        fails.append("a POST-only mutating fn should PASS")
    bad = 'if (req.method === "GET") { await db.from("x").delete().eq("id", id); }'
    if check_file(bad):
        fails.append("a GET that DELETES should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_no_get_mutation self-test (GET+delete reddens; GET-read + POST-mutate pass)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
