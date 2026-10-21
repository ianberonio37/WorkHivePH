"""validate_one_person_cannot_flood.py - a page's typing waits for a pause, a held key sends once, and its polls are
spaced, so one person cannot flood the backend (SL RL3, 2026-10-22).

Surveyed from the code the browser runs (tools/lib/js_reach.py) on the 36 RL3 pages and every shared script: 26 keystroke
handlers reach the network. Every SEARCH already waited for the typing to pause (community, inventory, logbook's asset
picker, the marketplace search and price boxes, marketplace-admin, asset-hub, the search overlay, the sign-up name
check). The flood was the Enter key. A button that sends locks itself while it works (`disabled`), so a second click
cannot reach it - but Enter in the field beside it called the same function directly, past the lock, and a key held
down repeats about 30 times a second: hive's reliability coach sent one AI call a repeat (each charged to the hive's
budget), its join-by-code one join, index's sign-in one login and its sign-up one breach check and one account each
(the sign-up's lock came after its first wait, so even a second click got through). Founder-console's R shortcut ran
the whole 14-read refresh on every repeat, aborting only 2 of them. And a control that stays focused while its key acts
- an achievement card toggling open and shut, asset-hub's detail tabs (the arrows wrap, so a held arrow cycled the tabs
and loaded the Weibull and P-F panels on every pass) - ran its read or its usage event on every repeat.

STATIC  F1 typing waits for a pause: an input / keyup / keypress / search listener (or a keydown that tests no key) whose
           handler reaches the network - in its own file or through the shared scripts its page loads - runs through
           debounce(), or defers through a timer it cancels on the next keystroke (clearTimeout + setTimeout), in the
           handler or the one function it names; or the line above says why it must not wait (`typing-network: <why>`);
        F2 a held key sends once: a key command (a handler that tests which key) whose action reaches the network reads
           the event's `.repeat`, is a dismissal (Escape only), or runs a function that refuses while its last run is
           still working - an early return, before the function's first await, on the lock it sets there (a flag, a
           control's `disabled`), or a field it empties there that the early return reads;
        F3 polls are spaced: every network setInterval the LB4 gate holds (tools/validate_refresh_stands_down_hidden.py
           refreshers - the same roster, so the two gates agree on what a poll is), every whPoll / whLivePoll /
           pollMs a page asks for, and every timer loop that reschedules itself and reaches the network, runs at 10 s
           or slower (the LB4 banker's floor) - its period read from the literal, the constant, the parameter default or
           the options of the <select> that sets it - or ends itself (its tick clears its own interval; a retry loop
           bounded by a count), or is in CADENCE_DECLARED with why;
        F4 the helpers hold: utils.js debounce() cancels the pending call and schedules the next; whPoll skips a tick
           while the last one is in flight and keeps a floor on its period; whLivePoll's default is 10 s or slower.
EXCLUDED, and why: a `change` listener (it fires once, when the person commits); a listener the handler BINDS (it runs on
its own event, not on this keystroke); old backup folders (.*_bak, never served); the network reached only through the
error logger whTold (a failure line, one per sentence per load) still counts - a debounced search that logs a failure is
debounced.
SELF-TEST (--self-test): each rule broken in a copy of a real file (or a synthetic page beside them), each caught; the
clean run is green.

    python tools/validate_one_person_cannot_flood.py [--self-test] [--list]
"""
from __future__ import annotations

import functools
import re
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from lib import js_reach as jr  # noqa: E402
import validate_refresh_stands_down_hidden as lb4  # noqa: E402

FLOOR_MS = 10000
EV = r"input|keyup|keydown|keypress|search"
# a handler that reads which key was pressed is a key command; one that reads only the text is typing
KEY_TEST = re.compile(r"\.(?:key|code|keyCode|which)\b(?!\s*\()")
# the keys a command compares against (e.key === 'Enter', k !== 'ArrowRight', 'Escape' === e.key)
KEYS = re.compile(r"""[!=]==?\s*(['"])([^'"\n]{1,12})\1|(['"])([^'"\n]{1,12})\3\s*[!=]==?""")
DECLARE = "typing-network:"
# a poll whose period sits under the floor by design: the file, the period as written, and why it cannot flood
CADENCE_DECLARED = {
    ("connectivity-widget.js", "4000"): "refreshes the connectivity popover's figures only while the popover is OPEN (a "
                                        "person reading it) or the device is offline (nothing leaves it); LB4 walked "
                                        "every page idle and this timer sent nothing",
}


