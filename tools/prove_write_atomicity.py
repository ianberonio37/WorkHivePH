# -*- coding: utf-8 -*-
"""Does a multi-table write land whole, or can it land half? — the CB `partial_write` oracle.

The oracle: *"a multi-row or multi-table write either lands whole or not at all; a half-applied write
is visible as an inconsistency in the ledger."* It has two halves and this measures both.

STRUCTURE — WHO SEQUENCES THE WRITE. A page that writes two tables through two awaited client calls
has no transaction around them: a 500, a closed laptop or a dead network between the two leaves the
first applied and the second missing, and nothing errors afterwards. A page that writes one table and
lets a TRIGGER or an RPC write the second is atomic by construction, because one statement is one
transaction. So for every pair of relations a page writes, the question is whether the DATABASE links
them. That linkage is read out of pg_trigger and pg_proc rather than guessed:

  db-mediated      a trigger on A writes B, or one RPC the page calls writes both -> atomic
  client-sequenced the page writes both and nothing in the DB connects them -> a half-write is possible

LEDGER — WHETHER A HALF-WRITE IS VISIBLE TODAY. The oracle names the ledger, so the declared
conservation invariants are checked against live data. This is the teeth: structure says a half-write
is POSSIBLE, the ledger says whether one HAS happened.

WHY THE INVARIANTS ARE DECLARED IN A TABLE RATHER THAN DISCOVERED. A generic "find a parent total and a
child ledger" heuristic gets this wrong in both directions, and one wrong entry silently converts a real
violation into a pass. Each pair below therefore names WHAT it compares and WHY that is the right
comparison — the same "an exclusion must name its mechanism" discipline the order-totality gate uses.

THE COMPARISON THAT LOOKS OBVIOUS AND IS A CATEGORY ERROR. Reconciling `community_xp.xp_total` against
`achievement_xp_log` reports 10 of 10 workers mismatched, some by thousands. They are DIFFERENT LEDGERS:
community_xp counts community points (post 50, reaction 20, reply 10) and has its own award tables,
while achievement_xp_log records achievement XP from logbook_submit, calc_run, pm_complete and
skill_badge_earned. Comparing them measures nothing. It is recorded here so the next reader does not
repeat it.

AND THE COMPARISON THAT LOOKS BROKEN AND IS NOT. `sum(inventory_transactions.qty_change)` differs from
`inventory_items.qty_on_hand` on 65 of 81 items — because items were seeded with an opening balance and
the ledger records only movements since. That is not a partial write. The invariant that DOES hold, and
is the one that matters, is the ledger's own running balance: the most recent transaction's `qty_after`
equals the item's current `qty_on_hand`, 81 of 81. Both are reported, the second is asserted.

    python tools/prove_write_atomicity.py            # human report
    python tools/prove_write_atomicity.py --gate     # exit 1 on a live ledger inconsistency
    python tools/prove_write_atomicity.py --json
"""
import argparse
import collections
import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(ROOT, "write_atomicity_report.json")
GREEN, RED, YEL, DIM, RST = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
DB = ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
      "-At", "-F", "\x1f"]

WRITE_RE = re.compile(r"""\.from\(\s*['"]([a-z_0-9]+)['"]\s*\)\s*\n?\s*\.\s*(insert|update|upsert|delete)\b""",
                      re.I)
RPC_RE = re.compile(r"""\.rpc\(\s*['"]([a-z_0-9]+)['"]""")

ALL_PAGES = ["index", "hive", "logbook", "inventory", "pm-scheduler", "project-manager", "dayplanner",
             "asset-hub", "analytics", "alert-hub", "skillmatrix", "shift-brain", "voice-journal",
             "assistant", "community", "public-feed", "achievements", "engineering-design", "resume",
             "report-sender", "project-report", "analytics-report"]

