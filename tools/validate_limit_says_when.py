"""validate_limit_says_when.py - a limit tells a person, in one sentence, that it was hit and when to try again (SL RL2,
2026-10-22).

Surveyed on the 24 RL2 pages and the shared scripts they load, from the limit outward:
  * utils.js whWriteError - the sentence most saves on the platform are answered with - knew the deliberate refusal
    codes (23514, P0001, 42501) and not the codes the platform's own LIMITS refuse with: 54000 (the daily caps on 31
    tables, the logbook's own limit, the five hive quotas) and 23P01 (the feedback limit); a gateway's 429 met the
    same fate. Each reached the person as the caller's "That did not go through. Please try again." - no limit named,
    and the one remedy that cannot work until it clears. Measured against the pre-fix file: 6 of 20 limit shapes.
  * the database's own sentences: the listing limit, the AI-answer rating limit and the review limit said a limit was
    reached and never when; the feedback limit said "later" and read the account id back to a signed-in person; the
    five hive quotas answered with a table name, a hive id and two counts.
  * report-sender and shift-brain (three places) answered a limit with a stand-in 429 - "Wait a moment" - throwing
    away the function's own "Try again in about 40 minutes"; shift-brain's first open, handed supabase-js's
    placeholder, said "Something went wrong" on the branch that knew a limit was hit.
  * the AI answers' "was this right?" row answered every refusal, its daily limit included, "Not recorded - try
    again"; the feedback button told a visitor who had sent nothing "You've already sent 5 messages this hour";
    marketplace's hire-request helper said "Something went wrong" to a daily cap; index's sign-in lockout said "Try
    again later" beside the server's retry_after_seconds.

STATIC  L1 the four sentence makers, called for real (tools/test_limit_says_when.mjs, utils.js in a DOM-less shim):
           every limit shape - a daily cap, a quota (both wordings), the feedback limit, the listing, review and rating
           limits, posting too fast, a gateway 429 (with and without a window), a read's 429, the AI limit (with and
           without a window), a function's hour / per-person / day-budget / could-not-count refusals - is ONE sentence
           naming the limit and when it clears; an exclusion constraint and Postgres's own program limit fall through;
        L2 every limit the database raises (a RAISE EXCEPTION with code 54000 or 23P01, or worded as a rate, daily,
           hourly or quota limit, or as too fast / too many) says when it clears - a time, midnight, tomorrow, a wait,
           or a quota's archive-or-raise remedy - read from the newest definition of each function in
           supabase/migrations, and from the LOCAL database's pg_proc when it answers;
        L3 the shared chrome speaks the limit: whAiTrustRow's failure note reads the refusal through a sentence maker;
           the feedback button reads the trigger's own sentence before its stock one; the companion (29 pages) shows the
           gateway's own limit sentence - whose limit, and when - before any stock line (it said "You've used up your
           AI questions for this hour. Try again in a little while - your teammates aren't affected" to a HIVE whose
           allowance was spent, with "about 12 minutes" in the sentence it threw away);
        L4 no page answers a limit with a stand-in: whAiError({ message: '429' }) never appears (the error itself, or
           whFnError on it, carries the window);
        L5 every list of refusal codes that speak for themselves (one naming 23514 and P0001) lets a limit speak too:
           its function handles 54000;
        L6 index's sign-in lockout (423) reads the proxy's retry_after_seconds;
        L7 every edge refusal for a limit is handed its window: each call of rateLimitedResponse / userRateLimitedResponse
           / routeRateLimitedResponse / soloRateLimitedResponse in supabase/functions passes the limiter's
           retry_after_seconds.
EXCLUDED, and why: a size limit with a remedy and no clock (the PDF chunk ceiling: "Split the document") is not a
"try again" limit; a limit refusal a page shows by the error's own message is held at its source (L2), not per page.
SELF-TEST (--self-test): each rule broken in a copy, each caught; the clean run is green.

    python tools/validate_limit_says_when.py [--self-test] [--list]
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from lib import js_reach as jr  # noqa: E402

DB = "supabase_db_workhive"
MIG = ROOT / "supabase" / "migrations"
FUNCS = ROOT / "supabase" / "functions"
HARNESS = ROOT / "tools" / "test_limit_says_when.mjs"
LIMIT_WORDS = re.compile(r"\b(?:rate limit|limit of|limit reached|free limit|daily [\w ]{0,30}limit|hourly [\w ]{0,20}"
                         r"(?:limit|ceiling)|too fast|too many|quota)\b", re.I)
# WHEN it clears - not the limit's own rate ("5 per hour" says how much, not when) and not "later" or "shortly", which a
# person cannot act on: a clock time, a day boundary, a wait in numbers, or a quota's archive-or-raise remedy
WHEN_WORDS = re.compile(r"\b(?:midnight|tomorrow|in about|in \d+|a few seconds|wait a few|resets? at|archive)\b", re.I)
RAISE = re.compile(r"RAISE\s+EXCEPTION\s+'((?:[^']|'')*)'([^;]*);", re.I | re.S)
FUNC_DEF = re.compile(r"create\s+(?:or\s+replace\s+)?function\s+(?:public\.)?\"?([a-z_][a-z0-9_]*)\"?\s*\(", re.I)
BUILDERS = ("rateLimitedResponse", "userRateLimitedResponse", "routeRateLimitedResponse", "soloRateLimitedResponse")


# ── L2: the database's limit sentences ─────────────────────────────────────────────────────────────────────────────
def latest_definitions(files: dict[str, str]) -> dict[str, tuple[str, str]]:
    """function name -> (migration file, body) for the newest definition in the migrations, in file order"""
    out: dict[str, tuple[str, str]] = {}
    for name in sorted(files):
        src = files[name]
        for m in FUNC_DEF.finditer(src):
            tag = re.search(r"\bAS\s+(\$[A-Za-z_]*\$)", src[m.end():m.end() + 4000], re.I)
            if not tag:
                continue
            s = m.end() + tag.end()
            e = src.find(tag.group(1), s)
            if e < 0:
                continue
            out[m.group(1).lower()] = (name, src[s:e])
    return out


SIZE_LIMIT = re.compile(r"\btoo large\b|\bexceeds the\b[^.]*\blimit\b|\bbytes\b", re.I)


def limit_raises(body: str) -> list[tuple[str, str]]:
    """the RAISE EXCEPTIONs in a body that refuse for a limit that clears with time: (message, the rest of the statement).
    A SIZE limit (a PDF past its chunk ceiling, an image past its byte cap) is 54000 too, but nothing about it clears
    by waiting - its remedy is a smaller thing to send - so it is not held to saying when."""
    out = []
    for m in RAISE.finditer(body):
        msg, rest = m.group(1).replace("''", "'"), m.group(2)
        code = re.search(r"ERRCODE\s*=\s*'([^']+)'", rest, re.I)
        if SIZE_LIMIT.search(msg):
            continue
        if (code and code.group(1) in ("54000", "23P01")) or LIMIT_WORDS.search(msg):
            out.append((msg, rest))
    return out


def says_when(msg: str, rest: str) -> bool:
    if WHEN_WORDS.search(msg):
        return True
    return "%" in msg and bool(re.search(r"\bv_when\b", rest))


def check_db_static(files: dict[str, str]) -> tuple[list[str], int]:
    issues, n = [], 0
    for fn, (fname, body) in sorted(latest_definitions(files).items()):
        for msg, rest in limit_raises(body):
            n += 1
            if not says_when(msg, rest):
                issues.append(f"L2 {fn} ({fname}) refuses for a limit without saying when it clears: '{msg[:110]}'")
    return issues, n


def check_db_live(names: set[str]) -> tuple[list[str], str]:
    """the same rule over the LOCAL database's pg_proc - the definitions the platform actually runs"""
    sql = ("select p.proname || chr(31) || p.prosrc from pg_proc p join pg_namespace n on n.oid = p.pronamespace "
           "where n.nspname = 'public' and p.prosrc ~* 'raise exception';")
    try:
        r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-At", "-R", chr(30), "-c", sql],
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        return [], f"the local database did not answer ({e}) - the live half was not read"
    if r.returncode != 0:
        return [], f"the local database did not answer ({(r.stderr or '').strip()[:120]}) - the live half was not read"
    issues = []
    for rec in r.stdout.split(chr(30)):
        if chr(31) not in rec:
            continue
        fn, src = rec.split(chr(31), 1)
        for msg, rest in limit_raises(src):
            if not says_when(msg, rest):
                issues.append(f"L2 {fn.strip()} (LIVE local database) refuses for a limit without saying when it clears: "
                              f"'{msg[:110]}' - apply the newest migrations")
    return issues, ""


