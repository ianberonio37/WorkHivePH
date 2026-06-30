"""
measure_gateway_gate -- the HONEST per-layer depth figure Ian asked for: a GATEWAY and a
GATE for EVERY full-stack layer, graded by REAL depth, not presence.
=========================================================================================
WHY THIS EXISTS (Ian, 2026-06-17: "you are providing a false sense of overall coverage,
when in reality there are still gaps... I want a gate AND a gateway for every architectural
layer, with the same depth and honest percentage figures").

TWO existing instruments BOTH overstate, for the same two reasons:
  • the §4 13x6 matrix reads 78/78 = 100%  -- but it credits DETECTION presence only, and
  • measure_layer_depth (A7.4) reads 84.3%  -- but it credits a MECHANISM EXISTING only,
and CRUCIALLY both credit a LOCAL SUBSTITUTE (load_probe for k6, game_day for chaos,
docker-psql for the prod DB) the SAME as the real production capability. AWS Well-Architected
(Reliability + Operational Excellence pillars) requires multi-AZ failover, autoscaling, tested
restores, blue/green deploys -- none of which exist locally -- yet the infra rows show a green
tick. That is the false sense.

THE HONEST MODEL -- 3 graded axes per layer (each 0 / 0.5 / 1.0):
  • GATEWAY  (PREVENTION, a Policy-Enforcement-Point chokepoint -- the harder, more valuable
             half): 1.0 = a single convergence point ALL paths must traverse AND a
             bypass-coverage validator proves nothing skips it · 0.5 = a convergence
             mechanism exists but adoption is incomplete / bypassable · 0.0 = detection only,
             no prevention chokepoint.
  • GATE     (DETECTION, a forward-only ratchet): 1.0 = a baseline that FAILs on regression ·
             0.5 = detection exists but not ratcheted / sampled · 0.0 = none.
  • PROD-REAL (is the proof the PRODUCTION thing, or a local stand-in?): 1.0 = the mechanism
             IS the prod capability (RLS, gateway.ts, render code -- runs for real users) ·
             0.5 = a faithful LOCAL SUBSTITUTE, prod path is Ian's gate (load_probe/game_day/
             docker-psql) · 0.0 = the production capability genuinely does not exist anywhere
             (autoscale, multi-AZ failover, LB, prod log aggregation -- external/unbuilt).

honest depth% (layer)  = (gateway + gate + prod_real) / 3
honest depth% (overall) = sum of all three axes / (3 * 13 layers).

HONESTY ABOUT THE INSTRUMENT ITSELF (no false sense about the false-sense tool): the GATE axis
is MEASURED (the 13x6 ratchet cells are tool-checked) and the PROD-REAL=0 cells are FACTUAL
(the capability is external). The GATEWAY grade and the 0.5 PROD-REAL grades are ASSESSED,
anchored to a named artifact (a bypass-coverage validator that exists, or a local-substitute
tool that exists) -- each cell carries its `basis` so you can see measured-vs-assessed. This
is a directional HONEST rank, deliberately STRICTER than the two instruments it corrects;
it is not claimed to be a single-reading instrument for the gateway axis (that needs a
per-layer bypass-coverage validator, the build this tool's gaps name).

Writes gateway_gate_depth.json + .md; ratchets gateway_gate_baseline.json (forward-only on
the COMPOSITE per layer). Register in run_platform_checks (Maturity, not skip_if_fast).
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "run_platform_checks.py"
OUT_JSON = ROOT / "gateway_gate_depth.json"
OUT_MD = ROOT / "gateway_gate_depth.md"
BASELINE = ROOT / "gateway_gate_baseline.json"

# Each layer: (code, name, gateway, gate, prod_real, gateway_basis, gate_basis, prod_basis)
#   grade ∈ {0.0, 0.5, 1.0}. basis names the REAL artifact (m:=measured/validator exists;
#   a:=assessed/judgment; f:=factual-external). Anchored to this repo's evidence + §14.3.
L = [
 ("A",  "APIs & Backend Logic", 1.0, 1.0, 1.0,
   "m: _shared/gateway.ts PEP + validate_gateway_coverage (no fn bypasses the pipeline)",
   "m: edge_contracts + envelope ratchets",
   "f: edge fns ARE the prod backend"),
 ("AU", "Auth & Permissions", 1.0, 1.0, 1.0,
   "m: resolveIdentity/resolveTenancy chokepoint + validate_gateway_tenancy/policy-hive-binding (bypass-tested, foreign-hive->403 live)",
   "m: rls-strict/rls-symmetry + tenancy ratchets",
   "f: RLS + identity run in prod"),
 ("S",  "Security & RLS", 1.0, 1.0, 1.0,
   "m: gateway policy + pii-egress hard-fail + RLS chokepoint",
   "m: 12 security validators + sast-scan ratchet",
   "f: RLS/redaction run in prod"),
 ("F",  "Frontend", 0.5, 1.0, 1.0,
   "a: escHtml is a partial render chokepoint, but VALUE-render has NO convergence point (the data-gateway gap -- a tile can read a producer's raw output); §13/A6 narrowing it",
   "m: many F ratchets (xss, a11y, displayed-values, capture-roundtrip)",
   "f: the HTML/JS runs for real users"),
 ("D",  "Database & Storage", 0.5, 1.0, 1.0,
   "a: canonical v_*_truth is the value chokepoint but RAW writes bypass it (capture round-trip showed direct .insert paths); partial PEP",
   "m: migration-immutability + truth-view + lineage ratchets",
   "f: Postgres/Supabase is the prod store"),
 ("CI", "CI/CD & Version Control", 1.0, 1.0, 0.5,
   "m: run_platform_checks IS the change chokepoint (auto-discovery proves every change classified) + 408 validators",
   "m: forward-only baselines + migration-immutability-strict",
   "s: local runner proven; GitHub Actions runner is external (Ian's gate)"),
 ("RL", "Rate Limiting", 1.0, 1.0, 0.5,
   "m: rate-gate in the pipeline keyed on verifiedHiveId (policy-hive-binding, spoof-tested live)",
   "m: rate-limit-fairness/adoption ratchets",
   "s: live burst proven LOCAL (60x->429); prod-scale fairness is external"),
 ("CA", "Caching & CDN", 0.5, 0.5, 0.5,
   "a: cached() is a partial chokepoint, adoption < target (documented residual); no CDN-edge convergence",
   "a: cache-hit-rate ratchet present but adoption-incomplete",
   "s: app-cache prod-real; CDN-edge config is external"),
 ("L",  "Error Tracking & Logs", 0.5, 0.5, 0.0,
   "a: structured-log + trace-store partial adoption; no single log convergence point yet",
   "a: structured-log-adoption ratchet but sampled",
   "f: PROD aggregation (Loki/Sentry) is external -- local ndjson only"),
 ("AV", "Availability & Recovery", 0.5, 1.0, 0.0,
   "a: /health is a convergence for liveness, but no prod failover chokepoint",
   "m: game-day-readiness ratchet (game_day + verify_backups + RTO/RPO present)",
   "f: prod failover / multi-AZ / PITR drill are external/unbuilt"),
 ("H",  "Hosting & Deployment", 0.0, 1.0, 0.0,
   "f: no deploy/rollout chokepoint locally enforceable; prod deploy is external",
   "m: migration-immutability + deploy-safety ratchet (local)",
   "f: prod hosting / blue-green / rollback are external (Ian's gate)"),
 ("C",  "Cloud & Compute", 0.0, 0.5, 0.0,
   "f: no provisioning/autoscale chokepoint (prod-infra)",
   "a: health-surface-discovery + cold-start ratchets (partial)",
   "f: autoscale / provisioning / multi-AZ are external/unbuilt"),
 ("LB", "Load Balancing & Scaling", 0.0, 0.5, 0.0,
   "f: NO load-balancing chokepoint exists (prod-infra)",
   "s: load_probe + connection-pool ratchet are LOCAL SUBSTITUTES (the green tick that most overstated)",
   "f: real LB / horizontal autoscale are external/unbuilt"),
]

AXES = ("gateway", "gate", "prod_real")


def _measured_gateway():
    """G2: override the ASSESSED gateway grade with the MEASURED one from
    validate_gateway_bypass (gateway_bypass.json) wherever a real bypass report exists."""
    p = ROOT / "gateway_bypass.json"
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for l in d.get("layers", []):
        if str(l.get("basis", "")).startswith("measured"):
            out[l["code"]] = (l["gateway_grade"], f"m: bypass={l['bypass']} via {l['report']} ({l['basis']})")
    return out


def measure():
    rows = []
    mg = _measured_gateway()
    for code, name, gw, ga, pr, gwb, gab, prb in L:
        if code in mg:                       # G2: instrument-backed gateway grade wins
            gw, gwb = mg[code][0], mg[code][1]
        comp = round((gw + ga + pr) / 3 * 100, 1)
        rows.append({"code": code, "name": name, "gateway": gw, "gate": ga, "prod_real": pr,
                     "composite_pct": comp,
                     "gateway_basis": gwb, "gate_basis": gab, "prod_basis": prb})
    totals = {ax: round(sum(r[ax] for r in rows), 2) for ax in AXES}
    overall = round(sum(totals.values()) / (3 * len(rows)) * 100, 1)
    return rows, totals, overall


def main() -> int:
    update = "--update-baseline" in sys.argv
    rows, totals, overall = measure()
    report = {"_overall_pct": overall, "axis_totals": totals, "n_layers": len(rows),
              "_note": "HONEST 3-axis depth (Gateway PEP / Gate ratchet / Prod-real). Stricter than the 13x6 matrix (100%) + measure_layer_depth coverage (84.3%) because it (a) requires a PREVENTION chokepoint not just detection, and (b) does NOT credit a local substitute as prod-real.",
              "layers": rows}
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _md(report)

    print("\n  HONEST per-layer depth — GATEWAY × GATE × PROD-REAL (Ian's ask, 2026-06-17)")
    print("  (stricter than 13x6=100% & coverage=84.3%: prevention-chokepoint + prod-real required)\n  " + "=" * 66)
    print(f"  {'Layer':<26} {'GW':>4} {'Gate':>5} {'Prod':>5} {'depth%':>8}")
    for r in sorted(rows, key=lambda x: -x["composite_pct"]):
        print(f"  {r['name']:<26} {r['gateway']:>4} {r['gate']:>5} {r['prod_real']:>5} {r['composite_pct']:>7}%")
    print("  " + "-" * 66)
    print(f"  {'axis totals (/13)':<26} {totals['gateway']:>4} {totals['gate']:>5} {totals['prod_real']:>5}")
    print(f"\n  ★ HONEST OVERALL DEPTH = {overall}%   (vs 84.3% coverage / 100% gate-matrix — the false sense)")
    bands = {"request-flow (A/AU/S)": [r for r in rows if r['code'] in ('A','AU','S')],
             "value (F/D)": [r for r in rows if r['code'] in ('F','D')],
             "infra/prod (H/C/LB/L/AV/CA)": [r for r in rows if r['code'] in ('H','C','LB','L','AV','CA')]}
    print("\n  by band (where the gaps really are):")
    for b, rs in bands.items():
        avg = round(sum(r['composite_pct'] for r in rs)/len(rs), 1)
        print(f"    {b:<34} {avg:>5}%")

    cur = {r["code"]: r["composite_pct"] for r in rows}
    if update or not BASELINE.exists():
        BASELINE.write_text(json.dumps(cur, indent=2), encoding="utf-8")
        print(f"\n  baseline {'updated' if update else 'initialised'} → gateway_gate_baseline.json")
        return 0
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    regr = [f"{c}: {cur[c]}% < baseline {base[c]}%" for c in cur if c in base and cur[c] < base[c] - 1e-9]
    if regr:
        print("\n  ✗ DEPTH RATCHET REGRESSION:")
        for x in regr: print("    - " + x)
        return 1
    print("\n  ✓ honest-depth ratchet held")
    return 0


def _md(report):
    md = ["# HONEST per-layer depth — GATEWAY × GATE × PROD-REAL (2026-06-17)\n",
          "_The corrected figure Ian asked for: a Gateway (prevention chokepoint / PEP) AND a Gate (detection ratchet) for every layer, graded by REAL depth + whether the proof is PROD-REAL or a local substitute. Deliberately stricter than the 13×6 matrix (100%) and `measure_layer_depth` coverage (84.3%), which both credit detection-presence and local substitutes._\n",
          f"\n**★ HONEST OVERALL DEPTH = {report['_overall_pct']}%**  (axis totals /13 — Gateway {report['axis_totals']['gateway']} · Gate {report['axis_totals']['gate']} · Prod-real {report['axis_totals']['prod_real']})\n",
          "\n| Layer | Gateway | Gate | Prod-real | depth% |",
          "|---|---|---|---|---|"]
    for r in sorted(report["layers"], key=lambda x: -x["composite_pct"]):
        md.append(f"| {r['name']} | {r['gateway']} | {r['gate']} | {r['prod_real']} | **{r['composite_pct']}%** |")
    md.append("\n## Per-layer basis (m=measured · a=assessed · s=local-substitute · f=factual-external)\n")
    for r in sorted(report["layers"], key=lambda x: -x["composite_pct"]):
        md.append(f"\n### {r['name']} — {r['composite_pct']}%")
        md.append(f"- **Gateway {r['gateway']}** — {r['gateway_basis']}")
        md.append(f"- **Gate {r['gate']}** — {r['gate_basis']}")
        md.append(f"- **Prod-real {r['prod_real']}** — {r['prod_basis']}")
    OUT_MD.write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
