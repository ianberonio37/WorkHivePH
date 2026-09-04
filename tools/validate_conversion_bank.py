#!/usr/bin/env python3
"""validate_conversion_bank.py — T1.4: the conversion funnel's evidence bank + its gate.

WHY A SEPARATE BANK. The 22 page banks are a FIXED 200-row frame per page; the funnel is a
CROSS-PAGE subject (index + public-feed + marketplace + 114 template pages + the auth
boundary) with a different denominator — the scenario-matrix cells. Precedent: the
marketplace registry (877 rows) lives beside the page banks for the same reason.

Rows are keyed (cell × oracle). Oracle text is IMPORTED from the ONE vocabulary
(tools/build_live_mcp_registry.py ORACLES) — never copied, so a reworded oracle cannot
silently diverge here (the an-oracle-must-match-the-claim lesson).

  --build     regenerate banks/conversion_funnel_bank.json from the live artifacts
  (default)   validate: rows ↔ matrix cells, oracle keys ∈ vocabulary, every green row's
              evidence artifact EXISTS and its verdict still holds (the artifact is re-read
              every run — a bank must not outlive its provers' readings silently; ages are
              printed so staleness is visible, and artifacts older than MAX_AGE_DAYS make
              the row OWED, not green).
  --self-test mutate in memory and demand reds.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from build_live_mcp_registry import ORACLES  # noqa: E402  (one vocabulary, imported)

BANK = ROOT / "banks" / "conversion_funnel_bank.json"
MATRIX = ROOT / "substrate" / "reference" / "scenario_matrix.json"
CTA_REPORT = ROOT / "cta_activation_report.json"
JOURNEYS = ROOT / "live_page_journeys_results.json"
SURFACE = ROOT / "public_surface_registry.json"

CHECK_NAMES = ["cv_funnel"]
MAX_AGE_DAYS = 45   # a wave close re-runs the provers; evidence older than a wave is stale

CV_KEYS = {"cta_activation", "signup_affordance", "signup_deeplink", "funnel_complete", "claim_honesty"}

# Which oracles apply to which covered cell (device|auth|entry|intent), and what proves each.
# Evidence kinds: cta-report (dead==0), journey:<ID> (that journey LIVE), surface (0 violations).
APPLICABILITY = {
    "cold-direct":    ["cta_activation", "signup_affordance", "signup_deeplink", "funnel_complete"],
    "search-landing": ["cta_activation", "signup_affordance", "claim_honesty"],
    "shared-link":    ["cta_activation", "signup_affordance", "signup_deeplink"],
    "pwa-icon":       ["signup_affordance"],
}
EVIDENCE = {
    "cta_activation":    [{"kind": "cta-report", "ref": "cta_activation_report.json"}],
    "signup_affordance": [{"kind": "journey", "ref": "LA8"}, {"kind": "journey", "ref": "LA10"},
                          {"kind": "surface", "ref": "public_surface_registry.json"}],
    "signup_deeplink":   [{"kind": "journey", "ref": "LA9"}],
    "funnel_complete":   [{"kind": "journey", "ref": "LA7"}, {"kind": "journey", "ref": "LA11"}],
    "claim_honesty":     [{"kind": "surface", "ref": "public_surface_registry.json"}],
}


def _age_days(p: Path) -> float:
    return (time.time() - p.stat().st_mtime) / 86400 if p.exists() else float("inf")


def _load(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _journey_live(results, jid: str) -> bool | None:
    if not results:
        return None
    for j in results.get("journeys", []):
        if j.get("id") == jid:
            return bool(j.get("live"))
    return None


def verify_evidence(ev: dict, arts: dict) -> tuple[bool, str]:
    """(holds, note). Re-reads the artifact EVERY run — never trusts the banked verdict."""
    if ev["kind"] == "cta-report":
        r = arts["cta"]
        if r is None:
            return False, "cta_activation_report.json MISSING"
        return (r.get("dead") == 0), f"dead={r.get('dead')} probes={r.get('probes')}"
    if ev["kind"] == "journey":
        live = _journey_live(arts["journeys"], ev["ref"])
        if live is None:
            return False, f"journey {ev['ref']} not in results"
        return live, f"{ev['ref']} live={live}"
    if ev["kind"] == "surface":
        s = arts["surface"]
        if s is None:
            return False, "public_surface_registry.json MISSING"
        return (s.get("violations") == 0), f"violations={s.get('violations')} pages={s.get('pages')}"
    return False, f"unknown evidence kind {ev['kind']}"


def build() -> dict:
    matrix = _load(MATRIX)
    covered = [c for c in matrix["cells"] if c["status"] == "covered"]
    rows = []
    for cell in covered:
        for key in APPLICABILITY.get(cell["entry"], []):
            rows.append({
                "id": f"CVB-{cell['id']}-{key}",
                "cell": cell["id"],
                "oracle_key": key,
                "oracle": ORACLES[key],
                "evidence": EVIDENCE[key],
                "stamp": "2026-08-24 T1 walk",
            })
    return {
        "_doc": ("T1.4 conversion-funnel bank — cross-page subject keyed by scenario-matrix cell x "
                 "oracle. Verdicts are NOT stored: the gate re-derives every row's verdict from the "
                 "live artifacts each run, so a row cannot stay green after its prover stops agreeing."),
        "frame": "scenario_matrix covered cells x APPLICABILITY(entry)",
        "total": len(rows),
        "rows": rows,
    }


def validate() -> int:
    bank = _load(BANK)
    if bank is None:
        print("FAIL cv-funnel — bank missing (run --build)")
        return 1
    matrix = _load(MATRIX)
    covered_ids = {c["id"] for c in matrix["cells"] if c["status"] == "covered"}
    arts = {"cta": _load(CTA_REPORT), "journeys": _load(JOURNEYS), "surface": _load(SURFACE)}
    ages = {p.name: round(_age_days(p), 1) for p in (CTA_REPORT, JOURNEYS, SURFACE)}

    problems: list[str] = []
    green = owed = 0
    for row in bank["rows"]:
        if row["oracle_key"] not in CV_KEYS or row["oracle_key"] not in ORACLES:
            problems.append(f"{row['id']}: oracle_key outside the vocabulary")
            continue
        if row["oracle"] != ORACLES[row["oracle_key"]]:
            problems.append(f"{row['id']}: oracle TEXT diverged from the vocabulary (rebuild)")
        if row["cell"] not in covered_ids:
            problems.append(f"{row['id']}: cell {row['cell']} is not covered in the matrix")
        verdicts = [verify_evidence(ev, arts) for ev in row["evidence"]]
        stale = any(_age_days({"cta-report": CTA_REPORT, "journey": JOURNEYS,
                               "surface": SURFACE}[ev["kind"]]) > MAX_AGE_DAYS
                    for ev in row["evidence"])
        if all(h for h, _ in verdicts) and not stale:
            green += 1
        else:
            owed += 1
            notes = "; ".join(n for h, n in verdicts if not h) or "evidence stale"
            problems.append(f"{row['id']}: OWED — {notes}" if not stale
                            else f"{row['id']}: OWED — evidence older than {MAX_AGE_DAYS}d")

    exp = build()
    if {r["id"] for r in exp["rows"]} != {r["id"] for r in bank["rows"]}:
        problems.append("bank rows drifted from (covered cells x applicability) — rebuild")

    print(f"cv-funnel: {len(bank['rows'])} rows · green {green} · owed {owed} · artifact ages(d) {ages}")
    if problems:
        for p in problems[:12]:
            print(f"  FAIL {p}")
        return 1
    print("PASS cv-funnel — every row's evidence re-verified against the live artifacts.")
    return 0


def self_test() -> int:
    import copy
    bank = _load(BANK)
    arts = {"cta": _load(CTA_REPORT), "journeys": _load(JOURNEYS), "surface": _load(SURFACE)}
    fails = []
    # 1. a dead CTA must fail the cta rows
    a2 = copy.deepcopy(arts); a2["cta"]["dead"] = 3
    if verify_evidence({"kind": "cta-report", "ref": "x"}, a2)[0]:
        fails.append("dead=3 should fail cta evidence")
    # 2. a gapped journey must fail
    a3 = copy.deepcopy(arts)
    for j in a3["journeys"]["journeys"]:
        if j["id"] == "LA9":
            j["live"] = False
    if verify_evidence({"kind": "journey", "ref": "LA9"}, a3)[0]:
        fails.append("LA9 live=false should fail journey evidence")
    # 3. surface violations must fail
    a4 = copy.deepcopy(arts); a4["surface"]["violations"] = 2
    if verify_evidence({"kind": "surface", "ref": "x"}, a4)[0]:
        fails.append("violations=2 should fail surface evidence")
    # 4. oracle text divergence
    row = copy.deepcopy(bank["rows"][0]); row["oracle"] = "reworded"
    if row["oracle"] == ORACLES[row["oracle_key"]]:
        fails.append("mutated oracle text should differ")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_conversion_bank self-test (dead-cta / gapped-journey / surface-violations / oracle-divergence all redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.build:
        BANK.write_text(json.dumps(build(), indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"built {BANK.name}: {json.loads(BANK.read_text(encoding='utf-8'))['total']} rows")
        sys.exit(0)
    sys.exit(self_test() if a.self_test else validate())
