"""
AI Payload Hygiene -- WorkHive Platform
==========================================
Catches three payload anti-patterns that silently inflate cost, leak
data, and break prompt caching:

  1. `db.from('x').select('*')` immediately before callAI -- ships every
     column (including PII) into the model and inflates token use.
  2. System prompts built inline (template-string interpolation) instead
     of declared as a module-level const -- defeats prompt caching
     (90% Claude discount goes away).
  3. Unbounded DB reads (no .limit()) feeding LLM context -- a hive with
     50k logbook entries dumps the whole set into one prompt.

(Note: JSON-mode coverage + rate-gate-first + fallback chain live in
`validate_ai_pattern_compliance.py`. This validator focuses on payload
SIZE and CACHE-FRIENDLINESS specifically.)

Layer 1 -- No select('*') directly feeding callAI                        [WARN]
  A `.select('*')` within ~800 chars of a callAI invocation in the same
  edge fn flags as column-hygiene + token-inflation risk.

Layer 2 -- System prompts are module-level const for caching             [WARN]
  Prompts should be `const SYSTEM_PROMPT = ...` at module scope so
  Claude prompt caching can hit them. Inline-built ${...} prompts
  cannot be cached.

Layer 3 -- DB reads feeding LLM are .limit()-bounded                     [WARN]
  Any callAI-invoking fn with DB reads should have at least one
  .limit(N) call. Forward-looking ratchet -- DEFERRED until adoption.

Layer 4 -- Per-fn payload pattern inventory (informational)              [INFO]
  Counts of (select_star, inline_prompt_count, limit_count) per fn.

Skills consulted: ai-engineer (prompt cache, cost optimisation),
security (column-by-default vs explicit-select), performance
(LLM payload size economics).
"""
from __future__ import annotations

import re
import json
import sys
import os
from collections import defaultdict

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


FUNCTIONS_DIR = os.path.join("supabase", "functions")

PAYLOAD_OK = {
    "ai-gateway":      "Router only — does not build prompts directly",
    "semantic-search": "Embedding search; not callAI",
    "embed-entry":     "Embedding write; not callAI",
}

# Forward-looking ratchet — baseline 2026-05-11: 3 fns build prompts
# inline (no module-level const), 2 fns have unbounded DB reads. Each
# fn carries real refactor cost; tracked in PRODUCTION_FIXES (prompt-
# cache adoption + LLM payload bounds).
PAYLOAD_DEFERRED = True

CALLAI_RE        = re.compile(r"\bcallAI\s*\(")
SELECT_STAR_RE   = re.compile(r"""\.select\(\s*['"]\*['"]\s*\)""")
MODULE_PROMPT_RE = re.compile(
    r"""^(?:const|let|var)\s+(\w*(?:PROMPT|SYSTEM|INSTRUCTIONS)\w*)\s*=\s*[`'"]""",
    re.MULTILINE,
)
INLINE_PROMPT_RE = re.compile(
    r"""(?:system|content|prompt)\s*[:=]\s*`[^`]*\$\{[^}]+\}""",
)
LIMIT_RE       = re.compile(r"""\.limit\s*\(\s*\d+\s*\)""")
SELECT_NO_STAR = re.compile(r"""\.from\(\s*['"](\w+)['"]\s*\)\s*\.select\(\s*[^*]""")


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


# -- Layer 1: select('*') near callAI -------------------------------------

def check_select_star_near_callai(fns) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for name, path in fns:
        if name in PAYLOAD_OK:
            continue
        src = _strip_comments(read_file(path) or "")
        if not CALLAI_RE.search(src):
            continue
        callai_positions = [m.start() for m in CALLAI_RE.finditer(src)]
        select_star_positions = [m.start() for m in SELECT_STAR_RE.finditer(src)]
        co_occurrences = 0
        for sp in select_star_positions:
            for cp in callai_positions:
                if cp > sp and (cp - sp) < 800:
                    co_occurrences += 1
                    break
        if co_occurrences:
            issues.append({
                "check":  "select_star_near_callai",
                "reason": f"{name}: {co_occurrences} occurrence(s) of .select('*') within 800 chars of callAI",
            })
        report.append({"fn": name, "select_stars": len(select_star_positions), "co_occur": co_occurrences})
    return issues, report


