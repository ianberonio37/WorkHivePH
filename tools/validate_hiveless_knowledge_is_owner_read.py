#!/usr/bin/env python3
"""validate_hiveless_knowledge_is_owner_read.py - a hive-less person's knowledge is read by its OWNER, and by nobody else.

THE FINDING (2026-10-07, from source, while making photo defect capture work for solo owners). A signed-in person with
no hive saves a logbook entry; trg_embed_outbox_logbook queues it and the outbox drain writes the entry's fault_knowledge
row with hive_id NULL. Nobody could ever read it: fault_knowledge_read was `hive_id IN (the caller's active hives)`, and
search_fault_knowledge, search_all_knowledge and v_knowledge_truth all filtered `hive_id = <hive>` - which NULL never
meets. So logbook.html's "Past repairs on this machine" panel was ALWAYS empty for a solo owner, and 6 of the 12
hive-less rows carried no auth_uid at all (neither writer of the table stamped it). Fixed by migration
20261007000014_a_solo_owner_reads_their_own_knowledge.sql. This gate holds BOTH halves of the property - the owner
CAN read, everyone else CANNOT - because a fix for the first half is exactly how the second one breaks.

RULES (live, as the real roles, every probe inside BEGIN ... ROLLBACK - mutates nothing)
  R1 OWNER READS   each hive-less owner, acting as themselves (role authenticated + their JWT sub), sees EVERY one of
                   their hive-less fault_knowledge rows, on the table and through v_knowledge_truth.
  R2 NOBODY ELSE   every other principal - another hive-less owner, active hive members, anon - sees NONE of them,
                   on the table and through the view (what each sees is a subset of their own hive-less rows).
  R3 BOUND OWNER   every hive-less row names its owner: auth_uid equals the author of the logbook entry it copies, no
                   hive-less row is unowned, and tg_bind_owner_fault_knowledge restores an owner a writer left out.
  R4 OWN SEARCH    search_fault_knowledge / search_all_knowledge with match_hive_id NULL return the caller's own
                   hive-less rows (the owner finds their own row), never another person's - not even when the caller
                   NAMES that person in match_owner; anon and a hive member get nothing; service_role naming the owner
                   gets exactly that owner's rows; a hive member's own-hive search still answers (hive path intact).
                   GENERIC (2026-10-08): the same own-scope searches through a prepared statement under
                   force_generic_plan - how PostgREST runs an RPC - return EVERY embedded row of the owner. With
                   literals the planner folds the scope away and reads exactly; bound, 20261007000014's OR predicate
                   rode the ivfflat index (probes=1) and returned 1 of 3. Fixed by 20261008000001.
  R5 INVOKER VIEW  v_knowledge_truth keeps security_invoker (a definer view would read as its owner and bypass R2).
  R6 THE PANEL     logbook.html loadMachineHistory: each fault_knowledge read has a solo branch scoped to the person's
                   own hive-less rows (.is('hive_id', null) + _MINE()), so the panel asks the question the policy answers.

THE AI PATHS (static, from source; added 2026-10-08). The rules above made the rows READABLE; nothing made the AI ASK
for them. ai-gateway built a knowledge block only for a hive (buildKnowledgeContext is reached only from
buildOpsSnapshot), and semantic-search's no-hive path searched on a service-role client with no owner - auth.uid() is
NULL there, so the own scope named nobody. A solo owner's answers never used their own past repairs.
  R7 OWN SEARCH    supabase/functions/_shared/own-knowledge.ts searchOwnFaultKnowledge(admin, embedding, ownerUid, n):
                   returns [] with no owner, asks search_fault_knowledge/search_all_knowledge for match_hive_id null +
                   match_owner = ownerUid, then re-reads each returned id as hive-less AND auth_uid = ownerUid and
                   keeps only those (a defensive filter: an SQL regression shows nothing, never another's rows).
  R8 GATEWAY SOLO  ai-gateway's signed-in no-hive branch (else if (authUid && !hive_id ...)) builds a knowledge
                   block on the SERVICE-ROLE adminClient with authUid as the owner, through a builder that calls
                   searchOwnFaultKnowledge with that owner and labels the block as the person's own ("=== YOUR OWN");
                   authUid is bound only from auth.getUser() (user.id), never from the body or context.
  R9 SEARCH SOLO   semantic-search's no-hive path calls searchOwnFaultKnowledge with an owner bound only from
                   resolveIdentity's authUid; and in either function no fault/all knowledge search is called with a
                   NULL-able hive and no match_owner (the shape that silently returned nothing).
  R10 ORCHESTRATOR (2026-10-08) ai-orchestrator asked semantic-search with the SERVICE-ROLE key for every caller, so a
                   solo person's assistant turn searched as nobody. It now forwards, for a verified non-service caller
                   with no hive only, the request's OWN Authorization (never a body field) through orchestrate()'s
                   searchHeaders; ai-gateway's forward header rides along only after `const X = await
                   isTrustedGatewayForward(req)` holds; and semantic-search skips its solo limiter only under such a
                   verified forward (the gateway already counted the person - counting again halved their budget).

Personas: whoever owns hive-less rows (tools/seed_solo_personas.py seeds jun / boyet), plus up to two active hive members.
A production login (ianphone) is never impersonated. Fewer than two hive-less owners = FAIL, not a vacuous PASS: the
cross-owner half of R2 cannot be proven with one owner (seed with `python tools/seed_solo_personas.py --apply`).

USAGE:      python tools/validate_hiveless_knowledge_is_owner_read.py
Self-test:  python tools/validate_hiveless_knowledge_is_owner_read.py --self-test
            (8 database/page mutants, each applied inside a rolled-back transaction or in memory, plus 16 in-memory
             source mutants for R7-R10, must each FAIL the rule they break; the unmutated database, page and sources
             must PASS)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "logbook.html"
FUNCS = ROOT / "supabase" / "functions"
AI_SOURCES = {
    "gateway": FUNCS / "ai-gateway" / "index.ts",
    "search": FUNCS / "semantic-search" / "index.ts",
    "helper": FUNCS / "_shared" / "own-knowledge.ts",
    "orch": FUNCS / "ai-orchestrator" / "index.ts",
}
DB = "supabase_db_workhive"
US, RS = "\x1f", "\x1e"
GREEN, RED, YEL, DIM, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"
NEVER_ACT_AS = ("%ianphone%",)          # production logins: never impersonated, never probed


def psql(sql: str, timeout: int = 120) -> tuple[int, str, str]:
    try:
        r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-X", "-q",
                            "-t", "-A", "-F", US, "-v", "ON_ERROR_STOP=1"],
                           input=sql, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout)
    except Exception as e:                                   # docker missing / hung
        return 99, "", str(e)
    return r.returncode, r.stdout or "", r.stderr or ""


def lit(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


# ── ground truth (as postgres, read-only) ───────────────────────────────────────────────────────
SUMMARY = ("md5(CONCAT('Machine: ', f.machine, ' | Problem: ', f.problem, "
           "' | Root cause: ', f.root_cause, ' | Fix: ', f.action))")


def ground_truth() -> dict | None:
    excl = " or ".join(f"u.email ilike {lit(p)}" for p in NEVER_ACT_AS)
    sql = f"""
