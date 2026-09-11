#!/usr/bin/env python3
"""critic_seed_missing.py — the critic bank grows with the trajectory registry, from ONE place.

validate_critic_registry.py R3 requires EVERY non-descoped trajectory id to appear in critic_registry.json
exactly once. seed_p_program_catalog.py honours that for the P program by emitting its critic rows in the
same change; the LX (layer-UX) and EX (expansion) seeders did not, so the gate went RED with 1,060 in-scope
trajectories missing from the bank (335 LX + 725 EX, 2026-09-07). This tool is the one seeder both of them
now call at the end of their write, and it is idempotent: it ADDS a pending critic row for every in-scope
trajectory that has none, and never touches a row that exists (the preservation rule must hold on both
sides of a paired write — see feedback_a_preservation_rule_on_one_side_of_a_paired_write).

Every row enters 'pending' — honest: not walked, nothing graded. Rows whose trajectory has no page (the
LX-FN edge-function rows) carry the explicit no_ui_basis R5 requires. The critic cell is derived from the
trajectory's structured device/persona axes in the bank's own vocabulary (`device|persona|browser-ui|operate`);
'any' resolves to the bank's default walk cell (wide-1920|worker) so the walk viewport is never invented.

  python tools/critic_seed_missing.py            add the missing rows (atomic write)
  python tools/critic_seed_missing.py --dry-run  report what would be added
"""
from __future__ import annotations

import io
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CRITIC = ROOT / "critic_registry.json"
TRAJ = ROOT / "trajectory_registry.json"

DEVICE_DEFAULT = "wide-1920"
PERSONA_DEFAULT = "worker"
NARROW = ("narrow-320", "phone-390")


def _cell(t: dict) -> tuple[str, int]:
    cells = t.get("cells") or []
    if cells:
        c = cells[0]
        return c, (390 if any(n in c for n in NARROW) else 1920)
    device = t.get("device") or "any"
    persona = t.get("persona") or "any"
    if device == "any":
        device = DEVICE_DEFAULT
    if persona == "any":
        persona = PERSONA_DEFAULT
    return f"{device}|{persona}|browser-ui|operate", (390 if device in NARROW else 1920)


def build_missing(critic: dict, traj: dict) -> list[dict]:
    seen = {r.get("id") for r in critic.get("rows") or []}
    out = []
    for t in traj.get("trajectories", []):
        if t.get("status") == "descoped" or t["id"] in seen:
            continue
        cell, vp = _cell(t)
        fn = (t.get("functions") or [None])[0]
        row = {
            "id": t["id"], "wave": t.get("wave") or t["id"].rstrip("0123456789"), "status": "pending",
            "pages": list(t.get("pages") or []),
            "cell": cell, "walk_viewport_px": vp,
            "target_source": "critic_seed_missing", "needs_review": False,
            "dims_graded": [], "findings": [],
        }
        if not row["pages"]:
            row["no_ui_basis"] = (f"edge function supabase/functions/{fn} — no UI surface; critiqued against the "
                                  "AI/API dimensions via its contract, not a browser walk") if fn else \
                                 "no UI surface named by the trajectory; critiqued against its contract"
        out.append(row)
    return out


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def seed_missing(dry_run: bool = False) -> int:
    critic = json.loads(io.open(CRITIC, encoding="utf-8").read())
    traj = json.loads(io.open(TRAJ, encoding="utf-8").read())
    missing = build_missing(critic, traj)
    by_wave = Counter(r["wave"] for r in missing)
    if not missing:
        print("critic_seed_missing: every in-scope trajectory already has a critic row - nothing to add")
        return 0
    print(f"critic_seed_missing: {'would add' if dry_run else 'adding'} {len(missing)} pending critic row(s) - "
          + " | ".join(f"{k} {v}" for k, v in sorted(by_wave.items())))
    if dry_run:
        return 0
    critic["rows"] = list(critic["rows"]) + missing
    _atomic_write(CRITIC, json.dumps(critic, indent=2, ensure_ascii=False) + "\n")
    print(f"  wrote {CRITIC.name}: {len(critic['rows'])} rows")
    return 0


if __name__ == "__main__":
    sys.exit(seed_missing(dry_run="--dry-run" in sys.argv))