# -- Layer 2: System prompts module-level for cache hits ----------------

def check_module_prompts(fns) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for name, path in fns:
        if name in PAYLOAD_OK:
            continue
        src = read_file(path) or ""
        if not CALLAI_RE.search(src):
            continue
        module_prompts = MODULE_PROMPT_RE.findall(src)
        inline_count   = len(INLINE_PROMPT_RE.findall(src))
        if not module_prompts and inline_count > 0:
            issues.append({
                "check":  "module_prompts",
                "reason": f"{name}: 0 module-level const PROMPT but {inline_count} inline ${{}}-interpolated prompt(s) — prompt cache will miss",
                "skip":   PAYLOAD_DEFERRED,
            })
        report.append({
            "fn":              name,
            "module_prompts":  module_prompts,
            "inline_prompts":  inline_count,
        })
    return issues, report


# -- Layer 3: DB reads feeding LLM are .limit()-bounded -----------------

def check_limit_bounds(fns) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for name, path in fns:
        if name in PAYLOAD_OK:
            continue
        src = _strip_comments(read_file(path) or "")
        if not CALLAI_RE.search(src):
            continue
        selects = len(SELECT_NO_STAR.findall(src))
        limits  = len(LIMIT_RE.findall(src))
        if selects > 0 and limits == 0:
            issues.append({
                "check":  "limit_bounds",
                "reason": f"{name}: {selects} DB select(s) in a callAI fn, 0 .limit() calls — payload could grow unbounded",
                "skip":   PAYLOAD_DEFERRED,
            })
        report.append({"fn": name, "selects": selects, "limits": limits})
    return issues, report


# -- Layer 4: Per-fn payload pattern inventory ---------------------------

def check_inventory(fns) -> tuple[list[dict], list[dict]]:
    report: list[dict] = []
    for name, path in fns:
        src = _strip_comments(read_file(path) or "")
        if not CALLAI_RE.search(src):
            continue
        report.append({
            "fn":              name,
            "select_star":     len(SELECT_STAR_RE.findall(src)),
            "inline_prompt":   len(INLINE_PROMPT_RE.findall(src)),
            "module_prompt":   len(MODULE_PROMPT_RE.findall(src)),
            "limit":           len(LIMIT_RE.findall(src)),
        })
    return [], report


# -- Runner -----------------------------------------------------------------

CHECK_NAMES = [
    "select_star_near_callai",
    "module_prompts",
    "limit_bounds",
    "payload_inventory",
]
CHECK_LABELS = {
    "select_star_near_callai": "L1  No .select('*') feeding callAI within 800-char window         [WARN]",
    "module_prompts":          "L2  System prompts are module-level const (cache-friendly)        [WARN]",
    "limit_bounds":            "L3  DB reads feeding LLM context bounded by .limit()              [WARN]",
    "payload_inventory":       "L4  Per-fn payload pattern inventory                              [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nAI Payload Hygiene (4-layer)"))
    print("=" * 60)

    fns = list_edge_fns()
    print(f"  {len(fns)} edge fn(s) scanned (PAYLOAD_OK={len(PAYLOAD_OK)}).")
    print(f"  See also: validate_ai_pattern_compliance.py for JSON-mode + rate-gate.\n")

    l1_issues, l1_report = check_select_star_near_callai(fns)
    l2_issues, l2_report = check_module_prompts(fns)
    l3_issues, l3_report = check_limit_bounds(fns)
    l4_issues, l4_report = check_inventory(fns)

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":               "ai_payload_hygiene",
        "total_checks":            total,
        "passed":                  n_pass,
        "warned":                  n_warn,
        "failed":                  n_fail,
        "n_fns":                   len(fns),
        "select_star_near_callai": l1_report,
        "module_prompts":          l2_report,
        "limit_bounds":            l3_report,
        "payload_inventory":       l4_report,
    }
    try:
        with open("ai_payload_hygiene_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    except Exception:
        pass

    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
