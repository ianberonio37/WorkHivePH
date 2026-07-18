#!/usr/bin/env python3
"""
security_adversarial_sweep.py - Arc R (Security / Adversarial) aggregate scorer (R0).
=====================================================================================
The ONE ratcheted, measured-% board for the platform's adversarial posture, across the
four OWASP-derived lenses:

  X - Injection & XSS        (input -> sink)
  Z - AuthZ / Access         (IDOR/BOLA/BFLA/SSRF + the DB read-paths + public-fn authZ)
  S - Secrets & Supply-chain (egress, SRI, CVE, config, SAST-map completeness)
  P - Prompt & AI security   (injection, RAG hive-scope, output-escape, anti-fabrication)

INVENT NOTHING for the existing cells - it runs the platform's existing security validators
as subprocesses (never imports a gate) and maps each to a lens + the FULL OWASP 2021 Top-10
(so A07/A09/A10 are explicit, unlike sast_scan.py which only enumerates 7 categories).

NEW Arc-R cells with no validator yet are scored MISSING == "unscanned attack surface" -
measured-not-credited: an honest baseline shows the gap rather than hiding it. As each new
gate lands (sri_cdn_scripts, public_fn_internal_authz, ssrf_egress, committed_env_secret,
sast_owasp_complete) its cell flips to live.

Per-lens %  = PASS cells / total cells in lens.
Floors      : X 100 / Z 100 / S 95 / P 90  (security floors run high).
Ratchet     : security_adversarial_baseline.json - a lens %% may not regress below baseline.

Output : security_adversarial_results.json (+ console board)
Exit 0 : all floors met AND no lens regressed below baseline
Exit 1 : a floor missed or a regression
"""
from __future__ import annotations
import io, json, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
RESULTS = ROOT / "security_adversarial_results.json"
BASELINE = ROOT / "security_adversarial_baseline.json"

CHECK_NAMES = ["security_adversarial_sweep"]
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; C = "\033[96m"; X = "\033[0m"

FLOORS = {"X": 100, "Z": 100, "S": 95, "P": 90}

# Each cell: (key, validator-stem-or-None, owasp, note).
# validator None == a NEW Arc-R surface with no gate yet -> scored MISSING (unscanned).
# Validators are resolved at ROOT first, then ROOT/tools (the base is split across both).
LENSES = {
    "X": {  # Injection & XSS
        "title": "Injection & XSS",
        "cells": [
            ("xss_eschtml",           "validate_xss",                       "A03", "escHtml coverage on render paths"),
            ("innerhtml_eschtml",     "validate_innerhtml_eschtml",         "A03", "innerHTML sinks escaped"),
            ("companion_output_esc",  "validate_companion_output_escaping", "A03", "AI output escaped before DOM"),
            ("dom_xss_advanced",      "validate_dom_xss_fields",            "A03", "DB free-text in HTML must be escHtml (R1)"),
        ],
    },
    "Z": {  # AuthZ / Access
        "title": "AuthZ / Access",
        "cells": [
            ("gateway_bypass",        "validate_gateway_bypass",            "A01", "gateway tenancy not bypassable"),
            ("gateway_tenancy",       "validate_gateway_tenancy",           "A01", "gateway scopes by verified hive"),
            ("definer_tenant_gate",   "validate_definer_tenant_gate",       "A01", "DEFINER RPCs self-scope (IDOR)"),
            ("function_security",     "validate_function_security",         "A01", "fn priv/grant locked"),
            ("policy_hive_binding",   "validate_policy_hive_binding",       "A01", "RLS bound to hive membership"),
            ("rls_strict",            "validate_rls_strict",                "A04", "RLS strict on every table"),
            ("rls_no_permissive",     "validate_rls_no_permissive_bypass",  "A04", "no permissive USING(true) bypass"),
            ("rls_tenant_isolation",  "validate_rls_tenant_isolation",      "A01", "two-tenant isolation proven"),
            ("anon_key_retirement",   "validate_anon_key_retirement",       "A01", "anon reads 0 from hive tables"),
            ("realtime_isolation",    "validate_realtime_subscription_isolation", "A01", "published-table RLS (4th path)"),
            ("python_api_auth",       "validate_python_api_auth",           "A01", "compute API auth/key"),
            ("service_role_exposure", "validate_service_role_exposure",     "A01", "service-role not client-reachable"),
            ("public_fn_internal_authz", "validate_public_fn_authz",         "A01", "60 verify_jwt=false fns re-verify auth (R2)"),
            ("public_fn_write_authz", "validate_public_fn_write_authz",      "A01", "no anon-triggerable service-role writer / BFLA (R2)"),
            ("ssrf_egress",           "validate_ssrf_egress",               "A10", "no user-controlled fetch egress (R2)"),
            ("migration_grant_regression", "validate_migration_grant_regression", "A01", "a revoked anon/auth lock not silently re-granted by a later migration (R0)"),
            ("login_lockout",         "validate_login_proxy_lockout",       "A07", "brute-force login lockout (auth failures)"),
        ],
    },
    "S": {  # Secrets & Supply-chain
        "title": "Secrets & Supply-chain",
        "cells": [
            ("integration_security",  "validate_integration_security",      "A02", "key-format, CORS, webhook"),
            ("hardcoded_secrets",     "validate_hardcoded_secrets",         "A02", "no secret literal in source"),
            ("pii_egress",            "validate_pii_egress",                "A06", "no PII egress"),
            ("definer_search_path",   "validate_security_definer_search_path","A05","search_path pinned (CVE-2018-1058)"),
            ("cors_wildcard",         "validate_cors_wildcard",             "A05", "no wildcard CORS"),
            ("python_api_deps",       "validate_python_api_deps",           "A08", "dep CVEs triaged"),
            ("sri_cdn_scripts",       "validate_sri",                       "A08", "SRI on every CDN script (R3)"),
            ("committed_env_secret",  "validate_committed_env_secret",      "A02", "no tracked .env.* secret (R3)"),
            ("sast_owasp_complete",   "validate_sast_owasp_complete",       "A09", "SAST map covers full Top-10 (R3)"),
        ],
    },
    "P": {  # Prompt & AI security
        "title": "Prompt & AI security",
        "cells": [
            ("ai_prompt_injection",   "validate_ai_prompt_injection",       "A03", "user text delimited/capped"),
            ("ai_retrieval_isolation","validate_ai_retrieval_isolation",    "A01", "RAG hive-scoped (no x-tenant)"),
            ("ai_input_caps",         "validate_ai_input_caps",             "A03", "user text length-capped before LLM (deterministic; replaces flaky narrative_grounding on the board)"),
        ],
    },
}


