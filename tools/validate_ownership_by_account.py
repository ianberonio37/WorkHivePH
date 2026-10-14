#!/usr/bin/env python3
"""validate_ownership_by_account.py - "mine" is decided by the ACCOUNT, never by the name the device remembers (gate
`ownership-by-account`).

SL sub-layer AU3 (2026-10-14): "the platform must treat the signed-in account as this page's identity, so a renamed or
shared name never moves anyone's rows." Walked as one signed-in person with the device remembering another member's
display name (a rename made elsewhere, or a namesake): the logbook listed that member's 2,140 bound entries as this
person's (4,417 vs 2,277), the hive board counted their open job as "assigned to you", the PM scheduler marked five of
their assets "yours" and offered Delete on them, community took this person's own posts and reactions for someone
else's, and a real platform admin was refused marketplace-admin. Two shapes, both now forbidden:

  A. THE WIDE UNION. `_mineFilter()` built `auth_uid.eq.<me>,worker_name.eq."<name>"`, so any row bound to ANOTHER
     account still matched by name. The name half must apply only where auth_uid IS NULL - the legacy and service-role
     rows it exists to reach: `auth_uid.eq.<me>,and(auth_uid.is.null,worker_name.eq."<name>")`.
  B. OWNERSHIP BY NAME. `row.worker_name === WORKER_NAME` (or author_name, either side). A row that carries auth_uid is
     mine only when it is my account (pages use a local `_isMine(row)` / `_isMineRow(row)`); a line that compares the
     name on purpose - the fallback branch after the account was asked - carries `name-compare-allow: <reason>`.

Comments are stripped before matching (a `/*` glued to a word or a quote - `accept="image/*"` - is not an opener).

  python tools/validate_ownership_by_account.py
  python tools/validate_ownership_by_account.py --self-test
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_BLOCK_C = re.compile(r"(?<![\w\"'*/=])/\*.*?\*/", re.S)
_HTML_C = re.compile(r"<!--.*?-->", re.S)
_LINE_C = re.compile(r"^\s*//.*$", re.M)
ALLOW = "name-compare-allow:"

WIDE_UNION = re.compile(
    r"'auth_uid\.eq\.'\s*\+\s*[A-Za-z_]\w*\s*\+\s*\(\s*nm\s*\?\s*','\s*\+\s*quoted"          # the _mineFilter builder
    r"|'auth_uid\.eq\.'\s*\+\s*[A-Za-z_][\w.]*\s*\+\s*',(?:worker_name|author_name)\.eq\.")   # ...and the same union inline
BY_NAME = re.compile(r"\.(?:worker_name|author_name)\s*[!=]==?\s*WORKER_NAME\b"
                     r"|\bWORKER_NAME\s*[!=]==?\s*[A-Za-z_][\w?.]*\.(?:worker_name|author_name)\b")


def _blank(m: re.Match) -> str:
    return re.sub(r"[^\n]", " ", m.group(0))   # keep line numbers


def _code(text: str) -> str:
    return _LINE_C.sub(_blank, _BLOCK_C.sub(_blank, _HTML_C.sub(_blank, text)))


def findings(text: str) -> list[tuple[int, str, str]]:
    raw_lines = text.split("\n")
    code = _code(text)
    out = []
    for rx, kind in ((WIDE_UNION, "wide union"), (BY_NAME, "ownership by name")):
        for m in rx.finditer(code):
            ln = code.count("\n", 0, m.start()) + 1
            if kind == "ownership by name" and ALLOW in raw_lines[ln - 1]:
                continue
            out.append((ln, kind, raw_lines[ln - 1].strip()[:140]))
    return sorted(out)


def _files() -> list[Path]:
    return sorted(list(ROOT.glob("*.html")) + list(ROOT.glob("*.js")))


def self_test() -> int:
    cases = [
        ("the wide union (the defect)", "  return 'auth_uid.eq.' + _authUid + (nm ? ',' + quoted : '');", 1),
        ("an INLINE wide union (assistant, achievements, hive, community, marketplace-seller had five)",
         ".or('auth_uid.eq.' + _uid + ',worker_name.eq.' + JSON.stringify(String(name || '')))", 1),
        ("the inline union narrowed",
         ".or('auth_uid.eq.' + _uid + ',and(auth_uid.is.null,worker_name.eq.' + JSON.stringify(String(name || '')) + ')')", 0),
        ("the narrowed union", "  return 'auth_uid.eq.' + uid + (nm ? ',and(auth_uid.is.null,' + quoted + ')' : '');", 0),
        ("ownership by name", "if (asset.worker_name !== WORKER_NAME) { deny(); }", 1),
        ("ownership by name, reversed", "const canMark = (WORKER_NAME === post.author_name);", 1),
        ("a realtime row by name", "if (payload.new.author_name === WORKER_NAME) mine.add(id);", 1),
        ("by the account", "if (!_isMine(asset)) { deny(); }", 0),
        ("the fallback branch, marked", "  return m.worker_name === WORKER_NAME;   // name-compare-allow: account asked first", 0),
        ("a comment that mentions the old check", "// was: if (asset.worker_name !== WORKER_NAME)\nok();", 0),
        ("accept=\"image/*\" does not hide a real check", "<input accept=\"image/*\">\n<script>\nif (a.worker_name === WORKER_NAME) x();\n/* c */\n</script>", 1),
        ("a teammate looked up by the name ON SCREEN is not ownership", "openProfile(row.worker_name);", 0),
    ]
    ok = True
    for name, text, want in cases:
        got = len(findings(text))
        good = got == want
        ok &= good
        print(f"  {'ok ' if good else 'BAD'} {name}: {got} finding(s), want {want}")
    print("ownership-by-account self-test:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv[1:]:
        return self_test()
    bad = []
    for p in _files():
        text = io.open(p, encoding="utf-8", errors="replace").read()
        for ln, kind, line in findings(text):
            bad.append(f"{p.name}:{ln} {kind}: {line}")
    if bad:
        for b in bad:
            print("  FAIL", b)
        print(f"ownership-by-account: FAIL - {len(bad)} place(s) decide 'mine' by the remembered name. Use the account "
              f"(a page-local _isMine(row)), narrow a union to and(auth_uid.is.null,...), or mark a deliberate fallback "
              f"with `{ALLOW} <reason>`.")
        return 1
    print(f"ownership-by-account: PASS - {len(_files())} pages and shared scripts decide 'mine' by the account.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
