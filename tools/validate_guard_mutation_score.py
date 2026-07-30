#!/usr/bin/env python3
"""validate_guard_mutation_score.py — does the marketplace test bank actually have TEETH?

THE QUESTION THIS ANSWERS. The bank's SQL lane is 130/130 green and the transition board reads 99.6%. Both
numbers say the cells RAN and agreed with the guards. Neither says anyone would have NOTICED had a guard
behaved differently. The 2026-07-30 session is the evidence that the difference is real: of seven suite
failures triaged, four were defects I had just introduced, two were instruments, and ZERO were product
defects the suite had found — every genuine defect came from BUILDING a new instrument, not from a gate
going red. Coverage said the code ran; nothing measured whether it ran RIGHT.

Mutation testing is the discipline for exactly that, and the research is blunt about the gap: a suite with
100% line coverage can still score BELOW 50% when assertions are weak
(substrate/external/external-mutation-testing-does-the-suite-have-teeth.md). We had already hand-rolled the
idea four times in one session — restoring a vulnerable guard inside a rolled-back transaction to confirm an
exploit returns, planting a defect in a gate's self-test, feeding a broken worker to a matcher. Each was a
one-off mutant proved by anecdote. This makes it systematic and gives it a SCORE.

WHY THE GUARDS, and not the Python gates. The four status-machine guards ARE the marketplace's security
surface: they decide who may move money, publish a listing, settle a job, verify a top-up. We have now found
bypasses in them TWICE (mig 20260729000003 in the review guard, mig 20260730000003 in all four status
guards). No off-the-shelf mutator exists for plpgsql, so this is ours to build — and the guards are small
enough that the operators below cover the ways a guard actually rots.

HOW A MUTANT CAN NEVER OUTLIVE ITS TEST. Each bank cell already runs as `begin; …fixture… …update…
rollback;`. The mutated `CREATE OR REPLACE` is injected INSIDE that same transaction, immediately after
`begin;`, so the mutation and the cell that judges it live and die together. DDL is transactional in
Postgres, so a crash mid-run cannot leave a weakened guard installed. Nothing is ever committed; no
migration is written. The alternative — commit the mutant, run cells, restore — would leave a window where
the platform's own security guard is deliberately broken, which is not a risk worth a metric.

READING THE SCORE:
  killed      a cell objected. The bank noticed this fault. Good.
  SURVIVED    the guard's behaviour changed and NO cell objected. This is a punch-list item naming a
              specific gap, not a vague worry.
  malformed   the mutation produced plpgsql that will not compile. Not a gap in the bank - discarded, and
              reported so the operator can be fixed rather than silently producing an easy score.
  unreachable a mutated branch no cell can reach. Excluded from the denominator WITH A PRINTED REASON,
              because a silently-excluded mutant is how a mutation score gets flattered (the same
              no-silent-skip rule this arc applied to the anon/admin partitions).

  mutation_score = killed / (killed + survived)

Usage:  python tools/validate_guard_mutation_score.py [--selftest] [--verbose] [--update-baseline]
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join(ROOT, "tools", "validate_marketplace_test_bank.py")
BANK = os.path.join(ROOT, "marketplace_test_bank.json")
BASELINE = os.path.join(ROOT, "guard_mutation_baseline.json")
DB = "supabase_db_workhive"
GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

# Each guard and the table whose bank cells judge it.
GUARDS = {
    "guard_service_request_status":     "service_requests",
    "guard_service_topup_status":       "service_credit_topups",
    "guard_marketplace_order_status":   "marketplace_orders",
    "guard_marketplace_listing_status": "marketplace_listings",
    # §12.1 — the first guard scored OUTSIDE the marketplace four. It is one of only four guards on the
    # platform that no registered gate names (found by ranking all 27 un-scored guards), and the only one of
    # those four that WRITES, so its failure mode is a cost leak rather than a corrupted row.
    #
    # This also settles the arc's open design fork for this guard, empirically rather than in the abstract: the
    # harness judges a guard by re-running the bank cells for its table, and `ai_reports` has no derived bank.
    # An AUTHORED cell (TB-QUOTA, declaring covers_tables: ai_reports) is a sufficient judge, so a full derived
    # lane was not needed here. That answer is per-guard, not general — a guard with many states would still
    # want the derived treatment.
    "check_hive_quota_ai_reports":      "ai_reports",
    # The TRUST guard (§12.1, third of the four unmonitored). Its judge is TB-TRUST, an authored cell.
    "guard_service_provider_writes":    "service_providers",
    # The rate limiter, scored once its global ceiling existed (mig 20260730000008). Judge: TB-RATE.
    "check_platform_feedback_rate_limit": "platform_feedback",
    # The fourth and mildest of the unmonitored four: a resource ceiling. Judge: TB-CAP.
    "cap_pdf_job_size":                 "pdf_jobs",
    # ── ARC 13 / F — the SELLER-side trust guard, sibling of guard_service_provider_writes. Also unnamed by
    # any gate. Judge: TB-SELLER, which asserts BOTH the security guarantee (a non-admin cannot self-forge
    # kyb/cert/tier/sales, by UPDATE or at INSERT) AND the intentional admin self-management Ian decided to
    # keep 2026-07-31 (admin_self_kyb=ALLOWED) — so a later party-guard on the admin bypass turns the cell red.
    "guard_marketplace_seller_trust_columns": "marketplace_sellers",
    # ── ARC 13 / F — guard_service_review is behaviourally BANKED (TB-SREVIEW, 11 assertions incl. its mig-003
    # admin-party self-deal protection) but its mutation-SCORING is DEFERRED, on purpose. It reuses the variable
    # names v_is_party / v_is_client from the service_request guards, so ~6 GENERIC operators written for those
    # guards bleed onto it (operators are not scoped to a guard). The admin-party case kills the party operators,
    # but the residual survivors are harness artifacts, not guard gaps — and forcing a 100% via unexplained
    # exclusions would be the false-green this arc exists to prevent. Scoring it cleanly needs OPERATOR SCOPING
    # (roadmap S14.3a / S14.4), the first harness improvement in the queue. The TB-SREVIEW cell still runs in the
    # SQL lane, so the guard's behaviour is covered; only the mutation SCORE waits for the scoping.
    # "guard_service_review": "marketplace_reviews",
    # ── ARC 13 / F — contract-terms immutability. A change order is a contract amendment; once raised its
    # commercial terms are fixed. Shares NO variable names with the status machines and calls neither
    # is_marketplace_admin() nor a system-write GUC, so no generic operator bleeds — it scores against its own
    # five column/DELETE operators alone. Judge: TB-CO. Clean — a bank, not a fix.
    "guard_change_order_terms_immutable": "project_change_orders",
    # ── ARC 13 / F — the two project_progress_logs guards. bind_progress_log_submitter binds identity
    # server-side (auth_uid + reported_by = the caller's own, non-members refused); guard_progress_log_is_a_record
    # makes a filed report immutable and gates acknowledgement to a supervisor who is NOT the reporter. Both share
    # the table, so both are judged by TB-PLOG. Neither shares a variable name with the marketplace guards, so no
    # bleed. Clean — a bank, not a fix.
    "bind_progress_log_submitter":       "project_progress_logs",
    "guard_progress_log_is_a_record":    "project_progress_logs",
    # ── ARC 13 / F — lessons-learned is on the signed project report, so only a hive supervisor may change it.
    # One rule, one operator (keyed on the guard's own unique raise message). Judge: TB-LESSONS. Clean.
    "guard_lessons_learned_is_supervisor": "projects",
    # ── ARC 13 / F — two pure forward-only status ratchets (no auth branch). Judge: TB-FWD. Each has one raise,
    # keyed on its own unique message so nothing bleeds. Clean.
    "anomaly_signals_forward_only_status": "anomaly_signals",
    "shift_plans_forward_only_status":     "shift_plans",
    # ── ARC 13 / F — a 1.5 MB inline-photo size cap on logbook/inventory_items. Resource bound. Judge: TB-IMG.
    # Two operators (cap removed / cap widened), keyed on this guard's own `v_len > v_cap` and cap literal. Clean.
    "check_inline_image_size":            "logbook",
    # ── ARC 13 / F — an announcement (category='announcement') may only be posted by a hive supervisor. One rule,
    # one operator (the guard's own unique raise message). Judge: TB-ANNC. Clean.
    "guard_community_announcement":       "community_posts",
    # ── ARC 13 / F — the FIRST count-based ceiling: logbook per-user/day rate limit. Judge: TB-RATE, which
    # isolates it from the sibling quota guard by pinning the hive cap high and the per-user cap to the caller's
    # live same-day count + 1. One operator, keyed on the user-cap raise's own HINT ('logbook_daily_user') so it
    # cannot hit the same guard's hive-cap raise. Clean.
    "check_logbook_rate_limit":           "logbook",
    # ── ARC 13 / F — the CUMULATIVE per-hive logbook quota. Same two-branch shape as check_hive_quota_ai_reports
    # (enforce -> 54000 / warn-only -> automation_log), so it is scored by the FOUR EXISTING §12 quota operators
    # with NO new operators. Judge: TB-QUOTA-logbook, which isolates it from check_logbook_rate_limit by dating
    # the fixture rows yesterday (cumulative>today). Clean.
    "check_hive_quota_logbook":           "logbook",
    # ── ARC 13 / F — the CUMULATIVE per-hive community-posts quota. Same two-branch shape, scored by the four
    # §12 quota operators, no new ones. Judge: TB-QUOTA-community, three-way isolated (yesterday-rows +
    # different author per insert + the 200/100 daily cap headroom). Clean.
    "check_hive_quota_community":          "community_posts",
}


# ── MUTATION OPERATORS ───────────────────────────────────────────────────────────────────────────────
# Not random character edits — each is a way one of THESE guards has actually rotted or plausibly could.
# `pattern` is searched in the function definition; the FIRST match only is mutated, so one mutant carries
# exactly one fault (two faults can mask each other and make a mutant unkillable for the wrong reason).
OPERATORS = [
    ("party_gate_negated", r"\band\s+not\s+v_is_party\b", "and v_is_party",
     "the admin bypass applies ONLY to a party — the exact self-deal shape mig 20260730000003 fixed"),
    ("party_gate_dropped", r"\band\s+not\s+v_is_party\b", "and true",
     "the admin bypass stops caring about party-ness at all (the pre-mig-003 state)"),
    # THIS OPERATOR TOOK THREE TRIES, AND BOTH WRONG VERSIONS LIED IN THE SAME DIRECTION — they invented a
    # gap that did not exist. Draft 1 injected a `false or ` PREFIX: `false OR X ≡ X`, a perfect no-op, so it
    # was unkillable and reported as a survivor on three guards. Draft 2 injected `false and ` — correct on
    # `guard_marketplace_listing_status`, whose party expression is a single term, and BROKEN on the other
    # three, whose expression is a DISJUNCTION: `v_is_party := false and A or B` parses as `(false and A) or B`
    # ≡ B, so the mutation quietly collapsed to "is the seller a party" — still true for the fixture's admin,
    # so the guard refused correctly and the mutant "survived". Diagnosing it needed the SQLSTATE, not the row
    # count: unmutated and mutated both raised the identical 23514, which is the tell that the mutation never
    # took ([[feedback_verify_the_instrument_before_the_page]]).
    #
    # So: replace the WHOLE assignment statement, not a prefix of its right-hand side. `[^;]*` is safe because
    # a plpgsql assignment carries no semicolon before its terminator. A prefix mutation of any boolean
    # expression is precedence-dependent and therefore unsafe by construction; a statement replacement is not.
    ("is_party_false", r"v_is_party\s*:=[^;]*;", "v_is_party := false;",
     "party-ness always computes FALSE, so every admin is treated as a non-party moderator"),
    ("client_check_true", r"v_is_client\s*:=\s*\(", "v_is_client := true or (",
     "every caller is treated as the client — the ownership pin stops meaning anything"),
    ("provider_check_true", r"v_is_matched_provider\s*:=\s*exists\s*\(", "v_is_matched_provider := true or exists (",
     "every caller is treated as the matched provider"),
    ("admin_bypass_unconditional", r"public\.is_marketplace_admin\(\)\s+AND\s+NOT\s+v_is_party",
     "public.is_marketplace_admin()",
     "the deny-shape guards' admin bypass goes back to unqualified (self-publish / self-release)"),
    # One operator, not two. There WAS a `refusal_removed_upper` here for "the guards written in upper case",
    # which was pure denominator inflation: the search runs with `re.IGNORECASE`, so both patterns matched the
    # SAME first site and the two replacements (`return new;` / `RETURN NEW;`) are the same statement in
    # different case. Every guard therefore contributed two IDENTICAL mutants — and on the order and top-up
    # guards both "survived", printing one real gap twice and making it look like two. Duplicate mutants
    # inflate the denominator exactly as equivalent ones deflate the score; neither may be left standing.
    ("refusal_removed", r"raise\s+exception\s+'Not allowed[^;]*;", "return new;",
     "a refusal becomes a silent allow — the guard fails OPEN"),
    ("state_list_widened", r"old\.status\s+in\s+\(([^)]*)\)", None,
     "an authorised from-state list gains one more state than the product allows"),

    # ── SECOND WAVE. The first nine gave 27/27, and a 100% is only worth what its operators can express -
    # so these six add faults the first wave could not reach. Each is a rot mode these guards specifically
    # could suffer, not a generic character edit.
    ("birth_status_unchecked", r"new\.status\s+not\s+in\s+\('requested','broadcasting'\)", "false",
     "a new request may be BORN in any state, including a privileged/terminal one"),
    ("attribution_pin_removed", r"new\.client_auth_uid\s+is\s+distinct\s+from\s+auth\.uid\(\)", "false",
     "a caller may file a request AS SOMEONE ELSE - the attribution pin stops holding"),
    ("born_matched_allowed", r"new\.matched_provider_id\s+is\s+not\s+null", "false",
     "a request may be born already MATCHED, bypassing the accept RPC entirely"),
    ("reassignment_allowed", r"new\.matched_provider_id\s+is\s+distinct\s+from\s+old\.matched_provider_id",
     "false",
     "matching may be reassigned by a direct write instead of the accept/select RPC"),
    ("ownership_transfer_allowed", r"new\.client_auth_uid\s+is\s+distinct\s+from\s+old\.client_auth_uid",
     "false",
     "a request's OWNERSHIP may be reassigned to another account"),
    ("guc_bypass_always_on",
     r"current_setting\('workhive\.[a-z_]+',\s*true\)\s*=\s*'on'", "true",
     "the announced system-write bypass is permanently ON, so every caller gets the backend path"),

    # ── THIRD WAVE. Written expecting at least one to SURVIVE - a survivor is the point of the exercise,
    # because it names a fault no cell can see. Reaching 100% three times running would only mean the
    # operators had stopped asking new questions.
    ("backend_branch_removed", r"auth\.uid\(\)\s+is\s+null\s+or", "false or",
     "the no-JWT backend/seeder path is gone, so system writes are judged as raw client writes"),
    ("hive_provider_branch_removed",
     r"or\s+\(sp\.provider_type\s*=\s*'hive'\s+and\s+sp\.hive_id\s+in\s*\(", "or (false and sp.hive_id in (",
     "a HIVE provider's active member can no longer act for that provider profile - the branch mig "
     "20260730000003 was careful to preserve"),
    ("stranger_field_edit_allowed",
     r"elsif\s+not\s+\(v_is_client\s+or\s+v_is_matched_provider\)\s+then", "elsif false then",
     "a stranger may edit a request's fields as long as they do not change the status"),
    ("dispute_narrowed_to_client",
     r"\(\(v_is_client\s+or\s+v_is_matched_provider\)\s+and\s+old\.status\s+in\s+\('in_progress','completed'\)",
     "((v_is_client) and old.status in ('in_progress','completed')",
     "only the client may open a dispute - the provider loses the right the guard grants them"),
    # ── FOURTH WAVE. A 100% is only ever "the operators asked nothing new", and the previous 100% here was
    # outright fabricated - so the score gets re-challenged rather than banked. These target rules NO operator
    # touched: the top-up guard's mint-once condition and the two non-payer branches of its party test, plus
    # the request guard's settle rule. All four are on the money path.
    ("mint_on_any_prior_status", r"old\.status\s*=\s*'pending_verification'", "true",
     "the ledger mint stops caring what the top-up came FROM, so re-verifying an already-verified top-up "
     "mints the credit a SECOND time"),
    ("party_provider_account_branch_removed",
     r"or\s*\(coalesce\(old\.account_type, new\.account_type\)\s*=\s*'provider'",
     "or (false and coalesce(old.account_type, new.account_type) = 'provider'",
     "verifying SOMEONE ELSE's top-up into an account you own stops counting as self-dealing - the exact "
     "case the guard's own comment says matters"),
    ("party_consumer_account_branch_removed",
     r"or\s*\(coalesce\(old\.account_type, new\.account_type\)\s*=\s*'consumer'",
     "or (false and coalesce(old.account_type, new.account_type) = 'consumer'",
     "same hole for a consumer wallet: crediting your own consumer balance from another person's top-up"),
    ("settle_by_provider_allowed",
     r"\(v_is_client and old\.status = 'completed'    and new\.status = 'settled'\)",
     "((v_is_client or v_is_matched_provider) and old.status = 'completed' and new.status = 'settled')",
     "the PROVIDER may mark the job settled - self-certifying that the client paid, which mints the "
     "commission"),

    # ── FIFTH WAVE. Four behaviours none of the 24 above can express. The pattern that justifies another
    # wave: every previous one (9 -> 15 -> 20 -> 24) found either a real gap or a defect in this harness, and
    # not one merely confirmed the previous number.
    ("provider_chain_skip_allowed",
     r"old\.status\s*=\s*'on_site'\s+and\s+new\.status\s*=\s*'in_progress'",
     "old.status in ('on_site','en_route') and new.status = 'in_progress'",
     "a provider may SKIP a state in the job chain - starting work without ever arriving on site, which is "
     "the sequence a client's timeline is reconstructed from"),
    ("verified_by_stamp_removed",
     r"new\.verified_by\s*:=\s*coalesce\(new\.verified_by,\s*auth\.uid\(\)\)",
     "new.verified_by := new.verified_by",
     "a top-up verification stops recording WHO verified it - the money path keeps the credit and loses the "
     "accountability ([[feedback_records_that_outlive_the_action]])"),
    ("order_deny_list_narrowed", r"NEW\.status\s+IN\s*\('released',\s*'refunded'\)", "NEW.status IN ('released')",
     "'refunded' drops out of the escrow-only list, so a buyer or seller may refund an order directly"),
    ("is_client_reads_new", r"v_is_client\s*:=\s*\(old\.client_auth_uid\s*=\s*auth\.uid\(\)\)",
     "v_is_client := (new.client_auth_uid = auth.uid())",
     "ownership is read from the INCOMING row rather than the stored one, so a caller could assert who they "
     "are in the same statement that uses it"),

    # The rule mig 20260730000005 added, so the fix cannot silently regress. This is the first operator here
    # written to lock a LIVE exploit rather than to probe for one: an admin who was a party to nothing could
    # redirect a stranger's top-up to their own provider account and verify it in ONE statement, because the
    # party gate reads `coalesce(old.account_id, ...)` while the mint inserts `new.account_id`. Probed end to
    # end before the fix - ALLOWED, one ledger row, 500 credits into the admin's own account.
    ("intake_immutability_removed", r"if TG_OP = 'UPDATE' and auth\.uid\(\) is not null",
     "if false and auth.uid() is not null",
     "a top-up's money-routing fields become rewritable again, so an admin can redirect a stranger's top-up "
     "to an account they own and verify it in one statement (the live exploit mig 20260730000005 closed)"),

    # The two rules mig 20260730000006 added, for the other two instances of the row-version class. Each
    # disables its whole immutability block by falsifying the block's own GUC-exemption term (the coalesce
    # form is unique to the new block; the original system-write check has no coalesce).
    ("order_identity_immutability_removed",
     r"coalesce\(current_setting\('workhive\.order_system_write', true\), ''\) <> 'on'", "false",
     "an order's parties and price become rewritable again, so an admin can claim a stranger's SALE - "
     "update_seller_tier bumps on NEW.seller_name while the party gate reads OLD (probed live: "
     "admin_total_sales=1, the real seller at 0)"),
    ("listing_identity_immutability_removed",
     r"coalesce\(current_setting\('workhive\.listing_system_write', true\), ''\) <> 'on'", "false",
     "a listing's owner becomes rewritable again, so an admin can take over a stranger's listing and publish "
     "it as their own (probed live: final_seller = the admin, final_status = published)"),

    # ── SEVENTH WAVE. Three questions none of the 28 above ask. The third is aimed at the fix I just shipped:
    # a new rule with no cell behind it is the same gap as any other, and my own migration should not get a
    # pass because I wrote it.
    ("admin_check_always_true", r"public\.is_marketplace_admin\(\)", "true",
     "EVERY caller is treated as a platform admin - the authority boundary tested from the other side, since "
     "every existing operator weakens the party gate rather than widening who counts as staff"),
    ("party_reads_incoming_row",
     r"coalesce\(old\.payer_auth_uid, new\.payer_auth_uid\)", "coalesce(new.payer_auth_uid, old.payer_auth_uid)",
     "party-ness on the money guard reads the INCOMING row first - the exact row-version divergence that "
     "produced three live exploits, reintroduced on the payer branch to check the new pin backstops it"),
    ("intake_pin_amount_removed", r"or new\.amount      is distinct from old\.amount\n", "",
     "the AMOUNT drops out of the pinned intake facts, so an admin can inflate a stranger's 500-credit top-up "
     "before verifying it - value forgery rather than destination forgery"),

    # ── EIGHTH WAVE. A PIN OVER N COLUMNS IS ONLY ASSERTED FOR THE COLUMNS SOMEONE THOUGHT TO TEST. Migs
    # 005/006 pin several fields each, and after wave 7 exactly two of them had cells: `amount` (top-ups) and
    # `seller_name` (orders/listings). The rest are unmonitored code inside a rule I wrote eight sections ago —
    # the same "every disjunct needs its own negative" lesson, applied to a CONJUNCTION of pinned columns.
    # The patterns are written against the LIVE `pg_get_functiondef` text, not against my migration source:
    # the first draft of all three matched NOTHING, because the migration builder joined the disjuncts with its
    # own indentation and the catalog returns them normalised. A pattern that matches nothing produces no
    # mutant, so the operator would have asked no question while looking like a clean 100% — caught only
    # because every new pattern here is checked against the live guard before being trusted.
    #
    # `price` is a MIDDLE disjunct, so deleting the line leaves a valid chain. `gcash_ref` and `hive_id` are the
    # LAST disjunct in their blocks and are followed by the `then` / `) THEN` terminator, so removing the line
    # outright would leave a dangling `or` and produce a MALFORMED mutant — an operator bug reported as such,
    # not a gap. They keep their terminator instead.
    ("order_pin_price_removed", r"\s*OR NEW\.price IS DISTINCT FROM OLD\.price", "",
     "an order's PRICE drops out of the pin, so an admin can restate what a settled trade was worth before "
     "releasing it - the money field, on the guard that pays the seller"),
    ("topup_pin_gcash_ref_removed",
     r"or new\.gcash_ref\s+is distinct from old\.gcash_ref then", "then",
     "the GCash reference drops out of the pin, so the receipt a verification is justified by can be rewritten "
     "after the fact - the audit trail for real money"),
    # Named for the COLUMN, not one table: this pattern is the last disjunct of the pin on BOTH the order and
    # listing guards, so it fires twice and the first draft's name ("listing_pin_...") described only half of
    # what it does. An operator's name is read in a survivor report, where a wrong one sends the reader to the
    # wrong guard.
    ("pin_hive_id_removed",
     r"\s*OR NEW\.hive_id IS DISTINCT FROM OLD\.hive_id\) THEN", ") THEN",
     "hive_id drops out of the pin (orders AND listings), so a moderator can move a stranger's row into "
     "ANOTHER TENANT and settle or publish it there - a cross-hive transfer wearing a moderation action"),

    # ── §12.1 · the QUOTA guard's four rot modes. Its two branches fail differently, so both are probed: the
    # enforcing one refuses, the warn-only one records. The second is the dangerous one to lose, because losing
    # it is SILENT — overruns simply stop being recorded.
    ("quota_enforcement_disabled", r"IF q_enforce THEN", "IF false THEN",
     "the quota's BLOCKING mode stops blocking and silently degrades to warn-only, so a hive over its cap "
     "keeps writing while the platform keeps paying"),
    ("quota_warn_log_removed",
     r"INSERT INTO public\.automation_log \(job_name, status, detail, triggered_at\)", "PERFORM 1; -- (",
     "the WARN-ONLY branch stops RECORDING the overrun - the failure that produces no error, no red gate and "
     "no row, so nobody learns a cap was passed"),
    ("quota_boundary_narrowed", r"current_n >= q_max", "current_n > q_max",
     "the cap becomes off-by-one: a hive exactly AT its limit is allowed one more, which is the boundary the "
     "guard exists to hold"),
    ("quota_null_escape_widened", r"IF q_max IS NULL OR NEW\.hive_id IS NULL THEN", "IF true THEN",
     "the guard returns early for EVERY row, so quotas stop existing entirely - the whole-guard-disabled case"),

    # ── §12.1 · the TRUST guard's four rules, each its own operator. `verified` is the badge buyers price
    # against and `on_job` is dispatch state; both are protected on BOTH branches, and a guard covering only
    # one branch is a guard with a hole — which is exactly what these four operators check for.
    ("trust_insert_verified_allowed", r"if new\.verified then", "if false then",
     "a provider may be BORN verified - self-awarding the marketplace's trust badge at creation time, the "
     "branch a transition-shaped suite never enters"),
    ("trust_update_verified_pin_removed",
     r"if new\.verified is distinct from old\.verified or new\.verified_at is distinct from old\.verified_at then",
     "if false then",
     "the verification pin drops, so a provider can award themselves the badge (or forge only its DATE, which "
     "fakes the provenance while leaving the boolean honest)"),
    ("trust_insert_on_job_allowed", r"if new\.availability = 'on_job' then", "if false then",
     "a provider may be born ON_JOB - dispatch state self-declared at creation"),
    ("trust_update_on_job_allowed",
     r"if new\.availability = 'on_job' and old\.availability <> 'on_job' then", "if false then",
     "a provider may set themselves on_job, appearing busy to dodge the matcher or free while already working"),

    # ── §12.1 · the anonymous CEILING added by mig 20260730000008, so the fix cannot silently regress. The
    # per-identity limit was never the problem — it worked exactly as written and protected nothing, because
    # its bucket key is a field the client supplies.
    ("anon_ceiling_removed", r"IF NEW\.auth_uid IS NULL THEN", "IF false THEN",
     "the platform-wide anonymous ceiling disappears, so varying worker_name mints unlimited fresh buckets "
     "again - the evasion this migration closed"),
    ("anon_ceiling_widened", r"IF v_anon_count >= 20 THEN", "IF v_anon_count >= 100000 THEN",
     "the ceiling is raised out of reach, which is the same hole with a number in front of it"),

    # ── §12.1 · the PDF chunk ceiling. A resource bound, so its failure mode is a stalled embedding queue
    # rather than a stolen row — but a ceiling nobody tests quietly becomes a suggestion.
    ("pdf_cap_removed", r"IF n > 200 THEN", "IF false THEN",
     "the 200-chunk ceiling disappears, so one oversized upload can turn into an unbounded embedding run"),
    ("pdf_cap_widened", r"IF n > 200 THEN", "IF n > 100000 THEN",
     "the ceiling is raised out of reach - the same hole with a number in front of it"),
    ("pdf_array_typecheck_broken", r"jsonb_typeof\(NEW\.chunks_json\) = 'array'", "jsonb_typeof(NEW.chunks_json) = 'nope'",
     "every payload counts as ZERO chunks because the array test can never match, so the cap is computed but "
     "never triggered - a guard that runs and decides nothing"),

    ("cancel_window_widened",
     r"and\s+new\.status\s*=\s*'cancelled_by_provider'", "and new.status is not null",
     "the provider-cancel rule stops naming its target state, so it authorises any transition from those "
     "states"),

    # ── ARC 13 / F · the SELLER trust guard's UPDATE self-upgrade pins, one operator per column. The INSERT
    # branch and the admin/system-write bypasses are already covered by refusal_removed / admin_check_always_true
    # / guc_bypass_always_on, which fire on this guard the moment it enters GUARDS — so these four target only
    # the per-column UPDATE pins those generic operators cannot reach. Each pattern names a COLUMN unique to
    # marketplace_sellers (tier / total_sales / kyb_verified / cert_verified), so it matches this guard and no
    # other. Neutering one pin lets a non-admin seller self-set that one trust signal, which the matching
    # TB-SELLER assertion (self_tier / self_sales / self_kyb / self_cert) catches. The kyb/cert patterns key on
    # the UPDATE-branch `IS DISTINCT FROM COALESCE(OLD...)` form, which is unique to the UPDATE block — the
    # INSERT branch uses `= true OR`, so the first-match rule cannot confuse the two.
    ("seller_tier_selfupgrade_allowed", r"NEW\.tier\s+IS DISTINCT FROM OLD\.tier", "false",
     "a seller may raise their OWN tier - the bronze/silver/gold trust ladder becomes self-declared"),
    ("seller_sales_selfinflate_allowed", r"NEW\.total_sales\s+IS DISTINCT FROM OLD\.total_sales", "false",
     "a seller may inflate their OWN total_sales - the track record the matcher and buyers weigh, forged"),
    ("seller_kyb_selfverify_allowed",
     r"COALESCE\(NEW\.kyb_verified,false\)\s+IS DISTINCT FROM COALESCE\(OLD\.kyb_verified,false\)", "false",
     "a seller may turn their OWN kyb_verified on - the platform's KYB badge, self-awarded (UPDATE branch)"),
    ("seller_cert_selfverify_allowed",
     r"COALESCE\(NEW\.cert_verified,false\)\s+IS DISTINCT FROM COALESCE\(OLD\.cert_verified,false\)", "false",
     "a seller may turn their OWN cert_verified on - the certification badge, self-awarded (UPDATE branch)"),

    # NOTE: the three guard_service_review operators (review_status_gate_removed / _client_direction_unchecked /
    # _provider_direction_unchecked) were removed alongside deferring that guard from GUARDS above. They only
    # match guard_service_review's text, so they are re-added with it once operator scoping lands (roadmap
    # S14.3a) — keeping them here now would be dead code that matches nothing.

    # ── ARC 13 / F · guard_change_order_terms_immutable's five rot modes. Each pattern names a column UNIQUE to
    # project_change_orders (cost_impact_php / scope_change / co_number / schedule_impact_days) or the guard's own
    # DELETE message, so none can bleed onto another guard — the operator-scoping problem is avoided by keying on
    # text only this guard has. Dropping a pin makes that one term user-writable; TB-CO's matching negative
    # (user_edits_cost/scope/conumber/schedule) catches it. The DELETE operator lets a user delete a raised order,
    # caught by user_deletes. The title pin has no operator (title is not unique enough to mutate without bleed);
    # it is still locked by the cell's user_edits_title assertion in the SQL lane.
    ("co_cost_pin_removed", r"NEW\.cost_impact_php\s+IS DISTINCT FROM OLD\.cost_impact_php", "false",
     "a raised change order's COST becomes user-writable - the money term of a contract amendment, silently"),
    ("co_scope_pin_removed", r"NEW\.scope_change\s+IS DISTINCT FROM OLD\.scope_change", "false",
     "the SCOPE of a raised change order becomes rewritable - what work the amendment covers, changed after the fact"),
    ("co_number_pin_removed", r"NEW\.co_number\s+IS DISTINCT FROM OLD\.co_number", "false",
     "the CO number becomes rewritable, so the amendment's own identity on the trail can be reassigned"),
    ("co_schedule_pin_removed", r"NEW\.schedule_impact_days\s+IS DISTINCT FROM OLD\.schedule_impact_days", "false",
     "the SCHEDULE impact becomes rewritable - the delay the amendment commits to, restated"),
    # RETURN OLD, not PERFORM 1: a BEFORE-DELETE trigger allows the delete only by returning a non-null row.
    # Replacing the raise with PERFORM 1 let control fall THROUGH to the terms-check, which references NEW.* —
    # NULL on a DELETE — and errored, so the delete stayed blocked by a downstream accident and the mutant
    # SURVIVED (blocked, but not by the rule this operator removes). RETURN OLD skips the terms check and
    # actually permits the delete, which TB-CO's user_deletes assertion then catches.
    ("co_delete_allowed", r"RAISE EXCEPTION 'A change order cannot be deleted[^;]*;", "RETURN OLD;",
     "a raised change order can be DELETED outright, erasing it from the amendment trail instead of cancelling"),

    # ── ARC 13 / F · the two project_progress_logs guards. All seven patterns are unique to these guards
    # (progress-log columns, the bind assignments, or the two guards' own raise messages), so none bleeds.
    # bind_progress_log_submitter — identity binding:
    ("plog_bind_reported_by_bypassed", r"NEW\.reported_by := v_me", "NEW.reported_by := NEW.reported_by",
     "the submitter's name stops being bound server-side, so a worker can file a report UNDER SOMEONE ELSE'S "
     "name - free-text identity becomes a claim again"),
    ("plog_bind_auth_bypassed", r"NEW\.auth_uid\s+:= auth\.uid\(\)", "NEW.auth_uid := NEW.auth_uid",
     "the auth_uid attribution stops being pinned to the caller, so a report can be filed with no or a forged "
     "actor"),
    # guard_progress_log_is_a_record — immutability + the two ack rules:
    ("plog_pct_pin_removed", r"NEW\.pct_complete IS DISTINCT FROM OLD\.pct_complete", "false",
     "a filed report's pct_complete becomes editable - the progress figure a project rollup and earned value "
     "are computed from, rewritten after the fact"),
    ("plog_hours_pin_removed", r"NEW\.hours_worked IS DISTINCT FROM OLD\.hours_worked", "false",
     "a filed report's hours_worked becomes editable - the labour figure behind cost, restated"),
    ("plog_blockers_pin_removed", r"NEW\.blockers\s+IS DISTINCT FROM OLD\.blockers", "false",
     "a filed report's blockers text becomes editable, so the record of what was in the way can be quietly erased"),
    ("plog_ack_supervisor_removed",
     r"RAISE EXCEPTION 'Acknowledging a progress report is a supervisor action\.'[^;]*;", "NULL;",
     "a non-supervisor may acknowledge a progress report - the sign-off that says a supervisor reviewed the work"),
    ("plog_ack_own_removed", r"RAISE EXCEPTION 'You cannot acknowledge your own[^;]*;", "NULL;",
     "a supervisor may acknowledge their OWN report - reviewing your own work, the self-signature the "
     "segregation rule exists to stop"),

    # ── ARC 13 / F · guard_lessons_learned_is_supervisor (projects). One rule, keyed on the guard's own unique
    # raise message so it cannot bleed.
    ("lessons_supervisor_gate_removed", r"RAISE EXCEPTION 'Lessons-learned appears on the signed[^;]*;", "NULL;",
     "a non-supervisor may rewrite the lessons-learned on a signed project report - the sign-off text, edited "
     "by someone who never signed"),

    # ── ARC 13 / F · the two forward-only status ratchets. Each keyed on its own unique raise message.
    # The message itself contains a semicolon ('...is terminal; cannot regress...'), so a `[^;]*;` pattern stops
    # INSIDE the string literal and leaves a dangling clause — a malformed mutant that dies as a broken fixture,
    # not a real kill. Match the whole statement through its real terminator (USING ERRCODE ... ;) instead.
    ("anomaly_terminal_regress_allowed",
     r"RAISE EXCEPTION 'anomaly_signals:[\s\S]*?USING ERRCODE = 'check_violation';", "NULL;",
     "an anomaly signal may regress OUT of a terminal state (resolved/expired -> active), so a closed anomaly "
     "can be silently reopened past the state machine"),
    ("shift_regress_allowed", r"RAISE EXCEPTION 'shift_plans: cannot regress[^;]*;", "NULL;",
     "a shift plan may regress (published -> draft), so an archived or published schedule can be pulled back to "
     "a draft, breaking the forward-only ratchet"),

    # ── ARC 13 / F · the inline-image size cap. Both patterns are unique to this guard.
    ("image_cap_removed", r"v_len > v_cap", "false",
     "the 1.5 MB inline-photo cap stops firing, so one oversized base64 data-URL can bloat a row and every list "
     "query that reads it"),
    ("image_cap_widened", r"v_cap  integer := 1500000", "v_cap  integer := 900000000",
     "the cap is raised to ~900 MB, out of any real reach - the same hole with a number in front of it"),

    # ── ARC 13 / F · announcements are supervisor-only. Keyed on the guard's own unique raise message.
    ("announcement_supervisor_gate_removed",
     r"RAISE EXCEPTION 'Only supervisors can post announcements'[^;]*;", "NULL;",
     "any member may post a hive-wide ANNOUNCEMENT, not just a supervisor - the broadcast channel stops being "
     "an authority statement"),

    # ── ARC 13 / F · the logbook PER-USER rate limit. Keyed on the user-cap raise's own HINT so it targets the
    # per-user rule and not this guard's identically-messaged hive-cap raise (which differs only in the HINT).
    ("logbook_user_rate_removed", r"RAISE EXCEPTION 'You have logged[^;]*logbook_daily_user';", "NULL;",
     "the per-user/day logbook rate limit stops firing, so one account can flood the logbook past its abuse cap"),
]

VOCAB_EXTRA = "'settled'"


# ── EXCLUSIONS ───────────────────────────────────────────────────────────────────────────────────────────
# A mutant NO caller can observe is not a gap in the bank, and counting it as a survivor understates the
# bank exactly as counting a false kill overstates it. Excluded mutants leave the denominator, but only
# with (a) a mechanism, (b) the on-disk evidence, and (c) a self-policing re-run below.
#
# The bar is deliberately high because "unreachable" is the easiest thing in this whole tool to lie with.
# Three of the four admin-bypass mutants on `guard_service_request_status` LOOKED unreachable for exactly
# this reason and were nearly excluded on the strength of TB-I2's prose — then TB-FIELD gave the guard an
# admin who is a PARTY (via hive membership, so the USING clause lets the row through) and all four died.
# They were never unreachable; the bank simply had no cell that could see them. So an exclusion has to name
# the MECHANISM that makes observation impossible, not the absence of a cell that observes it.
EXCLUDED = {
    # ARC 13 / F: state_list_widened bleeds onto anomaly_signals (both use `OLD.status IN (...)`), but is
    # EQUIVALENT here because VOCAB_EXTRA ('settled') is not a valid anomaly status — the CHECK constraint on
    # anomaly_signals.status allows only active/acknowledged/resolved/expired, so no row can ever hold 'settled'
    # and widening the terminal set to include it cannot change any outcome. This is the operator-scoping bleed
    # (roadmap S14.4) handled locally with a provable equivalence rather than a false kill. Falsifiable: the
    # mutant is still run every time, and if a cell ever objects the gate FAILS as a STALE EXCLUSION.
    ("anomaly_signals_forward_only_status", "state_list_widened"): (
        "Equivalent: VOCAB_EXTRA 'settled' is not a valid anomaly_signals.status (the CHECK allows only "
        "active/acknowledged/resolved/expired), so widening the terminal set `('resolved','expired')` to "
        "include it is unreachable — no row can be 'settled', so the added element never participates in a "
        "transition. state_list_widened was written for the service_request status machine and bleeds onto this "
        "guard only because both write `OLD.status IN (...)`; it is retired here by construction, not by a "
        "missing test."
    ),
    ("guard_service_request_status", "stranger_field_edit_allowed"): (
        "RLS pre-empts the trigger. `service_requests_party_update` is "
        "USING (client_auth_uid = auth.uid() OR matched_provider_id IN my_service_provider_ids()) with no "
        "admin clause, and a USING clause filters row VISIBILITY, so a stranger's UPDATE matches ZERO rows "
        "and the trigger never fires - the guard cannot refuse what it is never asked about. Unlike the "
        "admin-bypass case there is no identity that fixes this: any caller who CAN see the row is by "
        "definition a party, and the mutated branch only governs non-parties. Evidence on disk: "
        "TB-FIELD-nonstatus-edits-and-hive-party asserts stranger_edits_field_layer=rls-filtered, which "
        "fails if RLS ever stops pre-empting."
    ),
    ("guard_service_request_status", "is_client_reads_new"): (
        "Equivalent under every OUTCOME, because a later rule backstops the only paths where it could matter. "
        "`v_is_client` is read from OLD; the mutant reads NEW. Those two agree on every UPDATE that leaves "
        "`client_auth_uid` alone, so the mutation is a no-op there. The only way they can disagree is an UPDATE "
        "that CHANGES `client_auth_uid` - and the guard's own field rule (`new.client_auth_uid is distinct from "
        "old.client_auth_uid` -> 'request ownership cannot be reassigned') refuses precisely those, after the "
        "status branch and the party branch have run. So whichever way v_is_client computes, such a write is "
        "still refused: the mutant can change WHICH rule objects, never WHETHER one does. Killing it would "
        "require asserting an error MESSAGE rather than an outcome, which is a brittle oracle this bank "
        "deliberately avoids. Falsifiable by construction: the mutant is still executed every run, and if any "
        "cell ever does object the gate FAILS as a STALE EXCLUSION rather than pocketing the kill."
    ),
    # `admin_check_always_true` on all three deny-shape guards. The mechanism is worth stating precisely,
    # because it is the sharpest instance of masking in this file: the mutation widens who counts as an admin
    # INSIDE THE GUARD, while the RLS policy on the same table evaluates the REAL `is_marketplace_admin()`.
    #   mkt_listings_update      USING (seller_name IN auth_worker_names() OR is_marketplace_admin())
    #   mkt_orders_update        USING (buyer_name IN ... OR seller_name IN ... OR is_marketplace_admin())
    #   topups_admin_update      USING is_marketplace_admin()
    # So a member / counterparty / cross-tenant actor - the only ones whose refusal could reveal the mutant -
    # is filtered by the policy before the trigger fires, and a 0-row UPDATE satisfies "refused". The one
    # actor RLS does admit is the OWNER, for whom v_is_party is TRUE, so `true AND NOT v_is_party` is false
    # and the bypass does not apply either way. No caller can observe it.
    #
    # The general form, which is not obvious: MUTATING A GUARD CANNOT BE OBSERVED THROUGH A PATH THE POLICY
    # CLOSES USING THE SAME PREDICATE, because the policy still calls the real function. Widening a trigger's
    # notion of "staff" is invisible wherever RLS independently gates on staff-ness.
    ("guard_marketplace_listing_status", "admin_check_always_true"): (
        "Masked by RLS, which evaluates the REAL is_marketplace_admin() while the mutant only widens the guard's copy. Every actor whose refusal could reveal it (member / counterparty / cross-tenant) is filtered by the UPDATE policy before the trigger fires, so the write affects 0 rows and that IS a refusal; the only actor the policy admits is the owner, who is a party, so the bypass does not apply either way. Falsifiable by construction: still executed every run, and a cell that ever objects fails the gate as a STALE EXCLUSION."
    ),
    ("guard_marketplace_order_status", "admin_check_always_true"): (
        "Masked by RLS, which evaluates the REAL is_marketplace_admin() while the mutant only widens the guard's copy. Every actor whose refusal could reveal it (member / counterparty / cross-tenant) is filtered by the UPDATE policy before the trigger fires, so the write affects 0 rows and that IS a refusal; the only actor the policy admits is the owner, who is a party, so the bypass does not apply either way. Falsifiable by construction: still executed every run, and a cell that ever objects fails the gate as a STALE EXCLUSION."
    ),
    ("guard_service_topup_status", "admin_check_always_true"): (
        "Masked by RLS, which evaluates the REAL is_marketplace_admin() while the mutant only widens the guard's copy. Every actor whose refusal could reveal it (member / counterparty / cross-tenant) is filtered by the UPDATE policy before the trigger fires, so the write affects 0 rows and that IS a refusal; the only actor the policy admits is the owner, who is a party, so the bypass does not apply either way. Falsifiable by construction: still executed every run, and a cell that ever objects fails the gate as a STALE EXCLUSION."
    ),
    ("guard_service_topup_status", "party_reads_incoming_row"): (
        "Masked by the fix it was written to test, which is the intended outcome. Reading "
        "coalesce(NEW.payer_auth_uid, OLD.payer_auth_uid) instead of OLD-first can only differ when "
        "payer_auth_uid CHANGES in the same statement - and mig 20260730000005 pinned payer_auth_uid as an "
        "immutable intake fact, so any write that changes it is refused before the party computation matters. "
        "The row-version divergence that produced three live exploits is now unreachable on this branch by "
        "construction. Recorded rather than deleted: if the pin is ever loosened, this mutant becomes "
        "killable and the STALE EXCLUSION failure is the alarm."
    ),
}


def psql(sql: str, timeout: int = 60):
    try:
        r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-At"],
                           input=sql, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
    except Exception:
        return None
    return (r.stdout or "") if r.returncode == 0 else None


def load_runner():
    """Import the bank's SQL-lane runner as a module so the mutation score is measured by the REAL cells.

    Re-implementing cell execution here would measure a copy of the bank, not the bank — and a copy drifts.
    """
    spec = importlib.util.spec_from_file_location("tb_runner", RUNNER)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def functiondef(name: str):
    """The complete, directly-executable CREATE OR REPLACE for a guard."""
    out = psql(f"select pg_get_functiondef(oid) from pg_proc where proname = '{name}' limit 1;")
    return out.strip() if out and out.strip() else None


def make_mutants(name: str, fdef: str):
    """-> [(op_name, description, mutated_definition)] — one fault each."""
    mutants = []
    for op, pattern, repl, why in OPERATORS:
        m = re.search(pattern, fdef, re.IGNORECASE)
        if not m:
            continue
        if op == "state_list_widened":
            inner = m.group(1)
            if VOCAB_EXTRA in inner:
                continue                       # already there; widening it would be a no-op mutant
            mutated = fdef[:m.start(1)] + inner + ", " + VOCAB_EXTRA + fdef[m.end(1):]
        else:
            mutated = fdef[:m.start()] + repl + fdef[m.end():]
        if mutated != fdef:
            mutants.append((op, why, mutated))
    return mutants


def cells_for(bank, runner, table: str):
    """The bank's own executable cells for one table, positives FIRST — derived cells AND authored probes.

    THE AUTHORED PROBES NEARLY GOT MISSED, and that would have been a lie in the honest direction. Probes
    carry no `transition` field, so a selection keyed on `transition.table` cannot see them. The first score
    this tool produced reported `guard_service_topup_status` at **0% on 1 cell** — while
    `TB-I2-admin-bypass-only-for-non-parties` was sitting in the bank asserting precisely the top-up
    self-deal those mutants create, and reading the credit ledger back to prove nothing was minted.
    Under-counting the bank is the same class of error as over-claiming it: both report a number whose
    evidence is elsewhere ([[feedback_verify_the_instrument_before_the_page]]).

    Probes declare `covers_tables` explicitly rather than having it inferred from their SQL, so the claim
    "this probe exercises that guard" is auditable and cannot drift silently when a probe is edited.

    Order is for speed only: a fail-open mutant dies on the first negative cell, a fail-closed one on the
    first positive, and the loop early-exits on the first objection.
    """
    derived = [c for c in bank["tests"]
               if c.get("lane") == "sql" and c.get("status") != "covered"
               and isinstance(c.get("transition"), dict)
               and c["transition"].get("table") == table
               and runner.has_identity(c.get("authority"))
               and (c["transition"].get("from") != "*" or table in runner.DENY_FIXTURES)]
    derived.sort(key=lambda c: 0 if c.get("expect") == "allowed" else 1)
    authored = [c for c in bank["tests"]
                if isinstance(c.get("probe"), dict) and table in (c.get("covers_tables") or [])]
    # Authored probes first: they assert whole scenarios (self-deal + the ledger read-back), so they tend to
    # kill the subtle party-gate mutants that a single-UPDATE derived cell cannot see.
    return authored + derived


def run_cells(runner, cells, legal, injected_ddl=None, stop_on_fail=True):
    """Run cells, optionally with a mutated guard injected INSIDE each cell's own transaction.

    -> (n_ran, first_objection_or_None)
    """
    original = runner.psql_script
    if injected_ddl is not None:
        # THE TRAILING SEMICOLON IS LOAD-BEARING, and its absence silently faked an entire score.
        #
        # `pg_get_functiondef()` returns the definition ending at `$function$` with NO terminator. Injected
        # as-is after the cell's `begin;`, the CREATE statement swallowed the cell's next statement and psql
        # reported `syntax error at or near "insert"` — the cell never ran at all.
        #
        # That failure mode is invisible in the worst way, because the runner's oracle treats an ERROR as a
        # REFUSAL: a NEGATIVE cell therefore PASSED on broken SQL, while a POSITIVE cell failed and was
        # scored as "the bank noticed". So the kills were counted for a mutation the bank never saw. The
        # first 42/42 was measuring my own broken injection, not the bank's assertions
        # ([[feedback_gate_parsed_text_not_the_db_false_green]] — a green whose evidence is something else).
        ddl = injected_ddl.rstrip()
        if not ddl.endswith(";"):
            ddl += ";"

        def patched(sql, timeout=60, args=()):
            # After the cell's own `begin;` — so the mutation is rolled back with the cell, always.
            idx = sql.find("begin;")
            if idx >= 0:
                cut = idx + len("begin;")
                sql = sql[:cut] + "\n" + ddl + "\n" + sql[cut:]
            return original(sql, timeout=timeout, args=args)
        runner.psql_script = patched
    try:
        ran = 0
        for c in cells:
            # THIS DISPATCH IS THE RUNNER'S, DUPLICATED — and the duplication bit immediately. When the birth
            # lane landed, its `from: "(insert)"` branch was added to the runner's own dispatch in main() and
            # NOT here, so 22 birth cells were executed by the UPDATE path: `update ... where` against a row
            # that does not exist yet returned rows=0, which the transition oracle reads as REFUSED. A
            # legitimate `born as broadcasting` cell therefore failed on the UNMUTATED guard, the baseline
            # went red, and the whole request guard was skipped — dropping absolute kills 41 -> 22 while the
            # percentage still read 100%. Exactly the "fix EVERY path, not just the walked one" class
            # ([[feedback_fix_every_path_that_mutates_not_just_the_walked_one]]).
            #
            # Worth noting what caught it: not this run's green percentage, but the `killed` ratchet added an
            # hour earlier, which FAILED on 41 -> 22 precisely because a score-only ratchet cannot see teeth
            # lost behind an unchanged 100%.
            if isinstance(c.get("probe"), dict):
                ok, detail = runner.run_probe(c)
            elif c["transition"].get("from") == "(insert)":
                ok, detail = runner.run_birth_cell(c)
            elif c["transition"].get("from") == "*":
                ok, detail = runner.run_deny_cell(c)
            else:
                ok, detail = runner.run_cell(c, False, legal)
            if ok is None:
                continue
            ran += 1
            if not ok:
                # A cell that failed because the HARNESS broke the SQL is not a detection. Injecting a
                # malformed CREATE once turned every positive cell into a "kill" and produced a fabricated
                # 42/42, so a genuine syntax fault is refused loudly instead of counted.
                #
                # But NOT every "the probe produced nothing" is a harness fault, and the distinction matters:
                # a mutant can be strong enough to break the probe's own FIXTURE (e.g. removing the no-JWT
                # backend branch makes a service-role INSERT get judged as a raw client write, so the setup
                # is refused before any assertion runs). That IS a kill — the suite failed — but it is a
                # WEAKER kill than an assertion objecting to product behaviour, so it is labelled rather
                # than blended in.
                blob = str(detail)
                if "syntax error" in blob:
                    raise RuntimeError(
                        f"harness fault, not a detection: cell {c['id']} failed with {blob[:90]!r}. The "
                        f"injected mutation did not compile, so this mutant was never shown to the bank.")
                via = "fixture" if "NO RESULT lines" in blob else "assertion"
                return ran, (c["id"], detail, via)
            # a passing cell under a mutant means it did NOT notice; keep going
        return ran, None
    finally:
        runner.psql_script = original


def score_all(verbose=False):
    runner = load_runner()
    if runner.psql_script("select 1;")[0] is None:
        return None
    with open(BANK, encoding="utf-8") as f:
        bank = json.load(f)
    legal = runner.legal_origins(bank)

    results = {}
    for guard, table in GUARDS.items():
        fdef = functiondef(guard)
        if not fdef:
            results[guard] = {"error": "guard not found in this database"}
            continue
        cells = cells_for(bank, runner, table)

        # BASELINE FIRST. If a cell already fails on the UNMUTATED guard, every mutant would look "killed"
        # by that same pre-existing failure and the score would be a lie.
        n_base, base_fail = run_cells(runner, cells, legal)
        if base_fail:
            results[guard] = {"error": f"baseline already RED on {base_fail[0]} ({base_fail[1]}) — "
                                      f"fix the lane before scoring"}
            continue

        mutants = make_mutants(guard, fdef)
        killed, survived, malformed, excluded, stale = [], [], [], [], []
        for op, why, mutated in mutants:
            # Does the mutant even compile? A malformed mutation is an operator bug, not a bank gap.
            probe = psql("begin;\n" + mutated + "\nrollback;")
            if probe is None:
                malformed.append((op, why))
                continue
            n, objection = run_cells(runner, cells, legal, injected_ddl=mutated)
            reason = EXCLUDED.get((guard, op))
            if reason:
                # EXCLUDED MUTANTS ARE STILL RUN. Skipping them would make the exclusion list a trapdoor:
                # anything inconvenient could be declared unreachable and would then never be tested again,
                # which is precisely how a skipped partition reads as a covered one
                # ([[feedback_a_skipped_partition_reads_as_a_covered_one]]). Running it keeps the claim
                # falsifiable — if a cell ever DOES object, the exclusion was wrong and the tool says so
                # instead of silently pocketing the kill.
                (stale if objection else excluded).append((op, why, reason))
            elif objection:
                killed.append((op, why, objection[0], objection[2] if len(objection) > 2 else "assertion"))
            else:
                survived.append((op, why, n))
            if verbose:
                mark = f"{GREEN}killed{RST}" if objection else f"{RED}SURVIVED{RST}"
                print(f"    {mark:<20} {op:<28} {DIM}{why[:66]}{RST}")

        denom = len(killed) + len(survived)
        results[guard] = {
            "cells": len(cells), "baseline_ran": n_base,
            "killed": killed, "survived": survived, "malformed": malformed,
            "excluded": excluded, "stale": stale,
            # Kept so the leak check at the end can compare byte-for-byte against the pre-mutation truth
            # rather than guessing at a mutation's text signature.
            "fdef": fdef,
            "score": round(100.0 * len(killed) / denom, 1) if denom else None,
        }
    return results


def selftest():
    """Prove the harness measures what it claims: a WEAKENED cell set must score LOWER than the full one.

    Without this the tool could report 100% because its operators are toothless rather than because the bank
    is strong — the same false-green shape it exists to detect.
    """
    print("  selftest: a weakened cell set must score BELOW the full one")
    runner = load_runner()
    if runner.psql_script("select 1;")[0] is None:
        print(f"  {YEL}SKIP{RST} — docker/psql unavailable")
        return 0
    with open(BANK, encoding="utf-8") as f:
        bank = json.load(f)
    legal = runner.legal_origins(bank)
    guard, table = "guard_service_request_status", "service_requests"
    fdef = functiondef(guard)
    if not fdef:
        print(f"  {YEL}SKIP{RST} — {guard} absent")
        return 0
    mutants = make_mutants(guard, fdef)
    full = cells_for(bank, runner, table)
    # `full[:1]` is NOT a weak set — after the ordering change the first cell is an AUTHORED PROBE, which
    # asserts a whole scenario (self-deal blocked AND moderation works AND the ledger read back) and so
    # kills nearly everything on its own. The first version of this self-test used it, saw 9 == 9, and
    # correctly failed: a "weak" set that is really the strongest single cell measures nothing.
    #
    # A genuinely weak set is ONE DERIVED cell — a single UPDATE with one expectation.
    derived_only = [c for c in full if not isinstance(c.get("probe"), dict)]
    one_derived = derived_only[-1:] or full[:1]      # the last is a negative: the weakest single assertion

    def run(cellset):
        k = 0
        for op, why, mutated in mutants:
            if psql("begin;\n" + mutated + "\nrollback;") is None:
                continue
            _, obj = run_cells(runner, cellset, legal, injected_ddl=mutated)
            if obj:
                k += 1
        return k

    k_full, k_derived, k_one = run(full), run(derived_only), run(one_derived)
    print(f"    full set        ({len(full):>3} cells) killed {k_full}")
    print(f"    derived only    ({len(derived_only):>3} cells) killed {k_derived}   "
          f"{DIM}(authored probes removed){RST}")
    print(f"    one derived cell({len(one_derived):>3} cell ) killed {k_one}")

    if k_one >= k_full:
        print(f"  {RED}FAIL{RST} — a single derived cell scored as well as the whole lane, so this harness "
              f"is not measuring the CELLS. Its operators are being killed by the FIXTURE, not by any "
              f"assertion — the mutation score would then be a property of the probe scaffolding.")
        return 1

    # Not a failure, but the number worth knowing: how much of our teeth rests on a handful of authored
    # probes rather than the derived grid. If removing them drops the kill count, the grid alone is thinner
    # than the headline score suggests, and THAT is the punch list for P3.
    gap = k_full - k_derived
    print(f"  {GREEN}PASS{RST} — the score tracks cell-set strength ({k_one} -> {k_full} as cells are "
          f"added), so it measures assertions, not scaffolding.")
    if gap > 0:
        print(f"  {YEL}note{RST}  {gap} of {k_full} mutants are killed ONLY by authored probes — the "
              f"derived grid alone would miss them.")
    else:
        print(f"  {DIM}note: the derived grid alone kills as many as the full set, so the teeth are not "
              f"resting on a few authored probes.{RST}")
    return 0


def main(argv):
    if "--selftest" in argv:
        return selftest()
    verbose = "--verbose" in argv
    print(f"{BOLD}Guard mutation score{RST} — would the bank NOTICE if a guard behaved differently?")
    results = score_all(verbose)
    if results is None:
        print(f"  {YEL}SKIP{RST} — docker/psql unavailable; nothing asserted.")
        return 0

    total_k = total_s = 0
    for guard, r in results.items():
        if r.get("error"):
            print(f"  {YEL}SKIP{RST}  {guard}: {r['error']}")
            continue
        k, s, mal = len(r["killed"]), len(r["survived"]), len(r["malformed"])
        total_k += k
        total_s += s
        col = GREEN if s == 0 else YEL
        print(f"  {col}{str(r['score']) + '%':>6}{RST}  {guard:<34} "
              f"{DIM}{k} killed · {s} survived · {r['cells']} cells{RST}")
        via_fixture = [k for k in r["killed"] if len(k) > 3 and k[3] == "fixture"]
        if via_fixture:
            print(f"          {DIM}{len(via_fixture)} of {k} killed via a broken FIXTURE rather than an "
                  f"assertion ({', '.join(x[0] for x in via_fixture[:3])}) - a real kill, weaker "
                  f"evidence{RST}")
        for op, why, _n in r["survived"]:
            print(f"          {RED}SURVIVED{RST} {op}: {why}")
        for op, why in r["malformed"]:
            print(f"          {DIM}malformed (operator bug, not a bank gap): {op}{RST}")
        # Printed every run, never folded into the %: an exclusion the reader cannot see is an exclusion
        # nobody can challenge.
        for op, _why, reason in r.get("excluded", []):
            print(f"          {DIM}excluded from the denominator — {op}: {reason[:150]}{RST}")
        for op, _why, _reason in r.get("stale", []):
            print(f"          {RED}STALE EXCLUSION{RST} {op}: a cell DID object, so this mutant is "
                  f"observable after all — delete it from EXCLUDED and let it score.")

    denom = total_k + total_s
    overall = round(100.0 * total_k / denom, 1) if denom else 0.0
    print(f"\n  platform mutation score: {BOLD}{overall}%{RST}  ({total_k} killed / {denom} viable mutants)")

    # No mutated function may survive the run. The injection is inside each cell's transaction, so this
    # should be structurally impossible - assert it anyway, because "should be impossible" is what every
    # silent failure this arc found had in common.
    #
    # THIS CHECK WAS ITSELF FALSE-GREEN. It used to grep prosrc for `v_is_party := false or`, the literal text
    # of the FIRST draft of the is_party_false operator. Correcting that operator left the detector hunting a
    # string no mutation produces any more, so it would have reported "0 mutated guards persist" while one
    # was installed - a safety check that silently stopped checking, which is the exact class this arc keeps
    # finding ([[feedback_teach_the_gate_not_bend_the_code]] in reverse: the gate drifted, not the code).
    #
    # Now it compares each guard's CURRENT definition against the one captured before any mutation ran. That
    # is exact, and it cannot rot when the operator table changes, because it knows nothing about operators.
    changed = [g for g, r in results.items()
               if r.get("fdef") and functiondef(g) != r["fdef"]]
    if changed:
        print(f"  {RED}FAIL{RST} — a MUTATED guard is still installed ({', '.join(changed)}). Restore from "
              f"migrations now: `supabase db reset` or re-apply 20260730000003.")
        return 1
    print(f"  {DIM}verified: 0 mutated guards persist — each guard's definition is byte-identical to the one "
          f"captured before the first mutation ran{RST}")

    # A stale exclusion is a false claim in the report, so it fails the gate rather than printing a note. It
    # also cannot be reached by accident: it means a cell now objects to a mutant the tool told the reader
    # nothing could observe, which is good news that must be banked by deleting the exclusion.
    if any(r.get("stale") for r in results.values()):
        print(f"  {RED}FAIL{RST} — the exclusion list makes a claim the run disproved (above). An excluded "
              f"mutant that a cell kills must be scored, not excluded.")
        return 1

    # ── EVIDENCE QUALITY, ratcheted separately from the score ───────────────────────────────────────────
    # The score alone could not have caught this tool's own fabricated 100%: the broken injection scored
    # exactly 100.0%, byte-identical to the honest 100.0% that replaced it, so a score-only ratchet saw
    # nothing. What DID differ is HOW the mutants died. When the injection was swallowing each cell's next
    # statement, every kill came from a cell whose FIXTURE errored rather than from an assertion that
    # objected - and the tool already labels those. So the count of fixture-kills is ratcheted too: it may
    # fall, never rise. A broken injection makes it spike to the full mutant count, which now FAILS instead
    # of printing a triumphant 100%.
    fixture_kills = sum(1 for r in results.values() if not r.get("error")
                        for k in r["killed"] if len(k) > 3 and k[3] == "fixture")

    def write_baseline():
        with open(BASELINE, "w", encoding="utf-8") as f:
            json.dump({"score": overall, "viable": denom, "killed": total_k,
                       "fixture_kills": fixture_kills,
                       "_doc": "forward-only, on THREE axes. `killed` may never fall - that is the absolute "
                               "teeth count. `score` may only fall when `viable` GREW (new operators asked "
                               "new questions); at an unchanged vocabulary it may never fall. "
                               "`fixture_kills` may only fall: a kill via an errored fixture is weaker "
                               "evidence than a kill via an assertion, and a spike in it is the signature "
                               "of a broken injection (which once produced a fabricated 100% here)."},
                      f, indent=2)

    base, base_fx, base_viable, base_killed = 0.0, None, None, None
    if os.path.exists(BASELINE):
        try:
            saved = json.load(open(BASELINE, encoding="utf-8"))
            base = float(saved.get("score", 0.0))
            base_fx = saved.get("fixture_kills")
            base_viable = saved.get("viable")
            base_killed = saved.get("killed")
        except Exception:
            base = 0.0
    if "--update-baseline" in argv or not os.path.exists(BASELINE):
        write_baseline()
        print(f"  {DIM}baseline set to {overall}% ({fixture_kills} fixture-kills){RST}")
        return 0

    # ADDING AN OPERATOR LEGITIMATELY LOWERS THE SCORE, and a ratchet that cannot tell that from a real
    # regression punishes the one move that makes the score worth anything. This platform already treats a
    # GROWN denominator as progress everywhere else (a new guarded transition grows the transition board's
    # denominator by itself), so the same rule applies here: when `viable` rises, the score is measured
    # against a harder question set and may dip. What may NEVER fall is the absolute number of faults the
    # bank catches - so `killed` is the forward-only axis, and `score` is forward-only only at an unchanged
    # vocabulary. Without this split I would have been pushed to either drop the four new money-path
    # operators or fake the baseline, which is the ratchet-that-turns-both-ways trap
    # ([[feedback_a_ratchet_that_turns_both_ways]], [[feedback_short_denominator_is_a_false_100]]).
    grew = base_viable is not None and denom > base_viable
    if base_killed is not None and total_k < base_killed:
        print(f"  {RED}FAIL{RST} — the bank now catches FEWER faults: {base_killed} -> {total_k} killed. "
              f"That is a real regression regardless of the percentage.")
        return 1
    if overall < base and not grew:
        print(f"  {RED}FAIL{RST} — mutation score REGRESSED {base}% -> {overall}% at an unchanged operator "
              f"vocabulary ({denom} viable): a fault the bank used to catch now slips through.")
        return 1
    if overall < base and grew:
        was_k = base_killed if base_killed is not None else "?"
        print(f"  {YEL}note{RST}  score dipped {base}% -> {overall}% because the operator vocabulary GREW "
              f"({base_viable} -> {denom} viable) while kills went {was_k} -> {total_k}. New questions "
              f"asked, not teeth lost — each survivor above is a punch-list item.")
        write_baseline()
        return 0
    if base_fx is not None and fixture_kills > base_fx:
        print(f"  {RED}FAIL{RST} — evidence QUALITY regressed: kills via an errored fixture went "
              f"{base_fx} -> {fixture_kills} while the score held at {overall}%. A mutant that dies because "
              f"a cell could not run is not a mutant the bank NOTICED. Check the injection before trusting "
              f"this score — that is exactly how the first 100% here was fabricated.")
        return 1
    if overall > base or (base_fx is not None and fixture_kills < base_fx):
        write_baseline()
        moved = f"{base}% -> {overall}%" if overall > base else f"fixture-kills {base_fx} -> {fixture_kills}"
        print(f"  {GREEN}PASS{RST} — baseline ratcheted ({moved})")
        return 0
    # PERSIST WHENEVER THE BASELINE IS STALE OR INCOMPLETE, not only when the headline score moves. Twice in
    # one session a newly-added ratchet axis sat unseeded because the steady-state path (score == base) never
    # wrote the file - so `killed` stayed absent and `viable` stayed at 37 while the real vocabulary was 41,
    # leaving a gate that looked implemented and checked nothing. Any tracked field being missing or
    # out-of-date is itself a reason to write.
    if base_fx is None or base_killed is None or denom != base_viable or total_k != base_killed:
        seeded = [n for n, v in (("fixture_kills", base_fx), ("killed", base_killed)) if v is None]
        write_baseline()
        detail = f"seeded {', '.join(seeded)}; " if seeded else ""
        print(f"  {GREEN}PASS{RST} — holds at the {base}% baseline; {detail}recorded "
              f"{total_k} killed of {denom} viable, {fixture_kills} fixture-kills "
              f"(was {base_killed} of {base_viable})")
        return 0
    print(f"  {GREEN}PASS{RST} — holds at the {base}% baseline ({total_k}/{denom} killed, "
          f"{fixture_kills} fixture-kills, floor {base_fx})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
