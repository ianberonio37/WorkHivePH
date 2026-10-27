#!/usr/bin/env python3
"""validate_probe_identities_resolve.py - a probe acts as a person it LOOKS UP, never as a literal account id (2026-10-28).

WHY. Eight bank probes and two provers named the people they act as - a Baguio worker, a supervisor, an outsider - and
the project they act on, by literal uuids. The clean reseed (2026-10-27) recreated every account and project, so each
id named nobody: a supervisor's legitimate write read BLOCKED, change orders broke their foreign key, a prover could not
insert its first post, and a probe of a guard that keys on "not a member" passed on a ghost who is a member of nothing.
The same literal then reached the public repository and GitGuardian mailed Ian a "Generic High Entropy Secret" alert
for it (a dead test-account id - not a credential, but a random-looking literal in a public repo reads as one).

THE RULE. Where a probe or prover names WHO acts - a JWT `sub`, an `auth_uid = '...'` filter, a `uid:` / `UID_*` /
`sub:` constant - the id is resolved at run time (by e-mail, or by role in a pinned hive). Two literals stay legal:
  - a SYNTHETIC fixture id (six zeros in a row, e.g. d0000000-0000-4000-8000-0000000000e1): minted by the probe, never
    a real account, and it cannot rot;
  - an account the same file CREATES (`insert into auth.users ... '<that id>'`), rolled back with it.

    python tools/validate_probe_identities_resolve.py
    python tools/validate_probe_identities_resolve.py --self-test
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
UU = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
# the contexts that say "this id is a PERSON who acts or is named"
ACTOR = [
    re.compile(r'"sub"\s*:\s*"(' + UU + r')"', re.I),                          # a JWT claim written as JSON
    re.compile(r"\bauth_uid\s*=\s*'(" + UU + r")'", re.I),                      # SQL: filter on the account
    re.compile(r"\b(?:uid|sub)\s*:\s*['\"](" + UU + r")['\"]", re.I),           # JS: { uid: '...' }
    re.compile(r"\bUID_?\w*\s*=\s*['\"](" + UU + r")['\"]"),                     # PY: UID_A = "..."
]
GLOBS = ["tests/bank_probes/*.sql", "tools/psql_probes/*.sql", "tools/*.mjs", "tools/*.py", "tools/lib/*.mjs",
         "tools/lib/*.py", "tests/*.spec.js", "tests/**/*.spec.js"]
SELF = Path(__file__).name


def synthetic(u: str) -> bool:
    # a hand-made fixture id repeats one digit (d0000000-..., 11111111-...); a random uuid almost never has six in a row
    return bool(re.search(r"([0-9a-f])\1{5}", u.replace("-", "")))


def created_here(u: str, src: str) -> bool:
    return bool(re.search(r"insert\s+into\s+auth\.users[^;]*?" + re.escape(u), src, re.I | re.S))


def offenders(src: str) -> list[tuple[int, str]]:
    out = []
    for rx in ACTOR:
        for m in rx.finditer(src):
            u = m.group(1).lower()
            if synthetic(u) or created_here(u, src):
                continue
            out.append((src.count("\n", 0, m.start()) + 1, u[:6] + "..."))
    return sorted(set(out))


def self_test() -> int:
    real = "3f9a1c2e-7b4d-4e8a-9c1f-5d2b6a7e8f90"
    cases = [
        ("a claim as a literal real-looking id", "select set_config('request.jwt.claims','{\"sub\":\"%s\",\"role\":\"authenticated\"}', true);" % real, True),
        ("an auth_uid filter on a literal", "select 1 from t where auth_uid = '%s';" % real, True),
        ("a JS person constant", "const B = { name: 'Bryan', uid: '%s' };" % real, True),
        ("a PY person constant", 'UID_B = "%s"' % real, True),
        ("a synthetic fixture id", "'{\"sub\":\"d0000000-0000-4000-8000-0000000000e1\"}'", False),
        ("an account the file creates", "insert into auth.users (id, email) values ('%s', 'x@y');\n'{\"sub\":\"%s\"}'" % (real, real), False),
        ("a claim built from a lookup", "json_build_object('sub', (select worker from _tb), 'role', 'authenticated')", False),
        ("a hive id is not a person", "insert into hives(id) values ('%s');" % real, False),
    ]
    bad = 0
    for name, src, want in cases:
        got = bool(offenders(src))
        ok = got == want
        bad += not ok
        print(f"  {'ok ' if ok else 'BAD'} {name}: {'flagged' if got else 'clean'} (want {'flagged' if want else 'clean'})")
    print("self-test " + ("PASS" if not bad else f"FAIL ({bad})"))
    return 1 if bad else 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    files = sorted({p for g in GLOBS for p in ROOT.glob(g) if p.is_file() and p.name != SELF and "node_modules" not in p.parts})
    hits = []
    for p in files:
        try:
            src = p.read_text(encoding="utf-8")
        except Exception:
            continue
        for line, u in offenders(src):
            hits.append((p.relative_to(ROOT).as_posix(), line, u))
    if hits:
        print(f"FAIL probe-identities-resolve - {len(hits)} literal account id(s) a probe or prover acts as or names:")
        for f, line, u in hits[:60]:
            print(f"  {f}:{line}  {u}")
        print("  Resolve the person at run time (by e-mail, or by role in a pinned hive) - see tests/bank_probes/"
              "TB-PLOG-progress-log-record.sql's _tb lookup.")
        return 1
    print(f"PASS probe-identities-resolve - {len(files)} probe/prover files; every person a probe acts as is looked up, "
          "minted synthetic, or created in the file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
