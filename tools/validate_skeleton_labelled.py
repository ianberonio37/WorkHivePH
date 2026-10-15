"""validate_skeleton_labelled.py - every list's wait says which list it is (SL F1, 2026-10-16).

The F1 walk held each page's list reads and read the page at 1.5 s. Wherever the shared whListSkeleton / whCardSkeleton
drew the wait, the page showed grey bars and nothing else: no word of what was coming, and an aria-live region with no
text in it, so a screen reader was told nothing either. The helpers now take the list's name and caption the bars
("Loading your logbook entries…"). This gate holds every call to that:

  whListSkeleton(el, rows, '<the list, as it reads in a sentence>')     or  ..., false /* why */)
  whCardSkeleton(el, count, { label: '<the list>' })                   or  { label: false }

`false` is for a caller that already captions its own wait (the hive and logbook boot-wait panels) - say so beside it.
An empty string is not a name. Scans every production .html and .js (utils.js holds the definitions, so it is skipped).

  python tools/validate_skeleton_labelled.py             # exit 1 on any unlabelled call
  python tools/validate_skeleton_labelled.py --self-test # teeth: planted unlabelled calls must fail
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".tmp", ".git", "node_modules", "archive", "_archive", "test-data-seeder", "supabase", "tools", "seeders",
             "playwright-report", "test-results", ".vercel", "dist"}
CALL = re.compile(r"\b(whListSkeleton|whCardSkeleton)\s*\(")
LABEL_STR = re.compile(r"""^\s*(['"`])(?P<v>.*)\1\s*$""", re.S)


def strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", lambda m: " " * len(m.group(0)), src, flags=re.S)
    return re.sub(r"(^|[\s;{}(,])//[^\n]*", lambda m: m.group(1), src, flags=re.M)


def args_of(src: str, start: int):
    """The top-level arguments of the call whose '(' is at src[start-1]."""
    depth, quote, cur, out, i = 0, None, "", [], start
    while i < len(src):
        ch = src[i]
        if quote:
            cur += ch
            if ch == "\\":
                cur += src[i + 1]; i += 2; continue
            if ch == quote:
                quote = None
        elif ch in "'\"`":
            quote = ch; cur += ch
        elif ch in "([{":
            depth += 1; cur += ch
        elif ch in ")]}":
            if depth == 0:
                out.append(cur.strip()); return out
            depth -= 1; cur += ch
        elif ch == "," and depth == 0:
            out.append(cur.strip()); cur = ""
        else:
            cur += ch
        i += 1
    return None


def label_ok(expr: str) -> bool:
    expr = expr.strip()
    if expr == "false":
        return True
    m = LABEL_STR.match(expr)
    return bool(m and m.group("v").strip())


def check_text(src: str, name: str):
    bad = []
    code = strip_comments(src)
    for m in CALL.finditer(code):
        before = code[max(0, m.start() - 9):m.start()]
        if before.rstrip().endswith("function"):
            continue
        fn = m.group(1)
        args = args_of(code, m.end())
        line = code.count("\n", 0, m.start()) + 1
        if args is None:
            bad.append(f"{name}:{line} {fn}: could not read its arguments"); continue
        if fn == "whListSkeleton":
            if len(args) < 3 or not label_ok(args[2]):
                bad.append(f"{name}:{line} whListSkeleton({', '.join(args)}) names no list - pass it as the third argument")
        else:
            opts = args[2] if len(args) >= 3 else ""
            lm = re.search(r"\blabel\s*:\s*(false|'[^']*'|\"[^\"]*\"|`[^`]*`)", opts)
            if not lm or not label_ok(lm.group(1)):
                bad.append(f"{name}:{line} whCardSkeleton({', '.join(args)}) names no list - pass {{ label: '...' }}")
    return bad


def files():
    for p in ROOT.rglob("*"):
        if p.suffix not in (".html", ".js") or not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if any(part in SKIP_DIRS or part.startswith(".") or part.endswith("_bak") for part in rel.parts[:-1]) \
                or p.name in ("utils.js",) or p.name.endswith(".min.js"):
            continue
        yield p, rel.as_posix()


def self_test() -> int:
    cases = [
        ("whListSkeleton(el, 3);", False),
        ("whListSkeleton(el, 3, '');", False),
        ("whListSkeleton(el, 3, 'your parts');", True),
        ("whListSkeleton(el, 3, \"the hive's activity\");", True),
        ("whListSkeleton(el, 3, false /* the panel captions it */);", True),
        ("whCardSkeleton(grid, 8, { variant: 'grid' });", False),
        ("whCardSkeleton(grid, 8);", False),
        ("whCardSkeleton(grid, 8, { variant: 'grid', label: 'the listings' });", True),
        ("// whListSkeleton(el, 3) in a comment is not a call\nfunction whListSkeleton(el, rows, label) {}", True),
        ("if (typeof whListSkeleton === 'function') whListSkeleton(document.getElementById('x'), 4);", False),
    ]
    fails = 0
    for src, want_ok in cases:
        got_ok = not check_text(src, "<case>")
        if got_ok != want_ok:
            fails += 1
            print(f"  SELF-TEST WRONG: {src!r} read {'clean' if got_ok else 'unlabelled'}")
    print(f"self-test: {len(cases) - fails}/{len(cases)} cases read as planted")
    return 1 if fails else 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    bad, calls = [], 0
    for p, rel in files():
        src = p.read_text(encoding="utf-8", errors="replace")
        if "Skeleton(" not in src:
            continue
        calls += len(CALL.findall(strip_comments(src)))
        bad += check_text(src, rel)
    if bad:
        print(f"FAIL skeleton-labelled: {len(bad)} wait state(s) name no list")
        for b in bad:
            print("  ", b)
        return 1
    print(f"PASS skeleton-labelled: every skeleton call names its list ({calls} calls)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
