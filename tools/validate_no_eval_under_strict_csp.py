#!/usr/bin/env python3
r"""no-eval-under-strict-csp — served code must not need what the CSP forbids (2026-09-12).

THE INCIDENT THIS GATE EXISTS FOR. The ffca85f1 release shipped `vercel.json` with
`script-src 'self' 'unsafe-inline' ...` and NO `'unsafe-eval'`. The site is served by VERCEL, so
that CSP went live and BLOCKED eval() on every browser. `browser-floor.js` detected an old engine by
RUNNING `eval('... ?. ?? ...')` and treating any throw as "too old" — so under the CSP it threw on a
current Chrome/Edge/Firefox and painted a full-width red "This browser is too old to run WorkHive /
Masyadong luma ang browser" banner for EVERY visitor. A capability probe cannot require the one thing
the security policy forbids.

`validate_csp_covers_what_ships.py` is the sibling gate — but it (a) reads `_headers`, which Vercel
IGNORES (the site is on Vercel), and (b) checks external subresources + Permissions-Policy, never the
eval FAMILY. This gate closes the eval half against the CSP that is ACTUALLY enforced.

THE CONTRACT. If the effective prod CSP's `script-src` lacks `'unsafe-eval'`, then no JS file LOADED
BY A PAGE (a `<script src>` that is same-origin / relative, not a CDN) may use `eval(...)` or
`new Function(...)` — the two code-from-string sinks whose `identifier(` signature survives comment/
string stripping. (`setTimeout`/`setInterval` with a string arg are the same 'unsafe-eval' class but
are already held at 0 by the canonical contract's "setTimeout(string) eval" dimension.) Each is a
silent, prod-only, every-browser failure.

  * The effective CSP is read from `vercel.json` FIRST (the live header source on Vercel), then
    `_headers` as a fallback — never only the inert file, which is the bug that let this ship.
  * Only page-loaded, same-origin scripts are scanned. A dev-only file that no page includes
    (`survey_ufai_rubric.js`, injected by provers) is not in the critical path and is not flagged.
  * Comments and string literals are stripped before the scan, so `eval(` inside a `//` note or a
    doc-comment (as the FIXED browser-floor.js now carries) is NOT a violation — only a real call is.

Usage:      python tools/validate_no_eval_under_strict_csp.py
Self-test:  python tools/validate_no_eval_under_strict_csp.py --self-test
"""
import glob
import io
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SKIP = re.compile(r"backup|^index-.*-test|\.bak", re.I)

# a <script src="..."> whose src is same-origin (relative or /rooted, NOT http(s):// and NOT //cdn)
PAGE_SCRIPT = re.compile(r"""<script[^>]*\bsrc\s*=\s*["']([^"']+)["']""", re.I)
# The forbidden sinks, matched in COMMENT/STRING-STRIPPED code. Only the two whose signature is
# `identifier(` — they survive comment/string stripping cleanly (the identifier + paren remain).
# `setTimeout`/`setInterval` with a STRING first arg are ALSO 'unsafe-eval'-gated, but detecting the
# string arg needs the quote, which the stripper (correctly) blanks; that class is already covered by
# the canonical contract's "setTimeout(string) eval" dimension (baseline 0), so it is not re-checked here.
SINKS = [
    ("eval", re.compile(r"\beval\s*\(")),
    ("new Function", re.compile(r"\bnew\s+Function\s*\(")),
]


def strip_comments_and_strings(src: str) -> str:
    """Return the code with // + /* */ comments and '..'/".."/`..` string bodies blanked out.

    Blanks (not deletes) so line/column and other tokens are preserved; a real `eval(` in code
    survives, an `eval(` inside a comment or a string literal does not. A small hand tokenizer -
    good enough for detecting a call sink, and it never treats a quote inside a comment (or a // inside
    a string) as opening its own context, which a naive regex sweep gets wrong.
    """
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        two = src[i:i + 2]
        if two == "//":
            j = src.find("\n", i)
            j = n if j == -1 else j
            out.append(" " * (j - i))
            i = j
        elif two == "/*":
            j = src.find("*/", i + 2)
            j = n if j == -1 else j + 2
            out.append(" " * (j - i))
            i = j
        elif c in "'\"`":
            q = c
            out.append(" ")
            i += 1
            while i < n:
                if src[i] == "\\":            # escaped char inside the string
                    out.append("  ")
                    i += 2
                    continue
                if src[i] == q:
                    out.append(" ")
                    i += 1
                    break
                out.append("\n" if src[i] == "\n" else " ")
                i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def parse_script_src(csp_value: str):
    """Return the set of script-src tokens (falling back to default-src), or None if no CSP."""
    if not csp_value:
        return None
    directives = {}
    for part in csp_value.split(";"):
        part = part.strip()
        if part:
            bits = part.split()
            directives[bits[0].lower()] = set(bits[1:])
    return directives.get("script-src", directives.get("default-src")) if directives else None


