"""validate_prover_reads_whole_list.py - an instrument that reads what a page says reads every row of its long lists
(SL LB3 follow-on, 2026-10-22).

A long list (utils.js whRenderRows long:true, class wh-rows-cv) lets the browser skip drawing its off-screen rows
(content-visibility:auto). A skipped row has no innerText, and the page's innerText leaves it out entirely: on the live
logbook at 390, document.body.innerText held the words of 2 of Bryan Garcia's 20 entries (tools/lib/long_list_text.mjs
proven both ways: with ALL_ROWS_DRAWN 20 of 20, with PAGE_TEXT 20 of 20). Every prover that read a long-list page's text
with innerText saw a tenth of the list from the day the rule shipped - and a "this must not appear" check passed over
the rest. 91 instruments read innerText on the 15 long-list pages.

STATIC  W1 tools/lib/long_list_text.mjs draws the rows of the class utils.js actually uses: utils.js carries
           `.<class>>*{content-visibility:auto` and the helper's ALL_ROWS_DRAWN forces `.<class>>*{content-visibility:
           visible!important}` for the same class, and PAGE_TEXT reads `.<class> > *`;
        W2 every instrument (a script under tools/ that run_platform_checks.py or another tool names) that opens a
           browser or drives one, reads innerText, and names a long-list page (a served page whose script calls
           whRenderRows with long:true - derived, never listed) does one of:
             - imports ALL_ROWS_DRAWN from ./lib/long_list_text.mjs and installs it on every context it opens - as many
               `addInitScript(ALL_ROWS_DRAWN)` as `newContext(` calls plus `newPage(` calls on a launched browser - or
               draws the rows in place with `evaluate(ALL_ROWS_DRAWN)` (a sweep that times the page first);
             - imports PAGE_TEXT / pageText and reads its text through it (a walk that times the rendering);
             - carries an inline copy marked `long-list-text:` (a walk body cannot import): the drawing copy with the
               helper's exact style and id, or the reading copy over `.<class> > *` with `!r.innerText`.
SELF-TEST (--self-test): each rule broken in a copy, each caught; the clean run is green.

    python tools/validate_prover_reads_whole_list.py [--self-test]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
HELPER = "tools/lib/long_list_text.mjs"
DRAW_CSS = "{content-visibility:visible!important}"
OPENS = re.compile(r"from ['\"]playwright|require\(['\"]playwright|chromium\.launch\(|\.newContext\(|\.newPage\(|addInitScript\(")
LAUNCHED = re.compile(r"([A-Za-z_$][\w$]*)\s*=\s*await\s+(?:chromium|firefox|webkit|pw\.chromium|playwright\.chromium)\.launch\(")


def blank_comments(src: str) -> str:
    """JS comments blanked (a comment naming addInitScript opens no browser); a // inside a URL or string is kept"""
    out = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), src, flags=re.S)
    return re.sub(r"(^|[^:'\"\\])//[^\n]*", lambda m: m.group(1) + " " * (len(m.group(0)) - len(m.group(1))), out)


def bare_innertext(code: str) -> int:
    """innerText reads with no textContent after them in the same || chain: `e.innerText || e.textContent` reads a
    skipped row's words (its innerText is empty), `document.body.innerText` cannot - the body's text is not empty"""
    n = 0
    for m in re.finditer(r"\binnerText\b", code):
        tail = code[m.end():m.end() + 160]
        stop = re.search(r"[;\n]", tail)
        if not re.match(r"\s*\|\|[^;\n]*\btextContent\b", tail[:stop.start() if stop else 160]):
            n += 1
    return n


def long_list_pages(texts: dict[str, str]) -> list[str]:
    return sorted(n for n, s in texts.items() if n.endswith(".html") and re.search(r"long:\s*true", s))


def list_class(utils: str) -> str | None:
    m = re.search(r"'\.([\w-]+)>\*\{content-visibility:auto", utils)
    return m.group(1) if m else None


