#!/usr/bin/env python3
"""
apply_c5_muted_vars.py — C5/APCA: lift per-page MUTED-TEXT CSS VARIABLES.

Many pages define a LOCAL muted-text token in their <style> (`--muted: rgba(255,255,255,0.6)`,
also 0.55/0.62/0.7/0.4) and use `color: var(--muted)` everywhere. The literal-`color:` fix could not
see these variable DEFINITIONS, so `.sub`/caption text kept failing APCA on those pages (project-
manager 62, inventory 60, etc.). Lifting the DEFINITION fixes every `var(--muted)` usage on the page
at once. Only white/cloud-base muted alphas 0.40-0.79 are lifted to 0.80 (already->=0.80 left alone;
these vars are semantically TEXT colour - used as `color:` - so brightening is the whole point).

Var names covered: --muted, --text-muted, --sub, --dim, --muted-2, --text-dim, --subtle (the muted-
text idioms seen in the pages). Fills/borders use their own tokens, untouched. --check reports scope.
"""
from __future__ import annotations
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE = {"architecture.html", "design-system.html", "symbol-gallery.html", "validator-catalog.html",
           "llm-observability.html", "agentic-rag-observability.html", "ai-quality.html", "status.html",
           "offline-fallback.html", "promo-poster.html", "resume.html", "platform-health.html",
           "engineering-design-test.html"}
NONPROD = re.compile(r"backup|\.bak\b|-test\.|\.test\.|\.old\b|copy", re.I)

VAR_NAMES = r"(?:muted|text-muted|sub|dim|muted-2|text-dim|subtle|muted-text)"
# --<mutedname>: rgba(white|cloud, .40-.79)  -> lift alpha to 0.80. Optional leading zero.
PAT = re.compile(
    r"(--" + VAR_NAMES + r"\s*:\s*rgba\(\s*(?:255\s*,\s*255\s*,\s*255|244\s*,\s*246\s*,\s*250)\s*,\s*)"
    r"(0?\.(?:[47]\d?|5\d?|6\d?))(\s*\))", re.I)


def lift(m: re.Match) -> str:
    a = m.group(2)
    if a.startswith("."):
        a = "0" + a
    try:
        if float(a) >= 0.80:
            return m.group(0)   # already bright enough
    except ValueError:
        return m.group(0)
    return m.group(1) + "0.80" + m.group(3)


def main() -> int:
    check = "--check" in sys.argv
    total = files = 0
    for p in sorted(ROOT.glob("*.html")):
        if p.name in EXCLUDE or NONPROD.search(p.name):
            continue
        s = p.read_text(encoding="utf-8", errors="replace")
        n = len(PAT.findall(s))
        if not n:
            continue
        total += n
        files += 1
        if not check:
            p.write_text(PAT.sub(lift, s), encoding="utf-8")
    print(f"C5 muted-var lift: {'would lift' if check else 'lifted'} {total} muted-text CSS var defs across {files} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