select 'ROW', f.id, coalesce(f.auth_uid::text,''), coalesce(l.auth_uid::text,''),
       (f.embedding is not null)::text, {SUMMARY}
  from public.fault_knowledge f left join public.logbook l on l.id = f.logbook_id
 where f.hive_id is null order by f.created_at, f.id;
select 'EXCL', u.id from auth.users u where {excl};
select 'MEM', m.auth_uid, m.hive_id,
       (select f.id from public.fault_knowledge f where f.hive_id = m.hive_id and f.embedding is not null
         order by f.created_at desc, f.id limit 1)
  from (select distinct on (hm.auth_uid) hm.auth_uid, hm.hive_id
          from public.hive_members hm join auth.users u on u.id = hm.auth_uid
         where hm.status = 'active' and not ({excl})
           and exists (select 1 from public.fault_knowledge f where f.hive_id = hm.hive_id and f.embedding is not null)
           and not exists (select 1 from public.fault_knowledge f where f.hive_id is null and f.auth_uid = hm.auth_uid)
         order by hm.auth_uid, hm.hive_id) m
 order by 2 limit 2;
select 'VIEWOPT', coalesce(array_to_string(c.reloptions, ','), '') from pg_class c
 where c.oid = 'public.v_knowledge_truth'::regclass;
