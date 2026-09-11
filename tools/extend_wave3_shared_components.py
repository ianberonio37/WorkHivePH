#!/usr/bin/env python3
"""extend_wave3_shared_components.py — seed the shared pieces the prover walks and the seeder capped out.

★A CAP IN THE SEEDER IS A CAP ON THE WAVE, AND THE PROVER DID NOT KNOW ABOUT IT. `_shared_components()` ends
with `(never + chrome)[:14]` — an arbitrary 14 — while `tools/prove_shared_components.mjs` carries a declared
CONTRACT for **19** pieces and walks every one of them. So the wave banked 27 rows and reported
**20 verdicts that matched no seeded row**: real evidence about `nav-hub.js` (loaded by 31 pages),
`device-fingerprint.js` (33), `companion-launcher.js` (29), `button-lock.js` and `impact-preview.js`, with
nowhere to be written down.

Rule ★×16 says one seeder decides a wave's size and the gate derives its expected ids from that seeder's
plan — so this does not hand-add rows behind the seeder's back. `plan()` REPLAYS whatever carries the W3
prefix once any W3 row exists, which is exactly what makes an explicit, recorded extension safe: the rows
below become part of the plan the moment they are written, and the gate reads them like any other.

  python tools/extend_wave3_shared_components.py --check
  python tools/extend_wave3_shared_components.py --apply
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "trajectory_registry.json"
PREFIX = "W3"

# the same four lenses the seeder writes for every shared piece, in the same words
SC_LENSES = [
    ("U", "This shared piece says the same thing on every page that carries it", ["F"]),
    ("F", "This shared piece does its job on every page that carries it, not only the one it was written for", ["F", "D"]),
    ("A", "This shared piece holds up on a phone, offline, and on a wall display", ["H", "F"]),
    ("I", "This shared piece never shows one person another person's state", ["S", "F"]),
]
STORY = ("{js}: walked on three host pages (phone, desktop, wall display), because shared chrome is "
         "graded once and styled before paint")


def prover_roster() -> list[str]:
    """The pieces the prover actually declares a contract for — the honest roster."""
    src = (ROOT / "tools" / "prove_shared_components.mjs").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"const CONTRACT\s*=\s*\{(.*?)\n\};", src, re.S)
    body = m.group(1) if m else src
    return sorted(set(re.findall(r"['\"]([a-z0-9-]+\.js)['\"]\s*:", body)))


def main() -> int:
    apply = "--apply" in sys.argv
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = reg["trajectories"]
    seeded = {(t.get("title") or "").rsplit(" - ", 1)[-1].strip()
              for t in rows if t.get("wave") == f"{PREFIX}-SC"}
    walked = prover_roster()
    missing = [j for j in walked if j not in seeded]

    print(f"shared pieces the prover walks: {len(walked)}")
    print(f"  already seeded: {len(seeded & set(walked))}")
    print(f"  never seeded:   {len(missing)} -> {missing}")
    if not missing:
        print("  nothing to extend")
        return 0
    print(f"  would add {len(missing) * len(SC_LENSES)} row(s)")

    have = {t["id"] for t in rows}
    nxt = max((int(t["id"][len(PREFIX):]) for t in rows
               if t["id"].startswith(PREFIX) and t["id"][len(PREFIX):].isdigit()), default=1000)
    added = []
    for js in missing:
        for dim, lens, layers in SC_LENSES:
            nxt += 1
            while f"{PREFIX}{nxt}" in have:
                nxt += 1
            rid = f"{PREFIX}{nxt}"
            have.add(rid)
            added.append({
                "id": rid, "status": "specced", "pct": 5, "wave": f"{PREFIX}-SC",
                "title": f"{lens} - {js}", "pages": [], "layers": list(layers), "ufai": [dim],
                "persona": "any", "device": "phone-390", "entry": "hub-nav", "framing": "person",
                "story": STORY.format(js=js),
            })
    for a in added[:4]:
        print(f"     {a['id']}  {a['ufai'][0]}  {a['title'][-40:]}")

    if not apply:
        print("\n  --check only; re-run with --apply to write them")
        return 0

    rows.extend(added)
    reg["updated"] = date.today().isoformat()
    tmp = REGISTRY.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(reg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, REGISTRY)
    print(f"\n  {len(added)} row(s) written")

    # each new trajectory owes a critic row, exactly as the seeder gives its own
    cs = ROOT / "tools" / "critic_seed_missing.py"
    if cs.exists():
        p = subprocess.run([sys.executable, str(cs)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        print("  critic:", (p.stdout or p.stderr).strip().splitlines()[-1][:100] if (p.stdout or p.stderr) else "")
    for script in ("update_trajectory_scoreboard.py", "validate_trajectory_registry.py"):
        p = subprocess.run([sys.executable, str(ROOT / "tools" / script)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        out = (p.stdout or p.stderr).strip().splitlines()
        print(f"  {script}: {out[-1][:96] if out else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
