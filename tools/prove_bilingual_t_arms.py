"""bilingual-t-arms — a forward-only ratchet on `_t(en, fil)` calls whose two arms are IDENTICAL.

WHY THIS GATE EXISTS (2026-09-15, found by Impeccable's critique lens on alert-hub.html, Assessment A).
`window._t(en, fil)` returns the Filipino arm under FIL and falls back to the English one when the Filipino
arm is empty - which is the right fallback, and is exactly what makes this defect invisible:

    _t(`Risk score 78%, pm overdue, time to mtbf`, `Risk score 78%, pm overdue, time to mtbf`)

is wrapped, passes every "is this string translated?" check a reviewer or a grep can run, renders English to
a Filipino reader forever, and no test on the platform could see it. I wrote that exact line myself during
the copy lens two hours before the critique found it, so the class is not hypothetical and not rare.

NOT EVERY IDENTICAL PAIR IS A BUG. Some strings are genuinely the same word in both languages - a product
name ("WorkHive Analytics AI"), a loan term the plant floor actually says ("Automation job", "AMC"), a unit.
So this is a RATCHET, not a ban: today's measured count per file is the floor, and any NEW identical-arm call
fails the gate. Lowering the floor is a deliberate `--rebase` with a reason, exactly like the design detector
ratchet next to it.

    python tools/prove_bilingual_t_arms.py --check          # gate (forward-only)
    python tools/prove_bilingual_t_arms.py --list           # every identical-arm call, with file:line
    python tools/prove_bilingual_t_arms.py --rebase --reason "..."
    python tools/prove_bilingual_t_arms.py --self-test      # proves the gate bites
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "bilingual_t_arms_baseline.json"

# _t('a', 'b') / _t("a", "b") / _t(`a`, `b`) - two string-literal arms, any quote style, possibly multiline.
# A call whose arms are expressions (a variable, a ternary) is out of scope: it cannot be judged statically.
CALL = re.compile(
    r"_t\(\s*(?P<q1>['\"`])(?P<a>(?:\\.|(?!(?P=q1)).)*)(?P=q1)\s*,\s*(?P<q2>['\"`])(?P<b>(?:\\.|(?!(?P=q2)).)*)(?P=q2)\s*\)",
    re.S,
)
SKIP_PREFIXES = (".tmp/", "node_modules/", "tests/", "_fixtures/")
SKIP_PARTS = ("/vendor/", "/dist/")


def _mask_comments(txt: str) -> str:
    """Blank out // and /* */ comments, leaving offsets and line numbers intact.

    ★A GATE THAT READS ITS OWN DESCRIPTION AS A DEFECT PUNISHES DOCUMENTATION (2026-09-17, W46024).
    This scanner read raw text, so the moment a sw.js CACHE_NAME note EXPLAINED a `_t('NORMAL',
    'NORMAL')` it had just fixed, the gate failed on the sentence describing the repair. The same
    hole in tools/check_inline_scripts.js the same day made a `<script>` token inside an HTML comment
    open a script block. A comment is not code, in either direction: a commented-out `_t` with two
    identical arms is not shipping, and prose quoting one is not a call.

    String state is tracked so that a `//` inside "https://..." or a `/*` inside a regex-ish literal
    does not start a comment. Template literals are treated as strings; a ${} expression inside one
    cannot contain a comment worth finding here.
    """
    out = list(txt)
    i, n = 0, len(txt)
    quote = None
    while i < n:
        c = txt[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in "'\"`":
            quote = c
            i += 1
            continue
        if c == "/" and i + 1 < n and txt[i + 1] == "/":
            while i < n and txt[i] != "\n":
                out[i] = " "
                i += 1
            continue
        if c == "/" and i + 1 < n and txt[i + 1] == "*":
            while i < n and not (txt[i] == "*" and i + 1 < n and txt[i + 1] == "/"):
                if txt[i] != "\n":
                    out[i] = " "
                i += 1
            for _ in range(2):
                if i < n:
                    out[i] = " "
                    i += 1
            continue
        i += 1
    return "".join(out)


def _tracked_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "*.html", "*.js"], cwd=ROOT,
                         capture_output=True, text=True, check=False).stdout.split()
    files = []
    for rel in out:
        if rel.startswith(SKIP_PREFIXES) or any(p in "/" + rel for p in SKIP_PARTS):
            continue
        p = ROOT / rel
        if p.is_file():
            files.append(p)
    return files


def scan() -> dict[str, list[tuple[int, str]]]:
    """{relative path: [(line, the identical string), ...]} for every _t call whose arms match byte for byte."""
    found: dict[str, list[tuple[int, str]]] = {}
    for p in _tracked_files():
        try:
            txt = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = p.relative_to(ROOT).as_posix()
        for m in CALL.finditer(_mask_comments(txt)):
            a, b = m.group("a"), m.group("b")
            if a == b and a.strip():
                found.setdefault(rel, []).append((txt[:m.start()].count("\n") + 1, a[:90]))
    return found


def _counts(found: dict[str, list[tuple[int, str]]]) -> dict[str, int]:
    return {f: len(v) for f, v in sorted(found.items())}


def _load_baseline() -> dict:
    if not BASELINE.exists():
        return {}
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def _write_baseline(counts: dict[str, int], reason: str) -> None:
    BASELINE.write_text(json.dumps({
        "_doc": ("Forward-only floor for `_t(en, fil)` calls whose two arms are identical - a translation that "
                 "can never happen. A NEW one fails the gate `bilingual-t-arms`; the floor only ever drops. "
                 "Some entries are legitimate (a product name, a loan word the plant floor says in English)."),
        "reason": reason,
        "total": sum(counts.values()),
        "by_file": counts,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--rebase", action="store_true")
    ap.add_argument("--reason", default="")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        # the gate must bite on a NEW identical-arm call and stay quiet on a real translation
        probe = ROOT / "_bilingual_t_arms_selftest.js"
        try:
            base = _load_baseline().get("by_file", {})
            probe.write_text("var x = _t('Save changes', 'Save changes');\n"
                             "var y = _t('Save changes', 'I-save ang mga pagbabago');\n", encoding="utf-8")
            subprocess.run(["git", "add", "-N", probe.name], cwd=ROOT, capture_output=True, check=False)
            found = scan()
            rel = probe.name
            got = len(found.get(rel, []))
            ok_bites = got == 1
            rose = {f: n for f, n in _counts(found).items() if n > base.get(f, 0)}
            ok_fails = rel in rose
            print(f"self-test: the probe's identical arm is seen ({got} == 1): {ok_bites}")
            print(f"self-test: it reads as a RISE against the baseline: {ok_fails}")
            print(f"self-test: its real translation is NOT flagged: {got == 1}")
            return 0 if (ok_bites and ok_fails) else 1
        finally:
            subprocess.run(["git", "rm", "--cached", "-q", probe.name], cwd=ROOT, capture_output=True, check=False)
            probe.unlink(missing_ok=True)

    found = scan()
    counts = _counts(found)
    total = sum(counts.values())

    if a.list:
        for f, rows in sorted(found.items()):
            for line, text in rows:
                print(f"{f}:{line}  {text}")
        print(f"\n{total} identical-arm _t call(s) across {len(counts)} file(s)")
        return 0

    if a.rebase:
        if not a.reason:
            print("REFUSED: --rebase needs --reason (the floor is a claim about the platform)")
            return 2
        old = _load_baseline().get("total", 0)
        _write_baseline(counts, a.reason)
        print(f"rebased: {old} -> {total} identical-arm _t call(s)")
        return 0

    base = _load_baseline()
    if not base:
        _write_baseline(counts, "first run - today's measured floor")
        print(f"bilingual-t-arms: baseline written, {total} identical-arm _t call(s) across {len(counts)} file(s)")
        return 0

    by_file = base.get("by_file", {})
    rose = {f: (n, by_file.get(f, 0)) for f, n in counts.items() if n > by_file.get(f, 0)}
    if rose:
        print("FAIL bilingual-t-arms: a _t() call whose two arms are IDENTICAL cannot ever translate.")
        for f, (now, was) in sorted(rose.items()):
            print(f"  {f}: {was} -> {now}")
            for line, text in found.get(f, []):
                print(f"      {f}:{line}  {text}")
        print("  Write the Filipino arm, or --rebase with a reason if the term is genuinely identical.")
        return 1

    fell = sum(max(0, by_file.get(f, 0) - counts.get(f, 0)) for f in by_file)
    msg = f"PASS bilingual-t-arms: {total} identical-arm _t call(s), none rose against the floor of {base.get('total', 0)}"
    print(msg + (f" ({fell} fell - run --rebase to lower the floor)" if fell else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
