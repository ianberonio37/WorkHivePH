"""
AI Pattern Compliance Monitor -- WorkHive Platform
===================================================
Every AI-invoking edge function must follow the platform's standard chain:
rate-limit gate FIRST, then callAI() (which routes through the multi-provider
fallback), with JSON-mode for structured outputs. This validator catches the
four bug classes that bypass the chain — each one costs money or breaks
output contracts.

Layer 1 -- Rate-gate-first violations                                     [WARN]
  callAI() invocations that happen BEFORE checkAIRateLimit() in the same
  serve() handler. A missing or late rate gate lets a buggy hive burn the
  entire AI budget in seconds.

Layer 2 -- Missing fallback chain                                         [WARN]
  Edge functions that fetch directly from OpenAI / Groq / Cerebras /
  OpenRouter / DeepSeek / Gemini endpoints without going through callAI()
  shared chain. Direct calls bypass the multi-provider failover.

Layer 3 -- Structured outputs without JSON mode                           [WARN]
  callAI(... { jsonMode: false }) followed by JSON.parse() — the parser
  expects valid JSON from a model that wasn't told to emit JSON. Every
  whitespace difference is a parse failure.

Layer 4 -- AI-cost concentration                                          [INFO]
  AI fns ranked by callAI() invocation count. Heavy concentration in one
  fn is a fragility / cost-spike signal — useful to know during budget
  reviews even when there's no policy violation.

Skills consulted: ai-engineer (rate-gate-first rule, callAI shared chain,
JSON-mode-for-structured outputs), security (a leaked rate gate is the
fastest way to bankrupt a hive), platform-guardian (informational tier
non-blocking).
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


# ── Paths ─────────────────────────────────────────────────────────────────────

FUNCTIONS_DIR = os.path.join("supabase", "functions")

# Edge functions that legitimately do not need a rate gate (no callAI usage,
# write-only, fixed-cost orchestration). Listed by directory name.
RATE_GATE_EXEMPT = {
    "_shared",                       # shared lib, not an edge fn
    "ai-orchestrator",                # internal aggregator: rate gate enforced upstream
    "scheduled-agents",               # cron scheduler, gates checked per child
    "send-report-email",              # transactional email, no model
    "voice-transcribe",               # whisper only, gated by audio length cap
    "voice-action-router",            # routes to other gated fns; itself a thin dispatcher
    "intelligence-report",            # rate-limited via cron schedule, not per-request
    "intelligence-api",               # public read API, no model
    "engineering-bom-sow",            # rate-limited at the calc layer
    "engineering-calc-agent",         # AI is enrichment-only with a hardcoded fallback;
                                     # user-initiated bounded by the calc UI (no input hive_id).
    "failure-signature-scan",        # cron-driven daily, gated by schedule frequency.
}

# Direct AI provider hostnames / SDK markers we treat as "bypassed the chain".
DIRECT_AI_PATTERNS = [
    r"api\.openai\.com",
    r"api\.groq\.com",
    r"api\.cerebras\.ai",
    r"api\.deepseek\.com",
    r"openrouter\.ai/api",
    r"generativelanguage\.googleapis\.com",   # Gemini direct
]
# Edge functions allowed to talk to providers directly (the shared chain itself,
# plus voice-transcribe which uses OpenAI Whisper).
DIRECT_PROVIDER_EXEMPT = {
    "_shared",
    "voice-transcribe",   # Whisper is not part of the multi-provider chain
}


# ── Discovery ────────────────────────────────────────────────────────────────

def list_edge_fns() -> list[tuple[str, str]]:
    """Return [(fn_name, path)] for every edge function with index.ts."""
    out: list[tuple[str, str]] = []
    if not os.path.isdir(FUNCTIONS_DIR):
        return out
    for d in sorted(os.listdir(FUNCTIONS_DIR)):
        idx = os.path.join(FUNCTIONS_DIR, d, "index.ts")
        if os.path.isfile(idx):
            out.append((d, idx))
    return out


# ── Layer 1: Rate-gate-first violations ──────────────────────────────────────

def check_rate_gate_first(fns: list[tuple[str, str]]) -> tuple[list[dict], list[dict]]:
    """For each fn that uses callAI(), ensure checkAIRateLimit happens BEFORE
    the first callAI in any serve() handler. Position-based check.
    """
    issues: list[dict] = []
    report: list[dict] = []
    for name, path in fns:
        if name in RATE_GATE_EXEMPT:
            continue
        src = read_file(path) or ""
        if "callAI(" not in src:
            continue
        # Walk character-by-character: find the first callAI position and the
        # first checkAIRateLimit position. Skip occurrences inside comments.
        first_callai = src.find("callAI(")
        first_gate   = src.find("checkAIRateLimit")
        # Allow declaration via `const callAI = ...` to not count as a call.
        # Heuristic: if the char immediately before first_callai is '=' or 'st'
        # (from "const callAI = ..."), skip it and look for next.
        i = first_callai
        while i >= 0:
            preceding = src[max(0, i-30):i]
            if "import " in preceding or "function callAI" in preceding or "const callAI" in preceding:
                next_idx = src.find("callAI(", i + 1)
                if next_idx == -1:
                    first_callai = -1
                    break
                i = next_idx
                first_callai = i
                continue
            break
        if first_callai == -1:
            continue
        report.append({
            "fn":             name,
            "callai_pos":     first_callai,
            "rate_gate_pos":  first_gate,
            "gate_first":     first_gate >= 0 and first_gate < first_callai,
        })
        if first_gate < 0:
            issues.append({
                "check": "rate_gate_first", "skip": True,
                "reason": (
                    f"{name}/index.ts uses callAI() but never calls checkAIRateLimit(). "
                    f"Add the rate-limit gate before any model call, or document the "
                    f"exemption in RATE_GATE_EXEMPT in validate_ai_pattern_compliance.py."
                ),
            })
        elif first_gate > first_callai:
            issues.append({
                "check": "rate_gate_first", "skip": True,
                "reason": (
                    f"{name}/index.ts calls callAI() at offset {first_callai} BEFORE "
                    f"checkAIRateLimit() at offset {first_gate}. Order matters — a buggy "
                    f"hive can burn the entire AI budget if the gate runs after the model call."
                ),
            })
    return issues, report


# ── Layer 2: Missing fallback chain ──────────────────────────────────────────

def check_missing_fallback(fns: list[tuple[str, str]]) -> tuple[list[dict], list[dict]]:
    """fetch() to a known AI provider hostname without going through callAI()."""
    issues: list[dict] = []
    report: list[dict] = []
    direct_re = re.compile("|".join(DIRECT_AI_PATTERNS))
    for name, path in fns:
        if name in DIRECT_PROVIDER_EXEMPT:
            continue
        src = read_file(path) or ""
        if not direct_re.search(src):
            continue
        # Allow if the only direct provider mention is inside a comment line
        non_comment = re.sub(r"//[^\n]*", "", src)
        non_comment = re.sub(r"/\*[\s\S]*?\*/", "", non_comment)
        hits = direct_re.findall(non_comment)
        if not hits:
            continue
        report.append({"fn": name, "providers_seen": sorted(set(hits))})
        issues.append({
            "check": "missing_fallback", "skip": True,
            "reason": (
                f"{name}/index.ts fetches a model provider directly ({sorted(set(hits))}) "
                f"instead of going through the shared callAI() multi-provider chain. "
                f"Direct calls bypass failover; route via _shared/ai-chain.ts callAI() "
                f"or add to DIRECT_PROVIDER_EXEMPT with a justification."
            ),
        })
    return issues, report


# ── Layer 3: Structured outputs without JSON mode ────────────────────────────

CALLAI_RE = re.compile(r"callAI\s*\([\s\S]*?\)\s*", re.DOTALL)
JSON_PARSE_RE = re.compile(r"JSON\.parse\s*\(\s*\w*raw\w*", re.IGNORECASE)


def check_json_mode_compliance(fns: list[tuple[str, str]]) -> tuple[list[dict], list[dict]]:
    """callAI() invocations whose result feeds into JSON.parse(...) but were
    not invoked with `jsonMode: true` in their options object.
    """
    issues: list[dict] = []
    report: list[dict] = []
    for name, path in fns:
        if name in RATE_GATE_EXEMPT and name not in {"voice-action-router", "voice-transcribe"}:
            # exempt fns that don't use callAI anyway will short-circuit
            pass
        src = read_file(path) or ""
        if "callAI(" not in src:
            continue
        if "JSON.parse" not in src:
            continue
        # Heuristic: if 'jsonMode: true' appears in any callAI options block,
        # treat it as compliant. Conservative — false negatives are rarer
        # than the bug we're trying to catch.
        # Whitespace-tolerant — jsonMode and `true` may have variable indent.
        if re.search(r"jsonMode\s*:\s*true", src):
            report.append({"fn": name, "json_mode": True})
            continue
        report.append({"fn": name, "json_mode": False})
        issues.append({
            "check": "json_mode_compliance", "skip": True,
            "reason": (
                f"{name}/index.ts calls JSON.parse() on a callAI() response but does "
                f"not pass jsonMode: true. The model is free to wrap output in markdown "
                f"or natural-language preamble; every whitespace difference is a parse "
                f"failure. Add `jsonMode: true` to the callAI options object."
            ),
        })
    return issues, report


# ── Layer 4: AI cost concentration (informational) ────────────────────────────

def check_cost_concentration(fns: list[tuple[str, str]]) -> tuple[list[dict], list[dict]]:
    """Count callAI() invocations per fn. Pure information — no WARN."""
    counts: dict[str, int] = {}
    for name, path in fns:
        src = read_file(path) or ""
        n = src.count("callAI(")
        # Subtract import lines and shared-chain self-references
        if name == "_shared":
            continue
        if n > 0:
            counts[name] = n
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    return [], [{"fn": k, "callai_invocations": v} for k, v in ranked]


# ── Runner ────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "rate_gate_first",
    "missing_fallback",
    "json_mode_compliance",
    "cost_concentration",
]
CHECK_LABELS = {
    "rate_gate_first":      "L1  callAI() called only AFTER checkAIRateLimit()                  [WARN]",
    "missing_fallback":     "L2  No direct fetch() to AI providers (must route via callAI)      [WARN]",
    "json_mode_compliance": "L3  Every callAI() feeding JSON.parse() uses jsonMode: true        [WARN]",
    "cost_concentration":   "L4  AI cost spread across edge fns (informational)                 [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nAI Pattern Compliance (4-layer)"))
    print("=" * 60)

    fns = list_edge_fns()
    print(f"  {len(fns)} edge functions scanned (RATE_GATE_EXEMPT={len(RATE_GATE_EXEMPT)}, "
          f"DIRECT_PROVIDER_EXEMPT={len(DIRECT_PROVIDER_EXEMPT)}).\n")

    rate_issues,    rate_report     = check_rate_gate_first(fns)
    fallback_issues, fallback_report = check_missing_fallback(fns)
    json_issues,    json_report     = check_json_mode_compliance(fns)
    cost_issues,    cost_report     = check_cost_concentration(fns)

    all_issues = rate_issues + fallback_issues + json_issues + cost_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if cost_report:
        print(f"\n{bold('AI INVOCATION RANKING (callAI invocations per fn)')}")
        print("  " + "-" * 56)
        for entry in cost_report[:10]:
            print(f"  {entry['fn']:<40}  {entry['callai_invocations']}")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":             "ai_pattern_compliance",
        "total_checks":          total,
        "passed":                n_pass,
        "warned":                n_warn,
        "failed":                n_fail,
        "rate_gate_report":      rate_report,
        "missing_fallback":      fallback_report,
        "json_mode_report":      json_report,
        "cost_concentration":    cost_report,
        "issues":                [i for i in all_issues if not i.get("skip")],
        "warnings":              [i for i in all_issues if i.get("skip")],
    }
    with open("ai_pattern_compliance_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