def _resolve(stem: str) -> Path | None:
    for cand in (ROOT / f"{stem}.py", ROOT / "tools" / f"{stem}.py"):
        if cand.exists():
            return cand
    return None


# Per-validator timeout override (seconds). A few cells do MANY sequential live edge-fn /
# two-tenant DB probes — legitimately thorough, not hung — and exceed the 180s default. Giving
# them adequate time is correct: the board must MEASURE a slow-but-passing live check, not time
# it out into a fail-closed cell (2026-07-17: gateway_tenancy runs 39 live edge-fn tenancy probes
# ~5-8s each; standalone it PASSes with 0 unverified but exceeds 180s under the board).
SLOW_CELLS = {
    "validate_gateway_tenancy":  600,
    "validate_gateway_bypass":   480,
    "validate_public_fn_authz":  480,
    "validate_rls_tenant_isolation": 480,
    # network CVE scan (pip-audit → OSV database over the internet); slow when the network is,
    # and fail-closed (not a code hole) when the external DB is unreachable.
    "validate_python_api_deps":  360,
}
DEFAULT_CELL_TIMEOUT = 180


def _run(stem: str | None) -> str:
    if stem is None:
        return "MISSING"          # NEW surface, no gate yet -> unscanned
    p = _resolve(stem)
    if p is None:
        return "MISSING"
    try:
        r = subprocess.run([PY, str(p)], cwd=str(ROOT), capture_output=True, text=True,
                           timeout=SLOW_CELLS.get(stem, DEFAULT_CELL_TIMEOUT))
        return "PASS" if r.returncode == 0 else "FINDINGS"
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception:
        return "ERROR"


def _verdict(lens_out, baseline, baseline_error, baseline_missing, update):
    """Pure board verdict (no I/O) so --self-test can prove the anti-false-green rules bite.

    Fail-closed precedence: a corrupt ratchet, an infra-broken gate, a below-baseline regression,
    or an unmet floor ALL force exit 1 — none may resolve to the green PASS. --update-baseline is
    blocked whenever the board is currently regressed/below-floor (ratchet only ever moves UP)."""
    floors_ok, regressions, infra_errors = True, [], []
    for lens, L in lens_out.items():
        if L["pct"] < L["floor"]:
            floors_ok = False
        # An ERROR/TIMEOUT cell is an INFRA failure (gate could not run), not a clean measurement —
        # surface it explicitly so a broken validator can never masquerade as a benign non-PASS.
        for c in L["cells"]:
            if c.get("status") in ("ERROR", "TIMEOUT"):
                infra_errors.append(f"{lens}/{c['key']}={c['status']}")
        base_pct = baseline.get(lens, {}).get("pct")
        if base_pct is not None and L["pct"] < base_pct - 0.05:
            regressions.append(f"{lens}: {L['pct']} < baseline {base_pct}")
    update_blocked = bool(update and (regressions or not floors_ok))
    code = 1 if (baseline_error or infra_errors or regressions or not floors_ok) else 0
    return {"floors_ok": floors_ok, "regressions": regressions, "infra_errors": infra_errors,
            "update_blocked": update_blocked, "exit_code": code}