# ── L1: the sentence makers, called for real ──────────────────────────────────────────────────────────────────────
L1_SHAPES = {"n": None}   # how many limit shapes the harness asked about, read from its own PASS line


def check_makers(utils_src: str | None = None) -> list[str]:
    path, tmp = ROOT / "utils.js", None
    if utils_src is not None:
        fd, name = tempfile.mkstemp(suffix=".js", dir=str(ROOT / ".tmp"))
        with open(fd, "w", encoding="utf-8") as fh:
            fh.write(utils_src)
        path = tmp = Path(name)
    try:
        r = subprocess.run(["node", str(HARNESS), str(path)], capture_output=True, text=True, encoding="utf-8",
                           timeout=120, cwd=str(ROOT))
        if r.returncode != 0:
            bad = [ln[5:] for ln in (r.stdout or "").splitlines() if ln.startswith("FAIL ")]
            return ["L1 a limit no longer reaches a person as a sentence naming it and when it clears: "
                    + ("; ".join(bad[:3]) or (r.stderr or r.stdout).strip()[-200:])]
        m = re.search(r"PASS limit-says-when - (\d+) limit shapes", r.stdout or "")
        if utils_src is None and m:
            L1_SHAPES["n"] = int(m.group(1))
        return []
    except (OSError, subprocess.TimeoutExpired) as e:
        return [f"L1 could not run tools/test_limit_says_when.mjs: {e}"]
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()


