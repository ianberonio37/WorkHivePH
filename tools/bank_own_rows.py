#!/usr/bin/env python3
"""bank_own_rows.py - bank OWN rows on the receipt of the prover their lens names (2026-11-02).

The OWN wave's public-page lenses had provers and no banker, so 391 rows stayed specced while the provers ran:
  anchor  "browser Back: anchor jumps do not pollute history"   tools/prove_anchor_back.mjs -> anchor_back_report.json
          after the in-page jumps (contents list, FAQ, skip link), ONE Back leaves the page - at phone-390 and desktop-1280
  grow    "text grows (200% zoom + text spacing)"               tools/prove_text_grows.mjs  -> text_grows_report.json
          WCAG 1.4.4 + 1.4.12: nothing scrolls sideways, clips, or loses a control that was there before
  forced  "forced colours"                                       (same prover, the forced ask)
          forced-colors active: no control loses its ink, no focus ring is erased
A row closes only when its page's reading passed at BOTH widths, the reading was taken within MAX_AGE_H, and the gate
that holds the lens is registered. A failing or missing page is left as it is and printed with the reason.

    python tools/bank_own_rows.py --lens anchor|grow|forced [--dry]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import bank_sl_walk as bsw  # noqa: E402

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

MAX_AGE_H = 6
LENSES = {
    "anchor": {"lens": "browser Back", "ask": "anchor jumps do not pollute history", "report": "anchor_back_report.json",
               "prover": "tools/prove_anchor_back.mjs", "gate": "own_anchor_back", "key": None,
               "says": "after its in-page jumps (contents list, FAQ, skip link) one press of Back left the page for the "
                       "front page it was reached from, and each jump still landed with focus on its target"},
    "grow": {"lens": "text grows / colours taken away", "ask": "text grows (200% zoom + text spacing)",
             "report": "text_grows_report.json", "prover": "tools/prove_text_grows.mjs", "gate": "own_text_grows", "key": "grow",
             "says": "with WCAG 1.4.12 text spacing and the text at 200% (desktop: 640x400 CSS viewport; phone: every "
                     "font-size doubled at 390) nothing scrolls sideways, nothing is clipped across or down, and every "
                     "control offered before is still offered - each finding differential on one page and one load"},
    "forced": {"lens": "text grows / colours taken away", "ask": "forced colours", "report": "text_grows_report.json",
               "prover": "tools/prove_text_grows.mjs", "gate": "own_text_grows", "key": "forced",
               "says": "under forced-colors (High Contrast) every control that had ink still has ink and every focus "
                       "ring that showed still shows - read from screenshots, since the forced palette is applied at paint"},
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lens", choices=sorted(LENSES), required=True)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    L = LENSES[a.lens]
    checks = (ROOT / "run_platform_checks.py").read_text(encoding="utf-8")
    if f'"{L["gate"]}"' not in checks:
        print(f"refused: gate {L['gate']} is not registered - a row is never banked on a gate that does not exist")
        return 1
    rep_path = ROOT / L["report"]
    if not rep_path.exists():
        print(f"refused: no {L['report']} - run node {L['prover']}")
        return 1
    rep = json.loads(rep_path.read_text(encoding="utf-8"))
    reg = bsw._load_registry()
    rows = [t for t in reg["trajectories"] if t.get("wave") == "OWN" and (t.get("own") or {}).get("lens") == L["lens"]
            and (t.get("own") or {}).get("ask") == L["ask"] and t.get("status") not in ("locked", "locking", "descoped")]
    now = datetime.now(timezone.utc)
    today = date.today().isoformat()
    banked, left = [], []
    for t in rows:
        page = t["own"]["page"]
        entry = (rep.get("pages") or {}).get(page)
        reading = (entry or {}).get(L["key"]) if L["key"] else entry
        if not reading:
            left.append(f"{t['id']} {page}: not walked - run node {L['prover']} --page {page}")
            continue
        ran = reading.get("ran") or rep.get("generated")
        age_h = (now - datetime.fromisoformat(str(ran).replace("Z", "+00:00"))).total_seconds() / 3600
        if age_h > MAX_AGE_H:
            left.append(f"{t['id']} {page}: read {age_h:.1f} h ago (limit {MAX_AGE_H}) - re-walk it")
            continue
        if reading.get("pass") is not True:
            bad = [r.get("vp") for r in reading.get("runs", []) if r.get("ok") is not True or r.get("shape") not in (None, "LEFT", "NO ANCHORS")]
            left.append(f"{t['id']} {page}: not proven ({', '.join(str(b) for b in bad) or 'ungraded'})")
            continue
        vps = ", ".join(str(r.get("vp")) for r in reading.get("runs", []))
        basis = (f"[{today}] pct -> {{pct}}. WALKED: {page} ({vps}) through {L['prover']} (receipt {L['report']}, read "
                 f"{str(ran)[:19]}Z): {L['says']}. HELD BY: gate {L['gate']}.")
        if not a.dry:
            bsw._bank(reg, t["id"], basis, [L["gate"]])
        banked.append(t["id"])
    if banked and not a.dry:
        bsw._write_registry(reg)
    for line in left[:40]:
        print("  left open: " + line)
    if len(left) > 40:
        print(f"  ... and {len(left) - 40} more")
    print(f"{'would bank' if a.dry else 'banked'} {len(banked)} OWN {a.lens} row(s); {len(left)} left open")
    return 0


if __name__ == "__main__":
    sys.exit(main())
