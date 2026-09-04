#!/usr/bin/env python3
"""update_critic_scoreboard.py — regenerate the UFAI Critic Deepwalk roadmap's scoreboard block
from critic_registry.json (the SSOT). Mirrors update_trajectory_scoreboard.py: the header is
GENERATED, never hand-typed, and can DROP (a demoted critique lowers it — that is the honesty
feature). pct per status: pending 0 · walked 40 · critiqued 70 · improving 85 · locked 100
(a critique's value is the walk + the grade; the last 30% is the improvement landing + its lock).
Writes the block between the markers in UFAI_CRITIC_DEEPWALK_ROADMAP.md; --stdout prints only."""
from __future__ import annotations

import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CRITIC = ROOT / "critic_registry.json"
CRITIC_STAGED = ROOT / ".tmp" / "critic_registry.seed.json"
DOC = ROOT / "UFAI_CRITIC_DEEPWALK_ROADMAP.md"
DOC_STAGED = ROOT / ".tmp" / "UFAI_CRITIC_DEEPWALK_ROADMAP.md"
MARK_A = "<!-- critic-scoreboard:begin (GENERATED - edit critic_registry.json, not this block) -->"
MARK_B = "<!-- critic-scoreboard:end -->"
PCT = {"pending": 0, "walked": 40, "critiqued": 70, "improving": 85, "locked": 100}


def block(critic: dict) -> str:
    rows = critic["rows"]
    st = Counter(r["status"] for r in rows)
    overall = sum(PCT[r["status"]] for r in rows) / max(len(rows), 1)
    waves = sorted({r["wave"] for r in rows}, key=lambda w: (len(w), w))
    per_wave = []
    for w in waves:
        wr = [r for r in rows if r["wave"] == w]
        pct = sum(PCT[r["status"]] for r in wr) / len(wr)
        per_wave.append(f"{w} {pct:.0f}%")
    sev = Counter(f"S{f['severity']}" for r in rows for f in r.get("findings") or [])
    open_major = sum(1 for r in rows for f in r.get("findings") or []
                    if f["severity"] >= 3 and not f.get("resolved"))
    lines = [
        MARK_A,
        f"**CRITIC PROGRAM: {overall:.1f}% overall · {len(rows)} in-scope trajectories · "
        + " · ".join(f"{k} {st[k]}" for k in ("pending", "walked", "critiqued", "improving", "locked") if st.get(k))
        + f" — registry critic_registry.json (updated {critic.get('updated')}, rubric {critic.get('rubric_sha')}).**",
        f"Findings: {sum(sev.values())} total ({', '.join(f'{k} {v}' for k, v in sorted(sev.items(), reverse=True)) or 'none yet'}) · open Major+ {open_major}.",
        "Per-wave: " + " · ".join(per_wave),
        MARK_B,
    ]
    return "\n".join(lines)


def main() -> int:
    src = CRITIC if CRITIC.exists() else CRITIC_STAGED
    critic = json.loads(io.open(src, encoding="utf-8").read())
    b = block(critic)
    if "--stdout" in sys.argv:
        print(b)
        return 0
    doc = DOC if DOC.exists() else DOC_STAGED
    text = io.open(doc, encoding="utf-8").read()
    if MARK_A not in text or MARK_B not in text:
        print(f"FAIL - scoreboard markers missing in {doc.name}")
        return 1
    new = re.sub(re.escape(MARK_A) + r".*?" + re.escape(MARK_B), b, text, flags=re.S)
    tmp = doc.with_suffix(".tmp")
    io.open(tmp, "w", encoding="utf-8").write(new)
    tmp.replace(doc)
    print(f"scoreboard regenerated in {doc.name} from {src.name}")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
