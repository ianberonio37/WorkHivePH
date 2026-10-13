"""sync_ca_crew_words.py - write THE crew vocabulary (tools/ca_crew_words.json) into the three CA readers (2026-10-09).

The CA lens counts "the crew's own words" on a page. Its list lived as three hand-copied array literals that had already
drifted (the LX walker had dropped 'ptw'; the W4 copies still carried 'philippine', 'pinoy', 'barangay'), and none knew
a maintenance trade: the skill matrix - Mechanical, Electrical, Instrumentation, MV Switchgear - read as two crew words.
One JSON now holds the list; this writes it into each reader's literal.

  python tools/sync_ca_crew_words.py           # write the list into every reader
  python tools/sync_ca_crew_words.py --check   # exit 1 if any reader's list differs from the JSON (gate)
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tools" / "ca_crew_words.json"
TARGETS = [
    (ROOT / "tools" / "lx_walk.body.js", "CREW"),
    (ROOT / "tools" / "w4_action_walk.body.js", "CA_CREW"),
    (ROOT / "tools" / "prove_w4_layer_ca.mjs", "CREW"),
]


def literal(words: list[str]) -> str:
    return "[" + ", ".join("'" + w.replace("\\", "\\\\").replace("'", "\\'") + "'" for w in words) + "]"


def main() -> int:
    words = json.loads(SRC.read_text(encoding="utf-8"))["words"]
    want = literal(words)
    check = "--check" in sys.argv
    drift = []
    for path, name in TARGETS:
        text = io.open(path, encoding="utf-8", newline="").read()
        rx = re.compile(r"(const " + name + r" = )\[[^\]]*\];")
        hits = rx.findall(text)
        if len(hits) != 1:
            drift.append(f"{path.name}: expected one `const {name} = [...];`, found {len(hits)}")
            continue
        current = rx.search(text).group(0)
        if current == f"const {name} = {want};":
            continue
        if check:
            drift.append(f"{path.name}: its {name} list differs from tools/ca_crew_words.json")
        else:
            text = rx.sub(lambda m: m.group(1) + want + ";", text)
            io.open(path, "w", encoding="utf-8", newline="").write(text)
            print(f"wrote {len(words)} words into {path.name}")
    if drift:
        for d in drift:
            print("FAIL ca-crew-words -", d)
        return 1
    print(f"PASS ca-crew-words - {len(TARGETS)} readers carry the {len(words)} words of tools/ca_crew_words.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
