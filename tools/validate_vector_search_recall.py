#!/usr/bin/env python3
"""validate_vector_search_recall.py - every vector search returns its scope's TRUE nearest rows, under the plan
PostgREST actually runs.

THE FINDING (2026-10-08, by the work that made solo owners' knowledge searchable - migration 20261008000001). When
PostgREST runs a search RPC it BINDS the arguments; the plan is generic, and Postgres then picks the approximate vector
index (ivfflat lists=50 probes=1, or hnsw ef_search=40), walks ONE list (~1/50th of the table) or 40 candidates, and
applies the hive / owner filter AFTER. A hive or a person whose rows sit outside that list gets a partial or an empty
answer. It looked right when typed into psql with literal values - a different plan. The own-scope fault searches were
fixed there; this gate measures EVERY vector search the same way and found the rest (pm_knowledge, voice journal,
skill, bom, calc, project, kb, platform facts, industry standards - migration 20261008000002).

RULES (live, every probe inside BEGIN ... ROLLBACK - seeds and mutants included; nothing survives a run)
  V1 COVERED      every SQL / plpgsql function and every view whose body uses a pgvector distance operator has a case
                  family below. A new search with no case FAILS here, so this gate cannot go quietly stale.
  V2 RECALL       each case runs the search the way PostgREST does - PREPAREd with BOUND parameters, under
                  plan_cache_mode force_generic_plan AND force_custom_plan - as the real principal (role authenticated +
                  the member's JWT sub; service_role where the edge function calls on a service-role client), for the
                  largest and the smallest scope, and compares the top k against the EXACT truth: the same call after
                  DISCARD PLANS with enable_indexscan = off (no index-ordered plan can exist, so the scan is exhaustive
                  over the scope). recall@k must be 1.0 for every question; a tie at the boundary distance counts.
  V3 NOT VACUOUS  every case's truth returns at least one row for at least one question - comparing two empty lists
                  proves nothing.

Scopes the local data cannot show are SEEDED inside the case's own transaction (bom / calc / project / kb / procedural
memory / platform facts are empty locally; skill has 9 rows): rows that copy fault_knowledge's real embeddings into the
largest member hive (1,200), the smallest (4) and the other hives (300 each), so the property is held for tables that are
empty here and full in production. Production logins (ianphone) are never impersonated.

USAGE:      python tools/validate_vector_search_recall.py            (the table: recall + latency per case)
            python tools/validate_vector_search_recall.py --only search_pm_knowledge,search_all_knowledge
Self-test:  python tools/validate_vector_search_recall.py --self-test
            (the current bodies must PASS; each PRE-FIX body - the definition before 20261008000002, verbatim, and
             20261007000014's one-OR-predicate fault search - recreated inside the case's rolled-back transaction, must
             FAIL V2 where it under-recalled on a reproducible plan: fault x2, all-knowledge, pm, kb, platform facts)

Measured 2026-10-08 before -> after 20261008000002 (recall@10, worst question, generic / custom plan):
  search_pm_knowledge 147-row hive 0.00/0.00 -> 1/1 · search_fault_knowledge 7,700-row hive 1.00/0.00 -> 1/1 ·
  search_all_knowledge 0.67/0.33 -> 1/1 · bom 1.00/0.20 · calc 1.00/0.10 · platform facts 1.00/0.00 -> 1/1 ·
  semantic_search_kb ERROR for every member (double precision into a real column) -> 1/1.
  Latency, largest scope (fault_knowledge hive b4f7fe63, 7,700 rows, generic, member): 24 ms -> 16 ms.

LIMIT OF THE APPROACH: the fence ranks every row of the scope - right while a scope is thousands of rows (17 ms at
7,700). A per-hive scope past ~50k rows wants a per-hive partial index or pgvector's iterative index scan instead;
this gate will keep measuring whichever is chosen.
"""
from __future__ import annotations

import json
import statistics
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

DB = "supabase_db_workhive"
US = "\x1f"
GREEN, RED, YEL, DIM, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"
NEVER_ACT_AS = ("%ianphone%",)          # production logins: never impersonated, never probed
K = 10                                   # top-k asked of every search (the callers ask 3-5; 10 is stricter)
EPS = 1e-5                               # similarity tie tolerance (several searches return real, not float8)
LARGE_SEED, SMALL_SEED, OTHER_SEED = 1200, 4, 300
SEED_TAG = "vector-search-recall seed (rolled back)"
DIST_OPS = r"<=>|<->|<#>|<[+]>|<~>|<%>"


def psql(sql: str, timeout: int = 300) -> tuple[int, str, str]:
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


def lines(out: str) -> list[str]:
    # split('\n'), NEVER splitlines(): str.splitlines() also breaks on \x1c-\x1e (see the hive-less gate's lesson)
    return out.replace("\r\n", "\n").split("\n")


# ── discovery (as postgres, read-only) ──────────────────────────────────────────────────────────
def discover() -> dict | None:
    excl = " or ".join(f"u.email ilike {lit(p)}" for p in NEVER_ACT_AS)
    sql = f"""
select 'FN', p.proname, pg_get_function_identity_arguments(p.oid)
  from pg_proc p join pg_namespace n on n.oid = p.pronamespace join pg_language l on l.oid = p.prolang
 where n.nspname not in ('pg_catalog', 'information_schema') and l.lanname in ('sql', 'plpgsql')
   and p.prosrc ~ '{DIST_OPS}';
select 'VW', schemaname || '.' || viewname from pg_views
 where schemaname not in ('pg_catalog', 'information_schema') and definition ~ '{DIST_OPS}';
select 'VW', schemaname || '.' || matviewname from pg_matviews where definition ~ '{DIST_OPS}';
select 'MEM', m.hive_id, m.auth_uid from (
  select distinct on (hm.hive_id) hm.hive_id, hm.auth_uid
    from public.hive_members hm join auth.users u on u.id = hm.auth_uid
   where hm.status = 'active' and not ({excl})
   order by hm.hive_id, (hm.role = 'worker') desc, hm.auth_uid) m;
select 'SC', 'fault_hive', hive_id, count(*) from public.fault_knowledge
 where embedding is not null and hive_id is not null group by hive_id;
select 'SC', 'fault_owner', f.auth_uid, count(*) from public.fault_knowledge f join auth.users u on u.id = f.auth_uid
 where f.embedding is not null and f.hive_id is null and not ({excl}) group by f.auth_uid;
select 'SC', 'pm_hive', hive_id, count(*) from public.pm_knowledge
 where embedding is not null and hive_id is not null group by hive_id;
select 'SC', 'skill_hive', hive_id, count(*) from public.skill_knowledge
 where embedding is not null and hive_id is not null group by hive_id;
select 'SC', 'voice_user', v.auth_uid, count(*) from public.voice_journal_entries v join auth.users u on u.id = v.auth_uid
 where v.embedding is not null and not ({excl}) group by v.auth_uid;
select 'SC', 'persona', persona_scope, count(*) from public.persona_knowledge
 where embedding is not null group by persona_scope;
select 'SC', 'kgf_hive', hive_id, count(*) from public.knowledge_graph_facts
 where embedding is not null and active and confidence >= 0.5 group by hive_id;
select 'SC', 'standards', 'all', count(*) from public.industry_standards_chunks where embedding is not null;
select 'QV', id from (select distinct on (coalesce(hive_id::text, '')) id from public.fault_knowledge
                       where embedding is not null order by coalesce(hive_id::text, ''), id) t order by id limit 6;
"""
    rc, out, err = psql(sql)
    if rc != 0:
        print(f"  {YEL}SKIP{RST} database unreachable ({(err or '').strip()[:160]})")
        return None
    d: dict = {"fns": set(), "views": set(), "members": {}, "scopes": {}, "qv": []}
    for ln in lines(out):
        p = ln.split(US)
        if p[0] == "FN" and len(p) >= 3:
            d["fns"].add(p[1])
        elif p[0] == "VW" and len(p) >= 2:
            d["views"].add(p[1])
        elif p[0] == "MEM" and len(p) >= 3:
            d["members"][p[1]] = p[2]
        elif p[0] == "SC" and len(p) >= 4:
            d["scopes"].setdefault(p[1], {})[p[2]] = int(p[3])
        elif p[0] == "QV" and len(p) >= 2:
            d["qv"].append(p[1])
    return d


