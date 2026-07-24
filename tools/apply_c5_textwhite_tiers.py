#!/usr/bin/env python3
"""
apply_c5_textwhite_tiers.py — the SECOND half of the C5 (APCA) fix: the Tailwind text-white utility
tiers. apply_c5_apca_textlift.py handled inline `color:rgba(...)` + components.css + utils.js, but the
DOMINANT muted-text source is the `text-white/NN` UTILITY CLASSES (wh-tw.css defines them in modern
space syntax `rgb(255 255 255 / 0.6)`, which the rgba-comma regex never matched). 731 usages.

APCA (validated) on the navy shell: text-white/45..75 ALL fail body Lc 75 (Lc 35-71); only /80 (Lc 77)
and /85 (Lc 84) clear it. So remap the failing tiers to the two APCA-safe tiers that ALREADY EXIST in
wh-tw.css (no new utilities, survives a wh-tw.css regeneration, preserves the class-name contract):
    text-white/45,50,55,60  -> text-white/80   (the "dim" muted tier, Lc 77)
    text-white/65,70,75     -> text-white/85   (the "medium" muted tier, Lc 84)

EXCLUDES hover:/focus: variants (a `(?<!:)` lookbehind) — hover/focus text is transient and not graded
by C5, and keeping the relative brighten-on-hover intact avoids a no-op hover. --check reports scope.
"""
from __future__ import annotations
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE = {"architecture.html", "design-system.html", "symbol-gallery.html", "validator-catalog.html",
           "llm-observability.html", "agentic-rag-observability.html", "ai-quality.html", "status.html",
           "offline-fallback.html", "promo-poster.html", "resume.html", "platform-health.html",
           "engineering-design-test.html"}
NONPROD = re.compile(r"backup|\.bak\b|-test\.|\.test\.|\.old\b|\.orig\b|copy", re.I)

# not preceded by ':' (so hover:/focus:/group-hover: variants are left alone), not preceded by a word char.
DIM = re.compile(r"(?<![:\w])text-white/(?:45|50|55|60)(?![\d])")
MED = re.compile(r"(?<![:\w])text-white/(?:65|70|75)(?![\d])")


def main() -> int:
    check = "--check" in sys.argv
    total = files = 0
    for p in sorted(ROOT.glob("*.html")):
        if p.name in EXCLUDE or NONPROD.search(p.name):
            continue
        s = p.read_text(encoding="utf-8", errors="replace")
        n = len(DIM.findall(s)) + len(MED.findall(s))
        if not n:
            continue
        total += n
        files += 1
        if not check:
            s = DIM.sub("text-white/80", s)
            s = MED.sub("text-white/85", s)
            p.write_text(s, encoding="utf-8")
    print(f"C5 text-white tier remap: {'would remap' if check else 'remapped'} {total} usages across {files} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
