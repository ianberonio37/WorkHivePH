#!/usr/bin/env python3
"""
validate_article_taxonomy.py — Content Grounding Gate: article <-> page taxonomy consistency.

The existing content_grounding checks (capability_drift, count_drift) do NOT catch a
feature /learn/ article stating a TAXONOMY that disagrees with its live page: e.g. the
engineering-calculators article claimed "6 disciplines / 30+ calculators" while the page
has "HVAC & Cooling / Mechanical / Electrical / Plumbing / Fire Protection / Machine Design,
53 calculations" (fixed 2026-07-05); and the skill-matrix article says "4 of 6 disciplines"
while skillmatrix.html says "across 5 disciplines".

This flags, per feature article, any TAXONOMY-NOUN count that the article states differently
from its own linked feature page. Prose-only + deterministic (no page render): it reads the
article's primary tool-page link (the CTA button href), then compares "<N> <noun>" claims
that BOTH the article and that page make, for a fixed set of taxonomy nouns.

Illustrative teaching tables ("Example matrix: 6 technicians, 8 disciplines") can trip a
naive scan, so a mismatch is reported as a finding for human triage and absorbed by a
frozen baseline (like the other ratchet checks), not an auto-fail of unrelated content.

CLI:
    python tools/validate_article_taxonomy.py            # report findings, exit 1 if over baseline
    python tools/validate_article_taxonomy.py --print     # show every article->page count pair
    python tools/validate_article_taxonomy.py --update-baseline
    python tools/validate_article_taxonomy.py --self-test
"""
from __future__ import annotations

import re
import sys
import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
# Canonical Windows cp1252 stdout guard (form detected by validate_validator_cp1252_guard).
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

LEARN = ROOT / "learn"
BASELINE = ROOT / "article_taxonomy_baseline.json"

# Taxonomy nouns whose stated count must agree between a feature article and its page.
# "level" is deliberately EXCLUDED: it is ordinal-ambiguous ("Level 3" / "TESDA NC IV" vs
# the count "5 skill levels"), and cross-scale differences (TESDA's 4 NC levels vs WorkHive's
# 5 skill levels) are legitimate, not drift.
NOUNS = ["discipline", "calculator", "calculation", "template", "tab", "module", "category"]
_NOUN_RE = "|".join(f"{n}s?" for n in NOUNS)

_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
          "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}

# "<N> <noun>" where N is a digit or a number-word. Captures (count, noun-singular).
_CLAIM = re.compile(r"\b(\d{1,3}|" + "|".join(_WORDS) + r")\s+(" + _NOUN_RE + r")\b", re.IGNORECASE)


def _num(tok: str) -> int | None:
    tok = tok.lower()
    if tok.isdigit():
        return int(tok)
    return _WORDS.get(tok)


def _strip_tags(html: str) -> str:
    # drop <script>/<style> bodies, then tags; keep visible + attribute-free prose.
    html = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", html)


def _counts(text: str) -> dict[str, set[int]]:
    """noun(singular) -> set of stated counts."""
    out: dict[str, set[int]] = {}
    for tok, noun in _CLAIM.findall(text):
        n = _num(tok)
        if n is None:
            continue
        key = noun.lower().rstrip("s")
        out.setdefault(key, set()).add(n)
    return out


def _primary_page(article_html: str) -> str | None:
    """The article's own feature page = the CTA-button href (/x.html), else the single
    non-learn feature page it links to."""
    m = re.search(r'class="cta-btn"[^>]*href="/([a-z0-9-]+\.html)"', article_html)
    if not m:
        m = re.search(r'href="/([a-z0-9-]+\.html)"[^>]*class="cta-btn"', article_html)
    if m:
        return m.group(1)
    pages = re.findall(r'href="/([a-z0-9-]+\.html)"', article_html)
    pages = [p for p in pages if p not in ("index.html",)]
    return pages[0] if pages else None


def scan() -> list[dict]:
    findings: list[dict] = []
    for d in sorted(LEARN.glob("*/")):
        art = d / "index.html"
        if not art.exists():
            continue
        html = art.read_text(encoding="utf-8", errors="replace")
        page_name = _primary_page(html)
        if not page_name:
            continue
        page = ROOT / page_name
        if not page.exists():
            continue
        art_counts = _counts(_strip_tags(html))
        page_counts = _counts(_strip_tags(page.read_text(encoding="utf-8", errors="replace")))
        for noun, avals in art_counts.items():
            pvals = page_counts.get(noun)
            if not pvals:
                continue  # page makes no count claim for this noun -> nothing to compare
            # a mismatch = the article states a count the page NEVER states for that noun.
            extra = sorted(v for v in avals if v not in pvals)
            if extra:
                findings.append({
                    "article": d.name, "page": page_name, "noun": noun,
                    "article_counts": sorted(avals), "page_counts": sorted(pvals),
                    "article_only": extra,
                })
    return findings


def _load_baseline() -> int:
    try:
        return int(json.loads(BASELINE.read_text(encoding="utf-8")).get("count", 0))
    except Exception:
        return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        # "4 of 6 disciplines": only "6 disciplines" is adjacent (the total to compare).
        a = _counts("reached Level 3 in 4 of 6 disciplines")
        p = _counts("maintenance competency across 5 disciplines")
        assert a.get("discipline") == {6} and p.get("discipline") == {5}, (a, p)
        assert _num("six") == 6 and _num("53") == 53
        # cross-check: 6 (article) not in {5} (page) -> a mismatch is detectable
        assert sorted(v for v in a["discipline"] if v not in p["discipline"]) == [6]
        print("self-test OK")
        return 0

    findings = scan()
    if "--print" in argv:
        for d in sorted(LEARN.glob("*/")):
            art = d / "index.html"
            if not art.exists():
                continue
            html = art.read_text(encoding="utf-8", errors="replace")
            pg = _primary_page(html)
            if pg and (ROOT / pg).exists():
                print(f"{d.name:55} -> {pg}")
        return 0

    if "--update-baseline" in argv:
        BASELINE.write_text(json.dumps({"count": len(findings)}, indent=2), encoding="utf-8")
        print(f"baseline set to {len(findings)}")
        return 0

    base = _load_baseline()
    n = len(findings)
    status = "OK" if n <= base else "FAIL"
    try:
        (ROOT / "article_taxonomy.json").write_text(
            json.dumps({"status": status, "count": n, "baseline": base, "findings": findings},
                       indent=2), encoding="utf-8")
    except Exception:
        pass
    print("Article <-> Page taxonomy consistency")
    print("=" * 60)
    for f in findings:
        print(f"  DRIFT  {f['article']}")
        print(f"         {f['noun']}: article says {f['article_only']} "
              f"(all {f['article_counts']}) but {f['page']} says {f['page_counts']}")
    print("-" * 60)
    print(f"  {status}  findings={n}  baseline={base}")
    return 0 if n <= base else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
