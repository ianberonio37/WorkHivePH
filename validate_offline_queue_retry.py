#!/usr/bin/env python3
"""validate_offline_queue_retry.py - Arc S (Resilience/DR) D-lens cell `queue_retry_strategy`.
================================================================================
A field-worker write queued offline must eventually drain OR be visibly given up
on — never silently stuck forever. The shared offline-queue.js drain() must:
  - track a per-item retry_count,
  - back off between attempts (not hammer on every tick),
  - dead-letter after a max (status='stalled') and skip it in auto-drain,
  - retry periodically (not only on the 'online' event — a backend that recovered
    while we never went offline would otherwise never drain),
  - surface stalled items (whGetQueueDepth reports them) so the worker is warned.

Exit 0 = robust retry/backoff/dead-letter; 1 = naive (stuck-forever) queue. Stdlib, $0.
"""
from __future__ import annotations
import io, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"


def main() -> int:
    print(f"{B}Arc S - offline-queue retry strategy (D-lens){X}")
    print("=" * 60)
    try:
        q = (ROOT / "offline-queue.js").read_text(encoding="utf-8", errors="replace")
    except OSError:
        print(f"  {R}FAIL{X}  offline-queue.js not found"); return 1

    checks = {
        "per-item retry_count tracked":        "retry_count" in q,
        "backoff between attempts":            ("BACKOFF" in q or "backoff" in q) and "_due" in q,
        "dead-letter after max (stalled)":     "MAX_RETRIES" in q and "stalled" in q,
        "periodic retry (not just 'online')":  "setInterval" in q,
        "stalled surfaced in queue depth":     "stalled" in q and "whGetQueueDepth" in q,
    }
    for k, ok in checks.items():
        print(f"  {(G+'PASS'+X) if ok else (R+'FAIL'+X)}  {k}")
    if not all(checks.values()):
        print(f"\n{R}{B}  QUEUE-RETRY: FAIL{X} - naive queue (an item could stick forever).")
        return 1
    print(f"\n{G}{B}  QUEUE-RETRY: PASS{X} - retry + backoff + dead-letter + periodic drain.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
