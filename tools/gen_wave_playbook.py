#!/usr/bin/env python3
"""gen_wave_playbook.py — generate a critique-wave playbook (walk cards) for any trajectory set.
Usage: python .tmp/gen_wave_playbook.py CW2 T19-T28   (range or comma list: T19,T21,T30)
Cards merge the roadmap spec (Story/Route/Pain probes) with the critic seed's walk targets.
The ROUTE is authoritative for the walk; targets are fix-receipt-ranked hints."""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROADMAP = ROOT / "UFAI_TRAJECTORY_ROADMAP.md"
SEED = ROOT / ".tmp" / "critic_registry.seed.json"
CRITIC = ROOT / "critic_registry.json"


def ids_from(arg: str) -> list[str]:
    m = re.match(r"^T(\d+)-T(\d+)$", arg)
    if m:
        return [f"T{n}" for n in range(int(m.group(1)), int(m.group(2)) + 1)]
    return [x.strip() for x in arg.split(",") if x.strip()]


def main() -> int:
    wave, id_arg = sys.argv[1], sys.argv[2]
    ids = ids_from(id_arg)
    text = io.open(ROADMAP, encoding="utf-8", errors="replace").read()
    src = CRITIC if CRITIC.exists() else SEED
    rows = {r["id"]: r for r in json.loads(io.open(src, encoding="utf-8").read())["rows"]}
    out = [f"# {wave} Playbook — walk cards ({id_arg})\n",
           "Walk protocol: UFAI_CRITIC_DEEPWALK_ROADMAP.md §2. Reap browsers first "
           "(tools/browser_gate_health.py --reap).",
           "★Targets are fix-receipt-ranked hints — the ROUTE is authoritative: walk the Route and "
           "correct the registry row's pages to the route's actual surfaces.\n"]
    for tid in ids:
        r = rows.get(tid)
        m = re.search(rf"^### {tid} — (.+?)$", text, re.M)
        title = m.group(1).strip() if m else (r or {}).get("title", "(expansion arc — spec in registry story field)")
        out.append(f"## {tid} — {title}")
        if r:
            out.append(f"**Targets**: {', '.join(r.get('pages') or [])} · cell `{r.get('cell')}` · "
                       f"{r.get('walk_viewport_px')}px · source {r.get('target_source')}"
                       + (" · NEEDS-REVIEW" if r.get("needs_review") else ""))
        if m:
            block = text[m.end():m.end() + 2600]
            nxt = re.search(r"\n### T\d+ ", block)
            if nxt:
                block = block[:nxt.start()]
            for f in ("Story", "Route", "Pain probes"):
                fm = re.search(rf"\*\*{f}\*\*:?\s*(.+?)(?=\n- \*\*|\n### |\Z)", block, re.S)
                if fm:
                    out.append(f"**{f}**: {re.sub(r'\\s+', ' ', fm.group(1)).strip()[:420]}")
        out.append("")
    dest = ROOT / ".tmp" / f"{wave.lower()}_playbook.md"
    io.open(dest, "w", encoding="utf-8").write("\n".join(out))
    print(f"{dest.name}: {len(ids)} cards")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
