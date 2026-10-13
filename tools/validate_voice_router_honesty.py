#!/usr/bin/env python3
# DEEPWALK-CELL: ai:* D13
# DEEPWALK-CELL: ai:* D24
"""validate_voice_router_honesty.py - the voice router never says it saved, and a body field never skips a limiter.

TWO DEFECTS in voice-action-router, reported 2026-10-07 (LM-V walk follow-up):

1. FALSE "DONE" NARRATION. The router only CLASSIFIES a spoken sentence; nothing is written until the person
   confirms and the page saves. Its narration said "Naks, you logged a 2 hour brake pad replacement" with nothing
   saved. The platform's false-done rail (_shared/action_provenance.ts stripFalseActionClaims) never saw it: the
   gateway applies that rail only to ADVISORY agents and listed voice-action as an EXECUTOR whose "logged" is true -
   and the rail guards "I did X", not "you logged". Fix: the router prompt asks for a PROPOSAL (rule 7, future or
   conditional tense), and the router runs its narration through the stricter PROPOSAL rail
   (honestProposalNarration): any past-tense platform-write claim - by I / we / you / passive / elided subject - is
   removed and an honest line takes its place, on the direct path and behind the gateway alike.

2. RATE-LIMIT BYPASS. The router skipped its own limiter whenever the request BODY said `gateway: true`. The gateway
   forwards the person's OWN JWT, so a direct call and a gateway call look identical by bearer, and any signed-in
   person could send `gateway: true` straight to the router and skip every limiter on it (hive, per-surface, solo).
   Fix: _shared/gateway-trust.ts - ai-gateway mints x-wh-gateway-forward (HMAC-SHA256 keyed on the service-role
   key over the exact bearer it forwards) and the router skips ONLY when isTrustedGatewayForward(req) is true.

CHECKS (exit 1 on any):
  S1  platform-wide: no edge function lets a BOOLEAN read from the request body (`x = body.gateway === true`,
      `!!body.internal`, a direct `body.x === true` condition) decide whether a check*RateLimit(...) call runs.
  S2  the router decides its limiter skip with isTrustedGatewayForward(req) and reads no `gateway` body field.
  S3  ai-gateway's specialist forward spreads gatewayForwardHeaders(<the Authorization it sends>) into its headers.
  S4  the router's narration goes through honestProposalNarration(narration...), and ROUTER_SYSTEM states the
      proposal contract ("NOTHING IS SAVED").
  S5  (2026-10-08) every function ai-gateway forwards to (its AGENT_ROUTES) runs a limiter that counts a bucket the
      gateway already counted - checkAIRateLimit / checkUserRateLimit / checkSoloRateLimit / checkClassedRateLimit /
      checkGlobalAIBudget, a local wrapper of one, or a write to ai_rate_limits / ai_user_rate_limits - ONLY when
      `const T = await isTrustedGatewayForward(req)` is false. Nine targets counted the same row twice per forward
      (voice-journal-agent's solo bucket is keyed on the very uid the gateway uses), so a person or a hive ran out at
      about half the stated rate. Its per-surface quota (checkRouteRateLimit on its OWN literal function name, never
      the gateway's agent id) is a different bucket and stays on both doors; any other limiter kept on a forward
      must be in KEEP with its reason. `--table` prints the per-target audit.
  B1  BEHAVIOUR (node, the REAL action_provenance.ts): the live-caught sentence and its family are stripped; future
      / conditional proposals, negations and the worker's own physical work are kept; the clarifier survives itself.
  B2  BEHAVIOUR (node, the REAL gateway-trust.ts): a minted header verifies for its own bearer only - not with no
      header (a direct call with `gateway: true`), not with another bearer, not tampered, not guessed, not with no
      service key configured (fails closed).

    python tools/validate_voice_router_honesty.py              # PASS / FAIL
    python tools/validate_voice_router_honesty.py --self-test  # teeth: pre-fix sources + 5 behavioural mutants FAIL

Static + node (no deno, no DB, no model, no browser).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FUNCS = ROOT / "supabase" / "functions"
ROUTER = FUNCS / "voice-action-router" / "index.ts"
GATEWAY = FUNCS / "ai-gateway" / "index.ts"
RAIL = FUNCS / "_shared" / "action_provenance.ts"
TRUST = FUNCS / "_shared" / "gateway-trust.ts"
GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"
RST = "\033[0m"

LIMITER = re.compile(r"\bcheck\w*RateLimit\s*\(")
BODY_WORD = r"(?:body|_whBody|payload|reqBody|rawBody)"


# ---------------------------------------------------------------------------------------------------------------------
# source helpers
# ---------------------------------------------------------------------------------------------------------------------
def strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), src, flags=re.S)
    return re.sub(r"(?m)(^|[^:\"'\\])//.*$", r"\1", src)


def blank_strings(src: str) -> str:
    """Blank the inside of single-line '...' / "..." literals so a brace or keyword in a message is not code."""
    return re.sub(r"""(["'])(?:\\.|(?!\1)[^\\\n])*\1""", lambda m: m.group(1) + " " * (len(m.group(0)) - 2) + m.group(1), src)


def _match_paren(s: str, i: int) -> int:
    """s[i] == '(' -> index of its matching ')' (or -1)."""
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "(":
            depth += 1
        elif s[j] == ")":
            depth -= 1
            if depth == 0:
                return j
    return -1


def _block_end(s: str, i: int) -> int:
    """From i (just after a condition), the end of the statement/block it governs."""
    j = i
    while j < len(s) and s[j].isspace():
        j += 1
    if j < len(s) and s[j] == "{":
        depth = 0
        for k in range(j, len(s)):
            if s[k] == "{":
                depth += 1
            elif s[k] == "}":
                depth -= 1
                if depth == 0:
                    return k + 1
        return len(s)
    k = s.find(";", j)
    return len(s) if k < 0 else k + 1


def _chain_end(s: str, i: int) -> int:
    """i = end of an if-block; extend over every following else-if / else."""
    end = i
    while True:
        m = re.match(r"\s*else\b", s[end:])
        if not m:
            return end
        k = end + m.end()
        m2 = re.match(r"\s*if\s*\(", s[k:])
        if m2:
            p = k + m2.end() - 1
            q = _match_paren(s, p)
            if q < 0:
                return end
            end = _block_end(s, q + 1)
        else:
            end = _block_end(s, k)


def body_flags(s: str) -> set[str]:
    """Identifiers assigned a BOOLEAN read from the request body."""
    out = set()
    for m in re.finditer(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::\s*boolean\s*)?=\s*([^;]+);", s):
        rhs = m.group(2)
        if not re.search(rf"\b{BODY_WORD}\b", rhs):
            continue
        if (re.search(r"(?:===?|!==?)\s*(?:true|false|1|0)\b", rhs)
                or re.match(r"\s*!!", rhs) or re.match(r"\s*Boolean\s*\(", rhs)):
            out.add(m.group(1))
    return out


def body_flag_limiter_skips(src: str) -> list[str]:
    """S1: places where a body-read boolean decides whether a limiter call runs."""
    s = blank_strings(strip_comments(src))
    if not LIMITER.search(s):
        return []
    flags = body_flags(s)
    # BOOLEAN reads only. A body STRING compared in a condition (`body.mode === "service_triage"`,
    # `body.type === "INSERT"`) is a mode dispatch whose branches carry their own gates (measured 2026-10-08:
    # embed-entry's webhook shape requires the service role; marketplace-listing-assist's triage mode has its own
    # limiter), so it is out of scope here - a string-keyed skip would need a per-branch reading this does not do.
    direct = re.compile(rf"\b{BODY_WORD}\b[^;{{}}]*?(?:===?|!==?)\s*(?:true|false|1|0)\b")
    def cond_is_flagged(cond: str) -> str | None:
        for f in flags:
            if re.search(rf"(?<![\w$.]){re.escape(f)}(?![\w$])", cond):
                return f
        return "a body field" if direct.search(cond) else None
    found = []
    for m in re.finditer(r"\bif\s*\(", s):
        p = m.end() - 1
        q = _match_paren(s, p)
        if q < 0:
            continue
        who = cond_is_flagged(s[p + 1:q])
        if not who:
            continue
        end = _chain_end(s, _block_end(s, q + 1))
        if LIMITER.search(s[q + 1:end]):
            line = s.count("\n", 0, m.start()) + 1
            found.append(f"line {line}: if (...{who}...) gates a rate limiter")
    # ternary / short-circuit in one statement: `flag ? x : await checkAIRateLimit(...)`, `flag || await check...`
    for stmt in re.finditer(r"[^;{}]*\bcheck\w*RateLimit\s*\([^;]*;", s):
        head = stmt.group(0)[: LIMITER.search(stmt.group(0)).start()]
        if re.search(r"[?]|&&|\|\|", head):
            who = cond_is_flagged(head)
            if who:
                line = s.count("\n", 0, stmt.start()) + 1
                found.append(f"line {line}: `{who}` short-circuits a rate limiter")
    return found


def router_static(router_src: str) -> list[str]:
    """S2 + S4 on the router source."""
    out = []
    s = strip_comments(router_src)
    if not re.search(r"=\s*await\s+isTrustedGatewayForward\(\s*req\s*\)", s):
        out.append("S2: the router does not decide its limiter skip with `await isTrustedGatewayForward(req)`")
    if re.search(rf"\b{BODY_WORD}\b[^;]*?\.\s*gateway\b|\[\s*[\"']gateway[\"']\s*\]", s):
        out.append("S2: the router still reads a `gateway` field from the request body")
    for f in body_flag_limiter_skips(router_src):
        out.append(f"S1: {f}")
    if not re.search(r"\bhonestProposalNarration\(\s*narration\w*", s):
        out.append("S4: the narration is not run through honestProposalNarration(narration...) - a past-tense "
                   "'you logged ...' reaches the worker with nothing saved")
    rs = re.search(r"const ROUTER_SYSTEM\s*=\s*`(.*?)`;", router_src, re.S)
    if not rs or "NOTHING IS SAVED" not in rs.group(1):
        out.append("S4: ROUTER_SYSTEM does not state the proposal contract (\"NOTHING IS SAVED\")")
    return out


def gateway_static(gw_src: str) -> list[str]:
    """S3: the forward carries the trust header minted over the bearer it actually sends."""
    s = strip_comments(gw_src)
    m = re.search(r"const\s+(\w+)\s*=\s*await\s+gatewayForwardHeaders\(\s*(\w+)\s*\)", s)
    if not m:
        return ["S3: ai-gateway does not mint gatewayForwardHeaders(<forward bearer>) for its specialist forward"]
    trust_var, auth_var = m.group(1), m.group(2)
    f = re.search(r"fetch\(\s*targetUrl\s*,\s*\{(.*?)\bbody\s*:", s, re.S)
    if not f:
        return ["S3: ai-gateway's specialist forward (fetch(targetUrl, ...)) not found"]
    block = f.group(1)
    out = []
    if not re.search(rf"\.\.\.\s*{re.escape(trust_var)}\b", block):
        out.append(f"S3: the forward's headers do not spread `{trust_var}` (the x-wh-gateway-forward header)")
    if not re.search(rf"[\"']Authorization[\"']\s*:\s*{re.escape(auth_var)}\b", block):
        out.append(f"S3: the forward's Authorization is not `{auth_var}` - the header is minted over a different bearer")
    return out


# ---------------------------------------------------------------------------------------------------------------------
# S5 - a gateway target never re-counts the bucket ai-gateway already counted (2026-10-08)
# ---------------------------------------------------------------------------------------------------------------------
# ai-gateway counts every forwarded turn ONCE: ai_rate_limits[verified hive] + ai_user_rate_limits[auth uid] (hive path),
# or ai_user_rate_limits[<auth uid | ip:caller>] (solo path), plus hive_route_calls[(hive, <agent id>)] and the global
# pool. Nine of its eleven target functions then counted the SAME row again on the forward - voice-journal-agent's solo
# bucket is keyed on the very uid the gateway uses - so a person or a hive ran out at about half the stated rate. A target
# may skip a limiter that counts one of those buckets ONLY under `const T = await isTrustedGatewayForward(req)` (never a
# body field). Its per-SURFACE quota (checkRouteRateLimit keyed on its own literal function name) is a different bucket
# and is kept on both doors; any other limiter kept on a forward must be listed in KEEP with the reason.
GATEWAY_BUCKET_LIMITERS = ("checkAIRateLimit", "checkUserRateLimit", "checkSoloRateLimit", "checkClassedRateLimit",
                           "checkGlobalAIBudget")
GATEWAY_BUCKET_TABLE = re.compile(r"""\.from\(\s*["'](?:ai_rate_limits|ai_user_rate_limits)["']\s*\)""")
WRITE_OP = re.compile(r"\.(?:upsert|update|insert)\s*\(")
TRUST_DECL = re.compile(r"\bconst\s+([A-Za-z_$][\w$]*)\s*(?::\s*boolean\s*)?=\s*await\s+isTrustedGatewayForward\(\s*req\s*\)")
TRUST_INLINE = re.compile(r"^\(?\s*await\s+isTrustedGatewayForward\(\s*req\s*\)\s*\)?$")

# Limiters a gateway target KEEPS on a forward, each with the reason. An entry must match exactly one call in its fn (a
# stale entry fails), and `requires`, when present, must hold in ai-gateway's source.
# (2026-10-08) service-triage's cap used to be KEPT here as "a different bucket": it wrote the auth uid into
# ai_rate_limits.hive_id, which a foreign key to hives refused on every call, so it was no bucket at all. It now lives on
# the person's ai_user_rate_limits row - the gateway's own solo bucket - so on a forward it READS that row
# (peekSoloRateLimit) and counts only on the direct door: guarded, no KEEP needed.
_LISTING_UNREACHABLE = {
    "why": "the listing-draft path, which no forward reaches: the gateway pins mode service_triage for this function "
           "and the triage branch returns first",
    "requires": r"agent\s*===\s*[\"']service-triage[\"']\s*\)\s*\{\s*forwardExtras\.mode\s*=\s*[\"']service_triage[\"']",
}
KEEP = [
    {"fn": "marketplace-listing-assist", "call": r"checkAIRateLimit\(\s*db\s*,\s*verifiedHiveId\s*,",
     **_LISTING_UNREACHABLE},
    {"fn": "marketplace-listing-assist", "call": r"checkSoloRateLimit\(\s*db\s*,\s*soloRateLimitKey\(\s*soloUid\s*,",
     **_LISTING_UNREACHABLE},
]


def _mask(src: str) -> tuple[str, str]:
    """Two same-length views of TS source: `nc` (comments blanked) and `code` (comments, string / template / regex
    literal CONTENTS blanked) - so a brace in a prompt, a backtick in a regex or a call in a comment is not structure."""
    n = len(src)
    nc, code = list(src), list(src)

    def blank(a: int, b: int, keep_delims: bool, also_nc: bool) -> None:
        lo, hi = (a + 1, b - 1) if keep_delims else (a, b)
        for k in range(lo, hi):
            if src[k] != "\n":
                code[k] = " "
                if also_nc:
                    nc[k] = " "

    i, last_sig = 0, ""
    while i < n:
        c = src[i]
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            j = n if j < 0 else j
            blank(i, j, False, True)
            i = j
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            blank(i, j, False, True)
            i = j
            continue
        if c in "\"'`":
            j = i + 1
            while j < n and src[j] != c:
                if src[j] == "\\":
                    j += 1
                elif c != "`" and src[j] == "\n":
                    break
                j += 1
            j = min(j + 1, n)
            blank(i, j, True, False)
            last_sig, i = c, j
            continue
        if c == "/" and (last_sig == "" or last_sig in "(,=:[!&|?{};+-*%<>~^" or
                         re.search(r"\b(?:return|typeof|case|in|of|void|delete)\s*$", src[max(0, i - 12):i])):
            j, in_cls = i + 1, False
            while j < n and src[j] != "\n":
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "[":
                    in_cls = True
                elif src[j] == "]":
                    in_cls = False
                elif src[j] == "/" and not in_cls:
                    break
                j += 1
            if j < n and src[j] == "/":
                blank(i, j + 1, True, False)
                last_sig, i = "/", j + 1
                continue
        if not c.isspace():
            last_sig = c
        i += 1
    return "".join(nc), "".join(code)


def _split_top(cond: str, op: str) -> list[str]:
    """Split a condition on a top-level `&&` / `||` (outside parentheses)."""
    parts, depth, cur, k = [], 0, [], 0
    while k < len(cond):
        ch = cond[k]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if depth == 0 and cond.startswith(op, k):
            parts.append("".join(cur).strip())
            cur, k = [], k + len(op)
            continue
        cur.append(ch)
        k += 1
    parts.append("".join(cur).strip())
    return parts


def _strip_parens(t: str) -> str:
    t = t.strip()
    while t.startswith("(") and _match_paren(t, 0) == len(t) - 1:
        t = t[1:-1].strip()
    return t


def _is_trust(term: str, trust: set[str]) -> bool:
    t = _strip_parens(term)
    return t in trust or bool(TRUST_INLINE.match(t))


def _guarded(code: str, pos: int, trust: set[str]) -> bool:
    """True when `pos` runs only on a call that is NOT a proven forward: inside the then-block of an `if` whose every
    top-level `||` disjunct has `!T` as a top-level `&&` conjunct, or inside the else-part of an `if` that has a bare
    `T` as a top-level `||` disjunct."""
    for m in re.finditer(r"\bif\s*\(", code):
        if m.start() > pos:
            break
        p = m.end() - 1
        q = _match_paren(code, p)
        if q < 0 or q > pos:
            continue
        then_end = _block_end(code, q + 1)
        cond = code[p + 1:q]
        if q < pos < then_end:
            ors = _split_top(cond, "||")
            if all(any(a.startswith("!") and _is_trust(a[1:], trust) for a in map(str.strip, _split_top(d, "&&")))
                   for d in ors):
                return True
        else:
            chain_end = _chain_end(code, then_end)
            if then_end <= pos < chain_end and any(_is_trust(d, trust) for d in _split_top(cond, "||")):
                return True
    return False


def _function_bodies(code: str) -> dict[str, tuple[int, int]]:
    """name -> (body start, body end) for `function NAME(...) [: Type] { ... }` declarations."""
    out: dict[str, tuple[int, int]] = {}
    for m in re.finditer(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*(?:<[^>()]*>)?\s*\(", code):
        q = _match_paren(code, m.end() - 1)
        if q < 0:
            continue
        k, angle = q + 1, 0
        while k < len(code):
            ch = code[k]
            if ch == "<":
                angle += 1
            elif ch == ">" and code[k - 1] != "=":
                angle -= 1
            elif ch == "{" and angle <= 0:
                break
            elif ch == ";" and angle <= 0:
                k = -1
                break
            k += 1
        if k < 0 or k >= len(code):
            continue
        end = _block_end(code, k)
        out[m.group(1)] = (k, end)
    return out


def _table_writes(nc: str, code: str, lo: int = 0, hi: int | None = None) -> list[int]:
    """Positions of `.from("ai_rate_limits" | "ai_user_rate_limits")...upsert/update/insert(` statements."""
    hi = len(nc) if hi is None else hi
    out = []
    for m in GATEWAY_BUCKET_TABLE.finditer(nc, lo, hi):
        semi = code.find(";", m.end())
        stmt = code[m.end(): semi if semi >= 0 else len(code)]
        if WRITE_OP.search(stmt):
            out.append(m.start())
    return out


def target_limiter_audit(fn: str, src: str, agent_ids: list[str], gw_src: str, keep=None) -> dict:
    """S5 for one gateway target. Returns {findings, guarded, kept, routes, keep_hits}."""
    keep = KEEP if keep is None else keep
    nc, code = _mask(src)
    trust = set(TRUST_DECL.findall(code))
    bodies = _function_bodies(code)
    names = set(GATEWAY_BUCKET_LIMITERS)
    local: dict[str, tuple[int, int]] = {}
    for _ in range(3):   # a local wrapper of a limiter is a limiter (transitively)
        call_re = re.compile(r"\b(?:" + "|".join(map(re.escape, sorted(names))) + r")\s*\(")
        for name, (a, b) in bodies.items():
            if name in local:
                continue
            if call_re.search(code, a, b) or _table_writes(nc, code, a, b):
                local[name] = (a, b)
                names.add(name)
    inside_local = lambda p: any(a <= p < b for a, b in local.values())
    call_re = re.compile(r"\b(" + "|".join(map(re.escape, sorted(names))) + r")\s*\(")
    sites = []
    for m in call_re.finditer(code):
        if re.search(r"\bfunction\s+$", code[max(0, m.start() - 16):m.start()]) or inside_local(m.start()):
            continue
        sites.append((m.start(), m.group(1)))
    sites += [(p, ".from(<gateway bucket table>).write") for p in _table_writes(nc, code) if not inside_local(p)]
    res = {"findings": [], "guarded": 0, "kept": [], "routes": [], "keep_hits": {}}
    for pos, name in sorted(sites):
        line = code.count("\n", 0, pos) + 1
        if _guarded(code, pos, trust):
            res["guarded"] += 1
            continue
        stmt_end = code.find(";", pos)
        stmt = nc[pos: stmt_end if stmt_end >= 0 else len(nc)]
        hit = None
        for idx, k in enumerate(keep):
            if k["fn"] == fn and re.match(k["call"], stmt):
                hit = idx
                break
        if hit is not None:
            res["keep_hits"][hit] = res["keep_hits"].get(hit, 0) + 1
            req = keep[hit].get("requires")
            if req and not re.search(req, _mask(gw_src)[0]):
                res["findings"].append(f"line {line}: {name}(...) is KEPT as unreachable by a forward, but ai-gateway "
                                       f"no longer guarantees it ({req})")
            else:
                res["kept"].append(f"line {line}: {stmt.strip()[:70]} - {keep[hit]['why']}")
            continue
        res["findings"].append(
            f"line {line}: {name}(...) counts a bucket ai-gateway already counted, and runs on a forwarded call - skip "
            f"it under `const T = await isTrustedGatewayForward(req)` (never a body field), or list it in KEEP with why")
    for m in re.finditer(r"\bcheckRouteRateLimit\s*\(", code):
        q = _match_paren(code, m.end() - 1)
        args = nc[m.end():q] if q > 0 else ""
        lit = re.search(r"""["']([\w\-]+)["']\s*$""", args.strip())
        line = code.count("\n", 0, m.start()) + 1
        if not lit:
            res["findings"].append(f"line {line}: checkRouteRateLimit route key is not a literal - cannot prove it is "
                                   f"not the gateway's own (hive, agent) row")
        elif lit.group(1) in agent_ids:
            res["findings"].append(f"line {line}: checkRouteRateLimit(..., \"{lit.group(1)}\") is the gateway's own "
                                   f"(hive, agent) route row - counted twice per forward")
        else:
            res["routes"].append(lit.group(1))
    return res


def gateway_target_map(gw_src: str) -> dict[str, list[str]]:
    """target function -> [agent ids] from ai-gateway's AGENT_ROUTES literal."""
    _, code = _mask(gw_src)
    nc = _mask(gw_src)[0]
    decl = re.search(r"const AGENT_ROUTES\b[^=]*=\s*\{", nc)
    if not decl:
        return {}
    end = _block_end(code, decl.end() - 1)
    out: dict[str, list[str]] = {}
    for m in re.finditer(r"""["']([a-z0-9\-]+)["']\s*:\s*\{[^}]*?\bfn\s*:\s*["']([a-z0-9\-]+)["']""",
                         nc[decl.end():end], re.S | re.I):
        out.setdefault(m.group(2), []).append(m.group(1))
    return out


def gateway_targets_static(gw_src: str, read=None) -> tuple[list[str], list[tuple]]:
    """S5 over every function ai-gateway forwards to. Returns (failures, table rows)."""
    read = read or (lambda fn: (FUNCS / fn / "index.ts").read_text(encoding="utf-8", errors="replace"))
    fails, rows = [], []
    targets = gateway_target_map(gw_src)
    if not targets:
        return ["S5: could not parse ai-gateway's AGENT_ROUTES"], rows
    keep_seen: dict[int, int] = {}
    for fn in sorted(targets):
        try:
            src = read(fn)
        except OSError:
            fails.append(f"S5: gateway target {fn} has no index.ts")
            continue
        r = target_limiter_audit(fn, src, targets[fn], gw_src)
        for idx, c in r["keep_hits"].items():
            keep_seen[idx] = keep_seen.get(idx, 0) + c
        fails += [f"S5: {fn} {x}" for x in r["findings"]]
        rows.append((fn, ",".join(targets[fn]), r["guarded"], len(r["kept"]), ",".join(r["routes"]) or "-",
                     "FAIL" if r["findings"] else "ok"))
    for idx, k in enumerate(KEEP):
        if k["fn"] in targets and keep_seen.get(idx, 0) != 1:
            fails.append(f"S5: KEEP entry for {k['fn']} ({k['call']}) matched {keep_seen.get(idx, 0)} calls, not 1 "
                         f"- stale or ambiguous")
    return fails, rows


# ---------------------------------------------------------------------------------------------------------------------
# behaviour (node, the real modules; Node >= 22.18 strips TS types natively)
# ---------------------------------------------------------------------------------------------------------------------
PROPOSAL_CASES = [
    # (narration, must be stripped)
    ("Naks, you logged a 2 hour brake pad replacement.", True),          # live-caught 2026-10-07
    ("Deducted 2 V-belts from stock.", True),
    ("PM marked as complete.", True),
    ("Done, I've logged it.", True),
    ("Got it, logged the brake pad replacement.", True),
    ("The entry has been saved.", True),
    ("Stock updated, two V-belts out.", True),
    ("I've marked the weekly inspection on the chiller complete.", True),
    ("You've recorded the job.", True),
    ("All done!", True),
    ("I can log a 2-hour brake pad replacement. Confirm to fill the form.", False),
    ("Ready to deduct 2 V-belts from stock once you confirm.", False),
    ("Once you confirm, the PM on the chiller will be marked complete.", False),
    ("Nothing is saved yet. Check the details and confirm to continue.", False),
    ("You replaced the V-belt on the pump, nice work. Confirm and I will log it.", False),
    ("Done with the weekly inspection? Nice.", False),
    ("This will be logged as a breakdown once you confirm.", False),
    ("Opening the logbook to log a breakdown.", False),
]

NODE_RUNNER = r"""
import { pathToFileURL } from "node:url";
const [apPath, gtPath, casesPath] = process.argv.slice(2);
globalThis.Deno = { env: { get: (k) => process.env[k] } };
const fs = await import("node:fs");
const cases = JSON.parse(fs.readFileSync(casesPath, "utf8"));
const out = { proposal: [], trust: {} };
const ap = await import(pathToFileURL(apPath).href);
for (const [text, want] of cases) out.proposal.push({ text, want, got: ap.stripProposalDoneClaims(text).hit });
const h = ap.honestProposalNarration("Naks, you logged a 2 hour brake pad replacement.");
out.honest = h.narration;
out.clarifier = ap.PROPOSAL_HONEST_CLARIFIER;
out.clarifierSurvives = !ap.stripProposalDoneClaims(ap.PROPOSAL_HONEST_CLARIFIER).hit;
const gt = await import(pathToFileURL(gtPath).href);
const name = gt.GATEWAY_FORWARD_HEADER;
const mk = (headers) => new Request("http://local/", { method: "POST", headers });
const A = "Bearer user-a-jwt", B = "Bearer user-b-jwt";
process.env.SUPABASE_SERVICE_ROLE_KEY = "selftest-service-key";
const hA = await gt.gatewayForwardHeaders(A);
const t = out.trust;
t.minted = Boolean(hA[name]);
t.genuine = await gt.isTrustedGatewayForward(mk({ Authorization: A, ...hA }));
t.no_header = await gt.isTrustedGatewayForward(mk({ Authorization: A }));
t.other_bearer = await gt.isTrustedGatewayForward(mk({ Authorization: B, ...hA }));
const flip = (v) => (v || "x").slice(0, -1) + ((v || "x").slice(-1) === "0" ? "1" : "0");
t.tampered = await gt.isTrustedGatewayForward(mk({ Authorization: A, [name]: flip(hA[name]) }));
t.guessed = await gt.isTrustedGatewayForward(mk({ Authorization: A, [name]: "true" }));
process.env.SUPABASE_SERVICE_ROLE_KEY = "";
t.no_key_mints_nothing = Object.keys(await gt.gatewayForwardHeaders(A)).length === 0;
t.no_key_verifies = await gt.isTrustedGatewayForward(mk({ Authorization: A, ...hA }));
console.log("@@RESULT@@" + JSON.stringify(out));
"""

TRUST_EXPECT = {"minted": True, "genuine": True, "no_header": False, "other_bearer": False, "tampered": False,
                "guessed": False, "no_key_mints_nothing": True, "no_key_verifies": False}


def run_behaviour(rail_src: str, trust_src: str) -> tuple[list[str], dict | None]:
    """B1 + B2 against the given module sources (the real files, or a mutant). Returns (failures, raw result)."""
    tmp = Path(tempfile.mkdtemp(prefix="wh_vrh_"))
    try:
        (tmp / "action_provenance.ts").write_text(rail_src, encoding="utf-8")
        (tmp / "gateway-trust.ts").write_text(trust_src, encoding="utf-8")
        (tmp / "cases.json").write_text(json.dumps(PROPOSAL_CASES), encoding="utf-8")
        (tmp / "runner.mjs").write_text(NODE_RUNNER, encoding="utf-8")
        try:
            proc = subprocess.run(
                ["node", str(tmp / "runner.mjs"), str(tmp / "action_provenance.ts"), str(tmp / "gateway-trust.ts"),
                 str(tmp / "cases.json")],
                capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return (["node not on PATH - the behavioural half cannot run"], None)
        line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("@@RESULT@@")), None)
        if not line:
            return ([f"node run produced no result (exit {proc.returncode}): {proc.stderr.strip()[-300:]}"], None)
        res = json.loads(line[len("@@RESULT@@"):])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    fails = []
    for c in res["proposal"]:
        if c["got"] != c["want"]:
            verb = "NOT stripped" if c["want"] else "wrongly stripped"
            fails.append(f"B1: {verb}: {c['text']!r}")
    if not res.get("clarifierSurvives"):
        fails.append("B1: the honest clarifier is stripped by its own rail")
    if "logged" in res.get("honest", "").lower() or res.get("clarifier", "") not in res.get("honest", ""):
        fails.append(f"B1: honestProposalNarration did not replace the live-caught claim: {res.get('honest')!r}")
    for k, want in TRUST_EXPECT.items():
        if res["trust"].get(k) != want:
            fails.append(f"B2: gateway trust `{k}` = {res['trust'].get(k)} (want {want})")
    return fails, res


# ---------------------------------------------------------------------------------------------------------------------
def main() -> int:
    print("voice-router-honesty: the router proposes (never claims a save) and only ai-gateway can skip its limiter")
    fails: list[str] = []
    n_lim = 0
    for f in sorted(FUNCS.glob("*/index.ts")):
        src = f.read_text(encoding="utf-8", errors="replace")
        if LIMITER.search(src):
            n_lim += 1
        for hit in body_flag_limiter_skips(src):
            fails.append(f"S1: {f.parent.name} {hit}")
    fails += [x for x in router_static(ROUTER.read_text(encoding="utf-8")) if not x.startswith("S1:")]
    gw_src = GATEWAY.read_text(encoding="utf-8")
    fails += gateway_static(gw_src)
    s5_fails, rows = gateway_targets_static(gw_src)
    fails += s5_fails
    if "--table" in sys.argv:
        print(f"  {'gateway target':28} {'agent id(s)':22} {'skipped on forward':>18} {'kept':>5}  per-surface route key")
        for fn, agents, g, k, routes, verdict in rows:
            print(f"  {fn:28} {agents:22} {g:>18} {k:>5}  {routes}  {verdict}")
        for k in KEEP:
            print(f"  KEEP {k['fn']}: {k['why']}")
    bfails, res = run_behaviour(RAIL.read_text(encoding="utf-8"), TRUST.read_text(encoding="utf-8"))
    fails += bfails
    if fails:
        for x in fails:
            print(f"  {RED}x{RST} {x}")
        print(f"{RED}FAIL voice-router-honesty - {len(fails)} breach(es){RST}")
        return 1
    n_cases = len(res["proposal"]) if res else 0
    n_guard = sum(r[2] for r in rows)
    print(f"{GREEN}PASS voice-router-honesty - {n_lim} limiter fns, none skipped on a body field; router skip = "
          f"isTrustedGatewayForward; gateway mints the header over its forward bearer; {len(rows)} gateway targets "
          f"re-count none of the gateway's buckets ({n_guard} limiter calls skipped only on a proven forward, "
          f"{len(KEEP)} kept with a reason); narration through the proposal rail ({n_cases} cases + clarifier); trust "
          f"header binds to its bearer and fails closed{RST}")
    return 0


PRE_FIX_ROUTER = '''
const ROUTER_SYSTEM = `... "narration": <string - 1-2 sentence prose acknowledgement ...> ...`;
serveObserved("voice-action-router", async (req) => {
    const body = await req.json().catch(() => ({}));
    const viaGateway = body.gateway === true;
    let remaining = -1;
    if (!viaGateway && soloUid) {
      const srl = await checkSoloRateLimit(db, soloRateLimitKey(soloUid, _ip), undefined, undefined, _ip || null);
      if (!srl.allowed) return soloRateLimitedResponse(corsHeaders, srl.retry_after_seconds);
      remaining = srl.remaining;
    } else if (!viaGateway) {
      const rl = await checkAIRateLimit(db, hive_id, RATE_LIMIT_PER_HOUR);
      remaining = rl.remaining;
    }
    const narrationRaw = typeof parsed.narration === "string" ? parsed.narration.trim() : "";
    const narration = narrationRaw.slice(0, 280);
});
'''

POST_FIX_ROUTER = '''
const ROUTER_SYSTEM = `... It is a PROPOSAL, because NOTHING IS SAVED when they hear it ...`;
serveObserved("voice-action-router", async (req) => {
    const body = await req.json().catch(() => ({}));
    const viaGateway = await isTrustedGatewayForward(req);
    let remaining = -1;
    if (!viaGateway && soloUid) {
      const srl = await checkSoloRateLimit(db, soloRateLimitKey(soloUid, _ip), undefined, undefined, _ip || null);
      remaining = srl.remaining;
    } else if (!viaGateway) {
      const rl = await checkAIRateLimit(db, hive_id, RATE_LIMIT_PER_HOUR);
      remaining = rl.remaining;
    }
    const honest = honestProposalNarration(narrationRaw, 280);
});
'''

S1_CASES = [
    ("pre-fix router (else-if chain)", PRE_FIX_ROUTER, True),
    ("post-fix router", POST_FIX_ROUTER, False),
    ("typed body flag, inverted block + else",
     "const internal: boolean = (body as any).internal === true;\nif (internal) { x(); } else { await checkAIRateLimit(db, h, 5); }", True),
    ("direct body condition",
     "if (body.internal !== true) { const r = await checkSoloRateLimit(db, k); }", True),
    ("string mode dispatch (each branch carries its own gate; out of scope)",
     "if (String(body.mode || '') === 'service_triage') { await checkAIRateLimit(db, uid, 20); return x; }", False),
    ("ternary skip", "const skip = !!body.skip_limits;\nconst rl = skip ? null : await checkAIRateLimit(db, h, 5);", True),
    ("hive-vs-solo selector (both branches limit, not a flag)",
     "const hive_id = String(body.hive_id || '');\nif (hive_id) { await checkAIRateLimit(db, hive_id, 5); } else { await checkSoloRateLimit(db, k); }", False),
    ("flag only in a comment",
     "// const viaGateway = body.gateway === true; if (!viaGateway) { checkAIRateLimit(db) }\nawait checkAIRateLimit(db, h, 5);", False),
]

GW_PRE = '''
    const resp = await fetch(targetUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": authHeader || `Bearer ${SERVICE_KEY}` },
      body: JSON.stringify({ message, gateway: true }),
    });
'''
GW_POST = '''
  const forwardAuth = authHeader || `Bearer ${SERVICE_KEY}`;
  const forwardTrust = await gatewayForwardHeaders(forwardAuth);
    const resp = await fetch(targetUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": forwardAuth, ...forwardTrust },
      body: JSON.stringify({ message, gateway: true }),
    });
'''
GW_WRONG_BEARER = GW_POST.replace('"Authorization": forwardAuth', '"Authorization": authHeader')

# (label, file, anchor, replacement) - each must make the behaviour check FAIL
MUTANTS = [
    ("proposal rail is a no-op", "rail", "function isProposalDoneClaim(unit: string): boolean {",
     "function isProposalDoneClaim(unit: string): boolean { return false;"),
    ("proposal rail ignores 'you' (the live-caught shape)", "rail", r"\b(?:i|we|you)\b", r"\b(?:i|we)\b"),
    ("future/conditional hedge dropped", "rail", "if (!PROPOSAL_FUTURE_LEAD.test(lead) && ", "if ("),
    ("trust always true", "trust", "export async function isTrustedGatewayForward(req: Request): Promise<boolean> {",
     "export async function isTrustedGatewayForward(req: Request): Promise<boolean> { return true;"),
    ("header not bound to the bearer", "trust", "enc.encode(MAC_CONTEXT + authorization)", "enc.encode(MAC_CONTEXT)"),
]


# S5 fixtures: (label, fn, gateway agent ids, source, want a finding). The PRE-fix shapes are the real 2026-10-08 sources.
S5_GW = 'const AGENT_ROUTES = { "service-triage": { fn: "marketplace-listing-assist" } };\n' \
        'if (agent === "service-triage") {\n    forwardExtras.mode = "service_triage";\n  }'
S5_CASES = [
    ("pre-fix voice-journal-agent: solo bucket on the gateway's uid, service-role exemption only",
     "voice-journal-agent", ["voice-journal"],
     "const _vjIsService = !!_WH_SERVICE_KEY && _vjAuth.includes(_WH_SERVICE_KEY);\nif (!_vjIsService) {\n"
     "  const _vjRl = await checkSoloRateLimit(_vjDb, soloRateLimitKey(_vjAuthUid, _vjIp));\n}", True),
    ("post-fix voice-journal-agent", "voice-journal-agent", ["voice-journal"],
     "const _vjIsService = !!_WH_SERVICE_KEY && _vjAuth.includes(_WH_SERVICE_KEY);\n"
     "const _vjViaGateway = await isTrustedGatewayForward(req);\nif (!_vjIsService && !_vjViaGateway) {\n"
     "  const _vjRl = await checkSoloRateLimit(_vjDb, soloRateLimitKey(_vjAuthUid, _vjIp));\n}", False),
    ("pre-fix asset-brain-query: hive bucket unguarded (route quota is fine)", "asset-brain-query", ["asset-brain"],
     'try { const _rq = await checkRouteRateLimit(db, hive_id || "", "asset-brain-query"); } catch {}\n'
     "const rl = await checkAIRateLimit(db, hive_id, RATE_LIMIT_PER_HOUR);", True),
    ("post-fix asset-brain-query", "asset-brain-query", ["asset-brain"],
     'try { const _rq = await checkRouteRateLimit(db, hive_id || "", "asset-brain-query"); } catch {}\n'
     "const viaGateway = await isTrustedGatewayForward(req);\nif (!viaGateway) {\n"
     "  const rl = await checkAIRateLimit(db, hive_id, RATE_LIMIT_PER_HOUR);\n}", False),
    ("pre-fix ai-orchestrator: skips only a service-role bearer the gateway never sends", "ai-orchestrator",
     ["assistant", "coach"],
     "if (!(_bearer && _serviceKey && _bearer === _serviceKey)) {\n"
     '  const _rl = await checkAIRateLimit(db, hive_id || "");\n}', True),
    ("skip on the body flag, not the header", "x", ["x"],
     "const viaGateway = body.gateway === true;\nif (!viaGateway) { await checkAIRateLimit(db, h); }", True),
    ("trust held in a reassignable let", "x", ["x"],
     "let t = await isTrustedGatewayForward(req);\nt = t || body.gateway === true;\n"
     "if (!t) { await checkAIRateLimit(db, h); }", True),
    ("pre-fix temporal-rag: inline counter in a local function, unguarded", "temporal-rag-orchestrator",
     ["temporal-rag"],
     "async function checkRateLimit(db: SupabaseClient, hiveId: string): Promise<{ allowed: boolean }> {\n"
     '  const { data } = await db.from("ai_rate_limits").select("call_count").eq("hive_id", hiveId).maybeSingle();\n'
     '  await db.from("ai_rate_limits").update({ call_count: data.call_count + 1 }).eq("hive_id", hiveId);\n'
     "  return { allowed: true };\n}\nconst rl = await checkRateLimit(db, hiveId);", True),
    ("post-fix temporal-rag: count on the direct path, read-only threshold on a forward", "temporal-rag-orchestrator",
     ["temporal-rag"],
     "async function checkRateLimit(db: SupabaseClient, hiveId: string): Promise<{ allowed: boolean }> {\n"
     '  await db.from("ai_rate_limits").update({ call_count: 2 }).eq("hive_id", hiveId);\n  return { allowed: true };\n}\n'
     "async function capRead(db: SupabaseClient, hiveId: string): Promise<boolean> {\n"
     '  const { data } = await db.from("ai_rate_limits").select("call_count").eq("hive_id", hiveId).maybeSingle();\n'
     "  return data.call_count > 30;\n}\nconst viaGateway = await isTrustedGatewayForward(req);\nlet hit: boolean;\n"
     "if (viaGateway) {\n  hit = await capRead(db, hiveId);\n} else {\n  const rl = await checkRateLimit(db, hiveId);\n"
     "  hit = !rl.allowed;\n}", False),
    ("an inline write to the person's bucket", "x", ["x"],
     'await db.from("ai_user_rate_limits").update({ call_count: n + 1 }).eq("user_id", uid);', True),
    ("a local wrapper around the shared limiter", "x", ["x"],
     "async function gate(db, h) { return await checkAIRateLimit(db, h); }\nconst r = await gate(db, h);", True),
    ("else-branch of a condition that is not the bare trust value", "x", ["x"],
     "const t = await isTrustedGatewayForward(req);\nif (t && quiet) { x(); } else { await checkAIRateLimit(db, h); }",
     True),
    ("the global pool, re-spent on a forward", "x", ["x"], 'const gb = await checkGlobalAIBudget(db, "voice");', True),
    ("route quota keyed on the gateway's own agent id", "voice-action-router", ["voice-action"],
     'const _rq = await checkRouteRateLimit(db, h, "voice-action");', True),
    ("route quota with a computed key", "x", ["x"], "const _rq = await checkRouteRateLimit(db, h, routeName);", True),
    ("post-fix router: solo + hive skipped on a forward, route quota on both doors", "voice-action-router",
     ["voice-action"],
     "const viaGateway = await isTrustedGatewayForward(req);\nif (!viaGateway && soloUid) {\n"
     "  const srl = await checkSoloRateLimit(db, soloRateLimitKey(soloUid, _ip), undefined, undefined, _ip || null);\n"
     '} else if (!soloUid) {\n  try { const _rq = await checkRouteRateLimit(db, verifiedHiveId, "voice-action-router"); } '
     "catch {}\n  if (!viaGateway) {\n    const rl = await checkAIRateLimit(db, verifiedHiveId, RATE_LIMIT_PER_HOUR);\n  }\n}",
     False),
    ("a call that exists only in a comment", "x", ["x"], "// await checkAIRateLimit(db, h);\nconst y = 1;", False),
    ("a regex literal holding backticks and a prompt holding braces do not break the structure", "x", ["x"],
     'const out = String(raw).replace(/```json|```/g, "").trim();\nconst P = `{ "a": 1 } if (x) {`;\n'
     "const t = await isTrustedGatewayForward(req);\nif (!t) { await checkAIRateLimit(db, h); }", False),
    ("marketplace triage counting the gateway's own person bucket on a forward (unguarded)",
     "marketplace-listing-assist", ["service-triage"],
     "if (ident.authUid) {\n  const trl = await checkSoloRateLimit(_db, soloRateLimitKey(ident.authUid, null), 20, 100, null, true);\n}",
     True),
    ("marketplace triage: counts on the direct door, reads on a forward; listing path kept as unreachable",
     "marketplace-listing-assist", ["service-triage"],
     "if (ident.authUid) {\n  const triageViaGateway = await isTrustedGatewayForward(req);\n  let trl;\n"
     "  if (triageViaGateway) {\n    trl = await peekSoloRateLimit(_db, soloRateLimitKey(ident.authUid, null), 20, 100);\n"
     "  } else {\n    trl = await checkSoloRateLimit(_db, soloRateLimitKey(ident.authUid, null), 20, 100, null, true);\n  }\n}\n"
     "const rl = verifiedHiveId\n  ? await checkAIRateLimit(db, verifiedHiveId, RATE_LIMIT_PER_HOUR)\n"
     "  : await checkSoloRateLimit(db, soloRateLimitKey(soloUid, null), RATE_LIMIT_PER_HOUR, DEFAULT_RATE_LIMIT_PER_DAY, null, true);",
     False),
]


def self_test() -> int:
    bad = []
    for label, src, want in S1_CASES:
        if bool(body_flag_limiter_skips(src)) != want:
            bad.append(f"S1 {label}: expected {'a finding' if want else 'clean'}")
    for label, fn, agents, src, want in S5_CASES:
        got = target_limiter_audit(fn, src, agents, S5_GW)["findings"]
        if bool(got) != want:
            bad.append(f"S5 {label}: expected {'a finding' if want else 'clean'}, got {got[:2]}")
    # the KEEP for the listing path holds only while the gateway pins the triage mode
    unpinned = target_limiter_audit("marketplace-listing-assist", S5_CASES[-1][3], ["service-triage"],
                                    'const AGENT_ROUTES = { "service-triage": { fn: "marketplace-listing-assist" } };')
    if not unpinned["findings"]:
        bad.append("S5 KEEP 'unreachable by a forward' still passed after the gateway stopped pinning the mode")
    pre = router_static(PRE_FIX_ROUTER)
    for tag in ("S2:", "S1:", "S4:"):
        if not any(x.startswith(tag) for x in pre):
            bad.append(f"pre-fix router: no {tag} finding")
    if router_static(POST_FIX_ROUTER):
        bad.append(f"post-fix router flagged: {router_static(POST_FIX_ROUTER)}")
    if not gateway_static(GW_PRE):
        bad.append("pre-fix gateway forward passed S3")
    if gateway_static(GW_POST):
        bad.append(f"post-fix gateway forward flagged: {gateway_static(GW_POST)}")
    if not gateway_static(GW_WRONG_BEARER):
        bad.append("a header minted over a different bearer than the forward sends passed S3")
    rail = RAIL.read_text(encoding="utf-8")
    trust = TRUST.read_text(encoding="utf-8")
    base_fails, _ = run_behaviour(rail, trust)
    if base_fails:
        bad.append(f"the REAL modules fail behaviour: {base_fails[:3]}")
    killed = 0
    for label, which, anchor, repl in MUTANTS:
        src = rail if which == "rail" else trust
        if anchor not in src:
            bad.append(f"mutant '{label}': anchor not found (stale mutant)")
            continue
        mutated = src.replace(anchor, repl, 1)
        mf, _ = run_behaviour(mutated if which == "rail" else rail, mutated if which == "trust" else trust)
        if mf:
            killed += 1
        else:
            bad.append(f"mutant '{label}' SURVIVED")
    if bad:
        for b in bad:
            print(f"  {RED}x{RST} {b}")
        print(f"{RED}SELF-TEST FAIL{RST}")
        return 1
    print(f"{GREEN}SELF-TEST PASS: {len(S1_CASES)} S1 cases; {len(S5_CASES)} S5 cases (the pre-fix voice-journal, "
          f"asset-brain, ai-orchestrator and temporal-rag gates fail, their fixes pass) + the KEEP pin; pre-fix router "
          f"fails S1+S2+S4 and pre-fix gateway fails S3; post-fix passes; {killed}/{len(MUTANTS)} behavioural mutants "
          f"KILLED{RST}")
    return 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else main())
