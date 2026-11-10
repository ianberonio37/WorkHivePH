#!/usr/bin/env python3
"""validate_retired_predictive_not_described.py - no shipped page sells the retired predictive dashboard
(gate retired-predictive-not-described, 2026-11-10).

★A PAGE RETIRED IN JUNE WAS STILL SOLD IN NOVEMBER (found rewriting the Asset Brain 360 guide, Wave CF M13).
predictive.html was retired on 2026-06-10: per-asset risk moved to Asset Hub (the asset list's risk band and each asset's
Risk Profile card, both from v_risk_truth) and the failure-trend forecast to Analytics' Predictive phase. Nothing on
the platform draws a "Health Heatmap", a fleet "Risk Ranking" dashboard or a 0-100 health score. Yet the landing page
(twice), the assistant's and the companion's platform knowledge, and the Asset Brain guide (three times) still described
that dashboard - the AI told users to open a page that is gone.

The check keys on the page actually being gone: while predictive.html is not served, a shipped sentence that names the
Health Heatmap, a 0-100 health score, or predictive.html as a live page fails. If the page ever comes back, the gate
passes again. A path in a script's list of app routes is not a description and is not judged.

    python tools/validate_retired_predictive_not_described.py [--self-test]
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SKIP = ("tools/", "tests/", "test-data-seeder/", "_fixtures/", "node_modules/", ".claude/", "supabase/", ".tmp/")
CLAIMS = [
    re.compile(r"\bHealth\s+Heatmap\b(?![^.<\n]{0,60}\b(?:no|retired|gone)\b)", re.I),
    re.compile(r"\(predictive\.html\):\s*Asset risk dashboard", re.I),
    re.compile(r"\bscores?\s+0\s*(?:to|-)\s*100\b[^.<\n]{0,80}\bevery asset\b", re.I),
]
NEGATED = re.compile(r"\b(?:no|retired|not|gone|There is no)\b[^.<\n]{0,40}$", re.I)


def page_is_gone() -> bool:
    return not (ROOT / "predictive.html").exists()


def check_text(src: str) -> list[str]:
    out = []
    for rx in CLAIMS:
        for m in rx.finditer(src):
            if NEGATED.search(src[max(0, m.start() - 50):m.start()]):
                continue
            out.append(repr(src[max(0, m.start() - 60):m.end() + 40].replace("\n", " ")))
    return out


def shipped() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "*.html", "*.js", "*.txt", "*.md"], cwd=ROOT, capture_output=True,
                         text=True).stdout.split()
    keep = []
    for p in out:
        if p.startswith(SKIP) or "survey_ufai_rubric" in p:
            continue
        if p.endswith(".md") and not p.endswith(".html.md"):
            continue
        keep.append(ROOT / p)
    return keep


def _self_test() -> int:
    bad = [
        "Predictive Maintenance: Risk Ranking, Health Heatmap, Failure Trend forecast.",
        "- Predictive Maintenance (predictive.html): Asset risk dashboard: Risk Ranking (critical/high/medium/low per asset)",
        "They live on Predictive Maintenance, which scores 0 to 100 and ranks every asset in the hive against every other.",
    ]
    good = [
        "the failure-trend forecast is Analytics' Predictive phase. There is no Health Heatmap.",
        "'/ph-intelligence.html', '/predictive.html', '/ai-quality.html',",
        "A risk band on every asset in Asset Hub, and a failure-trend forecast in Analytics.",
    ]
    fails = [("must fail: " + s[:50]) for s in bad if not check_text(s)]
    fails += [("must pass: " + s[:50]) for s in good if check_text(s)]
    print("FAIL retired-predictive-not-described self-test - " + "; ".join(fails) if fails
          else f"self-test OK: {len(bad)} descriptions of the retired dashboard fail, {len(good)} true lines pass")
    return 1 if fails else 0


def main() -> int:
    if "--self-test" in sys.argv:
        return _self_test()
    if not page_is_gone():
        print("PASS retired-predictive-not-described - predictive.html is served again, so describing it is not false")
        return 0
    hits = {}
    for p in shipped():
        try:
            errs = check_text(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if errs:
            hits[p.relative_to(ROOT).as_posix()] = errs
    for f, errs in sorted(hits.items()):
        for e in errs[:3]:
            print(f"  BAD {f}: {e[:220]}")
    if hits:
        print(f"FAIL retired-predictive-not-described - {sum(len(v) for v in hits.values())} sentence(s) in {len(hits)} "
              "file(s) describe the retired predictive dashboard (Health Heatmap / 0-100 / predictive.html)")
        return 1
    print("PASS retired-predictive-not-described - no shipped page describes the retired predictive dashboard; risk is "
          "described where it lives (Asset Hub's risk bands, Analytics' Predictive phase)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