# ── L3-L6: the pages and the shared chrome ─────────────────────────────────────────────────────────────────────────
def check_chrome(utils: str, fab: str) -> list[str]:
    issues = []
    u = jr.js_view("utils.js", utils)
    row = jr.fn_body(u, "whAiTrustRow") or ""
    # the branch a refused rating takes: the one that hands the buttons back (disabled = false), and what it says
    fail = re.search(r"\}\s*else\s*\{[\s\S]{0,300}?disabled\s*=\s*false[\s\S]{0,900}?note\.textContent\s*=([^;]+);", row)
    if not fail or not re.search(r"\bwh(?:Write|Read)Error\s*\(", fail.group(1)):
        issues.append("L3 utils.js whAiTrustRow answers a refused rating with a fixed sentence - its daily limit reads "
                      "'Not recorded - try again'; read the refusal through whWriteError")
    f = jr.js_view("wh-feedback-fab.js", fab)
    br = re.search(r"\bif\s*\(\s*error\.code\s*===\s*'23P01'", f)
    blk = ""
    if br:
        cond_end = jr.match(f, f.find("(", br.start()))
        k = f.find("{", cond_end)
        blk = f[k:jr.match(f, k) + 1] if k >= 0 else ""
    if not br or not re.search(r"\berror\.message\b", blk):
        issues.append("L3 wh-feedback-fab.js answers every feedback limit with its stock sentence - a visitor who sent "
                      "nothing is told they sent five; read the trigger's own sentence first")
    return issues