# ── cases ────────────────────────────────────────────────────────────────────────────────────────
@dataclass
class Case:
    fn: str
    scope: str                 # what the scope is, for the report
    rows: int                  # embedded rows in the scope (seeded rows included)
    role: str                  # authenticated | service_role
    sub: str | None            # the JWT sub (authenticated)
    types: list[str]           # PREPARE parameter types, in the function's argument order
    values: list[str]          # SQL expressions, in the same order; '{q}' = the question vector
    key: str                   # select-list expression naming a result row
    sim: str                   # select-list expression: similarity (higher = nearer)
    seed: str = ""             # SQL run as postgres inside the transaction, before the probe
    own_q: str = ""            # SQL returning one in-scope embedding::text (after the seed), added as a question
    seeded: bool = False

    @property
    def label(self) -> str:
        who = "service_role" if self.role == "service_role" else f"member {str(self.sub)[:8]}"
        return f"{self.scope} · {self.rows:,} rows · {who}" + (" · seeded" if self.seeded else "")


def big_small(scopes: dict, allowed=None) -> list[tuple[str, int]]:
    items = sorted(((k, n) for k, n in (scopes or {}).items() if allowed is None or k in allowed),
                   key=lambda kv: (-kv[1], kv[0]))
    if not items:
        return []
    return [items[0]] if len(items) == 1 else [items[0], items[-1]]


def seed_sql(insert_into: str, select_list: str, plan: list[tuple[str, int]], first_rn: int = 1) -> str:
    """Copy fault_knowledge's real embeddings (in id order, distinct per hive) into a table, `n` rows per hive."""
    vals, lo = [], first_rn
    for hive, n in plan:
        vals.append(f"({lit(hive)}::uuid, {lo}, {lo + n - 1})")
        lo += n
    return ("WITH src AS (SELECT embedding, row_number() OVER (ORDER BY id) AS rn FROM public.fault_knowledge "
            "WHERE embedding IS NOT NULL), "
            f"plan(hive, lo, hi) AS (VALUES {', '.join(vals)}) "
            f"INSERT INTO {insert_into} SELECT {select_list} FROM plan p JOIN src s ON s.rn BETWEEN p.lo AND p.hi;")


def nth_vector(rn: int) -> str:
    return (f"SELECT embedding::text FROM (SELECT embedding, row_number() OVER (ORDER BY id) AS rn "
            f"FROM public.fault_knowledge WHERE embedding IS NOT NULL) s WHERE rn = {rn}")


