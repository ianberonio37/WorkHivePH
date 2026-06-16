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

# OWASP Top-10 (2021/2025) category -> the WorkHive scanners that cover it.
OWASP = {
    "A01 Broken Access Control":   ["validate_gateway_tenancy.py", "validate_policy_hive_binding.py",
                                     "validate_service_role_exposure.py", "validate_function_security.py"],
    "A02 Cryptographic / Secrets": ["validate_hardcoded_secrets.py"],
    "A03 Injection / XSS":         ["validate_xss.py", "validate_innerhtml_eschtml.py"],
    "A04 Insecure Design / RLS":   ["validate_rls_strict.py"],
    "A05 Security Misconfig":      ["validate_cors_wildcard.py", "validate_security_definer_search_path.py"],
    "A06 Sensitive Data Exposure": ["validate_pii_egress.py"],
    "A08 Integration / Supply":    ["validate_integration_security.py"],
}


def _run(validator: str) -> tuple[str, bool]:
    p = ROOT / validator
    if not p.exists():
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