def check_helper(utils: str, helper: str) -> list[str]:
    cls = list_class(utils)
    if not cls:
        return ["W1 utils.js no longer gives a long list's rows content-visibility:auto - point this gate at the rule"]
    issues = []
    if f".{cls}>*{DRAW_CSS}" not in helper:
        issues.append(f"W1 {HELPER} ALL_ROWS_DRAWN does not force `.{cls}>*{DRAW_CSS}` - the class utils.js skips rows "
                      f"in is .{cls}; a prover installing it would still read a tenth of the list")
    if f"'.{cls} > *'" not in helper or "!r.innerText" not in helper:
        issues.append(f"W1 {HELPER} PAGE_TEXT does not put back the words of the `.{cls} > *` rows that have no innerText")
    return issues


def check_file(name: str, s: str, cls: str) -> str | None:
    """None when the instrument reads every row; else why not."""
    code = blank_comments(s)
    imports = re.search(r"import\s*\{[^}]*\b(ALL_ROWS_DRAWN|PAGE_TEXT|pageText)\b[^}]*\}\s*from\s*['\"]\./lib/long_list_text\.mjs['\"]", code)
    if imports:
        after = code[imports.end():]
        if re.search(r"\b(PAGE_TEXT|pageText)\b", after) or re.search(r"evaluate\(\s*ALL_ROWS_DRAWN\s*\)", after):
            return None
        browsers = set(LAUNCHED.findall(code))
        opened = len(re.findall(r"\.newContext\(", code)) + sum(len(re.findall(r"\b" + re.escape(b) + r"\.newPage\(", code)) for b in browsers)
        installed = len(re.findall(r"addInitScript\(\s*ALL_ROWS_DRAWN\s*\)", code))
        if installed < max(1, opened):
            return f"opens {opened} context(s) and installs ALL_ROWS_DRAWN on {installed}"
        return None
    if "long-list-text:" in s:
        if f".{cls}>*{DRAW_CSS}" in code and "wh-prover-all-rows" in code:
            return None
        if f".{cls} > *" in code and "!r.innerText" in code:
            return None
        return (f"carries a `long-list-text:` copy that neither draws `.{cls}>*` with the helper's style and id nor reads "
                f"`.{cls} > *` rows without innerText")
    return "reads innerText on a long-list page and neither installs ALL_ROWS_DRAWN nor reads through PAGE_TEXT"


def instruments(texts: dict[str, str], registry: str) -> dict[str, str]:
    """name -> source of every script under tools/ that a registered check or another tool names"""
    tools_py = "".join(s for n, s in texts.items() if n.startswith("tools/") and n.endswith(".py"))
    out = {}
    for n, s in texts.items():
        if not n.startswith("tools/") or n.startswith("tools/lib/") or not n.endswith((".mjs", ".js")):
            continue
        base = n.split("/")[-1]
        if base in registry or base in tools_py:
            out[n] = s
    return out


def check(texts: dict[str, str] | None = None) -> tuple[list[str], int]:
    if texts is None:
        texts = {}
        for p in list(ROOT.glob("*.html")) + list(ROOT.glob("tools/*.mjs")) + list(ROOT.glob("tools/*.js")) \
                + list(ROOT.glob("tools/*.py")) + [ROOT / "utils.js", ROOT / HELPER, ROOT / "run_platform_checks.py"]:
            texts[p.relative_to(ROOT).as_posix()] = p.read_text(encoding="utf-8", errors="replace")
    utils, helper, registry = texts["utils.js"], texts.get(HELPER, ""), texts["run_platform_checks.py"]
    issues = check_helper(utils, helper)
    cls = list_class(utils) or "wh-rows-cv"
    pages = long_list_pages(texts)
    if not pages:
        issues.append("W2 no served page draws a long list (whRenderRows long:true) - the scope is empty; point the gate at it")
    seen = 0
    for n, s in sorted(instruments(texts, registry).items()):
        code = blank_comments(s)
        if not bare_innertext(code) or not OPENS.search(code):
            continue
        hit = [p for p in pages if re.search(r"(?<![\w-])" + re.escape(p), s)]
        if not hit:
            continue
        seen += 1
        why = check_file(n, s, cls)
        if why:
            issues.append(f"W2 {n} {why} ({', '.join(x[:-5] for x in hit[:4])}{' ...' if len(hit) > 4 else ''})")
    return issues, seen


