#!/usr/bin/env python3
# DEEPWALK-CELL: ai:* D24
"""validate_rate_limit_key_is_verified.py - an AI rate limit must be keyed on the VERIFIED caller, in a column that can
hold that key, and a limiter that cannot count must refuse.

THE FINDING (LLM layer, live Grounding walk, LM120, 2026-10-07). voice-journal-agent keyed its solo limiter on
`body.auth_uid`. The ai-gateway never sends that field, so the key fell back to the request IP - and behind the gateway
that is the gateway's own container address. ai_user_rate_limits held "ip:172.18.0.2" at 30 calls an hour after the first
live walks: every person's companion questions on the platform drew on ONE bucket, and the companion answered "AI call
limit reached" to everyone at once. Three more functions (resume-extract, resume-polish, vehicle-doc-extract) took the
key from the body too, where any caller can name someone else's id and spend their bucket.

THE SECOND FINDING (2026-10-08, marketplace-listing-assist). For a seller with no hive the function passed the person's
AUTH UID to checkAIRateLimit, which wrote it into ai_rate_limits.hive_id - a column with a foreign key to hives. Every
upsert failed (23503), nobody read the error, no bucket row ever existed, and every call saw an empty bucket: the limit
did nothing for exactly the callers it was there for (its service_triage path did the same with a 20/hour cap).
checkUserRateLimit had the twin: it wrote hive_id "" for intelligence-report's and voice-semantic-rag's hive-less
callers (22P02 - "" is not a uuid), so their per-user bucket was never opened. And every limiter on the platform
discarded its read and write errors the same way, so ANY failed write meant an uncounted, admitted call.

RULES (baseline 0 each):
  K  KEY FROM THE BODY  the person argument of `soloRateLimitKey(<person>, <ip>)` is never a value read from the request
                        body; it comes from the verified JWT (resolveIdentity / auth.getUser) or is null (the IP floor).
  U  UID IN A HIVE KEY  the key a HIVE limiter writes - checkAIRateLimit / checkClassedRateLimit / checkRouteRateLimit /
                        checkUserRateLimit's hive argument, a function's own checkRateLimit, a `hive_id:` written to a
                        limiter table - is never something that can be a person's auth uid (ai_rate_limits,
                        ai_user_rate_limits, hive_route_calls and hive_route_quotas all key hive_id on hives(id)). A
                        hive-less person is limited per USER: checkSoloRateLimit(soloRateLimitKey(uid, ...)).
  N  "" IN A HIVE KEY   a `hive_id:` written to ai_user_rate_limits is null or `<x> || null` - never a bare value that
                        can be "" (a uuid column refuses it, and the bucket is never opened).
  E  ERROR IGNORED      every read and write of a limiter table captures its error and, when there is one, REFUSES
                        (allowed:false / "unavailable") - an unread bucket is not an empty one, and an unrecorded call is
                        one the limit can never see. Logging and carrying on is not refusing.
  Z  EMPTY HIVE KEY     a hive limiter (checkAIRateLimit / checkClassedRateLimit) is never handed `x || ""` or "": an empty
                        key returns "allowed" without counting anything, which is how ai-orchestrator,
                        analytics-orchestrator, project-orchestrator, voice-logbook-entry and voice-report-intent
                        served a caller with no hive - three of them with verify_jwt = false, to anyone - unmetered.
                        A caller with no hive goes to the per-person limiter; a trusted service-role path skips the
                        limiter explicitly. (checkUserRateLimit(db, "", uid) is the per-USER bucket alone - allowed.)
  H  HONEST REFUSAL     wherever a function asks a limiter (check*RateLimit / its own checkRateLimit), its refusal reads
                        the verdict's scope (or `unavailable`), so a limiter that could not count says so (503) instead
                        of claiming a limit the person never reached.

USAGE:      python tools/validate_rate_limit_key_is_verified.py
Self-test:  python tools/validate_rate_limit_key_is_verified.py --selftest   (also --self-test)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FUNCS = ROOT / "supabase" / "functions"
GREEN, RED = "\033[92m", "\033[91m"
RST = "\033[0m"

LIMITER_TABLES = ("ai_rate_limits", "ai_user_rate_limits", "hive_route_calls", "hive_route_quotas")
HIVE_LIMITERS = ("checkAIRateLimit", "checkClassedRateLimit", "checkRouteRateLimit", "checkUserRateLimit",
                 "checkRateLimit", "temporalCapReachedReadOnly")
ASK_LIMITERS = ("checkAIRateLimit", "checkSoloRateLimit", "checkUserRateLimit", "checkClassedRateLimit",
                "checkRouteRateLimit", "checkRateLimit")
# a value that can be a person's auth uid
UID_WORD = re.compile(r"\b(?:auth_?uid|uid|user_?id|actor_?uid|solo_?uid|solo_?rl_?uid|caller\.id|_?caller\.id|claims\.sub)\b",
                      re.I)


def _strip_comments(src: str) -> str:
    """Blank // and /* */ comments, KEEPING line breaks (rules E and H read line windows). Strings and URLs survive."""
    src = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), src, flags=re.S)
    return re.sub(r"(?m)(^|[^:\"'\\])//.*$", r"\1", src)


