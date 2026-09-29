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

# ★TWO STALE LISTS AGREEING WITH EACH OTHER IS NOT A CHECK (2026-09-28).
# A hand-maintained `ALLOWED_MODEL_SUBSTRINGS` used to live here, and it began with exactly the four
# model IDs that v5 had already deleted from PROVIDER_CHAIN: llama-3.1-8b-instant,
# llama-3.3-70b-versatile, qwen/qwen3-32b, llama-4-scout-17b-16e-instruct. Those four were also the
# entire vocabulary of TASK_PROFILES. So M03 compared a stale list against a stale list, agreed with
# itself, and printed PASS for a router in which NOT ONE profile matched a live chain entry -
# reorderChain's `matched` array came back empty every single call and the tiered router silently
# reordered nothing. The gate could not have caught it: nothing in this file had ever read
# PROVIDER_CHAIN, the thing the profiles are supposed to be substrings OF.
#
# Derive it instead. `chain_models()` reads the real PROVIDER_CHAIN out of ai-chain.ts, so the
# allowed set updates itself the moment a model is added or dropped, and a profile that names a
# model the chain no longer carries fails LOUDLY instead of passing quietly. This is the same repair
# validate_groq_fallback.check_models_are_live made one layer down, where a deny-list of 14 retired
# names was replaced by asking the provider. Free-tier-ness comes along for free: PROVIDER_CHAIN is
# free-tier-only by rule, enforced by M09/M10 below and L4 of validate_groq_fallback.
def chain_models() -> list[str]:
    """Every `model:` in ai-chain.ts's PROVIDER_CHAIN, as written there."""
    src = read_file(AI_CHAIN) or ""
    m = re.search(r"const PROVIDER_CHAIN[^=]*=\s*\[([\s\S]+?)\n\];", src)
    if not m:
        return []
    return re.findall(r'\bmodel:\s*"([^"]+)"', m.group(1))

PAID_PATTERNS = [r"\bhaiku\b", r"\bsonnet\b", r"\bopus\b", r"claude-3", r"claude-4", r"\bgpt-4\b", r"gpt-4o"]

# Freshness anchors (P3 of SELF_IMPROVING_GATE_ROADMAP.md): the load-bearing
# symbols this validator asserts. validate_validator_freshness.py checks these
# still exist in their target file at G-1, so a rename in ai-chain.ts surfaces
# *cheaply* as "model_router is asserting a shape the code moved past" instead
# of as an opaque full-gate FAIL. (M06 already rotted once this way.)
FRESHNESS_ANCHORS = [
    ("supabase/functions/_shared/ai-chain.ts",
     r"export\s+const\s+TASK_PROFILES", "M01 TASK_PROFILES export"),
    ("supabase/functions/_shared/ai-chain.ts",
     r"export\s+function\s+reorderChain\s*\(", "M04 reorderChain symbol"),
    ("supabase/functions/agentic-rag-loop/index.ts",
     r"taskProfile", "M07 loop passes taskProfile"),
]


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


def profile_values() -> tuple[list[str], str | None]:
    """The model substrings written inside TASK_PROFILES, with `//` comments removed.

    The comments are stripped because this file's own explanatory notes quote model IDs, and a bare
    `"([^"]+)"` sweep would grade the prose as if it were configuration.
    """
    src = read_file(AI_CHAIN) or ""
    m = re.search(r"TASK_PROFILES\s*:\s*Record<string,\s*string\[\]>\s*=\s*\{(.*?)\n\};", src, re.DOTALL)
    if not m:
        return [], "Could not locate TASK_PROFILES block"
    block = re.sub(r"^\s*//.*$", "", m.group(1), flags=re.MULTILINE)
    return [s for s in re.findall(r'"([^"]+)"', block) if s not in EXPECTED_PROFILES], None


def check_profiles_free_tier_only() -> list[dict]:
    """M03: every profile value must name a model PROVIDER_CHAIN actually carries.

    Matched exactly the way reorderChain matches it at runtime -
    `entry.model.toLowerCase().includes(value.toLowerCase())` - so a PASS here means the profile
    really does select an entry, not merely that it resembles something on a list.
    """
    values, err = profile_values()
    if err:
        return [{"check": "profiles_free_tier", "reason": err}]
    models = chain_models()
    if not models:
        return [{"check": "profiles_free_tier",
                 "reason": "Could not read PROVIDER_CHAIN out of ai-chain.ts - refusing to grade "
                           "TASK_PROFILES against an empty chain (that is how M03 passed for a "
                           "router in which nothing matched)."}]
    issues = []
    for s in values:
        if not any(s.lower() in mdl.lower() for mdl in models):
            issues.append({"check": "profiles_free_tier",
                           "reason": f'TASK_PROFILES value "{s}" matches no model in PROVIDER_CHAIN '
                                     f'({len(models)} entries) - reorderChain will never select it, '
                                     f'so every caller passing this profile silently gets the default order'})
    return issues


