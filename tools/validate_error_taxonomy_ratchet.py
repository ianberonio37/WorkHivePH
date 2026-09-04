#!/usr/bin/env python3
"""error-taxonomy ratchet — T176's "new errors are born compliant" gate (2026-08-26).

The platform has three taxonomy helpers — whReadError / whWriteError / whAiError —
that turn a raw failure into a sentence naming the CAUSE, the state of the user's
WORK, and the NEXT STEP. Adoption was driven page by page across several arcs. The
risk now is regression by accretion: a new `showToast('Something went wrong')`
costs nothing to write and quietly re-opens the class.

WHAT THIS COUNTS: user-facing failure strings handed to showToast / setStatus /
textContent / innerHTML inside (or right after) a catch or an `if (error)` branch,
where NO taxonomy helper appears on the same line. That is the RAW-APPEND class.

Forward-only ratchet against tools/error_taxonomy_baseline.json — the count may
fall (and the baseline auto-lowers), never rise. It deliberately does NOT try to
judge sentence quality: a lint that guesses at prose produces false reds, while a
count of raw appends is objective and is exactly the regression signal.

★ZERO IS NOT THE GOAL. Audited 2026-08-26 by reading the remainder one by one:
much of what is left is well-written raw sentences that already name cause, work
state and next step ("Wrong username or password.", "A logbook entry can only be
corrected by its author", "Someone else changed this feedback. Your note was not
saved") — they simply do not route through a helper. Rewriting those to lower the
number would make the copy WORSE to move a metric. Convert what ECHOES A DRIVER
MESSAGE or says nothing useful; leave sentences that already do the job.

Usage: python tools/validate_error_taxonomy_ratchet.py
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
BASELINE = ROOT / "tools" / "error_taxonomy_baseline.json"

# a user-facing sink carrying a string literal
SINK_RE = re.compile(
    r"(showToast|setStatus|textContent\s*=|innerHTML\s*=)\s*\(?\s*['\"`]([^'\"`]{12,240})['\"`]"
)
# failure vocabulary — the strings this gate is about
FAIL_RE = re.compile(
    r"(could ?n[o']t|could not|failed|unable|error|went wrong|problem|not saved|did not|didn't)",
    re.I,
)
# the helpers that make a failure string compliant
# whVoiceError joined 2026-08-27. The Web Speech API reports failures as bare codes, and three call
# sites pasted the code into a toast ('Voice error: network', 'Mic error: aborted'). It is a real
# taxonomy member, not a rename: the vocabulary is closed and specified, each branch names the cause
# and the remedy, and every branch says the same load-bearing thing - dictation failing never
# discards what is already typed, which is the one fact a person needs and none of the three sites
# said. Same admission test as the others: it maps a failure to a sentence that answers what
# happened, what happened to the WORK, and what to do next.
TAXONOMY_RE = re.compile(r"wh(Read|Write|Ai|List|Voice)Error|whIsAuthFailure|why_refused")
# a nearby failure context (same line or the 3 lines above)
CONTEXT_RE = re.compile(r"catch\s*\(|if\s*\(\s*!?\s*\w*(error|err)\b|\.error\b", re.I)


def scan():
    hits = []
    for f in sorted(glob.glob(str(ROOT / "*.html"))):
        lines = io.open(f, encoding="utf-8", errors="replace").read().splitlines()
        for i, line in enumerate(lines):
            m = SINK_RE.search(line)
            if not m:
                continue
            msg = m.group(2)
            if not FAIL_RE.search(msg):
                continue
            if TAXONOMY_RE.search(line):
                continue
            window = "\n".join(lines[max(0, i - 3): i + 1])
            if not CONTEXT_RE.search(window):
                continue
            hits.append((Path(f).name, i + 1, msg[:70]))
    return hits


def main() -> int:
    hits = scan()
    count = len(hits)
    per_file = {}
    for f, _, _ in hits:
        per_file[f] = per_file.get(f, 0) + 1
    for f, n in sorted(per_file.items(), key=lambda kv: -kv[1])[:10]:
        print(f"  {f}: {n}")

    if not BASELINE.exists():
        BASELINE.write_text(json.dumps({"count": count, "established": "2026-08-26"}, indent=1), encoding="utf-8")
        print(f"BASELINE established: {count} raw failure strings outside the taxonomy (forward-only)")
        return 0

    base = json.loads(BASELINE.read_text(encoding="utf-8")).get("count", 0)
    if count > base:
        print(f"FAIL error-taxonomy-ratchet — raw failure strings GREW {base} -> {count}.")
        for f, ln, msg in hits[-6:]:
            print(f"    {f}:{ln}  {msg}")
        print("    Route new failure copy through whReadError / whWriteError / whAiError.")
        return 1
    if count < base:
        BASELINE.write_text(json.dumps({"count": count, "ratcheted": "auto"}, indent=1), encoding="utf-8")
        print(f"PASS error-taxonomy-ratchet — improved {base} -> {count}; ratchet lowered.")
        return 0
    print(f"PASS error-taxonomy-ratchet — held at {count} raw failure strings (baseline {base}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
