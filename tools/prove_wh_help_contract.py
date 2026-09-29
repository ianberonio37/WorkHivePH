"""prove_wh_help_contract.py — the inline-help disclosure ships in THREE copies; assert they agree.

`.wh-help` is declared three times in this repo, on purpose:

  1. `components.css`      — the app pages that load it
  2. `wh-help.css`         — the pages that do NOT load components.css (project-report, and two more)
  3. `utils.js` (injected) — the runtime fallback, injected when neither stylesheet is present

Both CSS copies carry comments saying the three MUST move together, because a second, DIFFERENT
rule arriving after first paint is a layout shift. Those comments were written by people who then
edited two of the three files. On 2026-09-17 a design-lens craft walk of project-report.html found
`wh-help.css` behind on FOUR values at once — margin 14px vs 16px, padding 10px 14px vs 12px 16px,
summary 0.74rem vs 0.75rem, and `> p` margin 0.2rem (3.2px) vs 4px — every one of them fixed in the
other two copies weeks earlier, each under a comment asking the next editor to remember.

A step that depends on remembering does not happen. This gate does the remembering.

It compares the properties that actually move (spacing, size, radius) rather than whole strings, so
formatting differences between a `.css` file and a JS string literal do not trip it.

RUN:  python tools/prove_wh_help_contract.py --check
      python tools/prove_wh_help_contract.py --self-test
"""
import argparse
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# The properties whose drift is visible to a person. Colour/background are excluded deliberately:
# components.css uses var(--wh-radius, 12px) where the others hard-code 12px, and the point of this
# gate is geometry that shifts layout, not token spelling.
WATCHED = ("margin", "padding", "font-size", "border-radius")

RULES = ("wh-help", "wh-help > p", "wh-help > summary")


def _norm(v: str) -> str:
    """'0 0 16px' and '0  0  16px' are the same rule; 'var(--wh-radius, 12px)' resolves to its fallback."""
    v = v.strip().lower()
    m = re.match(r"var\(--[a-z0-9-]+,\s*([^)]+)\)$", v)
    if m:
        v = m.group(1).strip()
    return re.sub(r"\s+", " ", v)


def _body(text: str, selector: str) -> str | None:
    """The declaration block for a selector, in a .css file or inside a JS string literal."""
    sel = re.escape(selector).replace(r"\ >\ ", r"\s*>\s*")
    m = re.search(r"(?:^|[,}\n'\"])\s*\." + sel + r"\s*\{([^}]*)\}", text, re.M)
    return m.group(1) if m else None


def _props(body: str) -> dict:
    out = {}
    for prop, val in re.findall(r"([a-z-]+)\s*:\s*([^;]+)", body):
        if prop in WATCHED:
            out[prop] = _norm(val)
    return out


def read_copies() -> dict:
    return {
        "components.css": io.open(ROOT / "components.css", encoding="utf-8").read(),
        "wh-help.css": io.open(ROOT / "wh-help.css", encoding="utf-8").read(),
        "utils.js": io.open(ROOT / "utils.js", encoding="utf-8").read(),
    }


def compare(sources: dict) -> list:
    problems = []
    for rule in RULES:
        seen = {}
        for name, text in sources.items():
            body = _body(text, rule)
            if body is None:
                problems.append(f"{name} declares no `.{rule}` at all — the contract needs all three copies")
                continue
            seen[name] = _props(body)
        if len(seen) < 2:
            continue
        for prop in sorted({p for v in seen.values() for p in v}):
            vals = {name: v.get(prop) for name, v in seen.items()}
            distinct = {v for v in vals.values() if v is not None}
            if len(distinct) > 1:
                shown = ", ".join(f"{n}={v!r}" for n, v in sorted(vals.items()))
                problems.append(f".{rule} {{ {prop} }} DIFFERS across the copies: {shown}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        good = read_copies()
        if compare(good):
            print("SELF-TEST FAIL: the live files already disagree, so a passing case cannot be shown")
            return 2
        broken = dict(good)
        broken["wh-help.css"] = good["wh-help.css"].replace("margin: 0 0 16px", "margin: 0 0 14px", 1)
        found = compare(broken)
        if not any("margin" in p for p in found):
            print("SELF-TEST FAIL: a planted 14px/16px margin drift was NOT detected")
            return 2
        print("PASS self-test: the live copies agree, and a planted margin drift is caught —")
        print(f"   {found[0]}")
        return 0

    problems = compare(read_copies())
    if problems:
        print("FAIL wh-help-contract: the inline-help disclosure ships in three copies and they have drifted.")
        print("   Both CSS files carry comments saying they must move together — a second, DIFFERENT rule")
        print("   arriving after first paint is a layout shift. Edit ALL THREE:")
        for p in problems:
            print(f"   - {p}")
        return 1
    print(f"PASS wh-help-contract: all three copies of .wh-help agree on {', '.join(WATCHED)} "
          f"across {len(RULES)} rules (components.css, wh-help.css, the utils.js fallback).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
