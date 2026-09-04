#!/usr/bin/env python3
"""someone->you event coverage gate — T108's registry discipline (2026-08-25).

The registry (substrate/reference/someone_to_you_event_registry.json) enumerates every
event where person A's action creates work or attention for person B. The T108 bar:
each event needs a notification path and a tap that lands ON the item; 'none' rows are
the silent-work class to extinguish.

WHAT THIS GATE HOLDS (a forward-only ratchet, not a green demand):
  1. The registry file exists, parses, and every event row carries the required fields
     (event, source, notification, finding) with notification in the declared vocab.
  2. The count of 'none' (silent-work) rows never GROWS past the accepted baseline —
     shipping a new someone->you event without a notification path FAILs here by name.
     Fixing one (none -> badge-only/notified/realtime) tightens the baseline.

Baseline lives inline (SILENT_BASELINE); update it DOWNWARD as silent rows are fixed.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REG = ROOT / "substrate" / "reference" / "someone_to_you_event_registry.json"

# Accepted silent-work rows as of 2026-08-25 (4 at the T108 walk; ALL FOUR silent rows extinguished 2026-08-25 -> 0 (password-reset live-proof deferred to the close)).
# This may only DECREASE. Raising it requires deleting this gate's reason to exist.
SILENT_BASELINE = 0


def main() -> int:
    if not REG.exists():
        print(f"FAIL someone-to-you — registry missing: {REG}")
        return 1
    try:
        d = json.loads(REG.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"FAIL someone-to-you — registry unparseable: {e}")
        return 1
    vocab = set((d.get("_meta") or {}).get("status_vocab") or [])
    events = d.get("events") or []
    if not events or not vocab:
        print("FAIL someone-to-you — registry has no events or no status vocab")
        return 1
    bad = []
    silent = []
    for ev in events:
        missing = [k for k in ("event", "source", "notification", "finding") if not ev.get(k)]
        if missing:
            bad.append(f"{ev.get('event', '<unnamed>')}: missing {','.join(missing)}")
            continue
        if ev["notification"] not in vocab:
            bad.append(f"{ev['event']}: notification '{ev['notification']}' not in vocab")
            continue
        if ev["notification"] == "none":
            silent.append(ev["event"])
    if bad:
        print("FAIL someone-to-you — malformed rows:")
        for b in bad:
            print(f"  {b}")
        return 1
    if len(silent) > SILENT_BASELINE:
        print(f"FAIL someone-to-you — silent-work rows grew: {len(silent)} > baseline {SILENT_BASELINE}")
        for s in silent:
            print(f"  none: {s}")
        return 1
    if len(silent) < SILENT_BASELINE:
        print(f"PASS someone-to-you — {len(events)} events; silent rows IMPROVED to {len(silent)} "
              f"(< baseline {SILENT_BASELINE}) — ratchet SILENT_BASELINE down to {len(silent)}.")
        return 0
    print(f"PASS someone-to-you — {len(events)} events enumerated; {len(silent)} silent rows (== baseline; "
          f"the class to extinguish: {', '.join(silent)}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
