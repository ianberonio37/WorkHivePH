"""validate_refresh_stands_down_hidden.py - a page refreshes on a bounded cadence, and never for nobody (SL LB4, 2026-10-22).

Walked as each LB4 row's cast (75 s untouched and visible, then 75 s hidden, as a phone does when its screen goes off),
34 of 35 pages refreshed on a bounded cadence and fell silent while hidden; platform-actions sent all 14 of its queue
reads every minute to a tab nobody could see - its only stop was `pagehide`, which fires on leaving the page, not on
hiding it. Two more refreshers of the same shape could not be reached idle - marketplace's live-job map (every 10 s
while a job is tracked) and founder-console's chosen auto-refresh - and read the same way when hidden.

STATIC  H1 every setInterval on a served page or a shared script whose tick reaches the network (a database call, a
           function call, a fetch - in the callback or in the named function it runs, or one call further down) stands
           down while the tab is hidden:
             - its tick reads `document.hidden` / `visibilityState` before it reads anything, or
             - it runs through whPoll / whLivePoll (utils.js), whose ticks skip a hidden tab, or
             - it is started by a start function whose stop function a visibilitychange listener calls, or
             - the line above it says why it must run hidden: `refresh-hidden: <reason>` (an offline queue's drain sends
               what the person queued, and a queued write should reach the server from a background tab);
        H2 whPoll and whLivePoll themselves skip a hidden tab (their ticks read document.hidden).
SELF-TEST (--self-test): each rule broken in a copy, each caught; the clean run is green.

    python tools/validate_refresh_stands_down_hidden.py [--self-test] [--list]
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
NET = re.compile(r"\b(?:db|_db|sb|supa|supabase|client|window\.db|getDb\(\))\s*\.\s*(?:from|rpc|functions|storage)\b"
                 r"|\bfetch\s*\(|\.invoke\s*\(|\bwhFetch\w*\s*\(|\bwhRpc\w*\s*\(")
HIDDEN = re.compile(r"document\.hidden|visibilityState")
EXEMPT = "refresh-hidden:"


def served_files() -> list[Path]:
    out = sorted(p for p in ROOT.glob("*.html"))
    out += sorted(p for p in ROOT.glob("*/index.html"))
    out += sorted(p for p in ROOT.glob("learn/*/index.html"))
    out += sorted(p for p in ROOT.glob("*.js") if p.name not in ("sw.js",))
    return out


def blank_comments(src: str) -> str:
    out = re.sub(r"<!--.*?-->", lambda m: re.sub(r"[^\n]", " ", m.group(0)), src, flags=re.S)
    out = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), out, flags=re.S)
    return re.sub(r"(^|[^:'\"\\])//[^\n]*", lambda m: m.group(1) + " " * (len(m.group(0)) - len(m.group(1))), out)


def skip_str(s: str, j: int) -> int:
    q = s[j]; j += 1
    while j < len(s):
        c = s[j]
        if c == "\\":
            j += 2; continue
        if q == "`" and c == "$" and j + 1 < len(s) and s[j + 1] == "{":
            j = match(s, j + 1) + 1; continue
        if c == q:
            return j + 1
        j += 1
    return j


def match(s: str, i: int) -> int:
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack = [pairs[s[i]]]; j = i + 1
    while j < len(s) and stack:
        c = s[j]
        if c in "'\"`":
            j = skip_str(s, j); continue
        if c in pairs:
            stack.append(pairs[c])
        elif c in ")]}":
            if stack and c == stack[-1]:
                stack.pop()
                if not stack:
                    return j
        j += 1
    return len(s) - 1


def first_arg(s: str, open_i: int) -> str:
    """the text of a call's first argument (open_i at its '(')"""
    j, depth = open_i + 1, 0
    while j < len(s):
        c = s[j]
        if c in "'\"`":
            j = skip_str(s, j); continue
        if c in "([{":
            j = match(s, j) + 1; continue
        if c in ",)":
            return s[open_i + 1:j].strip()
        j += 1
    return s[open_i + 1:].strip()


def fn_body(code: str, name: str) -> str:
    m = re.search(r"(?:\bfunction\s+" + re.escape(name) + r"\s*\(|\b" + re.escape(name)
                  + r"\s*=\s*(?:async\s*)?(?:function\b[^{]*|\([^)]*\)\s*=>\s*|[\w$]+\s*=>\s*))", code)
    if not m:
        return ""
    k = code.find("{", m.end() - 1)
    return code[k:match(code, k) + 1] if k >= 0 else ""


def enclosing_fn(code: str, at: int) -> str | None:
    best = None
    for m in re.finditer(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(", code[:at]):
        k = code.find("{", m.end())
        if k >= 0 and k < at and match(code, k) > at:
            best = m.group(1)
    return best


NOT_CALLS = {"if", "for", "while", "switch", "return", "function", "catch", "setInterval", "setTimeout", "Promise", "await"}


def reaches_network(code: str, text: str, depth: int = 3) -> bool:
    """the tick reaches the network itself, or through the functions it calls by name in the same file (three calls
    down: founder-console's refreshAll reaches its reads through the loaders it calls)"""
    seen: set[str] = set()
    frontier = [text]
    for _ in range(depth + 1):
        nxt = []
        for t in frontier:
            if NET.search(t):
                return True
            for c in dict.fromkeys(re.findall(r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*\(", t)):
                if c in NOT_CALLS or c in seen:
                    continue
                seen.add(c)
                b = fn_body(code, c)
                if b:
                    nxt.append(b)
        frontier = nxt
        if not frontier:
            break
    return False


def refreshers(name: str, raw: str) -> list[dict]:
    code = blank_comments(raw)
    out = []
    for m in re.finditer(r"\bsetInterval\s*\(", code):
        o = m.end() - 1
        cb = first_arg(code, o)
        ident = re.fullmatch(r"(?:async\s+)?([A-Za-z_$][\w$]*)", cb)
        body = fn_body(code, ident.group(1)) if ident else cb
        tick = cb + " " + body
        if not reaches_network(code, tick):
            continue
        line = code.count("\n", 0, m.start()) + 1
        above = "\n".join(raw.split("\n")[max(0, line - 4):line])
        how = None
        if EXEMPT in above:
            how = "declared: " + above[above.find(EXEMPT) + len(EXEMPT):].split("\n")[0].strip()[:120]
        elif HIDDEN.search(tick):
            how = "the tick reads document.hidden"
        else:
            enc = enclosing_fn(code, m.start())
            if enc and re.match(r"start", enc, re.I):
                stop = "stop" + enc[5:]
                for vm in re.finditer(r"addEventListener\(\s*['\"]visibilitychange['\"]", code):
                    blk = code[vm.end(): vm.end() + 600]
                    if re.search(r"\b" + re.escape(stop) + r"\s*\(", blk):
                        how = f"{enc}/{stop} on visibilitychange"
                        break
        out.append({"file": name, "line": line, "cb": cb[:80], "how": how})
    return out


def check(texts: dict[str, str] | None = None) -> tuple[list[str], list[dict]]:
    if texts is None:
        texts = {p.relative_to(ROOT).as_posix(): p.read_text(encoding="utf-8", errors="replace") for p in served_files()}
    issues, seen = [], []
    for name, raw in sorted(texts.items()):
        for r in refreshers(name, raw):
            seen.append(r)
            if not r["how"]:
                issues.append(f"H1 {name}:{r['line']} setInterval({r['cb']}) reaches the network on every tick and keeps "
                              "going in a hidden tab - read document.hidden first, run it through whPoll, stop it on "
                              "visibilitychange, or say above it why it must run hidden (refresh-hidden: ...)")
    # H2: the TICK of each helper reads document.hidden (whPoll's refocus handler reads it too, so the whole body proves
    # nothing): whPoll's inner tick(), whLivePoll's interval callback
    u = blank_comments(texts.get("utils.js", ""))
    for helper in ("whPoll", "whLivePoll"):
        b = fn_body(u, helper)
        if helper == "whPoll":
            t = fn_body(b, "tick") if b else ""
        else:
            si = re.search(r"\bsetInterval\s*\(", b or "")
            t = first_arg(b, si.end() - 1) if si else ""
        if not t or not HIDDEN.search(t):
            issues.append(f"H2 utils.js {helper}'s tick no longer skips a hidden tab - every page that polls through it "
                          "refreshes for nobody")
    return issues, seen


def self_test() -> list[str]:
    fails = []
    texts = {p.relative_to(ROOT).as_posix(): p.read_text(encoding="utf-8", errors="replace") for p in served_files()}
    clean, seen = check(dict(texts))
    if clean:
        fails.append(f"the clean run is not green: {clean[:3]}")
    if len(seen) < 5:
        fails.append(f"only {len(seen)} network refreshers found - the classifier collapsed")

    def mut(label: str, changes: dict[str, str], want: str) -> None:
        t = dict(texts); t.update(changes)
        got, _ = check(t)
        if not any(g.startswith(want) for g in got):
            fails.append(f"mutant '{label}' was not caught (got {got[:2]})")

    pa = texts["platform-actions.html"]
    mut("platform-actions back on a bare interval", {"platform-actions.html": pa.replace(
        "const _refreshPoll = whPoll(refreshQueues, 60000, { immediate: false });", "const _refreshPoll = { stop() {} }; setInterval(refreshQueues, 60000);", 1)}, "H1")
    mut("the live-job map polling a hidden tab", {"marketplace.html": texts["marketplace.html"].replace(
        "setInterval(() => { if (!document.hidden) tick(); }, 10000);", "setInterval(tick, 10000);", 1)}, "H1")
    mut("founder-console's auto-refresh for nobody", {"founder-console.html": texts["founder-console.html"].replace(
        "setInterval(() => { if (!document.hidden) refreshAll(); }, secs * 1000);", "setInterval(() => refreshAll(), secs * 1000);", 1)}, "H1")
    ah = texts["alert-hub.html"]
    mut("alert-hub's stop taken off visibilitychange", {"alert-hub.html": re.sub(r"\bstopRefresh\s*\(\s*\)", "void 0", ah)}, "H1")
    mut("whPoll no longer skipping a hidden tab", {"utils.js": texts["utils.js"].replace(
        "if (typeof document !== 'undefined' && document.hidden) return;  // skip while backgrounded", "", 1)}, "H2")
    mut("a new page polling the database", {"synthetic-poll.html": "<script>setInterval(() => { db.from('logbook').select('*'); }, 30000);</script>"}, "H1")
    mut("a reason removed from a declared one", {k: v.replace(EXEMPT, "note:") for k, v in texts.items() if EXEMPT in v}, "H1")
    return fails


def main() -> int:
    if "--self-test" in sys.argv:
        fails = self_test()
        print("SELF-TEST PASS (7 mutants caught; the clean run is green)" if not fails else "SELF-TEST FAIL\n  " + "\n  ".join(fails))
        return 1 if fails else 0
    issues, seen = check()
    print("Refresh stands down when hidden (SL LB4): a page refreshes on a bounded cadence, and never for nobody")
    if "--list" in sys.argv:
        for r in seen:
            print(f"  {r['file']}:{r['line']}  setInterval({r['cb']})  ->  {r['how'] or 'KEEPS GOING HIDDEN'}")
    for i in issues[:40]:
        print("  [FAIL] " + i)
    print(f"  PASS - {len(seen)} network refreshers on the served pages and shared scripts; each stands down while the tab "
          f"is hidden or says why it must not" if not issues else f"  FAIL - {len(issues)} problem(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