"""
    rc, out, err = psql(sql)
    if rc != 0:
        print(f"  {YEL}SKIP{RST} database unreachable ({(err or '').strip()[:160]})")
        return None
    gt = {"rows": [], "excl": set(), "members": [], "viewopt": ""}
    for ln in out.replace("\r\n", "\n").split("\n"):
        p = ln.split(US)
        if p[0] == "ROW":
            gt["rows"].append({"id": p[1], "owner": p[2], "author": p[3], "embedded": p[4] == "true", "md5": p[5]})
        elif p[0] == "EXCL":
            gt["excl"].add(p[1])
        elif p[0] == "MEM" and p[3]:
            gt["members"].append({"uid": p[1], "hive": p[2], "qrow": p[3]})
        elif p[0] == "VIEWOPT":
            gt["viewopt"] = p[1]
    return gt


# ── the live probe script ───────────────────────────────────────────────────────────────────────
def build_probe(gt: dict, owners: list[str], probe_row: dict, bind_row: str | None, mutation: str) -> str:
    """One psql script: \\gset the query vectors, BEGIN, apply the mutation (if any), then act as every principal and
    print what each could read. ROLLBACK at the end, and psql's ON_ERROR_STOP drops the connection (rolling back)
    if anything fails mid-way - nothing this script does can survive it."""
    out = []
    for i, o in enumerate(owners):
        out.append(f"select embedding::text as q{i} from public.fault_knowledge where id = {lit(probe_row[o])} \\gset")
    for j, m in enumerate(gt["members"]):
        out.append(f"select embedding::text as h{j} from public.fault_knowledge where id = {lit(m['qrow'])} \\gset")
    out.append("BEGIN;")
    out.append("SET LOCAL lock_timeout = '5s';")
    out.append("SET LOCAL statement_timeout = '60s';")
    if mutation:
        out.append(mutation)
    if bind_row:
        # R3 behavioural: a writer that leaves the owner out must not leave the row unowned.
        out.append(f"UPDATE public.fault_knowledge SET auth_uid = NULL WHERE id = {lit(bind_row)};")
        out.append(f"SELECT 'BIND' || chr(31) || coalesce(auth_uid::text, '') FROM public.fault_knowledge "
                   f"WHERE id = {lit(bind_row)};")

    principals = [("owner:" + o, "authenticated", {"sub": o, "role": "authenticated"}) for o in owners]
    principals += [("member:" + m["uid"], "authenticated", {"sub": m["uid"], "role": "authenticated"})
                   for m in gt["members"]]
    principals += [("anon", "anon", {"role": "anon"}), ("service_role", "service_role", {"role": "service_role"})]

    agg = "coalesce((select string_agg(x, chr(30)) from ({q}) t(x)), '')"
    for label, role, claims in principals:
        out.append(f"SELECT set_config('request.jwt.claims', {lit(json.dumps(claims))}, true);")
        out.append(f"SET LOCAL ROLE {role};")
        if role != "service_role":
            t = agg.format(q="select id::text from public.fault_knowledge where hive_id is null")
            v = agg.format(q="select id::text from public.v_knowledge_truth where hive_id is null and source = 'fault'")
            out.append(f"SELECT 'T' || chr(31) || {lit(label)} || chr(31) || {t};")
            out.append(f"SELECT 'V' || chr(31) || {lit(label)} || chr(31) || {v};")
        for i, o in enumerate(owners):
            s = agg.format(q=f"select id::text from public.search_fault_knowledge(:'q{i}'::vector, NULL, 1000, "
                             f"{lit(o)}::uuid)")
            a = agg.format(q=f"select md5(summary) from public.search_all_knowledge(:'q{i}'::vector, NULL, 1000, "
                             f"{lit(o)}::uuid) where source = 'fault'")
            out.append(f"SELECT 'S' || chr(31) || {lit(label)} || chr(31) || {lit(o)} || chr(31) || {s};")
            out.append(f"SELECT 'A' || chr(31) || {lit(label)} || chr(31) || {lit(o)} || chr(31) || {a};")
        if label.startswith("member:"):
            j = [m["uid"] for m in gt["members"]].index(label.split(":", 1)[1])
            hive = gt["members"][j]["hive"]
            h = agg.format(q=f"select id::text from public.search_fault_knowledge(:'h{j}'::vector, "
                             f"{lit(hive)}::uuid, 5)")
            out.append(f"SELECT 'H' || chr(31) || {lit(label)} || chr(31) || {h};")
        if label == "service_role":
            # R4 GENERIC: the calls above pass LITERALS, so the planner folds match_hive_id NULL away and reads the
            # hive-less rows exactly. PostgREST binds an RPC's arguments: the plan is generic, and 20261007000014's
            # single OR predicate then rode the ivfflat index (probes=1) and returned 1 of an owner's 3 rows. So the
            # own scope is also asked here through a prepared statement under force_generic_plan, with a question
            # vector that is NOT the owner's own row (a hive row), and must return every embedded row of theirs.
            qv = ":'h0'" if gt["members"] else ":'q0'"
            out.append("SET LOCAL plan_cache_mode = force_generic_plan;")
            out.append("PREPARE own_g(vector, uuid, integer, uuid) AS "
                       "SELECT id::text FROM public.search_fault_knowledge($1, $2, $3, $4);")
            out.append("PREPARE own_ga(vector, uuid, integer, uuid) AS "
                       "SELECT md5(summary) FROM public.search_all_knowledge($1, $2, $3, $4) WHERE source = 'fault';")
            for o in owners:
                out.append(f"SELECT 'GB' || chr(31) || {lit(o)};")
                out.append(f"EXECUTE own_g({qv}::vector, NULL, 1000, {lit(o)}::uuid);")
                out.append(f"SELECT 'GAB' || chr(31) || {lit(o)};")
                out.append(f"EXECUTE own_ga({qv}::vector, NULL, 1000, {lit(o)}::uuid);")
                out.append("SELECT 'GE';")
            out.append("SET LOCAL plan_cache_mode = auto;")
        out.append("RESET ROLE;")
    out.append("ROLLBACK;")
    return "\n".join(out) + "\n"


def parse_probe(stdout: str) -> dict:
    res = {"T": {}, "V": {}, "S": {}, "A": {}, "H": {}, "G": {}, "GA": {}, "BIND": None}
    # split('\n'), NEVER splitlines(): str.splitlines() also breaks on \x1c-\x1e, so the RS-joined id lists were cut
    # into one id per "line" and every owner read as seeing 1 of their N rows - this gate's first run reported a false
    # R1 failure for all three owners from that alone.
    collecting: set | None = None          # the generic-plan EXECUTEs print bare rows between GB/GAB and GE
    for ln in stdout.replace("\r\n", "\n").split("\n"):
        p = ln.split(US)
        k = p[0]
        if k in ("GB", "GAB") and len(p) >= 2:
            collecting = res["G" if k == "GB" else "GA"].setdefault(p[1], set())
            continue
        if k == "GE":
            collecting = None
            continue
        if collecting is not None:
            if ln.strip():
                collecting.add(ln.strip())
            continue
        if k == "BIND":
            res["BIND"] = p[1] if len(p) > 1 else ""
        elif k in ("T", "V", "H") and len(p) >= 3:
            res[k][p[1]] = set(x for x in p[2].split(RS) if x)
        elif k in ("S", "A") and len(p) >= 4:
            res[k][(p[1], p[2])] = set(x for x in p[3].split(RS) if x)
    return res


# ── R6: the panel asks the question the policy answers ─────────────────────────────────────────
def check_page(src: str) -> list[str]:
    m = re.search(r"async function loadMachineHistory\(", src)
    if not m:
        return ["R6 logbook.html has no loadMachineHistory - the past-repairs panel moved; re-point this gate"]
    end = src.find("\n}\n", m.end())
    body = src[m.start(): end if end > 0 else len(src)]
    reads = len(re.findall(r"from\(\s*['\"]fault_knowledge['\"]\s*\)", body))
    solo = [ln for ln in body.splitlines()
            if re.match(r"\s*else\b", ln) and "_MINE()" in ln
            and re.search(r"\.is\(\s*['\"]hive_id['\"]\s*,\s*null\s*\)", ln)]
    fails = []
    if reads < 1:
        fails.append("R6 loadMachineHistory no longer reads fault_knowledge")
    if len(solo) < reads:
        fails.append(f"R6 loadMachineHistory has {reads} fault_knowledge read(s) but {len(solo)} solo branch(es) "
                     "scoped `.is('hive_id', null)` + `_MINE()` - a solo owner's panel would not ask for their own rows")
    return fails


# ── R7-R9: the AI paths ask for the person's own rows, owned by the VERIFIED uid ─────────────────
def _strip_ts_comments(src: str) -> str:
    """Comments describe intent; the rules read the code ([[feedback_quoting_a_comment_is_not_reading_the_code]]).
    A scanner, not a regex: this gate's first draft used `/\\*.*?\\*/`, and a `/*` inside a STRING in ai-gateway
    opened a "comment" that swallowed two-thirds of the file - the shape of
    [[feedback_accept_image_star_broke_comment_stripping]]. Strings, template literals (with nested ${...}) and regex
    literals are copied through untouched; only real comments are dropped."""
    out: list[str] = []
    n = len(src)
    stack: list[str] = []          # "`" inside a template literal; "${" / "{" inside an interpolation
    i, prev = 0, ""
    while i < n:
        c = src[i]
        if stack and stack[-1] == "`":
            if c == "\\":
                out.append(src[i:i + 2]); i += 2; continue
            if c == "`":
                stack.pop(); out.append(c); i += 1; prev = "`"; continue
            if src.startswith("${", i):
                stack.append("${"); out.append("${"); i += 2; prev = "{"; continue
            out.append(c); i += 1; continue
        if c in "\"'":
            j = i + 1
            while j < n and src[j] != c and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
            out.append(src[i:j + 1]); i = j + 1; prev = c; continue
        if c == "`":
            stack.append("`"); out.append(c); i += 1; continue
        if src.startswith("//", i):
            j = src.find("\n", i); i = n if j < 0 else j; continue
        if src.startswith("/*", i):
            j = src.find("*/", i + 2); out.append(" "); i = n if j < 0 else j + 2; continue
        if c == "/" and (prev == "" or prev in "(,=:[!&|?{};+-*%<>~^"):
            j, in_class = i + 1, False
            while j < n and src[j] != "\n":
                if src[j] == "\\":
                    j += 2; continue
                if src[j] == "[":
                    in_class = True
                elif src[j] == "]":
                    in_class = False
                elif src[j] == "/" and not in_class:
                    break
                j += 1
            out.append(src[i:j + 1]); i = j + 1; prev = "/"; continue
        if c == "{" and stack:
            stack.append("{")
        elif c == "}" and stack:
            stack.pop()
        out.append(c)
        if not c.isspace():
            prev = c
        i += 1
    return "".join(out)


def _balanced(src: str, i: int, open_ch: str, close_ch: str) -> int:
    """Index just past the bracket that closes the one at src[i] (== open_ch); -1 if unbalanced."""
    depth = 0
    for j in range(i, len(src)):
        if src[j] == open_ch:
            depth += 1
        elif src[j] == close_ch:
            depth -= 1
            if depth == 0:
                return j + 1
    return -1


def _function(src: str, name: str) -> tuple[list[str], str] | None:
    """(parameter names, body) of `function name(...) ... { body }`, or None."""
    m = re.search(rf"\bfunction\s+{re.escape(name)}\s*\(", src)
    if not m:
        return None
    p_end = _balanced(src, m.end() - 1, "(", ")")
    if p_end < 0:
        return None
    params = [re.split(r"[\s:?=]", p.strip(), maxsplit=1)[0]
              for p in src[m.end(): p_end - 1].split(",") if p.strip()]
    b = src.find("{", p_end)
    b_end = _balanced(src, b, "{", "}") if b >= 0 else -1
    return (params, src[b: b_end]) if b_end > 0 else None


def _rpc_args(src: str, fns: tuple[str, ...]) -> list[tuple[str, str]]:
    out = []
    for m in re.finditer(r"\.rpc\(\s*[\"'](\w+)[\"']\s*,\s*\{", src):
        if m.group(1) in fns:
            end = _balanced(src, m.end() - 1, "{", "}")
            out.append((m.group(1), src[m.end(): end - 1] if end > 0 else ""))
    return out


def _assigned_from(src: str, ident: str) -> list[str]:
    """Every right-hand side `ident` is given in this source: `ident = X`, `let ident: T = X`, and destructures
    `{ ..., ident, ... } = X` (X = the whole right-hand expression)."""
    rhs = [m.group(1).strip() for m in
           re.finditer(rf"(?<![\w.]){re.escape(ident)}\s*(?::[^=;\n,()]+)?=(?![=>])\s*([^;\n]+)", src)]
    rhs += [m.group(1).strip() for m in
            re.finditer(rf"\{{[^{{}}]*\b{re.escape(ident)}\b[^{{}}]*\}}\s*=(?![=>])\s*([^;\n]+)", src)]
    return rhs


OWN_SEARCHES = ("search_fault_knowledge", "search_all_knowledge")


def check_ai_paths(srcs: dict[str, str | None]) -> list[str]:
    fails: list[str] = []
    gw, ss, hp = (_strip_ts_comments(srcs.get(k) or "") for k in ("gateway", "search", "helper"))

    # R7 - the shared owner-scoped search
    fn = _function(hp, "searchOwnFaultKnowledge") if hp else None
    if not fn:
        fails.append("R7 supabase/functions/_shared/own-knowledge.ts has no searchOwnFaultKnowledge - there is no "
                     "owner-scoped knowledge search for a hive-less person")
    elif len(fn[0]) < 3:
        fails.append("R7 searchOwnFaultKnowledge no longer takes (admin, embedding, ownerUid, ...)")
    else:
        owner, body = fn[0][2], fn[1]
        if not re.search(rf"if\s*\(\s*!\s*{owner}\s*\)\s*return\s*\[\s*\]", body):
            fails.append(f"R7 searchOwnFaultKnowledge does not return [] when {owner} is empty - an anonymous or "
                         "unresolved caller would reach the search")
        scoped = [a for _, a in _rpc_args(body, OWN_SEARCHES)
                  if re.search(r"\bmatch_hive_id\s*:\s*null\b", a) and re.search(rf"\bmatch_owner\s*:\s*{owner}\b", a)]
        if not scoped:
            fails.append(f"R7 searchOwnFaultKnowledge does not search with match_hive_id null + match_owner = {owner} "
                         "- the own scope names nobody on a service-role client")
        reread = re.search(rf"\.eq\(\s*[\"']auth_uid[\"']\s*,\s*{owner}\s*\)", body)
        if not (reread and re.search(r"\.is\(\s*[\"']hive_id[\"']\s*,\s*null\s*\)", body)
                and re.search(r"\.filter\(", body[reread.end():])):
            fails.append(f"R7 searchOwnFaultKnowledge has no defensive re-read keeping only rows that are hive-less "
                         f"AND auth_uid = {owner} - an SQL regression would hand one person another's repairs")

    # R8 - the gateway's signed-in, no-hive branch
    if not gw:
        fails.append("R8 supabase/functions/ai-gateway/index.ts is missing")
    else:
        if not re.search(r"\bconst\s+adminClient\b[^=;]*=\s*createClient\(\s*SUPABASE_URL\s*,\s*SERVICE_KEY\s*\)", gw):
            fails.append("R8 ai-gateway's adminClient is no longer the service-role client - match_owner is honoured "
                         "only for service_role")
        bound = _assigned_from(gw, "authUid")
        bad = [r for r in bound if r not in ("user.id", "null")]
        if bad or "user.id" not in bound \
                or not re.search(r"\{\s*data:\s*\{\s*user\s*\}\s*\}\s*=\s*await\s+\w+\.auth\.getUser\(\s*\)", gw):
            fails.append(f"R8 ai-gateway binds authUid from something other than the verified auth.getUser() user "
                         f"({', '.join(bad) or 'no user.id binding'}) - the owner it names would not be proven")
        branch = None
        for m in re.finditer(r"else\s+if\s*\(", gw):
            c_end = _balanced(gw, m.end() - 1, "(", ")")
            if c_end > 0 and re.match(r"\s*authUid\s*&&\s*!\s*hive_id\b", gw[m.end(): c_end - 1]):
                b = gw.find("{", c_end)
                end = _balanced(gw, b, "{", "}") if b >= 0 else -1
                branch = gw[b: end] if end > 0 else ""
                break
        if branch is None:
            fails.append("R8 ai-gateway has no signed-in no-hive branch (else if (authUid && !hive_id ...)) - re-point "
                         "this gate if the solo snapshot moved")
        else:
            good = []
            for c in re.finditer(r"\b(\w+)\(\s*adminClient\s*,\s*authUid\s*,", branch):
                f = _function(gw, c.group(1))
                if f and len(f[0]) >= 2 and "=== YOUR OWN" in f[1] and re.search(
                        rf"\bsearchOwnFaultKnowledge\(\s*\w+\s*,\s*\w+\s*,\s*{f[0][1]}\s*,", f[1]):
                    good.append(c.group(1))
            if not good:
                fails.append("R8 ai-gateway's solo branch builds no knowledge block from searchOwnFaultKnowledge on "
                             "adminClient with the verified authUid as owner, labelled as the person's own - a solo "
                             "owner's answers never use their own past repairs")

    # R9 - semantic-search's no-hive path
    if not ss:
        fails.append("R9 supabase/functions/semantic-search/index.ts is missing")
    else:
        calls = re.findall(r"\bsearchOwnFaultKnowledge\(\s*db\s*,\s*\w+\s*,\s*(\w+)\s*,", ss)
        if not calls:
            fails.append("R9 semantic-search's no-hive path does not call searchOwnFaultKnowledge(db, ..., <owner>) - "
                         "a signed-in person with no hive gets nothing back")
        auth_src = _assigned_from(ss, "authUid")
        for owner in set(calls):
            src_of = _assigned_from(ss, owner)
            if any(r not in ("null", "authUid") for r in src_of) or "authUid" not in src_of \
                    or not auth_src or any("resolveIdentity(" not in r for r in auth_src):
                fails.append(f"R9 semantic-search's owner `{owner}` is not bound only from resolveIdentity's authUid "
                             f"({', '.join(src_of) or 'never assigned'}) - a body field could name another person")
    for label, src in (("ai-gateway", gw), ("semantic-search", ss)):
        for name, args in _rpc_args(src, OWN_SEARCHES):
            hv = re.search(r"\bmatch_hive_id\s*:\s*([^,\n]+)", args)
            if hv and re.search(r"(^null\b|\|\|\s*null\b|\?\?\s*null\b)", hv.group(1).strip()) \
                    and "match_owner" not in args:
                fails.append(f"R9 {label} calls {name} with match_hive_id `{hv.group(1).strip()}` and no match_owner "
                             "- with no hive that searches as nobody and silently returns nothing")
    fails += check_orchestrator_solo(_strip_ts_comments(srcs.get("orch") or ""), ss)
    return fails


TRUST_CONST = re.compile(r"\bconst\s+(\w+)\s*(?::\s*boolean\s*)?=\s*await\s+isTrustedGatewayForward\(\s*req\s*\)")


def _guarded_by(src: str, pos: int, cond_re: str) -> bool:
    """True when the statement at `pos` sits inside an `if (...) { ... }` block whose condition matches cond_re."""
    for m in re.finditer(r"\bif\s*\(", src[:pos]):
        c_end = _balanced(src, m.end() - 1, "(", ")")
        b = src.find("{", c_end) if c_end > 0 else -1
        if b < 0 or src[c_end:b].strip():
            continue
        end = _balanced(src, b, "{", "}")
        if b < pos < end and re.search(cond_re, src[m.end(): c_end - 1]):
            return True
    return False


def check_orchestrator_solo(oc: str, ss: str) -> list[str]:
    """R10 (2026-10-08) - ai-orchestrator asked semantic-search with the SERVICE-ROLE key for every caller, so for a
    person with no hive the search's own scope (the verified caller) named nobody: a solo turn through the assistant
    never used the person's own past repairs. Now a solo turn forwards the person's own Authorization, and the
    gateway's forward proof rides along only when it verifies, so semantic-search does not count the person twice."""
    fails: list[str] = []
    if not oc:
        return ["R10 supabase/functions/ai-orchestrator/index.ts is missing"]
    fn = _function(oc, "orchestrate")
    hdr = fn[0][6] if fn and len(fn[0]) >= 7 else None
    i = oc.find("/functions/v1/semantic-search")
    f = oc.rfind("fetch(", 0, i) if i >= 0 else -1
    end = _balanced(oc, f + len("fetch"), "(", ")") if f >= 0 else -1
    call = oc[f:end] if end > 0 else ""
    if not hdr or not re.search(rf"\.\.\.\(\s*{hdr}\s*\?\?", call):
        fails.append("R10 ai-orchestrator asks semantic-search with a fixed service-role bearer - with no hive that "
                     "searches as nobody, so a solo person's turn never uses their own knowledge")
    m = re.search(r"\bawait\s+orchestrate\(", oc)
    a_end = _balanced(oc, m.end() - 1, "(", ")") if m else -1
    args = [x.strip() for x in oc[m.end(): a_end - 1].split(",")] if a_end > 0 else []
    ident = args[6] if len(args) >= 7 and re.fullmatch(r"\w+", args[6]) else None
    if not ident:
        fails.append("R10 ai-orchestrator's handler passes orchestrate() no solo search headers")
    else:
        rhs = _assigned_from(oc, ident)
        built = [r for r in rhs if r != "null"]
        if not built or any(not re.search(r"\breq\.headers\.get\(\s*[\"']Authorization[\"']\s*\)", r)
                            or re.search(r"\bbody\b", r) for r in built):
            fails.append(f"R10 ai-orchestrator's solo search headers `{ident}` are not the request's own Authorization "
                         f"({'; '.join(built) or 'never built'}) - the search would run as someone the gate never verified")
        for a in re.finditer(rf"(?<![\w.]){re.escape(ident)}\s*=(?![=>])", oc):
            if not _guarded_by(oc, a.start(), r"!\s*hive_id\b") or not _guarded_by(oc, a.start(), r"_serviceKey"):
                fails.append(f"R10 ai-orchestrator builds `{ident}` outside the no-hive, non-service-role branch")
                break
        trust = TRUST_CONST.findall(oc)
        relays = list(re.finditer(rf"\b{re.escape(ident)}\s*\[\s*GATEWAY_FORWARD_HEADER\s*\]\s*=", oc))
        if not relays:
            fails.append("R10 ai-orchestrator never relays ai-gateway's forward proof - semantic-search would count a "
                         "gateway turn's solo bucket a second time")
        for r in relays:
            if not any(_guarded_by(oc, r.start(), rf"^\s*{t}\s*$") for t in trust):
                fails.append("R10 ai-orchestrator relays the gateway forward header without first verifying it "
                             "(`const X = await isTrustedGatewayForward(req)`; `if (X)`)")
    # semantic-search: a signed-in person's solo limiter is skipped ONLY for a verified gateway forward. Each
    # checkSoloRateLimit call's innermost `if` must be the service-role test or `!X` with X = a verified forward.
    if ss:
        lim = [mm.start() for mm in re.finditer(r"\bcheckSoloRateLimit\(", ss)]
        trust = set(TRUST_CONST.findall(ss))
        if not lim:
            fails.append("R10 semantic-search no longer rate-limits a signed-in person at all")
        skip_ok = 0
        for p in lim:
            cond = _innermost_if(ss, p)
            if cond is None or re.match(r"\s*!\s*isServiceRole\b", cond):
                continue
            neg = re.fullmatch(r"\s*!\s*(\w+)\s*", cond)
            if neg and neg.group(1) in trust:
                skip_ok += 1
                continue
            fails.append(f"R10 semantic-search's solo limiter runs only under `{cond.strip()}` - the skip must be a "
                         "verified gateway forward (`const X = await isTrustedGatewayForward(req)`; `if (!X)`)")
        if lim and not skip_ok:
            fails.append("R10 semantic-search counts a gateway-forwarded solo turn's bucket a second time (no "
                         "isTrustedGatewayForward skip) - the gateway already counted it")
    return fails


