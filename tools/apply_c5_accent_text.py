#!/usr/bin/env python3
"""
apply_c5_accent_text.py — C5/APCA final pass: SMALL brand-accent TEXT on dark.

Small orange/blue accent text fails APCA on the navy shell (orange Lc 60 / Lc 59 on a ghost tint,
blue Lc 53 — below the Lc 60 control-label floor). The -light shades clear it. But orange is also used
on LARGE headings + icons that PASS, so a blanket swap would over-brighten the brand. TARGET ONLY the
small-text case: an accent `color:` that co-occurs with a SMALL font-size in the SAME css rule `{...}`
or the SAME inline `style="..."`. Large-heading orange (no small font-size beside it) is left alone.

Swaps to the tokens.css --wh-orange-text / --wh-blue-text (#FDB94A / #5FCCE8), mirroring the existing
--wh-red-text / --wh-violet-text convention. Fills/borders/icons keep the strong brand hues. --check
reports scope.
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

ORANGE = re.compile(r"(?<![-\w])color:\s*(#f7a21b|var\(--wh-orange\)|rgb\(247,\s*162,\s*27\))", re.I)
BLUE   = re.compile(r"(?<![-\w])color:\s*(#29b6d9|var\(--wh-blue\)|rgb\(41,\s*182,\s*217\))", re.I)
# "small" = a sub-16px font in the same block: font-size:0.Nrem | font-size:<=15px | text-xs/sm | text-[..]
SMALL = re.compile(r"font-size:\s*0\.\d+rem|font-size:\s*(?:[0-9]|1[0-5])px|font-size:\s*0\.\d+em"
                   r"|\btext-xs\b|\btext-sm\b|\btext-\[(?:0\.\d+rem|[0-9]px|1[0-5](?:\.\d+)?px|0\.\d+em)\]", re.I)


def _swap_in_block(block: str) -> tuple[str, int]:
    if not SMALL.search(block):
        return block, 0
    n = 0
    def o(m):
        nonlocal n; n += 1; return "color:var(--wh-orange-text)"
    def b(m):
        nonlocal n; n += 1; return "color:var(--wh-blue-text)"
    block = ORANGE.sub(o, block)
    block = BLUE.sub(b, block)
    return block, n


def process(s: str) -> tuple[str, int]:
    total = 0
    # 1) CSS rules  selector { ... }
    def css_rule(m):
        nonlocal total
        body, n = _swap_in_block(m.group(1))
        total += n
        return "{" + body + "}"
    s = re.sub(r"\{([^{}]*)\}", css_rule, s)
    # 2) inline style="..."
    def inline(m):
        nonlocal total
        body, n = _swap_in_block(m.group(1))
        total += n
        return 'style="' + body + '"'
    s = re.sub(r'style="([^"]*)"', inline, s)
    return s, total


def main() -> int:
    check = "--check" in sys.argv
    total = files = 0
    targets = list(ROOT.glob("*.html")) + [ROOT / "components.css"]
    for p in sorted(targets):
        if p.name in EXCLUDE or NONPROD.search(p.name):
            continue
        s = p.read_text(encoding="utf-8", errors="replace")
        out, n = process(s)
        if n:
            total += n; files += 1
            if not check:
                p.write_text(out, encoding="utf-8")
    print(f"C5 accent-text pass: {'would swap' if check else 'swapped'} {total} SMALL orange/blue accent-text decls across {files} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