def build_cases(d: dict) -> list[Case]:
    mem = d["members"]
    sc = d["scopes"]
    cases: list[Case] = []
    q = "{q}"

    def member_cases(fn, fam_scopes, types, values_fn, key, sim, svc_on_big=False, own_q_fn=None, scope_name="hive"):
        for i, (h, n) in enumerate(big_small(fam_scopes, allowed=mem)):
            oq = own_q_fn(h) if own_q_fn else ""
            cases.append(Case(fn, f"{scope_name} {h[:8]}", n, "authenticated", mem[h], types, values_fn(h),
                              key, sim, own_q=oq))
            if svc_on_big and i == 0:
                cases.append(Case(fn, f"{scope_name} {h[:8]}", n, "service_role", None, types, values_fn(h),
                                  key, sim, own_q=oq))

    # seeded hive plan: the largest and the smallest member hive that holds fault rows, then the others
    fh = [h for h, _ in sorted(sc.get("fault_hive", {}).items(), key=lambda kv: (-kv[1], kv[0])) if h in mem]
    big_h, small_h = (fh[0], fh[-1]) if len(fh) >= 2 else (None, None)
    others = [h for h in sorted(sc.get("fault_hive", {})) if h not in (big_h, small_h)][:4]
    plan = ([(big_h, LARGE_SEED), (small_h, SMALL_SEED)] + [(h, OTHER_SEED) for h in others]) if big_h else []
    small_lo = LARGE_SEED + 1                                       # the small hive's first seeded rn

    def seeded_member_cases(fn, seed, types, values_fn, key, sim, svc_on_big=False, extra_seed_rows=0):
        if not plan:
            return
        for h, n in ((big_h, LARGE_SEED), (small_h, SMALL_SEED)):
            oq = nth_vector(1 if h == big_h else small_lo)
            cases.append(Case(fn, f"hive {h[:8]}", n + extra_seed_rows, "authenticated", mem[h], types, values_fn(h),
                              key, sim, seed=seed, own_q=oq, seeded=True))
            if svc_on_big and h == big_h:
                cases.append(Case(fn, f"hive {h[:8]}", n + extra_seed_rows, "service_role", None, types,
                                  values_fn(h), key, sim, seed=seed, own_q=oq, seeded=True))

    # 1 search_fault_knowledge: hive scope (member, + service_role as semantic-search calls it), and the own scope
    fk_types = ["vector", "uuid", "integer", "uuid"]
    member_cases("search_fault_knowledge", sc.get("fault_hive"), fk_types,
                 lambda h: [q, f"{lit(h)}::uuid", str(K), "NULL::uuid"], "id::text", "similarity", svc_on_big=True)
    for i, (o, n) in enumerate(big_small(sc.get("fault_owner"))):
        cases.append(Case("search_fault_knowledge", f"own {o[:8]}", n, "authenticated", o, fk_types,
                          [q, "NULL::uuid", str(K), f"{lit(o)}::uuid"], "id::text", "similarity"))
        if i == 0:   # own-knowledge.ts: the service-role client naming the verified owner
            cases.append(Case("search_fault_knowledge", f"own {o[:8]}", n, "service_role", None, fk_types,
                              [q, "NULL::uuid", str(K), f"{lit(o)}::uuid"], "id::text", "similarity"))

    # 2 search_all_knowledge: four hive branches (fault/skill/pm/project - project seeded) + the own fault branch
    proj_seed = seed_sql("public.project_knowledge (hive_id, source_type, project_code, project_type, text_chunk, "
                         "embedding)", f"p.hive, 'project_lesson', 'VSR', 'seed', {lit(SEED_TAG)}, s.embedding",
                         plan, first_rn=5001) if plan else ""
    for i, (h, n) in enumerate(big_small(sc.get("fault_hive"), allowed=mem)):
        extra = LARGE_SEED if h == big_h else (SMALL_SEED if h == small_h else OTHER_SEED)
        for role in (("authenticated", "service_role") if i == 0 else ("authenticated",)):
            cases.append(Case("search_all_knowledge", f"hive {h[:8]} (fault+skill+pm+project)",
                              n + sc.get("pm_hive", {}).get(h, 0) + sc.get("skill_hive", {}).get(h, 0) + extra,
                              role, mem[h] if role == "authenticated" else None, fk_types,
                              [q, f"{lit(h)}::uuid", str(K), "NULL::uuid"], "source || ':' || md5(summary)",
                              "similarity", seed=proj_seed, seeded=True))
    for o, n in big_small(sc.get("fault_owner"))[:1]:
        cases.append(Case("search_all_knowledge", f"own {o[:8]}", n, "authenticated", o, fk_types,
                          [q, "NULL::uuid", str(K), f"{lit(o)}::uuid"], "source || ':' || md5(summary)",
                          "similarity"))

    # 3 search_skill_knowledge / 4 search_pm_knowledge: semantic-search calls them on a service-role client
    h3 = ["vector", "uuid", "integer"]
    member_cases("search_skill_knowledge", sc.get("skill_hive"), h3, lambda h: [q, f"{lit(h)}::uuid", str(K)],
                 "id::text", "similarity",
                 own_q_fn=lambda h: f"SELECT embedding::text FROM public.skill_knowledge WHERE hive_id = {lit(h)} "
                                    f"AND embedding IS NOT NULL ORDER BY id LIMIT 1")
    seeded_member_cases("search_skill_knowledge",
                        # one row per (hive, worker, discipline) - skill_knowledge_one_per_worker_discipline
                        seed_sql("public.skill_knowledge (hive_id, worker_name, discipline, level, primary_skill, "
                                 "embedding)", "p.hive, 'vsr-seed-' || s.rn, 'Mechanical', 1, 'seed', s.embedding",
                                 plan),
                        h3, lambda h: [q, f"{lit(h)}::uuid", str(K)], "id::text", "similarity", svc_on_big=True)
    member_cases("search_pm_knowledge", sc.get("pm_hive"), h3, lambda h: [q, f"{lit(h)}::uuid", str(K)],
                 "id::text", "similarity", svc_on_big=True,
                 own_q_fn=lambda h: f"SELECT embedding::text FROM public.pm_knowledge WHERE hive_id = {lit(h)} "
                                    f"AND embedding IS NOT NULL ORDER BY id LIMIT 1")

    # 5 search_bom_knowledge / 6 search_calc_knowledge: empty locally - seeded
    seeded_member_cases("search_bom_knowledge",
                        seed_sql("public.bom_knowledge (hive_id, project_name, calc_type, key_spec, item_count, notes, "
                                 "embedding)", f"p.hive, 'vsr-seed', 'seed', 'seed', 1, {lit(SEED_TAG)}, s.embedding",
                                 plan), h3, lambda h: [q, f"{lit(h)}::uuid", str(K)], "id::text", "similarity",
                        svc_on_big=True)
    seeded_member_cases("search_calc_knowledge",
                        seed_sql("public.calc_knowledge (hive_id, calc_type, project_ref, key_inputs, key_outputs, "
                                 "notes, embedding)",
                                 f"p.hive, 'seed', 'vsr-seed', '{{}}'::jsonb, '{{}}'::jsonb, {lit(SEED_TAG)}, "
                                 "s.embedding", plan),
                        h3, lambda h: [q, f"{lit(h)}::uuid", str(K)], "id::text", "similarity", svc_on_big=True)

    # 7 search_voice_journal_entries: EXECUTE is service_role-only (journal-recall.ts); scope = one person
    for u, n in big_small(sc.get("voice_user")):
        cases.append(Case("search_voice_journal_entries", f"person {u[:8]}", n, "service_role", None,
                          ["vector", "uuid", "integer"], [q, f"{lit(u)}::uuid", str(K)], "id::text", "similarity",
                          own_q=f"SELECT embedding::text FROM public.voice_journal_entries WHERE auth_uid = {lit(u)} "
                                f"AND embedding IS NOT NULL ORDER BY id LIMIT 1"))

    # 8 match_procedural_memories: service_role-only; no procedural rows locally - seeded
    if plan:
        pm_seed = seed_sql("public.agent_episodic_memory (hive_id, worker_name, memory_type, content, embedding)",
                           f"p.hive, 'vsr-seed', 'procedural', {lit(SEED_TAG)}, s.embedding", plan)
        for h, n in ((big_h, LARGE_SEED), (small_h, SMALL_SEED)):
            cases.append(Case("match_procedural_memories", f"hive {h[:8]}", n, "service_role", None,
                              ["vector", "uuid", "text", "integer", "real"],
                              [q, f"{lit(h)}::uuid", "NULL::text", str(K), "-1"], "id::text", "similarity",
                              seed=pm_seed, own_q=nth_vector(1 if h == big_h else small_lo), seeded=True))

    # 9 match_persona_knowledge: persona-knowledge.ts, service-role client; scope = a persona scope
    for s_, n in big_small(sc.get("persona")):
        cases.append(Case("match_persona_knowledge", f"persona '{s_}'", n, "service_role", None,
                          ["vector", "text[]", "integer", "double precision"],
                          [q, f"ARRAY[{lit(s_)}]::text[]", str(K), "-1"], "id::text", "similarity",
                          own_q=f"SELECT embedding::text FROM public.persona_knowledge WHERE persona_scope = {lit(s_)} "
                                f"AND embedding IS NOT NULL ORDER BY id LIMIT 1"))

    # 10 semantic_search_kb: voice-handler.js, as the member; empty locally - seeded
    if plan:
        kb_seed = ("INSERT INTO public.kb_documents (hive_id, title) SELECT hive, " + lit(SEED_TAG) +
                   " FROM (VALUES " + ", ".join(f"({lit(h)}::uuid)" for h, _ in plan) + ") v(hive); " +
                   seed_sql("public.kb_chunks (doc_id, chunk_num, text, embedding)",
                            f"(SELECT d.id FROM public.kb_documents d WHERE d.hive_id = p.hive AND d.title = "
                            f"{lit(SEED_TAG)} ORDER BY d.id DESC LIMIT 1), s.rn::int, {lit(SEED_TAG)}, s.embedding",
                            plan))
        seeded_member_cases("semantic_search_kb", kb_seed, ["uuid", "vector", "real", "integer"],
                            lambda h: [f"{lit(h)}::uuid", q, "-1", str(K)], "chunk_id::text", "1 - similarity_score")

    # 11 semantic_search_kg_facts: the real hive (largest) + a seeded 3-fact hive (smallest)
    kg_types = ["uuid", "vector", "real", "integer", "real"]
    for h, n in big_small(sc.get("kgf_hive"), allowed=mem)[:1]:
        cases.append(Case("semantic_search_kg_facts", f"hive {h[:8]}", n, "authenticated", mem[h], kg_types,
                          [f"{lit(h)}::uuid", q, "-1", str(K), "0.5"], "fact_id::text", "1 - similarity_score",
                          own_q=f"SELECT embedding::text FROM public.knowledge_graph_facts WHERE hive_id = {lit(h)} "
                                f"AND embedding IS NOT NULL ORDER BY id LIMIT 1"))
    if plan:
        kg_seed = seed_sql("public.knowledge_graph_facts (hive_id, subject_type, subject_ref, predicate, object_type, "
                           "object_ref, claim_text, confidence, active, source_type, embedding)",
                           f"p.hive, 'asset', 'vsr-' || s.rn, 'relates_to', 'asset', 'vsr', {lit(SEED_TAG)}, 0.9, "
                           "true, 'logbook', s.embedding", [(small_h, 3)], first_rn=7001)
        cases.append(Case("semantic_search_kg_facts", f"hive {small_h[:8]}", 3, "authenticated", mem[small_h],
                          kg_types, [f"{lit(small_h)}::uuid", q, "-1", str(K), "0.5"], "fact_id::text",
                          "1 - similarity_score", seed=kg_seed, own_q=nth_vector(7001), seeded=True))

    # 12 semantic_search_platform_kg_facts: platform-wide, filtered by active + confidence; empty locally - seeded
    any_member = next(iter(sorted(mem.values())), None)
    if any_member:
        pk_seed = ("WITH src AS (SELECT embedding, row_number() OVER (ORDER BY id) AS rn FROM public.fault_knowledge "
                   "WHERE embedding IS NOT NULL) INSERT INTO public.platform_knowledge_graph_facts (subject_type, "
                   "subject_ref, predicate, object_type, object_ref, claim_text, confidence, active, source_type, "
                   "embedding) SELECT 'asset', 'vsr-' || rn, 'relates_to', 'asset', 'vsr', " + lit(SEED_TAG) +
                   ", CASE WHEN rn <= 5 THEN 0.99 WHEN rn % 3 = 0 THEN 0.9 ELSE 0.2 END, (rn <= 5 OR rn % 2 = 0), "
                   "'standard', embedding FROM src WHERE rn <= 2000;")
        for conf, n in (("0.5", 5 + 333), ("0.95", 5)):
            cases.append(Case("semantic_search_platform_kg_facts", f"active, confidence >= {conf}", n,
                              "authenticated", any_member, ["vector", "real", "integer", "real"],
                              [q, "-1", str(K), conf], "fact_id::text", "1 - similarity_score", seed=pk_seed,
                              own_q=nth_vector(6), seeded=True))

    # 13 semantic_search_industry_standards: platform-wide (every family) + a seeded 5-chunk family
    if any_member:
        st_types = ["vector", "real", "integer", "text"]
        n_all = sc.get("standards", {}).get("all", 0)
        if n_all:
            cases.append(Case("semantic_search_industry_standards", "every family", n_all, "authenticated",
                              any_member, st_types, [q, "-1", str(K), "NULL::text"], "chunk_id::text",
                              "1 - similarity_score",
                              own_q="SELECT embedding::text FROM public.industry_standards_chunks "
                                    "WHERE embedding IS NOT NULL ORDER BY id LIMIT 1"))
        st_seed = ("INSERT INTO public.industry_standards (standard_code, family, title) VALUES ('VSR-SEED-0001', "
                   "'iec', " + lit(SEED_TAG) + "); " +
                   "WITH src AS (SELECT embedding, row_number() OVER (ORDER BY id) AS rn FROM public.fault_knowledge "
                   "WHERE embedding IS NOT NULL) INSERT INTO public.industry_standards_chunks (standard_id, chunk_num, "
                   "text, embedding) SELECT (SELECT id FROM public.industry_standards WHERE standard_code = "
                   "'VSR-SEED-0001'), rn::int, " + lit(SEED_TAG) + ", embedding FROM src WHERE rn BETWEEN 9001 AND "
                   "9005;")
        cases.append(Case("semantic_search_industry_standards", "family 'iec'", 5, "authenticated", any_member,
                          st_types, [q, "-1", str(K), "'iec'::text"], "chunk_id::text", "1 - similarity_score",
                          seed=st_seed, own_q=nth_vector(9001), seeded=True))
    return cases


