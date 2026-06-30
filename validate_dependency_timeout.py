#!/usr/bin/env python3
"""validate_dependency_timeout.py - Arc S (Resilience/DR) F-lens cell `dependency_timeout`.
================================================================================
A dead/slow backend must FAIL FAST, not hang the tab forever. The platform routes
every Supabase call through the getDb() singleton, so installing a timeout-bounded
`fetch` there (passed to createClient via { global: { fetch } }) bounds EVERY
PostgREST + Auth + Storage request platform-wide in one place (F-002 db hang,
F-008 auth getSession hang).

This gate asserts getDb() in utils.js installs that timeout fetch: a custom fetch
wired into createClient's global option, using an AbortController + setTimeout (or
AbortSignal.timeout). Forward-only against someone dropping the wrapper.

Exit 0 = timeout-bounded client; 1 = unbounded (would hang). Stdlib, $0.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"


def main() -> int:
    print(f"{B}Arc S - dependency timeout (F-lens, no infinite hang){X}")
    print("=" * 60)
    try:
        u = (ROOT / "utils.js").read_text(encoding="utf-8", errors="replace")
    except OSError:
        print(f"  {R}FAIL{X}  utils.js not found")
        return 1

    # Find the getDb body.
    m = re.search(r"getDb\s*=\s*function[^{]*\{(.*?)\n\};", u, re.DOTALL)
    body = m.group(1) if m else ""
    checks = {
        "createClient gets a custom global.fetch":
            bool(re.search(r"createClient\([^;]*global\s*:\s*\{\s*fetch", body, re.DOTALL)),
        "the custom fetch is timeout-bounded (AbortController/AbortSignal + setTimeout)":
            ("AbortController" in body or "AbortSignal" in body) and "setTimeout" in body,
        "timeout is configurable (WH_DB_TIMEOUT_MS)":
            "WH_DB_TIMEOUT_MS" in body,
    }
    issues = [k for k, ok in checks.items() if not ok]
    for k, ok in checks.items():
        print(f"  {(G+'PASS'+X) if ok else (R+'FAIL'+X)}  {k}")

    if issues:
        print(f"\n{R}{B}  DEPENDENCY-TIMEOUT: FAIL{X} - getDb() client is not timeout-bounded.")
        return 1
    print(f"\n{G}{B}  DEPENDENCY-TIMEOUT: PASS{X} - every db/auth/storage call is timeout-bounded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
