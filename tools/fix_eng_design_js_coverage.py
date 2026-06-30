#!/usr/bin/env python3
# audit-scope-allow: one-shot maintenance fixer over the validate_*.py suite (not HTML/edge code).
"""
Autofix: add "engineering-design.js" to the page-list of every validator that scans
engineering-design.html for JS-level constructs (so the 2.14MB extracted bundle stays
covered). Inserts the .js sibling immediately after the LITERAL list entry
"engineering-design.html". SKIPS non-list contexts (const assignment `ENG = "..."`,
dict key `"...":`, comment lines) — those are structural and handled by hand.

Dry-run by default; pass --apply to write. Compile-checks every modified file.
"""
from __future__ import annotations
import re, sys, py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPLY = "--apply" in sys.argv

JS_TOKENS = [
    "db.from(", ".from('", '.from("', ".select(", ".insert(", ".upsert(", ".update(",
    ".delete(", ".rpc(", ".channel(", ".subscribe(", ".on('", '.on("', "innerHTML",
    "outerHTML", "insertAdjacentHTML", "setInterval", "setTimeout", "clearInterval",
    "addEventListener", "removeEventListener", "getElementById", "querySelector",
    "localStorage", "sessionStorage", "functions.invoke(", ".eq(", ".gte(", ".ilike(",
    ".textContent", "URLSearchParams", "searchParams", "classList", "trapFocus",
    "showToast", "Promise.all", "JSON.stringify", "toLocaleDateString", "renderSourceChip",
    "onclick", "new Function(", "eval(",
]

LIT_RE = re.compile(r'(["\'])engineering-design\.html\1')

def classify_match(txt: str, m: re.Match) -> str:
    """Return 'list' | 'const' | 'dict' | 'comment' | 'unknown' for a literal match."""
    start, end = m.start(), m.end()
    line_start = txt.rfind("\n", 0, start) + 1
    line = txt[line_start:txt.find("\n", end) if txt.find("\n", end) != -1 else len(txt)]
    if line.lstrip().startswith("#"):
        return "comment"
    after = txt[end:end + 4].lstrip()
    if after[:1] == ":":
        return "dict"
    # char before opening quote (skip ws)
    before = txt[max(0, start - 6):start].rstrip()
    if before.endswith("="):
        return "const"
    # list entry: preceded by [ or , or ( (tuple) or start-of-line inside a multi-line list
    if before.endswith(("[", ",", "(")) or before == "" or after[:1] in (",", "]", ")"):
        return "list"
    return "unknown"

def main():
    targets = sorted(ROOT.glob("validate_*.py")) + sorted((ROOT / "tools").glob("validate_*.py"))
    applied, skipped_struct, skipped_nojs, errors = [], [], [], []
    for p in targets:
        txt = p.read_text(encoding="utf-8", errors="replace")
        if '"engineering-design.js"' in txt or "'engineering-design.js'" in txt:
            continue  # already covered
        if not any(t in txt for t in JS_TOKENS):
            continue  # doesn't search JS constructs -> html-only, leave alone
        matches = list(LIT_RE.finditer(txt))
        if not matches:
            skipped_struct.append((p.name, "no literal entry (html-glob / dynamic discovery)"))
            continue
        # pick the FIRST list-entry match
        target_m = None
        for m in matches:
            if classify_match(txt, m) == "list":
                target_m = m
                break
        if target_m is None:
            kinds = {classify_match(txt, m) for m in matches}
            skipped_struct.append((p.name, f"literal present but not a list entry ({','.join(sorted(kinds))})"))
            continue
        q = target_m.group(1)
        old = f"{q}engineering-design.html{q}"
        new = f"{q}engineering-design.html{q}, {q}engineering-design.js{q}"
        # replace only the single target span
        new_txt = txt[:target_m.start()] + new + txt[target_m.end():]
        if APPLY:
            p.write_text(new_txt, encoding="utf-8")
            try:
                py_compile.compile(str(p), doraise=True)
            except py_compile.PyCompileError as e:
                errors.append((p.name, str(e)))
                p.write_text(txt, encoding="utf-8")  # revert
                continue
        applied.append(p.name)

    print(f"{'APPLIED' if APPLY else 'DRY-RUN'} — eng-design.js coverage fix")
    print(f"\n  would-add to list ({len(applied)}):")
    for n in applied:
        print(f"    + {n}")
    print(f"\n  structural / manual ({len(skipped_struct)}):")
    for n, why in skipped_struct:
        print(f"    ? {n:45} {why}")
    if errors:
        print(f"\n  COMPILE ERRORS (reverted) ({len(errors)}):")
        for n, e in errors:
            print(f"    ! {n}: {e}")

if __name__ == "__main__":
    main()
