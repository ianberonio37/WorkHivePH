#!/usr/bin/env python3
"""temporal-answer-names-its-window - T91: a window is a fact, not a request (2026-08-26).

temporal-rag-orchestrator answers "what changed since last month?" by decomposing a range into
periods and folding per-period analyses into one comparison. Its FOLD_SYSTEM rule 7 tells the
model to open with the resolved absolute range, because "last week" is ambiguous - trailing 7 days
versus calendar week, and the PHT boundary - and the numbers cannot be audited without it.

FOUND: that rule was the ONLY thing enforcing it. The handler returned `fold.answer` verbatim, and
the resolved range never appeared in the response at all. A model that skips rule 7 - models do -
produces an answer whose numbers belong to a window nobody can name. That is
two_windows_one_metric arriving through an LLM instead of a query, on figures a supervisor may
carry into a meeting.

★THE REPO ALREADY HAD THE ANSWER TO THIS. Its WAT split says compute the hard facts in code and
let the model write prose from them, which is exactly how the resume summary synthesis was built.
The periods carry their own resolved boundaries, so the range is known before the model is called.
It is now stated in code (prepended only when the model did not already do it, so a compliant
answer is never labelled twice) and returned structurally as `covering`, so a consumer never has
to parse prose to learn which window it is reading.

THE ASSERTION: the handler must not hand `fold.answer` back untouched, and the response must carry
the range.

★A PROMPT RULE IS NOT AN ENFORCEMENT. This gate exists because rule 7 was already written, and
correct, and insufficient.

Usage: python tools/validate_temporal_answer_names_its_window.py
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FN = ROOT / "supabase" / "functions" / "temporal-rag-orchestrator" / "index.ts"


def main() -> int:
    if not FN.exists():
        print("SKIP temporal-answer-names-its-window - temporal-rag-orchestrator not present")
        return 0

    src = FN.read_text(encoding="utf-8", errors="replace")
    fails = []

    # the answer must pass through something that guarantees the window
    body = re.search(r"return new Response\(JSON\.stringify\(\{(?:[^{}]|\{[^{}]*\})*answer:(?:[^{}]|\{[^{}]*\})*\}",
                     src, re.S)
    if not body:
        print("SKIP temporal-answer-names-its-window - could not locate the response body")
        return 0
    blob = body.group(0)

    if re.search(r"answer:\s*fold\.answer\s*\|\|", blob):
        fails.append("the handler returns fold.answer verbatim - if the model skips the range rule, "
                     "the answer carries no window at all")
    if "covering" not in blob:
        fails.append("the response does not carry the resolved range, so a consumer must parse prose "
                     "to learn which window the numbers belong to")
    if not re.search(r"function\s+coveringLabel\b", src) or not re.search(r"function\s+withCovering\b", src):
        fails.append("the deterministic range helpers are gone - the window is being requested from the "
                     "model again rather than stated")

    if fails:
        print(f"FAIL temporal-answer-names-its-window - {len(fails)} problem(s):")
        for x in fails:
            print("    - " + x)
        print("    \"Last month\" is ambiguous and the figures cannot be audited without their range.")
        print("    The periods already know it; state it in code rather than asking the model to.")
        return 1

    print("PASS temporal-answer-names-its-window - the covered range is computed in code, added when the "
          "model omits it, and returned structurally.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
