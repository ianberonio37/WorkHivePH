"""
content_freshness_gate.py — the refresh queue, measured (SEO_AEO_GEO_STRATEGY_V2 §4.3).
========================================================================================
Reports how stale every public content page is, and ranks what to refresh first.

WHY THIS EXISTS: Perplexity cites content updated within the last 30 days **82% of the
time** [substrate/external/external-chatgpt-vs-perplexity-ai-visibility-citations-tr], and
the refresh playbook says to keep pillars inside that window
[external-content-refresh-cadence-topical-authority-freshn]. That cadence was prescribed
with nothing measuring it, so it silently didn't happen: at first run, 43 of 53 articles
were 31-90 days old and only 10 were inside the window.

WHAT THIS IS NOT: an instruction to bump `dateModified`. Editing the date without editing
the content is a lie to the crawler and to the reader, it is trivially detectable by diffing
against the previous crawl, and it burns exactly the trust the freshness signal is meant to
measure. This tool ranks pages so a REAL refresh (new facts, new numbers, corrected claims,
new internal links) happens where it pays most. A refresh that changes nothing should not
change the date.

TIERS (staleness targets differ by what the page is for):
  pillar/comparison  30 days  — hubs and vs-pages carry pricing + rankings that go stale,
                                and they are the pages engines cite for a decision
  article            90 days  — evergreen method guides; refresh on fact drift
  calculator        365 days  — the formula and the standard do not move; the worked
                                numbers are regenerated from the engine on every build

Advisory by design (always exit 0): staleness is a backlog signal, not a build error, and
a blocking gate here would push toward the fake-bump it exists to prevent.

CLI:
    python tools/content_freshness_gate.py            # ranked refresh queue
    python tools/content_freshness_gate.py --json     # machine-readable
    python tools/content_freshness_gate.py --self-test
"""
from __future__ import annotations

import re
import sys
import json
from datetime import date, datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
REPORT = ROOT / "content_freshness_report.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TARGET_DAYS = {"pillar": 30, "comparison": 30, "article": 90, "calculator": 365}

# pages whose job is to be the cited hub for a decision
PILLARS = {
    "maintenance-metrics-reliability-guide", "start-digital-maintenance-guide",
    "ph-plant-compliance-guide", "free-engineering-calculators-philippine-plants",
    "what-is-workhive-complete-platform-guide", "reduce-unplanned-downtime-guide",
}
# PRODUCT comparisons only. A bare "-vs-" is too greedy: it swallows concept explainers
# like `mtbf-vs-mttr-for-supervisors`, which is an evergreen metrics guide, not a vs-page
# carrying vendor pricing that goes stale in a quarter.
COMPARISON_HINTS = ("workhive-vs-", "cmms-vs-", "best-free-cmms")

DATE_RE = (r'"dateModified":\s*"(\d{4}-\d{2}-\d{2})"',
           r'article:modified_time"\s+content="(\d{4}-\d{2}-\d{2})')


def _classify(slug: str, path: Path) -> str:
    if path.parent.parent.name == "tools" or slug.endswith("-calculator"):
        return "calculator"
    if slug in PILLARS:
        return "pillar"
    if any(h in slug for h in COMPARISON_HINTS):
        return "comparison"
    return "article"


def _date_of(text: str) -> date | None:
    for pat in DATE_RE:
        m = re.search(pat, text)
        if m:
            try:
                return date(*map(int, m.group(1).split("-")))
            except ValueError:
                return None
    return None


def scan(today: date | None = None) -> list[dict]:
    today = today or datetime.now(timezone.utc).date()
    out: list[dict] = []
    paths = sorted((ROOT / "learn").glob("*/index.html")) + \
            sorted((ROOT / "tools").glob("*-calculator/index.html"))
    for p in paths:
        slug = p.parent.name
        if slug == "learn":
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        d = _date_of(txt)
        kind = _classify(slug, p)
        age = (today - d).days if d else None
        target = TARGET_DAYS[kind]
        out.append({
            "slug": slug, "kind": kind, "modified": d.isoformat() if d else None,
            "age_days": age, "target_days": target,
            "over_by": (age - target) if (age is not None and age > target) else 0,
            # priority: how far past target, weighted by how much the page's freshness matters
            "priority": round(((age - target) / target) * (3 if kind in ("pillar", "comparison") else 1), 2)
                        if (age is not None and age > target) else 0.0,
        })
    return out


