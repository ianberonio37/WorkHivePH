#!/usr/bin/env python3
"""
landing_extractability_gate.py — SEO/AEO/GEO Arc, Phase P2.5 (the LANDING PAGE
extractability scoreboard — the layer the article-level gates missed).

The arc's other gates grade the 38 /learn ARTICLES (extractability_gate) and the
technical hygiene of the static surfaces (seo_technical_gate). NONE of them look
at whether index.html — the ONLY index,follow page on the property — actually
exposes its richest content (the tool catalog) and its internal tool links in the
CRAWLABLE DOM. This gate closes that blind spot.

WHY IT MATTERS (2026 evidence, see SEO_AEO_GEO_100_ARC.md §2026-06-30 extension):
  - Major AI crawlers (GPTBot/ClaudeBot/PerplexityBot/Meta/Bytespider) FETCH JS
    but never EXECUTE it (Vercel/MERJ, 500M+ GPTBot fetches, zero JS execution).
  - Googlebot runs JS but renders only the INITIAL state — it never fires a click
    handler (Google: "Search does not interact with your page"; Martin Splitt).
  => content/links that exist ONLY inside a JS string injected on click (index.html's
     stageData popup) reach NEITHER. But in-DOM display:none content IS crawlable,
     so this gate measures the SCRIPT-STRIPPED HTML — exactly what a crawler sees.

Each check is catalog-/stageData-DERIVED (never hand-listed) and ratcheted
forward-only (same convention as seo_technical_gate.py / content_grounding_gate.py).

  tool_page_links       every ACTIVE catalog tool page (route, excl index.html) has
                        >=1 real <a href> to it in the script-stripped static DOM
  popup_tool_copy       every stageData popup tool's NAME appears as crawlable text
                        (not only inside the <script> that builds the popup)
  popup_tool_links      every stageData popup tool's link: target is a real <a href>
                        in the script-stripped static DOM (not only a JS string)
  featurelist_jsonld    SoftwareApplication JSON-LD carries a featureList (machine-
                        readable tool set, independent of JS execution)
  count_claim_match     every "N tools/guides/calculators" numeric claim matches the
                        catalog count (adjective-tolerant: "28 free tools")

This gate is DETECTION-ONLY: it READS index.html, it never modifies it. Safe to run
before or after the P2.5 static-catalog render lands; it produces the measured
baseline either way.

CLI:
    python tools/landing_extractability_gate.py            # ratcheted run (exit 1 on NEW drift)
    python tools/landing_extractability_gate.py --strict   # fail on ANY issue > 0
    python tools/landing_extractability_gate.py --update-baseline
    python tools/landing_extractability_gate.py --self-test
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

import platform_catalog as pc  # noqa: E402

BASELINE_PATH = ROOT / "landing_extractability_baseline.json"
REPORT_PATH = ROOT / "landing_extractability_report.json"
LANDING = "index.html"

CHECK_ORDER = ["tool_page_links", "popup_tool_copy", "popup_tool_links",
               "featurelist_jsonld", "count_claim_match"]

_SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE)
# stageData tool entries: { name: '...', desc: '...', link: '...', icon: ... }
# (stage-level `name:` is followed by `quote:`/`label:`, not `desc:`+`link:`, so this
#  matches the 28 TOOL entries only, not the 4 stage names.)
_STAGE_TOOL_RE = re.compile(
    r"name:\s*'([^']+)'\s*,\s*desc:\s*'(?:\\.|[^'\\])*'\s*,\s*link:\s*'([^']+)'",
    re.DOTALL)
# SoftwareApplication featureList (machine-readable tool set)
_SOFTWAREAPP_RE = re.compile(r'"@type"\s*:\s*"SoftwareApplication"')


def _read(rel: str) -> str | None:
    try:
        return (ROOT / rel).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _strip_scripts(html: str) -> str:
    """Return the HTML a non-JS crawler sees: <script> bodies removed.

    display:none / hidden in-DOM markup is KEPT (it is crawlable); only content
    that lives inside <script> string literals (JS-injected on interaction) is
    dropped, because that never reaches the parsed DOM for an AI crawler nor the
    initial-state DOM Googlebot indexes."""
    return _SCRIPT_RE.sub("", html)


def _has_anchor_to(dom: str, route: str) -> bool:
    """True if the script-stripped DOM has a real <a ... href="...route">.

    Matches href="route", "/route", "/workhive/route", etc. — the filename as a
    path terminus, so analytics.html does not match analytics-report.html."""
    pat = re.compile(
        r'<a\b[^>]*\bhref\s*=\s*["\'](?:[^"\']*/)?' + re.escape(route) + r'["\']',
        re.IGNORECASE)
    return bool(pat.search(dom))


def _catalog_tool_routes(cat: dict) -> list[str]:
    """ACTIVE catalog features that own a real page route, excluding index.html.
    De-duped, ordered — catalog-derived so a new tool flows in automatically."""
    seen, out = set(), []
    for f in cat.get("features", []):
        route = (f.get("route") or "").strip()
        if not route or route == "index.html":
            continue
        if f.get("status") != "active":
            continue
        if route not in seen:
            seen.add(route)
            out.append(route)
    return out


def run_checks(cat: dict | None = None, html: str | None = None) -> dict:
    cat = cat or pc.build_catalog()
    if html is None:
        html = _read(LANDING) or ""
    dom = _strip_scripts(html)
    checks: dict[str, dict] = {k: {"count": 0, "issues": []} for k in CHECK_ORDER}

    # 1 — every active catalog tool page has a crawlable <a href> in the DOM
    for route in _catalog_tool_routes(cat):
        if not _has_anchor_to(dom, route):
            checks["tool_page_links"]["issues"].append(
                {"route": route,
                 "reason": f"tool page '{route}' has NO crawlable <a href> in index.html's "
                           f"static DOM (only reachable via JS/onclick) — invisible to AI crawlers"})

    # 2/3 — stageData popup tools: name as crawlable text + link as real anchor
    popup = _STAGE_TOOL_RE.findall(html)
    for name, link in popup:
        if name and name not in dom:
            checks["popup_tool_copy"]["issues"].append(
                {"tool": name,
                 "reason": f"popup tool '{name}' appears only inside the stageData <script>; "
                           f"its name/description is not in the crawlable DOM"})
        if link and not _has_anchor_to(dom, link.strip("/")):
            checks["popup_tool_links"]["issues"].append(
                {"tool": name, "link": link,
                 "reason": f"popup tool '{name}' links to '{link}' only as a JS string; "
                           f"no crawlable <a href> to it in the static DOM"})

    # 4 — SoftwareApplication featureList present AND covers the stageData tools
    #     (machine-readable tool set; drift-guarded against the popup it mirrors)
    if _SOFTWAREAPP_RE.search(html):
        fl = re.search(r'"featureList"\s*:\s*\[(.*?)\]', html, re.DOTALL)
        if not fl:
            checks["featurelist_jsonld"]["issues"].append(
                {"reason": "SoftwareApplication JSON-LD has no featureList — the tool set is not "
                           "machine-readable without executing JS"})
        else:
            listed = set(re.findall(r'"((?:\\.|[^"\\])*)"', fl.group(1)))
            # featureList must COVER the catalog's active features (the truth set —
            # derived from the real pages). content_grounding_gate.schema_featurelist
            # checks the reverse (every featureList item resolves to a catalog
            # feature), so together they pin featureList == catalog active features.
            cat_features = [f.get("name") for f in cat.get("features", [])
                            if f.get("status") == "active" and (f.get("route") or "") != "index.html"]
            for nm in cat_features:
                if nm and nm not in listed:
                    checks["featurelist_jsonld"]["issues"].append(
                        {"feature": nm,
                         "reason": f"featureList is missing catalog feature '{nm}' — drift from "
                                   f"the catalog (every active feature must be listed)"})

    # 5 — numeric "N tools|guides|calculators" claims match the catalog (adjective-tolerant)
    n_articles = len(cat.get("articles", []))
    n_tools = len(_catalog_tool_routes(cat))
    expect = {"guides": n_articles, "guide": n_articles,
              "articles": n_articles, "article": n_articles}
    dom_text = re.sub(r"<[^>]+>", " ", dom)
    # number, up to 3 marketing adjectives, then the noun:  "38 in-depth practical guides"
    for m in re.finditer(r"\b(\d{1,3})\s+(?:[a-z][a-z\-]+\s+){0,3}(guides?|articles?)\b",
                         dom_text, re.IGNORECASE):
        claimed, noun = int(m.group(1)), m.group(2).lower()
        want = expect.get(noun)
        if want is not None and claimed != want:
            checks["count_claim_match"]["issues"].append(
                {"claim": m.group(0).strip(), "expected": want,
                 "reason": f"count claim '{m.group(0).strip()}' != catalog {noun} count ({want})"})

    for k in CHECK_ORDER:
        checks[k]["count"] = len(checks[k]["issues"])
    return checks


# ── Ratchet engine (forward-only; mirrors seo_technical_gate.py) ───────────────

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


def _print(report: dict):
    def c(code, s): return f"\033[{code}m{s}\033[0m"
    print(c("96", "\n  LANDING EXTRACTABILITY GATE (P2.5) · ratchet"))
    print("  " + "=" * 62)
    for r in report["checks"]:
        col = "91" if r["status"] == "FAIL" else ("92" if r["status"] == "OK" else "93")
        print(f"    {c(col, r['status'].ljust(4))} {r['check']:<18} current={r['current']}  baseline={r['baseline']}")
        for i in r["issues"][:4]:
            print(f"          - {i['reason']}")
        if len(r["issues"]) > 4:
            print(f"          ... +{len(r['issues']) - 4} more")
    print("  " + "-" * 62)
    print(f"    total issues: {report['total_issues']}   failed: {report['failed_checks'] or 'none'}\n")


# ── Self-test (no live state needed; synthetic HTML proves each check) ─────────

def _self_test() -> int:
    fake_cat = {
        "articles": [{"slug": f"a{i}", "url": f"/learn/a{i}/"} for i in range(38)],
        "features": [
            {"id": "logbook", "name": "Logbook", "route": "logbook.html", "status": "active"},
            {"id": "pm", "name": "PM", "route": "pm-scheduler.html", "status": "active"},
            {"id": "old", "name": "Old", "route": "old.html", "status": "deprecated"},
            {"id": "intel", "name": "Intel", "route": None, "status": "active"},
            {"id": "home", "name": "Home", "route": "index.html", "status": "active"},
        ],
    }
    # routes should be: logbook.html, pm-scheduler.html  (excl deprecated/None/index)
    assert _catalog_tool_routes(fake_cat) == ["logbook.html", "pm-scheduler.html"], "route derivation"

    # GOOD page: both tool links crawlable (one in a display:none block — still counts),
    # popup names present in DOM, featureList present, count correct.
    good = """
    <html><head>
      <script type="application/ld+json">{"@type":"SoftwareApplication","featureList":["Logbook","PM","Intel"]}</script>
    </head><body>
      <footer><a href="/logbook.html">Logbook</a></footer>
      <div id="ops-home" style="display:none"><a href="pm-scheduler.html">PM Scheduler</a></div>
      <p>Logbook</p><p>PM Scheduler</p>
      <span>38 in-depth guides</span>
      <script>
        const stageData = { 1: { name:'Stage 1', quote:'q', tools:[
          { name: 'Logbook', desc: 'log it', link: 'logbook.html', icon: 'M1' },
          { name: 'PM Scheduler', desc: 'plan it', link: 'pm-scheduler.html', icon: 'M2' },
        ]}};
      </script>
    </body></html>"""
    ck = run_checks(fake_cat, good)
    assert ck["tool_page_links"]["count"] == 0, ("good tool_page_links", ck["tool_page_links"])
    assert ck["popup_tool_copy"]["count"] == 0, ("good popup_tool_copy", ck["popup_tool_copy"])
    assert ck["popup_tool_links"]["count"] == 0, ("good popup_tool_links", ck["popup_tool_links"])
    assert ck["featurelist_jsonld"]["count"] == 0, "good featurelist"
    assert ck["count_claim_match"]["count"] == 0, ("good count", ck["count_claim_match"])

    # BAD page: catalog/popup content lives ONLY in the <script>; no featureList;
    # wrong count claim.
    bad = """
    <html><head>
      <script type="application/ld+json">{"@type":"SoftwareApplication","name":"WorkHive"}</script>
    </head><body>
      <h1>Access Your Memory</h1>
      <span>24 in-depth guides</span>
      <script>
        const stageData = { 1: { name:'Stage 1', quote:'q', tools:[
          { name: 'Logbook', desc: 'log it', link: 'logbook.html', icon: 'M1' },
          { name: 'PM Scheduler', desc: 'plan it', link: 'pm-scheduler.html', icon: 'M2' },
        ]}};
        grid.innerHTML = '<a href="logbook.html">x</a>';
      </script>
    </body></html>"""
    ck = run_checks(fake_cat, bad)
    assert ck["tool_page_links"]["count"] == 2, ("bad tool_page_links", ck["tool_page_links"]["count"])
    assert ck["popup_tool_copy"]["count"] == 2, ("bad popup_tool_copy", ck["popup_tool_copy"]["count"])
    assert ck["popup_tool_links"]["count"] == 2, ("bad popup_tool_links", ck["popup_tool_links"]["count"])
    assert ck["featurelist_jsonld"]["count"] == 1, "bad featurelist"
    assert ck["count_claim_match"]["count"] == 1, ("bad count", ck["count_claim_match"]["count"])

    print("  landing_extractability_gate self-test: 10/10 OK")
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return _self_test()
    strict = "--strict" in argv
    update = "--update-baseline" in argv
    code, report = evaluate(strict=strict, update_baseline=update)
    _print(report)
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