# ── K ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
def bad_keys(src: str) -> list[str]:
    """The person arguments of soloRateLimitKey(...) that are read from the request body."""
    s = _strip_comments(src)
    out = []
    for m in re.finditer(r"soloRateLimitKey\(\s*([^,]+?)\s*,", s):
        arg = m.group(1).strip()
        if re.search(r"\bbody\b", arg):
            out.append(arg)
            continue
        if re.fullmatch(r"[A-Za-z_$][\w$]*", arg):
            assign = re.search(r"(?:const|let|var)\s+" + re.escape(arg) + r"\s*=([^;]+);", s)
            if assign and re.search(r"\bbody\b|_whBody|\bpayload\b", assign.group(1)):
                out.append(f"{arg} (= {assign.group(1).strip()[:60]})")
    return out


# ── U / N ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _uidish(expr: str, s: str) -> str | None:
    """Why `expr` can be an auth uid (None when it cannot): it names one, or a variable it reads is ever assigned one."""
    if UID_WORD.search(expr):
        return expr.strip()
    for ident in set(re.findall(r"(?<![\w$.])[A-Za-z_$][\w$]*", expr)):
        if ident in ("db", "_db", "adminClient", "String", "null", "undefined"):
            continue
        for m in re.finditer(r"(?<![\w$.])" + re.escape(ident) + r"\s*(?::[^=;\n]+)?=(?![=>])\s*([^;\n]+)", s):
            if UID_WORD.search(m.group(1)):
                return f"{ident} (= {m.group(1).strip()[:60]})"
    return None


def _args(s: str, open_idx: int) -> list[str]:
    """Top-level comma-separated arguments of the call whose '(' is at open_idx."""
    depth, cur, out = 0, [], []
    for c in s[open_idx:]:
        if c in "([{":
            depth += 1
            if depth == 1:
                continue
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                out.append("".join(cur).strip())
                return out
        if c == "," and depth == 1:
            out.append("".join(cur).strip())
            cur = []
            continue
        cur.append(c)
    return out


def uid_hive_keys(src: str, defs: bool = False) -> list[str]:
    """U: a hive limiter keyed by something that can be an auth uid. N: a "" into ai_user_rate_limits.hive_id."""
    s = _strip_comments(src)
    out = []
    for m in re.finditer(r"(?<![\w$.])(" + "|".join(HIVE_LIMITERS) + r")\s*\(", s):
        before = s[max(0, m.start() - 30):m.start()]
        if re.search(r"function\s+$", before):
            continue  # the definition, not a call
        a = _args(s, m.end() - 1)
        if len(a) < 2:
            continue
        why = _uidish(a[1], s)
        if why:
            out.append(f"U {m.group(1)}(..., {why}) - a hive limiter keyed by a person's id")
    for m in re.finditer(r"""\.from\(\s*["'](""" + "|".join(LIMITER_TABLES) + r""")["']\s*\)\s*\.(upsert|insert|update)\s*\(""", s):
        payload = s[m.end() - 1:m.end() - 1 + 600]
        hv = re.search(r"\bhive_id\s*:\s*([^,\n}]+)", payload)
        if not hv:
            continue
        val = hv.group(1).strip()
        why = _uidish(val, s)
        if why:
            out.append(f"U {m.group(1)}.{m.group(2)}(hive_id: {why}) - a person's id written to a hive key")
        if m.group(1) == "ai_user_rate_limits" and val != "null" and "|| null" not in val and "?? null" not in val:
            out.append(f"N ai_user_rate_limits.{m.group(2)}(hive_id: {val}) - can be \"\", which a uuid column refuses "
                       f"(write `{val} || null`)")
    return out