COVERED = {"search_fault_knowledge", "search_all_knowledge", "search_skill_knowledge", "search_pm_knowledge",
           "search_bom_knowledge", "search_calc_knowledge", "search_voice_journal_entries",
           "match_procedural_memories", "match_persona_knowledge", "semantic_search_kb", "semantic_search_kg_facts",
           "semantic_search_platform_kg_facts", "semantic_search_industry_standards"}


# ── the probe ────────────────────────────────────────────────────────────────────────────────────
PASSES = (("G", "force_generic_plan", False), ("C", "force_custom_plan", False), ("T", "force_custom_plan", True))


def build_probe(c: Case, qv: list[str], mutation: str = "") -> str:
    out = []
    for i, fid in enumerate(qv):
        out.append(f"select embedding::text as q{i} from public.fault_knowledge where id = {lit(fid)} \\gset")
    out.append("BEGIN;")
    out.append("SET LOCAL lock_timeout = '5s';")
    out.append("SET LOCAL statement_timeout = '180s';")
    if mutation:
        out.append(mutation)
    if c.seed:
        out.append(c.seed)
    nq = len(qv)
    if c.own_q:
        out.append(f"SELECT x AS q{nq} FROM ({c.own_q}) t(x) \\gset")
        nq += 1
    claims = {"sub": c.sub, "role": "authenticated"} if c.role == "authenticated" else {"role": "service_role"}
    out.append(f"SELECT set_config('request.jwt.claims', {lit(json.dumps(claims))}, true);")
    out.append(f"SET LOCAL ROLE {c.role};")
    params = ", ".join(f"${i + 1}" for i in range(len(c.types)))
    sel = f"SELECT ({c.key}) || chr(31) || (({c.sim}))::float8::text FROM public.{c.fn}({params}) AS r"
    for tag, mode, exact in PASSES:
        if exact:
            out.append("DISCARD PLANS;")
            out.append("SET LOCAL enable_indexscan = off;")
        out.append(f"SET LOCAL plan_cache_mode = {mode};")
        out.append(f"PREPARE vsr_{tag.lower()}({', '.join(c.types)}) AS {sel};")
        out.append("\\timing on")
        for i in range(nq):
            vals = ", ".join(v.replace("{q}", f":'q{i}'::vector") for v in c.values)
            out.append(f"SELECT 'QB' || chr(31) || '{tag}' || chr(31) || '{i}';")
            out.append(f"EXECUTE vsr_{tag.lower()}({vals});")
            out.append("SELECT 'QE';")
        out.append("\\timing off")
    out.append("RESET ROLE;")
    out.append("ROLLBACK;")
    return "\n".join(out) + "\n"