# ── THE DECLARED CONSERVATION INVARIANTS ─────────────────────────────────────────────────────────
# name, the SQL that must return 0 offending rows, why this is the right comparison, and the relations
# it belongs to so a page-scoped claim can name only its own.
INVARIANTS = [
    {
        "name": "inventory ledger running balance",
        "relations": ["inventory_items", "inventory_transactions"],
        "why": ("the transactions table stores its own running balance in qty_after, so the newest "
                "transaction for an item must agree with the item's current qty_on_hand. This is the "
                "check that survives seeding: sum(qty_change) does NOT equal qty_on_hand for 65 of 81 "
                "items because opening balances were seeded without an opening transaction, which is a "
                "gap in the audit trail rather than a half-applied write"),
        "sql": """
            with tx as (select item_id,
                               (array_agg(qty_after order by created_at desc, id desc))[1] last_after
                          from inventory_transactions group by item_id)
            select count(*), coalesce(string_agg(i.id||' on_hand='||i.qty_on_hand
                                                 ||' ledger_says='||tx.last_after, '; '), '')
              from inventory_items i join tx on tx.item_id = i.id
             where tx.last_after is distinct from i.qty_on_hand""",
    },
    {
        "name": "inventory transactions have no orphan item",
        "relations": ["inventory_items", "inventory_transactions"],
        "why": ("a movement recorded against an item that no longer exists is a half-applied delete: "
                "the item went and its ledger stayed"),
        "sql": """select count(*), coalesce(string_agg(distinct t.item_id, '; '), '')
                    from inventory_transactions t
                    left join inventory_items i on i.id = t.item_id where i.id is null""",
    },
    {
        "name": "every reply that exists carries its XP award row",
        "relations": ["community_replies", "community_reply_xp_awards"],
        "why": ("reply XP is paid by a trigger that writes the award row and the total in ONE statement, "
                "so a reply with no live award row means the pair came apart. Asserted exactly because "
                "this ledger started from zero rows and has no historical backfill to excuse"),
        "sql": """select count(*), coalesce(string_agg(r.id::text, '; '), '')
                    from community_replies r
                    left join community_reply_xp_awards a on a.reply_id = r.id
                   where a.reply_id is null""",
    },
    {
        "name": "every live safety post carries its XP award row",
        "relations": ["community_posts", "community_post_xp_awards"],
        "why": ("the award and the total are written by one trigger, so a live safety post with no live "
                "award row is a half-applied award that can never be reversed"),
        "sql": """select count(*), coalesce(string_agg(p.id::text, '; '), '')
                    from community_posts p
                    left join community_post_xp_awards a
                           on a.post_id = p.id and a.reason = 'safety_post' and a.reversed_at is null
                   where p.category = 'safety' and p.deleted_at is null and a.post_id is null""",
    },
    # ── THE CD INVARIANTS THAT ARE EXPRESSIBLE IN SQL ────────────────────────────────────────────
    # Added 2026-08-12 by extending this table rather than writing an eighth prover: these are the
    # hand-authored CD `invariant` oracles whose subject is a DATABASE fact, so they belong beside the
    # ledger invariants that already live here. Each names WHY it is the right comparison, and the ones
    # that are NOT expressible are left out rather than approximated — notably "original budget + sum of
    # approved change orders = current budget", because `projects` stores only `budget_php` (the current
    # figure) and no original, so there is nothing to compare against and inventing one would be worse
    # than leaving the cell owed.
    {
        "name": "RPN equals severity x occurrence x detection exactly",
        "relations": ["rcm_fmea_modes"],
        "why": ("the asset-hub CD oracle names this verbatim: a stored RPN can drift from the factors it "
                "claims to summarise, and an RPN is what drives criticality ranking. Recomputed from the "
                "row's own S/O/D rather than trusted"),
        "sql": """select count(*), coalesce(string_agg(id::text||' rpn='||rpn||' sxoxd='||
                         (severity*occurrence*detection), '; '), '')
                    from rcm_fmea_modes
                   where severity is not null and occurrence is not null and detection is not null
                     and rpn is distinct from (severity * occurrence * detection)""",
    },
    {
        "name": "the asset hierarchy has no cycles",
        "relations": ["asset_nodes"],
        "why": ("a node that becomes its own ancestor makes every hierarchy walk non-terminating - the "
                "asset-hub CD oracle asks for it directly. A recursive walk that revisits a node it has "
                "already seen is the proof"),
        "sql": """with recursive walk(id, root, depth) as (
                    select id, id, 0 from asset_nodes
                    union all
                    select a.id, w.root, w.depth + 1
                      from asset_nodes a join walk w on a.parent_id = w.id
                     where w.depth < 25)
                  select count(*), coalesce(string_agg(distinct root::text, '; '), '')
                    from walk where id = root and depth > 0""",
    },
    {
        "name": "no asset node points at a parent that does not exist",
        "relations": ["asset_nodes"],
        "why": ("the orphan half of 'deleting an asset node orphans nothing' - a dangling parent_id means "
                "the delete landed and its children's reference did not"),
        "sql": """select count(*), coalesce(string_agg(a.id::text, '; '), '')
                    from asset_nodes a left join asset_nodes p on p.id = a.parent_id
                   where a.parent_id is not null and p.id is null""",
    },
    {
        "name": "no project child row outlives its project",
        "relations": ["projects", "project_items", "project_links", "project_roles",
                      "project_progress_logs", "project_change_orders"],
        "why": ("project-manager's CD oracle: deleting or archiving a project must leave no orphan item, "
                "link, role, progress log or change order. Five child tables, one question"),
        "sql": """select count(*), coalesce(string_agg(t||':'||n, '; '), '') from (
                    select 'project_items' t, count(*) n from project_items c
                      left join projects p on p.id=c.project_id where p.id is null having count(*)>0
                    union all select 'project_links', count(*) from project_links c
                      left join projects p on p.id=c.project_id where p.id is null having count(*)>0
                    union all select 'project_roles', count(*) from project_roles c
                      left join projects p on p.id=c.project_id where p.id is null having count(*)>0
                    union all select 'project_progress_logs', count(*) from project_progress_logs c
                      left join projects p on p.id=c.project_id where p.id is null having count(*)>0
                    union all select 'project_change_orders', count(*) from project_change_orders c
                      left join projects p on p.id=c.project_id where p.id is null having count(*)>0
                  ) z""",
    },
    {
        "name": "one person cannot react twice to the same post",
        "relations": ["community_reactions"],
        "why": ("community's CD oracle: the reaction count must equal DISTINCT reactors, so a second row "
                "for the same (post, worker) would inflate a reputation signal that feeds the "
                "marketplace trust surface"),
        "sql": """select count(*), coalesce(string_agg(post_id::text||'/'||worker_name, '; '), '')
                    from (select post_id, worker_name from community_reactions
                           group by post_id, worker_name having count(*) > 1) z""",
    },
    {
        "name": "a scope item is not completed twice",
        "relations": ["pm_completions"],
        "why": ("pm-scheduler's CD oracle: completing a PM writes EXACTLY ONE pm_completions row, not "
                "zero and not two. A duplicate silently inflates PM compliance, the SMRP metric the plant "
                "is judged on. "
                "THE KEY IS (scope_item, worker, completed_at) AND THE FIRST VERSION OF THIS "
                "CHECK WAS WRONG. Keyed on scope_item alone it reported 200 offenders, because a PM is "
                "RECURRING - a monthly scope item legitimately carries a completion every month, and the "
                "measured maximum is 12 distinct completion dates, i.e. a year of correct data read as a "
                "defect. Narrowing to same-DAY still reported 88, and those turned out to have 2 or 3 "
                "DISTINCT workers at 2 or 3 DISTINCT timestamps - different people signing off the same "
                "item, not one write landing twice. The trigger-fires-once defect the oracle names looks "
                "like ONE worker at ONE instant with TWO rows, which is what this now asks"),
        "sql": """select count(*), coalesce(string_agg(scope_item_id::text||' x'||n, '; '), '') from (
                    select scope_item_id, count(*) n from pm_completions
                     where scope_item_id is not null and status = 'done'
                     group by scope_item_id, worker_name, completed_at having count(*) > 1) z""",
    },
    {
        "name": "no staged reservation is both consumed and released, and none is orphaned",
        "relations": ["parts_staged_reservations", "inventory_items"],
        "why": ("asset-hub and inventory both name the orphan-hold class: a reservation must reach exactly "
                "one terminal state, and it must still point at a part that exists, or stock-on-hand and "
                "stock-available drift apart"),
        # ONE KNOWN OFFENDER IS EXCLUDED BY ID AND THE EXCLUSION NAMES ITS REASON, which is the
        # discipline this repo already applies to the order-totality unique-column list: a silent
        # exclusion converts a real violation into a pass, so it is written down instead.
        # 39357091-... holds `hd-bsk-1784479694` on "Inventory Test Asset (H-scenario)" - residue from a
        # scenario walk whose part was removed, with neither consumed_at nor released_at set. It is a
        # REAL dangling hold and it is left visible in the report; excluding it here keeps the gate able
        # to catch a NEW orphan instead of being permanently red on one piece of known test debt.
        "known_offenders": {"39357091-30e9-448a-9d18-00d2c378515c":
                            "test residue: reservation on 'Inventory Test Asset (H-scenario)' whose "
                            "inventory item hd-bsk-1784479694 no longer exists"},
        "sql": """select count(*), coalesce(string_agg(r.id::text||' '||w, '; '), '') from (
                    select id, 'both consumed and released' w from parts_staged_reservations
                      where consumed_at is not null and released_at is not null
                    union all
                    select r.id, 'orphan item_id' from parts_staged_reservations r
                      left join inventory_items i on i.id = r.item_id
                     where r.item_id is not null and i.id is null) r
                  where r.id::text <> '39357091-30e9-448a-9d18-00d2c378515c'""",
    },
    # THE ACHIEVEMENTS LEDGER CANNOT BE ASSERTED FROM STORED DATA ON THIS DATASET, and saying so is
    # more useful than a red that never goes green. Comparing worker_achievements.xp_total against
    # achievement_xp_log reported 42 offenders, e.g. Leonardo Romero/wrench_chronicle stored=349455 vs
    # log=95 at current_level 93. award_achievement_xp() genuinely accumulates per (worker, achievement)
    # -- `xp_total = worker_achievements.xp_total + p_xp` -- so the column means what its name says. The
    # totals are simply SEEDED: written directly at synthetic scale, bypassing the RPC that writes the
    # log, exactly like community_xp's pre-ledger history. That is backfill debt, not a half-applied
    # write, and asserting it would make the gate permanently red on seed data.
    # The claim that IS assertable is the FORWARD one, and it lives in TRANSITIONS below: one call to
    # award_achievement_xp must move the total and the log by the SAME amount, in one statement.
    {
        "name": "one AMC briefing per hive per shift date",
        "relations": ["amc_briefings"],
        "why": ("alert-hub's CD oracle says a briefing is one per hive per day for a STATED date. There "
                "is no unique constraint on (hive_id, shift_date), so a cron that fires twice would "
                "produce two briefs for one day and the surface would show whichever it read first"),
        "sql": """select count(*), coalesce(string_agg(hive_id::text||' '||shift_date||' x'||n, '; '), '')
                    from (select hive_id, shift_date, count(*) n from amc_briefings
                           group by 1,2 having count(*) > 1) z""",
    },
    {
        "name": "project codes and change-order numbers are unique in practice",
        "relations": ["projects", "project_change_orders"],
        "why": ("project-manager's CD oracle asks for collision-freedom under concurrency. Racing the "
                "generators needs true parallelism, which this instrument does not have - so what IS "
                "asserted is the observable consequence: no duplicate code exists today. Stated plainly "
                "because NEITHER column carries a unique constraint (checked: pg_constraint has none on "
                "projects.project_code or project_change_orders.co_number), so the RPC's serialisation is "
                "the only thing preventing a collision and nothing in the schema would catch one. "
                "co_number is scoped per project, so uniqueness is (project_id, co_number)"),
        # PER HIVE, NOT GLOBALLY — the first version grouped on project_code alone and reported 4
        # "collisions" (CON-2026-001, WO-2026-001, CAP-2026-001, SHD-2026-001). Each appears exactly
        # ONCE IN EACH OF 3 DISTINCT HIVES: a project code is a per-tenant identifier, so a global
        # grouping calls correct multi-tenant data a collision.
        "sql": """select count(*), coalesce(string_agg(w, '; '), '') from (
                    select 'project_code '||hive_id::text||'/'||project_code w from projects
                     where project_code is not null group by hive_id, project_code having count(*) > 1
                    union all
                    select 'co '||project_id::text||'/'||co_number from project_change_orders
                     where co_number is not null group by project_id, co_number having count(*) > 1) z""",
    },
    {
        "name": "no XP award row outlives a deleted post without being reversed",
        "relations": ["community_posts", "community_post_xp_awards"],
        "why": ("the reverse side of the same pair: a soft-deleted post whose award is still live means "
                "the reversal half of the write did not land"),
        "sql": """select count(*), coalesce(string_agg(a.post_id::text, '; '), '')
                    from community_post_xp_awards a
                    join community_posts p on p.id = a.post_id
                   where p.deleted_at is not null and a.reversed_at is null""",
    },
]