def check_every_profile_selects() -> list[dict]:
    """M11: every profile as a WHOLE must end up selecting at least one chain entry.

    M03 grades each value; this grades each PROFILE. They differ in the case that actually bit us:
    a profile whose values are individually plausible but which, together, match nothing - and a
    profile is what a caller passes. `matched.length === 0` is the precise condition under which
    reorderChain returns the base chain and the router becomes decoration.
    """
    src = read_file(AI_CHAIN) or ""
    m = re.search(r"TASK_PROFILES\s*:\s*Record<string,\s*string\[\]>\s*=\s*\{(.*?)\n\};", src, re.DOTALL)
    if not m:
        return [{"check": "profile_selects", "reason": "Could not locate TASK_PROFILES block"}]
    block = re.sub(r"^\s*//.*$", "", m.group(1), flags=re.MULTILINE)
    models = chain_models()
    if not models:
        return [{"check": "profile_selects", "reason": "Could not read PROVIDER_CHAIN out of ai-chain.ts"}]
    issues = []
    for name, arr in re.findall(r"(\w+)\s*:\s*\[([^\]]*)\]", block):
        vals = re.findall(r'"([^"]+)"', arr)
        if not vals:
            continue
        if not any(v.lower() in mdl.lower() for v in vals for mdl in models):
            issues.append({"check": "profile_selects",
                           "reason": f'TASK_PROFILES.{name} = {vals} selects NOTHING from the '
                                     f'{len(models)}-entry PROVIDER_CHAIN - reorderChain returns the '
                                     f'base order, so this profile is inert'})
    return issues


def selftest() -> int:
    """Teeth: the check must FAIL on the exact configuration that shipped for 18 days.

    Guards against the vacuity this gate had - 9/9 PASS while no profile matched anything.
    """
    models = chain_models()
    dead = ["llama-3.1-8b-instant", "llama-3.3-70b-versatile",
            "qwen/qwen3-32b", "llama-4-scout-17b-16e-instruct"]
    cases = [
        ("PROVIDER_CHAIN is readable (>= 6 entries)", len(models) >= 6),
        ("the four v4 names the router used to hold match NOTHING today",
         all(not any(d.lower() in m.lower() for m in models) for d in dead)),
        ("today's profile values all match a live chain entry", not check_profiles_free_tier_only()),
        ("every profile selects at least one entry", not check_every_profile_selects()),
    ]
    ok = all(v for _n, v in cases)
    for name, v in cases:
        print(("  PASS  " if v else "  FAIL  ") + name)
    print("  selftest: " + ("teeth intact" if ok else
                            "VACUOUS - M03 is grading against something other than the live chain"))
    return 0 if ok else 1


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
    # Form (c) — the iteration is delegated to a helper that RECEIVES reorderChain's
    # output: `attemptChain(applySticky(reorderChain(taskProfile, true)))` and attemptChain
    # does `for (const entry of chainArr)`. This is the autoswitch/sticky refactor; the
    # old check false-FAILed it because the for-loop and reorderChain() sit in different fns.
    via_helper = (re.search(r"attemptChain\s*\([^;]*reorderChain\s*\(", src)
                  and re.search(r"for\s*\(\s*const\s+\w+\s+of\s+chainArr\b", src))
    if not (inline or via_var or via_helper):
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
    ("profiles_free_tier",     "M03 Every profile value matches a live PROVIDER_CHAIN model", check_profiles_free_tier_only),
    ("profile_selects",        "M11 Every profile selects >= 1 chain entry (router not inert)", check_every_profile_selects),
    ("reorder_chain",          "M04 reorderChain() exported",                       check_reorder_chain),
    ("callai_options",         "M05 callAI options include taskProfile?: string",   check_callai_options),
    ("callai_uses_reorder",    "M06 callAI iterates reorderChain(taskProfile)",     check_callai_uses_reorder),
    ("phase1_taskprofiles",    "M07 agentic-rag-loop stages pass taskProfile",      check_phase1_taskprofiles),
    ("phase2_taskprofile",     "M08 hierarchical-summarizer passes taskProfile",    check_phase2_taskprofile),
    ("no_paid_in_aichain",     "M09-M10 FREE-TIER ONLY enforced in ai-chain.ts",    check_no_paid_in_aichain),
]


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
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