def parse_probe(stdout: str) -> tuple[dict, dict]:
    rows: dict = {}
    times: dict = {}
    cur = None
    last_time = None
    for ln in lines(stdout):
        if ln.startswith("Time: "):
            try:
                last_time = float(ln.split()[1])
            except (IndexError, ValueError):
                pass
            continue
        p = ln.split(US)
        if p[0] == "QB" and len(p) >= 3:
            cur = (p[1], int(p[2]))
            rows[cur] = []
            last_time = None
            continue
        if p[0] == "QE":
            if cur is not None and last_time is not None:
                times[cur] = last_time
            cur = None
            continue
        if cur is not None and len(p) >= 2:
            try:
                rows[cur].append((p[0], float(p[1])))
            except ValueError:
                pass
    return rows, times


def recall(got: list, truth: list) -> float:
    if not truth:
        return 1.0
    gk, tk = Counter(k for k, _ in got), Counter(k for k, _ in truth)
    missing = tk - gk
    if not missing:
        return 1.0
    extra = gk - tk

    def take(rows: list, want: Counter) -> list:
        left, out = Counter(want), []
        for k, s in rows:
            if left[k] > 0:
                left[k] -= 1
                out.append(s)
        return out

    miss_s, ex_s = take(truth, missing), take(got, extra)
    unmatched = 0
    for s in miss_s:                 # a missing row tied at the same distance with a returned extra is not a loss
        j = next((i for i, e in enumerate(ex_s) if abs(e - s) <= EPS), None)
        if j is None:
            unmatched += 1
        else:
            ex_s.pop(j)
    return (len(truth) - unmatched) / len(truth)


@dataclass
class Result:
    case: Case
    err: str = ""
    recall: dict = field(default_factory=dict)     # pass -> min recall over questions
    mean: dict = field(default_factory=dict)       # pass -> mean recall over questions
    worst: dict = field(default_factory=dict)      # pass -> (found, truth) of the worst question
    truth_rows: int = 0
    lat: dict = field(default_factory=dict)        # pass -> median ms (warm executions)


def run_case(c: Case, qv: list[str], mutation: str = "") -> Result:
    rc, out, err = psql(build_probe(c, qv, mutation))
    r = Result(c)
    if rc != 0:
        r.err = (err or out).strip().replace("\n", " ")[:300]
        return r
    rows, times = parse_probe(out)
    nq = max((i for (_, i) in rows), default=-1) + 1
    for tag in ("G", "C"):
        worst, wpair, every = 1.0, (0, 0), []
        for i in range(nq):
            t = rows.get(("T", i), [])
            g = rows.get((tag, i), [])
            rc_ = recall(g, t)
            if t:
                every.append(rc_)
            if rc_ < worst or (rc_ == worst and not wpair[1]):
                worst, wpair = rc_, (round(rc_ * len(t)), len(t))
        r.recall[tag] = worst
        r.mean[tag] = statistics.mean(every) if every else 1.0
        r.worst[tag] = wpair
    r.truth_rows = max((len(rows.get(("T", i), [])) for i in range(nq)), default=0)
    for tag in ("G", "C", "T"):
        ts = [times[(tag, i)] for i in range(1, nq) if (tag, i) in times]   # the first one pays for planning
        r.lat[tag] = statistics.median(ts) if ts else None
    return r


def evaluate(d: dict, mutations: dict | None = None, only: set | None = None, quiet: bool = False
             ) -> tuple[list[str], list[Result]]:
    fails: list[str] = []
    uncovered = sorted(set(d["fns"]) - COVERED)
    for fn in uncovered:
        fails.append(f"V1 {fn} orders by a vector distance and has no case in this gate - add one (largest + "
                     f"smallest scope, the real principal)")
    for v in sorted(d["views"]):
        fails.append(f"V1 view {v} uses a vector distance and has no case in this gate")
    if len(d["qv"]) < 3:
        fails.append("V3 fewer than 3 embedded fault_knowledge rows to ask questions with - nothing can be measured")
        return fails, []
    results: list[Result] = []
    cases = [c for c in build_cases(d) if only is None or c.fn in only]
    for fn in sorted(COVERED & set(d["fns"])):
        if (only is None or fn in only) and not any(c.fn == fn for c in cases):
            fails.append(f"V3 {fn}: no scope with rows and a member to act as - the gate measured nothing for it")
    for c in cases:
        mut = (mutations or {}).get(c.fn, "")
        r = run_case(c, d["qv"], mut)
        results.append(r)
        if not quiet:
            print_row(r)
        if r.err:
            fails.append(f"V2 {c.fn} [{c.label}] the probe failed: {r.err}")
            continue
        if r.truth_rows == 0:
            fails.append(f"V3 {c.fn} [{c.label}] the exact truth is empty for every question - nothing was compared")
            continue
        for tag, name in (("G", "generic plan (how PostgREST runs an RPC)"), ("C", "custom plan")):
            if r.recall.get(tag, 0) < 1.0:
                f_, t_ = r.worst[tag]
                fails.append(f"V2 {c.fn} [{c.label}] {name}: recall@{K} {r.recall[tag]:.2f} - the worst question "
                             f"returned {f_} of the scope's {t_} nearest rows")
    return fails, results


