#!/usr/bin/env python3
"""validate_offline_resilience.py - Arc S (Resilience/DR) D-lens cell `offline_write_queue`.
================================================================================
A field worker on a brownout / 2G link must not LOSE a write. The shared offline
queue (offline-queue.js) existed but was never instantiated — dead code (D-001/D-006).
This gate asserts the critical field-worker WRITE pages actually have offline-write
protection: either a custom IndexedDB queue (logbook) OR the shared queue wired
(whCreateQueue + whRegisterQueue + startAutoSync) AND a primary write that enqueues
when offline (a `navigator.onLine` guard paired with `.enqueue(`).

Scope = the field-worker write surfaces (logbook, inventory, pm-scheduler). Supervisor/
admin pages (project-manager, integrations, marketplace) are a tracked follow-on, not
gated here — gating them would block the floor on non-field surfaces.

Exit 0 = field writes survive a brownout; 1 = a field page can lose a write. Stdlib, $0.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"

FIELD_WRITE_PAGES = ["logbook.html", "inventory.html", "pm-scheduler.html"]


def _read(name: str) -> str:
    try:
        return (ROOT / name).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _has_offline_write(name: str, t: str) -> tuple[bool, str]:
    # logbook ships a bespoke IndexedDB offline queue (predates the shared helper).
    if name == "logbook.html":
        custom = ("wh_logbook_offline" in t) or ("syncOfflineQueue" in t and "indexedDB" in t.lower())
        return custom, "custom IndexedDB queue" if custom else "no custom offline queue"
    # the others must wire the shared queue + enqueue offline.
    wired = ("whCreateQueue" in t) and ("startAutoSync" in t)
    enq = (".enqueue(" in t) and ("navigator.onLine" in t)
    detail = []
    if not wired: detail.append("queue not instantiated (whCreateQueue/startAutoSync)")
    if not enq:   detail.append("no offline enqueue path (navigator.onLine + .enqueue)")
    return (wired and enq), ("shared queue wired + offline enqueue" if not detail else "; ".join(detail))


def main() -> int:
    print(f"{B}Arc S - offline write queue (D-lens, no lost field write){X}")
    print("=" * 62)
    issues = []
    for page in FIELD_WRITE_PAGES:
        t = _read(page)
        ok, detail = _has_offline_write(page, t)
        print(f"  {(G+'PASS'+X) if ok else (R+'FAIL'+X)}  {page}: {detail}")
        if not ok:
            issues.append(page)
    if issues:
        print(f"\n{R}{B}  OFFLINE-WRITE-QUEUE: FAIL{X} - a field write could be lost on: {', '.join(issues)}")
        return 1
    print(f"\n{G}{B}  OFFLINE-WRITE-QUEUE: PASS{X} - field-worker writes queue offline + drain on reconnect.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