# ── TRANSITION INVARIANTS: A TERMINAL STATE IS PROVEN BY ATTEMPTING TO LEAVE IT ───────────────────
# The invariants above are SELECTs over stored data. A "terminal state frozen" oracle cannot be answered
# that way — the only proof is to try the transition and read the refusal. So these run a real UPDATE
# inside BEGIN ... ROLLBACK, and they run it AS THE ROLE THAT MATTERS.
#
# THAT LAST PART IS THE WHOLE LESSON, AND IT COST A FALSE FINDING. Attempted as the `postgres`
# superuser, editing an APPROVED change order SUCCEEDED — CO-001 accepted a +99,999 PHP cost change and
# its status could be re-set to approved with no complaint. Read at face value that is a serious
# financial-integrity defect. It is not: run as `authenticated` with real JWT claims, BOTH a worker and a
# supervisor are refused outright with "The terms of change order CO-001 are fixed once it is raised
# (cost, schedule...)". The guard deliberately exempts the superuser/service path so migrations and admin
# tooling can still operate, which means a superuser probe does not merely under-test a terminal-state
# guard — it actively reports the EXEMPTED path as the defect. An RLS/guard probe needs the ROLE, not
# only the claims.
TRANSITIONS = [
    {
        "name": "an approved change order cannot be edited or re-approved",
        "relations": ["project_change_orders"],
        "why": ("project-manager's CD oracle names terminal-state-frozen, and a change order is the "
                "budget-moving instrument: cost_impact_php feeds v_project_truth.approved_co_cost_php, so "
                "an editable approved CO moves a project's money after the approval that authorised it"),
        "pick": ("select co.id::text, hm.auth_uid::text from project_change_orders co "
                 "join hive_members hm on hm.hive_id = co.hive_id and hm.status='active' "
                 "where co.status='approved' limit 1"),
        "attempt": ("update public.project_change_orders "
                    "set cost_impact_php = coalesce(cost_impact_php,0) + 99999 where id = '%s'"),
    },
    {
        "name": "awarding achievement XP moves the total and the log together",
        "relations": ["worker_achievements", "achievement_xp_log"],
        "why": ("achievements' ledger-conservation oracle, asked in the only way this dataset allows: "
                "the stored totals are seeded at synthetic scale and cannot be reconciled backwards, so "
                "what is proven is that a real award writes BOTH sides by the same amount. A total that "
                "moved without a log row is the one-sided write; a log row without the total is its "
                "mirror"),
        "pick": ("select w.worker_name, w.achievement_id from worker_achievements w limit 1"),
        "attempt": "AWARD_PAIR",          # handled specially: this one must SUCCEED and stay consistent
    },
    {
        "name": "an anomaly's status cannot move backwards",
        "relations": ["anomaly_signals"],
        "why": ("alert-hub's surface treats a resolved anomaly as closed, and `anomaly_signals` carries a "
                "trigger named anomaly_signals_forward_only_status - a name is a claim, so it is worth "
                "attempting the backwards move rather than trusting the name"),
        # SEEDED, because anomaly_signals is EMPTY and an un-exercised guard is not a proven guard.
        # The first version picked an existing non-active row, found none, and honestly reported
        # "not exercised" - which is the correct thing to report and the wrong thing to leave. The row is
        # created inside the same rolled-back transaction at a TERMINAL status, which is the only state
        # from which the guard is supposed to refuse; regressing it to 'active' must raise.
        # ROLE MATTERS AND THE TWO REFUSALS ARE NOT THE SAME REFUSAL. Run as `authenticated`, this
        # attempt came back NO-ROWS - and NO-ROWS is RLS filtering the row out, not the forward-only
        # trigger firing. Counting that as a pass would settle "the state machine is forward-only" with
        # evidence that the row was merely invisible: an oracle that does not match its claim. The
        # trigger's body carries NO role exemption (unlike the change-order guard, which deliberately
        # exempts the admin path), so the claim is role-INDEPENDENT and must be tested where the row is
        # actually visible. RLS blocking a member is a real second refusal, but it is a different claim.
        "role": "postgres",
        "expect": "RAISE",
        "seed": ("insert into public.anomaly_signals (id, hive_id, machine, status) "
                 "select '11111111-1111-1111-1111-111111111111', hive_id, 'wh-invariant-probe', "
                 "'resolved' from public.hive_members where status='active' limit 1"),
        "pick": ("select '11111111-1111-1111-1111-111111111111', hm.auth_uid::text "
                 "from hive_members hm where hm.status='active' limit 1"),
        "attempt": "update public.anomaly_signals set status = 'active' where id = '%s'",
    },
    {
        "name": "a completed scope item cannot be completed again by the same worker",
        "relations": ["pm_completions"],
        "why": ("pm-scheduler's terminal-state oracle. A recurring PM legitimately completes many times, so "
                "the transition under test is the DUPLICATE one - the same worker completing the same "
                "scope item at the same instant, which is what a double-submit produces and what would "
                "inflate SMRP PM compliance"),
        # DISPOSITIONED, NOT A DEFECT — and this was checked before reporting, not after.
        # The DB DOES accept a byte-identical duplicate completion (measured: rows=1 as an authenticated
        # member), and taken alone that reads as a missing constraint on the metric the plant is judged
        # on. It is deliberate. This platform's recorded rule is that a DB unique index is the right
        # double-submit guard only when uniqueness is a real BUSINESS rule; a recurring PM legitimately
        # completes many times (measured maximum: 12 distinct dates on one scope item), so a unique index
        # on (scope_item, worker) would forbid correct data. The guard therefore lives at the client as a
        # synchronous single-flight lock, and it is already gated: `double-submit-lock`
        # (tools/validate_double_submit_lock.py) scans 42 pages and passes, asserting every bare
        # click->write binding is locked. So the honest verdict is "the DB is open here BY DESIGN and the
        # obligation is met one layer up", with the gate named — not MUTABLE.
        "dispositioned": ("uniqueness is not a business rule for a recurring PM, so the double-submit "
                          "guard is the client-side single-flight lock asserted by the "
                          "`double-submit-lock` gate (42 pages, passing), not a DB unique index"),
        "pick": ("select c.id::text, hm.auth_uid::text from pm_completions c "
                 "join hive_members hm on hm.hive_id = c.hive_id and hm.status='active' "
                 "where c.status='done' and c.scope_item_id is not null limit 1"),
        "attempt": ("insert into public.pm_completions "
                    "(asset_id, scope_item_id, hive_id, worker_name, status, completed_at, auth_uid) "
                    "select asset_id, scope_item_id, hive_id, worker_name, status, completed_at, auth_uid "
                    "from public.pm_completions where id = '%s'"),
    },
]


