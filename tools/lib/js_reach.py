"""js_reach.py - read a served page's own JavaScript the way the browser runs it, for the SL RL gates (2026-10-22).

The three Rate Limiting gates (tools/validate_one_person_cannot_flood.py RL3, validate_limit_says_when.py RL2,
validate_ai_spend_in_budget.py RL1) ask the same first question of a handler: what does it reach? This is that reader,
once. It is the reader tools/validate_refresh_stands_down_hidden.py (SL LB4) uses - a brace matcher and a call walk -
with the two things it could not do, both found while surveying RL3:

  * a regex literal is skipped as one token. A quote or a brace inside one (`/[&<>"']/g`) opened a "string" that ran
    on past the function's end, so utils.js escHtml's body ran into the i18n loader below it and a search box that
    escaped its text "reached the network" (marketplace's listing-quality widget, voice-journal's history filter).
  * a listener a handler BINDS is not something the handler RUNS. voice-journal's history render wires each row's
    Speak-again button to the text-to-speech fetch; typing in its search box re-renders the rows, it sends nothing.

Only inline classic scripts are read on an HTML page (a <script src> is its own served file); everything else in the
file is blanked with its line breaks kept, so a line number here is the file's line number.
"""
from __future__ import annotations

import functools
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# a call that leaves the browser: a database read or write, a function call, storage, a fetch, a beacon
NET = re.compile(r"\b(?:db|_db|_DB|dbClient|sb|supa|supabase|client|window\.db|window\._whSupabaseClient)\s*\.\s*"
                 r"(?:from|rpc|functions|storage|channel)\b"
                 r"|\b_?getDb\(\)\s*\.\s*(?:from|rpc|functions|storage)\b"
                 r"|(?<![\w$.])fetch\s*\(|\bwindow\.fetch\s*\(|\.invoke\s*\(|\bsendBeacon\s*\("
                 r"|\bwhFetch\w*\s*\(|\bwhRpc\w*\s*\(|\bfetchWithTimeout\s*\(")
KEYWORDS = {"if", "for", "while", "switch", "return", "function", "catch", "typeof", "new", "await", "async", "do",
            "else", "try", "finally", "throw", "delete", "void", "in", "of", "instanceof", "case", "yield", "class",
            "super", "this", "import", "export", "default", "var", "let", "const", "with"}
NOT_CALLS = KEYWORDS | {"setInterval", "setTimeout", "clearTimeout", "clearInterval", "requestAnimationFrame",
                        "Promise", "Math", "Number", "String", "Boolean", "Array", "Object", "JSON", "Date", "RegExp",
                        "Error", "parseInt", "parseFloat", "isNaN", "isFinite", "encodeURIComponent",
                        "decodeURIComponent", "_t", "escHtml", "escJsAttr", "escSafe", "e", "$"}
_BEFORE_REGEX = set("(,=:[!&|?{};+-*%<>~^")
_WORD_BEFORE_REGEX = {"return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "throw", "case", "do",
                      "else", "yield", "await"}


def served_files() -> list[Path]:
    """the served pages and shared scripts (the LB4 gate's roster, without the dot-folders of old backups)"""
    out = sorted(ROOT.glob("*.html")) + sorted(ROOT.glob("*/index.html")) + sorted(ROOT.glob("learn/*/index.html"))
    out += sorted(p for p in ROOT.glob("*.js") if p.name != "sw.js")
    return [p for p in out if not any(part.startswith(".") for part in p.relative_to(ROOT).parts)]


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def _regex_starts(s: str, j: int) -> bool:
    k = j - 1
    while k >= 0 and s[k] in " \t\r\n":
        k -= 1
    if k < 0:
        return True
    c = s[k]
    if c in _BEFORE_REGEX:
        return True
    if c.isalnum() or c in "_$":
        e = k + 1
        while k >= 0 and (s[k].isalnum() or s[k] in "_$"):
            k -= 1
        return s[k + 1:e] in _WORD_BEFORE_REGEX
    return False


def _skip_regex(s: str, j: int) -> int:
    j += 1
    cls = False
    while j < len(s):
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == "\n":
            return j
        if cls:
            if c == "]":
                cls = False
        elif c == "[":
            cls = True
        elif c == "/":
            j += 1
            while j < len(s) and s[j].isalpha():
                j += 1
            return j
        j += 1
    return j


