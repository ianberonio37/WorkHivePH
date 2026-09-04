#!/usr/bin/env python3
"""structured-data-parity - T154: machine-readable truth = human-readable truth (2026-08-26).

JSON-LD is what an answer engine quotes when it cites this platform. Nobody proofreads
it, because nobody SEES it - so it drifts away from the page underneath it and keeps
being served, confidently, to the machines that summarize us.

TWO CONTRACTS, both born from real drift:

  FAQ  Every FAQPage Question name must appear in the page's visible text. This is the
       class T1 caught on the landing page, where the LD still told the provisioning-
       waitlist story after the page had moved to instant signup. An FAQ rich result
       PROMISES the page answers that question; if the words are not there, the promise
       is to content that does not exist. MEASURED: 310 questions across 53 learn
       pages, all present.

  NAME An Article headline must still be recognisable as the page's own title (og:title
       or <title>). FOUND HERE: predictive-alert-thresholds-plants had been retitled to
       lead with "ISO 10816 Vibration Thresholds and Predictive Alert Limits" - a
       deliberate SEO move toward the citable standard - while its LD headline kept the
       older, vaguer "Predictive Alert Thresholds for Industrial Plants". An answer
       engine reading the structured data got the version WITHOUT the ISO anchor that
       makes the page worth citing. Synced.

★HowToStep NAMES ARE DELIBERATELY NOT GATED, and the exclusion is the finding, not a
convenience. A first pass flagged 31 "gaps" across 12 HowTo pages; every one was
editorial paraphrase, not drift - the OEE guide's LD says "Measure planned production
time" where the page heads the section "Step 1: Planned Production Time". Same step,
different register. A step NAME is a label for a procedure, and demanding substring
identity would have shipped 31 false findings and then trained everyone to ignore this
gate. The FAQ question and the headline are different: both are quoted VERBATIM by the
consumers that read them, so identity is the actual contract there.

Static: JSON-LD and page text both ship in the HTML, so there is nothing a browser
would add.

Usage: python tools/validate_structured_data_parity.py
"""
import glob
import io
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
LD = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S)

ENTITIES = [("&amp;", "&"), ("&quot;", '"'), ("&#39;", "'"), ("&nbsp;", " "),
            ("&lt;", "<"), ("&gt;", ">"), ("’", "'"), ("‘", "'"),
            ("“", '"'), ("”", '"'), ("—", "-"), ("–", "-")]


def _fold(t: str) -> str:
    for a, b in ENTITIES:
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t).strip().lower()


def visible_text(src: str) -> str:
    s = re.sub(r"<script.*?</script>", " ", src, flags=re.I | re.S)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.S)
    return _fold(re.sub(r"<[^>]+>", " ", s))


def nodes(obj):
    if isinstance(obj, list):
        for o in obj:
            yield from nodes(o)
    elif isinstance(obj, dict):
        yield obj
        for k in ("@graph", "mainEntity", "itemListElement"):
            if k in obj:
                yield from nodes(obj[k])


def main() -> int:
    files = sorted(glob.glob(str(ROOT / "learn" / "*" / "index.html"))
                   + glob.glob(str(ROOT / "tools" / "*" / "index.html"))
                   + [str(ROOT / "index.html"), str(ROOT / "about" / "index.html")])
    files = [f for f in files if Path(f).exists()]
    if not files:
        print("SKIP structured-data-parity - no public pages found")
        return 0

    faq_checked = name_checked = 0
    bad_json, faq_gaps, name_gaps = [], [], []

    for f in files:
        rel = Path(f).parent.name if Path(f).name == "index.html" else Path(f).name
        src = io.open(f, encoding="utf-8", errors="replace").read()
        vis = visible_text(src)

        og = re.search(r'property=["\']og:title["\']\s+content=["\']([^"\']+)', src)
        ti = re.search(r"<title>(.*?)</title>", src, re.S)
        titles = [_fold(re.sub(r"\s*\|\s*WorkHive\s*$", "", m.group(1), flags=re.I))
                  for m in (og, ti) if m]

        for block in LD.findall(src):
            try:
                data = json.loads(block.strip())
            except Exception as e:
                bad_json.append(f"{rel}: unparseable JSON-LD ({str(e)[:50]})")
                continue
            for n in nodes(data):
                t = n.get("@type")
                t = "/".join(t) if isinstance(t, list) else t
                if t == "Question" and n.get("name"):
                    faq_checked += 1
                    if _fold(n["name"]) not in vis:
                        faq_gaps.append(f"{rel}: FAQ question absent from the page - \"{n['name'][:66]}\"")
                elif t in ("Article", "TechArticle", "BlogPosting") and n.get("headline"):
                    name_checked += 1
                    h = _fold(n["headline"])
                    if titles and not any(h in x or x in h for x in titles):
                        name_gaps.append(f"{rel}: LD headline \"{n['headline'][:52]}\" != page title "
                                         f"\"{(og or ti).group(1)[:52]}\"")

    print(f"  pages {len(files)} | FAQ questions checked {faq_checked} | headlines checked {name_checked}"
          f" | HowToStep names not gated (editorial paraphrase, by design)")
    fails = bad_json + faq_gaps + name_gaps
    if fails:
        print(f"FAIL structured-data-parity - {len(fails)} claim(s) the page does not back:")
        for x in fails[:12]:
            print("    - " + x)
        if len(fails) > 12:
            print(f"    ... and {len(fails) - 12} more")
        print("    JSON-LD is what an answer engine QUOTES. An FAQ entry promises the page answers that")
        print("    question; a headline is the page's name. Both are read verbatim, so both must match")
        print("    what a person actually finds when they follow the citation.")
        return 1
    print(f"PASS structured-data-parity - {faq_checked} FAQ questions are answerable on their page and "
          f"{name_checked} headlines still match the title the page presents.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