def _innermost_if(src: str, pos: int) -> str | None:
    """The condition of the innermost `if (...) { ... }` block enclosing `pos`, or None."""
    best, best_b = None, -1
    for m in re.finditer(r"\bif\s*\(", src[:pos]):
        c_end = _balanced(src, m.end() - 1, "(", ")")
        b = src.find("{", c_end) if c_end > 0 else -1
        if b < 0 or src[c_end:b].strip():
            continue
        end = _balanced(src, b, "{", "}")
        if b < pos < end and b > best_b:
            best, best_b = src[m.end(): c_end - 1], b
    return best


def load_ai_sources() -> dict[str, str | None]:
    return {k: (p.read_text(encoding="utf-8-sig") if p.exists() else None) for k, p in AI_SOURCES.items()}


# ── the evaluation ─────────────────────────────────────────────────────────────────────────────
def evaluate(gt: dict, mutation: str = "", page_src: str | None = None) -> tuple[list[str], dict]:
    fails: list[str] = []
    rows = gt["rows"]
    by_owner: dict[str, set] = {}
    md5_by_owner: dict[str, set] = {}
    for r in rows:
        if r["owner"]:
            by_owner.setdefault(r["owner"], set()).add(r["id"])
            md5_by_owner.setdefault(r["owner"], set()).add(r["md5"])

    # R3 static: every hive-less row names the author of its entry, and none is unowned.
    unowned = [r["id"] for r in rows if not r["owner"]]
    disagree = [r["id"] for r in rows if r["author"] and r["owner"] and r["owner"] != r["author"]]
    if unowned:
        fails.append(f"R3 {len(unowned)} hive-less knowledge row(s) carry no owner - unreadable by the person who "
                     f"wrote them (e.g. {unowned[0]})")
    if disagree:
        fails.append(f"R3 {len(disagree)} hive-less row(s) name an owner other than their entry's author "
                     f"(e.g. {disagree[0]}) - the owner policy would hand them to the wrong person")

    owners = sorted(o for o in by_owner if o not in gt["excl"])
    probe_row = {}
    for o in owners:
        emb = [r["id"] for r in rows if r["owner"] == o and r["embedded"]]
        if emb:
            probe_row[o] = emb[0]
    owners = [o for o in owners if o in probe_row]
    if len(owners) < 2:
        fails.append(f"R2 only {len(owners)} hive-less owner(s) with an embedded row - cross-owner isolation cannot "
                     "be proven (seed: python tools/seed_solo_personas.py --apply)")
        return fails, {}
    if not gt["members"]:
        fails.append("R2 no active hive member (outside the never-act-as list) in a hive with knowledge - the "
                     "member half of R2 and the hive-path half of R4 cannot be proven")
    bind_row = next((r["id"] for r in rows if r["author"] and r["owner"] in owners), None)

    rc, out, err = psql(build_probe(gt, owners, probe_row, bind_row, mutation))
    if rc != 0:
        fails.append(f"probe did not run: {(err or '').strip()[:240]}")
        return fails, {}
    res = parse_probe(out)

    # R3 behavioural
    if bind_row:
        want = next(r["author"] for r in rows if r["id"] == bind_row)
        if res["BIND"] != want:
            fails.append(f"R3 a write that left auth_uid out stayed {res['BIND'] or 'NULL'} (entry author {want}) - "
                         "tg_bind_owner_fault_knowledge did not bind the owner from the entry")

    def own(label: str) -> set:
        return by_owner.get(label.split(":", 1)[1], set()) if label.startswith("owner:") else set()

    def own_md5(label: str) -> set:
        return md5_by_owner.get(label.split(":", 1)[1], set()) if label.startswith("owner:") else set()

    for kind, what in (("T", "the table"), ("V", "v_knowledge_truth")):
        for label, seen in res[kind].items():
            mine = own(label)
            if label.startswith("owner:") and mine - seen:
                fails.append(f"R1 {label} reads {len(seen & mine)} of their {len(mine)} hive-less row(s) on {what}")
            foreign = seen - mine
            if foreign:
                victims = sorted({o for o, ids in by_owner.items() if ids & foreign})
                fails.append(f"R2 {label} reads {len(foreign)} hive-less row(s) of another person on {what} "
                             f"(owners {', '.join(v[:8] for v in victims) or 'unowned'})")
        expected = {"owner:" + o for o in owners} | {"member:" + m["uid"] for m in gt["members"]} | {"anon"}
        missing = expected - set(res[kind])
        if missing:
            fails.append(f"probe printed no {what} line for {sorted(missing)}")

    for (label, named), seen in res["S"].items():
        if label == "service_role":
            if seen - by_owner.get(named, set()):
                fails.append(f"R4 search_fault_knowledge as service_role naming {named[:8]} returned another "
                             "person's row")
            if probe_row[named] not in seen:
                fails.append(f"R4 search_fault_knowledge as service_role naming {named[:8]} did not find that "
                             "owner's own row (match_owner not honoured for a server role)")
            continue
        foreign = seen - own(label)
        if foreign:
            fails.append(f"R4 search_fault_knowledge as {label} naming {named[:8]} returned {len(foreign)} row(s) "
                         "that are not theirs")
        if label == "owner:" + named and probe_row[named] not in seen:
            fails.append(f"R4 search_fault_knowledge as {label} (own scope) did not find their own row")
    for (label, named), seen in res["A"].items():
        allowed = md5_by_owner.get(named, set()) if label == "service_role" else own_md5(label)
        if seen - allowed:
            fails.append(f"R4 search_all_knowledge as {label} naming {named[:8]} returned fault knowledge that is "
                         "not theirs")
        probe_md5 = next(r["md5"] for r in rows if r["id"] == probe_row[named])
        if label in ("owner:" + named, "service_role") and probe_md5 not in seen:
            fails.append(f"R4 search_all_knowledge as {label} for {named[:8]} (own scope) returned no fault row of "
                         "theirs")
    for m in gt["members"]:
        label = "member:" + m["uid"]
        if not res["H"].get(label):
            fails.append(f"R4 {label} searching their OWN hive got nothing - the hive path broke")
    # R4 GENERIC: under the plan PostgREST gets, the own scope still returns EVERY embedded row of the owner, and no
    # other row (search_fault_knowledge by id; search_all_knowledge by summary md5).
    for o in owners:
        emb = {r["id"] for r in rows if r["owner"] == o and r["embedded"]}
        emb_md5 = {r["md5"] for r in rows if r["owner"] == o and r["embedded"]}
        got = res["G"].get(o)
        if got is None:
            fails.append(f"probe printed no generic-plan line for owner {o[:8]}")
        elif got != emb:
            fails.append(f"R4 search_fault_knowledge under a GENERIC plan (how PostgREST runs an RPC) returned "
                         f"{len(got & emb)} of owner {o[:8]}'s {len(emb)} row(s)"
                         + (f" and {len(got - emb)} not theirs" if got - emb else "")
                         + " - the own scope is riding the approximate vector index")
        got_a = res["GA"].get(o)
        if got_a is not None and got_a != emb_md5:
            fails.append(f"R4 search_all_knowledge under a GENERIC plan returned {len(got_a & emb_md5)} of owner "
                         f"{o[:8]}'s {len(emb_md5)} fault summar(ies)"
                         + (f" and {len(got_a - emb_md5)} not theirs" if got_a - emb_md5 else ""))

    # R5
    opts = gt["viewopt"] if not mutation else None
    if opts is not None and "security_invoker=true" not in opts and "security_invoker=on" not in opts:
        fails.append(f"R5 v_knowledge_truth is not security_invoker ({opts or 'no options'})")

    # R6
    src = page_src if page_src is not None else PAGE.read_text(encoding="utf-8-sig")
    fails += check_page(src)
    stats = {"owners": len(owners), "rows": len(rows), "members": len(gt["members"]),
             "principals": len(owners) + len(gt["members"]) + 2}
    return fails, stats


