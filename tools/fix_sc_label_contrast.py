"""
fix_sc_label_contrast.py — Grounded Sweep (axe-core, platform-wide).
====================================================================
Live axe-core flagged the shared calm-dashboard KPI label `.sc-label` at
color:rgba(255,255,255,0.4) -> 3.72:1 on the dark card bg, below the 4.5:1 AA
floor (the label is 0.65rem bold uppercase = normal text, not "large"). It is
copy-pasted into ~18 dashboard pages, so every dashboard inherits the miss.

Fix: bump the alpha INSIDE the `.sc-label { ... }` rule only (0.4 -> 0.6,
~5.4:1). Scoped regex so other rgba(255,255,255,0.4) uses are untouched.
Idempotent + re-runnable. Pages using `color:var(--muted)` are left alone
(different mechanism).

Usage:  python tools/fix_sc_label_contrast.py [--check]
"""
from __future__ import annotations
import io, re, sys, glob, os
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SKIP = re.compile(r"(\.backup\d*\.html$|-test\.html$|index-v\d|index-hive-test|index-native-test|symbol-gallery)")
# only the color alpha inside a .sc-label { ... } rule
_RE = re.compile(r'(\.sc-label\s*\{[^}]*?color:\s*rgba\(255,\s*255,\s*255,\s*)0?\.4(\s*\)[^}]*?\})', re.IGNORECASE)


def main() -> int:
    check = "--check" in sys.argv
    changed = []
    for fp in sorted(glob.glob(str(ROOT / "**" / "*.html"), recursive=True)):
        if "node_modules" in fp or SKIP.search(os.path.basename(fp)):
            continue
        p = Path(fp)
        text = p.read_text(encoding="utf-8", errors="replace")
        new, n = _RE.subn(r'\g<1>0.6\g<2>', text)
        if n and new != text:
            changed.append((os.path.relpath(fp, ROOT).replace("\\", "/"), n))
            if not check:
                p.write_text(new, encoding="utf-8")
    verb = "WOULD fix" if check else "fixed"
    print(f".sc-label contrast: {verb} {sum(n for _,n in changed)} rule(s) across {len(changed)} file(s).")
    for rel, n in changed:
        print(f"  {rel}")
    return 1 if (check and changed) else 0


if __name__ == "__main__":
    sys.exit(main())