def fmt_ms(v) -> str:
    return "   -   " if v is None else f"{v:7.1f}"


def print_header() -> None:
    print(f"  {'function':36} {'scope':58} {'recall@k generic':>16} {'recall@k custom':>16} {'ms gen':>7} "
          f"{'ms exact':>8}")
    print(f"  {'':36} {'':58} {'(worst / mean)':>16} {'(worst / mean)':>16}")


def print_row(r: Result) -> None:
    if r.err:
        print(f"  {r.case.fn:36} {r.case.label[:58]:58} {RED}ERROR{RST} {r.err[:120]}")
        return

    def col(tag: str) -> str:
        v, m = r.recall.get(tag, 0), r.mean.get(tag, 0)
        return f"{GREEN if v >= 1.0 else RED}{v:7.2f} / {m:4.2f}{RST}  "

    print(f"  {r.case.fn:36} {r.case.label[:58]:58} {col('G')} {col('C')} {fmt_ms(r.lat.get('G'))} "
          f"{fmt_ms(r.lat.get('T')):>8}")


# ── teeth: the bodies before 20261008000002, recreated inside each case's rolled-back transaction ──
# (name, function, CREATE OR REPLACE text, must_fail). Taken verbatim from pg_get_functiondef() before the fix ran.
# must_fail = the pre-fix body MEASURED below 1.0 on a plan this gate can reproduce every run, so it must FAIL V2.
# Reported only: skill / voice / standards (exact today only because the planner prefers the btree on today's
# statistics), and bom / calc - they DID measure 0.20 / 0.10 under a custom plan, but their tables are empty and the
# seeded rows are planned from the table's vacuum state (relpages/reltuples), which flips between runs. Holding that
# fixed would need ANALYZE, whose relpages/reltuples write is in-place and survives the ROLLBACK - not worth a
# persistent side effect on a gate that must leave nothing behind.
PRE_FIX: list[tuple[str, str, str, bool]] = [
    ("the pre-20261008000002 search_fault_knowledge (measured under 1.0)", "search_fault_knowledge", r"""CREATE OR REPLACE FUNCTION public.search_fault_knowledge(query_embedding vector, match_hive_id uuid, match_count integer DEFAULT 5, match_owner uuid DEFAULT NULL::uuid)
 RETURNS TABLE(id uuid, machine text, problem text, root_cause text, action text, knowledge text, worker_name text, similarity double precision)
 LANGUAGE sql
 STABLE
AS $function$
  SELECT id, machine, problem, root_cause, action, knowledge, worker_name, similarity FROM (
    -- HIVE scope: the pre-20261007000014 predicate, so it plans as it did (hive index + distance sort).
    SELECT h.id, h.machine, h.problem, h.root_cause, h.action, h.knowledge, h.worker_name, h.similarity FROM (
      SELECT f.id, f.machine, f.problem, f.root_cause, f.action, f.knowledge, f.worker_name,
             1 - (f.embedding <=> query_embedding) AS similarity
        FROM fault_knowledge f
       WHERE match_hive_id IS NOT NULL AND f.embedding IS NOT NULL AND f.hive_id = match_hive_id
       ORDER BY f.embedding <=> query_embedding
       LIMIT match_count
    ) h
    UNION ALL
    -- OWN scope: a hive-less row belongs to the person who wrote its entry. The owner is the CALLER (auth.uid());
    -- match_owner is honoured only for a server role that has already resolved the person. Exact, never probed.
    SELECT o.id, o.machine, o.problem, o.root_cause, o.action, o.knowledge, o.worker_name, o.similarity FROM (
      WITH mine AS MATERIALIZED (
        SELECT f.id, f.machine, f.problem, f.root_cause, f.action, f.knowledge, f.worker_name, f.embedding
          FROM fault_knowledge f
         WHERE match_hive_id IS NULL AND f.hive_id IS NULL AND f.embedding IS NOT NULL
           AND f.auth_uid = COALESCE(auth.uid(),
                                     CASE WHEN current_user IN ('service_role', 'postgres') THEN match_owner END)
      )
      SELECT m.id, m.machine, m.problem, m.root_cause, m.action, m.knowledge, m.worker_name,
             1 - (m.embedding <=> query_embedding) AS similarity
        FROM mine m
       ORDER BY m.embedding <=> query_embedding
       LIMIT match_count
    ) o
  ) r
  ORDER BY similarity DESC;
$function$;""", True),
    ("the pre-20261008000002 search_all_knowledge (measured under 1.0)", "search_all_knowledge", r"""CREATE OR REPLACE FUNCTION public.search_all_knowledge(query_embedding vector, match_hive_id uuid, match_count integer DEFAULT 3, match_owner uuid DEFAULT NULL::uuid)
 RETURNS TABLE(source text, summary text, similarity double precision)
 LANGUAGE sql
 STABLE
AS $function$
  SELECT source, summary, similarity FROM (
    SELECT 'fault' AS source,
      CONCAT('Machine: ', machine, ' | Problem: ', problem,
             ' | Root cause: ', root_cause, ' | Fix: ', action) AS summary,
      1 - (embedding <=> query_embedding) AS similarity
    FROM fault_knowledge
    WHERE match_hive_id IS NOT NULL AND embedding IS NOT NULL AND hive_id = match_hive_id
    ORDER BY embedding <=> query_embedding LIMIT match_count
  ) f

  UNION ALL

  -- OWN scope (hive-less person): only fault_knowledge carries an owner column, so it is the only branch that
  -- answers it; the branches below keep hive_id = match_hive_id, which a NULL never meets. Exact, never probed.
  SELECT source, summary, similarity FROM (
    WITH mine AS MATERIALIZED (
      SELECT machine, problem, root_cause, action, embedding
        FROM fault_knowledge
       WHERE match_hive_id IS NULL AND hive_id IS NULL AND embedding IS NOT NULL
         AND auth_uid = COALESCE(auth.uid(),
                                 CASE WHEN current_user IN ('service_role', 'postgres') THEN match_owner END)
    )
    SELECT 'fault' AS source,
      CONCAT('Machine: ', machine, ' | Problem: ', problem,
             ' | Root cause: ', root_cause, ' | Fix: ', action) AS summary,
      1 - (embedding <=> query_embedding) AS similarity
    FROM mine
    ORDER BY embedding <=> query_embedding LIMIT match_count
  ) fo

  UNION ALL

  SELECT source, summary, similarity FROM (
    SELECT 'skill' AS source,
      CONCAT('Worker: ', worker_name, ' | Discipline: ', discipline,
             ' | Level: ', level::text, ' | Primary: ', primary_skill) AS summary,
      1 - (embedding <=> query_embedding) AS similarity
    FROM skill_knowledge
    WHERE hive_id = match_hive_id AND embedding IS NOT NULL
    ORDER BY embedding <=> query_embedding LIMIT match_count
  ) s

  UNION ALL

  SELECT source, summary, similarity FROM (
    SELECT 'pm' AS source,
      CONCAT('Asset: ', asset_name, ' | Category: ', category,
             ' | Overdue tasks: ', overdue_count::text, ' | ', health_summary) AS summary,
      1 - (embedding <=> query_embedding) AS similarity
    FROM pm_knowledge
    WHERE hive_id = match_hive_id AND embedding IS NOT NULL
    ORDER BY embedding <=> query_embedding LIMIT match_count
  ) p

  UNION ALL

  -- PJ15: the branch that was missing. Everything above it was readable; project lessons and scope
  -- items were embedded into a table nothing queried.
  SELECT source, summary, similarity FROM (
    SELECT 'project' AS source,
      CONCAT('Project: ', COALESCE(project_code, '?'),
             ' (', COALESCE(project_type, 'project'), ')',
             ' | Record: ', COALESCE(source_type, 'note'),
             ' | ', COALESCE(text_chunk, '')) AS summary,
      1 - (embedding <=> query_embedding) AS similarity
    FROM project_knowledge
    WHERE hive_id = match_hive_id AND embedding IS NOT NULL
    ORDER BY embedding <=> query_embedding LIMIT match_count
  ) pr;
$function$;""", True),
    ("the pre-20261008000002 search_skill_knowledge (structural: measured exact on this data)", "search_skill_knowledge", r"""CREATE OR REPLACE FUNCTION public.search_skill_knowledge(query_embedding vector, match_hive_id uuid, match_count integer DEFAULT 5)
 RETURNS TABLE(id uuid, worker_name text, discipline text, level integer, primary_skill text, similarity double precision)
 LANGUAGE sql
 STABLE
 SET search_path TO 'pg_catalog', 'public'
AS $function$
  SELECT
    id, worker_name, discipline, level, primary_skill,
    1 - (embedding <=> query_embedding) AS similarity
  FROM skill_knowledge
  WHERE hive_id = match_hive_id
    AND embedding IS NOT NULL
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$function$;""", False),
    ("the pre-20261008000002 search_pm_knowledge (measured under 1.0)", "search_pm_knowledge", r"""CREATE OR REPLACE FUNCTION public.search_pm_knowledge(query_embedding vector, match_hive_id uuid, match_count integer DEFAULT 5)
 RETURNS TABLE(id uuid, asset_name text, category text, overdue_count integer, last_completed timestamp with time zone, health_summary text, similarity double precision)
 LANGUAGE sql
 STABLE
AS $function$
  SELECT
    id, asset_name, category, overdue_count, last_completed, health_summary,
    1 - (embedding <=> query_embedding) AS similarity
  FROM pm_knowledge
  WHERE hive_id = match_hive_id
    AND embedding IS NOT NULL
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$function$;""", True),
    ("the pre-20261008000002 search_bom_knowledge (seeded: measured 0.20; plan follows the table's vacuum state)",
     "search_bom_knowledge", r"""CREATE OR REPLACE FUNCTION public.search_bom_knowledge(query_embedding vector, match_hive_id uuid, match_count integer DEFAULT 5)
 RETURNS TABLE(id uuid, project_name text, calc_type text, key_spec text, item_count integer, notes text, similarity double precision)
 LANGUAGE sql
 STABLE
AS $function$
  SELECT
    id, project_name, calc_type, key_spec, item_count, notes,
    1 - (embedding <=> query_embedding) AS similarity
  FROM bom_knowledge
  WHERE hive_id = match_hive_id
    AND embedding IS NOT NULL
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$function$;""", False),
    ("the pre-20261008000002 search_calc_knowledge (seeded: measured 0.10 once; plan follows the table's vacuum state)",
     "search_calc_knowledge", r"""CREATE OR REPLACE FUNCTION public.search_calc_knowledge(query_embedding vector, match_hive_id uuid, match_count integer DEFAULT 5)
 RETURNS TABLE(id uuid, calc_type text, project_ref text, key_inputs jsonb, key_outputs jsonb, notes text, similarity double precision)
 LANGUAGE sql
 STABLE
AS $function$
  SELECT
    id, calc_type, project_ref, key_inputs, key_outputs, notes,
    1 - (embedding <=> query_embedding) AS similarity
  FROM calc_knowledge
  WHERE hive_id = match_hive_id
    AND embedding IS NOT NULL
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$function$;""", False),
    ("the pre-20261008000002 search_voice_journal_entries (structural: measured exact on this data)", "search_voice_journal_entries", r"""CREATE OR REPLACE FUNCTION public.search_voice_journal_entries(query_embedding vector, match_auth_uid uuid, match_count integer DEFAULT 5)
 RETURNS TABLE(id uuid, transcript text, reply text, lang text, created_at timestamp with time zone, similarity double precision)
 LANGUAGE sql
 STABLE
 SET search_path TO 'public', 'pg_catalog'
AS $function$
  -- Per-user scope only. hive_id is intentionally NOT part of the filter:
  -- the voice journal is a private per-worker diary, not a hive-scoped
  -- knowledge surface. Isolation is enforced by auth_uid alignment with
  -- the RLS policies on voice_journal_entries. Other vector search RPCs
  -- (search_calc_knowledge, search_bom_knowledge, etc.) scope by hive_id
  -- because their underlying tables are hive-shared; this one is not.
  SELECT
    vje.id,
    vje.transcript,
    vje.reply,
    vje.lang,
    vje.created_at,
    1 - (vje.embedding <=> query_embedding) AS similarity
  FROM public.voice_journal_entries vje
  WHERE vje.auth_uid = match_auth_uid
    AND vje.embedding IS NOT NULL
  ORDER BY vje.embedding <=> query_embedding
  LIMIT match_count;
$function$;""", False),
    ("the pre-20261008000002 semantic_search_kb (measured under 1.0)", "semantic_search_kb", r"""CREATE OR REPLACE FUNCTION public.semantic_search_kb(p_hive_id uuid, p_query_embedding vector, p_similarity_threshold real DEFAULT 0.7, p_limit integer DEFAULT 5)
 RETURNS TABLE(chunk_id bigint, doc_id bigint, doc_title text, chunk_text text, similarity_score real)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
begin
  if not public.user_can_access_hive(p_hive_id) then return; end if;
  return query
  select kc.id, kc.doc_id, kd.title, kc.text, (kc.embedding <=> p_query_embedding) as sim
  from kb_chunks kc join kb_documents kd on kc.doc_id = kd.id
  where kd.hive_id = p_hive_id and kc.embedding is not null
    and (kc.embedding <=> p_query_embedding) <= (1 - p_similarity_threshold)
  order by kc.embedding <=> p_query_embedding
  limit p_limit;
end;
$function$;""", True),
    ("the pre-20261008000002 semantic_search_platform_kg_facts (measured under 1.0)", "semantic_search_platform_kg_facts", r"""CREATE OR REPLACE FUNCTION public.semantic_search_platform_kg_facts(p_query_embedding vector, p_similarity_threshold real DEFAULT 0.5, p_limit integer DEFAULT 5, p_min_confidence real DEFAULT 0.5)
 RETURNS TABLE(fact_id uuid, subject_ref text, predicate text, object_ref text, claim_text text, confidence numeric, source_type text, source_ref text, similarity_score real)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
BEGIN
  RETURN QUERY
  SELECT
    f.id                                AS fact_id,
    f.subject_ref,
    f.predicate,
    f.object_ref,
    f.claim_text,
    f.confidence,
    f.source_type,
    f.source_ref,
    (f.embedding <=> p_query_embedding)::real AS similarity_score
  FROM public.platform_knowledge_graph_facts f
  WHERE f.active     = true
    AND f.embedding  IS NOT NULL
    AND f.confidence >= p_min_confidence
    AND (f.embedding <=> p_query_embedding) <= (1 - p_similarity_threshold)
  ORDER BY f.embedding <=> p_query_embedding
  LIMIT p_limit;
END;
$function$;""", True),
    ("the pre-20261008000002 semantic_search_industry_standards (structural: measured exact on this data)", "semantic_search_industry_standards", r"""CREATE OR REPLACE FUNCTION public.semantic_search_industry_standards(p_query_embedding vector, p_similarity_threshold real DEFAULT 0.6, p_limit integer DEFAULT 5, p_family text DEFAULT NULL::text)
 RETURNS TABLE(chunk_id bigint, standard_id uuid, standard_code text, standard_title text, family text, section text, chunk_text text, similarity_score real, source_url text)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
BEGIN
  RETURN QUERY
  SELECT
    isc.id              AS chunk_id,
    s.id                AS standard_id,
    s.standard_code,
    s.title             AS standard_title,
    s.family,
    isc.section,
    isc.text            AS chunk_text,
    (isc.embedding <=> p_query_embedding)::real AS similarity_score,
    s.source_url
  FROM public.industry_standards_chunks isc
  JOIN public.industry_standards        s ON isc.standard_id = s.id
  WHERE isc.embedding IS NOT NULL
    AND (p_family IS NULL OR s.family = p_family)
    AND (isc.embedding <=> p_query_embedding) <= (1 - p_similarity_threshold)
  ORDER BY isc.embedding <=> p_query_embedding
  LIMIT p_limit;
END;
$function$;""", False),
    # The ORIGINAL finding (20261007000014's body): the own scope as one OR predicate - exact with literals, ivfflat
    # probes=1 under the generic plan PostgREST gets (a solo owner's 3 rows came back as 1).
    ("20261007000014's search_fault_knowledge: the own scope as one OR predicate", "search_fault_knowledge",
     """CREATE OR REPLACE FUNCTION public.search_fault_knowledge(query_embedding vector, match_hive_id uuid,
  match_count integer DEFAULT 5, match_owner uuid DEFAULT NULL)
RETURNS TABLE(id uuid, machine text, problem text, root_cause text, action text, knowledge text, worker_name text,
  similarity double precision) LANGUAGE sql STABLE AS $m$
  SELECT id, machine, problem, root_cause, action, knowledge, worker_name, 1 - (embedding <=> query_embedding)
    FROM fault_knowledge WHERE embedding IS NOT NULL AND (hive_id = match_hive_id OR (match_hive_id IS NULL
     AND hive_id IS NULL AND auth_uid = COALESCE(auth.uid(),
         CASE WHEN current_user IN ('service_role', 'postgres') THEN match_owner END)))
   ORDER BY embedding <=> query_embedding LIMIT match_count $m$;""", True),
]


