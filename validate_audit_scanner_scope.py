"""
Audit Scanner Scope Validator (L0 meta-validator).
==================================================
Codifies the rule from memory `feedback_audit_scanner_scope.md`:

  Every static auditor (`tools/audit_*.py`, `tools/mine_*.py`) that scans
  the codebase for column / capture / read consumers MUST cover:

    1. supabase/functions/_shared/**/*.ts
    2. Subdirectory HTML (one level deep beyond ROOT)
    3. Intra-migration view consumers (own-migration matches >= 2)

  Caught 12 false-positive phantom columns 2026-05-20 because three sister
  auditors all had the same scope gap.

This validator scans every `tools/audit_*.py` and `tools/mine_*.py` and
flags any file that:

  - Scans `functions/*` for `.ts` (edge fns) but never touches
    `_shared` or `functions/_shared`.
  - Globs `*.html` at project root but never recurses into subdirectories
    (no `rglob` / `iterdir` over subdirectories beyond `tools|tests|...`).

Detection is heuristic — false positives can be muted with a one-line
opt-out comment on the file's first 30 lines:

  # audit-scope-allow: this script does not scan code for consumers

Exit code:
  0 if every scanner covers both scopes (or has the opt-out comment)
  1 otherwise
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path


if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent

OPT_OUT_RE  = re.compile(r"audit-scope-allow", re.IGNORECASE)

# Signals that a script scans edge functions for .ts files.
EDGE_SCAN_RE = re.compile(
    r'functions["\']\s*\)\s*\.glob\(\s*["\']\*'        # ("functions").glob("*")
    r'|functions.*\.ts\b'                              # functions ... .ts
    r'|functions["\']\s*\)\s*/\s*fn_dir'               # supabase / "functions" / fn_dir
    r'|fn_dir\s*/\s*["\']index\.ts'                    # fn_dir / "index.ts"
)
SHARED_SCAN_RE = re.compile(r"_shared", re.IGNORECASE)

# Signals that a script globs root HTML.
HTML_GLOB_RE   = re.compile(r'ROOT\.glob\(\s*["\']\*\.html["\']\)|ROOT\.glob\(\s*HTML_GLOB\s*\)')
SUBDIR_SCAN_RE = re.compile(r"subdir\.rglob\(\s*['\"]\*\.html|ROOT\.rglob\(\s*['\"]\*\.html|for\s+subdir\s+in")


# Sentinel binding: name the L2 test `test('audit_scanner_scope: ...')` for coverage credit.
CHECK_NAMES = ["audit_scanner_scope"]


def main() -> int:
    targets: list[Path] = []
    for p in sorted((ROOT / "tools").glob("audit_*.py")):
        targets.append(p)
    for p in sorted((ROOT / "tools").glob("mine_*.py")):
        targets.append(p)

    if not targets:
        print("FAIL: no audit/miner scripts found under tools/")
        return 2

    issues: list[tuple[str, str]] = []
    pass_count = 0
    skipped: list[str] = []

    for p in targets:
        text = p.read_text(encoding="utf-8", errors="replace")
        header = "\n".join(text.splitlines()[:40])

        if OPT_OUT_RE.search(header):
            skipped.append(p.name)
            continue

        scans_edge_fns = bool(EDGE_SCAN_RE.search(text))
        scans_root_html = bool(HTML_GLOB_RE.search(text))

        # If the script does neither, the scope-gap rule doesn't apply.
        if not scans_edge_fns and not scans_root_html:
            skipped.append(p.name)
            continue

        file_issues: list[str] = []
        if scans_edge_fns and not SHARED_SCAN_RE.search(text):
            file_issues.append("scans functions/*.ts but never references _shared")
        if scans_root_html and not SUBDIR_SCAN_RE.search(text):
            file_issues.append("globs root *.html but no subdirectory rglob")

        if file_issues:
            for msg in file_issues:
                issues.append((p.name, msg))
        else:
            pass_count += 1

    print()
    print("Audit Scanner Scope Validator")
    print("=" * 56)
    print(f"  Scripts inspected:   {len(targets)}")
    print(f"  Pass (full scope):   {pass_count}")
    print(f"  Skipped (no scan):   {len(skipped)}")
    print(f"  Issues:              {len(issues)}")

    if issues:
        print()
        print("FAILURES")
        print("-" * 56)
        for fname, msg in issues:
            print(f"  FAIL  {fname}")
            print(f"        {msg}")
        print()
        print("Fix: extend the consumer-scan loop. Reference impl is")
        print("`_gather_blobs()` in tools/audit_phantom_columns.py.")
        print("If the rule doesn't apply, add a top-of-file comment:")
        print("  # audit-scope-allow: <reason>")
        return 1

    print()
    print("OK — every consumer-scanning auditor covers _shared + subdir HTML.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
