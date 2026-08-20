"""
cta_gate.py — the last SXO lever that had no instrument (SEO_AEO_GEO_V3 §6).
============================================================================
SXO is what happens after the click. Three of its four levers now have gates —
load speed (`cwv`), the page shell (`validate_calc_pages`), and mobile viewport.
The fourth, "clear CTAs", had none, so nothing noticed that **19 of 53 /learn
articles end with no next action at all**.

WHAT COUNTS AS A CTA HERE: an in-body link to an ACTION surface — a WorkHive tool
or the join flow. Deliberately NOT counted:
  · links to other articles — a good next read is not a next action;
  · header and footer links — every page has those, so counting them would score
    100% and measure nothing (the failure mode this gate exists to avoid).

Winning the citation is the expensive half. A visitor who arrives from an AI
answer, reads to the end, and finds nowhere to go is the cheapest loss on the
board.

RATCHETED forward-only: the honest state is 19 pages short, and a gate that fails
the build on day one gets ignored rather than fixed.

CLI:
    python tools/cta_gate.py
    python tools/cta_gate.py --self-test
"""
from __future__ import annotations

import re
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

BASELINE = ROOT / "cta_baseline.json"
REPORT = ROOT / "cta_report.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Action surfaces: the app's tools and the join flow.
#
# AN ORACLE'S VOCABULARY IS PART OF THE ORACLE, and this list was short by eight. The gate
# reported 13 pages whose only next action was the generic /#join, which reads as an SXO
# defect worth fixing by hand. Reading one of them showed the opposite: the shift-handover
# guide already ends with <a href="/shift-brain.html" class="cta-btn">Open Shift Brain</a>,
# a perfectly targeted CTA the gate simply could not see. Eight real tool pages were absent
# from the allowlist, every one of them present on disk and linked as the "Open X" button of
# exactly the article it belongs to. Adding them corrects a MEASUREMENT, and the alternative
# was 13 hand-edits to pages that were never broken.
ACTION_RE = re.compile(
    r'href="(/#join|/engineering-design\.html|/logbook\.html|/pm-scheduler\.html|'
    r'/skillmatrix\.html|/hive\.html|/assistant\.html|/analytics\.html|/inventory\.html|'
    r'/dayplanner\.html|/alert-hub\.html|/asset-hub\.html|/community\.html|/marketplace\.html|'
    r'/resume\.html|/voice-journal\.html|'
    r'/shift-brain\.html|/integrations\.html|/project-manager\.html|/achievements\.html|'
    r'/audit-log\.html|/ai-quality\.html|/plant-connections\.html|/ph-intelligence\.html|'
    r'/workhive/[^"]*)"')


def body_region(html: str) -> str:
    """The article body only — header/footer chrome excluded, because those links
    appear on every page and would make the check pass without meaning anything."""
    start = html.find("<article")
    if start == -1:
        start = html.find("<main")
    body = html[start:] if start != -1 else html
    end = body.find("<footer")
    return body[:end] if end != -1 else body


def ctas(html: str) -> set[str]:
    return set(ACTION_RE.findall(body_region(html)))


def _pages() -> list[str]:
    try:
        import seo_technical_gate as st
        return [p for p in st.indexable_pages()
                if p.startswith("learn/") or p.startswith("tools/")]
    except Exception:
        return sorted(str(p.relative_to(ROOT).as_posix())
                      for p in ROOT.glob("learn/*/index.html"))


def audit() -> dict:
    rows = []
    for rel in _pages():
        f = ROOT / rel
        if not f.exists() or Path(rel).parent.name == "learn":
            continue
        n = len(ctas(f.read_text(encoding="utf-8", errors="replace")))
        rows.append({"page": rel, "ctas": n, "ok": n >= 1})
    missing = [r for r in rows if not r["ok"]]
    return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "pages": len(rows), "with_cta": len(rows) - len(missing),
            "missing": len(missing), "missing_pages": [r["page"] for r in missing], "rows": rows}


def run() -> int:
    rep = audit()
    REPORT.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    base = {}
    if BASELINE.exists():
        try:
            base = json.loads(BASELINE.read_text(encoding="utf-8"))
        except Exception:
            base = {}
    prior = base.get("missing", rep["missing"])

    print("=" * 62)
    print("  CTA COVERAGE — SXO, the next action (V3 §6)")
    print("=" * 62)
    print(f"  pages: {rep['pages']}   with a CTA: {rep['with_cta']}   missing: {rep['missing']}  (baseline {prior})")
    for p in rep["missing_pages"][:12]:
        print(f"    no next action  {p}")
    if rep["missing"] > 12:
        print(f"    … and {rep['missing'] - 12} more")
    print("=" * 62)
    if rep["missing"] > prior:
        print(f"  FAIL — regressed {prior} -> {rep['missing']} pages without a CTA")
        return 1
    BASELINE.write_text(json.dumps({"missing": min(prior, rep["missing"]),
                                    "established": base.get("established", rep["generated_at"])},
                                   indent=2), encoding="utf-8")
    print("  PASS — no regression." if BASELINE.exists() else "  baseline established.")
    if rep["missing"]:
        print(f"  A reader finishing one of these {rep['missing']} pages has nowhere to go.")
    return 0


def self_test() -> int:
    ok = True

    def ck(c, label):
        nonlocal ok
        ok &= bool(c)
        print(f"  {'PASS' if c else 'FAIL'}  {label}")

    ck(ctas('<article><a href="/engineering-design.html">Open</a></article>') == {"/engineering-design.html"},
       "an in-body tool link counts")
    ck(ctas('<article><a href="/#join">Join</a></article>') == {"/#join"}, "the join flow counts")
    ck(ctas('<article><a href="/learn/what-is-oee-how-to-calculate/">read</a></article>') == set(),
       "a link to another article is NOT a next action")
    ck(ctas('<article>body</article><footer><a href="/#join">Join</a></footer>') == set(),
       "footer chrome does not count — it is on every page")
    ck(ctas('<article><a href="/hive.html">a</a><a href="/hive.html">b</a></article>') == {"/hive.html"},
       "two links to one surface is one CTA")
    # THE VOCABULARY GUARD. This gate once reported 13 pages as offering only the generic
    # /#join. Eight of them already ended with a perfectly targeted CTA -- "Open Shift
    # Brain", "Open Audit Log" -- pointing at real tool pages simply absent from ACTION_RE.
    # The gate was not finding a content defect, it was describing its own blind spot, and
    # acting on it would have meant 13 hand-edits to pages that were never broken. This
    # fails if an article's cta-btn points somewhere the allowlist cannot see.
    unseen = {}
    for rel in _pages():
        f = ROOT / rel
        if not f.exists():
            continue
        body = body_region(f.read_text(encoding="utf-8", errors="replace"))
        for href in re.findall(r'href="(/[a-z0-9\-]+\.html)"[^>]*class="cta-btn"', body):
            if not ACTION_RE.search('href="%s"' % href):
                unseen.setdefault(href, []).append(rel)
    ck(not unseen,
       "every cta-btn target is in ACTION_RE" + (f" (blind to: {sorted(unseen)})" if unseen else ""))

    rep = audit()
    ck(rep["pages"] > 100, f"audits the content surface ({rep['pages']} pages)")
    print("  self-test", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(self_test() if "--self-test" in sys.argv[1:] else run())