def effective_script_src():
    """(source_name, script_src_set|None). vercel.json is the live header on Vercel; _headers is inert
    there, so it is only a fallback. Prefer the file the deploy actually serves."""
    vj = ROOT / "vercel.json"
    if vj.exists():
        try:
            data = json.loads(vj.read_text(encoding="utf-8"))
            for block in data.get("headers", []):
                for h in block.get("headers", []):
                    if h.get("key", "").lower() == "content-security-policy":
                        ss = parse_script_src(h.get("value", ""))
                        if ss is not None:
                            return "vercel.json", ss
        except Exception as e:
            print(f"  (warning: could not parse vercel.json CSP: {e})")
    hdr = ROOT / "_headers"
    if hdr.exists():
        m = re.search(r"Content-Security-Policy:\s*([^\n]+)", hdr.read_text(encoding="utf-8", errors="replace"))
        if m:
            ss = parse_script_src(m.group(1))
            if ss is not None:
                return "_headers", ss
    return None, None


def page_loaded_local_scripts():
    """Every same-origin .js a shipped .html includes via <script src>. Returns a set of file names."""
    names = set()
    for html in glob.glob(str(ROOT / "*.html")):
        if SKIP.search(Path(html).name):
            continue
        src = io.open(html, encoding="utf-8", errors="replace").read()
        for m in PAGE_SCRIPT.finditer(src):
            ref = m.group(1).strip()
            if ref.startswith(("http://", "https://", "//")):
                continue                     # a CDN script is governed by its own host grant, not this
            base = ref.split("?", 1)[0].split("#", 1)[0].lstrip("/")
            if base.endswith(".js") and "/" not in base:   # root-level shared/page scripts
                names.add(base)
    return names


def audit(script_src, scripts):
    """script_src: set of tokens or None. scripts: iterable of root-relative .js file names."""
    if script_src is None:
        return None            # no CSP to enforce against
    if "'unsafe-eval'" in script_src or "unsafe-eval" in script_src:
        return []              # eval is permitted; nothing to forbid
    problems = []
    for name in sorted(scripts):
        p = ROOT / name
        if not p.exists():
            continue
        code = strip_comments_and_strings(io.open(p, encoding="utf-8", errors="replace").read())
        for label, rx in SINKS:
            m = rx.search(code)
            if m:
                line = code[:m.start()].count("\n") + 1
                problems.append(f"{name}:{line} uses {label}(), which the prod CSP forbids "
                                f"(script-src has no 'unsafe-eval') - it throws on EVERY browser")
    return problems


def _self_test() -> int:
    strict = {"'self'", "'unsafe-inline'"}
    loose = {"'self'", "'unsafe-eval'"}
    ok = True

    def check(label, code, srcset, expect_problem):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "x.js"
            f.write_text(code, encoding="utf-8")
            # audit() takes file NAMES relative to ROOT; call the stripping+scan directly here
            stripped = strip_comments_and_strings(code)
            hit = any(rx.search(stripped) for _, rx in SINKS)
            if "'unsafe-eval'" in srcset:
                got = False
            else:
                got = hit
            good = (got == expect_problem)
            print(f"    {'ok ' if good else 'BAD'}  {label}")
            return good

    ok &= check("real eval() under strict CSP is flagged", "var x = eval('1+1');", strict, True)
    ok &= check("eval() in a // comment is NOT flagged", "// we removed the eval('?.') canary\nvar y=1;", strict, False)
    ok &= check("eval() in a /* */ comment is NOT flagged", "/* eval('old') was here */\nvar y=1;", strict, False)
    ok &= check("eval() in a string literal is NOT flagged", "var s = \"call eval( here\";", strict, False)
    ok &= check("new Function() under strict CSP is flagged", "var f = new Function('return 1');", strict, True)
    ok &= check("setTimeout(fn) is NOT an eval sink", "setTimeout(function(){doThing();}, 10);", strict, False)
    ok &= check("real eval() WITH unsafe-eval is allowed", "var x = eval('1+1');", loose, False)
    # the real fixed browser-floor.js: eval only in comments -> must pass under strict CSP
    bf = ROOT / "browser-floor.js"
    if bf.exists():
        probs = audit(strict, {"browser-floor.js"})
        bf_ok = (probs == [])
        print(f"    {'ok ' if bf_ok else 'BAD'}  the live fixed browser-floor.js passes (eval only in comments): "
              f"{probs if probs else 'clean'}")
        ok &= bf_ok
    print(f"  self-test: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv[1:]:
        return _self_test()

    source, script_src = effective_script_src()
    if script_src is None:
        print("SKIP no-eval-under-strict-csp - no Content-Security-Policy found in vercel.json or _headers")
        return 0
    scripts = page_loaded_local_scripts()
    problems = audit(script_src, scripts)

    if problems is None:
        print("SKIP no-eval-under-strict-csp - no script-src to enforce")
        return 0
    permits_eval = "'unsafe-eval'" in script_src
    print(f"  effective CSP from {source}: script-src {'PERMITS' if permits_eval else 'FORBIDS'} eval "
          f"| page-loaded local scripts scanned: {len(scripts)}")
    if problems:
        print(f"FAIL no-eval-under-strict-csp - {len(problems)} served script(s) use a code-from-string "
              f"sink the prod CSP blocks:")
        for p in problems[:12]:
            print("    - " + p)
        print("    Either use CSP-safe code (feature detection, a real function, not a string), or - only")
        print("    with a deliberate security decision - add 'unsafe-eval' to script-src. A probe must")
        print("    never require the one capability the policy forbids (the 'browser too old' banner).")
        return 1
    print(f"PASS no-eval-under-strict-csp - the prod CSP forbids eval and no page-loaded script uses it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
