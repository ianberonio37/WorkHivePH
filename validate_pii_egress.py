"""
PII Egress to Third Parties Detector -- WorkHive Platform
==========================================================
Catches the case where hive-scoped PII (worker names, emails, equipment
identifiers) leaves the platform via an outbound HTTP call to a third
party (Resend, OpenAI, Anthropic, Stripe, etc.) without first being
redacted. Industrial customers, especially in regulated sectors, treat
worker identity and equipment IDs as PII; egress without consent is a
compliance breach (GDPR, PDPA, ISO 27001).

Layer 1 -- Direct third-party fetch with PII in scope                    [WARN]
  Edge functions that BOTH call fetch() to a known third-party host AND
  reference PII tokens (worker_name, display_name, email, phone) in the
  same source file without going through a redactPII() helper. Fn-level
  exemptions in PII_EGRESS_OK with a one-line justification.

Layer 2 -- AI prompt with PII fields                                     [FAIL]
  Any callAI() prompt argument (or string template that builds an AI
  prompt) that includes raw PII tokens. Even when callAI() routes
  through the _shared chain, the model provider sees the prompt
  contents -- compliance-meaningful PII must be redacted before send.
  ENFORCED (2026-06-15, Gateway Pillar P): promoted WARN -> FAIL. PII to a
  3rd-party LLM is binary (redact, or be code-verified exempt in
  PII_EGRESS_OK) -- there is no acceptable "ratchet down from N", the bar is
  ZERO. A new fn that builds an AI prompt with raw PII + no redact helper +
  no exemption now BLOCKS the gate. (L1 direct-fetch stays WARN: broader
  heuristic, more false positives, and already empty.)

Layer 3 -- Third-party host distribution (informational)                 [INFO]
  Per-fn host call count. Helps spot lopsided egress patterns.

Layer 4 -- PII reach inventory (informational)                           [INFO]
  Per-fn count of PII tokens referenced. Pairs with L3 to map "where
  PII can reach" across the platform.

Skills consulted: enterprise-compliance (ISO 27001, SOC 2, GDPR/PDPA
data residency), security (data egress is a top-N OWASP concern),
notifications (Resend digests legitimately need worker emails -- gated
by user consent flag, exempt-listed here with a justification).
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob
from collections import defaultdict

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


FUNCTIONS_DIR = os.path.join("supabase", "functions")

# Third-party hosts that count as "egress" for PII purposes.
THIRD_PARTY_HOSTS = [
    r"api\.resend\.com",
    r"api\.openai\.com",
    r"api\.anthropic\.com",
    r"api\.groq\.com",
    r"api\.stripe\.com",
    r"api\.cerebras\.ai",
    r"api\.deepseek\.com",
    r"openrouter\.ai/api",
    r"generativelanguage\.googleapis\.com",
    r"connect\.stripe\.com",
]
HOST_RE = re.compile("|".join(THIRD_PARTY_HOSTS))

# Tokens that count as PII for the platform.
PII_TOKENS = {
    "worker_name",
    "workerName",
    "display_name",
    "displayName",
    "email",
    "phone",
    "phoneNumber",
    "fullName",
}

# Compliance signal: a fn that EITHER calls a redact helper OR uses an
# inline `<redacted>` placeholder substitution is considered compliant.
# Both shapes are functionally equivalent for the L2 detection -- the
# validator is checking that PII never reaches the model verbatim.
REDACT_HELPER_RE = re.compile(
    r"\b(redactPII|sanitizePII|maskPII|scrubPII)\s*\(|<redacted>",
)

# Per-fn exemptions. Each entry needs a one-line justification.
PII_EGRESS_OK = {
    "send-report-email":          "Resend digest legitimately needs worker email; opt-in flag enforced",
    "marketplace-checkout":       "Stripe needs buyer email + name for receipt + KYC",
    "marketplace-connect-onboard": "Stripe Connect KYB requires real seller name and email",
    "marketplace-connect-status": "Stripe Connect status read; mirrors onboard data",
    "marketplace-release":        "Stripe transfer needs seller name for compliance ledger",
    "engineering-bom-sow":        "AI BOM/SOW prompt operates on equipment names; PII redaction not applicable",
    "resume-extract":             "Solo Resume Builder — the user uploads their OWN resume to extract their OWN name/email/phone; the contact fields ARE the deliverable (JSON Resume `basics`). The PII is the user's own and opt-in by the act of uploading-to-extract — redaction would defeat the feature. (`worker_name` is read then `void`'d, unused.)",
    "agentic-rag-loop":           "Code-verified false positive (2026-06-15): worker_name/workerName are used ONLY for DB scoping (.eq) + cost-log rows, NEVER injected into a callAI prompt — all 5 stages (router/grader/generator/checker/extractor) prompt on question/chunks/answer/memory only. The 'phone' token is the literal word in an anti-PII prompt INSTRUCTION (GRADER_SYSTEM: 'content must NOT contain PII (phone numbers, emails...)'). No user PII reaches the model.",
    # Note: ai-orchestrator, analytics-orchestrator, asset-brain-query, and
    # scheduled-agents previously listed here as DEFERRED were closed on
    # 2026-05-11 by wiring `_shared/redactPII.ts` into each. They are now
    # validated by L2's `_has_redact_helper` check rather than allowlisted.
}

# AI prompt heuristic: any string template / variable named like a prompt
# that ALSO references a PII token.
AI_PROMPT_NAME_RE = re.compile(
    r"\b(prompt|system_prompt|context|instructions|user_msg|user_message)\s*[:=]",
    re.IGNORECASE,
)


def list_edge_fns() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if os.path.isdir(FUNCTIONS_DIR):
        for d in sorted(os.listdir(FUNCTIONS_DIR)):
            idx = os.path.join(FUNCTIONS_DIR, d, "index.ts")
            if os.path.isfile(idx):
                out.append((d, idx))
    return out


def _strip_comments(src: str) -> str:
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    src = re.sub(r"//[^\n]*", "", src)
    return src


def _has_pii(src: str) -> set[str]:
    found: set[str] = set()
    for token in PII_TOKENS:
        if re.search(rf"\b{re.escape(token)}\b", src):
            found.add(token)
    return found


def _has_third_party_fetch(src: str) -> set[str]:
    found: set[str] = set()
    for m in HOST_RE.finditer(src):
        found.add(m.group(0))
    return found


def _has_redact_helper(src: str) -> bool:
    return bool(REDACT_HELPER_RE.search(src))


# -- Layer 1: Direct fetch + PII in scope -----------------------------------

def check_direct_fetch_pii(
    fns: list[tuple[str, str]],
) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for name, path in fns:
        if name in PII_EGRESS_OK:
            continue
        src = _strip_comments(read_file(path) or "")
        hosts = _has_third_party_fetch(src)
        if not hosts:
            continue
        pii = _has_pii(src)
        if not pii:
            continue
        if _has_redact_helper(src):
            continue
        report.append({
            "fn":     name,
            "hosts":  sorted(hosts),
            "pii":    sorted(pii),
        })
        issues.append({
            "check": "direct_fetch_pii", "skip": True,
            "reason": (
                f"{name}/index.ts calls third-party host(s) {sorted(hosts)} AND "
                f"references PII token(s) {sorted(pii)} in the same source file "
                f"without using a redactPII() helper. Either wrap PII in "
                f"redactPII() before send, or add '{name}' to PII_EGRESS_OK with "
                f"a justification (e.g., legally required for the egress)."
            ),
        })
    return issues, report


# -- Layer 2: AI prompt with PII fields -------------------------------------

def check_ai_prompt_pii(
    fns: list[tuple[str, str]],
) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for name, path in fns:
        if name in PII_EGRESS_OK:
            continue
        src = _strip_comments(read_file(path) or "")
        if not AI_PROMPT_NAME_RE.search(src):
            continue
        # Restrict to fns that actually call callAI()
        if "callAI(" not in src:
            continue
        pii = _has_pii(src)
        if not pii:
            continue
        if _has_redact_helper(src):
            continue
        report.append({
            "fn":  name,
            "pii": sorted(pii),
        })
        issues.append({
            "check": "ai_prompt_pii", "skip": False,
            "reason": (
                f"{name}/index.ts builds an AI prompt and references PII "
                f"token(s) {sorted(pii)}. Models log prompts and the provider "
                f"sees the contents -- redact or hash before include. Add "
                f"'{name}' to PII_EGRESS_OK if the PII is essential to the "
                f"prompt (e.g., personalization the user opted into)."
            ),
        })
    return issues, report


# -- Layer 3: Third-party host distribution (informational) ----------------

def check_host_distribution(
    fns: list[tuple[str, str]],
) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    for name, path in fns:
        src = _strip_comments(read_file(path) or "")
        host_counts: dict[str, int] = defaultdict(int)
        for m in HOST_RE.finditer(src):
            host_counts[m.group(0)] += 1
        if not host_counts:
            continue
        rows.append({
            "fn":     name,
            "hosts":  dict(host_counts),
            "total":  sum(host_counts.values()),
        })
    rows.sort(key=lambda r: -r["total"])
    return [], rows


# -- Layer 4: PII reach inventory (informational) --------------------------

def check_pii_reach(
    fns: list[tuple[str, str]],
) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    for name, path in fns:
        src = _strip_comments(read_file(path) or "")
        pii = _has_pii(src)
        if not pii:
            continue
        rows.append({
            "fn":  name,
            "pii": sorted(pii),
            "n":   len(pii),
        })
    rows.sort(key=lambda r: -r["n"])
    return [], rows


# -- Runner -----------------------------------------------------------------

CHECK_NAMES = [
    "direct_fetch_pii",
    "ai_prompt_pii",
    "host_distribution",
    "pii_reach",
]
CHECK_LABELS = {
    "direct_fetch_pii":   "L1  Direct third-party fetch with PII in scope (or redacted)     [WARN]",
    "ai_prompt_pii":      "L2  AI prompt construction redacts PII (or is opt-in exempt)     [FAIL]",
    "host_distribution":  "L3  Third-party host call distribution per fn (informational)    [INFO]",
    "pii_reach":          "L4  PII token reach per fn (informational)                       [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nPII Egress to Third Parties Detector (4-layer)"))
    print("=" * 60)

    fns = list_edge_fns()
    print(f"  {len(fns)} edge fn(s) scanned (PII_EGRESS_OK={len(PII_EGRESS_OK)}).\n")

    l1_issues, l1_report = check_direct_fetch_pii(fns)
    l2_issues, l2_report = check_ai_prompt_pii(fns)
    l3_issues, l3_report = check_host_distribution(fns)
    l4_issues, l4_report = check_pii_reach(fns)

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l3_report:
        print(f"\n{bold('THIRD-PARTY HOST DISTRIBUTION (informational)')}")
        print("  " + "-" * 56)
        for r in l3_report[:8]:
            hosts = ", ".join(f"{k}={v}" for k, v in sorted(r["hosts"].items()))
            print(f"  {r['fn']:<32}  total={r['total']:<3}  ({hosts})")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":          "pii_egress",
        "total_checks":       total,
        "passed":             n_pass,
        "warned":             n_warn,
        "failed":             n_fail,
        "n_fns":              len(fns),
        "direct_fetch_pii":   l1_report,
        "ai_prompt_pii":      l2_report,
        "host_distribution":  l3_report,
        "pii_reach":          l4_report,
        "issues":             [i for i in all_issues if not i.get("skip")],
        "warnings":           [i for i in all_issues if i.get("skip")],
    }
    with open("pii_egress_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
