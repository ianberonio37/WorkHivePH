"""
Voice Canonical Anchor Validator -- WorkHive Platform
======================================================
Guards the canonical-data path on the voice companion surface
(voice-handler.js). The voice surface bypasses the AI gateway and goes
direct to a Cloudflare worker LLM, so the canonical anchor has to be
enforced LOCALLY inside voice-handler.js: classify the worker's
transcript, fetch the figure from v_*_truth, inject it as a DATA block
in the system prompt, and tell the model to anchor on it.

Without these four parts wired together, Hard Rule #2 ("never invent
numbers") + Rule #9 ("no inventing UI") leaves the model only one legal
answer ("check Analytics") -- which is what the walkthrough caught on
2026-05-13 with the MTBF question.

Layers:

  L1  _classifyDataIntent() exists in voice-handler.js and matches the
      canonical intents (mtbf, mttr, downtime, risk_top, failures_count).

  L2  _fetchCanonicalData() exists and reads at least one v_*_truth
      view (v_kpi_truth + v_risk_truth today).

  L3  _converseInline() calls the classifier AND awaits the fetch
      BEFORE _buildVoiceSystemPrompt(). If the call is missing, the
      DATA block can never reach the model.

  L4  _buildVoiceSystemPrompt() includes a CANONICAL DATA section and a
      hard rule telling the model to anchor verbatim on those numbers.

Snapshot, not ratcheted -- the surface is one file and the rule set is
small. Regression here means the voice surface stopped routing to
canonical data; fix the file.

Skills consulted: ai-engineer (RAG-style data injection patterns),
qa (cross-surface gating), platform-guardian (gate registration).
"""
from __future__ import annotations

import os
import sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


VOICE_HANDLER_JS = "voice-handler.js"

REQUIRED_INTENTS = ("mtbf", "mttr", "downtime", "risk_top", "failures_count")
REQUIRED_TRUTH_VIEWS = ("v_kpi_truth", "v_risk_truth")


def check_intent_classifier(src):
    issues = []
    if "_classifyDataIntent" not in src:
        issues.append({
            "check": "intent_classifier",
            "reason": "_classifyDataIntent() is missing from voice-handler.js. Without it, voice questions for MTBF / OEE / risk can never be detected before the LLM call.",
        })
        return issues
    missing = [k for k in REQUIRED_INTENTS if f"'{k}'" not in src and f'"{k}"' not in src]
    if missing:
        issues.append({
            "check": "intent_classifier",
            "reason": f"_classifyDataIntent() does not emit kind values for: {', '.join(missing)}. Canonical-data intents must round-trip through the classifier.",
        })
    return issues


def check_canonical_fetch(src):
    issues = []
    if "_fetchCanonicalData" not in src:
        issues.append({
            "check": "canonical_fetch",
            "reason": "_fetchCanonicalData() is missing. The classifier with no fetch produces nothing to inject; the worker still gets a vague 'check Analytics' reply.",
        })
        return issues
    missing_views = [v for v in REQUIRED_TRUTH_VIEWS if v not in src]
    if missing_views:
        issues.append({
            "check": "canonical_fetch",
            "reason": f"_fetchCanonicalData() does not read these v_*_truth views: {', '.join(missing_views)}. KPI questions need v_kpi_truth; risk ranking needs v_risk_truth.",
        })
    return issues


