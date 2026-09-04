#!/usr/bin/env python3
"""The wave-close queue, GENERATED from the trajectory registry's own basis lines.

Every advanced trajectory's basis ends with its 'Remaining:' items — the scattered
wave-close backlog. This extracts them into one regenerable report so the close
session works a LIST, not 89 prose paragraphs. Never hand-edited; re-run after
ledger updates.

Usage: python tools/extract_wave_close_queue.py   -> WAVE_CLOSE_QUEUE.md (repo root)
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "WAVE_CLOSE_QUEUE.md"


def main():
    r = json.loads((ROOT / "trajectory_registry.json").read_text(encoding="utf-8"))
    items = []
    for t in r["trajectories"]:
        b = t.get("basis") or ""
        m = re.search(r"Remaining[^:]*:\s*(.+?)(?:\(wave close[^)]*\)\.?|$)", b, re.S)
        if m and t["pct"] > 5:
            rem = re.sub(r"\s+", " ", m.group(1)).strip(" .-")
            if rem:
                items.append((t["id"], int(t["pct"]), rem))
    lines = [
        "# Wave-Close Queue (GENERATED — do not hand-edit)",
        "",
        f"Regenerate: `python tools/extract_wave_close_queue.py` · {len(items)} trajectories carry remainders.",
        "Each row is that trajectory's own 'Remaining:' line from trajectory_registry.json.",
        "",
        "| T | pct | remaining |",
        "|---|-----|-----------|",
    ]
    for tid, pct, rem in sorted(items, key=lambda x: int(x[0][1:])):
        lines.append(f"| {tid} | {pct} | {rem.replace('|', '/')} |")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT.name}: {len(items)} rows")


if __name__ == "__main__":
    main()
