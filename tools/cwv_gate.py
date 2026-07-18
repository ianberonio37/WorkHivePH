#!/usr/bin/env python3
# DEEPWALK-CELL: * D6
# DEEPWALK-CELL: content:* D6
"""
cwv_gate.py — SEO/AEO/GEO Arc, Phase P3 (the Core Web Vitals scoreboard).

The fast, ratcheted HALF of a two-tool scorer (the perf-skill pattern: a slow
live probe writes measurements, a fast gate ratchets them — like
perf_scale_sweep.mjs + mine_perf_scale_surfaces.py):

  - tools/cwv_probe.mjs     LIVE measurement (headless mobile Chromium across the
                            public surfaces; median-of-3; TRUSTED INP click; writes
                            cwv_measurements.json). Slow (~minutes) — run on demand.
  - tools/cwv_gate.py       THIS — reads cwv_measurements.json, counts pages over
                            the 2026 "good" thresholds, ratchets forward-only.
                            Sub-second; safe to register in run_platform_checks.

2026 "good" CWV thresholds (web.dev, 75th-pct mobile):
  LCP <= 2500 ms · INP <= 200 ms · CLS <= 0.1

Checks (each forward-only ratcheted, same convention as seo_technical_gate.py):
  lcp_over    pages whose median LCP exceeds 2500 ms
  inp_over    pages whose median (measured) INP exceeds 200 ms
  cls_over    pages whose median CLS exceeds 0.1
  coverage    expected public surfaces (catalog-derived) the probe did NOT measure
              — a probe that silently skips pages must not earn a free pass

HONESTY (perf-skill lessons, 2026-06-22):
  - LOCAL LCP is OPTIMISTIC vs PH-4G prod (a local pass is necessary-not-sufficient);
    the measurements stamp env:"local" / lcp_local_optimistic:true and this gate
    echoes it. True field CWV is Layer B.
  - INP needs a TRUSTED interaction; the probe drives a real mouse click. A page with
    no measurable INP is stamped inp_measured:false and surfaced explicitly here —
    never silently pass-credited as "INP good".

Surface list is DERIVED FROM THE CATALOG (reuses seo_technical_gate.indexable_pages)
— never hand-listed — so a new /learn article is covered automatically.

CLI:
    python tools/cwv_gate.py            # ratcheted run (exit 1 on NEW regression)
    python tools/cwv_gate.py --strict   # fail on ANY page over threshold
    python tools/cwv_gate.py --update-baseline
    python tools/cwv_gate.py --self-test
"""
from __future__ import annotations

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

# Reuse the canonical public-surface list (one source of truth across the SEO gates).
from seo_technical_gate import indexable_pages  # noqa: E402

BASELINE_PATH = ROOT / "cwv_baseline.json"
REPORT_PATH = ROOT / "cwv_report.json"
MEASUREMENTS_PATH = ROOT / "cwv_measurements.json"

CHECK_ORDER = ["lcp_over", "inp_over", "cls_over", "coverage"]

# 2026 "good" thresholds (web.dev), 75th-pct mobile.
LCP_MS = 2500
INP_MS = 200
CLS = 0.1

# A measurements file older than this many days is stale (informational warning).
STALE_DAYS = 21