# ── teeth ──────────────────────────────────────────────────────────────────────────────────────
HIVE_ONLY_POLICY = """ALTER POLICY fault_knowledge_read ON public.fault_knowledge USING ((auth.uid() IS NOT NULL)
  AND (hive_id IN (SELECT hm.hive_id FROM public.hive_members hm WHERE hm.auth_uid = auth.uid() AND hm.status = 'active')));"""
OWNERLESS_POLICY = """ALTER POLICY fault_knowledge_read ON public.fault_knowledge USING ((auth.uid() IS NOT NULL)
  AND ((hive_id IN (SELECT hm.hive_id FROM public.hive_members hm WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'))
       OR hive_id IS NULL));"""
SFK = """CREATE OR REPLACE FUNCTION public.search_fault_knowledge(query_embedding vector, match_hive_id uuid,
  match_count integer DEFAULT 5, match_owner uuid DEFAULT NULL)
RETURNS TABLE(id uuid, machine text, problem text, root_cause text, action text, knowledge text, worker_name text,
  similarity double precision) LANGUAGE sql STABLE AS $m$
  SELECT id, machine, problem, root_cause, action, knowledge, worker_name, 1 - (embedding <=> query_embedding)
    FROM fault_knowledge WHERE embedding IS NOT NULL AND ({pred})
   ORDER BY embedding <=> query_embedding LIMIT match_count $m$;"""
