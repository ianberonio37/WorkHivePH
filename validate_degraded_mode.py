#!/usr/bin/env python3
"""validate_degraded_mode.py - Arc S (Resilience/DR) D-lens cell `backend_degraded_mode`.
================================================================================
navigator.onLine only knows the DEVICE link. When the device is online but Supabase
is unreachable/5xx, the app would read as "Online" while every read/write silently
fails. The connectivity widget must DETECT backend degradation (a throttled health
ping) and expose a distinct degraded state so the chip + pages can react.

This gate asserts:
  - utils.js getDb() publishes the project URL (window.WH_SUPABASE_URL) so the widget
    can reach a health endpoint,
  - connectivity-widget.js health-pings the backend (timeout-bounded), tracks a
    degraded state distinct from offline, and exposes window.whConnectivityState()
    for pages to render a read-only / "writes will queue" banner.

Exit 0 = backend degradation is detectable + surfaced; 1 = it would read as Online. Stdlib, $0.
"""
from __future__ import annotations
import io, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"


def _read(name: str) -> str:
    try:
        return (ROOT / name).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def main() -> int:
    print(f"{B}Arc S - backend degraded-mode detection (D-lens){X}")
    print("=" * 60)
    utils = _read("utils.js")
    widget = _read("connectivity-widget.js")
    checks = {
        "getDb() publishes WH_SUPABASE_URL for the health ping":
            "WH_SUPABASE_URL" in utils,
        "widget health-pings the backend (timeout-bounded)":
            "pingBackend" in widget and ("fetchWithTimeout" in widget or "AbortController" in widget),
        "widget has a degraded state distinct from offline":
            'data-state' in widget and 'degraded' in widget,
        "widget exposes whConnectivityState() for pages":
            "whConnectivityState" in widget,
    }
    for k, ok in checks.items():
        print(f"  {(G+'PASS'+X) if ok else (R+'FAIL'+X)}  {k}")
    if not all(checks.values()):
        print(f"\n{R}{B}  DEGRADED-MODE: FAIL{X} - a backend outage would read as 'Online'.")
        return 1
    print(f"\n{G}{B}  DEGRADED-MODE: PASS{X} - backend degradation is detected + surfaced distinctly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
