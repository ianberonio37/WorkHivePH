"""
JS Syntax Sanity Validator -- WorkHive Platform Guardian
========================================================
Inline `<script>` blocks in HTML files don't go through a build step, so
parse-time SyntaxErrors at the top of a script make the ENTIRE block
silently dead -- no event handlers wired, no init code, no DOM
population. Lower scripts run, so the page paints partially and the bug
looks like "some pieces are missing" rather than "page is broken".

This validator catches the specific bug class that surfaced 2026-05-12
during a visual walkthrough: `await` inside a non-async function. The
home-page Today's One Thing IIFE was declared `(function () { ... })()`
but contained `await Promise.allSettled([...])`, which is a parse-time
SyntaxError. 130 validators PASSed; the user found it via inspection.

L1 -- await outside async (FAIL)
  For each inline `<script>` block, find every function-defining
  construct (function decl, function expr, arrow fn). If it lacks the
  `async` keyword AND its body contains `await` at the top level (not
  nested inside another async function), FAIL with the file:line of the
  offending function start.

  Detection is heuristic but precise:
    - Brace walker tracks nesting depth.
    - Inside each candidate body, we step into nested function/arrow
      bodies to skip them (their own async-ness is checked separately).
    - `await` appearing at depth 0 of the candidate body, while we're
      not inside a string/comment, is the failure signal.

Future layers (deferred until needed):
  L2 -- top-level return outside function
  L3 -- unbalanced template literal / unterminated string
  L4 -- Node-based full parse via `node -c -e ...` when available

Skills consulted: qa-tester (visual-walkthrough catches → validator
discipline, memory 2026-05-12), frontend (inline script semantics),
validator-design-patterns (brace walker over non-greedy regex).
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


EXCLUDED_HTML = ("-test.html", ".backup.html", "_backup.html", ".backup")


# ---------------------------------------------------------------------------
# Brace walker that skips strings + comments + template literals.
# Position-aware so we can report file:line on failures.
# ---------------------------------------------------------------------------

def _find_matching_brace(src: str, open_pos: int) -> int:
    """src[open_pos] must be '{'. Return the index of the matching '}'
    or -1 if unbalanced. Honours strings, template literals, line +
    block comments."""
    assert src[open_pos] == "{"
    n = len(src)
    depth = 0
    i = open_pos
    while i < n:
        c = src[i]
        # Line comment
        if c == "/" and i + 1 < n and src[i+1] == "/":
            nl = src.find("\n", i)
            i = (n if nl == -1 else nl + 1)
            continue
        # Block comment
        if c == "/" and i + 1 < n and src[i+1] == "*":
            end = src.find("*/", i + 2)
            i = (n if end == -1 else end + 2)
            continue
        # Single / double quoted string
        if c == "'" or c == '"':
            q = c
            i += 1
            while i < n:
                if src[i] == "\\":
                    i += 2; continue
                if src[i] == q:
                    i += 1; break
                if src[i] == "\n":  # unterminated single-line string
                    break
                i += 1
            continue
        # Template literal (can be multiline, contains ${ ... } interpolations)
        if c == "`":
            i += 1
            while i < n:
                if src[i] == "\\":
                    i += 2; continue
                if src[i] == "`":
                    i += 1; break
                # ${...} interpolation -- recurse via brace walker
                if src[i] == "$" and i + 1 < n and src[i+1] == "{":
                    end = _find_matching_brace(src, i + 1)
                    i = (n if end == -1 else end + 1)
                    continue
                i += 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _line_no(src: str, pos: int) -> int:
    return src.count("\n", 0, pos) + 1


def _strip_strings_and_comments(src: str) -> str:
    """Return src with strings, template literals, and comments replaced
    by spaces (preserving offsets so line numbers stay accurate)."""
    out = list(src)
    n = len(src)
    i = 0
    while i < n:
        c = src[i]
        if c == "/" and i + 1 < n and src[i+1] == "/":
            nl = src.find("\n", i)
            end = (n if nl == -1 else nl)
            for j in range(i, end): out[j] = " "
            i = end; continue
        if c == "/" and i + 1 < n and src[i+1] == "*":
            end = src.find("*/", i + 2)
            end = (n if end == -1 else end + 2)
            for j in range(i, end):
                if src[j] != "\n":
                    out[j] = " "
            i = end; continue
        if c == "'" or c == '"' or c == "`":
            q = c
            out[i] = " "
            i += 1
            while i < n:
                if src[i] == "\\" and i + 1 < n:
                    out[i] = " "; out[i+1] = " "; i += 2; continue
                if src[i] == q:
                    out[i] = " "; i += 1; break
                if q != "`" and src[i] == "\n":
                    break
                if src[i] != "\n":
                    out[i] = " "
                i += 1
            continue
        i += 1
    return "".join(out)


# ---------------------------------------------------------------------------
# Function-definition discovery
# ---------------------------------------------------------------------------

# Function declarations: `function NAME?() {` optionally async.
# This is unambiguous because `function` is a reserved word in JS.
FUNC_DECL_RE = re.compile(
    r"(?P<async>\basync\s+)?\bfunction\b\s*(?:\w+\s*)?\([^)]*\)\s*\{",
)

# Arrow functions: we DON'T use a forward regex because `[^)]*` greedily
# eats across function-call arg commas (e.g. `addEventListener('x', async
# () => {` matches as a single bogus arrow whose params are `('x', async ()`).
# Instead, find every `=> {` and walk BACKWARD to determine the real
# param boundary + async-ness.
ARROW_BODY_RE = re.compile(r"=>\s*\{")


def _walk_back_arrow_params(src: str, arrow_pos: int):
    """Given the position of `=>` in src, find the arrow's param-list
    start position. Returns (params_start, is_async) or None if the
    pattern preceding `=>` doesn't look like an arrow function (i.e.
    the `=>` is part of a larger token, or there's no valid param form).

    Arrow params are either:
      (a) A balanced `(...)` group immediately preceding `=>` (modulo
          whitespace). Walk back from `)` to its matching `(`.
      (b) A single bare identifier immediately preceding `=>` (modulo
          whitespace). Walk back through word chars.

    After we've located the param-list start, check whether `async`
    immediately precedes (with optional whitespace). Returns the
    earliest position (start of `async` if async, else start of params)
    so callers can correctly attribute async-ness.
    """
    i = arrow_pos - 1
    # Skip whitespace right before `=>`.
    while i >= 0 and src[i] in " \t\n\r":
        i -= 1
    if i < 0:
        return None
    if src[i] == ")":
        # Balanced-paren param list. Walk backward to matching `(`.
        depth = 1
        j = i - 1
        while j >= 0 and depth > 0:
            c = src[j]
            if c == ")":
                depth += 1
            elif c == "(":
                depth -= 1
                if depth == 0:
                    break
            j -= 1
        if j < 0 or depth != 0:
            return None
        params_start = j   # index of `(`
    elif src[i].isalnum() or src[i] == "_" or src[i] == "$":
        # Single bare-identifier param. Walk back through word chars.
        j = i
        while j >= 0 and (src[j].isalnum() or src[j] == "_" or src[j] == "$"):
            j -= 1
        params_start = j + 1
    else:
        # Doesn't look like an arrow (`=>` is probably part of a
        # comparison or unrelated token). Skip.
        return None

    # Check for `async` keyword immediately before params_start.
    k = params_start - 1
    while k >= 0 and src[k] in " \t\n\r":
        k -= 1
    is_async = False
    fn_start = params_start
    if k >= 4 and src[k-4:k+1] == "async":
        # Must be a word boundary before `async`.
        prev = src[k-5] if k >= 5 else None
        if prev is None or not (prev.isalnum() or prev == "_" or prev == "$"):
            is_async = True
            fn_start = k - 4
    return (fn_start, is_async)


def _find_async_function_bodies(src_clean: str):
    """Yield (is_async, fn_start, body_open, body_close) for every function/
    arrow with a braced body in src_clean. body_open is the index of `{`,
    body_close is the index of matching `}`."""
    out = []

    # Function declarations / expressions (unambiguous via the `function`
    # keyword).
    for m in FUNC_DECL_RE.finditer(src_clean):
        is_async = bool(m.group("async"))
        open_pos = m.end() - 1
        close = _find_matching_brace(src_clean, open_pos)
        if close == -1:
            continue
        out.append((is_async, m.start(), open_pos, close))

    # Arrow functions via back-walk from `=> {`.
    for m in ARROW_BODY_RE.finditer(src_clean):
        arrow_pos = m.start()   # index of `=`
        info = _walk_back_arrow_params(src_clean, arrow_pos)
        if info is None:
            continue
        fn_start, is_async = info
        # body_open is the `{` after the `=>` ; m.end() is one past `{`
        # because the regex matches `=>\s*\{`.
        body_open = m.end() - 1
        close = _find_matching_brace(src_clean, body_open)
        if close == -1:
            continue
        out.append((is_async, fn_start, body_open, close))

    out.sort(key=lambda t: t[2])
    return out


def _await_at_top_level(body_src: str, all_fns) -> int | None:
    """Return the position of the first top-level `await` in body_src, or
    None. body_src indices align with the global src (use slices). all_fns
    is the list of function bodies; we use it to skip over nested ones."""
    # Build a set of (open, close) ranges that fall *inside* this body so
    # we can skip them.
    return None  # placeholder; we compute against the global src in caller


# ---------------------------------------------------------------------------
# Main check
# ---------------------------------------------------------------------------

def check_inline_scripts(path: str):
    issues = []
    src = read_file(path) or ""
    if not src:
        return issues
    # Iterate over inline <script>...</script> blocks (skip src= scripts).
    script_rx = re.compile(
        r"<script(?![^>]*\bsrc\s*=)[^>]*>([\s\S]*?)</script>",
        re.IGNORECASE,
    )
    for sm in script_rx.finditer(src):
        block_start = sm.start(1)
        block_src = sm.group(1)
        cleaned = _strip_strings_and_comments(block_src)
        fns = _find_async_function_bodies(cleaned)
        if not fns: continue
        # For each non-async function, scan body for top-level `await`.
        # Skip ranges that fall inside nested fns (we walk in source order
        # and pop ranges as we move past them).
        for is_async, fn_start, body_open, body_close in fns:
            if is_async: continue
            body_inner = cleaned[body_open + 1:body_close]   # exclusive of braces
            # Walk body_inner; skip nested fn bodies.
            # Filter to DIRECT children only: any fn contained inside another
            # nested fn (grand-child) is already skipped when we jump past
            # the parent, so we don't want it in our skip list. Linear pass:
            # sort nested by open position, keep only those not contained in
            # the previous direct child.
            all_inside = sorted([
                (o, c)
                for (a, s, o, c) in fns
                if o > body_open and c < body_close   # strictly inside
            ])
            direct = []
            last_close = -1
            for o, c in all_inside:
                if o > last_close:
                    direct.append((o, c))
                    last_close = c
            nested = [
                (o - (body_open + 1), c - (body_open + 1))
                for (o, c) in direct
            ]
            # Sort + walk.
            nested.sort()
            i = 0
            n = len(body_inner)
            ni = 0
            while i < n:
                # Skip nested fn body if we entered one.
                if ni < len(nested) and i == nested[ni][0]:
                    i = nested[ni][1] + 1
                    ni += 1
                    continue
                # await keyword at top level.
                if (body_inner[i:i+5] == "await"
                        and (i + 5 >= n or not body_inner[i+5].isalnum())
                        and (i == 0 or not body_inner[i-1].isalnum())):
                    abs_pos = block_start + body_open + 1 + i
                    line = _line_no(src, abs_pos)
                    fn_line = _line_no(src, block_start + fn_start)
                    issues.append({
                        "check":  "await_outside_async",
                        "page":   path,
                        "line":   line,
                        "reason": (
                            f"{path}:{line} uses `await` inside a non-async "
                            f"function/IIFE declared at line {fn_line}. JS "
                            f"parsers raise SyntaxError at parse time, which "
                            f"silently kills the entire <script> block. Add "
                            f"`async` to the enclosing function/IIFE, or "
                            f"move the await into an inner `(async () => "
                            f"{{ ... }})()` IIFE."
                        ),
                    })
                    break   # one finding per function is enough
                i += 1
    return issues


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

CHECK_NAMES  = ["await_outside_async"]
CHECK_LABELS = {
    "await_outside_async": "L1  No `await` inside a non-async function/IIFE in inline scripts [FAIL]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nJS Syntax Sanity Validator (1-layer)"))
    print("=" * 60)

    files = [p for p in sorted(glob.glob("*.html"))
             if not any(p.endswith(x) for x in EXCLUDED_HTML)]
    print(f"  {len(files)} HTML files scanned\n")

    issues = []
    for path in files:
        issues += check_inline_scripts(path)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {len(CHECK_NAMES)} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "js_syntax_sanity",
        "total_checks": len(CHECK_NAMES),
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "n_files":      len(files),
        "issues":       [i for i in issues if not i.get("skip")],
        "warnings":     [i for i in issues if i.get("skip")],
    }
    with open("js_syntax_sanity_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