def check_companion(src: str) -> list[str]:
    """L3: the companion (29 pages) shows the gateway's own limit sentence - whose limit, and when - before any stock line"""
    c = jr.js_view("companion-launcher.js", src)
    body = jr.fn_body(c, "handleSend") or ""
    stock = body.find("You've used up your AI questions")
    own = None
    for m in re.finditer(r"\bif\s*\(", body):
        cond = body[m.end():jr.match(body, m.end() - 1)]
        k = body.find("{", jr.match(body, m.end() - 1))
        blk = body[k:jr.match(body, k) + 1] if k >= 0 else ""
        if re.search(r"limit", cond) and re.search(r"(?:minutes?|hours?|tomorrow|try again in)", cond) and \
                re.search(r"friendly\s*=\s*'[^']*'\s*\+\s*m\s*;", blk):
            own = m.start()
            break
    if own is None or (stock >= 0 and own > stock):
        return ["L3 companion-launcher.js rewrites the gateway's limit sentence into a stock line before showing its own "
                "- a hive's spent allowance reads as the asker's, 'your teammates aren't affected', 'in a little while'; "
                "show the server's sentence when it names a limit and when"]
    return []


def check_pages(texts: dict[str, str]) -> list[str]:
    issues = []
    for name, raw in sorted(texts.items()):
        code = jr.js_view(name, raw)
        for m in re.finditer(r"\bwhAiError\(\s*\{\s*message\s*:\s*(['\"])429\1\s*\}\s*\)", code):
            issues.append(f"L4 {name}:{jr.line_of(code, m.start())} answers a limit with a stand-in 429 - the error's own "
                          "window is thrown away ('Wait a moment' to a limit with most of an hour to run); pass the "
                          "error itself (await whFnError(error, ...))")
        for m in re.finditer(r"===\s*'23514'[^;\n]{0,80}===\s*'P0001'|===\s*'P0001'[^;\n]{0,80}===\s*'23514'", code):
            enc = None
            for d in re.finditer(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(", code[:m.start()]):
                k = code.find("{", jr.match(code, code.find("(", d.end() - 1)))
                if 0 <= k < m.start() and jr.match(code, k) > m.start():
                    enc = (k, jr.match(code, k))
            body = code[enc[0]:enc[1]] if enc else code[max(0, m.start() - 1500):m.start() + 1500]
            if "'54000'" not in body:
                issues.append(f"L5 {name}:{jr.line_of(code, m.start())} lets a guard's sentence speak (23514 / P0001) "
                              "but not a limit's (54000) - a daily cap reads as a generic failure")
    ix = jr.js_view("index.html", texts.get("index.html", ""))
    lk = re.search(r"if\s*\(\s*_resp\.status\s*===\s*423\s*\)\s*\{", ix)
    if not lk or "retry_after_seconds" not in ix[lk.end():jr.match(ix, lk.end() - 1)]:
        issues.append("L6 index.html's sign-in lockout (423) says 'later' - the proxy sends retry_after_seconds; say "
                      "how long")
    return issues


def check_edge(fn_texts: dict[str, str]) -> tuple[list[str], int]:
    issues, n = [], 0
    for name, src in sorted(fn_texts.items()):
        code = jr.strip_comments(src)
        for b in BUILDERS:
            for m in re.finditer(r"(?<![\w$.])" + b + r"\s*\(", code):
                if re.search(r"function\s+$", code[max(0, m.start() - 12):m.start()]):
                    continue
                n += 1
                args = code[m.end():jr.match(code, m.end() - 1)]
                if "retry_after_seconds" not in args:
                    issues.append(f"L7 {name}:{jr.line_of(code, m.start())} {b}(...) is not handed the limiter's "
                                  "retry_after_seconds - the refusal cannot say when it clears")
    return issues, n


def load() -> tuple[dict, dict, dict]:
    pages = {jr.rel(p): p.read_text(encoding="utf-8", errors="replace") for p in jr.served_files()}
    migs = {p.name: p.read_text(encoding="utf-8", errors="replace") for p in sorted(MIG.glob("*.sql"))}
    fns = {p.relative_to(ROOT).as_posix(): p.read_text(encoding="utf-8", errors="replace")
           for p in sorted(FUNCS.glob("*/index.ts"))}
    return pages, migs, fns


def check(pages: dict, migs: dict, fns: dict, live: bool = True, utils_mutant: str | None = None) -> tuple[list[str], dict]:
    issues, info = [], {}
    issues += check_makers(utils_mutant)
    db_issues, info["db_limits"] = check_db_static(migs)
    issues += db_issues
    if live:
        live_issues, info["live_note"] = check_db_live(set())
        issues += live_issues
    issues += check_chrome(pages.get("utils.js", ""), pages.get("wh-feedback-fab.js", ""))
    issues += check_companion(pages.get("companion-launcher.js", ""))
    issues += check_pages(pages)
    edge_issues, info["edge_calls"] = check_edge(fns)
    issues += edge_issues
    return issues, info


def self_test() -> list[str]:
    fails = []
    pages, migs, fns = load()
    clean, info = check(pages, migs, fns, live=False)
    if clean:
        fails.append(f"the clean run is not green: {clean[:3]}")
    if info["db_limits"] < 12 or info["edge_calls"] < 30:
        fails.append(f"only {info['db_limits']} database limits and {info['edge_calls']} edge refusals read - the reader collapsed")

    def mut(label: str, want: str, pages_=None, migs_=None, fns_=None, utils_src=None) -> None:
        p = dict(pages); p.update(pages_ or {})
        mg = dict(migs); mg.update(migs_ or {})
        f = dict(fns); f.update(fns_ or {})
        for k, v in list((pages_ or {}).items()) + list((migs_ or {}).items()) + list((fns_ or {}).items()):
            src = pages.get(k) if k in pages else migs.get(k) if k in migs else fns.get(k)
            if src is not None and v == src:
                fails.append(f"mutant '{label}' changed nothing in {k} (its anchor moved)")
                return
        got, _ = check(p, mg, f, live=False, utils_mutant=utils_src)
        if not any(g.startswith(want) for g in got):
            fails.append(f"mutant '{label}' was not caught (got {got[:2]})")

    ut = pages["utils.js"]
    mut("whWriteError forgetting the limit codes", "L1", utils_src=ut.replace(
        "if (code === '54000' || (code === '23P01' && /limit/i.test(msg))) {", "if (false) {", 1))
    mut("whWriteError forgetting a gateway's 429", "L1", utils_src=ut.replace(
        "if (code === '429' || _st === '429' || /\\brate.?limit|too many requests/i.test(msg)) {", "if (false) {", 1))
    # SL RL2 walk (2026-10-22): the two sentence makers the walk added - a role wall and an access gate under a limit
    mut("the role wall's note ignoring the read's error", "L1", utils_src=ut.replace(
        "var why = err ? whReadError(err, 'your role') : 'Your role could not be checked just now.';",
        "var why = 'Your role could not be checked just now.';", 1))
    mut("the access gate telling a limit to reload", "L1", utils_src=ut.replace(
        "    : (e && whIsRateLimited(e))\n", "    : (false)\n", 1))
    newest = sorted(migs)[-1]
    mut("the listing limit worded without its when again", "L2", migs_={"99999999999999_mutant.sql": (
        "CREATE OR REPLACE FUNCTION public.check_listing_rate() RETURNS trigger LANGUAGE plpgsql AS $function$\n"
        "BEGIN IF 1 = 1 THEN RAISE EXCEPTION 'Daily listing limit of 20 reached'; END IF; RETURN NEW; END;\n$function$;")})
    mut("a hive quota answering with a table and a hive id again", "L2", migs_={"99999999999999_mutant.sql": (
        "CREATE OR REPLACE FUNCTION public.check_hive_quota_logbook() RETURNS trigger LANGUAGE plpgsql AS $function$\n"
        "BEGIN RAISE EXCEPTION 'logbook cumulative quota exceeded for hive % (% >= %)', NEW.hive_id, 1, 1 "
        "USING ERRCODE = '54000'; RETURN NEW; END;\n$function$;")})
    mut("the rating row's fixed 'try again'", "L3", pages_={"utils.js": ut.replace(
        "note.textContent = (refused && typeof whWriteError === 'function')\n          ? whWriteError(refused, _t('Not recorded - try again.', 'Hindi naitala - subukan muli.'))\n          : _t(",
        "note.textContent = (false)\n          ? null\n          : _t(", 1)})
    fab = pages["wh-feedback-fab.js"]
    mut("the feedback button's stock sentence for every limit", "L3", pages_={"wh-feedback-fab.js": re.sub(
        r"const said = String\(error\.message \|\| ''\);[\s\S]*?: RATE_LIMIT_MSG\(\)\);", "setStatus('error', RATE_LIMIT_MSG());",
        fab, count=1)})
    cl = pages["companion-launcher.js"]
    mut("the companion's stock 'your teammates aren't affected' line first again", "L3", pages_={"companion-launcher.js": re.sub(
        r"if \(m && /\\b\(\?:limit\|budget\)\\b/i\.test\(m\)[\s\S]*?friendly = '⚠️ ' \+ m;\n      \} else if",
        "if (false) {\n      } else if", cl, count=1)})
    sb = pages["shift-brain.html"]
    mut("shift-brain's stand-in 429 put back", "L4", pages_={"shift-brain.html": sb.replace(
        "await window.whFnError(error, 'You have hit the AI rate limit.')", "window.whAiError({ message: '429' })", 1)})
    mk = pages["marketplace.html"]
    mut("marketplace's hire requests silencing a daily cap", "L5", pages_={"marketplace.html": mk.replace(
        "code === '23514' || code === 'P0001' || code === '54000'", "code === '23514' || code === 'P0001'", 1).replace(
        "under 54000, the code Postgres keeps for limits", "under the code Postgres keeps for limits", 1)})
    ix = pages["index.html"]
    mut("the sign-in lockout saying 'later' again", "L6", pages_={"index.html": ix.replace(
        "const _lockS = Number(_r.retry_after_seconds);", "const _lockS = 0;", 1)})
    fn0 = next(k for k, v in fns.items() if "soloRateLimitedResponse(corsHeaders, _rl.retry_after_seconds, _rl.scope)" in v)
    mut("an edge refusal not handed its window", "L7", fns_={fn0: fns[fn0].replace(
        "soloRateLimitedResponse(corsHeaders, _rl.retry_after_seconds, _rl.scope)",
        "soloRateLimitedResponse(corsHeaders, undefined, _rl.scope)", 1)})
    del newest
    return fails


def main() -> int:
    if "--self-test" in sys.argv:
        fails = self_test()
        print("SELF-TEST PASS (13 mutants caught; the clean run is green)" if not fails else "SELF-TEST FAIL\n  " + "\n  ".join(fails))
        return 1 if fails else 0
    pages, migs, fns = load()
    issues, info = check(pages, migs, fns)
    print("A limit says when (SL RL2): one sentence that a limit was hit and when to try again")
    if "--list" in sys.argv:
        for fn, (fname, body) in sorted(latest_definitions(migs).items()):
            for msg, _ in limit_raises(body):
                print(f"  {fn}: '{msg[:120]}'")
    if info.get("live_note"):
        print("  note: " + info["live_note"])
    for i in issues[:40]:
        print("  [FAIL] " + i)
    print(f"  PASS - {L1_SHAPES['n'] or '?'} limit shapes through the shared sentence makers; {info['db_limits']} database limits say when; the "
          f"shared chrome and the pages speak the limit; {info['edge_calls']} edge refusals are handed their window"
          if not issues else f"  FAIL - {len(issues)} problem(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
