#!/usr/bin/env python3
"""
seo_technical_gate.py — SEO/AEO/GEO Arc, Phase P1 (the SEO technical scoreboard).

The semantic layer validate_seo.py lacks. validate_seo.py checks PRESENCE
(noindex / title / canonical / meta / OG / a JSON-LD block exists). This gate adds
the 2026-research on-page technical levers it does NOT cover, each ratcheted
forward-only (same convention as content_grounding_gate.py):

  one_h1          every indexable page has EXACTLY one <h1> (heading hierarchy)
  img_alt         every <img> carries an alt attribute (accessibility + image SEO)
  jsonld_valid    every <script type="application/ld+json"> block PARSES as valid
                  JSON (validate_seo.py only checks the block exists, not that it
                  is well-formed — a malformed block earns 0 rich results silently)
  retired_schema  a page must NOT rely on FAQPage/HowTo rich-result types, which
                  Google retired (HowTo 2023, FAQ 2026-05-07) — keep the Q&A as
                  body content, not as a dead rich-result bet (2026 research)

Surface list is DERIVED FROM THE CATALOG (platform_catalog.build_catalog) — never
hand-listed — so a new /learn article is covered automatically. (validate_seo.py's
hand-kept LEARN_PAGES had silently drifted to 28 while 38 articles were live; this
gate cannot drift that way.)

CLI:
    python tools/seo_technical_gate.py            # ratcheted run (exit 1 on NEW drift)
    python tools/seo_technical_gate.py --strict   # fail on ANY issue > 0
    python tools/seo_technical_gate.py --update-baseline
    python tools/seo_technical_gate.py --self-test
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

BASELINE_PATH = ROOT / "seo_technical_baseline.json"
REPORT_PATH = ROOT / "seo_technical_report.json"

CHECK_ORDER = ["one_h1", "img_alt", "jsonld_valid", "retired_schema"]

# Non-article public surfaces (the indexable static pages). The 38 learn articles
# are derived from the catalog and appended — never hand-listed.
STATIC_PUBLIC = [
    "index.html", "learn/index.html",
    "about/index.html", "privacy-policy/index.html", "terms-of-service/index.html",
]

_LDJSON_RE = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.DOTALL | re.IGNORECASE)
_H1_RE = re.compile(r"<h1\b", re.IGNORECASE)
_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)


def indexable_pages(cat: dict | None = None) -> list[str]:
    """The indexable public surfaces, DERIVED from the catalog (+ the static set).
    A new /learn article flows in automatically — no hand-maintained list to rot."""
    cat = cat or pc.build_catalog()
    pages = list(STATIC_PUBLIC)
    for a in cat.get("articles", []):
        url = (a.get("url") or "").strip("/")
        if url.startswith("learn/"):
            pages.append(f"{url}/index.html")
    # de-dup, keep order
    seen, out = set(), []
    for p in pages:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _read(rel: str) -> str | None:
    try:
        return (ROOT / rel).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def run_checks(cat: dict | None = None) -> dict:
    cat = cat or pc.build_catalog()
    pages = indexable_pages(cat)
    checks: dict[str, dict] = {k: {"count": 0, "issues": []} for k in CHECK_ORDER}

    for page in pages:
        html = _read(page)
        if html is None:
            continue

        # one_h1 — exactly one <h1>
        n_h1 = len(_H1_RE.findall(html))
        if n_h1 != 1:
            checks["one_h1"]["issues"].append(
                {"page": page, "reason": f"{page} has {n_h1} <h1> (must be exactly 1 for heading hierarchy)"})

        # img_alt — every <img> has an alt attribute
        for img in _IMG_RE.findall(html):
            if not re.search(r"\balt\s*=", img, re.IGNORECASE):
                checks["img_alt"]["issues"].append(
                    {"page": page, "reason": f"{page} has an <img> with no alt attribute: {img[:80]}"})

        # jsonld_valid — every ld+json block parses
        for m in _LDJSON_RE.finditer(html):
            block = m.group(1).strip()
            try:
                json.loads(block)
            except json.JSONDecodeError as exc:
                checks["jsonld_valid"]["issues"].append(
                    {"page": page, "reason": f"{page} has a malformed JSON-LD block ({exc}); earns 0 rich results"})

        # retired_schema — must not rely on FAQPage/HowTo rich-result types (retired)
        for t in ("FAQPage", "HowTo"):
            if re.search(rf'"@type"\s*:\s*"{t}"', html):
                checks["retired_schema"]["issues"].append(
                    {"page": page, "reason": f"{page} declares retired rich-result @type '{t}' "
                                             f"(HowTo retired 2023, FAQ 2026-05-07); keep the Q&A as body content"})

    for k in CHECK_ORDER:
        checks[k]["count"] = len(checks[k]["issues"])
    return checks


# ── Ratchet engine (forward-only; mirrors content_grounding_gate.py) ───────────

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
    from datetime import datetime, timezone
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
    print(c("96", "\n  SEO TECHNICAL GATE (P1) · ratchet"))
    print("  " + "=" * 60)
    for r in report["checks"]:
        col = "91" if r["status"] == "FAIL" else ("92" if r["status"] == "OK" else "93")
        print(f"    {c(col, r['status'].ljust(4))} {r['check']:<16} current={r['current']}  baseline={r['baseline']}")
        for i in r["issues"][:4]:
            print(f"          - {i['reason']}")
        if len(r["issues"]) > 4:
            print(f"          … +{len(r['issues']) - 4} more")
    n = len(report["failed_checks"])
    print(c("92", f"\n  PASS — no check over baseline (total issues recorded: {report['total_issues']}).\n") if n == 0
          else c("91", f"\n  FAIL — {n} check(s) over baseline: {', '.join(report['failed_checks'])}\n"))


# ── Self-test (synthetic, live-state-INDEPENDENT) ──────────────────────────────

def self_test() -> int:
    fails = 0

    def ck(cond, msg):
        nonlocal fails
        print(("  \033[92mPASS\033[0m  " if cond else "  \033[91mFAIL\033[0m  ") + msg)
        if not cond:
            fails += 1

    print("\n\033[1mseo_technical_gate.py --self-test\033[0m")
    print("=" * 55)

    # Synthetic fixtures exercise each check directly (no reliance on live state).
    good = '<html><h1>One</h1><img src="a.png" alt="a"><script type="application/ld+json">{"@type":"Organization"}</script></html>'
    bad = '<html><h1>A</h1><h1>B</h1><img src="b.png"><script type="application/ld+json">{bad json}</script>' \
          '<script type="application/ld+json">{"@type":"FAQPage"}</script></html>'

    saved = globals().get("_read")
    globals()["_read"] = lambda rel: {"_good": good, "_bad": bad}.get(rel)
    saved_idx = globals().get("indexable_pages")
    try:
        globals()["indexable_pages"] = lambda cat=None: ["_good"]
        c1 = run_checks({"articles": []})
        ck(all(c1[k]["count"] == 0 for k in CHECK_ORDER), "clean page → 0 issues across all checks")

        globals()["indexable_pages"] = lambda cat=None: ["_bad"]
        c2 = run_checks({"articles": []})
        ck(c2["one_h1"]["count"] == 1, "two <h1> → one_h1 flags")
        ck(c2["img_alt"]["count"] == 1, "<img> without alt → img_alt flags")
        ck(c2["jsonld_valid"]["count"] == 1, "malformed JSON-LD → jsonld_valid flags")
        ck(c2["retired_schema"]["count"] == 1, "FAQPage @type → retired_schema flags")
    finally:
        globals()["_read"] = saved
        globals()["indexable_pages"] = saved_idx

    # Live: the surface list is catalog-derived and includes the learn articles.
    live_pages = indexable_pages()
    ck(len(live_pages) >= 30 and any(p.startswith("learn/") for p in live_pages),
       f"surface list is catalog-derived ({len(live_pages)} indexable pages, articles included)")

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
