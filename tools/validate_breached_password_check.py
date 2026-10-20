#!/usr/bin/env python3
"""validate_breached_password_check.py - BRH-W (2026-10-21): a password from a public breach list is refused where a
person sets one.

Supabase's advisor (auth_leaked_password_protection) found sign-up and password change accepting passwords known to be
leaked. The server-side check is a Supabase Pro-plan feature and this project is on Free, so index.html - the only page
that sets a password (sign-up, and the reset link's new password) - asks the Pwned Passwords range API the k-anonymity
way before it sends one: only the first 5 hex characters of the password's SHA-1 leave the browser.

STATIC  W1 index.html defines _passwordBreached and calls it BEFORE auth.signUp( and before auth.updateUser({ password
        W2 the breach check sends only a 5-character prefix (range/ + hex.slice(0, 5)) and never the password or its hash
        W3 sw.js passes api.pwnedpasswords.com through untouched (intercepted, the worker's own CSP refuses the request and
           the check fails open - protecting no one)
        W4 the CSP that serves index.html ('/' and '/index.html' in vercel.json) lets the page reach the API
SELF-TEST (--self-test): each of W1..W4 broken in a copy of the file, each caught.

    python tools/validate_breached_password_check.py [--self-test]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "api.pwnedpasswords.com"


def check(files: dict[str, str] | None = None) -> list[str]:
    def text(rel: str) -> str:
        return files[rel] if files and rel in files else (ROOT / rel).read_text(encoding="utf-8", errors="replace")

    issues = []
    page = text("index.html")
    if "async function _passwordBreached(" not in page:
        issues.append("W1 index.html no longer defines _passwordBreached")
    # the CALLS, not the definition: each setter must be preceded closely by its own call, with no other setter between
    calls = [m.start() for m in re.finditer(r"_passwordBreached\(", page)
             if not page[max(0, m.start() - 15):m.start()].endswith("function ")]
    setters = {what: re.search(rx, page) for rx, what in ((r"\.auth\.signUp\(", "sign-up"),
                                                         (r"\.auth\.updateUser\(\s*\{\s*password", "the new password a reset link sets"))}
    for what, m in setters.items():
        if not m:
            issues.append(f"W1 index.html no longer sets a password at {what} - re-read this gate's premise")
            continue
        before = [c for c in calls if c < m.start()]
        other = [s.start() for w, s in setters.items() if s and w != what and s.start() < m.start()]
        near = before[-1] if before else None
        if near is None or m.start() - near > 3000 or any(near < o < m.start() for o in other):
            issues.append(f"W1 {what} sends a password without asking _passwordBreached first")
    body = page[page.find("async function _passwordBreached("):][:2500]
    if "range/' + hex.slice(0, 5)" not in body:
        issues.append("W2 the breach check no longer sends only the 5-character SHA-1 prefix (range/ + hex.slice(0, 5))")
    if re.search(r"fetch\([^)]*\b(pw|hex)\b(?!\.slice\(0, 5\))", body):
        issues.append("W2 the breach check sends the password or its whole hash")
    sw = text("sw.js")
    fetch_at = sw.find("self.addEventListener('fetch'")
    first_respond = sw.find("respondWith(", fetch_at)
    passthrough = re.search(r"if \(url\.includes\('" + re.escape(API) + r"'\)\) return;", sw)
    if not passthrough or not (fetch_at < passthrough.start() < first_respond):
        issues.append(f"W3 sw.js intercepts {API}: the worker's own CSP refuses it, the check fails open and protects no one")
    v = json.loads(text("vercel.json"))
    for src in ("/", "/index.html"):
        rule = next((h for h in v.get("headers", []) if h.get("source") == src), None)
        csp = next((kv["value"] for kv in (rule or {}).get("headers", []) if kv.get("key", "").lower() == "content-security-policy"), "")
        m = re.search(r"connect-src ([^;]*)", csp)
        if not m or f"https://{API}" not in m.group(1):
            issues.append(f"W4 the CSP for {src} does not let the page reach https://{API} (connect-src)")
    return issues


def self_test() -> list[str]:
    fails = []
    if check():
        fails.append(f"the clean run is not green: {check()[:2]}")
    page = (ROOT / "index.html").read_text(encoding="utf-8")
    sw = (ROOT / "sw.js").read_text(encoding="utf-8")
    vj = (ROOT / "vercel.json").read_text(encoding="utf-8")
    mutants = [
        ("sign-up stops asking", {"index.html": page.replace("if (await _passwordBreached(password))", "if (false)", 1)}, "W1"),
        ("the reset stops asking", {"index.html": page.replace("if (await _passwordBreached(np))", "if (false)", 1)}, "W1"),
        ("the whole hash is sent", {"index.html": page.replace("range/' + hex.slice(0, 5)", "range/' + hex", 1)}, "W2"),
        ("the worker intercepts the API", {"sw.js": sw.replace("if (url.includes('api.pwnedpasswords.com')) return;", "", 1)}, "W3"),
        ("the CSP loses the API", {"vercel.json": vj.replace(" https://api.pwnedpasswords.com", "", 1)}, "W4"),
    ]
    for name, files, want in mutants:
        got = check(files)
        if not any(g.startswith(want) for g in got):
            fails.append(f"mutant '{name}' was not caught (got {got[:2]})")
    return fails


def main() -> int:
    if "--self-test" in sys.argv:
        fails = self_test()
        print("SELF-TEST PASS (5 mutants caught; the clean run is green)" if not fails else "SELF-TEST FAIL\n  " + "\n  ".join(fails))
        return 1 if fails else 0
    issues = check()
    print("Breached-password check (BRH-W): a password from a public breach list is refused where a person sets one")
    for i in issues:
        print("  [FAIL] " + i)
    print("  PASS - sign-up and the reset link ask the range API (5-character prefix) under a CSP that allows it, and the "
          "worker does not intercept it" if not issues else f"  FAIL - {len(issues)} problem(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