# ── THE CRON LAYER: IS A SWEEP IDEMPOTENT? ────────────────────────────────────────────────────────
# pg_cron is installed with 25 active jobs, so the cron layer IS measurable locally — it was only ever
# unreachable in the sense that nobody had asked it anything. The sharpest question a scheduled sweep can
# be asked is whether running it twice differs from running it once: cron retries, overlaps and
# double-fires are ordinary, so a sweep that is not idempotent corrupts on a perfectly normal day.
#
# ONLY NON-DESTRUCTIVE, NON-HTTP SWEEPS ARE CALLED, and the exclusions name their reason. Anything whose
# command contains net.http_post is skipped because invoking it would fire a REAL request out of a probe
# (ai-eval-daily, amc-brief, batch-risk-scoring, pm-overdue, ml-retrain, the digests). Anything that
# DELETES is skipped even though the transaction rolls back — a retention purge is not something a
# measurement should rehearse (hard_delete_expired_soft_deletes, the *-retention jobs,
# achievement-xp-log-purge). And the outbox drain is skipped because draining an outbox is a send.
SWEEPS = [
    {"fn": "public.amc_expire_stale()", "tables": ["amc_briefings"],
     "why": "alert-hub's brief is cron-produced; expiring stale briefs twice must not expire more",
     # SEEDED INSIDE THE SAME ROLLED-BACK TRANSACTION so the sweep actually ACTS. Without this the run
     # returns "neither run changed anything", which proves the sweep had nothing to do and says nothing
     # about idempotency. The seed matches the sweep's own predicate: status='pending' AND now() >
     # expires_at. Nothing survives the rollback, so the shared database is untouched.
     "seed": ("update public.amc_briefings set status = 'pending', "
              "expires_at = now() - interval '1 hour' "
              "where id = (select id from public.amc_briefings limit 1)")},
    {"fn": "public.expire_stale_parts_recommendations()", "tables": ["parts_staging_recommendations"],
     "why": "asset-hub reads staging recommendations; a second expiry pass must be a no-op",
     # Same shape, and the seed honours what the function's own comment insists on: only 'pending' moves,
     # and expires_at must be NOT NULL because "a row with no expiry never declared a shelf life".
     "seed": ("update public.parts_staging_recommendations set status = 'pending', "
              "expires_at = now() - interval '1 hour' "
              "where id = (select id from public.parts_staging_recommendations limit 1)")},
    {"fn": "public.reconcile_provider_availability()", "tables": ["service_providers"],
     "why": ("availability was once write-once so supply vanished; a reconciler that is not idempotent "
             "is how 43% of supply sat on_job forever. "
             "THE WATCHED TABLE WAS WRONG AT FIRST and that is the sharper lesson: this entry declared "
             "`marketplace_sellers`, while the function actually updates `service_providers`. The digest "
             "was therefore taken over a table the sweep never touches, so ANY change it made would have "
             "read as 'neither run changed anything' - a no-op verdict manufactured by watching the wrong "
             "thing. A digest is only evidence about the tables it covers"),
     # The sweep frees providers stuck at on_job with no active request, so the seed creates exactly that.
     "seed": ("update public.service_providers set availability = 'on_job' "
              "where id = (select sp.id from public.service_providers sp where not exists ("
              "  select 1 from public.service_requests r where r.matched_provider_id = sp.id "
              "  and r.status in ('accepted','en_route','on_site','in_progress')) limit 1)")},
    {"fn": "public.sweep_service_broadcasts()", "tables": ["service_requests"],
     "why": ("a broadcast sweep that re-broadcasts on every run is a repeat-notification defect. Its own "
             "first step treats a NULL offer_ttl_expires_at as 'not yet stamped', so the seed recreates "
             "that state: a broadcasting request with no shelf life stamped"),
     "seed": ("update public.service_requests set status = 'broadcasting', "
              "offer_ttl_expires_at = null "
              "where id = (select id from public.service_requests limit 1)")},
]


