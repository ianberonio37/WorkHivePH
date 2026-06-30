"""
validate_gateway_bypass -- G2: make the §14.6 GATEWAY axis MEASURED, not assessed.
=========================================================================================
§14.6 grades each layer's GATEWAY (the prevention chokepoint / Policy-Enforcement-Point) on
0/0.5/1.0 -- but those grades were ASSESSED. This validator derives them from REAL
bypass-coverage reports (reuse-first -- the chokepoint validators already run), so the
Gateway axis becomes an instrument:

  grade 1.0  -- a chokepoint EXISTS and its report shows ZERO unauthorised bypasses
  grade 0.5  -- a chokepoint exists but the report shows >0 real bypasses (partial PEP)
  grade 0.0  -- NO chokepoint validator exists for this layer (prevention is absent;
                detection-only). Honest by-absence, not a failure to find a file.

A "bypass" = a path that reaches a consumer WITHOUT passing the chokepoint (the §14 def:
the gateway's whole job is to be the only road; a bypass is a second road).

LAYER -> chokepoint report -> measured bypass count (the reuse map):
  A   APIs        gateway_coverage_report.json     bypass = failed (uncovered, non-exempt routes)
  AU  Auth        gateway_tenancy_report.json      bypass = unsafe_count (client-trusted hive_id)
  S   Security    policy_hive_binding_report.json  bypass = exploitable_count (cross-tenant key)
  RL  RateLimit   policy_hive_binding_report.json  bypass = exploitable_count (rate-key spoof)
  CI  CI/CD       auto_discovery_report.json       bypass = summary.fail (unclassified change)
  D   Database    canonical_sources_report.json    bypass = failed + len(drift) (raw-source reads)
  F   Frontend    user_facing_kpi_canonical_report.json  bypass = current_gap surfaces (value not canonical)
Layers with NO chokepoint report (H/C/LB/L/AV/CA) -> grade 0.0, tag=by-absence (the prod /
infra / data-gateway-incomplete frontier; honest, not hidden).

This is the DATA-GATEWAY meter too: D+F's bypass count is the hard number G1 drives to 0
(force every value through canonical truth). Forward-only ratchet on the bypass count per
layer (a NEW bypass FAILs); writes gateway_bypass.json. Register Maturity, not skip_if_fast.
"""
from __future__ import annotations
import io, json, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "gateway_bypass.json"
BASELINE = ROOT / "gateway_bypass_baseline.json"


def _load(name):
    p = ROOT / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _coverage_bypass(d):
    # gateway_coverage: every fn is "routed" or "bypass_ok" (legit-exempt); a real bypass is
    # status not in {routed, bypass_ok}. failed is the validator's own count.
    if not d:
        return None, False
    present = bool(d.get("platform_gateway_present"))
    cov = d.get("coverage") or []
    bad = [c for c in cov if isinstance(c, dict) and c.get("status") not in ("routed", "bypass_ok")]
    return (len(bad) + int(d.get("failed") or 0)), present


