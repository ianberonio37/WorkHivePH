#!/usr/bin/env python3
"""
validate_no_control_bytes - no CODE file may carry a byte an escape sequence mangles into (2026-09-05, register row 51).

Two word boundaries (backslash-b) in utils.js transport-settle regexes were written through a heredoc and landed as
U+0008, so the regexes could never match and the settle was a no-op on every page while four rewrites chased timing
and visibility. The same byte sat in the rubric survey nav-tile test, in a gate exclusion regex and in the checks
runner. A control byte is invisible in a terminal and in a diff; this gate makes it visible.

Targets ONLY the bytes an escape mangles into: backslash-b -> U+0008, backslash-a -> U+0007, backslash-v -> U+000B,
backslash-0 -> U+0000. ANSI ESC (reporters), the unit separator (a deliberate delimiter in two boards) and vendored
minified code are legitimate program bytes and are not flagged; generated .md/.json reports are out of scope.

  python tools/validate_no_control_bytes.py
"""
from __future__ import annotations
import os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# .ts joins the roster: 103 edge functions were unscanned, and one of them carried two literal NUL
# bytes as a composite-key delimiter - deliberate, but enough to make grep call the file binary and
# one re-encode away from silently vanishing. The class this gate exists for can hide in a DEPLOYED
# function as easily as in a page.
EXT = ('.js', '.mjs', '.py', '.html', '.sql', '.css', '.ts', '.cjs')
MANGLED = {chr(8), chr(7), chr(11), chr(0)}


def files() -> list[str]:
    r = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return [f for f in r.stdout.splitlines() if f.endswith(EXT) and 'node_modules' not in f and not f.startswith('tools/vendor/') and os.path.isfile(os.path.join(ROOT, f))]


def main() -> int:
    bad, scanned = [], 0
    for f in files():
        try:
            s = open(os.path.join(ROOT, f), encoding='utf-8', errors='strict').read()
        except Exception:
            continue
        scanned += 1
        for i, ch in enumerate(s):
            if ch in MANGLED:
                bad.append(f"{f}:{s[:i].count(chr(10)) + 1} U+{ord(ch):04X}")
                if len(bad) > 40:
                    break
    if bad:
        print("FAIL no-control-bytes - bytes an escape mangles into (written through a heredoc), invisible in a diff:")
        for b in bad[:40]:
            print("  " + b)
        return 1
    print(f"PASS no-control-bytes - {scanned} code files carry no mangled-escape byte (U+0008/0007/000B/0000)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