# ── Z ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
def empty_hive_keys(src: str) -> list[str]:
    """Z: a hive limiter handed an empty-able key (`x || ""`, `x ?? ""`, a bare "")."""
    s = _strip_comments(src)
    out = []
    for m in re.finditer(r"(?<![\w$.])(checkAIRateLimit|checkClassedRateLimit)\s*\(", s):
        if re.search(r"function\s+$", s[max(0, m.start() - 30):m.start()]):
            continue
        a = _args(s, m.end() - 1)
        if len(a) >= 2 and re.search(r"""(\|\||\?\?)\s*(["'`])\2\s*$|^\s*(["'`])\3\s*$""", a[1]):
            line = s.count("\n", 0, m.start()) + 1
            out.append(f"Z line {line}: {m.group(1)}(db, {a[1]}) - an empty hive key admits without counting")
    return out


# ── E ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
def _branch(text: str, if_idx: int) -> str:
    """The statement an `if (...)` at if_idx guards: its { block }, or the single statement up to `;`."""
    open_paren = text.find("(", if_idx)
    depth = 0
    j = open_paren
    while j < len(text):
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                break
        j += 1
    k = j + 1
    while k < len(text) and text[k].isspace():
        k += 1
    if k < len(text) and text[k] == "{":
        depth = 0
        for m in range(k, len(text)):
            if text[m] == "{":
                depth += 1
            elif text[m] == "}":
                depth -= 1
                if depth == 0:
                    return text[k:m + 1]
        return text[k:]
    end = text.find(";", k)
    return text[k:end + 1 if end >= 0 else len(text)]


def ignored_errors(src: str) -> list[str]:
    """E: a limiter-table read or write whose error is not captured, or whose error branch does not refuse."""
    s = _strip_comments(src)
    lines = s.split("\n")
    out = []
    for i, line in enumerate(lines):
        m = re.search(r"""\.from\(\s*["'](""" + "|".join(LIMITER_TABLES) + r""")["']\s*\)""", line)
        if not m:
            continue
        table = m.group(1)
        head = "\n".join(lines[max(0, i - 2):i + 1])
        dm = re.findall(r"(?:const|let)\s*\{([^}]*)\}\s*=\s*await\b", head)
        if not dm:
            out.append(f"E line {i + 1}: {table} is read/written with its error discarded (no `{{ error }}`)")
            continue
        names = dm[-1]
        em = re.search(r"\berror\s*:\s*(\w+)", names) or (re.search(r"\b(error)\b", names))
        if not em:
            out.append(f"E line {i + 1}: {table} is read/written with its error discarded (destructures no error)")
            continue
        var = em.group(1)
        tail = "\n".join(lines[i:i + 14])
        br = re.search(r"if\s*\(\s*" + re.escape(var) + r"\b", tail)
        if not br:
            out.append(f"E line {i + 1}: {table}'s error `{var}` is captured and never tested")
            continue
        body = _branch(tail, br.start())
        if not re.search(r"allowed\s*:\s*false|unavailable", body, re.I):
            out.append(f"E line {i + 1}: {table}'s error `{var}` is tested but the call is not refused "
                       f"(fail-open - a limiter that cannot count must not admit)")
    return out