def check_converse_wiring(src):
    issues = []
    # The fetch must be awaited BEFORE _buildVoiceSystemPrompt, otherwise
    # the DATA block can't reach the model on this turn.
    # ★THIS CHECK PASSED FOR AS LONG AS THE FEATURE EXISTED, ON A FILE WHERE NEITHER FUNCTION WAS EVER
    # CALLED. It used rfind() and called that "the call site" -- but rfind returns the DEFINITION when
    # there is nothing else, and the three definitions happen to sit in the order the check wants
    # (_classifyDataIntent at ~895, _fetchCanonicalData at ~946, _buildVoiceSystemPrompt at ~6508). So
    # the gate certifying that the companion answers MTBF questions from v_kpi_truth was reading the
    # order in which those functions are DECLARED. Found 2026-09-08 when adding three self-test cases
    # moved the last _classifyDataIntent( past the fetch and the check finally spoke.
    #
    # A call site is an occurrence that is NOT a declaration. Anything preceded by `function ` or
    # `async function ` is the definition; everything else is somebody invoking it.
    def call_sites(name):
        needle = name + "("
        out, i = [], src.find(needle)
        while i != -1:
            before = src[max(0, i - 20):i]
            if not before.rstrip().endswith("function"):
                out.append(i)
            i = src.find(needle, i + 1)
        return out

    classifier_sites = call_sites("_classifyDataIntent")
    fetch_sites      = call_sites("_fetchCanonicalData")
    builder_sites    = call_sites("_buildVoiceSystemPrompt")
    for label, sites in (("_classifyDataIntent", classifier_sites),
                         ("_fetchCanonicalData", fetch_sites),
                         ("_buildVoiceSystemPrompt", builder_sites)):
        if not sites:
            issues.append({
                "check": "converse_wiring",
                "reason": (label + " is DEFINED but never called. The canonical-data path is built and "
                           "unreachable: a worker's MTBF question is answered from the legacy scraper, "
                           "not from v_kpi_truth."),
            })
    if issues:
        return issues
    # compare the LAST call of each, which is the conversation path
    classifier_call = classifier_sites[-1]
    fetch_call      = fetch_sites[-1]
    builder_call    = builder_sites[-1]
    # the classifier is also exercised by the self-test table, which sits after the conversation path in
    # this file; the wiring question is about the call that FEEDS the fetch, so use the last classifier
    # call that still precedes it
    earlier = [i for i in classifier_sites if i < fetch_call]
    if earlier:
        classifier_call = earlier[-1]
    if classifier_call < 0 or fetch_call < 0 or builder_call < 0:
        issues.append({
            "check": "converse_wiring",
            "reason": "voice-handler.js is missing at least one of the call sites: _classifyDataIntent / _fetchCanonicalData / _buildVoiceSystemPrompt. The canonical path is wired through these three.",
        })
        return issues
    if not (classifier_call < fetch_call < builder_call):
        issues.append({
            "check": "converse_wiring",
            "reason": "Call order is wrong: _classifyDataIntent must run BEFORE _fetchCanonicalData which must run BEFORE _buildVoiceSystemPrompt. Otherwise the DATA block can't reach this turn's prompt.",
        })
    # The builder must be invoked with a canonicalData argument (7 args).
    # Cheap heuristic: the call site must be a multi-arg call that
    # includes the word canonicalData. Less brittle than a strict regex.
    builder_call_window = src[builder_call:builder_call + 400]
    if "canonicalData" not in builder_call_window:
        issues.append({
            "check": "converse_wiring",
            "reason": "_buildVoiceSystemPrompt() is called without a canonicalData argument. Pass the fetch result through so the prompt gets the DATA block.",
        })
    return issues


def check_prompt_data_block(src):
    issues = []
    # The builder must accept canonicalData as a parameter and embed it
    # as a DATA section in the system prompt, with an explicit "anchor
    # verbatim" instruction.
    if "function _buildVoiceSystemPrompt" not in src:
        issues.append({
            "check": "prompt_data_block",
            "reason": "_buildVoiceSystemPrompt definition missing.",
        })
        return issues
    builder_def = src.find("function _buildVoiceSystemPrompt")
    builder_end = src.find("\n  }\n", builder_def)
    if builder_end < 0:
        builder_end = builder_def + 4000
    window = src[builder_def:builder_end]
    if "canonicalData" not in window:
        issues.append({
            "check": "prompt_data_block",
            "reason": "_buildVoiceSystemPrompt does not accept canonicalData. The classifier + fetch produce a string that has nowhere to go.",
        })
    if "CANONICAL DATA" not in window:
        issues.append({
            "check": "prompt_data_block",
            "reason": "_buildVoiceSystemPrompt does not emit a 'CANONICAL DATA' header. The model needs an unambiguous section to anchor on.",
        })
    if "anchor" not in window.lower() and "verbatim" not in window.lower():
        issues.append({
            "check": "prompt_data_block",
            "reason": "_buildVoiceSystemPrompt does not instruct the model to anchor / use the figures verbatim. Without the instruction the model may paraphrase the digits.",
        })
    return issues


