"""
validate_prod_path_leak.py  (L0 — Grounded Sweep, link-destination class)
=========================================================================
Production serves at root (workhiveph.com/learn/, /logbook.html, ...). The
local Flask tester serves everything under /workhive/. A client-side "Local
dev URL bridge" rewrites root-absolute <a href> links to /workhive/<path> AT
RUNTIME when location starts with /workhive/ — but it ONLY touches <a href>.

Therefore ANY committed resource attribute that hardcodes the /workhive/
prefix — <script src>, <link href>, <img src>, <iframe src>, srcset, etc. —
ships BROKEN to production (the asset 404s; the tester hid it). This is the
exact class that shipped the learn-page feedback-FAB leak (37 pages loading
/workhive/wh-feedback-fab.js, dead in prod).

This validator FAILs (exit 1) on any committed /workhive/ inside a resource
attribute. <a href="/workhive/..."> is ALSO flagged: source links must be
root-absolute (/) and let the dev bridge add the prefix at runtime — a
committed /workhive/ href is wrong for prod too. String literals that merely
contain '/workhive/' inside inline <script> (e.g. the bridge itself) are NOT
matched because we only scan src=/href=/srcset= attribute values.

Baseline: 0. Forward-only.

Usage:  python validate_prod_path_leak.py
"""
from __future__ import annotations
import io, re, sys, glob, os
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
SKIP_RE = re.compile(r"(\.backup\d*\.html$|-test\.html$|index-v\d|index-hive-test|index-native-test|symbol-gallery)")

# Match src= / href= / srcset= attribute values that start with /workhive/.
_ATTR_RE = re.compile(r'(?:src|href|srcset)\s*=\s*"(/workhive/[^"]*)"', re.IGNORECASE)


def scan(path: Path) -> list[tuple[int, str]]:
    hits = []
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        for m in _ATTR_RE.finditer(line):
            hits.append((i, m.group(1)))
    return hits


def main() -> int:
    leaks = {}
    for fp in sorted(glob.glob(str(ROOT / "**" / "*.html"), recursive=True)):
        name = os.path.basename(fp)
        if SKIP_RE.search(name):
            continue
        if "node_modules" in fp or "test-data-seeder" in fp:
            continue
        h = scan(Path(fp))
        if h:
            leaks[os.path.relpath(fp, ROOT).replace("\\", "/")] = h

    bar = "=" * 70
    print(bar)
    if leaks:
        total = sum(len(v) for v in leaks.values())
        print(f"\033[91mFAIL\033[0m  prod-path leak: {total} committed /workhive/ resource path(s) "
              f"across {len(leaks)} file(s)")
        print("  These 404 in production (the dev bridge only rewrites <a href>, not src/link).")
        for f, hits in list(leaks.items())[:40]:
            for ln, val in hits[:4]:
                print(f"  - {f}:{ln}  {val}")
        print("  Fix: use a root-relative path (../wh-feedback-fab.js) for assets, or root-absolute")
        print("  '/' for <a href> links (the dev bridge adds /workhive/ locally).")
        print(bar)
        return 1
    print("\033[92mOK\033[0m  No committed /workhive/ resource paths — links are prod-safe.")
    print(bar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
