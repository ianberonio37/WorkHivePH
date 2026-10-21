"""validate_ai_spend_in_budget.py - what a page spends on AI and functions is charged to a budget before it is spent, and
the page says when the budget is gone (SL RL1, 2026-10-22).

Surveyed from the 31 RL1 pages outward (tools/lib/js_reach.py, every function a page or a shared script it loads calls,
read against supabase/functions/<fn>/index.ts):
  * gcash-receipt-ocr - the receipt reader the marketplace pages offer, a paid Azure Document Intelligence call - had no
    limiter at all and verify_jwt accepts the publishable key: any client could send receipt after receipt on the
    platform's account. It escaped tools/validate_ai_rate_limit_coverage.py because that gate's model markers know the
    LLM and speech chains and not OCR. Now bounded per person (or IP) like equipment-label-ocr, whose pipeline it
    mirrors.
  * export-hive-data - the heaviest read on the platform, every table a hive owns in one payload - was the one function
    hive.html calls that no hive allowance counted; it ran as often as the button was pressed. Now on the hive's
    per-route allowance (hive_route_quotas), keyed on the hive the caller is proven a supervisor of.
  * the pages that say nothing when the allowance is gone: marketplace's AI triage read a refusal as "No suggestion this
    time"; the receipt reader said "Could not read the receipt"; hive's export and integrations' sync answered through
    the save sentence, which cannot read a function's own words (hive's export would have said "nothing was saved").

STATIC  B1 every edge function a served page or shared script CALLS (functions.invoke('fn'), or a fetch whose URL is
           built from '/functions/v1/fn' in the same call) charges a budget before it spends: its index.ts asks a
           limiter (checkAIRateLimit / checkUserRateLimit / checkSoloRateLimit / checkRouteRateLimit /
           checkClassedRateLimit / its own counter over ai_rate_limits), or it is in BUDGET_EXEMPT with why - and a
           function that reaches a paid model (an LLM, speech, OCR or embedding service) can never be exempt;
        B2 every call site of a budgeted function says when the budget is spent: the function that makes the call reads
           the refusal in the function's own words (whFnError, whAiError, the response's .context, a page reader of it,
           or an inline 429 / limit test) - or the call is fire-and-forget (nothing awaits it, its failure is only
           logged), or it is in QUIET_OK with why (a fallback that gives the person the same thing).
EXCLUDED, and why: a function URL a page only SHOWS (integrations.html prints each sync config's webhook address for the
CMMS to call; the page never calls it); functions only other functions call (ai-gateway's specialists are charged at the
gateway - tools/validate_ai_rate_limit_coverage.py holds that half); whether a limiter is keyed right
(tools/validate_rate_limit_key_is_verified.py) and whether its refusal says when (tools/validate_limit_says_when.py).
SELF-TEST (--self-test): each rule broken in a copy, each caught; the clean run is green.

    python tools/validate_ai_spend_in_budget.py [--self-test] [--list]
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
sys.path.insert(0, str(ROOT / "tools"))
from lib import js_reach as jr  # noqa: E402

FUNCS = ROOT / "supabase" / "functions"
LIMITER = re.compile(r"\b(?:checkAIRateLimit|checkUserRateLimit|checkSoloRateLimit|checkRouteRateLimit|"
                     r"checkClassedRateLimit)\s*\(|\bcheckRateLimit\s*\(|\bai_rate_limits\b")
# a paid model: the LLM and speech chains, the embedding chain, a direct provider call, the OCR service
MODEL = re.compile(r"\bcallAI\w*\s*\(|\bcallGroq\w*\s*\(|ai-chain\.ts|audio-chain\.ts|embedding-chain\.ts|"
                   r"\btranscribeAudio\s*\(|generativelanguage\.googleapis|api\.groq\.com|api\.openai\.com|"
                   r"api\.anthropic\.com|AZURE_DOC_INTELLIGENCE|documentintelligence|elevenlabs", re.I)
# a function that charges no budget of its own, and why that is right for it (never one that reaches a model)
BUDGET_EXEMPT = {
    "login": "a sign-in reaches no model; its own lockout (5 failed tries per identifier and IP in 15 minutes) is the "
             "limit a sign-in needs, and it says how long (index.html reads retry_after_seconds)",
}
# a call site whose refusal the person never waits on, and why that is right for it
QUIET_OK = {
    ("project-manager.html", "fetchProgressRollup"): "a refusal falls back to the same rollup computed in the page "
                                                     "(clientRollup) - the person gets the figures either way",
    ("logbook.html", "embedFaultEntry"): "indexes an entry for search after its save landed - nobody waits on it",
    ("pm-scheduler.html", "embedPMEntry"): "indexes a completion for search after its save landed - nobody waits on it",
    ("skillmatrix.html", "embedSkillEntry"): "indexes a result for search after its save landed - nobody waits on it",
    ("wh-tts.js", "speakAzure"): "a refusal falls back to the browser's own voice - the words are still spoken",
    ("voice-journal.html", "speakAzure"): "a refusal falls back to the browser's own voice - the words are still spoken",
    ("voice-handler.js", "_invokePlatformScraper"): "context for a voice answer: a refusal falls back to the hive's own "
                                                    "reads, and the answer (whose own call speaks its limit) still comes",
    ("voice-handler.js", "_invokeRAGAgent"): "context for a voice answer: a refusal falls back to the recent journal, "
                                             "and the answer (whose own call speaks its limit) still comes",
}
# the call's refusal read in the function's own words: the shared readers, the response's .context, a page's reader of
# it, an inline 429 / limit test, or a failed response's body read for its .error
SPEAK = re.compile(r"\bwhFnError\s*\(|\bwhAiError\s*\(|\.context\b|\b_fnErrorReason\s*\(|\b429\b|rate.?limit|"
                   r"limit reached|call limit|__whGatewayFailure|!\s*[\w$]+\.ok\b[\s\S]{0,400}?\.error\b")
NOT_SERVED = re.compile(r"_battery\.js$|^survey_")   # QA harnesses in the root that no page loads
CALL = re.compile(r"\.invoke\(\s*['\"`]([a-z0-9-]+)['\"`]")
URL = re.compile(r"/functions/v1/([a-z0-9-]+)")
FETCHY = re.compile(r"(?<![\w$.])(?:fetch|fetcher|fetchWithTimeout|whFetch\w*|window\.fetch)\s*\(")


def fn_sources() -> dict[str, str]:
    return {d.name: (d / "index.ts").read_text(encoding="utf-8", errors="replace")
            for d in sorted(FUNCS.iterdir()) if d.is_dir() and not d.name.startswith("_") and (d / "index.ts").exists()}


def innermost_body(code: str, at: int) -> str | None:
    """the body of the innermost function around `at` - a declaration, or an arrow / function literal (a click handler
    has no name, and its catch is where the refusal is read)"""
    best = None
    for m in re.finditer(r"=>\s*\{|\bfunction\b\s*\*?\s*[\w$]*\s*\(", code[:at]):
        if m.group(0).startswith("=>"):
            k = m.end() - 1
        else:
            p = code.find("(", m.start())
            k = code.find("{", jr.match(code, p))
        if 0 <= k < at and jr.match(code, k) > at and (best is None or k > best):
            best = k
    return code[best:jr.match(code, best) + 1] if best is not None else None


def call_sites(name: str, raw: str) -> list[dict]:
    """every place this file calls an edge function: an invoke, or a fetch-family call whose own arguments build the
    function's URL (a URL in a template the page only shows is not a call)"""
    code = jr.js_view(name, raw)
    out = []
    for m in CALL.finditer(code):
        out.append({"fn": m.group(1), "at": m.start(), "how": "invoke"})
    for f in FETCHY.finditer(code):
        open_i = code.find("(", f.end() - 1)
        args = code[open_i:jr.match(code, open_i) + 1]
        first = jr.first_args(code, open_i)[:1]
        u = URL.search(first[0]) if first else None
        if not u:
            # the URL built a line before: `var url = ... + '/functions/v1/x'` then fetch(url, ...)
            nm = re.fullmatch(r"\s*([A-Za-z_$][\w$]*)\s*", first[0]) if first else None
            if nm:
                d = re.search(r"\b(?:var|let|const)\s+" + re.escape(nm.group(1)) + r"\s*=\s*([^;\n]+)",
                              code[max(0, f.start() - 1500):f.start()])
                u = URL.search(d.group(1)) if d else None
        if u and args:
            out.append({"fn": u.group(1), "at": f.start(), "how": "fetch"})
    for s in out:
        s["file"], s["line"] = name, jr.line_of(code, s["at"])
        s["enc"] = jr.enclosing_fn(code, s["at"])
        s["body"] = innermost_body(code, s["at"]) or code[s["at"]:s["at"] + 2500]
        before = code[max(0, s["at"] - 120):s["at"]]
        after = code[s["at"]:s["at"] + 700]
        # fire-and-forget: nothing awaits it, and what follows it only logs
        s["fire_and_forget"] = (not re.search(r"\bawait\s+(?:[\w$.]+\s*)?$", before.split(";")[-1].split("\n")[-1] + " ")
                                and not re.search(r"=\s*(?:await\s+)?[\w$.()\s]*$", before.split(";")[-1])
                                and bool(re.search(r"\)\s*\.(?:then|catch)\s*\(", after))
                                and not re.search(r"show|toast|textContent|innerHTML|alert\(", after[:400], re.I))
    return out