def skip_string(s: str, j: int) -> int:
    """from the quote at j, the index just past its close (a template's ${...} is matched as code)"""
    q = s[j]
    j += 1
    while j < len(s):
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if q == "`" and c == "$" and j + 1 < len(s) and s[j + 1] == "{":
            j = match(s, j + 1) + 1
            continue
        if c == q:
            return j + 1
        if c == "\n" and q != "`":
            return j          # an unterminated quote ends with its line, never swallows the file
        j += 1
    return j


def match(s: str, i: int) -> int:
    """the index of the bracket that closes the one at i, past strings, regex literals and comments"""
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack = [pairs[s[i]]]
    j = i + 1
    while j < len(s) and stack:
        c = s[j]
        if c in "'\"`":
            j = skip_string(s, j)
            continue
        if c == "/" and j + 1 < len(s):
            if s[j + 1] == "/":
                n = s.find("\n", j)
                j = len(s) if n < 0 else n
                continue
            if s[j + 1] == "*":
                n = s.find("*/", j + 2)
                j = len(s) if n < 0 else n + 2
                continue
            if _regex_starts(s, j):
                j = _skip_regex(s, j)
                continue
        if c in pairs:
            stack.append(pairs[c])
        elif c in ")]}":
            if c == stack[-1]:
                stack.pop()
                if not stack:
                    return j
        j += 1
    return len(s) - 1


def strip_comments(s: str) -> str:
    """comments blanked (line breaks kept), strings and regex literals left alone"""
    out = list(s)
    j, n = 0, len(s)
    while j < n:
        c = s[j]
        if c in "'\"`":
            j = skip_string(s, j)
            continue
        if c == "/" and j + 1 < n:
            if s[j + 1] in "/*":
                e = (s.find("\n", j) if s[j + 1] == "/" else s.find("*/", j + 2))
                e = n if e < 0 else (e if s[j + 1] == "/" else e + 2)
                for k in range(j, e):
                    if out[k] != "\n":
                        out[k] = " "
                j = e
                continue
            if _regex_starts(s, j):
                j = _skip_regex(s, j)
                continue
        j += 1
    return "".join(out)


_SCRIPT = re.compile(r"(<script\b([^>]*)>)(.*?)(</script\s*>)", re.S | re.I)


def js_view(name: str, raw: str) -> str:
    """the code the browser runs from this file: a .js file whole; an HTML page's inline classic scripts, the rest blanked
    (line breaks kept), comments blanked"""
    if name.endswith(".js"):
        return strip_comments(raw)
    out = re.sub(r"[^\n]", " ", raw)
    parts = list(out)
    for m in _SCRIPT.finditer(raw):
        attrs = m.group(2) or ""
        if re.search(r"\bsrc\s*=", attrs, re.I):
            continue
        t = re.search(r"\btype\s*=\s*['\"]?([\w/+.-]+)", attrs, re.I)
        if t and t.group(1).lower() not in ("text/javascript", "module", "application/javascript"):
            continue
        s, e = m.start(3), m.end(3)
        parts[s:e] = list(raw[s:e])
    return strip_comments("".join(parts))


def scripts_loaded(raw: str) -> list[str]:
    """the shared root scripts an HTML page loads (<script src="x.js">, query strings dropped)"""
    out = []
    for m in re.finditer(r"<script\b[^>]*\bsrc\s*=\s*['\"]/?([\w.-]+\.js)(?:\?[^'\"]*)?['\"]", raw, re.I):
        if (ROOT / m.group(1)).exists() and m.group(1) not in out:
            out.append(m.group(1))
    return out


_DEF = re.compile(
    r"\bfunction\s*\*?\s*(?P<d>[A-Za-z_$][\w$]*)\s*\("
    r"|(?<![\w$])(?P<a>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function\b[^{(]*\(|\([^()]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>)"
    r"|(?<![\w$])(?P<p>[A-Za-z_$][\w$]*)\s*:\s*(?:async\s*)?(?:function\b[^{(]*\(|\([^()]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>)"
    r"|(?:^|(?<=[{,;}\s]))(?:async\s+)?(?P<m>[A-Za-z_$][\w$]*)\s*\([^()]*\)\s*\{")


@functools.lru_cache(maxsize=None)
def _defs(code: str) -> dict[str, list[int]]:
    """every place a function is defined in code, by name: one pass, so a lookup is a dict read"""
    out: dict[str, list[int]] = {}
    for m in _DEF.finditer(code):
        k = m.lastgroup
        name = m.group(k)
        if name in KEYWORDS:
            continue
        out.setdefault(name, []).append(m.start(k))
    return out


