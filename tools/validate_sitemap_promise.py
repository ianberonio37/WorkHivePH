#!/usr/bin/env python3
"""sitemap-promise - the sitemap says what the pages say (Wave KA, 2026-10-26).

Measured on 2026-10-26: 120 URLs, 115 promising <changefreq>monthly</changefreq>, while 109 <lastmod> values read
2026-05-17/18 or 2026-08-05 - typed as `today` by scaffold_article.py at scaffold time and never derived again. The
pages themselves declared other dates in their JSON-LD (42 articles: 2026-08-24). The sitemap told the crawler one date
and the page another, and promised a cadence the dates contradicted.

TWO CONTRACTS:
  lastmod     for every URL whose page declares a dateModified, <lastmod> equals it (refresh_public_page.py
              --sync-sitemap derives it; --stamp moves both together)
  changefreq  matches the kind's window (pillar/comparison 30d and article 90d -> monthly; calculator 365d -> yearly);
              root pages keep whatever they declare

    python tools/validate_sitemap_promise.py
    python tools/validate_sitemap_promise.py --self-test
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))


def findings() -> tuple[list[str], int]:
    import content_freshness_gate as cfg
    from refresh_public_page import CHANGEFREQ_FOR_WINDOW, SITEMAP, local_of, sitemap_entries
    out, checked = [], 0
    for e in sitemap_entries(SITEMAP.read_text(encoding="utf-8")):
        local = local_of(e["loc"])
        p = ROOT / local
        if not p.exists():
            out.append(f"{local}: the sitemap names a page that is not in the project")
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        dm = cfg._date_of(text)
        checked += 1
        if dm and e["lastmod"] and dm.isoformat() != e["lastmod"]:
            out.append(f"{local}: <lastmod> {e['lastmod']} but the page declares dateModified {dm}")
        if (local.startswith("learn/") or local.startswith("tools/")) and local not in ("learn/index.html", "tools/index.html"):
            slug = local.split("/")[-2]
            kind = cfg._classify(slug, p)
            want = CHANGEFREQ_FOR_WINDOW.get(cfg.TARGET_DAYS.get(kind, 0))
            if want and e["changefreq"] and e["changefreq"] != want:
                out.append(f"{local}: <changefreq>{e['changefreq']}</changefreq> but a {kind} ({cfg.TARGET_DAYS.get(kind)}d) is {want}")
    return out, checked


def self_test() -> int:
    from refresh_public_page import CHANGEFREQ_FOR_WINDOW
    ok = CHANGEFREQ_FOR_WINDOW[30] == "monthly" and CHANGEFREQ_FOR_WINDOW[365] == "yearly"
    print(("PASS" if ok else "FAIL") + " sitemap-promise self-test")
    return 0 if ok else 1


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if "--self-test" in sys.argv:
        return self_test()
    f, n = findings()
    print(f"sitemap-promise (Wave KA): {n} URLs checked - <lastmod> equals each page's own dateModified, <changefreq> matches the kind's window")
    for x in f[:40]:
        print(f"  - {x}")
    if len(f) > 40:
        print(f"  ... and {len(f) - 40} more")
    print("PASS" if not f else "FAIL")
    return 0 if not f else 1


if __name__ == "__main__":
    sys.exit(main())