# ── H ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
def dishonest_refusals(src: str) -> list[str]:
    """H: a limiter verdict whose refusal never reads its scope / unavailable flag."""
    s = _strip_comments(src)
    lines = s.split("\n")
    out = []
    for i, line in enumerate(lines):
        m = re.search(r"(?<![\w$.])(\w+)\s*=\s*await\s+(" + "|".join(ASK_LIMITERS) + r")\s*\(", line)
        if not m:
            continue
        var, fn = m.group(1), m.group(2)
        window = "\n".join(lines[i:i + 40])
        if not re.search(r"(?<![\w$])" + re.escape(var) + r"\.(?:allowed)\b", window):
            continue  # verdict never consulted here (none today)
        if not re.search(r"(?<![\w$])" + re.escape(var) + r"\.(?:scope|unavailable)\b", window):
            out.append(f"H line {i + 1}: {var} = {fn}(...) - its refusal never reads {var}.scope, so a limiter that "
                       f"could not count would be reported as a limit reached")
    return out


def scan_files() -> list[Path]:
    return sorted(p for p in FUNCS.rglob("*.ts") if not p.name.endswith(".test.ts"))


def main() -> int:
    print("rate-limit-key-is-verified: a limit is keyed on the verified caller, in a column that holds that key, "
          "and a limiter that cannot count refuses")
    fails: dict[str, list[str]] = {}
    n_solo = 0
    for f in scan_files():
        src = f.read_text(encoding="utf-8", errors="replace")
        rel = f.relative_to(FUNCS).as_posix()
        got: list[str] = []
        if f.name == "index.ts" and "soloRateLimitKey(" in src:
            n_solo += 1
            got += [f"K BODY-KEYED {a}" for a in bad_keys(src)]
        if any(t in src for t in LIMITER_TABLES) or any(h + "(" in src for h in HIVE_LIMITERS):
            got += uid_hive_keys(src)
            got += ignored_errors(src)
            got += empty_hive_keys(src)
        if f.name == "index.ts":
            got += dishonest_refusals(src)
        if got:
            fails[rel] = got
    if fails:
        for rel, items in fails.items():
            for it in items:
                print(f"  {RED}FAIL{RST} {rel}: {it}")
        total = sum(len(v) for v in fails.values())
        print(f"{RED}FAIL rate-limit-key-is-verified - {total} finding(s) in {len(fails)} file(s){RST}")
        return 1
    print(f"{GREEN}PASS rate-limit-key-is-verified - {n_solo} per-person limiters keyed on the verified caller; no hive "
          f"limiter keyed by a person or by an empty key; every limiter read/write checks its error and refuses on it; "
          f"every refusal reads its verdict's scope{RST}")
    return 0


