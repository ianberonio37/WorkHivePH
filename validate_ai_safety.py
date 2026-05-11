"""
AI Input Bounds (Safety) -- WorkHive Platform
=================================================
Catches the unbounded-input bug class. WorkHive routes all LLM calls
through `_shared/callAI`, but the input side is not bounded: a fn can
receive a 20MB transcript, never .slice() it, blow past the model's
context window, and burn the entire hourly rate budget on a single
retry storm. Field-worker voice transcripts in noisy environments
frequently produce 30-60 minute monologues that exceed every model's
practical context.

(Note: rate-gate-first ordering and JSON-mode coverage live in
`validate_ai_pattern_compliance.py`. This validator focuses on the
INPUT side -- size, bounds, and source-field hygiene.)

Layer 1 -- Long-form input fields bounded by .slice (DEFERRED ratchet)   [WARN]
  Field names known to carry long user input (transcript, audio_text,
  user_message, raw_text, prompt, speech_text) referenced in a callAI
  fn must have a `.slice(0, N)` cap within 240 chars of the reference.

Layer 2 -- Every callAI fn has at least one input cap                    [WARN]
  Forward-looking ratchet: any edge fn that calls callAI() should
  carry at least one `.slice(0, N)` somewhere -- the proof that some
  upstream bound exists for SOME input.

Layer 3 -- Slice constants are sensible (N ≤ 32000)                      [WARN]
  Catches the `.slice(0, 999999)` cargo-cult anti-pattern that nominally
  bounds input but in practice never trims anything. Context windows
  on free providers cap at ~32k chars; anything larger is bad faith.

Layer 4 -- Per-fn AI input surface inventory (informational)             [INFO]
  Counts of (callAI calls, slice usage, max slice constant) per fn.
  Helps spot fns where bounds are missing.

Skills consulted: ai-engineer (context-window economics, prompt-size
budgets), security (input validation as DoS prevention),
enterprise-compliance (model provider TOS on payload size).
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

# Edge fns that legitimately do not need input bounds (no callAI, or
# router/scheduler fns that don't process user payloads themselves).
SAFETY_OK = {
    "ai-gateway":          "Gateway is the router; downstream specialists bound their own input",
    "scheduled-agents":    "Scheduled cron — payload is server-constructed, not user input",
    "embed-entry":         "Embedding write; uses embedding chain not callAI",
    "semantic-search":     "Read-only vector search; uses embedding chain not callAI",
}

# Forward-looking ratchet — baseline 2026-05-11: 11 fns have unbounded
# long-form input fields and 3 fns have zero slice caps anywhere. Each
# entry lands here on the first run; remove the entry once .slice(0, N)
# is added to the fn. Tracked in PRODUCTION_FIXES (AI safety adoption).
INPUT_BOUND_DEFERRED = True

TRANSCRIPT_FIELDS = [
    "transcript",
    "audio_text",
    "user_message",
    "user_msg",
    "raw_text",
    "prompt",
    "fullText",
    "speech_text",
]

MAX_REASONABLE_SLICE = 32000

CALLAI_RE = re.compile(r"\bcallAI\s*\(")
SLICE_RE  = re.compile(r"\.slice\s*\(\s*0\s*,\s*(?P<n>\d+)\s*\)")


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


def _has_callai(src: str) -> int:
    return len(CALLAI_RE.findall(src))


# -- Layer 1: Long-form input fields bounded by .slice -------------------

def check_field_slices(fns) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for name, path in fns:
        if name in SAFETY_OK:
            continue
        src = _strip_comments(read_file(path) or "")
        if _has_callai(src) == 0:
            continue
        unbounded: list[str] = []
        for field in TRANSCRIPT_FIELDS:
            for m in re.finditer(rf"\b{re.escape(field)}\b", src):
                window = src[m.start(): m.start() + 240]
                if not SLICE_RE.search(window):
                    unbounded.append(field)
                    break
        if unbounded:
            issues.append({
                "check":  "field_slices",
                "reason": f"{name}: long-form field(s) {sorted(set(unbounded))} reach prompt without a .slice(0, N) cap within 240 chars",
                "skip":   INPUT_BOUND_DEFERRED,
            })
        report.append({"fn": name, "unbounded": sorted(set(unbounded))})
    return issues, report


# -- Layer 2: Every callAI fn has at least one input cap ----------------

def check_any_slice_present(fns) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for name, path in fns:
        if name in SAFETY_OK:
            continue
        src = _strip_comments(read_file(path) or "")
        callai = _has_callai(src)
        if callai == 0:
            continue
        slices = SLICE_RE.findall(src)
        if not slices:
            issues.append({
                "check":  "any_slice_present",
                "reason": f"{name}: {callai} callAI invocation(s), 0 .slice(0, N) caps anywhere — no input bound proof",
                "skip":   INPUT_BOUND_DEFERRED,
            })
        report.append({"fn": name, "callai": callai, "slice_count": len(slices)})
    return issues, report


# -- Layer 3: Slice constants are sensible (≤ 32000) --------------------

def check_slice_constants(fns) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for name, path in fns:
        if name in SAFETY_OK:
            continue
        src = _strip_comments(read_file(path) or "")
        if _has_callai(src) == 0:
            continue
        big_slices = []
        for m in SLICE_RE.finditer(src):
            n = int(m.group("n"))
            if n > MAX_REASONABLE_SLICE:
                big_slices.append(n)
        if big_slices:
            issues.append({
                "check":  "slice_constants",
                "reason": f"{name}: .slice cap(s) {big_slices} exceed {MAX_REASONABLE_SLICE} chars — bound is cosmetic, not effective",
            })
        report.append({"fn": name, "big_slices": big_slices})
    return issues, report


# -- Layer 4: Per-fn AI input surface inventory --------------------------

def check_inventory(fns) -> tuple[list[dict], list[dict]]:
    report: list[dict] = []
    for name, path in fns:
        src = _strip_comments(read_file(path) or "")
        c = _has_callai(src)
        if c == 0:
            continue
        slices_n = [int(m.group("n")) for m in SLICE_RE.finditer(src)]
        report.append({
            "fn":          name,
            "callai":      c,
            "slice_count": len(slices_n),
            "max_slice":   max(slices_n) if slices_n else None,
        })
    return [], report


# -- Runner -----------------------------------------------------------------

CHECK_NAMES = [
    "field_slices",
    "any_slice_present",
    "slice_constants",
    "ai_input_inventory",
]
CHECK_LABELS = {
    "field_slices":       "L1  Long-form input fields bounded by .slice(0, N) upstream      [WARN]",
    "any_slice_present":  "L2  Every callAI fn has at least one .slice(0, N) cap            [WARN]",
    "slice_constants":    "L3  .slice constants ≤ 32000 (bound is effective, not cosmetic)  [WARN]",
    "ai_input_inventory": "L4  Per-fn AI input surface inventory                            [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nAI Input Bounds / Safety (4-layer)"))
    print("=" * 60)

    fns = list_edge_fns()
    print(f"  {len(fns)} edge fn(s) scanned (SAFETY_OK={len(SAFETY_OK)}).")
    print(f"  See also: validate_ai_pattern_compliance.py for rate-gate + JSON mode + fallback.\n")

    l1_issues, l1_report = check_field_slices(fns)
    l2_issues, l2_report = check_any_slice_present(fns)
    l3_issues, l3_report = check_slice_constants(fns)
    l4_issues, l4_report = check_inventory(fns)

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l4_report:
        print(f"\n{bold('PER-FN AI INPUT SURFACE (informational)')}")
        print("  " + "-" * 56)
        for r in l4_report[:10]:
            ms = f"max={r['max_slice']}" if r['max_slice'] else "no-slice"
            print(f"  {r['fn']:<32}  callAI={r['callai']:<2}  slices={r['slice_count']:<2}  ({ms})")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":         "ai_safety",
        "total_checks":      total,
        "passed":            n_pass,
        "warned":            n_warn,
        "failed":            n_fail,
        "n_fns":             len(fns),
        "field_slices":      l1_report,
        "any_slice_present": l2_report,
        "slice_constants":   l3_report,
        "inventory":         l4_report,
    }
    try:
        with open("ai_safety_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    except Exception:
        pass

    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
