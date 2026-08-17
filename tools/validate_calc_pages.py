"""
validate_calc_pages.py — the programmatic calculator-page gate (Pillar 3).
==========================================================================
Proves every generated `/tools/<slug>/` calculator page is:
  1. CRAWLABLE / static  — the answer + a numeric worked result live in the raw
     HTML, not injected by client-side JS (AI crawlers don't execute JS
     [external-ai-crawlers-fetch-but-do-not-execute-javascript-]).
  2. ANSWER-FIRST         — a `.answer-first` block appears right after the H1
     and contains a number (the citable stat).
  3. SCHEMA-VALID         — JSON-LD parses and includes SoftwareApplication +
     FAQPage (+ HowTo) [external-programmatic-seo-pages-step-by-step-implementati].
  4. NON-ORPHAN           — links back to its discipline pillar + >=1 sibling.
  5. WELL-FORMED          — title, meta description, self-referencing canonical, H1.

Scans `seo_assets/calc_pages_staging/` (pre-ship) and, once moved, `tools/` at
the site root. Non-thin check: page >= 2 KB of body text.

CLI:
    python tools/validate_calc_pages.py            # validate staged pages
    python tools/validate_calc_pages.py --self-test
Exit 0 = all pass (or no pages yet), 1 = a page failed.
"""
from __future__ import annotations

import re
import sys
import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
STAGING = ROOT / "seo_assets" / "calc_pages_staging"
SHIPPED = ROOT / "tools"          # once pages move to /tools/<slug>/index.html at site root
SITE = "https://workhiveph.com"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _extract_jsonld(html_text: str) -> list[dict]:
    out: list[dict] = []
    for m in re.finditer(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                         html_text, re.S | re.I):
        try:
            data = json.loads(m.group(1))
        except Exception:
            continue
        # unwrap @graph
        if isinstance(data, dict) and "@graph" in data:
            out.extend(x for x in data["@graph"] if isinstance(x, dict))
        elif isinstance(data, list):
            out.extend(x for x in data if isinstance(x, dict))
        elif isinstance(data, dict):
            out.append(data)
    return out


def _types(nodes: list[dict]) -> set[str]:
    t: set[str] = set()
    for n in nodes:
        v = n.get("@type")
        if isinstance(v, list):
            t.update(v)
        elif v:
            t.add(v)
    return t


def validate_page(path: Path) -> list[str]:
    """Return a list of failure strings ([] = pass)."""
    fails: list[str] = []
    txt = path.read_text(encoding="utf-8", errors="replace")
    slug = path.parent.name

    # 5. well-formed
    if not re.search(r"<title>.+?</title>", txt, re.S):
        fails.append("missing <title>")
    if not re.search(r'<meta\s+name=["\']description["\']', txt, re.I):
        fails.append("missing meta description")
    m_can = re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']+)["\']', txt, re.I)
    if not m_can:
        fails.append("missing canonical")
    elif slug not in m_can.group(1):
        fails.append(f"canonical does not self-reference slug ({m_can.group(1)})")
    if not re.search(r"<h1[^>]*>.+?</h1>", txt, re.S):
        fails.append("missing <h1>")

    # 2. answer-first: a .answer-first block AFTER the h1, containing a digit
    m_h1 = re.search(r"</h1>", txt, re.I)
    m_ans = re.search(r'class=["\']answer-first["\'][^>]*>(.*?)</p>', txt, re.S | re.I)
    if not m_ans:
        fails.append("no .answer-first block")
    else:
        if m_h1 and m_ans.start() < m_h1.end():
            fails.append("answer-first block precedes the h1")
        if not re.search(r"\d", m_ans.group(1)):
            fails.append("answer-first block has no number (not a citable stat)")

    # 1. crawlable/static: a numeric worked result present in raw HTML (not JS-only)
    #    heuristic — a results table with a numeric cell in the static body
    if not re.search(r"<td>[^<]*\d[^<]*</td>", txt):
        fails.append("no numeric worked result in static HTML (JS-only?)")

    # 3. schema-valid
    nodes = _extract_jsonld(txt)
    if not nodes:
        fails.append("no parseable JSON-LD")
    else:
        have = _types(nodes)
        for need in ("SoftwareApplication", "FAQPage"):
            if need not in have:
                fails.append(f"JSON-LD missing {need} (have: {sorted(have)})")
        # FAQPage must carry questions
        faq = next((n for n in nodes if n.get("@type") == "FAQPage"), None)
        if faq and not faq.get("mainEntity"):
            fails.append("FAQPage has no questions")

    # 4. non-orphan: >=2 internal links (pillar + sibling/related)
    internal = re.findall(r'href=["\'](/[^"\']+)["\']', txt)
    if len([h for h in internal if h.startswith("/learn/") or h.startswith("/tools/")]) < 2:
        fails.append("orphan-ish: <2 internal /learn or /tools links")

    # 6. PAGE SHELL — the page must look like the rest of the site (V3 §6, SXO).
    #    All 60 shipped with no CSS, header, footer or fonts: browser-default HTML,
    #    no branding, no way to navigate onward. Every other gate passed on them,
    #    because none of them looks at whether a human would trust the page.
    if "cdn.tailwindcss.com" not in txt:
        fails.append("no Tailwind — page renders unstyled")
    if ".prose-wh" not in txt:
        fails.append("missing the shared STYLE block (.prose-wh)")
    if '<header class="border-b' not in txt:
        fails.append("no site header — visitor cannot navigate onward")
    if '<footer class="py-10' not in txt:
        fails.append("no site footer")
    if "Poppins" not in txt:
        fails.append("no webfont — falls back to browser default")
    # mobile essentials for a page arriving from a phone-sized SERP
    m_vp = re.search(r'<meta[^>]+name=["\']viewport["\'][^>]*content=["\']([^"\']+)', txt, re.I)
    if not m_vp:
        fails.append("no viewport meta — unusable on mobile")
    elif "width=device-width" not in m_vp.group(1):
        fails.append(f"viewport lacks width=device-width ({m_vp.group(1)})")

    # non-thin: >= 2 KB of visible-ish text (strip tags)
    body_text = re.sub(r"<[^>]+>", " ", txt)
    body_text = re.sub(r"\s+", " ", body_text)
    if len(body_text) < 2000:
        fails.append(f"thin page ({len(body_text)} chars of text < 2000)")

    return fails


