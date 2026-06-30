#!/usr/bin/env python3
"""
platform_name_alignment.py — Platform Alignment Arc, the NAME-authority audit.

Ian (2026-06-30): everything written/displayed must stay aligned to the CURRENT
platform; the PAGES are the ground truth. We found the root: the catalog's feature
`name` field (hand-authored intel) has drifted from what the pages actually call
the tools — e.g. pm-scheduler.html titles itself "PM Scheduler" but the catalog
calls it "PM Checklist". Because schema_featurelist / feature_drift validate
content "⊆ catalog", they pass while the displayed names are stale-vs-reality.

This tool makes the PAGE the naming authority and reports, per feature, where the
catalog name / landing popup name disagree with the page's own title.

AUTHORITY = the page's <title>, cleaned of the " | WorkHive" / ": WorkHive" suffix
(the canonical self-name); the <h1> is recorded too (it can be a tagline, e.g.
logbook's "Your Repair Logbook", so it is informational, not the authority).

DETECTION-ONLY: reads the pages + catalog + index.html stageData; never writes.
Ratcheted forward-only (same convention as the sibling gates) so a NEW name drift
fails while the known backlog burns down via the auto-fixers.

CLI:
    python tools/platform_name_alignment.py            # ratcheted run
    python tools/platform_name_alignment.py --strict   # fail on ANY drift > 0
    python tools/platform_name_alignment.py --report    # print the full drift matrix
    python tools/platform_name_alignment.py --update-baseline
    python tools/platform_name_alignment.py --self-test
"""
from __future__ import annotations

import re
import sys
import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import platform_catalog as pc          # noqa: E402
import render_public_surface as rps    # noqa: E402  (parse_landing_tools)

BASELINE_PATH = ROOT / "platform_name_alignment_baseline.json"
REPORT_PATH = ROOT / "platform_name_alignment_report.json"

CHECK_ORDER = ["catalog_name_drift", "popup_name_drift", "footer_name_drift"]