def _body_at(code: str, at: int, name: str) -> str | None:
    """the body of the function whose name starts at `at`"""
    j = at + len(name)
    rest = code[j:j + 300]
    lead = re.match(r"\s*(?:[=:]\s*)?(?:async\s*)?(?:function\b[^({]*)?", rest)
    k = j + (lead.end() if lead else 0)
    if code[k:k + 1] == "(":
        q = match(code, k)
    else:
        bare = re.match(r"[A-Za-z_$][\w$]*", code[k:k + 60])     # `name = x => ...`
        if not bare:
            return None
        q = k + bare.end() - 1
    am = re.match(r"\s*(?:=>\s*)?\{", code[q + 1:q + 200])
    if am:
        b = q + 1 + am.end() - 1
        return code[b:match(code, b) + 1]
    am = re.match(r"\s*=>\s*", code[q + 1:q + 200])
    if am:                                       # an expression arrow: the expression up to its end
        s = q + 1 + am.end()
        e = s
        while e < len(code) and code[e] not in ",;\n)":
            if code[e] in "([{":
                e = match(code, e) + 1
                continue
            if code[e] in "'\"`":
                e = skip_string(code, e)
                continue
            e += 1
        return code[s:e]
    return None


@functools.lru_cache(maxsize=None)
def fn_body(code: str, name: str) -> str | None:
    """the body of the function `name` defined in code: a declaration, an assignment of a function or an arrow (on a
    variable or a property, window.x = function ...), an object-literal property, or a method"""
    for at in _defs(code).get(name, ()):
        b = _body_at(code, at, name)
        if b is not None:
            return b
    return None


@functools.lru_cache(maxsize=None)
def _depths(code: str) -> dict[int, int]:
    """the brace depth at every place a function is defined (one walk, strings and regex literals skipped)"""
    want = sorted(at for ats in _defs(code).values() for at in ats)
    out, depth, j, w, n = {}, 0, 0, 0, len(code)
    while j < n and w < len(want):
        while w < len(want) and want[w] <= j:
            out[want[w]] = depth
            w += 1
        c = code[j]
        if c in "'\"`":
            j = skip_string(code, j)
            continue
        if c == "/" and j + 1 < n and code[j + 1] not in "/*" and _regex_starts(code, j):
            j = _skip_regex(code, j)
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth = max(0, depth - 1)
        j += 1
    return out


@functools.lru_cache(maxsize=None)
def global_body(code: str, name: str) -> str | None:
    """the body of `name` as ANOTHER file can call it: a top-level definition, or one put on window (window.x =
    function ..., or window.x = x for a function defined inside a wrapper). A function defined inside another one is
    not reachable by name from another file - utils.js's recently-deleted panel has an inner `load`, and a calculator's
    own `load(` text is not a call into it."""
    dep = _depths(code)
    for at in _defs(code).get(name, ()):
        before = code[max(0, at - 16):at]
        if dep.get(at, 1) == 0 or re.search(r"(?:window|self|globalThis)\.$", before):
            b = _body_at(code, at, name)
            if b is not None:
                return b
    target = _window_names(code).get(name)
    if target:
        return fn_body(code, target)
    return None


@functools.lru_cache(maxsize=None)
def _window_names(code: str) -> dict[str, str]:
    """window.x = y (a function defined inside a wrapper, put on window): x -> y, in one pass"""
    return {m.group(1): m.group(2) for m in
            re.finditer(r"\b(?:window|self|globalThis)\.([A-Za-z_$][\w$]*)\s*=\s*([A-Za-z_$][\w$]*)\s*[;\n]", code)}


def first_args(s: str, open_i: int) -> list[str]:
    """the arguments of the call whose '(' is at open_i, as text"""
    args, cur, j = [], open_i + 1, open_i + 1
    end = match(s, open_i)
    while j < end:
        c = s[j]
        if c in "'\"`":
            j = skip_string(s, j)
            continue
        if c in "([{":
            j = match(s, j) + 1
            continue
        if c == "/" and _regex_starts(s, j):
            j = _skip_regex(s, j)
            continue
        if c == ",":
            args.append(s[cur:j].strip())
            cur = j + 1
        j += 1
    last = s[cur:end].strip()
    if last or args:
        args.append(last)
    return args