@functools.lru_cache(maxsize=None)
def _view(name: str, raw: str) -> str:
    return jr.js_view(name, raw)


def _codes_for(name: str, raw: str, texts: dict[str, str]) -> list[str]:
    """the code a handler in this file can call: its own, then the shared scripts its page loads (utils.js for a script)"""
    own = _view(name, raw)
    shared = jr.scripts_loaded(raw) if name.endswith(".html") else ["utils.js"]
    return [own] + [_view(s, texts[s]) for s in shared if s in texts and s != name]


def _body_of(codes: list[str], fn: str) -> str:
    """the function's body in the file's own code, else as a shared script exposes it (never an inner function there)"""
    for i, c in enumerate(codes):
        b = jr.fn_body(c, fn) if i == 0 else jr.global_body(c, fn)
        if b:
            return b
    return ""


def keystroke_handlers(name: str, raw: str, texts: dict[str, str]) -> list[dict]:
    code = _view(name, raw)
    codes = _codes_for(name, raw, texts)
    out = []

    def add(ev: str, at: int, src: str, text: str, named: str | None, line: int) -> None:
        body = _body_of(codes, named) if named else ""
        # an inline attribute that only calls a page function (handleInputKey(event)): that function is the handler
        if not named:
            only = re.fullmatch(r"\s*(?:return\s+)?([A-Za-z_$][\w$]*)\s*\([^()]*\)\s*;?\s*", text)
            if only and only.group(1) not in jr.NOT_CALLS:
                named, body = only.group(1), _body_of(codes, only.group(1))
        whole = text + " " + body
        keyed = ev in ("keydown", "keyup", "keypress") and bool(KEY_TEST.search(whole))
        path = jr.reaches_network(whole, codes)
        above = "\n".join(src.split("\n")[max(0, line - 3):line])
        out.append({"file": name, "line": line, "ev": ev, "text": text, "named": named, "body": body,
                    "whole": whole, "keyed": keyed, "path": path, "declared": DECLARE in above, "codes": codes})

    for m in re.finditer(r"\.addEventListener\(\s*['\"](" + EV + r")['\"]\s*,", code):
        args = jr.first_args(code, m.start() + len(".addEventListener"))
        text, named = jr.handler_text(args[1] if len(args) > 1 else "")
        add(m.group(1), m.start(), raw, text, named, jr.line_of(code, m.start()))
    for m in re.finditer(r"\.on(" + EV + r")\s*=(?!=)", code):
        text, named = jr.handler_text(jr.assigned_text(code, m.end()))
        add(m.group(1), m.start(), raw, text, named, jr.line_of(code, m.start()))
    # inline attributes, in the markup and in the templates that write markup
    for m in re.finditer(r"\bon(" + EV + r")\s*=\s*\"([^\"]*)\"", raw):
        text = m.group(2).replace("&quot;", '"').replace("&#39;", "'").replace("&amp;", "&")
        add(m.group(1), m.start(), raw, text, None, raw.count("\n", 0, m.start()) + 1)
    return out


def _deferred(h: dict) -> bool:
    """the handler's network work waits for the typing to pause"""
    for t in (h["text"], h["body"]):
        if re.search(r"\bdebounce\s*\(", t) or (re.search(r"\bclearTimeout\s*\(", t) and re.search(r"\bsetTimeout\s*\(", t)):
            return True
    # it names a function that IS a debounced one (const search = debounce(...))
    for nm in [h["named"]] + jr.calls_in(h["text"])[:2]:
        if nm and any(re.search(r"\b(?:const|let|var)\s+" + re.escape(nm) + r"\s*=\s*debounce\s*\(", c) for c in h["codes"]):
            return True
    return False


def _first_await(body: str) -> int:
    m = re.search(r"\bawait\b", body)
    return m.start() if m else len(body)