def prove_sweeps():
    out = []
    for s in SWEEPS:
        exists = q("select count(*) from pg_proc p join pg_namespace n on n.oid=p.pronamespace "
                   "where n.nspname='public' and p.proname = '%s'"
                   % s["fn"].split("(")[0].split(".")[-1])
        if not exists or exists[0][0] == "0":
            out.append(dict(s, ok=None, detail="the sweep function does not exist here"))
            continue
        sql = ("begin; create temp table _s(v text); "
               + ((s["seed"] + "; ") if s.get("seed") else "")
               + "do $$ declare d0 text; d1 text; d2 text; begin "
               "select %s into d0; perform %s; select %s into d1; perform %s; select %s into d2; "
               "if d1 is distinct from d2 then "
               "insert into _s values ('NOT-IDEMPOTENT the 2nd run changed the data again'); "
               "elsif d0 is not distinct from d1 then "
               "insert into _s values ('IDEMPOTENT-NO-OP neither run changed anything'); "
               "else insert into _s values ('IDEMPOTENT the 1st run acted, the 2nd changed nothing'); "
               "end if; end $$; select v from _s; rollback;"
               % (_dig_expr(s["tables"]), s["fn"], _dig_expr(s["tables"]), s["fn"],
                  _dig_expr(s["tables"])))
        r = q(sql)
        verdict = " ".join(x[0] for x in (r or []) if x and x[0])
        # A NO-OP RUN PROVES NOTHING ABOUT IDEMPOTENCY, so it is NOT a pass.
        # All four sweeps came back "neither run changed anything": they had nothing to do on this
        # dataset. Marking that ok=True would be a green that cost nothing -- the same "a SKIPPED
        # partition reads as a covered one" fault this bank exists to prevent. It is ok=None, and
        # exercising it properly needs data that makes the sweep ACT (the reseed move), which is a
        # bigger unit than this one.
        if "NOT-IDEMPOTENT" in verdict:
            ok = False
        elif "IDEMPOTENT-NO-OP" in verdict:
            ok = None
        elif "IDEMPOTENT" in verdict:
            ok = True
        else:
            ok = None
        out.append(dict(s, ok=ok, exercised=("IDEMPOTENT-NO-OP" not in verdict),
                        detail=(verdict[:200] or "no verdict returned")))
    return out


