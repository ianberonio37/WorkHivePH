"""
validate_md_twins.py — the markdown twins must never drift from their pages.
============================================================================
Every public page ships a clean markdown twin at `<page>.md` (llms.txt convention,
built by tools/build_md_twins.py). Each twin records the sha256 of the HTML it was
generated from; this gate fails when a page changed and its twin did not.

WHY A GATE AND NOT A README LINE: a stale twin is worse than no twin. An agent that
fetches the markdown gets a confident, well-formed, WRONG version of the page — the
same failure class as the knowledge substrate drifting from its sources, which is why
this uses the identical source_sha discipline.

FIX ON FAIL:  python tools/build_md_twins.py

CLI:
    python tools/validate_md_twins.py
    python tools/validate_md_twins.py --self-test
Exit 0 = every twin current (or none exist yet), 1 = drift.
"""
from __future__ import annotations

import sys
import hashlib
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from build_md_twins import _pages, _twin_path, SHA_MARK, GENERATOR_VERSION  # noqa: E402


def audit() -> tuple[list, list, int]:
    missing, drifted, ok = [], [], 0
    for page, _url in _pages():
        twin = _twin_path(page)
        rel = page.relative_to(ROOT).as_posix()
        if not twin.exists():
            missing.append(rel)
            continue
        src = page.read_text(encoding="utf-8", errors="replace")
        sha = hashlib.sha256((src + f"|gen{GENERATOR_VERSION}").encode("utf-8")).hexdigest()[:16]
        if f"{SHA_MARK} {sha} -->" in twin.read_text(encoding="utf-8", errors="replace"):
            ok += 1
        else:
            drifted.append(rel)
    return missing, drifted, ok


def run() -> int:
    missing, drifted, ok = audit()
    total = ok + len(missing) + len(drifted)
    print("=" * 64)
    print("  MARKDOWN TWINS — llms.txt convention, source_sha anti-drift")
    print("=" * 64)
    if total == 0:
        print("  No public pages resolved — nothing to check.")
        return 0
    print(f"  pages: {total}   current: {ok}   missing: {len(missing)}   drifted: {len(drifted)}")
    for r in missing[:10]:
        print(f"    MISSING  {r}")
    for r in drifted[:10]:
        print(f"    DRIFTED  {r}")
    extra = len(missing) + len(drifted) - 20
    if extra > 0:
        print(f"    ... and {extra} more")
    if missing or drifted:
        print("\n  FIX: python tools/build_md_twins.py")
        return 1
    print("\n  PASS — every page's markdown twin matches its source.")
    return 0


def self_test() -> int:
    import tempfile
    ok = True

    def ck(c, label):
        nonlocal ok
        ok &= bool(c)
        print(f"  {'PASS' if c else 'FAIL'}  {label}")

    from build_md_twins import html_to_md, _twin_path as tp
    html = ("<html><head><meta name='description' content='D'></head><body><article>"
            "<h1>T</h1><p>Hello <strong>world</strong> and <a href='/x/'>link</a>.</p>"
            "<ul><li>one</li><li>two</li></ul>"
            "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"
            "<script>bad()</script><footer>chrome</footer></article></body></html>")
    md = html_to_md(html, "https://workhiveph.com/x/")
    ck(md.startswith("# T"), "title becomes the H1")
    ck("> D" in md, "meta description becomes the blockquote")
    ck("Source: https://workhiveph.com/x/" in md, "source URL recorded")
    ck("**world**" in md, "bold preserved")
    ck("[link](https://workhiveph.com/x/)" in md, "relative link absolutised")
    ck("- one\n- two" in md, "list is tight, not paragraph-per-item")
    ck("| A | B |" in md, "table rendered as a markdown table")
    ck("bad()" not in md and "chrome" not in md, "script and footer chrome stripped")
    ck(tp(Path("a/index.html")).name == "index.html.md", "twin path appends .md per spec")
    print("  self-test", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(self_test() if "--self-test" in sys.argv[1:] else run())