def self_test(d: dict) -> int:
    ok = True
    base, _ = evaluate(d, quiet=True)
    mark = f"{GREEN}PASS{RST}" if not base else f"{RED}FAIL{RST}"
    print(f"  [{mark}] the current function bodies pass V1-V3" + ("" if not base else f": {base[:3]}"))
    ok &= not base
    if not PRE_FIX:
        print(f"  [{RED}FAIL{RST}] no pre-fix bodies recorded - the gate's teeth are unproven")
        return 1
    for name, fn, body, expect in PRE_FIX:
        fails, _ = evaluate(d, mutations={fn: body}, only={fn}, quiet=True)
        hit = [f for f in fails if f.startswith(f"V2 {fn} ")]
        if expect:
            mark = f"{GREEN}PASS{RST}" if hit else f"{RED}FAIL{RST}"
            print(f"  [{mark}] mutant '{name}' fails V2"
                  + (f" in {len(hit)} check(s); e.g. {hit[0][len(fn) + 4:][:170]}" if hit
                     else " - it PASSED, the gate has no teeth here"))
            ok &= bool(hit)
        else:
            print(f"  [{DIM}info{RST}] mutant '{name}': "
                  + (f"{len(hit)} V2 failure(s) - {hit[0][len(fn) + 4:][:150]}" if hit
                     else "exact on this data (a statistics change is what would flip it)"))
    return 0 if ok else 1