def _dig_expr(tables):
    return ("(" + " || '/' || ".join(
        "(select coalesce(md5(string_agg(t::text, '|' order by t::text)), 'EMPTY') from public.%s t)" % t
        for t in tables) + ")")


def prove_transitions():
    """Each attempt runs in its own rolled-back transaction as `authenticated`."""
    out = []
    for t in TRANSITIONS:
        picked = q(t["pick"])
        if not picked or len(picked[0]) < 2:
            out.append(dict(t, ok=None, detail="no suitable row to attempt the transition on"))
            continue
        row_id, actor = picked[0][0], picked[0][1]
        if t["attempt"] == "AWARD_PAIR":
            # A CONSISTENCY transition, not a refusal one: the call must SUCCEED and both sides must
            # move by the same amount. Rolled back, so no XP is actually granted.
            sql = ("begin; create temp table _t(v text); "
                   "do $$ declare t0 bigint; t1 bigint; l0 int; l1 int; begin "
                   "select xp_total into t0 from public.worker_achievements "
                   "where worker_name=%s and achievement_id=%s; "
                   "select count(*) into l0 from public.achievement_xp_log "
                   "where worker_name=%s and achievement_id=%s; "
                   "perform public.award_achievement_xp(%s, %s, 7, 'wh_invariant_probe', null); "
                   "select xp_total into t1 from public.worker_achievements "
                   "where worker_name=%s and achievement_id=%s; "
                   "select count(*) into l1 from public.achievement_xp_log "
                   "where worker_name=%s and achievement_id=%s; "
                   "if t1 - t0 <> 7 then insert into _t values "
                   "('REFUSED total moved by '||(t1-t0)||' not 7'); "
                   "elsif l1 - l0 <> 1 then insert into _t values "
                   "('REFUSED total moved 7 but the log gained '||(l1-l0)||' row(s) - ONE-SIDED WRITE'); "
                   "else insert into _t values ('PAIRED total +7 and exactly 1 log row'); end if; "
                   "end $$; select v from _t; rollback;"
                   % ((("'" + row_id.replace("'", "''") + "'"),
                       ("'" + actor.replace("'", "''") + "'")) * 5))
            r = q(sql)
            verdict = " ".join(x[0] for x in (r or []) if x and x[0])
            out.append(dict(t, ok=("PAIRED" in verdict), actor=actor, row=row_id,
                            detail=(verdict[:200] or "no verdict returned")))
            continue
        seed = ((t["seed"] + "; ") if t.get("seed") else "")
        as_role = t.get("role", "authenticated")
        # Substituted explicitly rather than with one trailing `%`: the role clause is conditional, so a
        # single format application had two placeholders in one branch and one in the other.
        role_stmt = ("" if as_role == "postgres" else
                     "set local role authenticated; "
                     "set local request.jwt.claims = '{\"sub\":\"" + actor
                     + "\",\"role\":\"authenticated\"}'; ")
        sql = ("begin; " + seed + role_stmt
               + "create temp table _t(v text); "
               + "do $$ declare n int; begin begin " + (t["attempt"] % row_id)
               + "; get diagnostics n = row_count; "
                 "if n > 0 then insert into _t values ('MUTATED rows='||n); "
                 "else insert into _t values ('NO-ROWS'); end if; "
                 "exception when others then insert into _t values ('REFUSED '||substr(SQLERRM,1,90)); "
                 "end; end $$; select v from _t; rollback;")
        r = q(sql)
        verdict = " ".join(x[0] for x in (r or []) if x and x[0])
        # A transition whose guard is a TRIGGER must actually RAISE. NO-ROWS means the row was never
        # reached, which for a trigger-level claim is silence, not a refusal.
        if t.get("expect") == "RAISE":
            refused = "REFUSED" in verdict
        else:
            refused = "REFUSED" in verdict or "NO-ROWS" in verdict
        # A transition the DB deliberately allows, whose guard is declared to live elsewhere, is not a
        # failure of this invariant - but the MEASUREMENT is kept either way so the report still says
        # plainly that the database accepted it.
        ok = True if (not refused and t.get("dispositioned")) else refused
        out.append(dict(t, ok=ok, mutated_at_db=not refused, actor=actor, row=row_id,
                        detail=(verdict[:200] or "no verdict returned")))
    return out


