#!/usr/bin/env python3
"""validate_no_interpolated_filter_injection.py — T368's lock: no edge function interpolates user input into a
PostgREST logic filter (.or/.filter/.match/.textSearch template) WITHOUT first stripping the filter
metacharacters — so a comma or paren in a search term cannot break out of one condition and inject another.

PostgREST parses .or("a.ilike.X,b.eq.Y") by SPLITTING on commas and grouping on parens. A raw
`.or(\`machine.ilike.%${q}%\`)` with q='x,id.gt.0' becomes two conditions — the search filter is bypassable
(RLS still bounds the rows, but the intended filter is defeated, and a stray '(' returns 400 "failed to parse
logic tree"). The two live call sites (agentic-rag-loop, visual-defect-capture) both sanitize first:
`.replace(/[,()\\]/g, " ")` strips the breakout chars and `.replace(/%/g,"\\%").replace(/_/g,"\\_")` escapes
the ILIKE wildcards. This gate holds that discipline: any file that builds an interpolated logic filter MUST
carry that metacharacter strip, or a future edit reopens the injection.

Static source lock (browser-free). Read-only. Registered in run_platform_checks (Platform).
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FNDIR = ROOT / "supabase" / "functions"

CHECK_NAMES = ["no-interpolated-filter-injection"]

# an interpolated PostgREST logic-filter call: .or/.filter/.match/.textSearch( `...${...}...` )
_INTERP_FILTER = re.compile(r"\.(?:or|filter|match|textSearch)\(\s*`[^`]*\$\{", re.S)
# the metacharacter strip that makes it safe: .replace(/[,()...]/ ...  (must include comma + paren)
_SANITIZE = re.compile(r"\.replace\(\s*/\[[^\]]*,[^\]]*[()][^\]]*\]/|\.replace\(\s*/\[[^\]]*[()][^\]]*,[^\]]*\]/")


def check_file(src: str) -> bool:
    """True if this file is SAFE (no interpolated filter, OR it sanitizes)."""
    if not _INTERP_FILTER.search(src):
        return True
    return bool(_SANITIZE.search(src))


def scan() -> list[str]:
    problems: list[str] = []
    for idx in sorted(FNDIR.glob("*/index.ts")):
        src = idx.read_text(encoding="utf-8", errors="replace")
        if not check_file(src):
            problems.append(f"{idx.parent.name}: interpolates user input into a PostgREST logic filter "
                            f"(.or/.filter) without a [,()] metacharacter strip — a comma in the term breaks "
                            f"out of the condition (filter injection).")
    return problems


def main() -> int:
    if not FNDIR.exists():
        print("SKIP no-interpolated-filter-injection — supabase/functions not found."); return 0
    problems = scan()
    if problems:
        print("FAIL no-interpolated-filter-injection — an interpolated PostgREST filter is not sanitized:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS no-interpolated-filter-injection — every edge fn that interpolates into a PostgREST logic "
          "filter first strips the [,()] breakout chars (and escapes %/_), so a search term cannot inject a "
          "second condition.")
    return 0


def self_test() -> int:
    fails = []
    safe = 'const safeQ = q.trim().replace(/[,()\\\\]/g, " ").replace(/%/g,"\\\\%");\n q.or(`machine.ilike.%${safeQ}%`);'
    if not check_file(safe):
        fails.append("a sanitized interpolated filter should PASS")
    unsafe = 'const q2 = q.trim();\n q.or(`machine.ilike.%${q2}%,root_cause.ilike.%${q2}%`);'
    if check_file(unsafe):
        fails.append("an UN-sanitized interpolated filter should FAIL")
    none = 'q.eq("hive_id", hiveId).eq("status", s);'
    if not check_file(none):
        fails.append("a file with only parameterized .eq() should PASS")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_no_interpolated_filter_injection self-test (unsanitized-interp reddens; sanitized + parameterized pass)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
