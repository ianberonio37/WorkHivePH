#!/usr/bin/env python3
"""edge-refusal-reaches-user - T82: don't show the user supabase-js's placeholder (2026-08-26).

supabase-js collapses EVERY non-2xx from functions.invoke into one FunctionsHttpError whose
message is the literal string "Edge Function returned a non-2xx status code". The status and
the body are still there, on `error.context` (a Response) - but a caller that reads only
`error.message` never sees them, and shows that placeholder to a person.

★THE CLIENT THEN SILENTLY UNDOES THE WORK THE BACKEND DID. rate-limit.ts answers a drained
hive with 429 and "AI call limit reached for this hive. Try again in an hour." - cause named,
clearing time named. Measured on asset-hub, the worker read "Could not reach Asset Brain: Edge
Function returned a non-2xx status code" instead: a CONNECTION-flavoured sentence for a QUOTA
event, sending them to check their signal rather than wait an hour. whAiError could not rescue
it either, since it keys on /429|rate.?limit|quota/ and the placeholder carries none of them.
Fixed centrally: utils.js whFnError() reads error.context, so the function's own sentence
survives and only a body-less failure falls back to the status taxonomy.

WHAT IT COUNTS: invoke error branches that put `error.message` in front of a user (a toast,
innerHTML, textContent, a whListError/whReadError call) without consulting error.context or
whFnError anywhere in the file.

★IT COUNTS RATHER THAN FORBIDS, because the backlog is real: 42 invoke sites across 18 files,
and only a handful unwrap. A gate that failed all of them on day one would be turned off. The
baseline ratchets forward only, so the count can fall and never climb.

★AND IT ONLY FLAGS BRANCHES THAT SPEAK. An invoke whose error is logged, swallowed, or rethrown
shows nobody the placeholder; charging for it would measure code shape rather than the harm.

★THE RESIDUAL IS KNOWN, AND CHASING IT TO ZERO WOULD MEAN EDITING CORRECT CODE. The count fell
16 -> 5 on 2026-08-26 as real sites were converted; every one of the remaining 5 was then read, and
all are artefacts of this gate's region heuristic (it flags a region containing BOTH a "speaks"
token and an error.message anywhere within it, which is cheap and occasionally wrong):
  * logbook.html cmms-push-completion and shift-brain.html shift-planner-orchestrator - console.warn
    only; shift-brain then restores an honest empty state. Neither shows anyone anything.
  * engineering-design.js - deliberately withholds the raw error, its comment saying it "leaks
    internals + unhelpful", with the full error going to console.error. That is the RIGHT call.
  * marketplace.html marketplace-listing-assist and project-manager.html embed-entry - prefer the
    function's own data.error, or are fire-and-forget.
So the honest reading of a 5 here is "5 flagged, 0 harmful". The baseline stays as a ratchet against
NEW placeholders rather than a debt to pay down; if it ever rises, that rise is the signal.

Usage: python tools/validate_edge_refusal_reaches_user.py
"""
import glob
import io
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "tools" / "edge_refusal_baseline.json"
SKIP = re.compile(r"_bak|backup|node_modules|_fixtures|^index-.*test|battery|^maplibre", re.I)

INVOKE = re.compile(r"functions\.invoke\s*\(")
# the error branch shows something to a person
SPEAKS = re.compile(r"showToast|innerHTML|textContent|whListError|whReadError|whAiError|whWriteError|alert\s*\(")
# ...using the placeholder-bearing message
USES_MSG = re.compile(r"\b(?:error|err|e)\s*(?:\?\.|\.)\s*message\b")
# ★A LOCAL UNWRAP COUNTS TOO. report-sender solved this before the shared helper existed,
# with its own _fnErrorReason(data, error, fallback) that reads error.context correctly - and
# this gate charged it anyway, because the region did not literally contain '.context'.
# Charging a page for solving the problem its own way is how a gate teaches people to ignore it.
UNWRAPS = re.compile(r"\.context\b|whFnError|\w*[Ee]rrorReason\s*\(")


def strip_comments(src: str) -> str:
    def blank(m):
        return "".join(c if c == "\n" else " " for c in m.group(0))
    s = re.sub(r"<!--.*?-->", blank, src, flags=re.S)
    # (?!quote): accept="image/*" is NOT a comment opener
    s = re.sub(r"/\*(?![\"']).*?\*/", blank, s, flags=re.S)
    return re.sub(r"(?m)^[ \t]*//[^\n]*$", blank, s)


def main() -> int:
    files = sorted(glob.glob(str(ROOT / "*.html"))) + sorted(glob.glob(str(ROOT / "*.js")))
    sites, findings = 0, []
    for f in files:
        name = Path(f).name
        if SKIP.search(name):
            continue
        src = strip_comments(io.open(f, encoding="utf-8", errors="replace").read())
        if not INVOKE.search(src):
            continue
        file_unwraps = bool(UNWRAPS.search(src))
        for m in INVOKE.finditer(src):
            sites += 1
            # the handling that follows this invoke, bounded by the next invoke
            nxt = INVOKE.search(src, m.end())
            region = src[m.end():nxt.start() if nxt else min(len(src), m.end() + 2600)]
            if not (SPEAKS.search(region) and USES_MSG.search(region)):
                continue
            if file_unwraps and UNWRAPS.search(region):
                continue
            findings.append(f"{name}:{src[:m.start()].count(chr(10)) + 1}")

    cur = len(findings)
    base = 10 ** 6
    if BASELINE.exists():
        try:
            base = int(json.loads(BASELINE.read_text(encoding="utf-8")).get("count", base))
        except (OSError, ValueError):
            base = 10 ** 6

    print(f"  invoke sites: {sites} | error branches showing the placeholder: {cur} (baseline {base if base < 10**6 else '-'})")
    for x in findings[:8]:
        print("    - " + x)

    if not BASELINE.exists():
        BASELINE.write_text(json.dumps({"count": cur, "note": "T82 forward-only: this may fall, never climb"},
                                       indent=2), encoding="utf-8")
        print(f"PASS edge-refusal-reaches-user - baseline recorded at {cur}.")
        return 0
    if cur > base:
        print(f"FAIL edge-refusal-reaches-user - {cur - base} new site(s) show supabase-js's placeholder")
        print("    to a person. \"Edge Function returned a non-2xx status code\" is not a reason: it hides a")
        print("    429 the function worded carefully, and reads as a connection fault, so a rate-limited")
        print("    worker goes to check their signal instead of waiting. Use whFnError(error, fallback).")
        return 1
    if cur < base:
        BASELINE.write_text(json.dumps({"count": cur, "note": "T82 forward-only: this may fall, never climb"},
                                       indent=2), encoding="utf-8")
        print(f"PASS edge-refusal-reaches-user - improved {base} -> {cur}; baseline tightened.")
        return 0
    print(f"PASS edge-refusal-reaches-user - holding at {cur}; no new placeholder shown to a user.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