def _self_test() -> int:
    """Teeth for the board's own anti-false-green logic — the three holes the roadmap named."""
    def lens(pct, floor, statuses):
        cells = [{"key": f"c{i}", "status": s, "owasp": "A01"} for i, s in enumerate(statuses)]
        passed = sum(1 for s in statuses if s == "PASS")
        return {"title": "t", "pct": pct, "passed": passed, "total": len(statuses),
                "floor": floor, "cells": cells}
    green = {"X": lens(100, 100, ["PASS"]), "P": lens(100, 90, ["PASS"])}
    base_green = {"X": {"pct": 100}, "P": {"pct": 100}}
    cases = [
        ("happy path green -> 0",
         _verdict(green, base_green, False, False, False)["exit_code"] == 0),
        ("above-floor regression with a LOADED baseline -> 1 (not a silent pass)",
         _verdict({"S": lens(97, 95, ["PASS"])}, {"S": {"pct": 100}}, False, False, False)["exit_code"] == 1),
        ("above-floor regression with a MISSING baseline still can't hide -> update stays blocked",
         _verdict({"S": lens(97, 95, ["PASS"])}, {}, False, True, True)["exit_code"] == 0
         and _verdict({"S": lens(80, 95, ["PASS"])}, {}, False, True, True)["exit_code"] == 1),
        ("corrupt baseline -> hard 1 even when floors read met",
         _verdict(green, {}, True, False, False)["exit_code"] == 1),
        ("infra ERROR cell -> hard 1 (not a benign non-PASS)",
         _verdict({"X": lens(100, 100, ["ERROR"])}, base_green, False, False, False)["exit_code"] == 1),
        ("floor miss -> 1",
         _verdict({"P": lens(66.7, 90, ["PASS", "FINDINGS", "PASS"])}, base_green, False, False, False)["exit_code"] == 1),
        ("--update-baseline BLOCKED on a regression (no ratcheting-in the regression)",
         _verdict({"S": lens(97, 95, ["PASS"])}, {"S": {"pct": 100}}, False, False, True)["update_blocked"] is True),
        ("--update-baseline ALLOWED on a clean ratchet-up",
         _verdict(green, base_green, False, False, True)["update_blocked"] is False),
    ]
    ok = True
    for name, passed in cases:
        print(f"  [{(G+'PASS'+X) if passed else (R+'FAIL'+X)}] {name}")
        ok = ok and passed
    print((G + "self-test PASS - board false-green logic has teeth." + X) if ok
          else (R + "self-test FAILED." + X))
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv:
        return _self_test()
    cache: dict[str, str] = {}
    lens_out = {}
    for lens, spec in LENSES.items():
        rows = []
        for key, stem, owasp, note in spec["cells"]:
            ck = stem or f"__new__{key}"
            if ck not in cache:
                cache[ck] = _run(stem)
            status = cache[ck]
            rows.append({"key": key, "validator": stem, "owasp": owasp,
                         "status": status, "note": note,
                         "covered": stem is not None and status != "MISSING"})
        total = len(rows)
        passed = sum(1 for r in rows if r["status"] == "PASS")
        pct = round(100 * passed / total, 1) if total else 0.0
        lens_out[lens] = {"title": spec["title"], "cells": rows,
                          "passed": passed, "total": total, "pct": pct,
                          "floor": FLOORS[lens]}

    # OWASP full-Top-10 coverage view (the thing sast_scan truncates)
    owasp_all = ["A01", "A02", "A03", "A04", "A05", "A06", "A07", "A08", "A09", "A10"]
    owasp_cov = {}
    for cat in owasp_all:
        cells = [r for L in lens_out.values() for r in L["cells"] if r["owasp"] == cat]
        owasp_cov[cat] = {"scanners": sum(1 for c in cells if c["covered"]),
                          "clean": all(c["status"] == "PASS" for c in cells if c["covered"]) if cells else False,
                          "covered": any(c["covered"] for c in cells)}

    # Load the ratchet baseline. A baseline file that EXISTS but is unreadable/corrupt is a
    # HARD FAIL (baseline_error) — never silently fall back to "no baseline", because that
    # disengages regression detection and lets an above-floor regression exit 0 (a false-green).
    # A genuinely-absent baseline (first run) is allowed but flagged so the ratchet-disengaged
    # state is loud rather than silent.
    baseline, baseline_error, baseline_missing = {}, False, False
    if BASELINE.exists():
        try:
            baseline = json.loads(BASELINE.read_text(encoding="utf-8")).get("lenses", {})
        except Exception as e:
            baseline_error = True
            baseline = {}
            print(f"{R}BASELINE CORRUPT ({BASELINE.name}: {e}) — ratchet cannot load; failing closed.{X}")
    else:
        baseline_missing = True

    update = "--update-baseline" in sys.argv
    v = _verdict(lens_out, baseline, baseline_error, baseline_missing, update)
    floors_ok = v["floors_ok"]; regressions = v["regressions"]
    infra_errors = v["infra_errors"]; update_blocked = v["update_blocked"]

    result = {
        "scored_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lenses": {k: {"title": lv["title"], "pct": lv["pct"], "passed": lv["passed"],
                       "total": lv["total"], "floor": lv["floor"], "cells": lv["cells"]}
                   for k, lv in lens_out.items()},
        "owasp_top10": owasp_cov,
        "floors_ok": floors_ok, "regressions": regressions,
        "infra_errors": infra_errors, "baseline_error": baseline_error,
        "baseline_missing": baseline_missing, "exit_code": v["exit_code"],
    }
    RESULTS.write_text(json.dumps(result, indent=2), encoding="utf-8")

    # Ratchet is UP-ONLY: --update-baseline REFUSES to write when a lens is currently below its
    # stored baseline or below its floor — otherwise it would lock a REGRESSION in as the new
    # "baseline" and the next run would silently exit 0 (the false-green the roadmap flagged).
    if update and not update_blocked:
        BASELINE.write_text(json.dumps(
            {"updated_at": result["scored_at"],
             "lenses": {k: {"pct": lv["pct"]} for k, lv in lens_out.items()}}, indent=2),
            encoding="utf-8")

    print(f"{B}{C}Arc R - Security / Adversarial sweep{X}")
    for lens, L in lens_out.items():
        ok = L["pct"] >= L["floor"]
        bar = (G if ok else R) + f"{L['pct']:5.1f}%" + X
        print(f"  {lens} {L['title']:<26} {bar}  ({L['passed']}/{L['total']})  floor {L['floor']}")
        for c in L["cells"]:
            if c["status"] != "PASS":
                col = Y if c["status"] == "MISSING" else R
                print(f"      {col}{c['status']:<9}{X} {c['key']}  ({c['owasp']}) - {c['note']}")
    # OWASP line: GREEN only when a category is BOTH covered AND clean. A category with a scanner
    # that is actively FAILING prints yellow with a '!' — never a green that masks an open finding
    # (the very "false sense of coverage" anti-pattern Meta-finding #1 called out in sast_scan).
    def _owasp_col(cat: str) -> str:
        oc = owasp_cov[cat]
        if not oc["covered"]:
            return R + cat + X
        if not oc["clean"]:
            return Y + cat + "!" + X
        return G + cat + X
    print(f"  {B}OWASP Top-10 coverage:{X} " + " ".join(_owasp_col(c) for c in owasp_all))
    uncovered = [c for c in owasp_all if not owasp_cov[c]["covered"]]
    dirty = [c for c in owasp_all if owasp_cov[c]["covered"] and not owasp_cov[c]["clean"]]
    if uncovered:
        print(f"  {Y}OWASP categories with NO scanner: {', '.join(uncovered)}{X}")
    if dirty:
        print(f"  {R}OWASP categories with an OPEN finding: {', '.join(dirty)}{X}")

    if update_blocked:
        print(f"{R}baseline NOT updated — refusing to ratchet in a regression/floor-miss.{X}")
    elif update:
        print(f"{G}baseline updated.{X}")
    # Fail-closed order: a corrupt ratchet file or an infra-broken gate is a HARD fail — neither
    # may resolve to the green PASS line, even when floors happen to read met.
    if baseline_error:
        print(f"{R}FAIL — baseline file corrupt; ratchet cannot be trusted.{X}")
        return 1
    if infra_errors:
        print(f"{R}FAIL — validator infra error/timeout (not a clean measurement): {'; '.join(infra_errors)}{X}")
        return 1
    if regressions:
        print(f"{R}REGRESSION: {'; '.join(regressions)}{X}")
        return 1
    if not floors_ok:
        print(f"{Y}floors not yet met (expected during the arc - ratchet up).{X}")
        return 1
    if baseline_missing:
        # First-ever run with no ratchet on disk: floors are met, but say so honestly rather than
        # printing a green that implies a ratchet is protecting the score.
        print(f"{Y}PASS on floors — no baseline on disk yet (ratchet disengaged; run --update-baseline to arm it).{X}")
        return 0
    print(f"{G}PASS - all lens floors met, no regression.{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