def run(as_json: bool = False) -> int:
    rows = scan()
    stale = sorted([r for r in rows if r["over_by"] > 0], key=lambda r: -r["priority"])
    REPORT.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {"pages": len(rows), "stale": len(stale),
                    "by_kind": {k: sum(1 for r in rows if r["kind"] == k) for k in TARGET_DAYS}},
        "queue": stale, "all": rows,
    }, indent=2), encoding="utf-8")
    if as_json:
        print(json.dumps(stale[:20], indent=2))
        return 0

    print("=" * 66)
    print("  CONTENT FRESHNESS — refresh queue (advisory)")
    print("=" * 66)
    for k in TARGET_DAYS:
        ks = [r for r in rows if r["kind"] == k]
        if not ks:
            continue
        over = sum(1 for r in ks if r["over_by"] > 0)
        print(f"  {k:<11} {len(ks):>3} page(s)  target {TARGET_DAYS[k]:>3}d   "
              f"{'OK' if not over else str(over) + ' past target'}")
    print("-" * 66)
    if not stale:
        print("  Everything inside its target window.")
    else:
        print(f"  Refresh these first ({len(stale)} past target; top 12 by priority):\n")
        print(f"  {'PRIO':>5}  {'AGE':>5}  {'OVER':>5}  {'KIND':<11} SLUG")
        # 2dp, not 1: an article 2 days past a 90-day target scores 0.02, and %.1f
        # printed that as "0.0" — visually identical to the in-window score the
        # self-test asserts is exactly 0. The ranking was correct and the column was
        # hiding it, which is the same class of defect as a lens measuring the wrong
        # thing: the number to distrust first is the one being displayed, not computed.
        # `OVER` carries the days past target so the row is readable without arithmetic.
        for r in stale[:12]:
            print(f"  {r['priority']:>5.2f}  {r['age_days']:>4}d  {r['over_by']:>4}d  "
                  f"{r['kind']:<11} {r['slug']}")
        print("\n  A refresh means new facts, numbers, or links — not a date bump.")
        print("  Once GSC is wired, re-rank by search position (3-20 first).")
    print("=" * 66)
    print(f"  report -> {REPORT.name}")
    return 0


def self_test() -> int:
    ok = True

    def ck(cond, label):
        nonlocal ok
        ok &= bool(cond)
        print(f"  {'PASS' if cond else 'FAIL'}  {label}")

    ck(_classify("workhive-vs-upkeep-free-cmms-comparison", ROOT / "learn/x/index.html") == "comparison",
       "vs-page classified as comparison")
    ck(_classify("mtbf-vs-mttr-for-supervisors", ROOT / "learn/x/index.html") == "article",
       "concept explainer with 'vs' is NOT a product comparison")
    ck(_classify("pump-tdh-calculator", ROOT / "tools/pump-tdh-calculator/index.html") == "calculator",
       "calculator classified by path")
    ck(_classify("ph-plant-compliance-guide", ROOT / "learn/x/index.html") == "pillar",
       "known hub classified as pillar")
    ck(_classify("free-pm-checklist-templates", ROOT / "learn/x/index.html") == "article",
       "ordinary guide classified as article")
    ck(_date_of('"dateModified": "2026-05-17",') == date(2026, 5, 17), "dateModified parsed")
    ck(_date_of('article:modified_time" content="2026-08-05T00:00:00+08:00"') == date(2026, 8, 5),
       "og modified_time parsed as fallback")
    ck(_date_of("<html>no date here</html>") is None, "missing date returns None")
    rows = scan()
    ck(len(rows) > 50, f"scan finds the content set ({len(rows)} pages)")
    ck(all(r["priority"] == 0 for r in rows if r["over_by"] == 0), "in-window pages carry zero priority")
    # a pillar and an article equally overdue: the pillar must rank higher
    p = ((120 - 30) / 30) * 3
    a = ((120 - 90) / 90) * 1
    ck(p > a, "pillar staleness outranks article staleness at equal age")
    print("  self-test", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--self-test" in args:
        raise SystemExit(self_test())
    raise SystemExit(run(as_json="--json" in args))
