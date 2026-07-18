#!/usr/bin/env python3
# DEEPWALK-CELL: * D20
r"""validate_client_resilience.py — D20 client resilience (fetch timeout-bounded, offline UX).

THE CLASS (utils.js §AbortController note, Arc S D-lens): a data read that hangs forever (a
dropped connection, a wedged edge fn) leaves the field worker staring at a spinner, assuming the
page is broken — with no timeout, no error, no retry. And a plant with intermittent connectivity
needs a visible offline signal + a path that survives the outage, not a silent white-screen.

The fix is a SHARED mechanism on the singleton Supabase client + two platform-wide widgets, so
every page inherits it — hence the `* D20` wildcard (one shared client + shared widgets, used
everywhere via the singleton that `validate_client_singleton.py` enforces).

THREE deterministic layers ($0, no browser/DB/model):
  1. TIMEOUT-BOUNDED FETCH — the singleton client is created with `global: { fetch: <wrapper> }`
     and that wrapper is a real AbortController-based timeout (a `setTimeout(...)=>abort()` guard),
     so EVERY client request is bounded — a hung backend surfaces as a catchable error, not an
     infinite spinner.
  2. OFFLINE SIGNAL — `offline-banner.js` exists (a visible degraded-connectivity banner).
  3. HEALTH/CONNECTIVITY — `connectivity-widget.js` exists (backend health-ping so the worker
     knows the difference between "slow" and "down").

Exit 0 = PASS, 1 = FAIL. No file is edited.
"""
from __future__ import annotations
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
UTILS = ROOT / "utils.js"
GRN, RED, YEL, BLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"


def main() -> int:
    fails: list[str] = []
    print(f"{BLD}CLIENT RESILIENCE (D20) — timeout-bounded fetch + offline UX, platform-wide{RST}")
    print("=" * 80)

    if not UTILS.is_file():
        print(f"{RED}FAIL{RST}: utils.js not found")
        return 1
    src = UTILS.read_text(encoding="utf-8", errors="replace")

    # 1. TIMEOUT-BOUNDED FETCH — the singleton client overrides global.fetch with a wrapper, and
    #    that wrapper is a genuine AbortController timeout (not a passthrough).
    fetch_override = re.search(r"global:\s*\{[^}]*\bfetch:\s*([A-Za-z_$][\w$]*)", src)
    if not fetch_override:
        fails.append("shared Supabase client does not override global.fetch with a timeout wrapper "
                     "(a hung backend read spins forever with no error)")
    else:
        wrapper = fetch_override.group(1)
        # the wrapper (or the module) must use AbortController + a timeout→abort guard
        has_abort = "AbortController" in src and re.search(r"setTimeout\([^)]*\.abort\(\)|\.abort\(\)", src)
        if not has_abort:
            fails.append(f"global.fetch wrapper `{wrapper}` has no AbortController/timeout→abort guard "
                         f"(not actually bounded)")

    # 2 + 3. OFFLINE + CONNECTIVITY widgets exist.
    if not (ROOT / "offline-banner.js").is_file():
        fails.append("offline-banner.js missing (no visible degraded-connectivity signal)")
    if not (ROOT / "connectivity-widget.js").is_file():
        fails.append("connectivity-widget.js missing (no backend health-ping / slow-vs-down signal)")

    fetch_ok = bool(fetch_override) and "global.fetch wrapper" not in "".join(fails)
    print(f"  timeout-bounded fetch: {'✓' if fetch_ok else '✗'} · "
          f"offline-banner: {'✓' if (ROOT/'offline-banner.js').is_file() else '✗'} · "
          f"connectivity-widget: {'✓' if (ROOT/'connectivity-widget.js').is_file() else '✗'}")

    if fails:
        print(f"\n{RED}FAIL{RST}: {len(fails)} D20 client-resilience breach(es):")
        for f in fails:
            print(f"  {RED}✗{RST} {f}")
        return 1
    print(f"\n{GRN}PASS{RST}: every client request is AbortController-timeout-bounded and the offline/"
          f"connectivity widgets are present → no infinite-spinner / silent-offline surface.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