def _load_measurements() -> dict | None:
    if MEASUREMENTS_PATH.exists():
        try:
            return json.loads(MEASUREMENTS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def run_checks(measurements: dict | None = None, expected: list[str] | None = None) -> dict:
    """Compute issue counts per check from a measurements dict.

    measurements: {"pages":[{"surface","lcp_ms","inp_ms","inp_measured","cls"}...], ...}
    expected:     the catalog-derived list of public surface paths the probe SHOULD cover.
    Both are injectable for a live-state-independent self-test.
    """
    if expected is None:
        expected = indexable_pages()
    checks = {k: {"count": 0, "issues": []} for k in CHECK_ORDER}

    pages = list((measurements or {}).get("pages", []))
    measured_by_surface = {p.get("surface"): p for p in pages if p.get("surface")}

    # coverage — every expected surface must have been measured
    for surf in expected:
        if surf not in measured_by_surface:
            checks["coverage"]["issues"].append(
                {"page": surf, "reason": f"{surf} was not measured by the CWV probe (run tools/cwv_probe.mjs)"}
            )
    checks["coverage"]["count"] = len(checks["coverage"]["issues"])

    # per-page threshold checks
    for p in pages:
        surf = p.get("surface") or p.get("url") or "?"
        lcp = p.get("lcp_ms")
        if isinstance(lcp, (int, float)) and lcp > LCP_MS:
            checks["lcp_over"]["issues"].append(
                {"page": surf, "reason": f"LCP {round(lcp)}ms > {LCP_MS}ms"}
            )
        inp = p.get("inp_ms")
        if p.get("inp_measured") and isinstance(inp, (int, float)) and inp > INP_MS:
            checks["inp_over"]["issues"].append(
                {"page": surf, "reason": f"INP {round(inp)}ms > {INP_MS}ms"}
            )
        cls = p.get("cls")
        if isinstance(cls, (int, float)) and cls > CLS:
            checks["cls_over"]["issues"].append(
                {"page": surf, "reason": f"CLS {round(cls, 3)} > {CLS}"}
            )
    for k in ("lcp_over", "inp_over", "cls_over"):
        checks[k]["count"] = len(checks[k]["issues"])

    return checks


def _load_baseline() -> dict:
    if BASELINE_PATH.exists():
        try:
            return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _measurements_meta(measurements: dict | None) -> dict:
    """Surface the env caveat + staleness + unmeasured-INP pages — never silent."""
    meta: dict = {"measurements_present": measurements is not None}
    if not measurements:
        return meta
    meta["env"] = measurements.get("env", "unknown")
    meta["lcp_local_optimistic"] = bool(measurements.get("lcp_local_optimistic"))
    meta["generated_at"] = measurements.get("generated_at")
    # stale?
    ga = measurements.get("generated_at")
    if ga:
        try:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(ga.replace("Z", "+00:00"))
            meta["age_days"] = round(age.total_seconds() / 86400, 1)
            meta["stale"] = age.days >= STALE_DAYS
        except Exception:
            pass
    # INP that could not be measured (stamped, NOT pass-credited)
    unmeasured = [p.get("surface") for p in measurements.get("pages", []) if not p.get("inp_measured")]
    meta["inp_unmeasured"] = unmeasured
    return meta


def evaluate(strict: bool = False, update_baseline: bool = False,
             measurements: dict | None = None) -> tuple[int, dict]:
    if measurements is None:
        measurements = _load_measurements()
    checks = run_checks(measurements)
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
        rows.append({
            "check": name,
            "current": cur,
            "baseline": 0 if strict else ratcheted,
            "status": "FAIL" if failing else ("OK" if cur == 0 else "HELD"),
            "issues": checks[name]["issues"],
        })
    total = sum(checks[n]["count"] for n in CHECK_ORDER)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "strict" if strict else "ratchet",
        "thresholds": {"lcp_ms": LCP_MS, "inp_ms": INP_MS, "cls": CLS},
        "total_issues": total,
        "failed_checks": fails,
        "measurements": _measurements_meta(measurements),
        "checks": rows,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if not strict:
        est = _load_baseline().get("established")
        BASELINE_PATH.write_text(json.dumps({
            "checks": new_base,
            "established": est or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "last_run": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }, indent=2), encoding="utf-8")
    elif update_baseline:
        BASELINE_PATH.write_text(json.dumps({
            "checks": {n: checks[n]["count"] for n in CHECK_ORDER},
            "established": _load_baseline().get("established")
                or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "last_run": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }, indent=2), encoding="utf-8")
    return (1 if fails else 0), report


def _print(report: dict) -> None:
    def c(code, s):
        return f"\033[{code}m{s}\033[0m"

    print(c("96", "\n  CORE WEB VITALS GATE (P3) · " + report["mode"]))
    print("  " + "=" * 62)
    m = report.get("measurements", {})
    if not m.get("measurements_present"):
        print(c("93", "    NO MEASUREMENTS — run:  node tools/cwv_probe.mjs"))
        print(c("90", "    (the gate ratchets the LAST probe; with none, only coverage is flagged)"))
    else:
        env = m.get("env", "?")
        opt = " · LCP optimistic vs PH-4G prod (local pass = necessary-not-sufficient)" if m.get("lcp_local_optimistic") else ""
        age = f" · {m.get('age_days')}d old" if m.get("age_days") is not None else ""
        print(c("90", f"    env={env}{opt}{age}"))
        if m.get("stale"):
            print(c("93", f"    STALE measurements (>{STALE_DAYS}d) — re-run tools/cwv_probe.mjs"))
        if m.get("inp_unmeasured"):
            print(c("90", f"    INP unmeasured on {len(m['inp_unmeasured'])} page(s) (stamped, not pass-credited): "
                          + ", ".join(m["inp_unmeasured"][:4]) + (" …" if len(m["inp_unmeasured"]) > 4 else "")))
    th = report.get("thresholds", {})
    print(c("90", f"    thresholds: LCP<={th.get('lcp_ms')}ms · INP<={th.get('inp_ms')}ms · CLS<={th.get('cls')}"))
    print("  " + "-" * 62)
    for r in report["checks"]:
        col = "91" if r["status"] == "FAIL" else ("92" if r["status"] == "OK" else "93")
        print(f"    {c(col, r['status'].ljust(4))} {r['check']:<10} current={r['current']}  baseline={r['baseline']}")
        for i in r["issues"][:5]:
            print(c("90", f"          - {i['page']}: {i['reason']}"))
        if len(r["issues"]) > 5:
            print(c("90", f"          … +{len(r['issues']) - 5} more"))
    n = len(report["failed_checks"])
    print(c("92", "\n  PASS — no check over baseline.\n") if n == 0
          else c("91", f"\n  FAIL — {n} check(s) over baseline: {', '.join(report['failed_checks'])}\n"))


def self_test() -> int:
    fails = 0

    def ck(cond, msg):
        nonlocal fails
        print(("  \033[92mPASS\033[0m  " if cond else "  \033[91mFAIL\033[0m  ") + msg)
        if not cond:
            fails += 1

    print("\n\033[1mcwv_gate.py --self-test\033[0m")
    print("=" * 60)

    # Synthetic, live-state-INDEPENDENT fixtures.
    expected = ["index.html", "learn/a/index.html", "learn/b/index.html", "learn/c/index.html"]

    clean = {
        "env": "local", "lcp_local_optimistic": True,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pages": [
            {"surface": "index.html",       "lcp_ms": 1200, "inp_ms": 80,  "inp_measured": True, "cls": 0.02},
            {"surface": "learn/a/index.html", "lcp_ms": 1800, "inp_ms": 120, "inp_measured": True, "cls": 0.05},
            {"surface": "learn/b/index.html", "lcp_ms": 900,  "inp_ms": 60,  "inp_measured": True, "cls": 0.00},
            {"surface": "learn/c/index.html", "lcp_ms": 2000, "inp_ms": 0,   "inp_measured": False, "cls": 0.09},
        ],
    }
    c1 = run_checks(clean, expected)
    ck(all(c1[k]["count"] == 0 for k in CHECK_ORDER), "all-good measurements → 0 issues across all checks")
    ck(c1["coverage"]["count"] == 0, "full coverage → coverage 0")

    bad = {
        "env": "local",
        "pages": [
            {"surface": "index.html",       "lcp_ms": 4200, "inp_ms": 90,  "inp_measured": True, "cls": 0.02},  # LCP over
            {"surface": "learn/a/index.html", "lcp_ms": 1500, "inp_ms": 350, "inp_measured": True, "cls": 0.03},  # INP over
            {"surface": "learn/b/index.html", "lcp_ms": 1500, "inp_ms": 80,  "inp_measured": True, "cls": 0.42},  # CLS over
            # learn/c MISSING → coverage flags 1
        ],
    }
    c2 = run_checks(bad, expected)
    ck(c2["lcp_over"]["count"] == 1, "one page LCP>2500 → lcp_over flags 1")
    ck(c2["inp_over"]["count"] == 1, "one page INP>200 → inp_over flags 1")
    ck(c2["cls_over"]["count"] == 1, "one page CLS>0.1 → cls_over flags 1")
    ck(c2["coverage"]["count"] == 1, "a missing surface → coverage flags 1")

    # INP must NOT be pass-credited when unmeasured (a high inp_ms with inp_measured:False is ignored, not failed)
    unmeasured_high = {"pages": [{"surface": "index.html", "lcp_ms": 1000, "inp_ms": 999, "inp_measured": False, "cls": 0.0}]}
    c3 = run_checks(unmeasured_high, ["index.html"])
    ck(c3["inp_over"]["count"] == 0, "inp_measured:False with high inp_ms → NOT counted (no false-fail)")
    meta = _measurements_meta(unmeasured_high)
    ck(meta.get("inp_unmeasured") == ["index.html"], "unmeasured INP is STAMPED in meta (not silent)")

    # Missing measurements file → coverage = all expected, others 0, meta flags absence
    c4 = run_checks(None, expected)
    ck(c4["coverage"]["count"] == len(expected), "no measurements → coverage flags every expected surface")
    ck(all(c4[k]["count"] == 0 for k in ("lcp_over", "inp_over", "cls_over")), "no measurements → no false threshold fails")
    ck(_measurements_meta(None)["measurements_present"] is False, "absent measurements → meta says not present")

    # Thresholds are the 2026 'good' values
    ck((LCP_MS, INP_MS, CLS) == (2500, 200, 0.1), "thresholds are the 2026 good values (2500/200/0.1)")

    # Surface list is catalog-derived (live) — not a hand-list
    try:
        live = indexable_pages()
        ck(len(live) >= 30 and any(p.startswith("learn/") for p in live),
           f"surface list is catalog-derived ({len(live)} pages)")
    except Exception as e:
        ck(False, f"indexable_pages() callable — {e}")

    print("=" * 60)
    print("\033[92m  self-test PASS\033[0m\n" if not fails else f"\033[91m  self-test FAIL — {fails}\033[0m\n")
    return 1 if fails else 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    if "--surfaces" in argv:
        # Emit the canonical catalog-derived public surface list (one source of truth
        # shared with tools/cwv_probe.mjs, which navigates to each).
        print(json.dumps(indexable_pages()))
        return 0
    rc, report = evaluate(strict="--strict" in argv, update_baseline="--update-baseline" in argv)
    _print(report)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