def check(texts: dict[str, str], fns: dict[str, str]) -> tuple[list[str], dict]:
    issues, seen_fns, sites = [], {}, []
    for name, raw in sorted(texts.items()):
        for s in call_sites(name, raw):
            sites.append(s)
            seen_fns.setdefault(s["fn"], set()).add(name)
    for fn, where in sorted(seen_fns.items()):
        src = fns.get(fn)
        if src is None:
            continue                                   # no such function here (a health ping, a retired one)
        body = jr.strip_comments(src)
        limited, model = bool(LIMITER.search(body)), bool(MODEL.search(body))
        if limited:
            continue
        if fn in BUDGET_EXEMPT and not model:
            continue
        what = "reaches a paid model with no budget" if model else "is charged to no budget"
        issues.append(f"B1 {fn} {what} - {', '.join(sorted(where))} call{'s' if len(where) == 1 else ''} it; ask the "
                      "hive's limiter (or the person's, for a caller with no hive) before it spends")
    for s in sites:
        src = fns.get(s["fn"])
        if src is None or not LIMITER.search(jr.strip_comments(src)):
            continue
        if s["fire_and_forget"] or (s["file"], s["enc"]) in QUIET_OK:
            continue
        if SPEAK.search(s["body"]):
            continue
        issues.append(f"B2 {s['file']}:{s['line']} calls {s['fn']} (in {s['enc'] or 'top level'}) and reads no refusal in "
                      "the function's words - when the budget is spent the person is not told, or not told when it "
                      "clears; read it through whFnError (or the response's .context)")
    return issues, {"fns": seen_fns, "sites": sites}


