"""
SAST Posture Scan (Maturity Phase 4 — S-layer capability, 2026-06-16).
=======================================================================
"Do you run automated security scanning?" — YES, and this is the single front
door that proves it. SAST = Static Application Security Testing. WorkHive already
has 12 focused security validators; this aggregates them into ONE OWASP-aligned
posture report so an enterprise/ISO buyer (or a CI pipeline) gets one answer
instead of twelve. INVENT NOTHING — it runs the existing scanners as
subprocesses (never imports a gate) and maps each to an OWASP Top-10 category.

The GATE assertion is COVERAGE: every mapped OWASP category must have >= 1
existing scanner (a category with no scanner = an unscanned attack surface =
FAIL). The individual pass/fail is POSTURE (those validators are the blocking
gates in the main guardian; each carries its own baseline).

Output:  sast_report.json
Exit code: 0 every OWASP category has a scanner / 1 a category is unscanned
"""
from __future__ import annotations
import io, json, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
REPORT = ROOT / "sast_report.json"

CHECK_NAMES = ["sast_scan"]
GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; BOLD = "\033[1m"; RESET = "\033[0m"

# OWASP Top-10 category -> the WorkHive scanners that cover it.
# RELABELLED 2021 -> 2025 (2026-07-17, bug-hunt denominator arc; crawled owasp.org/Top10/ ->
# substrate/external/external-owasp-top-10-2021-web-application-security-risk-.md). 2025 reshuffle:
#   crypto 2021-A02 -> A04 · injection A03 -> A05 · insecure-design A04 -> A06 · misconfig A05 -> A02 ·
#   vulnerable-components A06 -> A03 "Software Supply Chain Failures" · SSRF (2021-A10) folded into A01 ·
#   A10:2025 "Mishandling of Exceptional Conditions" is NEW -> real scanners: edge error-capture /
#   debug-echo prod-safety / status-body-consistency / webhook fail-closed (all VERIFIED to exist,
#   not faked — the anti-pattern this map was born from). 10/10 remains honest under 2025.
OWASP = {
    "A01:2025 Broken Access Control":                  ["validate_gateway_tenancy.py", "validate_policy_hive_binding.py",
                                                        "validate_service_role_exposure.py", "validate_function_security.py",
                                                        "validate_public_fn_authz.py", "validate_ssrf_egress.py"],
    "A02:2025 Security Misconfiguration":              ["validate_cors_wildcard.py", "validate_security_definer_search_path.py"],
    "A03:2025 Software Supply Chain Failures":         ["validate_python_api_deps.py", "validate_edge_unpinned_imports.py"],
    "A04:2025 Cryptographic Failures":                 ["validate_hardcoded_secrets.py", "validate_committed_env_secret.py",
                                                        "validate_pii_egress.py"],
    "A05:2025 Injection":                              ["validate_xss.py", "validate_innerhtml_eschtml.py",
                                                        "validate_dom_xss_fields.py", "validate_ai_prompt_injection.py"],
    "A06:2025 Insecure Design":                        ["validate_rls_strict.py"],
    "A07:2025 Authentication Failures":                ["validate_login_proxy_lockout.py", "validate_signup_enumeration_safety.py",
                                                        "validate_signup_bot_protection.py", "validate_password_recovery.py",
                                                        "validate_account_deactivation.py", "validate_anon_key_retirement.py"],
    "A08:2025 Software or Data Integrity Failures":    ["validate_integration_security.py", "validate_sri.py"],
    "A09:2025 Security Logging and Alerting Failures": ["validate_observability.py"],
    "A10:2025 Mishandling of Exceptional Conditions":  ["validate_edge_error_capture.py", "validate_debug_echo_prod_safe.py",
                                                        "validate_edge_status_body_consistency.py", "validate_cmms_webhook_security_live.py"],
}


def _resolve(validator: str):
    for cand in (ROOT / validator, ROOT / "tools" / validator):
        if cand.exists():
            return cand
    return None


def _run(validator: str) -> tuple[str, bool]:
    p = _resolve(validator)
    if p is None:
        return ("MISSING", False)
    try:
        r = subprocess.run([PY, str(p)], cwd=str(ROOT), capture_output=True, text=True, timeout=120)
        return ("PASS" if r.returncode == 0 else "FINDINGS", p.exists())
    except Exception:
        return ("ERROR", p.exists())


def main() -> int:
    cache: dict[str, tuple[str, bool]] = {}
    categories = {}
    uncovered = []
    for cat, validators in OWASP.items():
        rows = []
        present_any = False
        for v in validators:
            if v not in cache:
                cache[v] = _run(v)
            status, present = cache[v]
            present_any = present_any or present
            rows.append({"validator": v, "status": status, "present": present})
        if not present_any:
            uncovered.append(cat)
        categories[cat] = {
            "scanners": rows,
            "covered": present_any,
            "posture": "clean" if all(r["status"] == "PASS" for r in rows if r["present"]) else "has-findings",
        }

    owasp_covered = sum(1 for c in categories.values() if c["covered"])
    clean = sum(1 for c in categories.values() if c["posture"] == "clean")
    REPORT.write_text(json.dumps({
        "scanned_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "owasp_categories": len(OWASP), "covered": owasp_covered,
        "clean_categories": clean, "uncovered": uncovered,
        "categories": categories,
    }, indent=2), encoding="utf-8")

    print(f"{BOLD}SAST Posture Scan (S-layer · OWASP Top-10){RESET}")
    print(f"  scanners aggregated: {len(cache)}  ·  OWASP categories covered: {owasp_covered}/{len(OWASP)}")
    for cat, c in categories.items():
        mark = (GREEN + "✓ clean" + RESET) if c["posture"] == "clean" else (YEL + "● findings (own gate ratchets)" + RESET)
        cov = "" if c["covered"] else RED + " — UNSCANNED" + RESET
        print(f"  {cat:<30} {mark}{cov}")
    if uncovered:
        print(f"{RED}FAIL: {len(uncovered)} OWASP category has NO scanner — unscanned attack surface.{RESET}")
        return 1
    print(f"{GREEN}PASS — every OWASP Top-10 category has an automated scanner.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