CHECKS = (
    ("intent_classifier",  "Layer 1 -- _classifyDataIntent() exists + emits all canonical intent kinds"),
    ("canonical_fetch",    "Layer 2 -- _fetchCanonicalData() exists + reads v_kpi_truth + v_risk_truth"),
    ("converse_wiring",    "Layer 3 -- _converseInline() wires classifier -> fetch -> builder in order with canonicalData arg"),
    ("prompt_data_block",  "Layer 4 -- _buildVoiceSystemPrompt() accepts canonicalData + emits CANONICAL DATA section + anchor rule"),
)


def main():
    if "--selftest" in sys.argv:
        return selftest()

    print("== Voice Canonical Anchor Validator ==\n")
    src = read_file(VOICE_HANDLER_JS)
    if src is None:
        print(f"  FAIL  voice-handler.js not found at {VOICE_HANDLER_JS}")
        return 1

    issues = []
    issues += check_intent_classifier(src)
    issues += check_canonical_fetch(src)
    issues += check_converse_wiring(src)
    issues += check_prompt_data_block(src)

    check_names  = [c[0] for c in CHECKS]
    check_labels = dict(CHECKS)
    n_pass, n_skip, n_fail = format_result(check_names, check_labels, issues)

    print(f"\nResult: {n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL")
    return 0 if n_fail == 0 else 1


def _strip_calls(text, name):
    """Return `text` with every CALL to `name` renamed away, definitions left intact."""
    out, i, needle = [], 0, name + "("
    while True:
        j = text.find(needle, i)
        if j == -1:
            out.append(text[i:])
            break
        before = text[max(0, j - 20):j]
        if before.rstrip().endswith("function"):
            out.append(text[i:j + len(needle)])
        else:
            out.append(text[i:j])
            out.append("renamedAway(")
        i = j + len(needle)
    return "".join(out)


def selftest():
    """Does this gate BITE? It did not, for as long as the feature existed.

    The wiring check used rfind() and treated the result as a call site. With no call sites at all,
    rfind returns the DEFINITION - and the three definitions sit in exactly the order the check wants,
    so it printed PASS while the canonical-data path was unreachable. These cases pin the repair: a file
    carrying only the definitions must FAIL, and must name every function it could not find a caller for.
    """
    src = read_file(VOICE_HANDLER_JS)
    if src is None:
        print(f"  FAIL  voice-handler.js not found at {VOICE_HANDLER_JS}")
        return 1
    stripped = src
    for n in ("_classifyDataIntent", "_fetchCanonicalData", "_buildVoiceSystemPrompt"):
        stripped = _strip_calls(stripped, n)
    only_defs = check_converse_wiring(stripped)
    reasons = " ".join(i["reason"] for i in only_defs)

    cases = [
        ("the real file wires the path", not check_converse_wiring(src)),
        ("definitions alone FAIL", bool(only_defs)),
        ("and every uncalled function is named",
         all(n in reasons for n in ("_classifyDataIntent", "_fetchCanonicalData", "_buildVoiceSystemPrompt"))),
        ("the stripper actually removed the calls", stripped != src),
        ("a definition is not counted as a caller", len(only_defs) == 3),
    ]
    ok = 0
    for name, good in cases:
        print(("  PASS  " if good else "  FAIL  ") + name)
        ok += 1 if good else 0
    print()
    if ok == len(cases):
        print(f"All {ok} teeth cases passed.")
        return 0
    print(f"{len(cases) - ok} of {len(cases)} teeth cases failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
