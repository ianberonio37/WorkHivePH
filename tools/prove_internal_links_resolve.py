""" -*- coding: utf-8 -*-
Does every internal link land on something? — the directory-URL census (T155, 2026-08-28)

`validate_link_target_existence.py` resolves `.html` targets and `#frag` anchors across the ~30
app pages, and it is good at that. It cannot see the shape the ENTIRE PUBLIC FUNNEL is built
from: `/learn/<slug>/` and `/tools/<slug>/` are DIRECTORY urls served by an inner index.html, and
a href ending in `/` never matches a `.html` suffix test. The 113 public pages are also not link
SOURCES in any gate — so a guide pointing at a renamed sibling has nothing watching it.

★THE NAME `tools/` MEANS TWO THINGS IN THIS REPO AND THE CENSUS MUST KNOW IT. `tools/` holds both
the public calculator pages AND this framework's Python scripts. A first pass here counted "4 of
64 tool directories have no index.html" and was one step from filing four dead pages; the four
were `lib/`, `vendor/`, `psql_probes/` and `__pycache__/`. A directory is only a PAGE if it holds
an index.html — never because it sits under a directory whose name looks public.

WHAT COUNTS AS DEAD: a link whose resolved target is neither a file, nor a directory holding
index.html, nor an in-page fragment. Anything with a template marker (`{`, `$`, `<`) is dynamic
and skipped, and so is every off-site scheme.

USAGE:  python tools/prove_internal_links_resolve.py [--json]
Exit 0 always: a RECORDER. Read via tools/read_recorder_findings.py.
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "internal_link_census_report.json"

# ★THE WORD BOUNDARY IS LOad-BEARING. Without `(?<![\w-])` this pattern matches the tail of
# `data-action="acknowledge"` and reports `acknowledge` as a dead link - it did, 13 times across
# alert-hub and asset-hub, alongside a JS expression caught the same way. An attribute name that
# merely ENDS with a link attribute's name is not that attribute.
HREF = re.compile(r'(?<![\w-])(?:href|action)\s*=\s*["\']([^"\']+)["\']', re.I)

# ★AND THE SCAN MUST READ MARKUP, NOT SOURCE CODE. After the boundary fix three findings survived
# and all three were still the instrument: a COMMENT in alert-hub reading "Persists as
# action='acknowledged'", and audit-log's JS filter state. Neither is a link a user can click.
# Scripts, styles and comments are stripped before the scan - dynamic links are skipped as
# dynamic anyway, and validate_link_target_existence already owns the JS-redirect class.
NOISE = re.compile(r"<script\b.*?</script>|<style\b.*?</style>|<!--.*?-->", re.S | re.I)
# ★"//host/path" IS EXTERNAL — it inherits the page's scheme, and it does not start with http://,
# so a scheme list alone lets it through and the resolver then treats it as a path from the repo
# root. Found by testing this gate against edge cases rather than trusting its green: an injected
# //cdn.example.com/x.png was reported DEAD. No such link exists in the tree today, which is exactly
# why it was worth finding now — the first CDN reference anyone adds would have reddened the board
# for a link that works.
SKIP_SCHEME = ("http://", "https://", "//", "mailto:", "tel:", "javascript:", "data:", "#")
# Directories that live under a public-looking parent but are framework machinery, never pages.
NOT_PAGES = {"__pycache__", "lib", "vendor", "psql_probes", "node_modules"}


def page_files() -> list[Path]:
    """Every HTML page that can CONTAIN a link: app roots + the public directory pages."""
    out = [p for p in ROOT.glob("*.html")]
    for parent in ("learn", "tools"):
        base = ROOT / parent
        if not base.is_dir():
            continue
        for d in sorted(base.iterdir()):
            if not d.is_dir() or d.name in NOT_PAGES:
                continue
            idx = d / "index.html"
            if idx.exists():          # ★a directory is a page only if it serves one
                out.append(idx)
    return out


def resolves(target: str, src: Path) -> bool:
    """True when the target names something the server can actually serve."""
    t = target.split("#", 1)[0].split("?", 1)[0].strip()
    if not t:
        return True                                     # pure fragment/query on self
    p = (ROOT / t.lstrip("/")) if t.startswith("/") else (src.parent / t)
    try:
        p = p.resolve()
    except OSError:
        return False
    if p.is_file():
        return True
    if p.is_dir() and (p / "index.html").exists():      # ★the directory-url shape
        return True
    return False


def main() -> int:
    dead, checked = [], 0
    pages = page_files()
    for src in pages:
        try:
            s = io.open(src, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for raw in set(HREF.findall(NOISE.sub(" ", s))):
            t = raw.strip()
            if t.startswith(SKIP_SCHEME) or any(c in t for c in "{$<"):
                continue
            checked += 1
            if not resolves(t, src):
                dead.append({"page": src.relative_to(ROOT).as_posix(), "href": t})

    rel = sorted({d["page"] for d in dead})
    print("internal-links-resolve - does every internal link land on something?")
    print(f"  {len(pages)} pages | {checked} internal links | {len(dead)} dead on {len(rel)} page(s)\n")
    for d in sorted(dead, key=lambda x: (x["page"], x["href"]))[:60]:
        print(f"  DEAD  {d['page']:<52} -> {d['href']}")
    if len(dead) > 60:
        print(f"  ... and {len(dead) - 60} more (see {REPORT.name})")

    tmp = REPORT.with_suffix(".json.tmp")
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(
        json.dumps({"pages": len(pages), "links_checked": checked, "dead": dead},
                   indent=2, ensure_ascii=False))
    tmp.replace(REPORT)
    print(f"\n  wrote {REPORT.name}")
    # ★A GATE, NOT A RECORDER - because the tree is genuinely clean and the zero is PROVEN.
    # Three dead links (a directory url, a relative directory, a .html file) injected into a learn
    # page were all three caught, and removing them returned the count to zero. A prover that
    # cannot go red is a permanent false green; this one can, so it locks the class at zero
    # instead of merely describing it.
    if dead:
        print(f"  FAIL: {len(dead)} internal link(s) resolve to nothing.")
        return 1
    print("  PASS: every internal link resolves to a file or a directory that serves an index.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
