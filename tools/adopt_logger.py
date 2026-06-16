"""
Logger Adoption Transform (Maturity Phase 4 drawdown, 2026-06-16).
===================================================================
Mechanically migrates raw `console.*` calls in edge fns to the structured
`_shared/logger.ts` (`log.info/warn/error`), driving the L G-1 ratchet
(validate_log_surface_discovery.py) down. CONSERVATIVE + type-valid BY
CONSTRUCTION — there is no local deno to type-check, so the transform only
emits forms that cannot fail Supabase's deploy-time check:

  console.LEVEL("msg")              -> log.LEVEL(null, "msg")
  console.LEVEL("msg", arg)         -> log.LEVEL(null, "msg", { detail: arg })
  console.LEVEL("msg", a, b)        -> log.LEVEL(null, "msg", { detail: [a, b] })
  console.LEVEL(`tmpl ${x}`)        -> log.LEVEL(null, `tmpl ${x}`)
  console.LEVEL(nonString, ...)     -> log.LEVEL(null, "LEVEL", { detail: [nonString, ...] })

Safety rails:
  - paren-aware + quote/template/bracket-aware arg splitter (handles String(err))
  - SINGLE-LINE calls only; multi-line console calls are SKIPPED (left as-is, so
    the fn stays counted — honest, not gamed)
  - the first arg is used as `msg` only if it is a string/template literal,
    else msg = the level name and everything goes to detail (always type-valid)
  - import added once, after the first `../_shared/*` import
  - level map: log->info, info->info, warn->warn, error->error

Usage:
  python tools/adopt_logger.py --dry-run     # report, change nothing
  python tools/adopt_logger.py --apply       # write the safe transforms
  python tools/adopt_logger.py --apply --fn benchmark-compute   # one fn
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FN_DIR = ROOT / "supabase" / "functions"
LOGGER_IMPORT = 'import { log } from "../_shared/logger.ts";'
LEVEL_MAP = {"log": "info", "info": "info", "warn": "warn", "error": "error"}
CONSOLE_RE = re.compile(r"console\.(log|error|warn|info)\s*\(")
SHARED_IMPORT_RE = re.compile(r'^import .*?from\s+"\.\./_shared/[^"]+";\s*$', re.M)


def split_top_level(s: str) -> list[str]:
    """Split on top-level commas, respecting (), [], {}, '', "", ``."""
    args, depth, i, start = [], 0, 0, 0
    quote = None
    while i < len(s):
        c = s[i]
        if quote:
            if c == "\\":
                i += 2; continue
            if c == quote:
                quote = None
        elif c in "\"'`":
            quote = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "," and depth == 0:
            args.append(s[start:i].strip()); start = i + 1
        i += 1
    last = s[start:].strip()
    if last:
        args.append(last)
    return args


def match_paren(text: str, open_idx: int) -> int:
    """Given index of '(', return index of matching ')' (quote-aware), or -1."""
    depth, i, quote = 0, open_idx, None
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\":
                i += 2; continue
            if c == quote:
                quote = None
        elif c in "\"'`":
            quote = c
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def is_string_literal(arg: str) -> bool:
    return len(arg) >= 2 and arg[0] in "\"'`" and arg[-1] == arg[0]


def transform(text: str) -> tuple[str, int, int]:
    """Return (new_text, n_transformed, n_skipped)."""
    out = []
    i = 0
    n_ok = n_skip = 0
    for m in CONSOLE_RE.finditer(text):
        pass  # we iterate manually below for nested correctness
    # manual scan
    result = text
    idx = 0
    pieces = []
    while True:
        m = CONSOLE_RE.search(result, idx)
        if not m:
            pieces.append(result[idx:]); break
        open_idx = m.end() - 1
        close_idx = match_paren(result, open_idx)
        level = m.group(1)
        if close_idx == -1 or "\n" in result[open_idx:close_idx]:
            # multi-line or unbalanced — SKIP (leave as-is)
            pieces.append(result[idx:m.end()]); idx = m.end(); n_skip += 1
            continue
        inner = result[open_idx + 1:close_idx]
        args = split_top_level(inner)
        lvl = LEVEL_MAP[level]
        if args and is_string_literal(args[0]):
            msg = args[0]; rest = args[1:]
        else:
            msg = f'"{lvl}"'; rest = args
        if not rest:
            repl = f"log.{lvl}(null, {msg})"
        elif len(rest) == 1:
            repl = f"log.{lvl}(null, {msg}, {{ detail: {rest[0]} }})"
        else:
            repl = f"log.{lvl}(null, {msg}, {{ detail: [{', '.join(rest)}] }})"
        pieces.append(result[idx:m.start()]); pieces.append(repl)
        idx = close_idx + 1; n_ok += 1
    new_text = "".join(pieces)

    # add the import once, if we transformed anything and it's not present
    if n_ok and LOGGER_IMPORT not in new_text:
        im = SHARED_IMPORT_RE.search(new_text)
        if im:
            new_text = new_text[:im.end()] + "\n" + LOGGER_IMPORT + new_text[im.end():]
        else:
            n_ok = 0; new_text = text  # no safe import anchor — bail this fn
    return new_text, n_ok, n_skip


def depth_sig(text: str) -> tuple[int, int, int]:
    """Net (paren, bracket, brace) depth, quote-aware. The ABSOLUTE value may be
    nonzero for a valid TS file (this scanner doesn't model // /* */ comments or
    regex literals), but a balance-PRESERVING edit leaves the signature unchanged.
    So we compare new-vs-old signatures rather than trusting an absolute zero."""
    depth = {"(": 0, "[": 0, "{": 0}
    pairs = {")": "(", "]": "[", "}": "{"}
    quote = None; i = 0
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\": i += 2; continue
            if c == quote: quote = None
        elif c in "\"'`":
            quote = c
        elif c in "([{":
            depth[c] += 1
        elif c in ")]}":
            depth[pairs[c]] -= 1
        i += 1
    return (depth["("], depth["["], depth["{"])


def main() -> int:
    apply = "--apply" in sys.argv
    only = None
    if "--fn" in sys.argv:
        only = sys.argv[sys.argv.index("--fn") + 1]

    targets = []
    for d in sorted(FN_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        if only and d.name != only:
            continue
        idx = d / "index.ts"
        if not idx.exists():
            continue
        t = idx.read_text(encoding="utf-8", errors="replace")
        if "console." in t and "_shared/logger.ts" not in t:
            targets.append((d.name, idx, t))

    total_ok = total_skip = changed = 0
    for name, idx, t in targets:
        new_t, n_ok, n_skip = transform(t)
        total_ok += n_ok; total_skip += n_skip
        if n_ok == 0:
            continue
        if depth_sig(new_t) != depth_sig(t):
            print(f"  [SKIP-DELTA] {name} — transform changed the delimiter signature; left untouched")
            continue
        changed += 1
        print(f"  {name}: {n_ok} migrated" + (f", {n_skip} skipped (multi-line)" if n_skip else ""))
        if apply:
            idx.write_text(new_t, encoding="utf-8")

    print(f"\n{'APPLIED' if apply else 'DRY-RUN'}: {changed} fn(s) changed, {total_ok} console.* migrated, {total_skip} skipped (multi-line/unsafe).")
    if not apply:
        print("  Re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