def _locked(fn_body: str) -> str | None:
    """how a function refuses while its last run is still working, or None"""
    pre = fn_body[:_first_await(fn_body)]
    for g in re.finditer(r"\bif\s*\(", pre):
        close = jr.match(pre, g.end() - 1)
        cond, after, later = pre[g.end():close], pre[close + 1:close + 200], pre[close:]
        if not re.match(r"\s*(?:\{[^{}]*?)?\breturn\b", after):
            continue
        # the lock this early return reads is set AFTER it and before the first wait: a flag, or a control's disabled
        for f in re.findall(r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*=\s*true\b", later):
            if re.search(r"(?<![\w$.])" + re.escape(f) + r"(?![\w$])", cond):
                return f"returns while {f}"
        for d in re.findall(r"\b([A-Za-z_$][\w$]*)\.disabled\s*=\s*true\b", later):
            if re.search(r"(?<![\w$.])" + re.escape(d) + r"\.disabled\b", cond):
                return f"returns while {d}.disabled"
    # the field it sends is emptied before the first wait, and an early return reads what it sent
    if re.search(r"\.value\s*=\s*(?:''|\"\")", pre) and re.search(r"\bif\s*\(\s*!\s*[\w$]+[^)]*\)\s*(?:\{[^{}]*?)?\breturn\b", pre):
        return "empties the field it sends before it waits"
    return None


def _runs(h: dict) -> list[tuple[str, str]]:
    """the functions a key command runs that reach the network: (name, body). index's Enter runs the sign-in on one
    panel and the sign-up on the other, and each is its own way in."""
    out = []
    text = h["text"] if not h["named"] else h["body"]
    for c in jr.calls_in(jr.without_bound_listeners(text)):
        b = _body_of(h["codes"], c)
        if b and jr.reaches_network(b, h["codes"]):
            out.append((c, b))
    return out


def key_verdict(h: dict) -> tuple[str | None, list[str]]:
    """why a key command sends once per press (or None), and the functions it runs that reach the network unlocked"""
    if re.search(r"\.repeat\b", h["whole"]):
        return "skips a held key's repeats", []
    keys = {m[1] or m[3] for m in KEYS.findall(h["whole"])}
    if keys and keys <= {"Escape", "Esc", "Tab"}:
        return "a dismissal (Escape)", []
    ran = _runs(h)
    how = [f"{c} {_locked(b)}" for c, b in ran if _locked(b)]
    unlocked = [c for c, b in ran if not _locked(b)]
    if ran and not unlocked:
        return "; ".join(how), []
    return None, unlocked or [p for p in (h["path"] or [])[:1]]


def lock_bypassed(h: dict) -> list[str]:
    """F2b: a function a key runs that LOCKS its own control while it works (a disabled control or a busy flag it sets,
    and clears again) must test that lock before it sets it, and set it before its first wait - a click cannot reach a
    disabled button, but a key reaches the function directly. Tested in the handler (its .disabled) counts too."""
    out = []
    for c, b in _runs(h):
        sets = re.findall(r"\b([A-Za-z_$][\w$]*)\.disabled\s*=\s*true\b", b)
        flags = [f for f in re.findall(r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*=\s*true\b", b)
                 if re.search(r"(?<![\w$.])" + re.escape(f) + r"\s*=\s*false\b", b)]
        sets = [d for d in sets if re.search(r"\b" + re.escape(d) + r"\.disabled\s*=\s*false\b", b)]
        if not sets and not flags:
            continue                              # it holds no lock of its own: F2 asks of it what it asks of any key
        if _locked(b) or re.search(r"\.disabled\b", h["text"] if not h["named"] else h["body"]):
            continue
        first = _first_await(b)
        early = [x for x in sets + flags if re.search(r"\b" + re.escape(x) + r"(?:\.disabled)?\s*=\s*true\b", b[:first])]
        out.append(f"{c} sets its lock ({', '.join(dict.fromkeys(sets + flags))}) "
                   + ("but never tests it before setting it" if early else "only after its first wait"))
    return out


# ── F3 ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
def _resolve(expr: str, code: str, raw: str, depth: int = 0) -> list[int] | None:
    """the periods (ms) an expression can take: a literal, arithmetic over constants, a parameter's default, or the
    options of the <select> it is read from"""
    e = expr.strip().rstrip(";")
    if depth > 4 or not e:
        return None
    m = re.fullmatch(r"(.+?)\s*\|\|\s*([\d_]+)", e)
    if m:                                        # `periodMs || 60000`: the caller's value or the default
        left = _resolve(m.group(1), code, raw, depth + 1)
        return sorted(set((left or []) + [int(m.group(2).replace("_", ""))]))
    m = re.fullmatch(r"Math\.max\(\s*([\d_]+)\s*,\s*(.+)\)", e)
    if m:
        inner = _resolve(m.group(2), code, raw, depth + 1)
        return [max(int(m.group(1)), x) for x in inner] if inner else [int(m.group(1))]
    toks = re.findall(r"[A-Za-z_$][\w$.]*", e)
    vals: dict[str, list[int]] = {}
    for t in toks:
        if t in ("Math",):
            return None
        d = re.search(r"\b(?:const|let|var)\s+" + re.escape(t) + r"\s*=\s*([^;\n]+)", code)
        if not d:
            return None
        rhs = d.group(1).strip()
        depth_, cut = 0, len(rhs)               # `var pollMs = opts.pollMs || 60000, poll = null`: the first one only
        for i, ch in enumerate(rhs):
            if ch in "([{":
                depth_ += 1
            elif ch in ")]}":
                depth_ -= 1
            elif ch == "," and depth_ == 0:
                cut = i
                break
        rhs = rhs[:cut].strip()
        sel = re.search(r"Number\(\s*\w+\.target\.value\s*\)", rhs)
        if sel:                                  # read from a <select>: every option it offers, Off (0) aside
            lst = code[:d.start()].rfind("getElementById(")
            sid = re.match(r"getElementById\(\s*['\"]([^'\"]+)", code[lst:]) if lst >= 0 else None
            sm = sid and re.search(r"<select\b[^>]*\bid=\"" + re.escape(sid.group(1)) + r"\"[^>]*>(.*?)</select>", raw, re.S)
            if not sm:
                return None
            opts = [int(v) for v in re.findall(r"value=\"(\d+)\"", sm.group(1)) if int(v) > 0]
            vals[t] = opts or [0]
            continue
        r = _resolve(rhs, code, raw, depth + 1)
        if r is None:
            return None
        vals[t] = r
    if not re.fullmatch(r"[\w$.\s*+/()-]+", e):
        return None
    # one value per name at a time (a select contributes each option)
    names = list(vals)
    combos = [{}]
    for n in names:
        combos = [dict(c, **{n: v}) for c in combos for v in vals[n]]
    out = []
    for c in combos:
        ex = e
        for n in sorted(c, key=len, reverse=True):
            ex = re.sub(r"(?<![\w$.])" + re.escape(n) + r"(?![\w$])", str(c[n]), ex)
        if not re.fullmatch(r"[\d\s*+/()._-]+", ex):
            return None
        try:
            out.append(int(eval(ex.replace("_", ""), {"__builtins__": {}})))  # noqa: S307 - digits and operators only
        except Exception:
            return None
    return sorted(set(out))


def polls(name: str, raw: str, texts: dict[str, str]) -> list[dict]:
    code = _view(name, raw)
    codes = _codes_for(name, raw, texts)
    out = []
    # the LB4 gate's own roster of network setIntervals (it reads the file as written; its line is the file's line)
    lines = code.split("\n")
    for r in lb4.refreshers(name, raw):
        off = sum(len(x) + 1 for x in lines[:r["line"] - 1])
        m = re.compile(r"\bsetInterval\s*\(").search(code, off)
        if not m:
            continue
        args = jr.first_args(code, m.end() - 1)
        if len(args) < 2:
            continue
        cb = args[0]
        nm = re.fullmatch(r"(?:async\s+)?([A-Za-z_$][\w$]*)", cb.strip())
        tick = cb + " " + (_body_of(codes, nm.group(1)) if nm else "")
        out.append({"file": name, "line": r["line"], "what": "setInterval", "delay": args[1],
                    "ends": bool(re.search(r"\bclearInterval\s*\(", tick)), "code": code})
    for m in re.finditer(r"(?<![\w$.])(whPoll|whLivePoll)\s*\(", code):
        if re.search(r"function\s*$", code[max(0, m.start() - 12):m.start()]):
            continue
        args = jr.first_args(code, m.end() - 1)
        i = 1 if m.group(1) == "whPoll" else 3
        delay = args[i] if len(args) > i and args[i] else ("30000" if m.group(1) == "whPoll" else "15000")
        out.append({"file": name, "line": jr.line_of(code, m.start()), "what": m.group(1), "delay": delay, "ends": False,
                    "code": code})
    for m in re.finditer(r"\bpollMs\s*:\s*([^,}\n]+)", code):
        out.append({"file": name, "line": jr.line_of(code, m.start()), "what": "pollMs", "delay": m.group(1), "ends": False,
                    "code": code})
    # a timer loop that reschedules itself (setTimeout(fn) inside fn) and reaches the network
    for m in re.finditer(r"\bsetTimeout\s*\(\s*(?:\(\s*\)\s*=>\s*)?([A-Za-z_$][\w$]*)\s*(?:\(\s*\))?\s*,", code):
        fn = m.group(1)
        if jr.enclosing_fn(code, m.start()) != fn:
            continue
        body = jr.fn_body(code, fn) or ""
        if not jr.reaches_network(body, codes):
            continue
        args = jr.first_args(code, m.start() + len("setTimeout"))
        before = code[max(0, m.start() - 160):m.start()]
        bounded = bool(re.search(r"\bif\s*\(\s*[\w$]+\s*<=?\s*\d+\s*\)\s*$", before.rstrip()))
        out.append({"file": name, "line": jr.line_of(code, m.start()), "what": f"loop {fn}", "delay": args[1] if len(args) > 1 else "0",
                    "ends": bounded, "code": code})
    for p in out:
        p["ms"] = _resolve(p["delay"], p["code"], raw)
        p["declared"] = CADENCE_DECLARED.get((name, p["delay"].strip()))
    return out


def check_helpers(utils: str) -> list[str]:
    u = jr.js_view("utils.js", utils)
    issues = []
    d = jr.fn_body(u, "debounce") or ""
    if not (re.search(r"\bclearTimeout\s*\(", d) and re.search(r"\bsetTimeout\s*\(", d)):
        issues.append("F4 utils.js debounce() no longer cancels the pending call and schedules the next - every search "
                      "built on it sends a request per keystroke")
    w = jr.fn_body(u, "whPoll") or ""
    t = jr.fn_body(w, "tick") or ""
    if not re.search(r"\bif\s*\([^)]*\binFlight\b[^)]*\)\s*return", t):
        issues.append("F4 utils.js whPoll's tick no longer skips while its last load is in flight - a slow read and the "
                      "next tick overlap")
    if not re.search(r"Math\.max\(\s*\d{4,}", w):
        issues.append("F4 utils.js whPoll no longer keeps a floor on its period - a page can ask it to hammer")
    lv = jr.fn_body(u, "whLivePoll") or ""
    dm = re.search(r"\bms\s*\|\|\s*(\d+)", lv)
    if not dm or int(dm.group(1)) < FLOOR_MS:
        issues.append(f"F4 utils.js whLivePoll's default period is under {FLOOR_MS // 1000} s")
    return issues


_SEEN: dict = {}


def _analyze(name: str, raw: str, texts: dict[str, str]) -> tuple[list[dict], list[dict]]:
    """a file's keystroke handlers and polls - read once per version of the file and of the scripts it loads (the
    self-test changes one file at a time)"""
    shared = jr.scripts_loaded(raw) if name.endswith(".html") else ["utils.js"]
    key = (name, raw, tuple((s, texts.get(s)) for s in shared))
    if key not in _SEEN:
        _SEEN[key] = (keystroke_handlers(name, raw, texts), polls(name, raw, texts))
    return _SEEN[key]


def check(texts: dict[str, str] | None = None) -> tuple[list[str], list[dict], list[dict]]:
    if texts is None:
        texts = {jr.rel(p): p.read_text(encoding="utf-8", errors="replace") for p in jr.served_files()}
    issues, keys_seen, polls_seen = [], [], []
    for name, raw in sorted(texts.items()):
        handlers, file_polls = _analyze(name, raw, texts)
        for h in handlers:
            if not h["path"]:
                continue
            keys_seen.append(h)
            where = f"{name}:{h['line']} [{h['ev']}]"
            via = " > ".join(h["path"])
            if h["keyed"]:
                h["how"], unlocked = key_verdict(h)
                if not h["how"]:
                    issues.append(f"F2 {where} a key held down repeats about 30 times a second, and each repeat reaches the "
                                  f"network ({via}) - read event.repeat, or let {', '.join(unlocked)} refuse while its last "
                                  "run is still working")
                for bypass in lock_bypassed(h):
                    issues.append(f"F2 {where} {bypass} - a second press of the key while it works reaches it past the "
                                  "locked control; return early while the lock is set, and set it before the first wait")
            else:
                h["how"] = "debounced" if _deferred(h) else ("declared: typing-network" if h["declared"] else None)
                if not h["how"]:
                    issues.append(f"F1 {where} sends on every keystroke ({via}) - let it wait for the typing to pause "
                                  "(debounce, or a timer it cancels on the next keystroke)")
        for p in file_polls:
            polls_seen.append(p)
            ms = p["ms"]
            if p["ends"] or p["declared"]:
                continue
            if ms is None:
                issues.append(f"F3 {name}:{p['line']} {p['what']} every '{p['delay'][:40]}' - its period cannot be read; "
                              "write it as a number or a constant, or declare it in CADENCE_DECLARED with why")
            elif min(ms) < FLOOR_MS:
                issues.append(f"F3 {name}:{p['line']} {p['what']} reaches the network every {min(ms) / 1000:g} s - under "
                              f"the {FLOOR_MS // 1000} s floor")
    issues += check_helpers(texts.get("utils.js", ""))
    return issues, keys_seen, polls_seen


def self_test() -> list[str]:
    fails = []
    texts = {jr.rel(p): p.read_text(encoding="utf-8", errors="replace") for p in jr.served_files()}
    clean, keys_seen, polls_seen = check(dict(texts))
    if clean:
        fails.append(f"the clean run is not green: {clean[:3]}")
    if len(keys_seen) < 15 or len(polls_seen) < 10:
        fails.append(f"only {len(keys_seen)} network keystroke handlers and {len(polls_seen)} polls found - the reader collapsed")

    def mut(label: str, changes: dict[str, str], want: str) -> None:
        for k, v in changes.items():
            if k in texts and v == texts[k]:
                fails.append(f"mutant '{label}' changed nothing in {k} (its anchor moved)")
                return
        t = dict(texts)
        t.update(changes)
        got, _, _ = check(t)
        # caught by the rule it breaks, on the file it changed - not by some other finding the change happened to cause
        if not any(g.startswith(want) and any(k in g for k in changes) for g in got):
            fails.append(f"mutant '{label}' was not caught (got {got[:2]})")

    cm = texts["community.html"]
    mut("community's search sends per keystroke", {"community.html": cm.replace(
        "debounce(() => { loadPosts(); _commSyncUrl(); }, 400)", "() => { loadPosts(); _commSyncUrl(); }", 1)}, "F1")
    ix = texts["index.html"]
    mut("the sign-up name check asks per keystroke", {"index.html": ix.replace(
        "clearTimeout(_usernameTimer);\n    _usernameTimer = setTimeout(async () => {", "(async () => {", 1)}, "F1")
    mut("the sign-up locking only after its first wait (as before)", {"index.html": ix.replace(
        "    if (btn.disabled) return;   // a run already working", "    // a run already working", 1).replace(
        "    btn.textContent = 'Creating account…'; btn.disabled = true;\n    if (await _passwordBreached(password)) {",
        "    if (await _passwordBreached(password)) {", 1).replace(
        "    const db = _getDb();\n\n    // Username uniqueness",
        "    btn.textContent = 'Creating account…'; btn.disabled = true;\n    const db = _getDb();\n\n    // Username uniqueness", 1)},
        "F2")
    mut("the sign-in run past its own lock (as before)", {"index.html": ix.replace(
        "    if (btn.disabled) return;\n\n    errEl.classList.add('hidden');\n    if (!username || !password) {",
        "\n    errEl.classList.add('hidden');\n    if (!username || !password) {", 1)}, "F2")
    ahb = texts["asset-hub.html"]
    mut("a held arrow spinning asset-hub's tabs again", {"asset-hub.html": ahb.replace(
        "          if (ev.repeat) return;\n", "", 1)}, "F2")
    mut("a new page searching the database per keystroke", {"synthetic-search.html": (
        "<script src=\"utils.js\"></script><script>document.getElementById('q').addEventListener('input', (e) => "
        "{ db.from('logbook').select('*').ilike('machine', e.target.value); });</script>")}, "F1")
    hv = texts["hive.html"]
    mut("the coach's Enter past its lock again", {"hive.html": re.sub(
        r"\n\s*if \(btn\.disabled\) return;[^\n]*\n(\s*btn\.disabled\s*=\s*true;\n\s*btn\.textContent = '\.\.\.';)",
        r"\n\1", hv, count=1)}, "F2")
    mut("hive creation's double-submit guard removed", {"hive.html": hv.replace(
        "  if (btn.disabled) return;  // P7-01", "  // P7-01", 1)}, "F2")
    cl = texts["companion-launcher.js"]
    mut("the companion sends again on a held Enter", {"companion-launcher.js": cl.replace(
        "if (!message || isTyping) return;\n\n    input.value = '';", "if (!message) return;\n\n", 1)}, "F2")
    mut("a shortcut refreshing on every repeat", {"synthetic-shortcut.html": (
        "<script>document.addEventListener('keydown', e => { if (e.key === 'u') reload(); });"
        "async function reload() { await db.from('logbook').select('*'); }</script>")}, "F2")
    ah = texts["alert-hub.html"]
    mut("alert-hub polling every 3 s", {"alert-hub.html": re.sub(r"(setInterval\(\s*loadAll\s*,\s*)60000", r"\g<1>3000", ah, count=1)}, "F3")
    al = texts["audit-log.html"]
    mut("audit-log's poll asking for 4 s", {"audit-log.html": re.sub(r"(whPoll\([\s\S]{0,200}?,\s*)30000", r"\g<1>4000", al, count=1)}, "F3")
    fc = texts["founder-console.html"]
    mut("founder-console offering a 5 s auto-refresh", {"founder-console.html": fc.replace(
        '<option data-i="p_autos_5963" value="30">', '<option data-i="p_autos_5963" value="5">', 1)}, "F3")
    mut("a timer loop fetching every 2 s with no end", {"synthetic-loop.html": (
        "<script>function pull() { fetch('/rest/v1/logbook'); setTimeout(pull, 2000); }</script>")}, "F3")
    ut = texts["utils.js"]
    mut("debounce() calling at once", {"utils.js": ut.replace(
        "    clearTimeout(t);\n    t = setTimeout(() => fn.apply(this, args), wait);", "    fn.apply(this, args);", 1)}, "F4")
    mut("whPoll overlapping its own loads", {"utils.js": ut.replace(
        "if (stopped || inFlight) return;", "if (stopped) return;", 1)}, "F4")
    return fails


def main() -> int:
    if "--self-test" in sys.argv:
        fails = self_test()
        print("SELF-TEST PASS (16 mutants caught; the clean run is green)" if not fails else "SELF-TEST FAIL\n  " + "\n  ".join(fails))
        return 1 if fails else 0
    issues, keys_seen, polls_seen = check()
    print("One person cannot flood (SL RL3): typing waits for a pause, a held key sends once, polls are spaced")
    if "--list" in sys.argv:
        for h in keys_seen:
            print(f"  {h['file']}:{h['line']} [{h['ev']}{' key' if h['keyed'] else ''}] -> {' > '.join(h['path'])}  ::  {h.get('how') or 'FLOODS'}")
        for p in polls_seen:
            print(f"  {p['file']}:{p['line']} {p['what']} every {p['delay'][:30]!r} = {p['ms']} ms"
                  + (" (ends itself)" if p["ends"] else "") + (f" (declared: {p['declared'][:60]})" if p["declared"] else ""))
    for i in issues[:40]:
        print("  [FAIL] " + i)
    print(f"  PASS - {len(keys_seen)} keystroke handlers reach the network and each waits or sends once; {len(polls_seen)} "
          f"polls, each {FLOOR_MS // 1000} s or slower, ending itself, or declared" if not issues
          else f"  FAIL - {len(issues)} problem(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
