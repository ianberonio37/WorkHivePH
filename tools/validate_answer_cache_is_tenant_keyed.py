#!/usr/bin/env python3
"""validate_answer_cache_is_tenant_keyed.py - an ANSWER cache is keyed on, and read by, the VERIFIED tenant.

THE FINDING (2026-10-07, eval-bench work, confirmed from source). ai-gateway's adaptive cache - served instead of a 429
when a person is rate-limited, and instead of the platform-busy refusal when the org budget is spent, with
usage.served_from = 'adaptive_cache' - was keyed on sha256('ai-gateway-adaptive:gateway:<agent>:<message>'). No tenant.
Every answer it stores is grounded in the asker's own hive (live ops snapshot, a machine's logbook history, the team) or,
for a hive-less person, their own logbook, journal and memory. A rate-limited person in hive B who typed the same words
as someone in hive A was served hive A's answer; an anonymous voice-journal caller could be served a signed-in person's.

RULES
  R1 INVENTORY   every ai_cache call site in supabase/functions (cached / cacheLookup / cacheStore, or a raw
                 .from("ai_cache")) is CLASSIFIED below. An unclassified site fails: nobody has said whether what it
                 stores can carry one tenant's records.
  R2 TENANT-FREE a site may stay unscoped only with evidence that its output holds nothing the caller did not send:
                 its system prompt is a constant (no ${...}) and its key interpolates only the caller's own input.
  R3 ANSWER      the answer cache ('ai-gateway-adaptive') is reached ONLY through _shared/cache.ts
                 answerCacheLookup / answerCacheStore - never a direct cacheLookup/cacheStore/cached, never the model
                 literal hashed by hand (that is how the eval runner's reset key drifted from the gateway's).
  R4 HELPER      (behavioural, the REAL cache.ts under Node, stubbed db) a row filed for tenant A is not served to
                 tenant B, to a hive-mate, to the same person in another hive, or with no tenant; a row at A's key that
                 does not NAME tenant A (a pre-fix row) is not served; no-tenant writes nothing; A is still served A's.
  R5 GATEWAY     the tenant is answerCacheTenant(verifiedHiveId, authUid), verifiedHiveId is assigned only from
                 resolveTenancy's proven hive and authUid only from the verified user - never the client's hive_id -
                 and every answer-cache read/write passes that tenant; every served_from 'adaptive_cache' reply comes
                 from such a read.
  R6 RAG STAGES  agentic-rag-loop's Grader and Checker (outputs name and quote one tenant's records; keys cover only a
                 prefix of them) are keyed on tenantScope, built from the verified hive and the personal-lane identity.

USAGE:      python tools/validate_answer_cache_is_tenant_keyed.py
Self-test:  python tools/validate_answer_cache_is_tenant_keyed.py --self-test
            (the pre-fix HEAD sources and 10 mutants of the current sources must FAIL; the current sources PASS)
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
CACHE_TS = "_shared/cache.ts"
GATEWAY = "ai-gateway/index.ts"
RAG = "agentic-rag-loop/index.ts"
GREEN, RED, DIM, RST = "\033[92m", "\033[91m", "\033[2m", "\033[0m"

ANSWER_MODELS = {"ai-gateway-adaptive"}

# model -> (file, constant system prompt, identifiers the key may interpolate, why it holds no tenant data)
TENANT_FREE = {
    "agentic-rag-router": (RAG, "ROUTER_SYSTEM", {"question"},
                           "route JSON from a constant prompt + the caller's question; no records in the prompt"),
    "voice-action-router": ("voice-action-router/index.ts", "ROUTER_SYSTEM", {"personaKey", "userPrompt"},
                            "intent JSON from persona block + the caller's transcript/page/asset id; hive assets "
                            "are resolved AFTER the cached call"),
    "voice-report-intent": ("voice-report-intent/index.ts", "INTENT_SYSTEM", {"safeTranscript"},
                            "report-intent JSON from a constant prompt + the caller's transcript"),
}
# model -> (file, the identifier its key must interpolate)
TENANT_SCOPED = {
    "agentic-rag-grader":  (RAG, "tenantScope"),
    "agentic-rag-checker": (RAG, "tenantScope"),
}
# an input to a tenant-free key must not itself be built from tenant data
TENANT_WORDS = re.compile(r"\b(hive|hiveId|hive_id|verifiedHiveId|chunks?|catalog|block|kept|memory\w*|authUid|"
                          r"auth_uid|worker\w*|answer|snapshot|rows?|data)\b")


def strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    return re.sub(r"(?m)(^|[^:\"'`\\])//.*$", r"\1", src)


def call_args(s: str, open_paren: int) -> list[str]:
    """Top-level arguments of the call whose '(' is at open_paren (strings and template literals respected)."""
    args, depth, cur, i, quote = [], 0, [], open_paren + 1, None
    while i < len(s):
        ch = s[i]
        if quote:
            cur.append(ch)
            if ch == "\\" and i + 1 < len(s):
                cur.append(s[i + 1]); i += 2; continue
            if ch == quote:
                quote = None
        elif ch in "\"'`":
            quote = ch; cur.append(ch)
        elif ch in "([{":
            depth += 1; cur.append(ch)
        elif ch in ")]}":
            if depth == 0:
                args.append("".join(cur).strip()); return args
            depth -= 1; cur.append(ch)
        elif ch == "," and depth == 0:
            args.append("".join(cur).strip()); cur = []
        else:
            cur.append(ch)
        i += 1
    return args


def literal(expr: str) -> str | None:
    m = re.fullmatch(r"\s*([\"'])([^\"'`]*)\1\s*", expr or "")
    return m.group(2) if m else None


def key_interpolations(s: str, key_expr: str, pos: int | None = None) -> set[str] | None:
    """Identifiers interpolated into a cache key (the template itself, or the NEAREST const of that name before the
    call - one file can hold several `const cacheKey`, one per stage)."""
    tpl = key_expr.strip()
    if re.fullmatch(r"[A-Za-z_$][\w$]*", tpl):
        found = [m for m in re.finditer(r"\bconst\s+" + re.escape(tpl) + r"\s*=\s*(`[^`]*`)\s*;", s)
                 if pos is None or m.start() < pos]
        if not found:
            return None
        tpl = found[-1].group(1)
    if not tpl.startswith("`"):
        return None
    names: set[str] = set()
    for inner in re.findall(r"\$\{([^}]*)\}", tpl):
        names |= set(re.findall(r"[A-Za-z_$][\w$]*", inner)) - {"slice", "length", "String", "toLowerCase"}
    return names


def sites(srcs: dict[str, str]) -> list[dict]:
    """Every ai_cache call site outside _shared/cache.ts."""
    out = []
    for rel, raw in srcs.items():
        if rel == CACHE_TS or rel.endswith(".test.ts"):
            continue
        s = strip_comments(raw)
        for m in re.finditer(r"\b(cached|cacheLookup|cacheStore)\s*(?:<[^()]*?>)?\s*\(", s):
            if re.search(r"(function|import\s*\{[^}]*)\s*$", s[max(0, m.start() - 40):m.start()]):
                continue
            a = call_args(s, m.end() - 1)
            fn = m.group(1)
            model_expr, key_expr = (a[2] if len(a) > 2 else "", a[1] if len(a) > 1 else "") if fn == "cacheStore" \
                else (a[1] if len(a) > 1 else "", a[2] if len(a) > 2 else "")
            out.append({"file": rel, "fn": fn, "model": literal(model_expr), "model_expr": model_expr,
                        "key": key_expr, "src": s, "pos": m.start()})
        for m in re.finditer(r"\.from\(\s*[\"']ai_cache[\"']\s*\)", s):
            out.append({"file": rel, "fn": ".from('ai_cache')", "model": None, "model_expr": "(raw table access)",
                        "key": "", "src": s})
        for m in re.finditer(r"[\"'`]ai-gateway-adaptive[:\"'`]", s):
            out.append({"file": rel, "fn": "literal", "model": "ai-gateway-adaptive", "model_expr": m.group(0),
                        "key": "", "src": s})
    return out


def check_inventory(srcs: dict[str, str]) -> list[str]:
    fails = []
    for st in sites(srcs):
        where = f"{st['file']} {st['fn']}({st['model_expr'][:40]})"
        model = st["model"]
        if model in ANSWER_MODELS:
            fails.append(f"R3 {where}: the answer cache reached directly - it must go through answerCacheLookup/"
                         "answerCacheStore (keyed on, and checked against, the verified tenant)")
            continue
        if model is None:
            fails.append(f"R1 {where}: an ai_cache access that cannot be classified (no literal model / raw table)")
            continue
        s = st["src"]
        if model in TENANT_SCOPED:
            want_file, ident = TENANT_SCOPED[model]
            names = key_interpolations(s, st["key"], st.get("pos"))
            if st["file"] != want_file or names is None or ident not in names:
                fails.append(f"R6 {where}: key `{st['key'][:70]}` does not interpolate ${{{ident}}} - its output "
                             "names one tenant's records and the key covers only a prefix of them")
            continue
        if model in TENANT_FREE:
            want_file, sys_const, allowed, _why = TENANT_FREE[model]
            if st["file"] != want_file:
                fails.append(f"R2 {where}: '{model}' is registered tenant-free for {want_file} only")
                continue
            m = re.search(r"\bconst\s+" + sys_const + r"\s*=\s*`([^`]*)`", s)
            if not m or "${" in m.group(1):
                fails.append(f"R2 {where}: {sys_const} is not a constant template - a tenant value could be in "
                             "the prompt, so the cached output could carry it")
            names = key_interpolations(s, st["key"], st.get("pos"))
            if names is None or not names <= allowed:
                fails.append(f"R2 {where}: key interpolates {sorted(names or [])}, outside the caller-input set "
                             f"{sorted(allowed)}")
            for n in (names or set()) & allowed:
                a = re.search(r"\bconst\s+" + re.escape(n) + r"\s*=\s*(.+?);\s*$", s, re.S | re.M)
                if a and TENANT_WORDS.search(a.group(1)[:600]):
                    fails.append(f"R2 {where}: key input `{n}` is built from tenant data: {a.group(1)[:80]}")
            continue
        fails.append(f"R1 {where}: unclassified ai_cache model '{model}' - register it as tenant-free (with evidence) "
                     "or key it on the verified tenant")
    return fails


def check_gateway(gw_raw: str) -> list[str]:
    s = strip_comments(gw_raw)
    fails = []
    m = re.search(r"\bconst\s+answerTenant\s*=\s*answerCacheTenant\(\s*([^,]+?)\s*,\s*([^)]+?)\s*\)\s*;", s)
    if not m:
        return ["R5 ai-gateway: no `const answerTenant = answerCacheTenant(<verified hive>, <verified uid>)` - the "
                "answer cache has no verified tenant"]
    if (m.group(1), m.group(2)) != ("verifiedHiveId", "authUid"):
        fails.append(f"R5 ai-gateway: answerTenant is built from ({m.group(1)}, {m.group(2)}), not "
                     "(verifiedHiveId, authUid) - a client-sent id must never key a tenant's answers")
    for rhs in re.findall(r"(?<![=!<>.\w])verifiedHiveId\s*(?::[^=;]+)?=(?!=)\s*([^;]+);", s):
        if rhs.strip() not in ("null", "tenancy.hive_id"):
            fails.append(f"R5 ai-gateway: verifiedHiveId assigned from `{rhs.strip()[:60]}` - only resolveTenancy's "
                         "proven hive may be")
    if not re.search(r"\btenancy\s*=\s*await\s+resolveTenancy\(", s):
        fails.append("R5 ai-gateway: verifiedHiveId's tenancy no longer comes from resolveTenancy")
    for rhs in re.findall(r"(?<![=!<>.\w])authUid\s*(?::[^=;]+)?=(?!=)\s*([^;]+);", s):
        if rhs.strip() not in ("null", "user.id"):
            fails.append(f"R5 ai-gateway: authUid assigned from `{rhs.strip()[:60]}` - only the verified user's id may be")
    calls = list(re.finditer(r"\b(answerCacheLookup|answerCacheStore)\s*\(", s))
    for c in calls:
        a = call_args(s, c.end() - 1)
        if len(a) < 2 or a[1] != "answerTenant":
            fails.append(f"R5 ai-gateway: {c.group(1)}(..., {a[1] if len(a) > 1 else '?'}, ...) - the tenant argument "
                         "must be answerTenant")
    served = [x.start() for x in re.finditer(r"served_from\s*:\s*[\"']adaptive_cache[\"']", s)]
    for pos in served:
        if not re.search(r"answerCacheLookup\(\s*adminClient\s*,\s*answerTenant\b", s[max(0, pos - 700):pos]):
            fails.append("R5 ai-gateway: a reply marked served_from 'adaptive_cache' does not come from "
                         "answerCacheLookup(adminClient, answerTenant, ...)")
    if served and not any(c.group(1) == "answerCacheStore" for c in calls):
        fails.append("R5 ai-gateway: adaptive replies are served but nothing files them under answerTenant")
    return fails


def check_rag_scope(rag_raw: str) -> list[str]:
    s = strip_comments(rag_raw)
    m = re.search(r"\bconst\s+tenantScope\s*=\s*([^;]+);", s)
    if not m:
        return ["R6 agentic-rag-loop: no tenantScope - the Grader/Checker caches are not scoped to a tenant"]
    fails = []
    if not (re.search(r"\bhiveId\b", m.group(1)) and re.search(r"\beffectiveAuthUid\b", m.group(1))):
        fails.append(f"R6 agentic-rag-loop: tenantScope `{m.group(1)[:80]}` is not built from the verified hive and "
                     "the personal-lane identity (hiveId + effectiveAuthUid)")
    if re.search(r"\bbody\.", m.group(1)):
        fails.append("R6 agentic-rag-loop: tenantScope reads the request body")
    for stage in ("graderStage", "checkerStage"):
        for c in re.finditer(r"(?<!function )\b" + stage + r"\(\s*db\b", s):
            a = call_args(s, s.index("(", c.start()))
            if not a or a[-1] != "tenantScope":
                fails.append(f"R6 agentic-rag-loop: {stage}(...) is not passed tenantScope")
    return fails


NODE_DRIVER = r"""
import { pathToFileURL } from 'node:url';
const mod = await import(pathToFileURL(process.argv[2]).href);
const out = [];
const A = (name, cond) => out.push({ name, pass: !!cond });
function makeDb() {
  const rows = new Map();
  return {
    rows,
    from() {
      let key = null;
      const b = {
        select() { return b; },
        eq(col, val) { if (col === 'key') key = val; return b; },
        maybeSingle() { return Promise.resolve({ data: rows.has(key) ? rows.get(key) : null }); },
        upsert(row) { rows.set(row.key, { ...row }); return Promise.resolve({ error: null }); },
      };
      return b;
    },
    rpc() { return Promise.resolve({}); },
  };
}
const need = ['answerCacheTenant', 'answerCacheKey', 'answerCacheLookup', 'answerCacheStore'];
const missing = need.filter((f) => typeof mod[f] !== 'function');
if (missing.length) {
  A('cache.ts exports ' + missing.join(', ') + ' (the tenant-keyed answer cache)', false);
} else {
  const { answerCacheTenant: T, answerCacheKey: K, answerCacheLookup: L, answerCacheStore: S } = mod;
  const HA = '11111111-aaaa-4aaa-8aaa-000000000001', HB = '22222222-bbbb-4bbb-8bbb-000000000002';
  const UA = 'aaaaaaaa-0000-4000-8000-00000000000a', UB = 'bbbbbbbb-0000-4000-8000-00000000000b';
  const tA = T(HA, UA), tB = T(HB, UB), tMate = T(HA, UB), tOtherHive = T(HB, UA), tSolo = T(null, UA);
  A('no verified uid -> no tenant (anonymous caller)', T(null, null) === null && T(HA, null) === null && T(HA, '') === null);
  A('tenant names the proven hive AND the person', typeof tA === 'string' && tA.includes(HA) && tA.includes(UA));
  A('a hive-mate is a different tenant', tMate && tMate !== tA);
  A('the same person in another hive is a different tenant', tOtherHive && tOtherHive !== tA);
  A('the same person with no hive is a different tenant', tSolo && tSolo !== tA);
  const db = makeDb();
  const agent = 'voice-journal', q = 'How many open jobs do we have?';
  await S(db, tA, agent, q, 'Hive A: 7 open jobs on PMP-001 (Juan Dela Cruz)', 3600);
  A('a tenant-A write files exactly one row', db.rows.size === 1);
  A('tenant A is served its own answer', (await L(db, tA, agent, q)) === 'Hive A: 7 open jobs on PMP-001 (Juan Dela Cruz)');
  A('read and write share one normalised key (spaced message still hits)', (await L(db, tA, agent, '  How many open   jobs do we have? ')) !== null);
  A('tenant B is NOT served tenant A\'s answer', (await L(db, tB, agent, q)) === null);
  A('a hive-mate is NOT served it', (await L(db, tMate, agent, q)) === null);
  A('the same person in another hive is NOT served it', (await L(db, tOtherHive, agent, q)) === null);
  A('no tenant is NOT served it', (await L(db, null, agent, q)) === null);
  A('another agent is NOT served it', (await L(db, tA, 'asset-brain', q)) === null);
  const db2 = makeDb();
  await S(db2, null, agent, q, 'anonymous answer', 3600);
  A('a caller with no tenant caches nothing', db2.rows.size === 0);
  const db3 = makeDb();
  const kA = await K(tA, agent, q);
  db3.rows.set(kA, { key: kA, model: 'ai-gateway-adaptive', response_json: { answer: 'pre-fix row' }, expires_at: new Date(Date.now() + 3600e3).toISOString() });
  A('a row at A\'s key that does not NAME a tenant (pre-fix shape) is not served', (await L(db3, tA, agent, q)) === null);
  db3.rows.set(kA, { key: kA, model: 'ai-gateway-adaptive', response_json: { answer: 'B row', tenant: tB }, expires_at: new Date(Date.now() + 3600e3).toISOString() });
  A('a row at A\'s key naming ANOTHER tenant is not served', (await L(db3, tA, agent, q)) === null);
  A('the tenant is part of the key', kA !== (await K(tB, agent, q)) && kA !== (await K(tMate, agent, q)));
}
process.stdout.write(JSON.stringify(out));
"""


def check_helper(cache_raw: str) -> list[str]:
    node = shutil.which("node")
    if not node:
        return ["R4 node is not on PATH - the helper's behaviour cannot be proven (fail-closed)"]
    src = re.sub(r'^import\s*\{\s*SupabaseClient\s*\}\s*from\s*"[^"]*";', "type SupabaseClient = any;",
                 cache_raw.replace("\r\n", "\n"), flags=re.M)
    if "esm.sh" in src:
        return ["R4 could not neutralise cache.ts's supabase-js import for the Node harness"]
    # cache.ts reads "a model replied" from ai-chain.ts (2026-10-12: a no-answer is never cached). The harness has no
    # ai-chain.ts beside its copy, so the REAL aiAnswered() is copied in place of the import - one definition, not a stub.
    chain_imp = re.compile(r'^import\s*\{\s*aiAnswered\s*\}\s*from\s*"\./ai-chain\.ts";', re.M)
    if chain_imp.search(src):
        chain = (Path(__file__).resolve().parent.parent / "supabase" / "functions" / "_shared" / "ai-chain.ts")
        m = re.search(r"export function aiAnswered\([\s\S]*?\n}\n", chain.read_text(encoding="utf-8").replace("\r\n", "\n")) if chain.exists() else None
        if not m:
            return ["R4 cache.ts imports aiAnswered from ai-chain.ts, and ai-chain.ts holds no aiAnswered() to copy in (fail-closed)"]
        src = chain_imp.sub(lambda _m: m.group(0).replace("export function", "function", 1), src)
    tmp = Path(tempfile.mkdtemp(prefix="acache-"))
    try:
        (tmp / "cache_under_test.ts").write_text(src, encoding="utf-8")
        (tmp / "driver.mjs").write_text(NODE_DRIVER, encoding="utf-8")
        r = subprocess.run([node, "--no-warnings", str(tmp / "driver.mjs"), str(tmp / "cache_under_test.ts")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        if r.returncode != 0:
            return [f"R4 the Node harness could not run cache.ts: {(r.stderr or r.stdout).strip()[:300]}"]
        results = json.loads(r.stdout or "[]")
    except (OSError, ValueError, subprocess.TimeoutExpired) as e:
        return [f"R4 the Node harness failed: {e}"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if not results:
        return ["R4 the Node harness asserted nothing"]
    return [f"R4 cache.ts: {x['name']}" for x in results if not x["pass"]]


def load_current() -> tuple[dict[str, str], str]:
    srcs = {}
    for f in sorted(FUNCS.rglob("*.ts")):
        if "node_modules" in f.parts:
            continue
        srcs[f.relative_to(FUNCS).as_posix()] = f.read_text(encoding="utf-8", errors="replace")
    return srcs, srcs.get(CACHE_TS, "")


def check_all(srcs: dict[str, str], cache_raw: str) -> list[str]:
    return (check_inventory(srcs) + check_gateway(srcs.get(GATEWAY, "")) + check_rag_scope(srcs.get(RAG, ""))
            + check_helper(cache_raw))


def main() -> int:
    print("answer-cache-is-tenant-keyed: an answer cache is keyed on, and read by, the VERIFIED tenant")
    srcs, cache_raw = load_current()
    n_sites = len(sites(srcs))
    fails = check_all(srcs, cache_raw)
    for f in fails:
        print(f"  {RED}x{RST} {f}")
    if fails:
        print(f"{RED}FAIL answer-cache-is-tenant-keyed - {len(fails)} finding(s) over {n_sites} ai_cache site(s){RST}")
        return 1
    free = ", ".join(sorted(TENANT_FREE))
    print(f"  {DIM}tenant-free (constant prompt + caller input only): {free}{RST}")
    print(f"  {DIM}tenant-scoped: ai-gateway-adaptive (hive+uid, via answerCache*), {', '.join(sorted(TENANT_SCOPED))}{RST}")
    print(f"{GREEN}PASS answer-cache-is-tenant-keyed - {n_sites} ai_cache site(s) classified; the adaptive answer "
          f"cache is filed and served per verified tenant (behaviour proven on the real cache.ts){RST}")
    return 0


def git_head(rel: str) -> str | None:
    try:
        r = subprocess.run(["git", "show", f"HEAD:supabase/functions/{rel}"], cwd=ROOT, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=30)
        return r.stdout if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def self_test() -> int:
    srcs, cache_raw = load_current()
    cases: list[tuple[str, dict[str, str], str, bool]] = []   # name, srcs, cache, expect_fail

    head = dict(srcs)
    for rel in (CACHE_TS, GATEWAY, RAG, "ai-eval-runner/index.ts"):
        h = git_head(rel)
        if h is None:
            print(f"{RED}SELF-TEST cannot read HEAD:{rel}{RST}")
            return 1
        head[rel] = h
    cases.append(("pre-fix HEAD sources (cache.ts + gateway + rag loop + eval runner)", head, head[CACHE_TS], True))

    def mut(rel: str, old: str, new: str, name: str, on_cache: bool = False):
        base = cache_raw if on_cache else srcs[rel]
        if old not in base:
            print(f"{RED}SELF-TEST mutant '{name}' no longer applies - its anchor text is gone; update the mutant{RST}")
            sys.exit(1)
        if on_cache:
            cases.append((name, srcs, base.replace(old, new, 1), True))
        else:
            s2 = dict(srcs); s2[rel] = base.replace(old, new, 1)
            cases.append((name, s2, cache_raw, True))

    mut(CACHE_TS, "return `gateway:v2:${tenant}:${agent}:${normalize(message)}`;",
        "return `gateway:v2:${agent}:${normalize(message)}`;",
        "M1 cache.ts: tenant dropped from the key", on_cache=True)
    mut(CACHE_TS, "|| hit.data.tenant !== tenant", "", "M2 cache.ts: read stops requiring the stored tenant",
        on_cache=True)
    mut(CACHE_TS, "return hive ? `hive:${hive}|user:${uid}` : `user:${uid}`;", "return `user:${uid}`;",
        "M3 cache.ts: tenant ignores the proven hive", on_cache=True)
    mut(CACHE_TS, "return hive ? `hive:${hive}|user:${uid}` : `user:${uid}`;",
        "return hive ? `hive:${hive}` : `user:${uid}`;", "M4 cache.ts: tenant ignores the person (hive-mates share)",
        on_cache=True)
    mut(GATEWAY, "answerCacheTenant(verifiedHiveId, authUid)", "answerCacheTenant(hive_id, authUid)",
        "M5 gateway: tenant built from the client's hive_id")
    mut(GATEWAY, "await answerCacheLookup(adminClient, answerTenant, agent, message);",
        "await answerCacheLookup(adminClient, answerCacheTenant(String(hive_id), authUid), agent, message);",
        "M6 gateway: one read passes a tenant other than answerTenant")
    mut(GATEWAY, "const cachedAnswer = await answerCacheLookup(adminClient, answerTenant, agent, message);",
        "const { cacheLookup } = await import(\"../_shared/cache.ts\");\n        const cachedAnswer = (await cacheLookup<{ answer: string }>(adminClient, \"ai-gateway-adaptive\", `gateway:${agent}:${message}`)).data?.answer;",
        "M7 gateway: the pre-fix direct read (agent + message only) comes back")
    mut(RAG, "const cacheKey = `grader:${tenantScope}:${question}", "const cacheKey = `grader:${question}",
        "M8 rag loop: Grader key loses tenantScope")
    s9 = dict(srcs)
    s9["new-fn/index.ts"] = ('import { cached } from "../_shared/cache.ts";\n'
                             'const r = await cached<string>(db, "new-fn-answer", `ans:${hiveId}:${q}`, gen);\n')
    cases.append(("M9 a new, unclassified ai_cache site", s9, cache_raw, True))
    mut("voice-report-intent/index.ts", "const intentCacheKey = `voiceintent:${safeTranscript}`;",
        "const intentCacheKey = `voiceintent:${hive_id}:${safeTranscript}`;",
        "M10 a tenant-free key starts interpolating tenant data")
    cases.append(("CONTROL current sources", srcs, cache_raw, False))

    bad = []
    for name, s, c, expect_fail in cases:
        f = check_all(s, c)
        ok = bool(f) == expect_fail
        tag = f"{GREEN}ok{RST}" if ok else f"{RED}WRONG{RST}"
        verdict = "FAIL" if f else "PASS"
        print(f"  {tag} {name}: {verdict}" + (f" {DIM}({f[0][:110]}){RST}" if f else ""))
        if not ok:
            bad.append(name)
    if bad:
        print(f"{RED}SELF-TEST FAIL: {bad}{RST}")
        return 1
    print(f"{GREEN}SELF-TEST PASS: {len(cases)} cases (pre-fix HEAD + 10 mutants FAIL, current PASSES){RST}")
    return 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else main())
