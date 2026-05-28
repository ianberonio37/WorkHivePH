"""
add_validator_severity.py — one-shot migration tool.
====================================================
Walks run_platform_checks.py's VALIDATORS list and adds an explicit
`"severity": "blocker"` field to every entry that doesn't already have one.

Why: the orchestrator already treats missing severity as "blocker" (safe
default), but explicit declaration makes:
  1. `--severity-min` actually filter meaningfully.
  2. The validator catalog page (P2) renderable.
  3. PR diffs visible when a validator changes tier.

Idempotent. Run multiple times safely.
Default severity = blocker. Future passes can demote individual entries to
"regression" / "warn" / "info" via manual edits or a smarter classifier.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "run_platform_checks.py"

# Heuristic: validators with these substrings in their id deserve "warn"
# instead of "blocker" — they're advisory style/content rules, not
# correctness gates.
WARN_HINTS = {
    "em-dash", "em_dash", "content_quality", "partial_label", "em-dash",
    "console_log", "console-log", "drawing_standards", "drawings",
    "ai_attribution", "seo", "llms_sync", "feedback_widget",
    "industry_defining", "tool_aligned_cta", "revenue_surfaces",
    "ga4_coverage", "embed_integrity",
}

# Validators tagged "info" — pattern miners, audit reports that are
# always advisory rather than failing.
INFO_HINTS = {
    "pattern_mining", "pattern-mining", "edge_pattern", "html_pattern",
    "migration_pattern", "seeder_pattern", "skill_rules", "validator_pattern",
    "js_module_pattern", "python_tool_pattern",
}

# Matches every `{ ... "id": "X", ... },` block in the VALIDATORS list.
# The previous regex required `"id"` to be the first field; many entries
# have a leading comment block or different field order. This version is
# tolerant: any opening brace followed (within the block) by an `"id":`
# key, then any number of further keys, then a closing `}`.
#
# We anchor on the `"id":` to extract the id, then back up to the nearest
# `{` and forward to the matching closing `},`. Done in two passes:
#   1. Find every `"id": "X"` position.
#   2. For each, walk braces to find the enclosing dict literal.
ID_RE = re.compile(r'"id":\s*"([a-z0-9_\-]+)"')
SEVERITY_RE = re.compile(r'"severity":\s*"(blocker|regression|warn|info)"')


def severity_for(vid: str) -> str:
    v = vid.lower()
    for h in INFO_HINTS:
        if h in v: return "info"
    for h in WARN_HINTS:
        if h in v: return "warn"
    return "blocker"


def find_enclosing_dict(text: str, pos: int) -> tuple[int, int] | None:
    """Walk backwards from `pos` to find the nearest unmatched `{`, then
    walk forwards from there to find its matching `}`. Returns (start, end)
    where start is the index of `{` and end is the index AFTER the matching
    `}`."""
    # Backward walk: find the `{` whose matching `}` is past `pos`.
    depth = 0
    i = pos
    while i >= 0:
        c = text[i]
        if c == "}": depth += 1
        elif c == "{":
            if depth == 0:
                start = i
                break
            depth -= 1
        i -= 1
    else:
        return None

    # Forward walk from start.
    depth = 0
    j = start
    while j < len(text):
        c = text[j]
        if c == "{": depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return (start, j + 1)
        j += 1
    return None


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    n_added, n_skipped, n_missed = 0, 0, 0

    # Find every id position; iterate in reverse so insertions don't shift
    # earlier positions.
    positions: list[tuple[int, str]] = [(m.start(), m.group(1)) for m in ID_RE.finditer(text)]

    out = text
    for pos, vid in reversed(positions):
        bounds = find_enclosing_dict(out, pos)
        if not bounds:
            n_missed += 1
            continue
        start, end = bounds
        block = out[start:end]
        # Skip if not inside the VALIDATORS list (heuristic: look back ~3000
        # chars for the VALIDATORS = [ marker. Outside it, we're in some
        # other dict literal like AGENT_ROUTES).
        lookback = max(0, start - 5000)
        prev = out[lookback:start]
        if "VALIDATORS" not in prev:
            continue
        if SEVERITY_RE.search(block):
            n_skipped += 1
            continue
        sev = severity_for(vid)
        # Find indent: the `}` line's indent is the dict's outer indent;
        # inner keys use that + 4. Match the existing "id" line's indent.
        id_line_start = out.rfind("\n", 0, pos) + 1
        indent = out[id_line_start:pos]
        # Inject just before the closing `}`.
        # Need to handle entries that may not end with comma before `}`.
        injection = f'{indent}"severity": "{sev}",\n'
        # Insert right before the position of the closing `}` (i.e. at end - 1
        # we'd be inserting before `}`; preserve any whitespace before it).
        close_pos = end - 1
        # Walk back over whitespace + newlines so injection lands on its own
        # line above `}`.
        insert_pos = close_pos
        while insert_pos > start and out[insert_pos - 1] in " \t":
            insert_pos -= 1
        if insert_pos > 0 and out[insert_pos - 1] != "\n":
            injection = "\n" + injection
        out = out[:insert_pos] + injection + out[insert_pos:]
        n_added += 1

    if out == text:
        print(f"No changes. {n_skipped} already had severity, {n_missed} couldn't be parsed.")
        return 0
    TARGET.write_text(out, encoding="utf-8")
    print(f"Added severity to {n_added} validator(s). {n_skipped} already had one. {n_missed} unparseable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
