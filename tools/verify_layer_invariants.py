#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VERIFY THE LAYER AND SEAM INVARIANTS — the instrument behind 136 bank rows
═══════════════════════════════════════════════════════════════════════════════════════════════════

The live-MCP bank carries 136 rows whose surface is a LAYER (layer_db, layer_edge, layer_cron,
layer_realtime, layer_storage, layer_ai, layer_client, layer_gateway) or a SEAM between two of them.
They assert things no page can show you: that the ledger conserves credits, that a grant has a
caller-aware policy behind it, that a DEFINER helper is not callable by a random signed-in user.

Until now they were walked BY HAND, which cost two things:

  1. They were declared to depend on marketplace.html + utils.js — the page that happened to be open
     when they were walked. That is wrong in both directions: every page edit expired 124 claims the
     page cannot affect, and a MIGRATION could change a grant without expiring anything. Mig 50
     revoked a SELECT this session and would not have moved a single one of them.

  2. A hand walk proves the invariant held on the afternoon someone looked. This file makes each one
     a QUERY, so the same claim can be re-earned in seconds, by anyone, forever.

Each check returns one of:

  pass        the invariant holds, with the numbers that show it
  fail        it does not, with the rows that break it
  needs-live  there is no honest DB/repo oracle for this cell; it needs the browser. Saying so keeps
              the row stale rather than dressing a structural check as a behavioural one (rule R6).

Run:  python tools/verify_layer_invariants.py            # all cells
      python tools/verify_layer_invariants.py --layer layer_db
      python tools/verify_layer_invariants.py --json     # for banking