MUTANTS = [
    ("the pre-fix hive-only read policy", "R1", HIVE_ONLY_POLICY, False),
    ("a hive-less branch with no owner check", "R2", OWNERLESS_POLICY, False),
    ("search_fault_knowledge without an own scope", "R4",
     SFK.format(pred="hive_id = match_hive_id"), False),
    ("search_fault_knowledge ignoring match_owner for a server role", "R4",
     SFK.format(pred="hive_id = match_hive_id OR (match_hive_id IS NULL AND hive_id IS NULL AND auth_uid = auth.uid())"),
     False),
    # 20261007000014's body: right with literals, approximate (1 of 3 rows) under PostgREST's generic plan
    ("search_fault_knowledge's own scope as one OR predicate (rides ivfflat when generic)", "R4",
     SFK.format(pred="hive_id = match_hive_id OR (match_hive_id IS NULL AND hive_id IS NULL AND auth_uid = "
                     "COALESCE(auth.uid(), CASE WHEN current_user IN ('service_role', 'postgres') THEN match_owner END))"),
     False),
    ("v_knowledge_truth without security_invoker", "R2",
     "ALTER VIEW public.v_knowledge_truth SET (security_invoker = false);", False),
    ("the owner-binding trigger dropped", "R3",
     "DROP TRIGGER tg_bind_owner_fault_knowledge ON public.fault_knowledge;", False),
    ("the panel's solo branch without .is('hive_id', null)", "R6", "", True),
]