def handler_text(arg: str) -> tuple[str, str | None]:
    """a handler as written where it is bound (an argument's text, or what an `.onx =` assigns): (the code it runs,
    the name of the function it hands over, if it hands over a name)"""
    a = arg.strip()
    fm = re.match(r"(?:async\s*)?(?:function\b[^{(]*\(|\()", a)
    if fm:
        q = match(a, fm.end() - 1)
        am = re.match(r"\s*(?:=>\s*)?\{", a[q + 1:q + 40])
        if am:
            b = q + 1 + am.end() - 1
            return a[b:match(a, b) + 1], None
        am = re.match(r"\s*=>\s*", a[q + 1:q + 40])
        if am:
            return a[q + 1 + am.end():], None
    am = re.match(r"(?:async\s+)?[A-Za-z_$][\w$]*\s*=>\s*", a)
    if am:
        return a[am.end():], None
    nm = re.match(r"((?:window\.|this\.)?[A-Za-z_$][\w$.]*)\s*$", a)
    if nm:
        return nm.group(1) + "()", nm.group(1).split(".")[-1]
    return a, None


def assigned_text(code: str, k: int) -> str:
    """what is assigned from k (just past `=`): to the `;` or line end at depth 0"""
    e = k
    while e < len(code):
        c = code[e]
        if c in ";\n" and code[k:e].strip():
            break
        if c in "([{":
            e = match(code, e) + 1
            continue
        if c in "'\"`":
            e = skip_string(code, e)
            continue
        if c in ")]}":
            break
        e += 1
    return code[k:e]


_LISTEN = re.compile(r"\.addEventListener\(\s*['\"`][\w:-]+['\"`]\s*,|\.on[a-z]+\s*=(?!=)|\.on\(\s*['\"`]")


def without_bound_listeners(text: str) -> str:
    """a body with the callbacks it BINDS to other events cut out: binding a listener runs nothing"""
    out = text
    for _ in range(40):
        m = _LISTEN.search(out)
        if not m:
            break
        k = m.end()
        seg = out[k:k + 300]
        fm = re.match(r"\s*(?:async\s*)?(?:function\b[^{(]*\(|\()", seg)
        if fm and not re.match(r"\s*\(\s*['\"`]", seg):
            p = k + fm.end() - 1
            q = match(out, p)
            am = re.match(r"\s*(?:=>\s*)?\{", out[q + 1:q + 40])
            if am:
                b = q + 1 + am.end() - 1
                e = match(out, b)
                out = out[:m.start()] + " bound_listener()" + out[e + 1:]
                continue
        am = re.match(r"\s*[A-Za-z_$][\w$]*\s*=>\s*\{", seg)
        if am:
            b = k + am.end() - 1
            e = match(out, b)
            out = out[:m.start()] + " bound_listener()" + out[e + 1:]
            continue
        # a named function passed as the listener: binding it calls nothing now
        nm = re.match(r"\s*([A-Za-z_$][\w$.]*)\s*[,)]", seg)
        if nm:
            out = out[:m.start()] + " bound_listener" + out[k + nm.end() - 1:]
            continue
        out = out[:m.start()] + " " + out[m.end():]
    return out


def calls_in(text: str) -> list[str]:
    names = re.findall(r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*\(", text)
    names += re.findall(r"\b(?:window|this|self)\.([A-Za-z_$][\w$]*)\s*\(", text)
    return [c for c in dict.fromkeys(names) if c not in NOT_CALLS and c != "bound_listener"]


def reaches_network(text: str, codes: list[str], depth: int = 3) -> list[str] | None:
    """the chain of calls from `text` to a call that leaves the browser (looked up in each of `codes` in turn - the
    file's own code first, then the shared scripts it loads), or None. Listeners the code binds are not followed."""
    seen: set[str] = set()
    frontier = [("", without_bound_listeners(text), [])]
    for _ in range(depth + 1):
        nxt = []
        for name, t, path in frontier:
            m = NET.search(t)
            if m:
                return path + ([name] if name else []) + [re.sub(r"\s+", "", m.group(0))[:40]]
            for c in calls_in(t):
                if c in seen:
                    continue
                seen.add(c)
                for i, code in enumerate(codes):
                    b = fn_body(code, c) if i == 0 else global_body(code, c)   # another file: only what it exposes
                    if b:
                        nxt.append((c, without_bound_listeners(b), path + ([name] if name else [])))
                        break
        frontier = nxt
        if not frontier:
            break
    return None


def line_of(code: str, at: int) -> int:
    return code.count("\n", 0, at) + 1


def enclosing_fn(code: str, at: int) -> str | None:
    """the innermost named function declaration around `at`"""
    best = None
    for m in re.finditer(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(", code[:at]):
        p = code.find("(", m.end() - 1)
        q = match(code, p)
        k = code.find("{", q)
        if 0 <= k < at and match(code, k) > at:
            best = m.group(1)
    return best