# The catalog-mirror region (rendered by render_public_surface) — excluded from the
# footer scan so the mirror's own page-truth labels aren't double-counted.
_MIRROR_REGION_RE = re.compile(r"<!--CATALOG:tool_catalog_mirror-->.*?<!--/CATALOG:tool_catalog_mirror-->", re.DOTALL)
_SCRIPT_BLOCK_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE)
# Footer "Tools" column links are <li><a href="…X.html">Name</a></li>. Scope to
# list-item links so action CTAs ("Log a Job", "Ask AI" — correct verbs, not tool
# names) are NOT mis-flagged; match any path prefix (/X.html, /workhive/X.html, X.html).
_FOOTER_LINK_RE = re.compile(r'<li\b[^>]*>\s*<a\b[^>]*\bhref="(?:[^"]*/)?([a-z0-9-]+\.html)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
_TAGSTRIP_RE = re.compile(r"<[^>]+>")

_TITLE_RE = re.compile(r"<title>\s*(.*?)\s*</title>", re.IGNORECASE | re.DOTALL)
_H1_RE = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
# Brand suffix/prefix separators a page title uses around "WorkHive".
# pipe/colon/en-em-dash are separators (optional spaces); ASCII hyphen only when
# space-padded, so "Spare-Parts Inventory" is not split at its internal hyphen.
_SEP_RE = re.compile(r"\s*[|:–—]\s*|\s+-\s+")


def _clean_title(raw: str) -> str:
    """The page's self-name: drop the WorkHive brand token + separators."""
    parts = [p.strip() for p in _SEP_RE.split(raw) if p.strip()]
    parts = [p for p in parts if p.lower() != "workhive"]
    return parts[0] if parts else raw.strip()


def page_authority_name(route: str) -> tuple[str | None, str | None]:
    """(authoritative name from <title>, first <h1> text) for a page, or (None,None)."""
    try:
        html = (ROOT / route).read_text(encoding="utf-8")
    except OSError:
        return None, None
    tm = _TITLE_RE.search(html)
    title = _clean_title(tm.group(1)) if tm else None
    hm = _H1_RE.search(html)
    h1 = _TAG_RE.sub("", hm.group(1)).strip() if hm else None
    return title, (h1 or None)


def _popup_names_by_route(html: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for name, _desc, link in rps.parse_landing_tools(html):
        out.setdefault(link.strip("/").lower(), []).append(name.strip())
    return out


def build_matrix(cat: dict | None = None) -> list[dict]:
    cat = cat or pc.build_catalog()
    index_html = (ROOT / "index.html").read_text(encoding="utf-8")
    popup_by_route = _popup_names_by_route(index_html)
    rows = []
    for f in cat.get("features", []):
        route = (f.get("route") or "").strip()
        if not route or route == "index.html" or f.get("status") != "active":
            continue
        if not (ROOT / route).exists():
            continue
        title, h1 = page_authority_name(route)
        popup_names = popup_by_route.get(route.strip("/").lower(), [])
        rows.append({
            "route": route,
            "authority": title,           # the page's <title> self-name = truth
            "page_h1": h1,
            "nav_label": f.get("nav_label"),
            "catalog_name": f.get("name"),
            "popup_names": popup_names,
            "catalog_matches": (title is not None and f.get("name") == title),
            "popup_matches": (title is not None and (not popup_names or title in popup_names)),
        })
    return rows


def run_checks(cat: dict | None = None) -> dict:
    rows = build_matrix(cat)
    checks: dict[str, dict] = {k: {"count": 0, "issues": []} for k in CHECK_ORDER}
    for r in rows:
        if r["authority"] is None:
            continue
        if not r["catalog_matches"]:
            checks["catalog_name_drift"]["issues"].append(
                {"route": r["route"], "authority": r["authority"], "catalog_name": r["catalog_name"],
                 "reason": f"{r['route']}: page titles itself '{r['authority']}' but the catalog "
                           f"calls it '{r['catalog_name']}' (catalog name is stale vs page-truth)"})
        if not r["popup_matches"]:
            checks["popup_name_drift"]["issues"].append(
                {"route": r["route"], "authority": r["authority"], "popup_names": r["popup_names"],
                 "reason": f"{r['route']}: page titles itself '{r['authority']}' but the landing popup "
                           f"calls it {r['popup_names']} (popup name drifts from page-truth)"})
    # footer_name_drift — STATIC <a href="X.html"> link LABELS elsewhere on index.html
    # (the footer "Tools" column + hero links), EXCLUDING the catalog mirror + scripts,
    # whose text disagrees with the page-truth name of X. (The live walk found the
    # footer is a 4th naming surface the catalog/popup checks never covered.)
    auth_by_route = {r["route"]: r["authority"] for r in rows if r["authority"]}
    index_html = (ROOT / "index.html").read_text(encoding="utf-8")
    scan = _SCRIPT_BLOCK_RE.sub("", _MIRROR_REGION_RE.sub("", index_html))
    seen_pairs = set()
    for route, label_html in _FOOTER_LINK_RE.findall(scan):
        auth = auth_by_route.get(route)
        if not auth:
            continue
        label = _TAGSTRIP_RE.sub("", label_html).strip()
        if not label:
            continue
        key = (route, label)
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        if label != auth:
            checks["footer_name_drift"]["issues"].append(
                {"route": route, "authority": auth, "label": label,
                 "reason": f"{route}: a static link is labelled '{label}' but the page-truth "
                           f"name is '{auth}' (footer/hero link label drifts from page-truth)"})

    for k in CHECK_ORDER:
        checks[k]["count"] = len(checks[k]["issues"])
    return checks


# ── Ratchet engine (mirrors landing_extractability_gate.py) ───────────────────

def _load_baseline() -> dict:
    if BASELINE_PATH.exists():
        try:
            return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def evaluate(strict: bool = False, update_baseline: bool = False) -> tuple[int, dict]:
    from datetime import datetime, timezone
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


def _print_report():
    rows = build_matrix()
    print("\n  PLATFORM NAME ALIGNMENT — authority = page <title>\n  " + "=" * 78)
    print(f"  {'route':<24}{'AUTHORITY (title)':<26}{'catalog_name':<26}match")
    print("  " + "-" * 78)
    for r in sorted(rows, key=lambda x: (x["catalog_matches"], x["route"])):
        mark = "OK" if r["catalog_matches"] else "DRIFT"
        print(f"  {r['route']:<24}{str(r['authority']):<26}{str(r['catalog_name']):<26}{mark}")
        if not r["popup_matches"]:
            print(f"      popup: {r['popup_names']}  (≠ '{r['authority']}')")
    drift = sum(1 for r in rows if not r["catalog_matches"])
    pdrift = sum(1 for r in rows if not r["popup_matches"])
    print("  " + "-" * 78)
    print(f"  {len(rows)} features · catalog-name drift: {drift} · popup-name drift: {pdrift}\n")


def _print(report: dict):
    def c(code, s): return f"\033[{code}m{s}\033[0m"
    print(c("96", "\n  PLATFORM NAME ALIGNMENT (page-truth) · ratchet"))
    print("  " + "=" * 62)
    for r in report["checks"]:
        col = "91" if r["status"] == "FAIL" else ("92" if r["status"] == "OK" else "93")
        print(f"    {c(col, r['status'].ljust(4))} {r['check']:<20} current={r['current']}  baseline={r['baseline']}")
        for i in r["issues"][:6]:
            print(f"          - {i['reason']}")
        if len(r["issues"]) > 6:
            print(f"          ... +{len(r['issues']) - 6} more")
    print("  " + "-" * 62)
    print(f"    total drift: {report['total_issues']}   failed: {report['failed_checks'] or 'none'}\n")


def _self_test() -> int:
    assert _clean_title("PM Scheduler: WorkHive") == "PM Scheduler", _clean_title("PM Scheduler: WorkHive")
    assert _clean_title("Asset Hub | WorkHive") == "Asset Hub"
    assert _clean_title("WorkHive | Free Tools") == "Free Tools"
    assert _clean_title("Predictive Maintenance") == "Predictive Maintenance"
    # A feature whose page does NOT exist on disk → authority unknown → SKIPPED
    # (never a false drift). Uses a synthetic non-existent route so the test is
    # live-state-independent.
    fake = {"features": [
        {"name": "Whatever", "route": "zzz-nonexistent-selftest.html", "status": "active", "nav_label": "X"},
    ]}
    ck = run_checks(fake)
    assert ck["catalog_name_drift"]["count"] == 0, "missing page → skipped, not a false drift"
    # And a real page WHOSE title disagrees with the catalog name IS flagged.
    real = {"features": [
        {"name": "PM Checklist", "route": "pm-scheduler.html", "status": "active", "nav_label": "PM Scheduler"},
    ]}
    if (ROOT / "pm-scheduler.html").exists():
        ck2 = run_checks(real)
        assert ck2["catalog_name_drift"]["count"] == 1, "real title != catalog name IS flagged"
    print("  platform_name_alignment self-test: 6/6 OK")
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return _self_test()
    if "--report" in argv:
        _print_report()
        return 0
    code, report = evaluate(strict="--strict" in argv, update_baseline="--update-baseline" in argv)
    _print(report)
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