# Source mutants for R7-R9, applied in memory: (name, rule, which source, pattern, replacement). Each pattern must
# match the real source (a mutant that changes nothing is reported, never counted as teeth).
SOURCE_MUTANTS = [
    ("the gateway's solo branch with no own-knowledge block (the pre-fix shape)", "R8", "gateway",
     r"buildOwnKnowledgeContext\(adminClient, authUid, soloMsg\)", 'Promise.resolve("")'),
    ("the gateway naming the owner from the request context", "R8", "gateway",
     r"buildOwnKnowledgeContext\(adminClient, authUid,", "buildOwnKnowledgeContext(adminClient, (context as any).owner_uid,"),
    ("the gateway searching on the user-JWT client (match_owner ignored there)", "R8", "gateway",
     r"buildOwnKnowledgeContext\(adminClient,", "buildOwnKnowledgeContext(authedClient,"),
    ("the gateway binding authUid from the body", "R8", "gateway",
     r"authUid(\s*)= user\.id;", r"authUid\1= (body as any).auth_uid;"),
    ("the solo knowledge block labelled as a hive's", "R8", "gateway",
     r"=== YOUR OWN PAST REPAIRS", "=== KNOWLEDGE BASE"),
    ("the shared search without match_owner", "R7", "helper", r",\s*match_owner:\s*ownerUid", ""),
    ("the shared search without the defensive owner re-read", "R7", "helper",
     r"\.eq\(\"auth_uid\", ownerUid\)", ""),
    ("the shared search with no anonymous guard", "R7", "helper", r"if \(!ownerUid\) return \[\];", ""),
    ("semantic-search's no-hive path searching as nobody (the pre-fix shape)", "R9", "search",
     r"await searchOwnFaultKnowledge\(db, embedding, ownerUid, count\)",
     '(await db.rpc("search_fault_knowledge", { query_embedding: embedding, match_hive_id: hive_id || null, '
     'match_count: count })).data'),
    ("semantic-search taking the owner from the body", "R9", "search",
     r"ownerUid = authUid;", "ownerUid = _whBody.owner_uid;"),
    # R10 (2026-10-08): the orchestrator's solo knowledge search
    ("ai-orchestrator asking semantic-search with the service-role key for every caller (the pre-fix shape)", "R10",
     "orch", r"\.\.\.\(searchHeaders \?\? \{ \"Authorization\": `Bearer \$\{Deno\.env\.get\(\"SUPABASE_SERVICE_ROLE_KEY\"\)\}` \}\),",
     '"Authorization": `Bearer ${Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")}`,'),
    ("ai-orchestrator taking the solo search's bearer from the body", "R10", "orch",
     r"\{ \"Authorization\": req\.headers\.get\(\"Authorization\"\) \|\| \"\" \}",
     '{ "Authorization": String((body as any).authorization || "") }'),
    ("ai-orchestrator building the person's headers for a hive turn too", "R10", "orch",
     r"if \(!hive_id && !\(_bearer && _serviceKey && _bearer === _serviceKey\)\) \{\n      _soloSearchHeaders",
     "if (true) {\n      _soloSearchHeaders"),
    ("ai-orchestrator relaying the gateway header unverified", "R10", "orch",
     r"const _soloViaGateway = await isTrustedGatewayForward\(req\);", "const _soloViaGateway = true;"),
    ("semantic-search skipping the solo limiter on a body flag", "R10", "search",
     r"const _ssViaGateway = await isTrustedGatewayForward\(req\);",
     "const _ssViaGateway = Boolean(_whBody.gateway);"),
    ("semantic-search counting a gateway turn twice (no skip)", "R10", "search",
     r"if \(!_ssViaGateway\) \{", "if (!isServiceRole) {"),
]


