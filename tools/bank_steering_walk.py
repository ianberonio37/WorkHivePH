"""bank_steering_walk.py - bank the BRH-AP rows from the companion steering walk and its teeth (2026-10-30).

A row is banked only when BOTH reports are fresh (3 h) and both speak for it:
  companion_steering_walk.json        - the walk passed at phone-390 AND desktop-1280 (nothing dead sent, the reply on
                                         screen, the page action kept, the moved rule stated by the real gateway)
  companion_steering_walk_teeth.json  - the same walk against voice-handler.js at 69268f24~1 reproduced the defect: the
                                         row's instruction rode in context.platform_prompt, which no server reads. A
                                         'never' row records what the old file did - its condition read a field its
                                         detector never returned, so it built nothing.
Anything else is reported and left open.

  python tools/bank_steering_walk.py [--dry]
"""
from __future__ import annotations

import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import bank_sl_walk as bsw  # noqa: E402

WALK, TEETH = ROOT / "companion_steering_walk.json", ROOT / "companion_steering_walk_teeth.json"
FRESH_S = 3 * 3600
# why a 'never' row could not reproduce - read from the old file's own condition (69268f24~1)
NEVER = {
    "BRH714": "its condition read _sc.markers, and _scrubPii returns { text, scrubs }",
    "BRH718": "its condition read _susp.kind, and _detectSuspiciousActivity returns a bare string",
    "BRH720": "its condition read _mem.level, and _checkMemoryPressure returns { pressure, reason }",
}


def _load(p: Path) -> dict | None:
    if not p.exists():
        return None
    d = json.load(io.open(p, encoding="utf-8"))
    ran = datetime.fromisoformat(d["ran"].replace("Z", "+00:00"))
    if (datetime.now(timezone.utc) - ran).total_seconds() > FRESH_S:
        print(f"  {p.name} is stale ({d['ran']}) - re-run the walk")
        return None
    return d


def main() -> int:
    dry = "--dry" in sys.argv
    walk, teeth = _load(WALK), _load(TEETH)
    if not walk or not teeth or walk.get("teeth") or not teeth.get("teeth"):
        print("need a fresh walk and a fresh teeth run")
        return 1
    by = {}
    for r in walk["results"]:
        by.setdefault(r["id"], {})[r["viewport"]] = r
    tby = {}
    for r in teeth["results"]:
        tby.setdefault(r["id"], {})[r["viewport"]] = r
    reg = bsw._load_registry()
    banked, left = [], []
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for rid, vps in by.items():
        t = tby.get(rid, {})
        ok = all(vps.get(v, {}).get("ok") for v in ("phone-390", "desktop-1280"))
        tok = all(t.get(v, {}).get("ok") for v in ("phone-390", "desktop-1280"))
        if not ok or not tok:
            why = [f"{v}: {x.get('why')}" for v, x in {**vps}.items() if not x.get("ok")]
            why += [f"teeth {v}: {x.get('why')}" for v, x in t.items() if not x.get("ok")]
            left.append((rid, "; ".join(why) or "a viewport is missing"))
            continue
        r = vps["phone-390"]
        label, said, kind = r["label"], r.get("said") or [], r.get("kind")
        trigger = said[-1] if said else "the trigger"
        lead = (" after '" + "', '".join(said[:-1]) + "'") if len(said) > 1 else ""
        parts = [f"[{stamp}] LOCKING pct -> {{pct}}. Measured live - tools/prove_companion_steering_walk.mjs walked the voice "
                 f"companion as a signed-in worker on index.html at phone-390 and desktop-1280 (service worker blocked, every "
                 f"table write answered locally): said '{trigger}'{lead}; the voice-journal request carried no '{label} —' "
                 f"instruction and no context.platform_prompt, and the reply reached the screen at both viewports"]
        if r.get("action"):
            parts.append(f"the page action stayed: {r['action']}")
        if kind == "moved":
            st = vps["phone-390"].get("steering")
            if rid == "BRH712":
                # the gateway reads ITS clock, not the page's: outside 22:00-06:00 Manila it must NOT state the rule
                parts.append(f"the REAL local gateway reads its own clock - at the walk's hour (outside 22:00-06:00 Manila) it "
                             f"answered steering {json.dumps(st)} and correctly did not state quiet_hours; tools/prove_turn_steering.py "
                             f"at 02:53 Manila (2026-10-26T18:53Z) got ['loto', 'quiet_hours', 'shape_data']")
            else:
                parts.append(("the REAL local gateway stated it, its steering " + json.dumps(st)) if st is not None
                             else "the rule is stated by voice-journal-agent's own prompt")
        tr = t["phone-390"]
        if kind == "never":
            parts.append(f"Teeth (the same walk against voice-handler.js at 69268f24~1): the old file sent no '{label} —' - "
                         f"{NEVER.get(rid, 'its condition could not be met')}, so the instruction was never even built: dead "
                         f"twice, and removed with its detector")
        else:
            parts.append(f"Teeth (the same walk against voice-handler.js at 69268f24~1): '{label} —' rode in "
                         f"context.platform_prompt, which no server reads - the reproduction, on demand, at both viewports")
        parts.append("Gate companion-steering-walk (with turn-steering and the companion validators via tools/steering_moved.py).")
        basis = "; ".join(parts[:-1]) + ". " + parts[-1]
        if not dry:
            bsw._bank(reg, rid, basis, ["companion-steering-walk"])
        banked.append(rid)
    if not dry and banked:
        bsw._write_registry(reg)
    for rid, why in left:
        print(f"  OPEN {rid}: {why[:220]}")
    print(f"{'would bank' if dry else 'banked'} {len(banked)} BRH-AP row(s); {len(left)} left open")
    return 0


if __name__ == "__main__":
    sys.exit(main())
