#!/usr/bin/env python3
"""set_trajectory_next.py — advance the roadmap header's NEXT pointer (the ONLY writer of it).

Ian (2026-09-05): "lock this roadmap with our usual framework — the momentum drive and memento,
with anti-drift percentage completion on the upper header + a pointer on what's next."

The pointer lives in trajectory_registry.json's `next` field (the same SSOT the percentages come
from) and is RENDERED into the roadmap header by update_trajectory_scoreboard.py. It is never
typed into the doc, for the same reason the percentages are not: a hand-typed pointer goes stale
the moment the work moves, and a stale pointer is worse than no pointer — it aims the next
session at a unit that is already finished. Run this at each sub-unit close.

  set_trajectory_next.py "<the next unit>"   set the pointer and regenerate the header
  set_trajectory_next.py --show              print the current pointer
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "trajectory_registry.json"


def main() -> int:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if "--show" in sys.argv or len(sys.argv) < 2:
        print(reg.get("next") or "(unset)")
        return 0
    nxt = " ".join(a for a in sys.argv[1:] if not a.startswith("--")).strip()
    if not nxt:
        print("give the next unit as one argument, e.g.:\n"
              '  python tools/set_trajectory_next.py "P-A walk: render resolves x 18 root pages"')
        return 1
    reg["next"] = nxt
    tmp = REGISTRY.with_suffix(".json.tmp")   # atomic: open(w) truncates before the write
    tmp.write_text(json.dumps(reg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, REGISTRY)
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "update_trajectory_scoreboard.py")],
                       capture_output=True, text=True)
    print(f"NEXT set: {nxt}")
    print((r.stdout or r.stderr).strip())
    return r.returncode


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
