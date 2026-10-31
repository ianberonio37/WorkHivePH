"""validate_const_not_reassigned.py - a name destructured with `const` from an awaited read is never assigned again.

Found 2026-10-30 walking Wave HS (the hive at thirty) on project-manager.html: loadLinkOptions read
`const { data, error } = await fn();` and, when a list ran one past its cap, did `data = data.slice(0, cap)`. That is a
TypeError ("Assignment to constant variable") - but only at RUNTIME and only once a hive holds more than 50 logbook
entries or PM completions, so `node --check`, every small demo hive and every gate passed while a thirty-member hive
could link no logbook entry or PM to a project. The shape is mechanical, so it is checked mechanically: for every
`const { a, b: c } = await ...` in a shipped page or script, no name it binds is assigned again before the enclosing
function ends (within 60 lines - the reads this pattern guards are short).

    python tools/validate_const_not_reassigned.py            the shipped pages and scripts
    python tools/validate_const_not_reassigned.py --self-test   a planted reassignment must be found, a correct one not
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DECL = re.compile(r"\bconst\s*\{([^}]*)\}\s*=\s*await\b")
FUNC = re.compile(r"^\s*(async\s+)?function\b")
WINDOW = 60

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def scan(text: str) -> list[tuple[int, int, str, str]]:
    lines = text.split("\n")
    out = []
    for i, ln in enumerate(lines):
        m = DECL.search(ln)
        if not m:
            continue
        names = [n.split(":")[-1].split("=")[0].strip() for n in m.group(1).split(",")]
        names = [n for n in names if re.fullmatch(r"[A-Za-z_$][\w$]*", n)]
        for j in range(i + 1, min(i + WINDOW, len(lines))):
            if FUNC.search(lines[j]):
                break
            for n in names:
                if (re.search(r"(^|[^.\w$])" + re.escape(n) + r"\s*=(?!=)", lines[j])
                        and not re.search(r"\b(const|let|var)\s+" + re.escape(n) + r"\b", lines[j])):
                    out.append((i + 1, j + 1, n, lines[j].strip()[:100]))
    return out


def shipped() -> list[Path]:
    return sorted(p for p in list(ROOT.glob("*.html")) + list(ROOT.glob("*.js")) if p.is_file())


def self_test() -> int:
    bad = ("async function f() {\n  const { data, error } = await fn();\n  if (error) return;\n"
           "  if (more) data = data.slice(0, 50);\n}\n")
    good = ("async function f() {\n  let { data, error } = await fn();\n  if (more) data = data.slice(0, 50);\n"
            "  const { data: rows } = await g();\n  if (rows === null) return;\n}\n")
    fails = []
    if not scan(bad):
        fails.append("the planted const reassignment was not found")
    if scan(good):
        fails.append("a `let` destructure or an `===` comparison was flagged: " + str(scan(good)))
    print("FAIL const-not-reassigned self-test - " + "; ".join(fails) if fails
          else "PASS const-not-reassigned self-test: a planted reassignment is found, a let / === is not")
    return 1 if fails else 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    hits = []
    for p in shipped():
        for decl, at, name, line in scan(p.read_text(encoding="utf-8", errors="replace")):
            hits.append(f"{p.name}:{at} reassigns `{name}` destructured with const at line {decl}: {line}")
    for h in hits:
        print("  x " + h)
    print(f"{'FAIL' if hits else 'PASS'} const-not-reassigned: {len(shipped())} pages and scripts, "
          f"{len(hits)} const destructure(s) assigned again")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
