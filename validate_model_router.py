"""
Tiered Model Router Validator (Phase 4 of AGENTIC_RAG_ROADMAP.md)
==================================================================
Forward-only L0 ratchet locking the per-task model preference router.

  M01  _shared/ai-chain.ts has TASK_PROFILES export
  M02  TASK_PROFILES covers all 11 expected profile keys
  M03  Every profile in TASK_PROFILES references only free-tier model substrings
  M04  reorderChain() function exported
  M05  callAI options include taskProfile?: string
  M06  callAI uses reorderChain(taskProfile) instead of raw PROVIDER_CHAIN
  M07  agentic-rag-loop Router/Grader/Generator/Checker each pass taskProfile
  M08  hierarchical-summarizer digest passes taskProfile
  M09  FREE-TIER ONLY — no paid model substring in TASK_PROFILES
  M10  No paid-tier name appears in ai-chain.ts anywhere
"""
from __future__ import annotations
import os, sys, re

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

AI_CHAIN  = os.path.join("supabase", "functions", "_shared", "ai-chain.ts")
LOOP_FN   = os.path.join("supabase", "functions", "agentic-rag-loop", "index.ts")
SUM_FN    = os.path.join("supabase", "functions", "hierarchical-summarizer", "index.ts")

EXPECTED_PROFILES = [
    "intent_classification",
    "slot_extraction",
    "single_fact_retrieval",
    "orchestrator_router",
    "chunk_grader",
    "hallucination_checker",
    "multi_step_orchestration",
    "synthesis_long_output",
    "temporal_fold",
    "temporal_subagent",
    "narrative_report",
]

# Models allowed inside TASK_PROFILES values (free-tier substrings only).
ALLOWED_MODEL_SUBSTRINGS = [
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "qwen/qwen3-32b",
    "llama-4-scout-17b-16e-instruct",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "llama-3.3-70b",      # Cerebras name
    "qwen-3-32b",         # Cerebras name
    "llama3.1-8b",        # Cerebras name
    "gemini-2.5-flash-lite",
    "deepseek-v4-flash",
    "nemotron",            # OpenRouter
    "gemma-4",             # OpenRouter
    "gpt-oss-120b:free",   # OpenRouter
    "gemma-3-27b-it",      # OpenRouter
]

PAID_PATTERNS = [r"\bhaiku\b", r"\bsonnet\b", r"\bopus\b", r"claude-3", r"claude-4", r"\bgpt-4\b", r"gpt-4o"]


def check_task_profiles_export() -> list[dict]:
    src = read_file(AI_CHAIN) or ""
    if not re.search(r"export\s+const\s+TASK_PROFILES\s*:\s*Record<string", src):
        return [{"check": "task_profiles_export", "reason": "Missing 'export const TASK_PROFILES: Record<string, string[]>'"}]
    return []


def check_profiles_coverage() -> list[dict]:
    src = read_file(AI_CHAIN) or ""
    issues = []
    for p in EXPECTED_PROFILES:
        if f"{p}:" not in src:
            issues.append({"check": "profiles_coverage", "reason": f"TASK_PROFILES missing profile: {p}"})
    return issues


def check_profiles_free_tier_only() -> list[dict]:
    src = read_file(AI_CHAIN) or ""
    # Grab the TASK_PROFILES block
    m = re.search(r"TASK_PROFILES\s*:\s*Record<string,\s*string\[\]>\s*=\s*\{(.*?)\n\};", src, re.DOTALL)
    if not m:
        return [{"check": "profiles_free_tier", "reason": "Could not locate TASK_PROFILES block"}]
    block = m.group(1)
    # Extract all quoted strings inside arrays
    quoted = re.findall(r'"([^"]+)"', block)
    issues = []
    for s in quoted:
        # Each value must be one of the allowed substrings (or a known profile key).
        if s in EXPECTED_PROFILES: continue   # the key itself, not a value
        is_allowed = any(allowed.lower() in s.lower() or s.lower() in allowed.lower() for allowed in ALLOWED_MODEL_SUBSTRINGS)
        if not is_allowed:
            issues.append({"check": "profiles_free_tier",
                           "reason": f'TASK_PROFILES value "{s}" is not in the allowed free-tier model list'})
    return issues


def check_reorder_chain() -> list[dict]:
    src = read_file(AI_CHAIN) or ""
    if not re.search(r"export\s+function\s+reorderChain\s*\(", src):
        return [{"check": "reorder_chain", "reason": "Missing 'export function reorderChain(taskProfile?: string)'"}]
    return []