def self_test() -> list[str]:
    fails = []
    texts = {}
    for p in list(ROOT.glob("*.html")) + list(ROOT.glob("tools/*.mjs")) + list(ROOT.glob("tools/*.js")) \
            + list(ROOT.glob("tools/*.py")) + [ROOT / "utils.js", ROOT / HELPER, ROOT / "run_platform_checks.py"]:
        texts[p.relative_to(ROOT).as_posix()] = p.read_text(encoding="utf-8", errors="replace")
    clean, seen = check(dict(texts))
    if clean:
        fails.append(f"the clean run is not green: {clean[:3]}")
    if seen < 80:
        fails.append(f"only {seen} instruments in scope - the scope collapsed")

    def mut(name: str, changes: dict[str, str], want: str) -> None:
        t = dict(texts); t.update(changes)
        got, _ = check(t)
        if not any(g.startswith(want) for g in got):
            fails.append(f"mutant '{name}' was not caught (got {got[:2]})")

    sh = texts["tools/prove_shared_handover.mjs"]
    mut("a prover's install removed", {"tools/prove_shared_handover.mjs": re.sub(r"\n[ \t]*await \w+\.addInitScript\(ALL_ROWS_DRAWN\);", "", sh, count=1)}, "W2")
    mut("a prover's import removed", {"tools/prove_shared_handover.mjs": sh.replace("import { ALL_ROWS_DRAWN } from './lib/long_list_text.mjs';", "", 1)}, "W2")
    two = texts["tools/prove_a11y_personas.mjs"]
    mut("one of a prover's contexts left out", {"tools/prove_a11y_personas.mjs": re.sub(r"\n[ \t]*await \w+\.addInitScript\(ALL_ROWS_DRAWN\);", "", two, count=1)}, "W2")
    mut("the helper draws rows as they were", {HELPER: texts[HELPER].replace(DRAW_CSS, "{content-visibility:auto}", 1)}, "W1")
    mut("the helper reads a class utils.js does not use", {HELPER: texts[HELPER].replace("'.wh-rows-cv > *'", "'.wh-rows > *'", 1)}, "W1")
    mut("utils.js renames the long-list class", {"utils.js": texts["utils.js"].replace("'.wh-rows-cv>*{content-visibility:auto", "'.wh-long>*{content-visibility:auto", 1)}, "W1")
    mut("a walk body's inline copy drawing the wrong class", {"tools/lm_walk.body.js": texts["tools/lm_walk.body.js"].replace(".wh-rows-cv>*{content-visibility:visible!important}", ".wh-rows>*{content-visibility:visible!important}", 1)}, "W2")
    mut("the timing walk reading the page's innerText alone", {"tools/lx_walk.body.js": texts["tools/lx_walk.body.js"].replace(".filter((r) => !r.innerText && r.textContent.trim())", ".filter((r) => r.textContent.trim())", 1).replace("long-list-text:", "note:", 1)}, "W2")
    mut("a new registered prover reading the logbook's text", {
        "tools/prove_synthetic_rows.mjs": "import { chromium } from 'playwright';\nconst b = await chromium.launch();\n"
                                          "const ctx = await b.newContext();\nconst p = await ctx.newPage();\nawait p.goto('http://x/logbook.html');\n"
                                          "const t = await p.evaluate(() => document.body.innerText);\n",
        "run_platform_checks.py": texts["run_platform_checks.py"] + "\n# prove_synthetic_rows.mjs\n"}, "W2")
    return fails


def main() -> int:
    if "--self-test" in sys.argv:
        fails = self_test()
        print("SELF-TEST PASS (9 mutants caught; the clean run is green)" if not fails else "SELF-TEST FAIL\n  " + "\n  ".join(fails))
        return 1 if fails else 0
    issues, seen = check()
    print("Prover reads the whole list (SL LB3): an instrument that reads a long-list page's text reads every row")
    for i in issues[:60]:
        print("  [FAIL] " + i)
    print(f"  PASS - {seen} instruments read innerText on a long-list page; each draws every row or reads them back"
          if not issues else f"  FAIL - {len(issues)} problem(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
