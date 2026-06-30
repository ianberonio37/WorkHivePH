#!/usr/bin/env python3
"""validate_edge_symbol_imports.py — G0 gate: every USED _shared symbol is imported.

THE GAP THIS CLOSES (found 2026-06-19, Arc E live-invoke):
  project-progress/index.ts called resolveIdentity()/resolveTenancy() but never
  imported them -> ReferenceError at runtime -> the fn 500'd on EVERY call.
  validate_edge_import_exports.py checks imports RESOLVE to real exports; it does
  NOT check that a USED _shared symbol is imported. A live invoke caught it; no
  static gate did. This gate locks the class.

RULE: for each edge fn, any distinctive _shared exported symbol that is CALLED
  (`symbol(`) must be EITHER imported (multi-line aware) OR defined locally
  (a fn may keep its own copy, e.g. checkAIRateLimit). Otherwise = FAIL.

USAGE: python tools/validate_edge_symbol_imports.py   (baseline 0 violations)
"""
from __future__ import annotations
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FUNCS = ROOT / "supabase" / "functions"
SHARED = FUNCS / "_shared"
# Common short words that are also _shared exports → skip (too ambiguous to gate safely).
SKIP = {"ok", "fail", "json", "err", "log", "warn"}


def shared_exports() -> set[str]:
    names: set[str] = set()
    for p in SHARED.glob("*.ts"):
        src = p.read_text(encoding="utf-8", errors="replace")
        names |= set(re.findall(r"export\s+(?:async\s+)?function\s+([A-Za-z_]\w+)", src))
        names |= set(re.findall(r"export\s+(?:const|let)\s+([A-Za-z_]\w+)", src))
        for blk in re.findall(r"export\s*\{([^}]*)\}", src):
            names |= {n.strip().split(" as ")[-1].strip() for n in blk.split(",") if n.strip()}
    return {n for n in names if n and n not in SKIP and len(n) > 3}


def strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    return re.sub(r"//.*", "", src)


def imported_names(code: str) -> set[str]:
    """Parse from COMMENT-STRIPPED code (an inline // comment with a comma would
    otherwise corrupt the name split). Handles static + dynamic destructured imports."""
    names: set[str] = set()
    # static, multi-line aware: import { a, b,\n c } from '...'
    for blk in re.findall(r"import\s*\{([^}]*)\}\s*from", code, flags=re.DOTALL):
        names |= {n.strip().split(" as ")[-1].strip() for n in blk.split(",") if n.strip()}
    # dynamic destructured: const { a, b } = await import('...')
    for blk in re.findall(r"(?:const|let|var)\s*\{([^}]*)\}\s*=\s*await\s+import", code, flags=re.DOTALL):
        names |= {n.strip().split(":")[0].strip() for n in blk.split(",") if n.strip()}
    names |= set(re.findall(r"import\s+(\w+)\s+from", code))           # default import
    names |= set(re.findall(r"import\s+\*\s+as\s+(\w+)", code))        # namespace import
    return names


def local_defs(src: str) -> set[str]:
    names = set(re.findall(r"(?:async\s+)?function\s+([A-Za-z_]\w+)", src))
    names |= set(re.findall(r"(?:const|let|var)\s+([A-Za-z_]\w+)\s*=", src))
    return names


def main() -> int:
    exports = shared_exports()
    violations = []
    for d in sorted(FUNCS.glob("*/index.ts")):
        fn = d.parent.name
        if fn == "_shared":
            continue
        src = d.read_text(encoding="utf-8", errors="replace")
        code = strip_comments(src)
        imp = imported_names(code)           # parse from comment-stripped code
        loc = local_defs(code)
        called = set(re.findall(r"[^A-Za-z0-9_.]([A-Za-z_]\w+)\s*\(", code))
        for sym in sorted(exports & called):
            if sym not in imp and sym not in loc and ("namespace" not in imp):
                violations.append((fn, sym))

    print("=" * 64)
    print("  validate_edge_symbol_imports — used _shared symbol must be imported")
    print("=" * 64)
    print(f"  distinctive _shared exports tracked: {len(exports)}")
    if violations:
        for fn, sym in violations:
            print(f"  X  {fn}: calls {sym}() but neither imports nor defines it")
        print(f"\n  FAIL: {len(violations)} use-without-import (baseline 0)")
        return 1
    print(f"  OK  no use-without-import across {len(list(FUNCS.glob('*/index.ts')))} edge fns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