def main() -> int:
    print("=" * 100)
    print("  EVERY VECTOR SEARCH RETURNS ITS SCOPE'S TRUE NEAREST ROWS - under the plan PostgREST runs")
    print("=" * 100)
    d = discover()
    if d is None:
        return 0
    if "--self-test" in sys.argv[1:]:
        return self_test(d)
    only = None
    for a in sys.argv[1:]:
        if a.startswith("--only"):
            v = a.split("=", 1)[1] if "=" in a else sys.argv[sys.argv.index(a) + 1]
            only = {x.strip() for x in v.split(",") if x.strip()}
    print_header()
    fails, results = evaluate(d, only=only)
    print(f"\n  {len(d['fns'])} vector-search function(s) in the database · {len(results)} case(s) · k={K} · "
          f"{len(d['qv'])}+1 question(s) per case · passes: generic, custom, exact")
    if fails:
        for f in fails:
            print(f"    {RED}FAIL{RST} {f}")
        print(f"\n  {RED}FAIL{RST}: {len(fails)} finding(s)")
        return 1
    print(f"  {GREEN}PASS{RST} V1 every vector search in the database has a case")
    print(f"  {GREEN}PASS{RST} V2 every case returns its scope's true top-{K} under generic AND custom plans")
    print(f"  {GREEN}PASS{RST} V3 every case compared a non-empty exact truth")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