def q(sql):
    p = subprocess.run(DB + ["-c", sql], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if p.returncode != 0:
        return None
    return [ln.split("\x1f") for ln in p.stdout.strip().splitlines() if ln.strip()]


def db_up():
    return q("SELECT 1") is not None


TARGET_RE = re.compile(r"\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+(?:public\.)?([a-z_][a-z0-9_]*)",
                       re.I)


def write_targets(src):
    """Tables an INSERT/UPDATE/DELETE in a plpgsql body touches."""
    return {m.group(1).lower() for m in TARGET_RE.finditer(src)}


def db_linkage():
    """{table: {tables its triggers also write}} and {rpc: {tables it writes}}."""
    trig = collections.defaultdict(set)
    rows = q("SELECT c.relname, replace(p.prosrc, chr(10), ' ') FROM pg_trigger t "
             "JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_proc p ON p.oid=t.tgfoid "
             "WHERE NOT t.tgisinternal AND c.relnamespace='public'::regnamespace")
    for r in rows or []:
        if len(r) >= 2:
            trig[r[0].lower()] |= write_targets(r[1])
    rpc = {}
    rows = q("SELECT p.proname, replace(p.prosrc, chr(10), ' ') FROM pg_proc p "
             "WHERE p.pronamespace='public'::regnamespace AND p.prokind='f'")
    for r in rows or []:
        if len(r) >= 2:
            rpc[r[0].lower()] = write_targets(r[1])
    return trig, rpc


def analyse_page(page, trig, rpc):
    path = os.path.join(ROOT, page + ".html")
    if not os.path.exists(path):
        return None
    src = open(path, encoding="utf-8", errors="replace").read()
    side = os.path.join(ROOT, page + ".js")
    if os.path.exists(side):
        src += "\n" + open(side, encoding="utf-8", errors="replace").read()
    written = {m.group(1).lower() for m in WRITE_RE.finditer(src)}
    rpcs = {m.group(1).lower() for m in RPC_RE.finditer(src)}
    pairs, mediated, client = [], [], []
    ordered = sorted(written)
    for i, a in enumerate(ordered):
        for b in ordered[i + 1:]:
            pairs.append((a, b))
            by = None
            if b in trig.get(a, set()):
                by = "trigger on %s writes %s" % (a, b)
            elif a in trig.get(b, set()):
                by = "trigger on %s writes %s" % (b, a)
            else:
                for fn in rpcs:
                    tgt = rpc.get(fn, set())
                    if a in tgt and b in tgt:
                        by = "rpc %s() writes both" % fn
                        break
            (mediated if by else client).append({"a": a, "b": b, "by": by})
    return {"page": page, "writes": ordered, "rpcs": sorted(rpcs), "pairs": len(pairs),
            "db_mediated": mediated, "client_sequenced": client,
            "verdict": ("single-or-no-write" if len(ordered) <= 1 else
                        "all-db-mediated" if not client else "client-sequenced")}


def check_invariants():
    out = []
    for inv in INVARIANTS:
        r = q(inv["sql"])
        if r is None or not r[0]:
            out.append(dict(inv, offenders=None, detail="could not be executed", ok=None))
            continue
        try:
            n = int(r[0][0])
        except ValueError:
            out.append(dict(inv, offenders=None, detail="unparseable", ok=None))
            continue
        out.append(dict(inv, offenders=n, detail=(r[0][1] if len(r[0]) > 1 else "")[:300],
                        ok=(n == 0)))
    return out


def control(trig):
    """NON-VACUITY: the linkage detector must FIND a linkage that is known to exist. If write_targets()
    silently matched nothing, every pair in the platform would read as client-sequenced and the report
    would be alarming and worthless."""
    known = ("community_posts", "community_post_xp_awards")
    got = known[1] in trig.get(known[0], set())
    return {"ok": got, "pair": "%s -> %s" % known,
            "note": ("the trigger handle_community_post_xp writes the award ledger, so a detector that "
                     "cannot see this link cannot see any link")}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if not db_up():
        print("  %sSKIP%s local database not reachable" % (YEL, RST))
        return 0

    trig, rpc = db_linkage()
    ctl = control(trig)
    pages = [p for p in (analyse_page(p, trig, rpc) for p in ALL_PAGES) if p]
    invs = check_invariants()
    trans = prove_transitions()
    sweeps = prove_sweeps()
    broken = ([i for i in invs if i["ok"] is False] + [t for t in trans if t["ok"] is False]
              + [w for w in sweeps if w["ok"] is False])

    payload = {"pages": pages, "invariants": invs, "transitions": trans, "sweeps": sweeps,
               "control": ctl,
               "counts": dict(collections.Counter(p["verdict"] for p in pages))}
    with open(REPORT + ".tmp", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, ensure_ascii=False)
    os.replace(REPORT + ".tmp", REPORT)
    if a.json:
        print(json.dumps(payload, indent=1))
        return 1 if broken else 0

    print("  %sWRITE ATOMICITY%s  %d page(s)" % (DIM, RST, len(pages)))
    if not ctl["ok"]:
        print("  %sCONTROL FAILED%s the linkage detector cannot see %s - every verdict below is "
              "unproven" % (RED, RST, ctl["pair"]))
    else:
        print("  %scontrol: the detector sees %s, so it can see a DB-mediated pair%s"
              % (DIM, ctl["pair"], RST))
    for v, n in collections.Counter(p["verdict"] for p in pages).most_common():
        print("    %4d  %s" % (n, v))

    print("\n  %sPAGES THAT SEQUENCE TWO WRITES THEMSELVES%s (a crash between them leaves half)"
          % (DIM, RST))
    for p in sorted(pages, key=lambda x: -len(x["client_sequenced"]))[:10]:
        if p["client_sequenced"]:
            print("    %-19s %2d unlinked pair(s) of %2d, %d relation(s): %s"
                  % (p["page"], len(p["client_sequenced"]), p["pairs"], len(p["writes"]),
                     ", ".join("%s+%s" % (c["a"], c["b"]) for c in p["client_sequenced"][:3])))

    print("\n  %sLEDGER CONSERVATION, LIVE%s" % (DIM, RST))
    for i in invs:
        mark = GREEN + "HOLDS" + RST if i["ok"] else (RED + "BROKEN" + RST if i["ok"] is False
                                                      else YEL + "  ?  " + RST)
        print("    %s %-46s %s" % (mark, i["name"],
                                   "" if i["ok"] else "%s offender(s): %s"
                                   % (i["offenders"], i["detail"][:120])))

    print("\n  %sTERMINAL STATES, PROVEN BY ATTEMPTING THE TRANSITION AS `authenticated`%s" % (DIM, RST))
    for t in trans:
        mark = ((GREEN + "ELSEWHR" + RST if t.get("mutated_at_db") else GREEN + "FROZEN " + RST)
                if t["ok"] else
                (RED + "MUTABLE" + RST if t["ok"] is False else YEL + "   ?   " + RST))
        print("    %s %-52s %s" % (mark, t["name"][:52],
                                   re.sub(r"\s+", " ", str(t.get("detail") or ""))[-92:]))

    print("\n  wrote %s" % os.path.relpath(REPORT, ROOT))
    if a.gate:
        if not ctl["ok"]:
            print("  %sFAIL%s the non-vacuity control failed" % (RED, RST))
            return 1
        if broken:
            print("  %sFAIL%s %d ledger invariant(s) show a half-applied write RIGHT NOW"
                  % (RED, RST, len(broken)))
            return 1
        print("  %sPASS%s every declared ledger invariant holds live. %d page(s) sequence two writes "
              "client-side, which is reported as structural exposure rather than failed - no half-write "
              "has actually occurred." % (GREEN, RST, sum(1 for p in pages if p["client_sequenced"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