def self_test_sources() -> bool:
    ok = True
    real = load_ai_sources()
    base = check_ai_paths(real)
    mark = f"{GREEN}PASS{RST}" if not base else f"{RED}FAIL{RST}"
    print(f"  [{mark}] the current AI sources pass R7-R10" + ("" if not base else f": {base[:3]}"))
    ok &= not base
    for name, rule, key, pat, repl in SOURCE_MUTANTS:
        mutated_src, n = re.subn(pat, repl, real.get(key) or "")
        if not n:
            print(f"  [{RED}FAIL{RST}] mutant '{name}' matched nothing in the {key} source - re-point it")
            ok = False
            continue
        fails = check_ai_paths({**real, key: mutated_src})
        hit = any(f.startswith(rule) for f in fails)
        mark = f"{GREEN}PASS{RST}" if hit else f"{RED}FAIL{RST}"
        print(f"  [{mark}] mutant '{name}' fails {rule}" + ("" if hit else f" - got {fails[:2] or 'a PASS'}"))
        ok &= hit
    return ok


def self_test(gt: dict) -> int:
    ok = self_test_sources()
    base, _ = evaluate(gt)
    mark = f"{GREEN}PASS{RST}" if not base else f"{RED}FAIL{RST}"
    print(f"  [{mark}] the current database + page pass" + ("" if not base else f": {base[:3]}"))
    ok &= not base
    src = PAGE.read_text(encoding="utf-8-sig")
    for name, rule, sql, page in MUTANTS:
        if page:
            fails, _ = evaluate(gt, page_src=re.sub(r"\.is\(\s*'hive_id'\s*,\s*null\s*\)(?=\.or\(_MINE\(\)\))", "", src))
        else:
            fails, _ = evaluate(gt, mutation=sql)
        hit = any(f.startswith(rule) for f in fails)
        mark = f"{GREEN}PASS{RST}" if hit else f"{RED}FAIL{RST}"
        print(f"  [{mark}] mutant '{name}' fails {rule}" + ("" if hit else f" - got {fails[:2] or 'a PASS'}"))
        ok &= hit
    return 0 if ok else 1


def main() -> int:
    print("=" * 76)
    print("  HIVE-LESS KNOWLEDGE IS READ BY ITS OWNER, AND BY NOBODY ELSE")
    print("=" * 76)
    # R7-R9 read source only, so they hold even when the database is down.
    ai_fails = check_ai_paths(load_ai_sources())
    gt = ground_truth()
    if gt is None:
        if "--self-test" in sys.argv[1:]:
            return 0 if self_test_sources() else 1
        for f in ai_fails:
            print(f"    {RED}FAIL{RST} {f}")
        return 1 if ai_fails else 0
    if "--self-test" in sys.argv[1:]:
        return self_test(gt)
    fails, stats = evaluate(gt)
    fails += ai_fails
    if stats:
        print(f"  {stats['rows']} hive-less knowledge row(s) · {stats['owners']} owner(s) probed · "
              f"{stats['members']} hive member(s) · {stats['principals']} principals (incl. anon + service_role)")
    if fails:
        for f in fails:
            print(f"    {RED}FAIL{RST} {f}")
        print(f"\n  {RED}FAIL{RST}: {len(fails)} finding(s)")
        return 1
    print(f"  {GREEN}PASS{RST} R1 each owner reads all of their hive-less rows (table + view)")
    print(f"  {GREEN}PASS{RST} R2 no other owner, hive member or anon reads any of them")
    print(f"  {GREEN}PASS{RST} R3 every hive-less row is bound to its entry's author; the trigger rebinds an omission")
    print(f"  {GREEN}PASS{RST} R4 own-scope searches return only the caller's rows; naming another person returns none")
    print(f"  {GREEN}PASS{RST} R5 v_knowledge_truth is security_invoker")
    print(f"  {GREEN}PASS{RST} R6 logbook.html's past-repairs panel scopes its solo reads to the person's own rows")
    print(f"  {GREEN}PASS{RST} R7 searchOwnFaultKnowledge: no owner = nothing; own scope + match_owner; owner re-read")
    print(f"  {GREEN}PASS{RST} R8 ai-gateway's solo branch grounds in the person's own knowledge, owner = verified authUid")
    print(f"  {GREEN}PASS{RST} R9 semantic-search's no-hive path searches as the resolveIdentity-verified caller")
    print(f"  {GREEN}PASS{RST} R10 ai-orchestrator's solo search runs as the person (own bearer; verified gateway proof)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