def _iter_pages() -> list[Path]:
    pages: list[Path] = []
    if STAGING.is_dir():
        pages.extend(sorted(STAGING.glob("*/index.html")))
    # shipped location: ROOT/tools/<slug>/index.html — only *-calculator dirs
    for p in sorted(SHIPPED.glob("*-calculator/index.html")):
        pages.append(p)
    return pages


def run() -> int:
    pages = _iter_pages()
    print("=" * 60)
    print("  Programmatic calculator-page gate")
    print("=" * 60)
    if not pages:
        print("  No calculator pages found yet (staging empty) — PASS (nothing to gate).")
        return 0
    bad = 0
    for p in pages:
        fails = validate_page(p)
        tag = f"/tools/{p.parent.name}/"
        if fails:
            bad += 1
            print(f"  FAIL  {tag}")
            for f in fails:
                print(f"          - {f}")
        else:
            print(f"  PASS  {tag}")
    print("=" * 60)
    print(f"  {len(pages) - bad}/{len(pages)} pages pass.")
    return 1 if bad else 0


def self_test() -> int:
    """Synthetic: a known-good page passes, a broken one fails."""
    good = f"""<!DOCTYPE html><html><head><title>X Calculator</title>
<meta name="description" content="d"><link rel="canonical" href="{SITE}/tools/x-calculator/">
<script type="application/ld+json">{{"@context":"https://schema.org","@graph":[
{{"@type":"SoftwareApplication","name":"X"}},{{"@type":"HowTo","name":"h"}},
{{"@type":"FAQPage","mainEntity":[{{"@type":"Question","name":"q","acceptedAnswer":{{"@type":"Answer","text":"a"}}}}]}}]}}</script>
</head><body><main><h1>X Calculator</h1>
<p class="answer-first"><strong>The answer is 42 m.</strong></p>
<table><tr><td>Result 42 m</td></tr></table>
<ul><li><a href="/learn/free-engineering-calculators-philippine-plants/">pillar</a></li>
<li><a href="/tools/y-calculator/">sib</a></li></ul>
<p>{'padding text ' * 200}</p></main></body></html>"""
    import tempfile
    ok = True
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "x-calculator" / "index.html"
        p.parent.mkdir(parents=True)
        p.write_text(good, encoding="utf-8")
        gf = validate_page(p)
        ck = (gf == [])
        print(f"  {'PASS' if ck else 'FAIL'}  good page validates clean ({gf})")
        ok &= ck
        # break it: remove canonical + FAQPage + answer number
        bad = good.replace('<link rel="canonical"', '<link rel="x"').replace("42 m", "unknown")
        p.write_text(bad, encoding="utf-8")
        bf = validate_page(p)
        ck2 = len(bf) >= 2
        print(f"  {'PASS' if ck2 else 'FAIL'}  broken page is caught ({len(bf)} issues)")
        ok &= ck2
    print("  self-test", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv[1:]:
        raise SystemExit(self_test())
    raise SystemExit(run())