def measure():
    layers = []

    def add(code, name, bypass, present, report, note):
        if bypass is None or not present:
            grade, tag = 0.0, ("by-absence" if bypass is None else "chokepoint-missing")
            bypass = None if bypass is None else bypass
        elif bypass == 0:
            grade, tag = 1.0, "measured"
        else:
            grade, tag = 0.5, "measured-partial"
        layers.append({"code": code, "name": name, "gateway_grade": grade, "bypass": bypass,
                       "basis": tag, "report": report, "note": note})

    gc = _load("gateway_coverage_report.json"); b, pres = _coverage_bypass(gc)
    add("A", "APIs & Backend Logic", b, pres, "gateway_coverage_report.json", "edge fns route through platform-gateway or are code-verified exempt")

    gt = _load("gateway_tenancy_report.json")
    add("AU", "Auth & Permissions", (gt or {}).get("unsafe_count") if gt else None, bool(gt), "gateway_tenancy_report.json", "resolveIdentity/resolveTenancy chokepoint; bypass = client-trusted hive_id")

    ph = _load("policy_hive_binding_report.json")
    add("S", "Security & RLS", (ph or {}).get("exploitable_count") if ph else None, bool(ph), "policy_hive_binding_report.json", "gateway policy + verified-tenant key; bypass = cross-tenant exploitable site")
    add("RL", "Rate Limiting", (ph or {}).get("exploitable_count") if ph else None, bool(ph), "policy_hive_binding_report.json", "rate-limit keyed on verifiedHiveId; bypass = spoofable rate-key")

    ad = _load("auto_discovery_report.json")
    ci_bypass = (ad or {}).get("summary", {}).get("fail") if ad else None
    add("CI", "CI/CD & Version Control", ci_bypass, bool(ad), "auto_discovery_report.json", "run_platform_checks is the change chokepoint; bypass = unclassified change")

    cs = _load("canonical_sources_report.json")
    if cs:
        drift = cs.get("drift"); ndrift = len(drift) if isinstance(drift, list) else int(drift or 0)
        d_bypass = int(cs.get("failed") or 0) + ndrift
    else:
        d_bypass = None
    add("D", "Database & Storage", d_bypass, bool(cs), "canonical_sources_report.json", "canonical v_*_truth is the value chokepoint; bypass = raw-source read / drift")

    uk = _load("user_facing_kpi_canonical_report.json")
    f_bypass = len((uk or {}).get("current_gap") or {}) if uk else None
    add("F", "Frontend", f_bypass, bool(uk), "user_facing_kpi_canonical_report.json", "rendered value must map to a canonical source; bypass = surface displaying a non-canonical value")

    # G2b: L + AV are ADOPTION-RATCHET chokepoints (the mechanism exists, adoption is
    # partial) -- measurable, but they top out at 0.5 (partial) until adoption is full,
    # NOT a clean 0/1 like the request-flow chokepoints. The bypass = the un-adopted /
    # un-covered count (the G3 target).
    sl = _load("structured_log_adoption_report.json")
    if sl:
        non = len(sl.get("fns") or []) - len(sl.get("adopters") or [])
        add("L", "Error Tracking & Logs", max(non, 0), True, "structured_log_adoption_report.json",
            "structured ndjson logger (beginRequest/log) is the convergence; bypass = edge fn not emitting structured logs (partial-adoption ratchet)")
    else:
        add("L", "Error Tracking & Logs", None, False, None, "structured-log adoption report missing")

    hs = _load("health_surface_discovery_report.json")
    if hs is not None:
        add("AV", "Availability & Recovery", int(hs.get("without_health") or 0), True, "health_surface_discovery_report.json",
            "/health is the liveness convergence; bypass = edge fn without a /health probe (frozen-baseline ratchet)")
    else:
        add("AV", "Availability & Recovery", None, False, None, "health-surface report missing")

    # CA = cache-adoption ratchet too, but the non-adopter TOTAL is not cleanly countable
    # from the current reports (would need the full cacheable-LLM-call denominator) -> stays
    # ASSESSED in measure_gateway_gate (honest: not claimed measured). H/C/LB = factual
    # by-absence (no LOCAL prevention chokepoint; prod-infra = Ian's external gate).
    for code, name in [("CA", "Caching & CDN"), ("H", "Hosting & Deployment"),
                       ("C", "Cloud & Compute"), ("LB", "Load Balancing & Scaling")]:
        add(code, name, None, False, None, "no cleanly-countable prevention-chokepoint bypass meter (cache denom unknown / prod-infra is external)")
    return layers


def main() -> int:
    update = "--update-baseline" in sys.argv
    layers = measure()
    measured = [l for l in layers if l["basis"].startswith("measured")]
    total_grade = round(sum(l["gateway_grade"] for l in layers), 2)
    report = {"validator": "gateway-bypass", "gateway_axis_total": total_grade, "n_layers": len(layers),
              "measured_layers": len(measured), "assessed_or_absent": len(layers) - len(measured),
              "layers": layers,
              "_note": "G2: the §14.6 Gateway axis derived from REAL bypass reports. measured = instrument; by-absence = no chokepoint (honest frontier). D+F bypass = the data-gateway target G1 drives to 0."}
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n  GATEWAY axis — MEASURED from bypass reports (G2, §14.6)\n  " + "=" * 60)
    print(f"  {'Layer':<26} {'grade':>5} {'bypass':>7}  basis")
    for l in layers:
        bp = "-" if l["bypass"] is None else l["bypass"]
        print(f"  {l['name']:<26} {l['gateway_grade']:>5} {str(bp):>7}  {l['basis']}")
    print("  " + "-" * 60)
    print(f"  Gateway axis total = {total_grade}/13   ({len(measured)} layers MEASURED, {len(layers)-len(measured)} by-absence/assessed)")
    dg = [l for l in layers if l["code"] in ("D", "F")]
    dg_by = sum((l["bypass"] or 0) for l in dg)
    print(f"  ★ DATA-GATEWAY bypass (G1 target → 0): {dg_by}  (D={dg[0]['bypass']} canonical drift/fail · F={dg[1]['bypass']} non-canonical surfaces)")

    # forward-only ratchet on bypass counts (measured layers only)
    cur = {l["code"]: l["bypass"] for l in layers if l["bypass"] is not None}
    if update or not BASELINE.exists():
        BASELINE.write_text(json.dumps(cur, indent=2), encoding="utf-8")
        print(f"\n  baseline {'updated' if update else 'initialised'} → gateway_bypass_baseline.json")
        return 0
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    regr = [f"{c}: bypass {cur[c]} > baseline {base[c]} (a NEW gateway bypass appeared)"
            for c in cur if c in base and cur[c] > base[c]]
    if regr:
        print("\n  ✗ GATEWAY-BYPASS RATCHET REGRESSION:")
        for x in regr: print("    - " + x)
        return 1
    print("\n  ✓ gateway-bypass ratchet held (no new bypass)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