def load() -> tuple[dict, dict]:
    return ({jr.rel(p): p.read_text(encoding="utf-8", errors="replace") for p in jr.served_files()
             if not NOT_SERVED.search(p.name)}, fn_sources())


def self_test() -> list[str]:
    fails = []
    texts, fns = load()
    clean, info = check(texts, fns)
    if clean:
        fails.append(f"the clean run is not green: {clean[:3]}")
    if len(info["fns"]) < 25 or len(info["sites"]) < 40:
        fails.append(f"only {len(info['fns'])} functions and {len(info['sites'])} call sites read - the reader collapsed")

    def mut(label: str, want: str, texts_=None, fns_=None) -> None:
        for k, v in list((texts_ or {}).items()) + list((fns_ or {}).items()):
            src = texts.get(k) if k in texts else fns.get(k)
            if src is not None and v == src:
                fails.append(f"mutant '{label}' changed nothing in {k} (its anchor moved)")
                return
        t = dict(texts); t.update(texts_ or {})
        f = dict(fns); f.update(fns_ or {})
        got, _ = check(t, f)
        keys = list((texts_ or {}).keys()) + list((fns_ or {}).keys())
        if not any(g.startswith(want) and any(k in g for k in keys) for g in got):
            fails.append(f"mutant '{label}' was not caught (got {got[:2]})")

    g = fns["gcash-receipt-ocr"]
    mut("the receipt reader spending with no budget again", "B1", fns_={"gcash-receipt-ocr": re.sub(
        r"const _rl = await checkSoloRateLimit\([^;]*;", "const _rl = { allowed: true };", g, count=1)})
    e = fns["export-hive-data"]
    mut("the hive export counted by nothing again", "B1", fns_={"export-hive-data": re.sub(
        r"const _rq = await checkRouteRateLimit\([^;]*;", "const _rq = { allowed: true };", e, count=1)})
    mut("a sign-in exemption stretched over a model call", "B1", fns_={"login": fns["login"] + "\nconst _m = await callAI('x');\n"})
    mut("a new page calling an unbudgeted function", "B1", texts_={"synthetic-spend.html": (
        "<script>async function go() { const { error } = await db.functions.invoke('cold-archive-query', { body: {} }); "
        "if (error) showToast(whFnError(error)); }</script>")})
    mk = texts["marketplace.html"]
    mut("the AI triage reading a spent allowance as 'no suggestion'", "B2", texts_={"marketplace.html": mk.replace(
        "      if (resp.error) {\n        const said = typeof whFnError === 'function'\n          ? await whFnError(resp.error, 'The AI could not suggest anything just now.')\n          : 'The AI could not suggest anything just now.';\n        if (out) out.textContent = said + ' Pick the fields yourself.';\n        return;\n      }\n",
        "", 1)})
    ut = texts["utils.js"]
    mut("the receipt reader saying only 'could not read'", "B2", texts_={"utils.js": ut.replace(
        "    var _st = error.context && error.context.status;\n    if ((_st === 429 || _st === 503) && typeof whFnError === 'function') {\n      throw new Error(await whFnError(error, 'The receipt reader is at its limit right now.') + ' You can type the details, or paste the receipt text.');\n    }\n",
        "", 1)})
    ig = texts["integrations.html"]
    mut("the sync answered through the save sentence again", "B2", texts_={"integrations.html": re.sub(
        r"showToast\(typeof whFnError === 'function' \? await whFnError\(error, (_t\('The sync did not start[^;]*?\)\)) : whWriteError\(error, _t\('The sync did not start[^;]*?\)\)\); return; \}",
        r"showToast(whWriteError(error, \1); return; }", ig, count=1).replace(
        "the function's own sentence, which only whFnError reads off the response", "the function's own sentence", 1)})
    return fails


def main() -> int:
    if "--self-test" in sys.argv:
        fails = self_test()
        print("SELF-TEST PASS (7 mutants caught; the clean run is green)" if not fails else "SELF-TEST FAIL\n  " + "\n  ".join(fails))
        return 1 if fails else 0
    texts, fns = load()
    issues, info = check(texts, fns)
    print("AI and function spend in budget (SL RL1): charged before it is spent, and the page says when it is gone")
    if "--list" in sys.argv:
        for fn, where in sorted(info["fns"].items()):
            src = fns.get(fn)
            tag = ("no such function" if src is None else "limited" if LIMITER.search(jr.strip_comments(src))
                   else f"exempt: {BUDGET_EXEMPT[fn][:60]}" if fn in BUDGET_EXEMPT else "NO BUDGET")
            print(f"  {fn}: {tag}  <- {', '.join(sorted(where))[:120]}")
    for i in issues[:40]:
        print("  [FAIL] " + i)
    print(f"  PASS - {len(info['fns'])} functions the pages call, each charged to a budget or exempt with why; "
          f"{len(info['sites'])} call sites, each saying when the budget is spent, fire-and-forget, or quiet with why"
          if not issues else f"  FAIL - {len(issues)} problem(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
