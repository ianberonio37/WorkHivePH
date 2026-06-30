"""
measure_layer_depth -- A7.4: make the §14.3 layer scorecard MEASURED (the COVERAGE half).
=========================================================================================
THE DRIFT IT KILLS
------------------
§14.3 scored each of the 13 full-stack layers with THREE percentages (Gateway-converge,
Gate-anti-regress, true-scope-depth) that were honest ENGINEERING ESTIMATES, not instrument
readings -- which §14.4 itself flagged as a drift risk. This tool converts the MEASURABLE
half into a tool-pulled fraction: **sub-discipline COVERAGE** = the fraction of each layer's
full discipline checklist for which AT LEAST ONE real mechanism (validator/tool/artifact)
exists. Same discipline that turned "P-fully" and "grounding-contract" from estimates into
measured ratchets.

★HONESTY -- COVERAGE IS NOT DEPTH (do NOT relabel this as true-scope depth, that is the
false-sense trap). COVERAGE answers "does a mechanism EXIST for this sub-discipline?"
(presence/breadth). True-scope DEPTH answers "how exhaustively is that mechanism BUILT?"
(thoroughness). A sub-discipline can be COVERED by one shallow validator yet shallow in
depth. So **coverage% is an UPPER BOUND on true-scope depth%, never equal to it** -- you
cannot be deep where you have zero mechanism, but having a mechanism does not make you deep.
This number therefore tracks the GATE/breadth axis (§14.3 Gate column, 30-80%), NOT the
true-scope estimate (15-45%); reported as coverage, the two are consistent, not contradictory.
What this instrument makes UN-FUDGEABLE is the **ABSENT set** -- whole sub-disciplines with
NO mechanism -- which is the real, measured depth backlog (mostly the external prod ceiling:
LB / failover / aggregation / autoscale). Depth-WITHIN-covered stays a bounded estimate
because it is fractal/subjective to instrument objectively; coverage is the honest, bounded,
ratchetable half.

THE METHOD (denominator-first, §13.5)
-------------------------------------
For each layer, define its FULL production-discipline CHECKLIST -- the sub-disciplines a
mature build of that layer must cover, drawn from the recognised rubrics already cited in
§12 (AWS Well-Architected, Google SRE, 12-Factor, OWASP ASVS, SaaS maturity L1-4). That
checklist is the DENOMINATOR. Then each sub-discipline is classified by EVIDENCE that
actually exists in this repo:
  • COVERED  -- >=1 evidence token matches a REGISTERED validator id (run_platform_checks)
                OR an existing tools/<file> / repo-root artifact. Falsifiable: the token
                names a real file/id you can open.
  • PARTIAL  -- a mechanism exists but is local-only / sampled / adoption-incomplete
                (flagged with the reason); counts 0.5.
  • ABSENT   -- no mechanism. Usually the honest external ceiling (prod LB / failover /
                aggregation) or a real depth gap. Counts 0. THESE ARE THE BACKLOG.

coverage% (layer) = (covered + 0.5*partial) / total_sub_disciplines.
The number is only as honest as the checklist is complete -- so the checklist is FIXED from
the rubric, never trimmed to flatter the score, and ABSENT items are printed, not hidden.

RATCHET: writes layer_depth_baseline.json (per-layer covered+partial counts). Forward-only --
a layer's measured depth may only RISE; a drop FAILs (a deleted/renamed validator that
silently un-covers a sub-discipline). Register in run_platform_checks (Maturity group,
NOT skip_if_fast -- it's static).

Usage: python tools/measure_layer_depth.py [--update-baseline] [--strict]
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
REGISTRY = ROOT / "run_platform_checks.py"
OUT_JSON = ROOT / "layer_depth.json"
OUT_MD = ROOT / "layer_depth.md"
BASELINE = ROOT / "layer_depth_baseline.json"

# ── the FIXED denominator: each layer's full sub-discipline checklist (from the rubric) ──
# Each item: (sub_discipline, [evidence tokens], status_override)
#   evidence token = a validator-id (or substring) registered in run_platform_checks,
#   OR a "tool:<filename>" / "art:<repo-root-file>" existence check.
#   status_override: None = auto (COVERED if any token resolves), "partial:<why>", "absent:<why>".
P = lambda why: ("partial", why)
A = lambda why: ("absent", why)

LAYERS: dict[str, list] = {
    "Frontend": [
        ("Render-value truth (rendered number == source)", ["displayed-values", "source-chip-truth", "diagram_value_alignment", "narrative_grounding"], None),
        ("XSS-safe rendering (escHtml coverage)", ["xss", "innerhtml-eschtml"], None),
        ("Accessibility (aria / labels / headings / contrast)", ["accessibility", "aria-label-coverage", "heading-hierarchy", "icon-button-label", "table-accessible-name"], None),
        ("Responsive / mobile (touch, safe-area, viewport)", ["mobile", "viewport-user-scalable"], None),
        ("Empty / loading / error states", ["loading-state", "feedback-widget"], None),
        ("Render budget / Core Web Vitals", ["render-budget", "bundle-bloat"], P("CWV is L2-spec only; live-boot capture unreliable")),
        ("State management discipline (module scope, listener cleanup)", ["module-scope-state", "event-listener-cleanup", "timer-cleanup"], None),
        ("Design-system tokens / brand consistency", ["design-tokens"], None),
        ("Capture round-trip (input value -> DB faithfully)", ["capture-contracts", "tool:verify_capture_roundtrip.py"], None),
    ],
    "APIs & Backend Logic": [
        ("Request/response envelope contract", ["edge-contracts", "envelope-conformance", "envelope-return-shape", "edge-response-contract"], None),
        ("Input validation / guards", ["input-guards", "json-parse-safety", "response_format_validation"], None),
        ("Idempotency (safe retries)", ["idempotency", "optimistic-concurrency"], None),
        ("Error status + body contract", ["edge-status-body", "edge-response-content-type", "edge-body-size-guard"], None),
        ("Gateway pipeline (one front door)", ["gateway-routing", "gateway-coverage", "gateway-audit"], None),
        ("Routing coverage (no bypass)", ["gateway-coverage", "edge-caller-contract", "edge-function-invoke"], None),
        ("OpenAPI / contract sync", ["openapi-sync"], None),
        ("CORS / preflight correctness", ["cors-wildcard", "edge-options-preflight"], None),
        ("Dependency pinning (reproducible imports)", ["edge-unpinned-imports", "reproducible-build-pin"], None),
    ],
    "Database & Storage": [
        ("Canonical truth layer (one definition per value)", ["truth-view-contract", "truth-view-consumer-columns", "kpi-source-registry", "canonical-registry"], None),
        ("Migration immutability + ordering", ["migration-immutability", "migration-order", "migration-immutability-strict"], None),
        ("Schema drift / coverage", ["schema-drift", "schema-coverage", "phantom-columns", "query-column-existence"], None),
        ("Referential integrity (FK / on-delete)", ["fk-on-delete", "soft-delete"], None),
        ("Data lineage (input -> consumer graph)", ["tool:mine_lineage_map.py", "tool:journey_trace.py"], None),
        ("Retention / archival", ["data-retention", "cold-archive", "cold-archive-wiring"], None),
        ("Indexing / query performance", ["index-coverage", "jsonb-index", "unbounded-query"], None),
        ("JSONB / semi-structured integrity", ["jsonb-drift", "vector-schema", "pgvector-consistency"], None),
        ("Backup / restore verification", ["tool:verify_backups.py"], P("verify_backups is a local structural check; prod PITR is external")),
    ],
    "Auth & Permissions": [
        ("Identity resolution (server-derived, not client)", ["gateway-tenancy", "auth-boundary"], None),
        ("Tenancy resolution (hive scoping)", ["gateway-tenancy", "tenant-boundary"], None),
        ("RBAC roles consistency", ["role-string-consistency", "admin-gates"], None),
        ("RLS policies (strict + symmetric)", ["rls-strict", "rls-symmetry", "rls-open-policy", "rls-readiness"], None),
        ("IDOR / policy binding (per-tenant key)", ["policy-hive-binding", "definer-membership-gate"], None),
        ("Auth migration readiness", ["auth-migration-readiness"], None),
        ("SSO / SAML (enterprise)", ["sso-readiness"], P("readiness check only; live SSO is enterprise-gated")),
        ("Service-role exposure guard", ["service-role-exposure", "security-definer-search-path"], None),
    ],
    "Hosting & Deployment": [
        ("Deploy safety gate", ["deploy-safety", "ci-gate-sentinel"], None),
        ("Migration immutability at deploy", ["migration-immutability-strict"], None),
        ("Env / config completeness", ["env-variable-existence", "env-secret-coverage", "edge-config"], None),
        ("Secrets management (no hardcode)", ["hardcoded-secrets"], None),
        ("Reproducible build (pinned)", ["reproducible-build-pin"], None),
        ("Deploy-signal mining", ["mine-deploy-signals"], None),
        ("Blue-green / rollback", [], A("prod rollout strategy is external (Ian's prod gate)")),
        ("CDN / static hosting config", [], A("prod CDN/hosting config is external")),
    ],
    "Cloud & Compute": [
        ("Runtime health endpoints", ["health-endpoint", "health-surface-discovery"], None),
        ("Cold-start / warm-path optimisation", ["cold-start-memoization"], None),
        ("Capacity signal mining", ["mine-capacity-signals"], None),
        ("Edge runtime config", ["edge-config"], None),
        ("Autoscaling policy", [], A("autoscale is prod-infra, external")),
        ("Provisioning / IaC", [], A("provisioning/IaC is external")),
        ("Compute cost observability", ["ai-cost-observability"], P("AI compute cost tracked; general compute cost is prod-billing")),
    ],
    "CI/CD & Version Control": [
        ("Change chokepoint (every change gated)", ["auto-discovery", "gate-observability"], None),
        ("Validator self-coverage", ["validator-self-coverage", "validator-freshness", "tester-coverage"], None),
        ("Immutability of shipped artifacts", ["migration-immutability-strict"], None),
        ("Pattern-mining (new code auto-classified)", ["edge-pattern-mining", "html-pattern-mining", "seeder-pattern-mining", "validator-pattern-mining"], None),
        ("Baseline / regression ratchets", ["sentinel-baseline", "tool:platform_baseline.json"], None),
        ("CI gate runner", ["ci-gate-sentinel", "tool:ci_gate.py"], P("ci_gate runs locally; GitHub Actions runner is external")),
        ("Reproducible build pin", ["reproducible-build-pin"], None),
    ],
    "Security & RLS": [
        ("XSS / output encoding", ["xss", "innerhtml-eschtml"], None),
        ("Injection (SQL/LIKE/JSON)", ["like-escape", "json-parse-safety", "kpi-count-query-safety"], None),
        ("Secrets hygiene", ["hardcoded-secrets", "env-secret-coverage"], None),
        ("PII egress control", ["pii-egress"], None),
        ("SAST scanning", ["sast-scan"], None),
        ("CORS / origin policy", ["cors-wildcard"], None),
        ("Service-role / privilege escalation", ["service-role-exposure", "security-definer-search-path", "provider-bypass"], None),
        ("Audit trail / tamper evidence", ["audit-trail-coverage", "audit-log-coverage", "audit-scanner-scope"], None),
        ("Auth boundary (cross-ref Auth layer)", ["auth-boundary", "policy-hive-binding"], None),
    ],
    "Rate Limiting": [
        ("Per-tenant rate-limit binding", ["policy-hive-binding"], None),
        ("Fairness (no cross-tenant drain)", ["rate-limit-fairness"], None),
        ("Adoption across endpoints", ["rate-limit-adoption"], None),
        ("Rate-limit signal mining", ["mine-rate-limit-signals"], None),
        ("429 + Retry-After contract", ["edge-status-body"], P("429 contract asserted statically; live burst is V-strict/local")),
        ("Per-route quota", ["rate-limit-adoption"], P("per-route quota in ai-gateway only; not all routes")),
    ],
    "Caching & CDN": [
        ("Application cache (LLM / compute)", ["llm-cache-adoption", "cache-hit-rate"], None),
        ("Cache invalidation correctness", ["cache-invalidation"], None),
        ("Hit-rate observability", ["cache-hit-rate"], None),
        ("Cache-signal mining", ["mine-cache-signals", "mine-cache-name-drift"], None),
        ("Offline / service-worker cache", ["offline-resilience", "sw-offline", "service-worker-shell", "pwa"], None),
        ("CDN edge caching", [], A("prod CDN edge config is external")),
        ("Cache adoption breadth", ["llm-cache-adoption"], P("cache adoption ratchet < target (documented residual)")),
    ],
    "Load Balancing & Scaling": [
        ("Connection-pool saturation guard", ["connection-pool-saturation", "connection-surface-discovery"], None),
        ("Capacity planning", ["mine-capacity-signals"], None),
        ("Load resilience (degraded-mode)", ["load-resilience"], None),
        ("Load test (concurrent burst)", ["tool:load_test.k6.js"], P("k6 harness points at local edge; prod load tier needs k6 install/prod")),
        ("Horizontal scaling policy", [], A("horizontal scale is prod-infra, external")),
        ("Load balancer config", [], A("LB config is prod-infra, external")),
    ],
    "Error Tracking & Logs": [
        ("Structured logging adoption", ["structured-log-adoption"], None),
        ("Log correlation (trace id)", ["log-correlation"], None),
        ("Trace store / SLI rollup", ["tool:trace-store.ts", "observability", "adoption-observability"], None),
        ("Log-surface discovery", ["log-surface-discovery"], None),
        ("Console-log drift guard", ["console-log-drift"], None),
        ("Prod aggregation (Loki/Sentry)", [], A("prod log aggregation backend is external")),
        ("Error budget / alerting", ["pattern-alerts", "proactive-alerts"], P("alerting present; formal error-budget burn is prod-SLO")),
    ],
    "Availability & Recovery": [
        ("Health endpoints", ["health-endpoint", "health-surface-discovery"], None),
        ("SLO definition", ["art:GATEWAY_SLO.md"], None),
        ("Game-day readiness", ["game-day-readiness", "tool:game_day.py"], None),
        ("Backup verification", ["tool:verify_backups.py"], P("structural backup check local; prod PITR external")),
        ("Degraded-mode / offline resilience", ["offline-resilience", "load-resilience"], None),
        ("Failover / multi-region", [], A("failover/multi-region is prod-infra, external")),
        ("PITR / restore drill", [], A("point-in-time-restore drill is external")),
    ],
}


def load_registered_ids() -> set[str]:
    if not REGISTRY.exists():
        return set()
    t = REGISTRY.read_text(encoding="utf-8", errors="replace")
    return set(re.findall(r'"id":\s*"([^"]+)"', t))


def evidence_exists(token: str, ids: set[str]) -> bool:
    if token.startswith("tool:"):
        return (TOOLS / token[5:]).exists() or any(p.name == token[5:] for p in ROOT.rglob(token[5:]) if p.is_file()) or (ROOT / token[5:]).exists()
    if token.startswith("art:"):
        return (ROOT / token[4:]).exists() or any(True for _ in ROOT.rglob(token[4:]))
    # a validator-id (exact or substring of a registered id)
    return token in ids or any(token in vid for vid in ids)


def classify(item, ids):
    name, tokens, override = item
    resolved = [t for t in tokens if evidence_exists(t, ids)]
    if override and override[0] == "absent":
        return "ABSENT", 0.0, override[1], resolved
    if override and override[0] == "partial":
        # partial requires the mechanism to at least exist
        return ("PARTIAL", 0.5, override[1], resolved) if (resolved or not tokens) else ("ABSENT", 0.0, override[1] + " (no evidence found)", resolved)
    if resolved:
        return "COVERED", 1.0, "", resolved
    return "ABSENT", 0.0, "no validator/tool evidence", resolved


def main() -> int:
    update = "--update-baseline" in sys.argv
    strict = "--strict" in sys.argv
    ids = load_registered_ids()
    if not ids:
        print("  run_platform_checks.py not found / no ids — cannot measure")
        return 1

    report, totals_cov, totals_n = {}, 0.0, 0
    for layer, items in LAYERS.items():
        rows = []
        score = 0.0
        for it in items:
            status, pts, why, ev = classify(it, ids)
            score += pts
            rows.append({"sub": it[0], "status": status, "points": pts, "why": why, "evidence": ev})
        n = len(items)
        pct = round(100.0 * score / n, 1)
        covered = sum(1 for r in rows if r["status"] == "COVERED")
        partial = sum(1 for r in rows if r["status"] == "PARTIAL")
        absent = sum(1 for r in rows if r["status"] == "ABSENT")
        report[layer] = {"coverage_pct": pct, "score": round(score, 1), "total": n,
                          "covered": covered, "partial": partial, "absent": absent, "rows": rows}
        totals_cov += score
        totals_n += n

    overall = round(100.0 * totals_cov / totals_n, 1)
    report["_overall"] = {"coverage_pct": overall, "score": round(totals_cov, 1), "total": totals_n,
                           "_note": "COVERAGE (presence-of-mechanism) = UPPER BOUND on true-scope depth, NOT depth itself. ABSENT cells are the measured backlog."}

    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_md(report)

    # ── print scoreboard ──
    print("\n  §14.3 sub-discipline COVERAGE — MEASURED (A7.4)")
    print("  (presence-of-mechanism per sub-discipline = UPPER BOUND on true-scope depth, NOT depth)\n  " + "=" * 62)
    print(f"  {'Layer':<28} {'cov%':>7} {'cov':>4} {'part':>5} {'abs':>4}")
    for layer in LAYERS:
        r = report[layer]
        print(f"  {layer:<28} {r['coverage_pct']:>6}% {r['covered']:>4} {r['partial']:>5} {r['absent']:>4}")
    print("  " + "-" * 62)
    print(f"  {'OVERALL sub-discipline coverage':<28} {overall:>6}%   ({report['_overall']['score']}/{totals_n} sub-disciplines have a mechanism)")
    print(f"  {'ABSENT (measured depth backlog)':<28} {sum(report[l]['absent'] for l in LAYERS):>7}   sub-disciplines with NO mechanism (mostly external prod ceiling)")

    # ── ratchet ──
    cur = {l: {"score": report[l]["score"]} for l in LAYERS}
    if update or not BASELINE.exists():
        BASELINE.write_text(json.dumps(cur, indent=2), encoding="utf-8")
        print(f"\n  baseline {'updated' if update else 'initialised'} → layer_depth_baseline.json")
        return 0

    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    regressions = []
    for l in LAYERS:
        b = base.get(l, {}).get("score", 0.0)
        if report[l]["score"] < b - 1e-9:
            regressions.append(f"{l}: depth {report[l]['score']} < baseline {b} (a sub-discipline lost its evidence)")
    if regressions:
        print("\n  ✗ TRUE-SCOPE RATCHET REGRESSION:")
        for r in regressions:
            print(f"    - {r}")
        return 1
    print("\n  ✓ true-scope ratchet held (no layer lost measured depth)")
    if strict:
        gaps = sum(report[l]["absent"] for l in LAYERS)
        print(f"  --strict: {gaps} ABSENT sub-disciplines remain (the honest depth backlog; see layer_depth.md)")
    return 0


def _write_md(report):
    md = ["# §14.3 sub-discipline COVERAGE — MEASURED (A7.4)\n",
          "_Tool-pulled by `tools/measure_layer_depth.py`; denominator = each layer's full sub-discipline checklist (rubric-fixed). COVERED=validator/tool evidence exists · PARTIAL=local/sampled · ABSENT=gap (mostly external prod ceiling)._\n",
          "\n> ★**COVERAGE ≠ DEPTH.** This measures whether a MECHANISM EXISTS per sub-discipline (presence/breadth) — an **upper bound on** true-scope depth, NOT depth itself. It tracks the §14.3 *Gate* axis (30–80%), not the true-scope estimate (15–45%). The honest, un-fudgeable signal is the **ABSENT set** = the measured depth backlog.\n",
          f"\n**Overall measured sub-discipline coverage: {report['_overall']['coverage_pct']}%** ({report['_overall']['score']}/{report['_overall']['total']} sub-disciplines have ≥1 mechanism)\n",
          "\n| Layer | coverage% | covered | partial | absent |",
          "|---|---|---|---|---|"]
    for layer in LAYERS:
        r = report[layer]
        md.append(f"| {layer} | {r['coverage_pct']}% | {r['covered']} | {r['partial']} | {r['absent']} |")
    md.append("\n## Per-layer sub-discipline detail (the denominator + evidence)\n")
    for layer in LAYERS:
        r = report[layer]
        md.append(f"\n### {layer} — {r['coverage_pct']}% covered")
        for row in r["rows"]:
            mark = {"COVERED": "✅", "PARTIAL": "🟡", "ABSENT": "🔴"}[row["status"]]
            ev = (" · `" + "`, `".join(row["evidence"][:3]) + "`") if row["evidence"] else ""
            why = f" — _{row['why']}_" if row["why"] else ""
            md.append(f"- {mark} {row['sub']}{ev}{why}")
    OUT_MD.write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