def self_test() -> int:
    cases: list[tuple[str, callable, str, bool]] = []
    # K
    old = ('const auth_uid = body.auth_uid ? String(body.auth_uid).slice(0, 80) : null;\n'
           'const rl = await checkSoloRateLimit(db, soloRateLimitKey(auth_uid, clientIp));')
    inline = 'const rl = await checkSoloRateLimit(db, soloRateLimitKey((body as any).auth_uid, ip));'
    good = ('const _rlUid = (await resolveIdentity(db, req).catch(() => null))?.authUid ?? null;\n'
            'const rl = await checkSoloRateLimit(db, soloRateLimitKey(_rlUid, clientIp));')
    commented = good + '\n// soloRateLimitKey(body.auth_uid, ip) was the old form'
    cases += [("K body-assigned variable", bad_keys, old, True), ("K inline body field", bad_keys, inline, True),
              ("K verified identity", bad_keys, good, False), ("K old form only in a comment", bad_keys, commented, False)]
    # U
    mla_old = ('let rlKey = hive_id;\nif (!hive_id) { rlKey = authUid; }\n'
               'const rl = await checkAIRateLimit(db, rlKey, RATE_LIMIT_PER_HOUR);')
    triage_old = 'const trl = await checkAIRateLimit(_db, ident.authUid, 20, 100);'
    hive_ok = 'const rl = await checkAIRateLimit(db, hive_id, RATE_LIMIT_PER_HOUR);'
    solo_ok = 'const trl = await checkSoloRateLimit(_db, soloRateLimitKey(ident.authUid, null), 20, 100, null, true);'
    direct_old = 'const { error: e } = await db.from("ai_rate_limits").upsert({ hive_id: authUid, call_count: 1 });'
    cases += [("U a uid reassigned into the hive key (marketplace)", uid_hive_keys, mla_old, True),
              ("U a uid passed straight as the hive key (triage)", uid_hive_keys, triage_old, True),
              ("U a uid written to ai_rate_limits.hive_id", uid_hive_keys, direct_old, True),
              ("U a verified hive id", uid_hive_keys, hive_ok, False),
              ("U a person on the per-person limiter", uid_hive_keys, solo_ok, False)]
    # N
    n_bad = 'const { error: openErr } = await db.from("ai_user_rate_limits").upsert({\n  user_id: userId,\n  hive_id: hiveId,\n});'
    n_ok = 'const { error: openErr } = await db.from("ai_user_rate_limits").upsert({\n  user_id: userId,\n  hive_id: hiveId || null,\n});'
    cases += [("N a bare hive id into ai_user_rate_limits", uid_hive_keys, n_bad, True),
              ("N `|| null` into ai_user_rate_limits", uid_hive_keys, n_ok, False)]
    # E
    e_read = 'const { data } = await db.from("ai_rate_limits")\n  .select("call_count").eq("hive_id", h).maybeSingle();'
    e_write = 'await db.from("ai_user_rate_limits").upsert({ user_id: k, hive_id: null });'
    e_open = ('const { error: incErr } = await db.from("ai_rate_limits").update({ call_count: 2 }).eq("hive_id", h);\n'
              'if (incErr) console.warn("counter did not advance");\nreturn { allowed: true, remaining: 3 };')
    e_ok = ('const { data, error: readErr } = await db.from("ai_rate_limits")\n  .select("call_count").maybeSingle();\n'
            'if (readErr) return limiterUnavailable("read", readErr);')
    e_ok2 = ('const { data, error } = await db\n    .from("ai_rate_limits")\n    .select("x").maybeSingle();\n'
             'if (error) {\n  console.warn("read failed");\n  return { allowed: false, remaining: 0, unavailable: true };\n}')
    e_open2 = ('const { error: openErr } = await db.from("ai_rate_limits")\n  .upsert({ hive_id: h, call_count: 1 });\n'
               'if (openErr) log.warn(null, "window could not be opened");\nreturn { allowed: true, remaining: 4 };\n}\n'
               'if (data.call_count >= CAP) return { allowed: false, remaining: 0 };')
    cases += [("E a one-line fail-open with a deny nearby (the branch is the statement, not the next lines)",
               ignored_errors, e_open2, True)]
    cases += [("E a read with no error captured", ignored_errors, e_read, True),
              ("E a write with no destructure at all", ignored_errors, e_write, True),
              ("E an error logged and the call admitted (fail-open)", ignored_errors, e_open, True),
              ("E a read that refuses on error", ignored_errors, e_ok, False),
              ("E a multi-line read that refuses on error", ignored_errors, e_ok2, False)]
    # Z
    z_bad = 'const rl = await checkAIRateLimit(db, hive_id || "");'
    z_bad2 = "const rl = await checkAIRateLimit(db, '', 20);"
    z_ok = 'if (verifiedHiveId) { const rl = await checkAIRateLimit(db, verifiedHiveId); }'
    z_user = 'const rl = await checkUserRateLimit(db, "", uid, 50, 6);'
    cases += [("Z an empty-key fallback into the hive limiter", empty_hive_keys, z_bad, True),
              ("Z a bare empty hive key", empty_hive_keys, z_bad2, True),
              ("Z a proven hive, no fallback", empty_hive_keys, z_ok, False),
              ("Z the per-user bucket alone (checkUserRateLimit with no hive) is not a hive limiter", empty_hive_keys,
               z_user, False)]
    # H
    h_bad = ('const rl = await checkSoloRateLimit(db, soloRateLimitKey(uid, ip));\n'
             'if (!rl.allowed) return json({ error: "AI call limit reached." }, 429);')
    h_ok = ('const rl = await checkSoloRateLimit(db, soloRateLimitKey(uid, ip));\n'
            'if (!rl.allowed) return soloRateLimitedResponse(cors, rl.retry_after_seconds, rl.scope);')
    cases += [("H a refusal that never reads the scope", dishonest_refusals, h_bad, True),
              ("H a refusal that passes the scope", dishonest_refusals, h_ok, False)]

    bad = []
    for name, fn, src, want in cases:
        got = bool(fn(src))
        if got != want:
            bad.append(f"{name}: wanted {'a finding' if want else 'clean'}, got {fn(src)}")
    # the real tree, mutated back to each defect this gate exists for
    real = []
    rl = (FUNCS / "_shared" / "rate-limit.ts").read_text(encoding="utf-8")
    mla = (FUNCS / "marketplace-listing-assist" / "index.ts").read_text(encoding="utf-8")
    arl = (FUNCS / "agentic-rag-loop" / "index.ts").read_text(encoding="utf-8")
    muts = [
        ("the marketplace's hive-less key goes back into checkAIRateLimit",
         lambda: uid_hive_keys(mla.replace("checkSoloRateLimit(db, soloRateLimitKey(soloUid, null), RATE_LIMIT_PER_HOUR, DEFAULT_RATE_LIMIT_PER_DAY, null, true)",
                                           "checkAIRateLimit(db, soloUid, RATE_LIMIT_PER_HOUR)"))),
        ("checkAIRateLimit stops reading its write error",
         lambda: ignored_errors(rl.replace("const { error: writeErr } = await db.from(\"ai_rate_limits\").upsert({",
                                           "await db.from(\"ai_rate_limits\").upsert({"))),
        ("checkUserRateLimit writes hive_id \"\" again",
         lambda: uid_hive_keys(rl.replace("hive_id:      hiveId || null,", "hive_id:      hiveId,"))),
        ("agentic-rag-loop's limiter fails open again",
         lambda: ignored_errors(arl.replace("""    console.warn("[agentic-rag-loop] rate-limit read failed:", error.message);
    return { allowed: false, remaining: 0, unavailable: true };""",
                                         """    console.warn("[agentic-rag-loop] rate-limit read failed:", error.message);
    return { allowed: true, remaining: RATE_LIMIT_PER_HOUR };"""))),
    ]
    vle = (FUNCS / "voice-logbook-entry" / "index.ts").read_text(encoding="utf-8")
    muts.append(("voice-logbook-entry's no-hive caller goes back to checkAIRateLimit(db, hive_id || \"\")",
                 lambda: empty_hive_keys(vle.replace("const rl = await checkAIRateLimit(db, _verifiedHiveId);",
                                                     "const rl = await checkAIRateLimit(db, hive_id || \"\");"))))
    for name, run in muts:
        if not run():
            bad.append(f"real-tree mutant not caught: {name}")
    for name, run in [("the unmutated rate-limit.ts", lambda: ignored_errors(rl) + uid_hive_keys(rl)),
                      ("the unmutated marketplace-listing-assist", lambda: uid_hive_keys(mla) + dishonest_refusals(mla)),
                      ("the unmutated agentic-rag-loop", lambda: ignored_errors(arl) + dishonest_refusals(arl))]:
        got = run()
        if got:
            bad.append(f"{name} has findings: {got[:2]}")
    n = len(cases) + len(muts) + 3
    if bad:
        print(f"{RED}SELF-TEST FAIL ({len(bad)}/{n}):{RST}")
        for b in bad:
            print("  " + b)
        return 1
    print(f"{GREEN}SELF-TEST PASS: {n} checks - K body keys, U uid hive keys, N \"\" hive keys, Z empty hive keys, "
          f"E ignored / fail-open limiter errors, H refusals blind to scope; each caught on fixtures and on the real "
          f"tree mutated back{RST}")
    return 0


if __name__ == "__main__":
    sys.exit(self_test() if ("--self-test" in sys.argv or "--selftest" in sys.argv) else main())
