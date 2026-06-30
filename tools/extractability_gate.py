#!/usr/bin/env python3
"""
extractability_gate.py — SEO/AEO/GEO Arc, Phase P2 (on-page AEO/GEO extractability).

The on-page levers AEO + GEO are actually won by (the parts WorkHive fully
controls), from the Princeton/SIGKDD 2024 GEO study + 2026 AEO research:

  answer_first    a crisp self-contained opener (20-90 words) near the top — the
                  40-60w "direct answer" AI engines lift into a generated answer
  has_statistic   >=1 concrete number/stat in the body — "Statistics Addition"
                  lifted AI citation up to +40% in the Princeton study
  has_citation    >=1 authoritative source cited (a standard or an outbound source)
                  — "Cite Sources" lifted citation up to +40%

Ratcheted forward-only (mirrors content_grounding_gate.py / seo_technical_gate.py):
PASS on pre-existing, FAIL on NEW drift, so a newly-generated article can't ship
without the extractability levers. Surface list is CATALOG-DERIVED (every /learn
article flows in automatically). Conservative heuristics (flag only clear misses)
so the gate guides the P2 retrofit without false alarms.

CLI:
    python tools/extractability_gate.py            # ratcheted run
    python tools/extractability_gate.py --strict
    python tools/extractability_gate.py --update-baseline
    python tools/extractability_gate.py --self-test
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
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import platform_catalog as pc  # noqa: E402

BASELINE_PATH = ROOT / "extractability_baseline.json"
REPORT_PATH = ROOT / "extractability_report.json"
CHECK_ORDER = ["answer_first", "has_statistic", "has_citation"]

# Authoritative-source signals an article may cite (standards bodies, agencies,
# or any outbound link). Conservative: any ONE clears has_citation.
_CITE_RE = re.compile(
    r'(?i)\bsources?\b|\bISO\s?\d|\bIEC\s?\d|\bNFPA\b|\bASHRAE\b|\bASME\b|\bAPI\s?\d|\bSMRP\b|'
    r'\bDOLE\b|\bOSHS\b|\bTESDA\b|\bDOST\b|\bDTI\b|\bPSME\b|\bIIEE\b|\bPMI\b|\bPMBOK\b|\bPAS\s?\d|'
    r'\bNSCP\b|\bPEC\b|href=["\']https?://')
_TAG_RE = re.compile(r"<[^>]+>")
_P_RE = re.compile(r"<p\b[^>]*>(.*?)</p>", re.DOTALL | re.IGNORECASE)


def indexable_articles(cat: dict | None = None) -> list[str]:
    cat = cat or pc.build_catalog()
    out = []
    for a in cat.get("articles", []):
        url = (a.get("url") or "").strip("/")
        if url.startswith("learn/"):
            out.append(f"{url}/index.html")
    return out


def _read(rel: str) -> str | None:
    try:
        return (ROOT / rel).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _body(html: str) -> str:
    """The article's main prose region (prose-wh → id="faq"); falls back to after
    the first </h1>. Excludes the FAQ accordion + head so checks judge the body."""
    start = html.find("prose-wh")
    if start == -1:
        m = re.search(r"</h1>", html, re.IGNORECASE)
        start = m.end() if m else 0
    end = html.find('id="faq"')
    if end == -1:
        end = len(html)
    return html[start:end]


def _words(s: str) -> int:
    return len(_TAG_RE.sub(" ", s).split())


def analyze(html: str) -> dict:
    """Per-article verdict for the three extractability levers (True = present)."""
    body = _body(html)
    paras = _P_RE.findall(body)
    # answer_first — a crisp opener among the first 3 paragraphs (20-90 words)
    answer_first = any(20 <= _words(p) <= 90 for p in paras[:3])
    visible = _TAG_RE.sub(" ", body)
    has_statistic = bool(re.search(r"\d", visible))
    has_citation = bool(_CITE_RE.search(body))
    return {"answer_first": answer_first, "has_statistic": has_statistic, "has_citation": has_citation}


def run_checks(cat: dict | None = None) -> dict:
    cat = cat or pc.build_catalog()
    checks = {k: {"count": 0, "issues": []} for k in CHECK_ORDER}
    for page in indexable_articles(cat):
        html = _read(page)
        if html is None:
            continue
        v = analyze(html)
        if not v["answer_first"]:
            checks["answer_first"]["issues"].append(
                {"page": page, "reason": f"{page} has no crisp answer-first opener (20-90w) in the first 3 paragraphs"})
        if not v["has_statistic"]:
            checks["has_statistic"]["issues"].append(
                {"page": page, "reason": f"{page} body has no statistic/number (Princeton: stats lift AI citation up to +40%)"})
        if not v["has_citation"]:
            checks["has_citation"]["issues"].append(
                {"page": page, "reason": f"{page} cites no authoritative source (Princeton: cite-sources lifts citation up to +40%)"})
    for k in CHECK_ORDER:
        checks[k]["count"] = len(checks[k]["issues"])
    return checks


def _load_baseline() -> dict:
    if BASELINE_PATH.exists():
        try:
            return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def evaluate(strict: bool = False, update_baseline: bool = False) -> tuple[int, dict]:
    checks = run_checks()
    prior = _load_baseline().get("checks", {})
    rows, fails, new_base = [], [], {}
    for name in CHECK_ORDER:
        cur = checks[name]["count"]
        base = prior.get(name, cur)
        ratcheted = min(base, cur)
        new_base[name] = ratcheted
        failing = (cur > 0) if strict else (cur > ratcheted)
        if failing:
            fails.append(name)
        rows.append({"check": name, "current": cur, "baseline": 0 if strict else ratcheted,
                     "status": "FAIL" if failing else ("OK" if cur == 0 else "HELD"),
                     "issues": checks[name]["issues"]})
    total = sum(checks[n]["count"] for n in CHECK_ORDER)
    report = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "mode": "strict" if strict else "ratchet", "total_issues": total,
              "failed_checks": fails, "checks": rows}
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if not strict:
        est = _load_baseline().get("established")
        BASELINE_PATH.write_text(json.dumps({
            "checks": new_base,
            "established": est or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "last_run": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }, indent=2), encoding="utf-8")
    elif update_baseline:
        BASELINE_PATH.write_text(json.dumps(
            {"checks": {n: checks[n]["count"] for n in CHECK_ORDER}}, indent=2), encoding="utf-8")
    return (1 if fails else 0), report


def _print(report: dict):
    def c(code, s): return f"\033[{code}m{s}\033[0m"
    print(c("96", "\n  EXTRACTABILITY GATE (P2) · Princeton triad · ratchet"))
    print("  " + "=" * 60)
    for r in report["checks"]:
        col = "91" if r["status"] == "FAIL" else ("92" if r["status"] == "OK" else "93")
        print(f"    {c(col, r['status'].ljust(4))} {r['check']:<15} current={r['current']}  baseline={r['baseline']}")
        for i in r["issues"][:4]:
            print(f"          - {i['reason']}")
        if len(r["issues"]) > 4:
            print(f"          … +{len(r['issues']) - 4} more")
    n = len(report["failed_checks"])
    print(c("92", f"\n  PASS — no check over baseline (total issues: {report['total_issues']}).\n") if n == 0
          else c("91", f"\n  FAIL — {n} check(s) over baseline: {', '.join(report['failed_checks'])}\n"))


def self_test() -> int:
    fails = 0

    def ck(cond, msg):
        nonlocal fails
        print(("  \033[92mPASS\033[0m  " if cond else "  \033[91mFAIL\033[0m  ") + msg)
        if not cond:
            fails += 1

    print("\n\033[1mextractability_gate.py --self-test\033[0m")
    print("=" * 55)

    good = ('<div class="prose-wh"><p>' + "WorkHive logs a repair in under a minute and OEE rises to 85% per ISO 22400 "
            "after a month of consistent capture across the plant floor team here." + '</p>'
            '<p>Sources: ISO 14224, SMRP.</p></div><div id="faq"></div>')
    no_stat = '<div class="prose-wh"><p>' + ("WorkHive helps your team capture work and hand over shifts cleanly every day "
              "without paper, which the whole crew appreciates over time on the floor.") + '</p><p>Source: SMRP.</p></div><div id="faq"></div>'
    no_cite = '<div class="prose-wh"><p>' + ("WorkHive raised OEE to 85% in one month for a Cabuyao bottling line crew "
              "that logged every repair with photos and voice on their phones daily.") + '</p></div><div id="faq"></div>'
    no_answer = ('<div class="prose-wh"><p>Hi.</p><p>Yo.</p><p>Hey.</p>'
                 '<p>OEE 85% per ISO 14224 source.</p></div><div id="faq"></div>')

    a = analyze(good)
    ck(a["answer_first"] and a["has_statistic"] and a["has_citation"], "well-formed article passes all 3 levers")
    ck(not analyze(no_stat)["has_statistic"], "article with no number → has_statistic flags")
    ck(not analyze(no_cite)["has_citation"], "article with no source → has_citation flags")
    ck(not analyze(no_answer)["answer_first"], "article with only tiny opening paragraphs → answer_first flags")

    live = indexable_articles()
    ck(len(live) >= 30, f"surface list is catalog-derived ({len(live)} articles)")

    print("=" * 55)
    print("\033[92m  self-test PASS\033[0m\n" if not fails else f"\033[91m  self-test FAIL — {fails}\033[0m\n")
    return 1 if fails else 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    rc, report = evaluate(strict="--strict" in argv, update_baseline="--update-baseline" in argv)
    _print(report)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