def check_callai_options() -> list[dict]:
    src = read_file(AI_CHAIN) or ""
    # Options interface (inline in callAI signature) must include taskProfile.
    if not re.search(r"taskProfile\s*\?\s*:\s*string", src):
        return [{"check": "callai_options", "reason": "callAI options must declare 'taskProfile?: string'"}]
    return []


def check_callai_uses_reorder() -> list[dict]:
    src = read_file(AI_CHAIN) or ""
    # callAI must reorder the chain by task profile AND iterate the reordered
    # result (not the raw PROVIDER_CHAIN const). Two equivalent forms are valid:
    #   (a) inline:   for (const entry of reorderChain(taskProfile)) { ... }
    #   (b) via var:  const chain = reorderChain(taskProfile); ... for (const entry of chain)
    # Form (b) is what sticky-session pinning requires — it splices `chain` to
    # move the pinned model to the front before iterating. The old check only
    # accepted (a) and false-FAILed after the sticky-session refactor.
    inline  = re.search(r"for\s*\(\s*const\s+entry\s+of\s+reorderChain\s*\(", src)
    via_var = (re.search(r"const\s+chain\s*=\s*reorderChain\s*\(", src)
               and re.search(r"for\s*\(\s*const\s+entry\s+of\s+chain\b", src))
    if not (inline or via_var):
        return [{"check": "callai_uses_reorder",
                 "reason": "callAI body must iterate reorderChain(taskProfile) — inline "
                           "`for (const entry of reorderChain(...))` or via "
                           "`const chain = reorderChain(...); for (const entry of chain)` — not raw PROVIDER_CHAIN"}]
    return []


def check_phase1_taskprofiles() -> list[dict]:
    src = read_file(LOOP_FN) or ""
    issues = []
    expected = {
        "orchestrator_router":   "Router stage",
        "chunk_grader":          "Grader stage",
        "synthesis_long_output": "Generator stage",
        "hallucination_checker": "Checker stage",
    }
    for profile, stage in expected.items():
        if f'taskProfile:  "{profile}"' not in src and f'taskProfile: "{profile}"' not in src:
            issues.append({"check": "phase1_taskprofiles",
                           "reason": f"{stage} in agentic-rag-loop must pass taskProfile: \"{profile}\""})
    return issues


def check_phase2_taskprofile() -> list[dict]:
    src = read_file(SUM_FN) or ""
    if not re.search(r'taskProfile\s*:\s*"narrative_report"', src):
        return [{"check": "phase2_taskprofile", "reason": "hierarchical-summarizer digest call must pass taskProfile: \"narrative_report\""}]
    return []


def check_no_paid_in_aichain() -> list[dict]:
    src = (read_file(AI_CHAIN) or "").lower()
    issues = []
    for pat in PAID_PATTERNS:
        if re.search(pat, src):
            issues.append({"check": "no_paid_in_aichain",
                           "reason": f"Forbidden paid-model reference matched /{pat}/ in _shared/ai-chain.ts"})
    return issues


CHECKS = [
    ("task_profiles_export",   "M01 TASK_PROFILES exported",                       check_task_profiles_export),
    ("profiles_coverage",      "M02 All 11 expected profiles covered",             check_profiles_coverage),
    ("profiles_free_tier",     "M03 Profile values are free-tier model substrings", check_profiles_free_tier_only),
    ("reorder_chain",          "M04 reorderChain() exported",                       check_reorder_chain),
    ("callai_options",         "M05 callAI options include taskProfile?: string",   check_callai_options),
    ("callai_uses_reorder",    "M06 callAI iterates reorderChain(taskProfile)",     check_callai_uses_reorder),
    ("phase1_taskprofiles",    "M07 agentic-rag-loop stages pass taskProfile",      check_phase1_taskprofiles),
    ("phase2_taskprofile",     "M08 hierarchical-summarizer passes taskProfile",    check_phase2_taskprofile),
    ("no_paid_in_aichain",     "M09-M10 FREE-TIER ONLY enforced in ai-chain.ts",    check_no_paid_in_aichain),
]


def main() -> int:
    print("\033[1m\nTiered Model Router Validator (Phase 4 of AGENTIC_RAG_ROADMAP.md)\033[0m")
    print("=" * 70)
    all_issues = []
    keys = [c[0] for c in CHECKS]
    labels = {c[0]: c[1] for c in CHECKS}
    for key, _label, fn in CHECKS:
        for issue in fn():
            issue.setdefault("check", key)
            all_issues.append(issue)
    n_pass, n_skip, n_fail = format_result(keys, labels, all_issues)
    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