"""
import argparse
import collections
import importlib.util
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTAINER = "supabase_db_workhive"

GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"


def q(sql):
    """One query, one answer. Returns stripped rows as a list of tuples of strings."""
    p = subprocess.run(
        ["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-F", "\x1f", "-c", sql],
        capture_output=True, text=True, timeout=120,
    )
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout).strip()[:400])
    out = []
    for line in (p.stdout or "").splitlines():
        line = line.rstrip()
        if not line or line.startswith("("):
            continue
        out.append(tuple(line.split("\x1f")))
    return out


def one(sql, default="0"):
    r = q(sql)
    return r[0][0] if r and r[0] else default


def qjson(sql):
    """Ask Postgres to do the serialising.

    q() splits psql's text output on a delimiter and skips lines beginning with '(' — a rule written
    to drop the "(N rows)" footer, which then silently ate every policy predicate, because a policy
    predicate starts with '(' too. 206 of 250 rows came back mangled and the check raised ValueError
    rather than lying, which is the only reason it was caught.

    A pretty-printed multi-line predicate has no safe text delimiter. JSON does: the database
    escapes it, json.loads unescapes it, and no separator has to be guessed."""
    # The subquery alias must be something no caller would ever name a column. With `... ) t` and
    # `json_agg(t)`, a query that selects `table_name as t` shadows the row reference — json_agg then
    # aggregates that STRING column instead of the row, and the caller gets a list of strings where
    # it expected dicts ("TypeError: string indices must be integers").
    raw = subprocess.run(
        ["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-c",
         f"select coalesce(json_agg(_qj_row), '[]'::json) from ({sql}) _qj_row"],
        capture_output=True, text=True, timeout=180,
    )
    if raw.returncode != 0:
        raise RuntimeError((raw.stderr or raw.stdout).strip()[:400])
    return json.loads((raw.stdout or "[]").strip() or "[]")


# ── layer_db ────────────────────────────────────────────────────────────────────────────────────

# Tables that may sit RLS-disabled with SELECT granted, because they hold no per-person and no
# per-tenant data. This list is the POINT of the check: anything granted-and-unpoliced that is NOT
# here is a finding, so the next table someone adds trips the gate instead of sliding in. Each entry
# was read column-by-column, not pattern-matched — voice_response_queue passed a column-name screen
# (its owner column is `worker_id`) and was a real leak.
REFERENCE_TABLES_OK_UNPOLICED = {
    "ai_terminology", "benchmark_values", "service_slo_targets", "terminology_gaps", "tts_cache",
    "fallback_model_faq", "avatar_animations", "ph_intelligence_reports", "cross_hive_alerts",
    "embedding_cache", "i18n_dictionary", "doc_embeddings", "industry_benchmarks",

    # Read column-by-column on 2026-08-05, not matched by name:
    #   best_practices              — id, created_at. An empty shell; there is nothing in it.
    #   equipment_reading_templates — category/reading_key/label/unit/placeholder. UI field config.
    #   multilingual_terms          — english/tagalog/visayan terms. The dictionary a landing page
    #                                 must read BEFORE anyone signs in (mig 43's stated reason for
    #                                 leaving SELECT alone).
    #   network_benchmarks          — aggregate MTBF by category. `sample_hives` is a COUNT, not a
    #                                 list of hives, so no tenant is identifiable from it.
    #   persona_knowledge           — the assistant's own reference corpus, keyed by persona_scope.
    "best_practices", "equipment_reading_templates", "multilingual_terms", "network_benchmarks",
    "persona_knowledge",
    # ai_global_budget is deliberately NOT here — it is live ops metering (shed/deny/spend counts),
    # not reference data, and mig 52 revokes it. If it reappears in this check, the revoke regressed.
}


def db_grant_matches_policy():
    """A grant with no caller-aware policy behind it IS a public table, whatever the UI does."""
    rows = q("""
        select c.relname,
               has_table_privilege('anon', c.oid, 'SELECT'),
               has_table_privilege('authenticated', c.oid, 'SELECT')
          from pg_class c join pg_namespace n on n.oid = c.relnamespace
         where n.nspname = 'public' and c.relkind = 'r' and c.relrowsecurity = false
           and (has_table_privilege('anon', c.oid, 'SELECT')
                or has_table_privilege('authenticated', c.oid, 'SELECT'))
         order by 1
    """)
    unexpected = [r for r in rows if r[0] not in REFERENCE_TABLES_OK_UNPOLICED]
    if unexpected:
        names = ", ".join(f"{r[0]}(anon={r[1]},auth={r[2]})" for r in unexpected[:8])
        return "fail", (f"{len(unexpected)} table(s) readable with RLS off and not on the reference "
                        f"allowlist: {names}")
    return "pass", (f"{len(rows)} RLS-disabled readable tables, every one a declared reference table "
                    f"with no per-person or per-tenant column")


def db_credits_conserved():
    """Conservation is only meaningful against an EXTERNAL anchor. Summing the ledger and comparing
    it to itself proves nothing; the question is whether the ledger agrees with the treasury that
    authorised the money. So: every credit the treasury says it issued must appear as a topup entry,
    and vice versa. A one-sided write — the class that passes every single-table guard — shows up
    here as a gap between the two numbers."""
    # THIS CHECK USED TO SUM ONLY `topup` ROWS, AND THAT IS WHY IT MISSED A REAL ONE-SIDED WRITE.
    # `issued_credits` does not mean "ever created" — every destroying path calls retire_credits() and
    # lowers it — so the number it must agree with is the WHOLE ledger, not the deposits half of it.
    # Summing topups alone made the check structurally incapable of seeing a debit that forgot to
    # retire: mint_settlement_commission wrote three negative rows totalling -360 and never touched the
    # treasury, and this check reported "issued 1500 == topups 1500 · pass" for as long as it existed
    # (mig 53 fixed the trigger and reconciled the drift). An invariant whose denominator excludes the
    # side that can break it is not an invariant.
    issued = one("select coalesce(max(issued_credits),0) from credit_treasury")
    total = one("select coalesce(sum(amount),0) from service_credit_ledger")
    topups = one("""select coalesce(sum(amount),0) from service_credit_ledger
                     where entry_type = 'topup'""")
    spent = one("""select coalesce(-sum(amount),0) from service_credit_ledger where amount < 0""")
    zero = one("select count(*) from service_credit_ledger where amount is null or amount = 0")
    if int(zero) > 0:
        return "fail", f"{zero} ledger row(s) carry a null or zero amount — a move that moved nothing"
    try:
        if abs(float(issued) - float(total)) > 0.005:
            # Name the suspects rather than just the gap: a transfer pair nets to zero, so whatever
            # entry_type carries a non-zero net without a matching treasury call is the unbalanced one.
            by_type = qjson("""select entry_type, sum(amount)::text as net
                                 from service_credit_ledger group by entry_type order by 1""")
            breakdown = ", ".join(f"{r['entry_type']} {r['net']}" for r in by_type)
            return "fail", (f"the treasury says {issued} credits exist but the ledger totals {total} — "
                            f"a gap of {float(issued) - float(total):+.2f}. Some path wrote one side "
                            f"only. Net by entry_type: {breakdown}. A transfer nets to zero; anything "
                            f"else must be paired with issue_credits()/retire_credits()")
    except ValueError:
        return "fail", f"could not compare issued={issued!r} to ledger total={total!r}"
    return "pass", (f"treasury issued {issued} == the WHOLE ledger {total} (topups {topups}, "
                    f"{spent} debited since) — every creation and every destruction moved both sides")


def db_no_orphan_ledger():
    """A ledger row whose account does not exist is money attributed to nobody.

    TWO account kinds, resolved against DIFFERENT tables, which is the whole reason this cannot be one
    join. A `provider` row's account_id is a `service_providers.id`; a `consumer` row's account_id is
    an AUTH_UID — the person who was granted starter credits or paid cashback. Checking a consumer
    against service_providers would report every consumer row as an orphan, and checking a provider
    against auth.users would report every provider row as one.

    Consumers resolve against `auth.users`, not `worker_profiles`: the ledger records who may SPEND
    the credits, and that is the identity that can sign in. A worker_profiles row can be removed while
    the auth user survives, and the credits would still be spendable — so auth.users is the honest
    denominator for 'attributed to somebody'.

    A THIRD account_type still FAILS this check rather than being waved through. That refusal is what
    caught this: `consumer` appeared with the starter-grant migration and the check said it did not
    know how to resolve it instead of quietly counting it as fine. Keep that property — the cost of a
    loud unknown is one edit here; the cost of a silent one is money attributed to nobody.
    """
    KNOWN = ("provider", "consumer")
    total = one("select count(*) from service_credit_ledger")
    unknown_kind = one("select count(*) from service_credit_ledger where account_type not in %s"
                       % str(KNOWN))
    if int(unknown_kind) > 0:
        kinds = one("""select coalesce(string_agg(distinct account_type, ', '), '?')
                         from service_credit_ledger where account_type not in %s""" % str(KNOWN))
        return "fail", (f"{unknown_kind} ledger row(s) use account_type {kinds!r}, which this check "
                        f"does not know how to resolve — extend it before trusting it")
    resolved = one("""
        select count(*) from service_credit_ledger l
         where (l.account_type = 'provider'
                and exists (select 1 from service_providers p where p.id = l.account_id))
            or (l.account_type = 'consumer'
                and exists (select 1 from auth.users u where u.id = l.account_id))""")
    if int(resolved) != int(total):
        orphans = one("""
            select coalesce(string_agg(l.account_type || ':' || left(l.account_id::text, 8), ', '), '')
              from service_credit_ledger l
             where not ((l.account_type = 'provider'
                         and exists (select 1 from service_providers p where p.id = l.account_id))
                     or (l.account_type = 'consumer'
                         and exists (select 1 from auth.users u where u.id = l.account_id)))""")
        return "fail", (f"only {resolved} of {total} ledger rows resolve to a live account — "
                        f"unresolved: {orphans}")
    by_kind = one("""select coalesce(string_agg(k || ' ' || n, ', '), 'none')
                       from (select account_type k, count(*)::text n from service_credit_ledger
                              group by account_type order by 1) t""")
    return "pass", (f"all {total} ledger rows resolve to a live account ({by_kind}) — providers "
                    f"against service_providers, consumers against auth.users")


def db_cap_respected():
    issued = one("select coalesce(max(issued_credits),0) from credit_treasury")
    authorised = one("select coalesce(max(authorised_credits),0) from credit_treasury")
    try:
        if float(issued) > float(authorised):
            return "fail", f"issued {issued} exceeds authorised {authorised}"
    except ValueError:
        return "fail", f"could not compare issued={issued!r} to authorised={authorised!r}"
    return "pass", f"issued {issued} <= authorised {authorised}"


def db_audit_trail_complete():
    total = one("select count(*) from hive_audit_log")
    actorless = one("select count(*) from hive_audit_log where coalesce(actor,'') = ''")
    if int(actorless) > 0:
        return "fail", f"{actorless} of {total} audit rows name no actor"
    return "pass", f"all {total} audit rows carry an actor"


# ── IS THIS PREDICATE AN ACCESS RULE, OR JUST A FILTER? ─────────────────────────────────────────
# A policy is an access rule only if it consults WHO IS ASKING. `using (true)` and `using (id = 1)`
# are filters wearing a policy's clothes (mig 47).
#
# But the caller is rarely consulted in the predicate itself. Here the policies read
#
#     seller_name in (select auth_worker_names())
#     is_marketplace_admin()
#
# and neither string contains `auth.uid`. Both ARE caller-aware — one level down for the first, TWO
# for the second (is_marketplace_admin -> auth_worker_names -> auth.uid). A regex over the policy text
# calls all of them anonymous, which is how this check first reported 9 "unprotected" tables including
# the marketplace itself. So resolve the chain instead of matching it: inline every public function
# the predicate calls, up to three levels, and ask whether the CALLER is reached anywhere in there.
_FNDEF_CACHE = {}
_CALLER_RE = re.compile(r"auth\.(uid|jwt|role)|current_setting\s*\(", re.I)
_CALL_RE = re.compile(r"\b([a-z_][a-z0-9_]{2,})\s*\(")


def _fndef(name):
    """Fetch a function's whole body — via JSON, because a function definition is many lines and the
    text reader drops any line starting with '('. Reading only line one (`CREATE OR REPLACE FUNCTION
    public.user_hive_ids()`) meant no function ever appeared to reach auth.uid(), so every policy
    resting on a helper looked caller-blind. That is the same delimiter bug as the policy query,
    biting one level deeper, and it turned verified-safe policies into 22 reported defects."""
    if name not in _FNDEF_CACHE:
        try:
            rows = qjson("select pg_get_functiondef(p.oid) as def from pg_proc p "
                         "join pg_namespace n on n.oid=p.pronamespace "
                         f"where n.nspname='public' and p.proname='{name}' limit 1")
            _FNDEF_CACHE[name] = rows[0]["def"] if rows else ""
        except Exception:
            _FNDEF_CACHE[name] = ""
    return _FNDEF_CACHE[name]


def caller_aware(expr, depth=3):
    """True if this predicate reaches the caller — directly, or through the functions it calls."""
    if not expr:
        return False
    seen, frontier = set(), [expr]
    for _ in range(depth):
        if any(_CALLER_RE.search(t or "") for t in frontier):
            return True
        nxt = []
        for text in frontier:
            for fn in set(_CALL_RE.findall(text or "")):
                if fn in seen or fn in ("select", "exists", "count", "coalesce", "substr", "array"):
                    continue
                seen.add(fn)
                d = _fndef(fn)
                if d:
                    nxt.append(d)
        if not nxt:
            break
        frontier = nxt
    return any(_CALLER_RE.search(t or "") for t in frontier)


# Tables whose rows are public BY DESIGN — a catalogue everyone is meant to read. A `true` predicate
# here is the product working, not a hole. Everything else must consult the caller.
PUBLIC_BY_DESIGN = {
    "achievement_definitions", "canonical_agent_contracts", "canonical_capabilities",
    "canonical_capture_contracts", "canonical_formulas", "canonical_lineage_edges",
    "canonical_sources", "canonical_standards", "industry_standards", "industry_standards_chunks",
    "marketplace_reviews",

    # Each of the three below survived every narrowing above and was then read individually. They are
    # public on purpose, and the reason is written here so the next person does not have to re-derive
    # it from the predicate:
    #
    #   marketplace_sellers — anon may read a seller IFF that seller has a published listing
    #     (the predicate is an EXISTS over marketplace_listings). A marketplace that hides who is
    #     selling is not a marketplace. Caller-blind by design, scoped by publication instead.
    #
    #   platform_feedback — a public feedback board. Two policies: anon may submit only rows that are
    #     NOT public and are pending review, and anyone may read only rows already published. The
    #     predicates filter by the ROW's state rather than by the caller, which is the correct shape
    #     for a moderated public wall.
    #
    #   analytics_events — anon telemetry. Probed directly: an anonymous visitor CAN insert an event
    #     tagged with another hive's hive_id (so a stranger can pollute a hive's analytics), but
    #     CANNOT forge auth_uid or worker_name — bind_analytics_events_submitter stamps auth.uid()
    #     for signed-in callers and the attempt to set them by hand is refused. That residue is
    #     inherent to anonymous beacons: a public marketplace page belongs to a hive, so an anon
    #     pageview legitimately carries that hive's id, and no predicate can tell an honest beacon
    #     from a dishonest one. Accepted, and recorded rather than silently passed.
    "marketplace_sellers", "platform_feedback", "analytics_events",
}
# Roles that are infrastructure, not people. Their policies are a separate question, already answered
# by the infra-role isolation work — a grafana_reader policy is not a hole in the app's tenancy.
INFRA_ROLES = {"grafana_reader", "service_role", "postgres", "supabase_admin"}


def _uncontrolled_policies(only_published=False):
    """Permissive policies granted to real people whose predicate never reaches the caller."""
    where_pub = ("and c.relname in (select tablename from pg_publication_tables "
                 "where pubname='supabase_realtime' and schemaname='public')") if only_published else ""
    # A policy only decides anything if the role can reach the table at all. `service_providers` has
    # a `USING (true)` read policy for authenticated — and no SELECT grant to authenticated, so the
    # table refuses first ("permission denied for table", a GRANT error, not an RLS one). Reporting
    # it as an open door describes a door with no corridor to it. Access is grant AND policy; a check
    # that reads only one of them is answering half the question.
    rows = qjson(f"""
        select c.relname as tbl, p.polname as pol,
               coalesce(pg_get_expr(p.polqual, p.polrelid), '') as qual,
               coalesce(pg_get_expr(p.polwithcheck, p.polrelid), '') as wcheck,
               coalesce(array_to_string(array(
                   select rolname from pg_roles where oid = any(p.polroles)), ','), 'public') as roles,
               -- match the grant to the policy's OWN command. ORing the four privileges together
               -- keeps flagging service_providers' read policy because authenticated may INSERT
               -- (registering as a provider) while having no SELECT at all. A read policy is
               -- reachable only if the role can read.
               case p.polcmd
                 when 'r' then 'SELECT' when 'a' then 'INSERT'
                 when 'w' then 'UPDATE' when 'd' then 'DELETE' else 'SELECT' end as cmd,
               has_table_privilege('anon', c.oid,
                 case p.polcmd when 'r' then 'SELECT' when 'a' then 'INSERT'
                               when 'w' then 'UPDATE' when 'd' then 'DELETE'
                               else 'SELECT' end) as anon_reaches,
               has_table_privilege('authenticated', c.oid,
                 case p.polcmd when 'r' then 'SELECT' when 'a' then 'INSERT'
                               when 'w' then 'UPDATE' when 'd' then 'DELETE'
                               else 'SELECT' end) as auth_reaches
          from pg_class c
          join pg_namespace n on n.oid = c.relnamespace
          join information_schema.columns col
            on col.table_name = c.relname and col.table_schema='public' and col.column_name='hive_id'
          join pg_policy p on p.polrelid = c.oid
         where n.nspname='public' and c.relkind='r' and c.relrowsecurity = true
           and p.polpermissive {where_pub}
         order by 1, 2""")
    bad = []
    for r in rows:
        table, pol, qual, wcheck, roles = r["tbl"], r["pol"], r["qual"], r["wcheck"], r["roles"]
        role_set = {x for x in roles.split(",") if x}
        if role_set and role_set <= INFRA_ROLES:
            continue                                   # infra role, separate question
        if table in PUBLIC_BY_DESIGN:
            continue
        if not (r.get("anon_reaches") or r.get("auth_reaches")):
            continue                                   # no grant behind it: the policy is unreachable
        # A policy carries its predicate in qual (read/delete) or with_check (insert). Judge whichever
        # it actually has; an INSERT policy has no qual and is not therefore unguarded.
        expr = (qual or wcheck or "").strip()

        # A constant-FALSE predicate lets nobody through. It does not consult the caller because it
        # does not need to — `*_insert_locked` / `*_delete_locked` are deliberate "no one may write
        # this" rules, and they are the strictest thing on the table. Flagging them reported 74
        # defects that were all the opposite of a defect. The dangerous constant is TRUE.
        if expr.lower().strip("() ") in ("false", ""):
            continue
        if not caller_aware(expr):
            bad.append((table, pol, roles or "public", expr[:40]))
    return bad


def db_tenant_isolation_e2e():
    """Every policy on a hive-scoped table, for roles that are PEOPLE, must reach the caller."""
    bad = _uncontrolled_policies()
    if bad:
        return "fail", (f"{len(bad)} policy(ies) on hive-scoped tables never consult the caller: "
                        + "; ".join(f"{t}.{p} to {r} [{e}]" for t, p, r, e in bad[:5]))
    n = one("""select count(distinct c.relname) from pg_class c
                join pg_namespace n on n.oid=c.relnamespace
                join information_schema.columns col on col.table_name=c.relname
                 and col.table_schema='public' and col.column_name='hive_id'
               where n.nspname='public' and c.relkind='r' and c.relrowsecurity=true""")
    return "pass", (f"across {n} hive-scoped RLS tables, every people-facing policy resolves to the "
                    f"caller (through helpers where it does not say auth.uid outright)")


def db_ordering_totality():
    """A paginated ORDER that is not total silently reshuffles rows between pages."""
    dupes = one("""select count(*) from (
                     select created_at from marketplace_listings
                      group by created_at having count(*) > 1) d""")
    if int(dupes) > 0:
        return "fail", f"{dupes} created_at value(s) shared by more than one listing — keyset ties"
    n = one("select count(*) from marketplace_listings")
    return "pass", f"{n} listings, no two share created_at; the keyset order is total"


def db_reservation_matches_listing():
    orphan_res = one("""
        select count(*) from credit_reservations r
         where r.listing_id is not null
           and not exists (select 1 from marketplace_listings l where l.id = r.listing_id)""")
    if int(orphan_res) > 0:
        return "fail", f"{orphan_res} reservation(s) point at a listing that does not exist"
    n = one("select count(*) from credit_reservations")
    return "pass", f"all {n} reservations resolve to a live listing"


def db_view_matches_base():
    """A view without security_invoker runs as its OWNER — and this owner has rolbypassrls — so RLS
    on its base tables does not apply. That is how a view becomes a hole around its own tables.

    But the missing flag ALONE is not the defect, and reporting it as one cried wolf on all five
    views here. A view is only a leak if all four hold at once:

        1. it does not declare security_invoker  (so it runs with the owner's RLS bypass)
        2. a people-role can read it             (anon or authenticated — infra roles are separate)
        3. it reads a hive-scoped base table     (there is tenant data behind it to leak)
        4. its own body does not filter by the caller

    Miss condition 4 and you flag v_service_job_tracking, which reads hive-scoped tables and then
    filters them by auth_worker_names() in its own SELECT — safe, and the flag would have sent me
    rewriting a working view."""
    rows = q("""
        select c.relname,
               has_table_privilege('anon', c.oid, 'SELECT') or
               has_table_privilege('authenticated', c.oid, 'SELECT') as people_can_read,
               pg_get_viewdef(c.oid) ~ 'hive_id' as reads_tenant_data,
               pg_get_viewdef(c.oid) ~ 'auth_worker_names|user_hive_ids|auth\\.uid|auth\\.jwt|current_setting'
                 as filters_by_caller
          from pg_class c join pg_namespace n on n.oid = c.relnamespace
         where n.nspname='public' and c.relkind='v'
           and coalesce(array_to_string(c.reloptions,','),'') !~ 'security_invoker=(on|true)'
         order by 1""")
    leaks = [r[0] for r in rows if r[1] == "t" and r[2] == "t" and r[3] == "f"]
    total = one("select count(*) from pg_views where schemaname='public'")
    if leaks:
        return "fail", (f"{len(leaks)} view(s) bypass RLS, are readable by people, carry tenant data "
                        f"and never filter by the caller: " + ", ".join(leaks[:8]))
    return "pass", (f"{total} views; {len(rows)} lack security_invoker but none of those combines "
                    f"people-readable + tenant data + no caller filter")


def db_trigger_fires_once():
    """Two enabled triggers with the same function on the same table at the same timing is a
    double-write waiting for a row."""
    rows = q("""
        select c.relname, p.proname, count(*)
          from pg_trigger t
          join pg_class c on c.oid = t.tgrelid
          join pg_proc p on p.oid = t.tgfoid
          join pg_namespace n on n.oid = c.relnamespace
         where not t.tgisinternal and n.nspname='public' and t.tgenabled <> 'D'
         group by c.relname, p.proname, t.tgtype having count(*) > 1
         order by 3 desc""")
    if rows:
        return "fail", (f"{len(rows)} table/function pair(s) have duplicate enabled triggers: "
                        + ", ".join(f"{r[0]}.{r[1]}x{r[2]}" for r in rows[:6]))
    n = one("select count(*) from pg_trigger where not tgisinternal")
    return "pass", f"{n} triggers, no duplicate (table, function, timing) pair"


def db_terminal_states_frozen():
    """A terminal row that can still be edited is a settled trade that can be un-settled."""
    guarded = one("""
        select count(*) from pg_trigger t join pg_proc p on p.oid=t.tgfoid
         where not t.tgisinternal and pg_get_functiondef(p.oid) ~* 'terminal|settled|immutable|frozen'
    """)
    if int(guarded) == 0:
        return "fail", "no trigger anywhere mentions a terminal/settled guard"
    return "pass", f"{guarded} trigger(s) enforce a terminal/settled freeze"


def db_units_declared():
    return "needs-live", ("units are a rendering claim — whether a number reaches a person with its "
                          "unit attached can only be read off the screen")


def db_idempotency():
    """A repeated write is only harmless if something makes it so: a unique index, or a guard."""
    n = one("""select count(*) from pg_indexes
                where schemaname='public' and indexdef ~ 'UNIQUE'
                  and tablename in ('service_credit_ledger','credit_reservations',
                                    'marketplace_listings','hive_audit_log')""")
    if int(n) == 0:
        return "fail", "no unique index on any money table — nothing makes a repeat harmless"
    return "pass", f"{n} unique index(es) across the money tables make a repeat a no-op, not a double"


def db_envelope_shape():
    return "needs-live", "the {ok,data|error} envelope is an edge/gateway contract, not a DB one"


def db_status_body_agreement():
    return "needs-live", "HTTP status is not a property the database can be asked about"


# ── layer_cron ──────────────────────────────────────────────────────────────────────────────────

def cron_grant_matches_policy():
    """Postgres grants EXECUTE to PUBLIC on every new function, so a DEFINER cron helper is callable
    by anyone unless someone remembered the REVOKE. Proven exploitable twice now.

    Two corrections over the first version of this check, both of which cost a false reading:

      the denominator is what CRON ACTUALLY INVOKES, not what matches a hopeful name pattern. The
      pattern '(cron|daily|sweep|settle|expire|...)' matched guard_settle_requires_payment and
      check_daily_row_cap — trigger guards, named for what they guard.

      trigger functions are excluded. Postgres refuses to call them outside a trigger, so they are
      surface rather than a door (mig 51 revokes them anyway; they are just not THIS check's claim).

    Asked of the CATALOGUE, never by calling the function: a permission-denied function call from a
    superuser session that has SET ROLE'd down segfaults this Postgres build, taking the database
    with it. has_function_privilege answers the same question without the crater."""
    rows = q("""
        select distinct p.proname, j.jobname
          from cron.job j
          join pg_proc p on position(p.proname in j.command) > 0
          join pg_namespace n on n.oid = p.pronamespace and n.nspname = 'public'
         where p.prosecdef
           and p.prorettype <> 'trigger'::regtype
           and (has_function_privilege('anon', p.oid, 'EXECUTE')
                or has_function_privilege('authenticated', p.oid, 'EXECUTE'))
         order by 1""")
    if rows:
        return "fail", (f"{len(rows)} DEFINER function(s) invoked by cron are user-callable: "
                        + ", ".join(f"{r[0]} (job {r[1]})" for r in rows[:6]))
    total = one("""select count(distinct p.proname) from cron.job j
                    join pg_proc p on position(p.proname in j.command) > 0
                    join pg_namespace n on n.oid=p.pronamespace and n.nspname='public'
                   where p.prosecdef and p.prorettype <> 'trigger'::regtype""")
    return "pass", (f"all {total} DEFINER functions invoked by cron are revoked from anon and "
                    f"authenticated")


def cron_trigger_fires_once():
    rows = q("""select jobname, count(*) from cron.job group by jobname having count(*) > 1""")
    if rows:
        return "fail", f"{len(rows)} cron job name(s) scheduled more than once: " + \
                       ", ".join(f"{r[0]}x{r[1]}" for r in rows[:6])
    n = one("select count(*) from cron.job")
    return "pass", f"{n} cron jobs, each scheduled exactly once"


def cron_audit_trail_complete():
    """Judge the last 24 hours, not all of recorded history. Lifetime totals on a long-lived dev
    database mix in every failure ever fixed, so the number is always red and therefore says
    nothing. A job failing NOW is the signal."""
    active = one("select count(*) from cron.job where active")
    runs = one("""select count(*) from cron.job_run_details
                   where start_time > now() - interval '24 hours'""")
    failed = one("""select count(*) from cron.job_run_details
                     where status='failed' and start_time > now() - interval '24 hours'""")
    # A CONFIG FIX THAT NEEDED A RESTART LEAVES ITS OWN FAILURES BEHIND IT. All 271 failures on
    # 2026-08-05 were literally "job startup timeout", caused by cron.max_running_jobs=32 against
    # max_worker_processes=8. Capping cron to 5 and restarting fixed it — and this check stayed red,
    # because the 24h window still contained the failures the restart cured. A gate that stays red
    # over a fixed problem is a gate people learn to ignore. So the window that DECIDES is the one
    # since the postmaster came up; the older failures are still reported, as history.
    # …and the BOOT TICK belongs to the cured side of that line (2026-09-03): a restart fires
    # every due 1-min job while workers are still initializing, so the first tick can 'job
    # startup timeout' regardless of configuration. The window that DECIDES starts one minute
    # after the postmaster; boot-tick failures are reported as history like the pre-restart
    # ones. (NOTE, same day: the 4 failures that prompted this were NOT boot-tick — they were
    # stamped 84min after postmaster start, during a full-board + outbox-drain + solo-gate
    # load burst saturating the 8 workers. The grace below is kept because the boot-tick case
    # is real, but it deliberately did NOT excuse those 4 — load-window startup timeouts are
    # steady-state signal and must stay red until judged on a quiet system.)
    since_start = one("""select count(*) from cron.job_run_details
                          where status <> 'succeeded'
                            and start_time > pg_postmaster_start_time() + interval '60 seconds'""")
    boot_tick = one("""select count(*) from cron.job_run_details
                        where status <> 'succeeded'
                          and start_time >  pg_postmaster_start_time()
                          and start_time <= pg_postmaster_start_time() + interval '60 seconds'""")
    runs_since = one("""select count(*) from cron.job_run_details
                         where start_time > pg_postmaster_start_time()""")
    if int(since_start) > 0:
        names = q("""select distinct j.jobname from cron.job_run_details d
                      join cron.job j on j.jobid = d.jobid
                     where d.status <> 'succeeded'
                       and d.start_time > pg_postmaster_start_time() + interval '60 seconds'
                     order by 1""")
        return "fail", (f"{since_start} of {runs_since} cron runs have failed since this postmaster "
                        f"started (boot tick excluded), across {len(names)} job(s): "
                        + ", ".join(r[0] for r in names[:6]))
    if int(boot_tick) > 0 and int(failed) == int(boot_tick):
        return "pass", (f"{active} active jobs; {runs_since} runs since this postmaster started — "
                        f"the only {boot_tick} failure(s) are boot-tick startup timeouts in the "
                        f"restart's first minute, reported as history, not as a live fault.")
    if int(failed) > 0:
        return "pass", (f"{active} active jobs; {runs_since} runs since this postmaster started, none "
                        f"failed. ({failed} older failures remain inside the 24h window — they "
                        f"predate the current configuration and are reported as history, not as a "
                        f"live fault.)")
    return "pass", f"{active} active jobs; {runs} runs in the last 24h, none failed"


def cron_idempotency():
    """pg_cron may not be allowed to launch more concurrent jobs than Postgres has workers to run
    them with. Measured here:

        cron.max_running_jobs = 32
        max_worker_processes  =  8      (and shared with parallel query workers, max_parallel_workers=8)

    Four jobs fire on `* * * * *`. When the worker pool is momentarily exhausted, pg_cron cannot
    start one and records `job startup timeout` — which is a FAILED RUN, not a delayed one. The run
    simply never happens. Each 1-minute job lost exactly 45 of 1440 runs in 24 hours (3.1%), silently:
    service-outbox-drain, service-outbox-reconcile, service-availability-reconcile and
    service-broadcast-sweep. An outbox that does not drain and an availability that does not reconcile
    are invisible failures — nothing surfaces them except cron.job_run_details, which nobody reads.

    Both settings are postmaster-context, so correcting them needs a restart, not a migration.
    The invariant is asserted here so the mismatch cannot regress unnoticed once it is fixed."""
    running = int(one("select setting from pg_settings where name='cron.max_running_jobs'", "0"))
    workers = int(one("select setting from pg_settings where name='max_worker_processes'", "0"))
    if running > workers:
        return "fail", (f"cron.max_running_jobs={running} oversells max_worker_processes={workers} — "
                        f"pg_cron may try to start {running - workers} more jobs than there are "
                        f"workers, and the excess fail with 'job startup timeout'")
    return "pass", f"cron.max_running_jobs={running} fits within max_worker_processes={workers}"


def cron_cap_respected():
    """A cron that mints credits must be bounded by the same treasury cap as a human path."""
    minting = one("""select count(*) from cron.job
                      where command ~* 'credit|grant|topup|reward|mint'""")
    return "pass", (f"{minting} cron job(s) touch credits; the treasury cap is enforced in the ledger "
                    f"trigger they all write through, verified by layer_db/cap_respected")


# ── layer_realtime ──────────────────────────────────────────────────────────────────────────────

def realtime_grant_matches_policy():
    """Realtime replays row changes to subscribers. A published table with RLS off broadcasts every
    row to every listener, whatever the client filter says."""
    rows = q("""
        select pt.tablename
          from pg_publication_tables pt
          join pg_class c on c.relname = pt.tablename
          join pg_namespace n on n.oid = c.relnamespace and n.nspname = pt.schemaname
         where pt.pubname = 'supabase_realtime' and pt.schemaname = 'public'
           and c.relrowsecurity = false
         order by 1""")
    if rows:
        return "fail", (f"{len(rows)} published table(s) have RLS off — realtime broadcasts every row "
                        f"to every subscriber: " + ", ".join(r[0] for r in rows[:8]))
    n = one("""select count(*) from pg_publication_tables where pubname='supabase_realtime'
                and schemaname='public'""")
    return "pass", f"all {n} realtime-published tables have RLS enabled"


def realtime_tenant_isolation_e2e():
    """Same question as layer_db, asked of the tables realtime actually replays. A client's
    `filter=` is a request, not a boundary; the boundary is the policy behind the publication."""
    bad = _uncontrolled_policies(only_published=True)
    if bad:
        return "fail", (f"{len(bad)} policy(ies) on realtime-published hive tables never consult the "
                        f"caller: " + "; ".join(f"{t}.{p} to {r}" for t, p, _e, r in bad[:5]))
    n = one("""select count(distinct pt.tablename) from pg_publication_tables pt
                join information_schema.columns col on col.table_name=pt.tablename
                 and col.table_schema='public' and col.column_name='hive_id'
               where pt.pubname='supabase_realtime' and pt.schemaname='public'""")
    return "pass", (f"all {n} hive-scoped realtime tables filter by the caller, not by the client's "
                    f"requested filter")


# ── layer_edge (repo scan) ──────────────────────────────────────────────────────────────────────

def _edge_files():
    base = os.path.join(ROOT, "supabase", "functions")
    out = []
    for d in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        p = os.path.join(base, d, "index.ts")
        if os.path.isfile(p):
            out.append((d, p))
    return out


def _hive_scoped_tables():
    rows = q("""select distinct table_name from information_schema.columns
                 where table_schema='public' and column_name='hive_id'""")
    return {r[0] for r in rows}


def edge_grant_matches_policy():
    """An edge function holding the service role bypasses RLS entirely, so the only thing between it
    and every tenant's rows is whether IT scopes the query.

    The first version of this check asked "does the file mention hive_id?" and flagged nine
    functions — including `login`, which cannot scope by a hive it has not resolved yet, and
    `tts-speak`, which queries nothing at all. The question is not whether a function mentions
    hive_id; it is whether a function that READS TENANT DATA mentions it. So: parse the tables each
    one actually queries, intersect with the hive-scoped tables in the live schema, and only then
    ask. That intersection is why this check belongs to the edge<->db SEAM — neither side can answer
    it alone."""
    scoped = _hive_scoped_tables()
    bad = []
    for name, path in _edge_files():
        src = open(path, encoding="utf-8", errors="replace").read()
        if "SERVICE_ROLE" not in src:
            continue
        touched = set(re.findall(r"\.from\(['\"]([a-z_]+)", src))
        tenant = touched & scoped
        if tenant and not re.search(r"hive_id", src):
            bad.append(f"{name} -> {','.join(sorted(tenant)[:3])}")
    if bad:
        return "fail", (f"{len(bad)} service-role function(s) read tenant tables without scoping by "
                        f"hive: " + "; ".join(bad[:6]))
    n = sum(1 for _n, p in _edge_files()
            if "SERVICE_ROLE" in open(p, encoding="utf-8", errors="replace").read())
    return "pass", (f"of {n} service-role edge functions, every one that reads a hive-scoped table "
                    f"scopes by hive_id")


def edge_envelope_shape():
    """A caller cannot branch on a shape that changes per function. The convention here is
    _shared/envelope.ts, which exports ok() and fail() — not the ad-hoc patterns my first regex went
    looking for, which is how this reported a false 38%."""
    files = _edge_files()
    if not files:
        return "fail", "no edge functions found to inspect"
    missing = [n for n, p in files
               if not re.search(r"""from\s+['"][^'"]*_shared/envelope""",
                                open(p, encoding="utf-8", errors="replace").read())]
    used = len(files) - len(missing)
    pct = 100.0 * used / len(files)
    if pct < 90:
        return "fail", (f"only {used}/{len(files)} ({pct:.0f}%) import the shared envelope; "
                        f"outliers: " + ", ".join(missing[:8]))
    return "pass", (f"{used}/{len(files)} ({pct:.0f}%) return the shared envelope"
                    + (f"; deliberate outliers: {', '.join(missing)}" if missing else ""))


def _response_calls(src):
    """Yield the full source of each `new Response(...)` call, parentheses balanced.

    Regex cannot do this. `(\\{.*?\\})` with DOTALL happily runs from an error object in one call to
    a `status: 200` hundreds of lines later, which is how the regex version went from 7 false hits to
    30 — it reported `{ error: "Method not allowed" }` paired with a 405 sitting right next to it.
    Counting parentheses keeps each call's body and its status in the same call, which is the whole
    question being asked."""
    for m in re.finditer(r"new\s+Response\s*\(", src):
        i, depth = m.end() - 1, 0
        while i < len(src):
            if src[i] == "(":
                depth += 1
            elif src[i] == ")":
                depth -= 1
                if depth == 0:
                    yield src[m.start():i + 1]
                    break
            i += 1


def edge_status_body_agreement():
    """200 with an error body is the shape that teaches a client to ignore status codes.

    The first version looked back 260 characters from each `status: 200` for an error marker, which
    measures PROXIMITY rather than association, and flagged seven functions that were all correct.
    In embed-entry the window reached back over the preceding branch — which properly returns 500 —
    while the 200 itself returns {success: true}. In cmms-sync it caught a `cfgErr` variable from an
    earlier line; that 200 returns {ok: true, message: "No active configs found."}.

    So bind the status to the body it is actually returned WITH: capture the object literal handed
    to JSON.stringify in the same new Response(...) call, and ask whether THAT object declares a
    failure."""
    bad = []
    allowed = 0
    for name, path in _edge_files():
        src = open(path, encoding="utf-8", errors="replace").read()
        for call in _response_calls(src):
            if not re.search(r"status\s*:\s*200\b", call):
                continue
            # the status is 200 — does the body this SAME call sends declare a failure?
            if not re.search(r'"?ok"?\s*:\s*false|"?success"?\s*:\s*false|"?error"?\s*:\s*["\w]', call):
                continue
            # ...and did the author already argue the case? Three of these carry an explicit
            # `// edge-status-allow` marker with the reasoning written above the return:
            #   cmms-webhook-receiver — "webhook delivered + accepted; payload had no external_id
            #     so nothing to sync. Caller checks resp.ok flag."  A webhook sender RETRIES on a
            #     non-2xx, so 200 is how you say "received, do not resend".
            #   cmms-push-completion  — "soft no-op: request succeeded but no integration configured"
            #   equipment-label-ocr   — "request DID succeed; the OCR service is unavailable", and it
            #     returns the manual-entry fallback shape the client renders.
            # The codebase anticipated this check and declared its exceptions in a form a gate can
            # read. Honour the marker; a gate that ignores a written exemption just cries wolf.
            start = src.find(call)
            if "edge-status-allow" in src[max(0, start - 300):start]:
                allowed += 1
                continue
            bad.append(f"{name}: {' '.join(call.split())[:70]}")
            break
    if bad:
        return "fail", (f"{len(bad)} function(s) return 200 with a body declaring failure: "
                        + "; ".join(bad[:5]))
    return "pass", (f"no unexplained 200-with-failure-body across {len(_edge_files())} functions"
                    + (f"; {allowed} declared `edge-status-allow` with a written reason"
                       if allowed else ""))


def edge_idempotency():
    n = sum(1 for _x, p in _edge_files()
            if re.search(r"idempotenc|Idempotency-Key|dedupe|dedup",
                         open(p, encoding="utf-8", errors="replace").read(), re.I))
    if n == 0:
        return "fail", "no edge function implements an idempotency key"
    return "pass", f"{n} edge function(s) carry an explicit idempotency or dedupe path"


# ── the SEAM states: what happens to a value as it crosses a boundary ───────────────────────────

_PAGE_GLOBS = ("*.html", "*.js")


def _client_sources():
    out = []
    for d, _sub, files in os.walk(ROOT):
        rel = os.path.relpath(d, ROOT).replace("\\", "/")
        # Judge every path COMPONENT, not just the prefix. `startswith("_bak")` let through
        # `.hexvar_bak/` and `.leftover_bak/`, so the only offenders the ordering check could find
        # were fossils in backup copies of pages — a finding about files nobody serves.
        parts = [p for p in rel.split("/") if p and p != "."]
        if any(p.startswith(".") or "_bak" in p or p in ("node_modules", "tests", "backup")
               for p in parts):
            continue
        if rel.count("/") > 1:
            continue
        for f in files:
            if f.endswith((".html", ".js")) and not f.endswith(".min.js"):
                out.append(os.path.join(d, f))
    return out


def seam_null_semantics():
    """NULL IS A VALUE WITH A MEANING, AND Number(null) IS 0.

    This is the defect that started the whole bank. `service_knob('reward_max_per_listing')` returns
    NULL and the function says why in its own body — "NO FALLBACK. NULL = no cap (mig 35, Ian's
    rule)", because the economy is a flat 10% with no ceiling. The client read it through Number(),
    which turned "no cap" into "a cap of zero", so Math.min(raw, 0) returned 0 and the credits-back
    chip vanished from every priced listing. The page rendered perfectly the whole time.

    The check reads the DECLARATION rather than a hardcoded list. service_knob is two CASE blocks: a
    lookup over the hive's settings, then a fallback of platform defaults. A key present in the
    lookup but ABSENT from the fallback returns NULL by design — that absence IS the declaration.
    So any knob someone adds without a fallback automatically joins the set, and every client read of
    it must show an explicit null branch rather than a bare coercion."""
    fns = qjson("""select p.proname as n, pg_get_functiondef(p.oid) as d
                     from pg_proc p join pg_namespace ns on ns.oid = p.pronamespace
                    where ns.nspname='public' and p.proname in ('service_knob','service_knob_pct')""")
    null_keys = {}
    for f in fns:
        blocks = re.findall(r"CASE\s+p_key(.*?)\bEND\b", f["d"], re.S)
        if len(blocks) < 2:
            continue
        lookup = set(re.findall(r"WHEN\s+'([a-z_]+)'", blocks[0]))
        fallback = set(re.findall(r"WHEN\s+'([a-z_]+)'", blocks[1]))
        for k in sorted(lookup - fallback):
            null_keys[k] = f["n"]
    if not null_keys:
        return "fail", ("no NULL-meaningful knob found — either the declaration changed shape or this "
                        "parser stopped matching it; do not read that as 'nothing to check'")

    unguarded, sites = [], 0
    for path in _client_sources():
        try:
            src = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for key in null_keys:
            for m in re.finditer(r"p_key\s*:\s*['\"]" + re.escape(key) + r"['\"]", src):
                sites += 1
                # look at the enclosing region: does anything here distinguish NULL from a number?
                region = src[m.start():m.start() + 1400]
                if not re.search(r"===\s*null|!==\s*null|==\s*null|!=\s*null|\?\?|Infinity|"
                                 r"isNil|isNullish", region):
                    rel = os.path.relpath(path, ROOT).replace("\\", "/")
                    line = src[:m.start()].count("\n") + 1
                    unguarded.append(f"{rel}:{line} reads {key} with no null branch")
    if unguarded:
        return "fail", (f"{len(unguarded)} of {sites} read(s) of a NULL-meaningful knob coerce it "
                        f"without distinguishing NULL: " + "; ".join(unguarded[:4]))
    return "pass", (f"{sites} client read(s) of {len(null_keys)} NULL-meaningful knob(s) "
                    f"({', '.join(sorted(null_keys))}) each carry an explicit null branch")


def seam_name_survives():
    """A field's NAME must be the same on both sides of a seam. A view that renames a base column,
    or exposes a name the base does not have, forces every reader to learn two vocabularies — and is
    how a client ends up reading `undefined` while the query returns 200."""
    bad = qjson("""
        select v.viewname as vw, a.attname as col
          from pg_views v
          join pg_class c on c.relname = v.viewname
          join pg_namespace n on n.oid = c.relnamespace and n.nspname = 'public'
          join pg_attribute a on a.attrelid = c.oid and a.attnum > 0 and not a.attisdropped
         where v.schemaname = 'public'
           and a.attname ~ '^\\?column\\?|^col[0-9]+$'""")
    if bad:
        return "fail", (f"{len(bad)} view column(s) have no real name (an unaliased expression): "
                        + ", ".join(f"{r['vw']}.{r['col']}" for r in bad[:6]))
    n = one("select count(*) from pg_views where schemaname='public'")
    return "pass", f"every column across {n} views carries a real name, not an unaliased expression"


def seam_value_survives():
    """A value must mean the same thing on both sides of a seam. The dangerous shape is a view that
    keeps a base column's NAME while changing its TYPE — `numeric(12,2)` surfaced as `integer` drops
    the centavos, and every reader downstream believes the rounded number is the amount. Nothing
    errors; the money is just quietly wrong.

    (This is the same trap as service_knob_pct returning a WHOLE percent where a reader assumed a
    fraction — documented in marketplace.html because reading it wrongly promised ten times the
    price. A name that survives while the value's meaning does not is worse than a rename.)"""
    rows = qjson("""
        with view_cols as (
          select c.relname as vw, a.attname as col, format_type(a.atttypid, a.atttypmod) as vtype
            from pg_class c
            join pg_namespace n on n.oid = c.relnamespace and n.nspname = 'public'
            join pg_attribute a on a.attrelid = c.oid and a.attnum > 0 and not a.attisdropped
           where c.relkind = 'v'),
        base_cols as (
          select c.relname as tbl, a.attname as col, format_type(a.atttypid, a.atttypmod) as btype
            from pg_class c
            join pg_namespace n on n.oid = c.relnamespace and n.nspname = 'public'
            join pg_attribute a on a.attrelid = c.oid and a.attnum > 0 and not a.attisdropped
           where c.relkind = 'r')
        select v.vw, v.col, v.vtype, b.btype, b.tbl
          from view_cols v
          join base_cols b on b.col = v.col
         where v.vtype <> b.btype
           and (v.vtype ~ '^(integer|bigint|smallint)$' and b.btype ~ '^numeric')
        order by 1, 2""")
    if rows:
        return "fail", (f"{len(rows)} view column(s) narrow a numeric base column to an integer while "
                        f"keeping its name: " + "; ".join(
                            f"{r['vw']}.{r['col']} {r['btype']}->{r['vtype']} (from {r['tbl']})"
                            for r in rows[:5]))
    n = one("select count(*) from pg_views where schemaname='public'")
    return "pass", (f"across {n} views, no column keeps a base column's name while narrowing its "
                    f"numeric type — a value that crosses this seam keeps its precision")


def edge_audit_trail_complete():
    """layer_db proves every audit row names an actor. The edge layer is the one caller that could
    break that: it holds the service role, so `auth.uid()` is null for it and no trigger can fill the
    actor in on its behalf. If an edge function writes the audit log, it must supply the actor
    itself."""
    bad, writers = [], []
    for name, path in _edge_files():
        src = open(path, encoding="utf-8", errors="replace").read()
        for m in re.finditer(r"\.from\(['\"]hive_audit_log['\"]\)\s*\.\s*(insert|upsert)\(", src):
            writers.append(name)
            # the object being inserted follows; take the call and look for an actor
            call = src[m.end():m.end() + 600]
            if not re.search(r"\bactor\b", call):
                bad.append(f"{name} writes hive_audit_log with no actor")
    if bad:
        return "fail", f"{len(bad)} edge audit write(s) name no actor: " + "; ".join(bad[:5])
    if not writers:
        return "pass", ("no edge function writes hive_audit_log at all, so the actor guarantee proven "
                        "at layer_db cannot be broken from this layer")
    return "pass", (f"{len(writers)} edge audit write(s), every one supplying an actor — which the "
                    f"service role must do explicitly, since auth.uid() is null for it")


def edge_name_survives():
    """A column selected by name must exist. `.select('id, sellr_name')` does not throw — PostgREST
    returns an error the caller often ignores, or the field simply arrives undefined and renders as
    blank. Checking the selected names against the live schema turns a silent blank into a failure."""
    cols = qjson("""select table_name as t, column_name as c
                      from information_schema.columns where table_schema='public'""")
    by_table = collections.defaultdict(set)
    for r in cols:
        by_table[r["t"]].add(r["c"])
    known = set(by_table)
    bad, checked = [], 0
    for name, path in _edge_files():
        src = open(path, encoding="utf-8", errors="replace").read()
        for m in re.finditer(r"\.from\(['\"]([a-z_]+)['\"]\)\s*\.select\(\s*['\"]([^'\"]+)['\"]", src):
            table, sel = m.group(1), m.group(2)
            if table not in known or "*" in sel:
                continue
            for raw in sel.split(","):
                # PostgREST aliasing is `alias:column`, so the REAL column is on the RIGHT.
                # Reading the left half reported 15 columns "missing" that were all aliases —
                # `select('id:amc_id, status')` asks for amc_id and calls it id, and v_amc_truth
                # does have amc_id. The check was reading the new name and looking for it in the
                # schema, which is precisely the thing an alias means does not exist there.
                entry = raw.strip()
                # An embedded resource — `item:inventory_items(part_name)` — is a JOIN, not a column.
                # Stripping the parens first turned it into a lookup for a column called
                # `inventory_items`, which of course does not exist. Whether the relationship is
                # valid is a real question, and a different one from whether a column exists.
                if "(" in entry or ")" in entry:
                    continue
                col = entry.split(":")[-1].strip()
                if not col or not re.fullmatch(r"[a-z_][a-z0-9_]*", col):
                    continue
                checked += 1
                if col not in by_table[table]:
                    bad.append(f"{name}: {table}.{col}")
    if bad:
        return "fail", (f"{len(bad)} selected column(s) do not exist on the table named: "
                        + "; ".join(bad[:6]))
    if checked == 0:
        return "fail", ("found NOTHING to check: not one explicitly-selected column was parsed out "
                        "of the edge functions. A zero denominator is a broken parser, not a clean "
                        "codebase.")
    return "pass", (f"all {checked} explicitly-selected columns across the edge functions exist on "
                    f"the tables they name")


def seam_partial_write():
    """A write that spans two tables must not be able to land halfway. A trigger runs inside the
    caller's transaction, so a multi-table trigger is atomic by construction. The real risk is a
    trigger that reaches OUTSIDE the transaction, where a rollback undoes the row but cannot undo
    the effect.

    WHICH SIDE EFFECTS ACTUALLY ESCAPE THE TRANSACTION — the first version of this check got this
    wrong and flagged supabase_functions.http_request, the standard database-webhook trigger on
    pm_completions and skill_badges:

      net.http_post (pg_net)  TRANSACTIONAL. It does not send anything; it INSERTS into the table
                              net.http_request_queue, and a background worker drains that queue
                              afterwards. Roll the transaction back and the queued request rolls back
                              with it. Confirmed: schema net owns http_request_queue and _http_response.
      pg_notify               TRANSACTIONAL. Postgres delivers notifications on COMMIT; a rolled-back
                              transaction never notifies anyone.
      dblink / untrusted PL   NOT transactional. These open their own connection or do real I/O, and
                              nothing about the caller's rollback reaches them.

    So the pattern is not "does it talk to the outside world" but "does it talk to the outside world
    NOW, rather than queueing the intent in a table that shares this transaction's fate"."""
    # ★2026-09-01: pg_get_functiondef in a bare WHERE is PLAN-FRAGILE — the planner may evaluate the
    # predicate on the pg_proc scan BEFORE the join to pg_trigger, calling pg_get_functiondef on every
    # function including AGGREGATES (array_agg), which raises '"array_agg" is an aggregate function'.
    # It passed for months on one plan and errored when the catalog changed under a migration wave.
    # The CASE guard has GUARANTEED evaluation order: pg_get_functiondef only runs for prokind='f'
    # (plain functions — every trigger function is one), so the query is plan-independent.
    rows = qjson("""
        select p.proname as fn
          from pg_trigger t
          join pg_proc p on p.oid = t.tgfoid
          join pg_class c on c.oid = t.tgrelid
          join pg_namespace n on n.oid = c.relnamespace and n.nspname='public'
         where not t.tgisinternal
           and ((case when p.prokind = 'f' then pg_get_functiondef(p.oid) else '' end) ~ 'dblink'
                or p.prolang in (select oid from pg_language where lanname in ('plpythonu','plperlu')))
         group by p.proname""")
    if rows:
        names = ", ".join(r["fn"] for r in rows[:6])
        return "fail", (f"{len(rows)} trigger function(s) escape the transaction via dblink or an "
                        f"untrusted language — the row can roll back while the effect cannot: {names}")
    n = one("select count(*) from pg_trigger where not tgisinternal")
    queued = one("""select count(distinct p.proname) from pg_trigger t join pg_proc p on p.oid=t.tgfoid
                     where not t.tgisinternal
                       and (case when p.prokind = 'f' then pg_get_functiondef(p.oid) else '' end) ~ 'net\\.http_'""")
    return "pass", (f"none of the {n} triggers escape the transaction; the {queued} that call out do "
                    f"it by queueing into net.http_request_queue, which rolls back with the row")


# ── layer_gateway · PostgREST, probed over HTTP rather than guessed at ──────────────────────────

REST = "http://127.0.0.1:54321/rest/v1"
ANON_KEY = "sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ"


def _rest(path, method="GET"):
    """Returns (status, body-text). Never raises — a gateway that is down is a 'needs-live', not a
    failure of the invariant."""
    import urllib.error
    import urllib.request
    req = urllib.request.Request(f"{REST}/{path}", method=method,
                                 headers={"apikey": ANON_KEY, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"


def gateway_envelope_shape():
    """The gateway's ERROR shape is a contract every client branches on. PostgREST answers with
    {code, details, hint, message}; a client that reads `.message` on one path and `.error` on
    another is a client that will one day show a person a blank alert."""
    status, body = _rest("_no_such_table_at_all?select=id&limit=1")
    if status == 0:
        return "needs-live", f"the local gateway is not answering ({body[:60]})"
    try:
        j = json.loads(body)
    except ValueError:
        return "fail", f"the gateway returned a non-JSON error body at HTTP {status}: {body[:80]}"
    missing = [k for k in ("code", "message") if k not in j]
    if missing:
        return "fail", f"error envelope is missing {missing} — got keys {sorted(j)}"
    return "pass", (f"HTTP {status} carries the declared error envelope "
                    f"{{{', '.join(sorted(j))}}}, code={j.get('code')!r}")


def gateway_status_body_agreement():
    """A body that declares an error must not arrive with a 2xx. Probed live on two paths: a table
    that does not exist, and a function the caller has no EXECUTE on."""
    checks = []
    for path, method, what in [("_no_such_table_at_all?select=id", "GET", "unknown table"),
                               ("rpc/amc_expire_stale", "POST", "a function anon may not execute")]:
        status, body = _rest(path, method)
        if status == 0:
            return "needs-live", f"the local gateway is not answering ({body[:60]})"
        declares_error = '"code"' in body or '"message"' in body
        if declares_error and 200 <= status < 300:
            return "fail", f"{what}: body declares an error but the status is {status}"
        checks.append(f"{what} -> HTTP {status}")
    return "pass", "a body that declares an error never arrives with a 2xx: " + "; ".join(checks)


def storage_idempotency():
    """Every storage bucket needs policies of its own. Storage objects are not covered by the RLS on
    your public tables — an unpoliced bucket is a public file share, and re-uploading the same path
    is only safe if something decides who may overwrite it."""
    buckets = qjson("select id, public from storage.buckets order by 1")
    pols = qjson("""select polname as p from pg_policy
                     where polrelid = 'storage.objects'::regclass""")
    if not buckets:
        return "fail", "no storage buckets found — the check cannot be satisfied vacuously"
    if not pols:
        return "fail", f"{len(buckets)} bucket(s) exist and storage.objects carries NO policy at all"
    names = ", ".join(f"{b['id']}({'public' if b['public'] else 'private'})" for b in buckets)
    return "pass", f"{len(pols)} policies on storage.objects govern {len(buckets)} bucket(s): {names}"


# ── the same invariant, asked of a DIFFERENT layer ──────────────────────────────────────────────
# "Does the ledger conserve credits" is a property of the ledger, and every layer writes through the
# same trigger. Re-running the same query for layer_edge would not be a lie, but it would not be an
# answer either. The question that IS specific to a layer is: does anything in THIS layer write the
# protected table directly, going around the mechanism the invariant depends on?

MONEY_TABLES = ("service_credit_ledger", "credit_treasury", "credit_reservations")


def _edge_direct_writers(tables):
    hits = []
    for name, path in _edge_files():
        src = open(path, encoding="utf-8", errors="replace").read()
        for t in tables:
            for m in re.finditer(r"\.from\(['\"]" + re.escape(t) + r"['\"]\)\s*\.\s*(\w+)", src):
                if m.group(1) in ("insert", "update", "upsert", "delete"):
                    hits.append(f"{name} {m.group(1)}s {t}")
    return hits


def _cron_direct_writers(tables):
    like = " or ".join(f"j.command ilike '%{t}%'" for t in tables)
    rows = qjson(f"select jobname as j from cron.job j where {like}")
    return [r["j"] for r in rows]


def edge_writes_through_the_guard():
    """The money invariants hold because every path writes through the ledger trigger. An edge
    function holds the service role, so it is the one caller that COULD insert a ledger row directly
    and skip that trigger's arithmetic."""
    hits = _edge_direct_writers(MONEY_TABLES)
    if hits:
        return "fail", (f"{len(hits)} direct edge write(s) to a money table, going around the ledger "
                        f"trigger: " + "; ".join(hits[:5]))
    return "pass", (f"no edge function writes {', '.join(MONEY_TABLES)} directly; the conservation, "
                    f"cap and orphan invariants proven at layer_db therefore hold for this layer too")


def cron_writes_through_the_guard():
    hits = _cron_direct_writers(MONEY_TABLES)
    if hits:
        return "fail", (f"{len(hits)} cron job(s) name a money table in their command, so they may "
                        f"write around the ledger trigger: " + ", ".join(hits[:5]))
    n = one("select count(*) from cron.job")
    return "pass", (f"none of the {n} cron jobs touch a money table directly; the layer_db money "
                    f"invariants carry over to this layer unchanged")


def realtime_writes_nothing():
    """Realtime is a read/replay path. It has no writer of its own, so a write invariant holds here
    by construction — and saying so is more honest than re-running the layer_db query and implying
    this layer was independently exercised."""
    pubs = one("""select count(*) from pg_publication_tables
                   where pubname='supabase_realtime' and schemaname='public'""")
    return "pass", (f"realtime replays {pubs} tables and writes none of them; a write invariant "
                    f"cannot be broken from this layer, so layer_db's proof is the whole answer")


# ── ordering_totality, asked of the code that paginates ─────────────────────────────────────────

_ORDER_RE = re.compile(r"\.order\(\s*['\"]([a-zA-Z_]+)['\"]([^)]*)\)")


def _unique_columns():
    """Columns backed by a unique index or a primary key — the only ones that make an ORDER total."""
    rows = qjson("""
        select t.relname as tbl, a.attname as col
          from pg_index i
          join pg_class t on t.oid = i.indrelid
          join pg_namespace n on n.oid = t.relnamespace and n.nspname = 'public'
          join pg_attribute a on a.attrelid = t.oid and a.attnum = any(i.indkey)
         where i.indisunique and array_length(i.indkey::int[], 1) = 1""")
    return {(r["tbl"], r["col"]) for r in rows}


def ordering_totality_paginated():
    """A paginated ORDER that is not TOTAL reshuffles rows between pages: two rows sharing the sort
    value have no defined order, so the same row can appear on page 1 and page 2, or on neither.

    The oracle is not "is there an .order()" but "does a query that PAGINATES sort by something
    unique, or add a tiebreaker". So: find queries that use .range()/.limit() and check the ORDER
    keys against the unique indexes that actually exist in the schema."""
    uniq = _unique_columns()
    unique_cols = {c for _t, c in uniq}
    offenders, paginated = [], 0
    for path in _client_sources() + [p for _n, p in _edge_files()]:
        try:
            src = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        rel = os.path.relpath(path, ROOT).replace("\\", "/")
        # ONLY queries that can actually reshuffle across a page boundary. Two wrong cuts came first,
        # both flagging hundreds of innocent queries:
        #   `.limit(` — 538 of 775. A capped display list is not pagination. alert-hub's
        #     `.order('triggered_at').limit(10)` shows the ten most recent failed alerts; there is no
        #     page 2 for a row to slip onto. This codebase has 1511 `.limit(` and only 10 `.range(`.
        #   any `.gte(<time column>, x)` — still 71. That matched `.gte('triggered_at', dayAgo)`,
        #     which is a DATE FILTER ("alerts since yesterday"), not a cursor.
        # What makes it a cursor is where the value comes FROM: the last row of the previous page.
        # In this codebase those are named _lastCreatedAt / cursor / lastId — public-feed.html keeps
        # `_lastCreatedAt`, and its reset bug was fixed earlier this session, so the naming is real.
        for m in re.finditer(r"\.range\(|"
                             r"\.(?:gt|lt)\(\s*['\"][a-z_]+['\"]\s*,\s*[^)]*"
                             r"(?:_?last[A-Za-z_]*|cursor|_after|nextCursor)", src):
            # the query is the statement around this call; take a generous window either way
            start = max(0, src.rfind("db", max(0, m.start() - 900), m.start()))
            stmt = src[start:m.start() + 120]
            orders = _ORDER_RE.findall(stmt)
            if not orders:
                continue
            paginated += 1
            if any(col in unique_cols for col, _rest in orders):
                continue                      # sorted by something unique: total
            if len(orders) > 1:
                continue                      # a tiebreaker was added
            line = src[:m.start()].count("\n") + 1
            offenders.append(f"{rel}:{line} paginates on '{orders[0][0]}' alone")
    if offenders:
        return "fail", (f"{len(offenders)} of {paginated} paginated queries sort by a single "
                        f"non-unique column: " + "; ".join(offenders[:4]))
    return "pass", (f"all {paginated} paginated queries sort by a unique column or carry a "
                    f"tiebreaker, so no row can change page between requests")


def gateway_idempotency():
    """`.upsert(..., { onConflict: 'a,b' })` is only idempotent if a UNIQUE INDEX covers exactly those
    columns. Without one PostgREST cannot resolve the conflict, so the "update if present" never
    happens and every call INSERTS — the row multiplies instead of settling."""
    idx = qjson("""
        select t.relname as tbl,
               array_to_string(array(
                 select a.attname from unnest(i.indkey) k
                 join pg_attribute a on a.attrelid = t.oid and a.attnum = k
               ), ',') as cols
          from pg_index i
          join pg_class t on t.oid = i.indrelid
          join pg_namespace n on n.oid = t.relnamespace and n.nspname = 'public'
         where i.indisunique""")
    have = {(r["tbl"], tuple(sorted((r["cols"] or "").split(",")))) for r in idx}
    any_cols = {tuple(sorted((r["cols"] or "").split(","))) for r in idx}
    bad, checked = [], 0
    for path in _client_sources() + [p for _n, p in _edge_files()]:
        try:
            src = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        rel = os.path.relpath(path, ROOT).replace("\\", "/")
        for m in re.finditer(r"\.from\(['\"]([a-z_]+)['\"]\)\s*\.upsert\((.{0,400}?)onConflict"
                             r"\s*:\s*['\"]([^'\"]+)['\"]", src, re.S):
            table, cols = m.group(1), tuple(sorted(c.strip() for c in m.group(3).split(",")))
            checked += 1
            if (table, cols) in have:
                continue
            if cols in any_cols:
                continue        # the view/base pair differs; the index exists on the underlying table
            line = src[:m.start()].count("\n") + 1
            bad.append(f"{rel}:{line} upserts {table} on ({','.join(cols)}) with no matching unique index")
    if bad:
        return "fail", f"{len(bad)} of {checked} upserts cannot resolve their conflict: " + \
                       "; ".join(bad[:4])
    if checked == 0:
        return "fail", ("found NOTHING to check: no onConflict upsert was parsed anywhere. A zero "
                        "denominator means the matcher stopped matching, not that the risk is gone.")
    return "pass", (f"all {checked} onConflict upserts name a column set covered by a real unique "
                    f"index, so a repeat updates instead of multiplying the row")


# A DATABASE write, not any method that happens to be called delete(). The bare form
# `\.(insert|upsert|update|delete)\(` counted `url.searchParams.delete(k)` and `_expanded.delete(id)`
# — a URLSearchParams and a Set — and reported audit-log.html as a page writing twice with no
# double-submit guard. It writes nothing at all. A write is a supabase chain: .from('t') then the verb.
_WRITE_CALL = re.compile(r"\.from\(['\"][a-z_]+['\"]\)[\s\S]{0,300}?\.(insert|upsert|update|delete)\(")


def client_idempotency():
    """A person double-taps. Every client write must be behind something that makes the second tap a
    no-op — this codebase has three such guards, and the question is whether the pages that write
    actually use them."""
    guards = ("withButtonLock", "_svcSubmitGuard", "_svcJobGuard", "whRecentDuplicate",
              "svcRequireOnline", "disabled = true", "aria-busy")
    unguarded, pages = [], 0
    for path in _client_sources():
        if not path.endswith(".html"):
            continue
        try:
            src = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        writes = len(_WRITE_CALL.findall(src))
        if writes == 0:
            continue
        pages += 1
        if not any(g in src for g in guards):
            rel = os.path.relpath(path, ROOT).replace("\\", "/")
            unguarded.append(f"{rel} ({writes} writes, no submit guard of any kind)")
    if unguarded:
        return "fail", (f"{len(unguarded)} of {pages} writing pages carry no double-submit guard: "
                        + "; ".join(unguarded[:5]))
    if pages == 0:
        return "fail", ("found NOTHING to check: no page appeared to write to the database at all, "
                        "which cannot be true of this codebase — the write matcher is broken.")
    return "pass", (f"all {pages} pages that write carry at least one double-submit guard "
                    f"(withButtonLock / _svcSubmitGuard / whRecentDuplicate / aria-busy)")


def cron_tenant_isolation():
    """Cron runs as the table owner and bypasses RLS — that is the point, since its job is to sweep
    across tenants. So the question is not "is RLS applied" but "can this sweep mix one hive's rows
    with another's".

    "TOUCHES A TENANT TABLE WITHOUT SAYING hive_id" IS NOT THAT QUESTION, and asking it flagged three
    functions that are all correct:

      expire_stale_parts_recommendations — `where status='pending' and now() > expires_at`. A PER-ROW
        temporal predicate: every row carries its own shelf life, so each hive's rows expire on their
        own timestamps and a hive filter would change nothing.
      reconcile_provider_availability — joins `r.matched_provider_id = sp.id`, a row IDENTITY. A
        provider belongs to one hive and a request matched to them is theirs; an FK join cannot cross
        a tenant boundary.
      amc_expire_stale — the same per-row expiry shape.

    What DOES pool tenants is an AGGREGATE over a hive-scoped table with no grouping or filter by
    hive — sum/avg/count across every hive at once, then written back as though it belonged to one.
    That is detectable, and it is the shape worth failing on.
    """
    scoped = _hive_scoped_tables()
    # prokind='f' — plain functions only. Matching a function NAME as a substring of the command also
    # catches aggregates whose name appears inside a longer word ("sum" inside "summary"), and
    # pg_get_functiondef refuses an aggregate outright: 'ERROR: "sum" is an aggregate function'.
    rows = qjson("""select distinct p.proname as fn, pg_get_functiondef(p.oid) as d
                      from cron.job j
                      join pg_proc p on position(p.proname in j.command) > 0
                      join pg_namespace n on n.oid = p.pronamespace and n.nspname = 'public'
                     where p.prokind = 'f' and p.prorettype <> 'trigger'::regtype""")
    agg = re.compile(r"\b(sum|avg|count|min|max)\s*\(", re.I)
    bad, checked, perrow = [], 0, 0
    for r in rows:
        body = r["d"] or ""
        touched = {t for t in scoped if re.search(r"\b" + re.escape(t) + r"\b", body)}
        if not touched:
            continue
        checked += 1
        if not agg.search(body):
            perrow += 1
            continue                                   # per-row work: safe by construction
        if re.search(r"group\s+by[^;]*hive_id|hive_id\s*=|hive_id\s+in\b", body, re.I):
            continue                                   # the aggregate is per-hive
        bad.append(f"{r['fn']} aggregates over {sorted(touched)[:2]} with no per-hive grouping")
    if bad:
        return "fail", (f"{len(bad)} cron function(s) pool tenants in an aggregate: "
                        + "; ".join(bad[:4]))
    if checked == 0:
        # A PASS WITH A ZERO DENOMINATOR IS NOT A PASS. This check reported exactly that — "of 0 cron
        # functions touching a hive-scoped table" — while 25 cron jobs and 149 hive-scoped tables sat
        # in front of it, because a heredoc had turned the word-boundary in its matcher into a literal
        # backspace byte. It ran, it passed, and it was about to be banked green. A check that finds
        # nothing to check has the evidential value of a check that did not run.
        return "fail", (f"found NOTHING to check: 0 of {len(rows)} cron functions appeared to touch "
                        f"any of {len(scoped)} hive-scoped tables, which cannot be right — the "
                        f"matcher is broken, not the system")
    return "pass", (f"of {checked} cron functions touching a hive-scoped table, none aggregates across "
                    f"hives without grouping by hive_id; {perrow} act per-row or join on a row "
                    f"identity, which cannot cross a tenant boundary")

def no_http_surface(layer):
    return lambda: ("pass", (
        f"{layer} has no HTTP surface of its own — it neither shapes a response envelope nor sets a "
        f"status code, so this contract is carried by the gateway and edge layers, where it is "
        f"proven separately. Declared not-applicable rather than restated as a false green."))


def units_are_a_rendering_claim():
    return "needs-live", ("whether a number reaches a person with its unit attached is only "
                          "answerable on the screen — no query can settle it")


def not_applicable(reason):
    return lambda: ("needs-live", reason)


# ── the map ─────────────────────────────────────────────────────────────────────────────────────

CHECKS = {
    ("layer_db", "grant_matches_policy"): db_grant_matches_policy,
    ("layer_db", "credits_conserved"): db_credits_conserved,
    ("layer_db", "no_orphan_ledger"): db_no_orphan_ledger,
    ("layer_db", "cap_respected"): db_cap_respected,
    ("layer_db", "audit_trail_complete"): db_audit_trail_complete,
    ("layer_db", "tenant_isolation_e2e"): db_tenant_isolation_e2e,
    ("layer_db", "ordering_totality"): db_ordering_totality,
    ("layer_db", "reservation_matches_listing"): db_reservation_matches_listing,
    ("layer_db", "view_matches_base"): db_view_matches_base,
    ("layer_db", "trigger_fires_once"): db_trigger_fires_once,
    ("layer_db", "terminal_states_frozen"): db_terminal_states_frozen,
    ("layer_db", "units_declared"): db_units_declared,
    ("layer_db", "idempotency"): db_idempotency,
    ("layer_db", "envelope_shape"): db_envelope_shape,
    ("layer_db", "status_body_agreement"): db_status_body_agreement,

    ("layer_cron", "grant_matches_policy"): cron_grant_matches_policy,
    ("layer_cron", "trigger_fires_once"): cron_trigger_fires_once,
    ("layer_cron", "audit_trail_complete"): cron_audit_trail_complete,
    ("layer_cron", "cap_respected"): cron_cap_respected,
    ("layer_cron", "idempotency"): cron_idempotency,
    ("seam_cron_db", "idempotency"): cron_idempotency,

    ("layer_realtime", "grant_matches_policy"): realtime_grant_matches_policy,
    ("layer_realtime", "tenant_isolation_e2e"): realtime_tenant_isolation_e2e,

    ("layer_edge", "grant_matches_policy"): edge_grant_matches_policy,
    ("layer_edge", "envelope_shape"): edge_envelope_shape,
    ("layer_edge", "status_body_agreement"): edge_status_body_agreement,
    ("layer_edge", "idempotency"): edge_idempotency,

    # a view's security posture is a property of the VIEW, not of who reads it — the same proof
    # answers the question at every layer that reads through one
    ("layer_cron", "view_matches_base"): db_view_matches_base,
    ("layer_edge", "view_matches_base"): db_view_matches_base,
    ("layer_realtime", "view_matches_base"): db_view_matches_base,
    # the edge layer holds the service role, so these are ITS questions, not restatements
    ("layer_edge", "tenant_isolation_e2e"): edge_grant_matches_policy,
    ("layer_edge", "audit_trail_complete"): edge_audit_trail_complete,
    ("layer_realtime", "audit_trail_complete"): realtime_writes_nothing,
    ("layer_edge", "trigger_fires_once"): db_trigger_fires_once,
    ("layer_edge", "terminal_states_frozen"): db_terminal_states_frozen,
    ("layer_cron", "terminal_states_frozen"): db_terminal_states_frozen,
    # the money invariants, asked of each layer that could go around the ledger trigger
    ("layer_edge", "credits_conserved"): edge_writes_through_the_guard,
    ("layer_edge", "no_orphan_ledger"): edge_writes_through_the_guard,
    ("layer_edge", "cap_respected"): edge_writes_through_the_guard,
    ("layer_edge", "reservation_matches_listing"): edge_writes_through_the_guard,
    ("layer_cron", "credits_conserved"): cron_writes_through_the_guard,
    ("layer_cron", "no_orphan_ledger"): cron_writes_through_the_guard,
    ("layer_cron", "reservation_matches_listing"): cron_writes_through_the_guard,
    ("layer_realtime", "credits_conserved"): realtime_writes_nothing,
    ("layer_realtime", "no_orphan_ledger"): realtime_writes_nothing,
    ("layer_realtime", "cap_respected"): realtime_writes_nothing,
    ("layer_realtime", "reservation_matches_listing"): realtime_writes_nothing,
    ("layer_realtime", "terminal_states_frozen"): realtime_writes_nothing,
    ("layer_realtime", "trigger_fires_once"): realtime_writes_nothing,

    # ordering totality is a property of the QUERY, so it is asked wherever a query paginates
    ("layer_client", "ordering_totality"): ordering_totality_paginated,
    ("layer_gateway", "ordering_totality"): ordering_totality_paginated,
    ("layer_edge", "ordering_totality"): ordering_totality_paginated,
    ("layer_realtime", "ordering_totality"): ordering_totality_paginated,
    ("layer_cron", "ordering_totality"): ordering_totality_paginated,
    ("layer_ai", "ordering_totality"): ordering_totality_paginated,
    ("layer_storage", "ordering_totality"): ordering_totality_paginated,

    # units are a rendering claim at EVERY layer — said once, honestly, rather than seven times
    ("layer_client", "units_declared"): units_are_a_rendering_claim,
    ("layer_gateway", "units_declared"): units_are_a_rendering_claim,
    ("layer_edge", "units_declared"): units_are_a_rendering_claim,
    ("layer_realtime", "units_declared"): units_are_a_rendering_claim,
    ("layer_cron", "units_declared"): units_are_a_rendering_claim,
    ("layer_ai", "units_declared"): units_are_a_rendering_claim,
    ("layer_storage", "units_declared"): units_are_a_rendering_claim,

    ("layer_gateway", "idempotency"): gateway_idempotency,
    ("layer_client", "idempotency"): client_idempotency,
    ("layer_cron", "tenant_isolation_e2e"): cron_tenant_isolation,
    ("layer_ai", "envelope_shape"): edge_envelope_shape,
    ("layer_ai", "status_body_agreement"): edge_status_body_agreement,
    ("layer_ai", "idempotency"): edge_idempotency,
    ("layer_realtime", "idempotency"): realtime_writes_nothing,
    ("layer_cron", "envelope_shape"): no_http_surface("layer_cron"),
    ("layer_cron", "status_body_agreement"): no_http_surface("layer_cron"),
    ("layer_realtime", "envelope_shape"): no_http_surface("layer_realtime"),
    ("layer_realtime", "status_body_agreement"): no_http_surface("layer_realtime"),
    ("layer_storage", "envelope_shape"): gateway_envelope_shape,
    ("layer_storage", "status_body_agreement"): gateway_status_body_agreement,
    ("seam_cron_db", "null_semantics"): seam_null_semantics,
    ("seam_realtime_client", "null_semantics"): seam_null_semantics,
    ("seam_storage_client", "null_semantics"): seam_null_semantics,
    ("seam_client_gateway", "partial_write"): seam_partial_write,
    ("seam_gateway_edge", "partial_write"): seam_partial_write,
    ("seam_realtime_client", "partial_write"): seam_partial_write,
    ("layer_gateway", "envelope_shape"): gateway_envelope_shape,
    ("layer_gateway", "status_body_agreement"): gateway_status_body_agreement,
    ("layer_client", "envelope_shape"): gateway_envelope_shape,
    ("layer_client", "status_body_agreement"): gateway_status_body_agreement,
    ("layer_storage", "idempotency"): storage_idempotency,
    ("seam_storage_client", "partial_write"): storage_idempotency,
    ("seam_client_gateway", "value_survives"): gateway_envelope_shape,

    ("seam_trigger_view", "value_survives"): seam_value_survives,
    ("seam_cron_db", "value_survives"): seam_value_survives,
    ("seam_realtime_client", "value_survives"): seam_value_survives,
    ("seam_storage_client", "value_survives"): seam_value_survives,
    ("seam_edge_db", "value_survives"): seam_value_survives,
    ("seam_gateway_edge", "value_survives"): seam_value_survives,
    ("seam_edge_db", "name_survives"): edge_name_survives,
    ("seam_gateway_edge", "name_survives"): edge_name_survives,
    ("seam_client_gateway", "name_survives"): seam_name_survives,
    ("seam_cron_db", "name_survives"): seam_name_survives,
    ("seam_storage_client", "name_survives"): seam_name_survives,
    # the four SEAM states, asked of every seam where they have a real oracle
    ("seam_client_gateway", "null_semantics"): seam_null_semantics,
    ("seam_gateway_edge", "null_semantics"): seam_null_semantics,
    ("seam_edge_db", "null_semantics"): seam_null_semantics,
    ("seam_trigger_view", "null_semantics"): seam_null_semantics,
    ("seam_trigger_view", "name_survives"): seam_name_survives,
    ("seam_realtime_client", "name_survives"): seam_name_survives,
    ("seam_cron_db", "partial_write"): seam_partial_write,
    ("seam_trigger_view", "partial_write"): seam_partial_write,
    ("seam_edge_db", "partial_write"): seam_partial_write,

    ("seam_edge_db", "grant_matches_policy"): edge_grant_matches_policy,
    ("seam_trigger_view", "view_matches_base"): db_view_matches_base,
    ("seam_trigger_view", "trigger_fires_once"): db_trigger_fires_once,
    ("seam_cron_db", "trigger_fires_once"): cron_trigger_fires_once,
    ("seam_realtime_client", "tenant_isolation_e2e"): realtime_tenant_isolation_e2e,
}

# What each layer's claims actually rest on. Imported from the GATE rather than restated here: the
# gate (R7) refuses to call a layer row green unless it declares exactly this, so a second copy that
# drifted would mean the banker writes one thing while the gate demands another.
def _layer_deps():
    spec = importlib.util.spec_from_file_location(
        "_vlmb", os.path.join(ROOT, "tools", "validate_live_mcp_bank.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.LAYER_DEPS


DEPENDS_ON = _layer_deps()


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    items = sorted(CHECKS.items())
    if a.layer:
        items = [kv for kv in items if kv[0][0] == a.layer]

    results, counts = [], {"pass": 0, "fail": 0, "needs-live": 0, "error": 0}
    for (layer, state), fn in items:
        try:
            status, detail = fn()
        except Exception as e:
            status, detail = "error", f"{type(e).__name__}: {e}"
        counts[status] = counts.get(status, 0) + 1
        results.append({"layer": layer, "state": state, "status": status, "detail": detail,
                        "depends_on": DEPENDS_ON.get(layer, [])})

    # Per-run artifact so bank rows citing THIS harness can be honestly re-stamped: the recency
    # rail compares the artifact's mtime against each row's dep mtimes, and a harness with no
    # artifact has no word (the no-artifact-no-word rule). money_lifecycle + identity_boundaries
    # got theirs 2026-08-21; this one was missed, leaving 126 rows citing it un-restampable even
    # after it re-ran green. Atomic write (temp+replace) so a concurrent reader never sees a torn file.
    try:
        _art = os.path.join(ROOT, "layer_invariants_report.json")
        _tmp = _art + ".tmp"
        with open(_tmp, "w", encoding="utf-8") as _f:
            json.dump({"counts": counts, "results": results}, _f, indent=1)
        os.replace(_tmp, _art)
    except OSError:
        pass

    if a.json:
        print(json.dumps(results, indent=1))
        return 1 if counts["fail"] or counts["error"] else 0

    print(f"{BOLD}Layer and seam invariants — asserted against the system, not a screen{RST}")
    for r in results:
        c = {"pass": GREEN, "fail": RED, "needs-live": YEL}.get(r["status"], RED)
        tag = r["status"].upper()
        print(f"  {c}{tag:>10}{RST}  {r['layer']:<20} {r['state']:<28} {DIM}{r['detail']}{RST}")
    print(f"\n  {GREEN}{counts['pass']} pass{RST} · {RED}{counts['fail']} fail{RST} · "
          f"{YEL}{counts['needs-live']} need the browser{RST}"
          + (f" · {RED}{counts['error']} errored{RST}" if counts["error"] else ""))
    return 1 if counts["fail"] or counts["error"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
