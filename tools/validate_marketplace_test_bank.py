#!/usr/bin/env python3
"""validate_marketplace_test_bank.py — Runner B, the SQL lane of the marketplace test bank.

WHAT IT PROVES, AND WHY THIS LANE EXISTS AT ALL. Deriving the bank's denominator from the guard
functions exposed an asymmetry: of 20 authorised transitions, only 4 had any gate — and every existing
gate encodes "this must not happen", because each was written after a security finding. **Nothing
asserted "this must still work."** That is how a guard tightened one notch too far ships green (this
same platform watched pm_assets creation become supervisor-only and two gates redden for the old
permission, not a real break). This lane closes the positive direction.

WHY SQL AND NOT A BROWSER. A transition's legality is a database fact. Google's flake study is blunt
about UI tests being the most flake-prone, and flakiness masks real bugs; Fowler's pyramid says the UI
layer should be the smallest. Proving `accepted -> en_route` through a browser would buy nothing and
cost determinism. Every check here runs inside `begin; … rollback;` — self-minted probe identities,
zero pollution, no dependence on seeded state.

FIXTURES ARE SELF-MINTED (the pattern proven by validate_service_dispatch_isolation): a borrowed seeded
identity is never clean, because `my_service_provider_ids()` surfaces hive providers to their MEMBERS
and a member-uid silently picks a pre-existing verified provider over the probe's. Fresh uids own
nothing by construction.

  positive cell  the authorised actor CAN fire the transition   -> expect 1 row updated
  negative cell  every other actor is refused                   -> expect an exception OR 0 rows
                 (the guard RAISES; RLS would yield 0 rows — both are a refusal, neither is a pass)

Usage:  python tools/validate_marketplace_test_bank.py [--selftest] [--verbose]
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, "marketplace_test_bank.json")
DB = "supabase_db_workhive"
GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

# Probe identities: C = client/owner, P = the matched provider, X = an unrelated member,
# A = a real platform admin who is a party to NOTHING.
C = "d1aaaaaa-0000-4000-8000-000000000001"
P = "d1aaaaaa-0000-4000-8000-000000000002"
X = "d1aaaaaa-0000-4000-8000-000000000003"
A = "d1aaaaaa-0000-4000-8000-000000000005"
LOC = "'POINT(120.5960 16.4023)'::extensions.geography"


def psql_script(sql: str, timeout: int = 60, args: tuple = ()):
    """`encoding='utf-8'` is not cosmetic: without it Python encodes stdin with the Windows locale
    codepage, and a probe whose comments carry a box-drawing rule raises UnicodeEncodeError — which
    surfaces as the runner's generic "docker/psql unavailable" SKIP. A probe that silently never ran
    must never look like an environment problem."""
    try:
        r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres",
                            *args],
                           input=sql, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
    except Exception as e:
        return None, str(e)
    return (r.stdout or ""), (r.stderr or "")


def mint():
    """service-role preamble — runs BEFORE any `set local role`, rolled back with the check.

    ALSO FUNDS THE PROBE SELLER'S CREDIT WALLET, because publishing now costs working capital. The credit
    economy (migs 20260803000005+) makes a listing hold 10% of its price in reserved credits, so the
    `any -> published as admin-or-system` cell started FAILING against a freshly-minted seller who has
    never held a credit — and the cell is about AUTHORITY, not solvency. An admin may still publish; the
    seller must still be able to cover the reservation. Without this the bank silently stopped testing
    what it says it tests and started reporting a legitimate economic precondition as an authority
    regression ([[feedback_gates_lock_refusal_not_permission]]).

    auth.uid() is NULL here (no JWT yet), which the ledger guards treat as a vetted backend write — the
    same exemption every seeder uses. Rolled back with the rest of the probe.
    """
    vals = ",".join(f"('{u}','tb-probe-{i}@gate.local')" for i, u in enumerate((C, P, X, A)))
    return (
        f"insert into auth.users(id, email) values {vals};\n"
        # generous relative to any fixture price here. Fixtures list at PHP600 (-> PHP60 held): they must
        # clear the PHP500 minimum listing price (mig 36), which refuses publication below it.
        f"insert into public.service_credit_ledger"
        f"(account_type, account_id, entry_type, amount, ref_kind, note) values "
        f"('consumer','{C}','topup',1000,'probe','tb-probe reservation float');\n")


def make_admin(uid: str, hive_pick: str = "order by id limit 1"):
    """Make `uid` a REAL platform admin, resolved the way the product resolves it.

    `is_marketplace_admin()` reads `marketplace_platform_admins.worker_name IN auth_worker_names()`, and
    `auth_worker_names()` maps auth.uid() through hive_members / marketplace_sellers. So an admin cannot
    be faked with a flag — the identity has to be built through both hops or the guard sees a stranger.

    This is why the `admin` partition went 18 cells unexecuted: `actor_uid('admin')` had no uid to
    return, the runner skipped every one, and the bank's own derived assertion *an admin must be refused
    this transition* was never run. The exploit that assertion describes was live for five weeks
    (mig 20260730000003). A partition with no probe identity is not a covered partition — it is a
    silent one, exactly like `anon` was.
    """
    return (f"insert into public.hive_members(hive_id, worker_name, role, status, auth_uid) values "
            f"((select id from public.hives {hive_pick}),'TB Probe Admin','worker','active','{uid}');\n"
            f"insert into public.marketplace_platform_admins(worker_name, granted_by) values "
            f"('TB Probe Admin','tb-probe');\n")


def jwt(uid: str):
    return ("set local role authenticated;\n"
            f"set local request.jwt.claims = '{{\"sub\":\"{uid}\",\"role\":\"authenticated\"}}';\n")


def actor_uid(authority: str):
    """Map the bank's authority partition onto a probe identity.

    `anon` returns None DELIBERATELY and is handled separately: it is not an identity, it is the absence
    of one, so it needs the `anon` ROLE with no JWT rather than a minted uid. It used to be skipped
    entirely, which meant the partition with the largest blast radius - an unauthenticated stranger on
    the public internet - was ENUMERATED as 18 obligations and never once executed.
    """
    return {"owner": C, "counterparty": P, "member": X, "cross-tenant": X,
            "anon": None, "admin": A}.get(authority)


# `refused-or-idempotent` is satisfied by the state NOT MOVING, which is not the same claim as "refused".
# Printing it as "must be refused" would describe a passing cell inaccurately — and a label is a claim
# ([[feedback_metric_label_is_a_claim_add_the_missing_half]]).
EXPECT_LABEL = {"allowed": "must work", "refused": "must be refused"}


def has_identity(authority: str) -> bool:
    """Can this runner mount an identity for the partition at all?

    Three answers, and only the third is a real "no":
      · a minted uid                       -> owner / counterparty / member / cross-tenant / admin
      · the ABSENCE of one (`role anon`)   -> anon
      · the admin identity, reused         -> admin-or-system (the guard's own branch is
                                              `is_marketplace_admin() OR <a GUC system write>`, and the
                                              admin half is the half a user can hold, so that is the half
                                              worth probing)
    """
    return authority in ("anon", "admin-or-system") or actor_uid(authority) is not None


ACTIVE = ("accepted", "en_route", "on_site", "in_progress")

# The happy-path chain, in order. Only used to derive the OUT-OF-ORDER sneak path: "skip a state" has no
# meaning without knowing which state comes before which, and hardcoding a list of illegal pairs would be
# me deciding the answer instead of deriving it.
CHAIN = ("requested", "broadcasting", "accepted", "en_route", "on_site", "in_progress", "completed",
         "settled")


def legal_origins(bank):
    """-> {(authority, to): {every `from` the guard authorises for that actor}}, read from the BANK.

    Derived, never hardcoded: the bank's own `expect: allowed` cells ARE the guard's authorised set, so
    this map updates itself when a migration changes a transition.
    """
    m: dict[tuple, set] = {}
    for c in bank["tests"]:
        t = c.get("transition")
        if isinstance(t, dict) and c.get("expect") == "allowed" and t.get("table") == "service_requests":
            m.setdefault((c.get("authority"), t.get("to")), set()).add(t.get("from"))
    return m


def out_of_order_origin(authority: str, to_state: str, legal: dict):
    """A state to plant from which reaching `to` is ILLEGAL for this actor — the real out-of-order probe.

    My first cut planted "two states earlier in the chain" and FAILED FOUR CELLS on correct behaviour.
    `cancelled_by_client` is authorised from FIVE states (`requested`, `broadcasting`, `accepted`,
    `en_route`, `on_site`), so an earlier chain position is very often ANOTHER LEGAL ORIGIN — the probe
    was demanding a refusal the guard rightly does not give, i.e. the bank accusing the product. Exactly
    the trap the derived-negatives code already carries a comment about, walked into from the other side.
    So the origin cannot be positional. It has to be *any state the guard does not authorise `to` from*,
    which is only knowable from the authorised set itself.

    First match in CHAIN order, for determinism. Skips `to` itself (a same-status update is not a
    sequence violation) and returns None if every state is authorised — then the cell is genuinely
    inexpressible and says so by name.
    """
    allowed = legal.get((authority, to_state), set())
    for s in CHAIN:
        if s != to_state and s not in allowed:
            return s
    return None


def build_sql(from_state: str, to_state: str, as_uid: str | None):
    """A request already sitting in `from_state`, matched to P, owned by C — then one UPDATE.

    The row is planted with the SERVICE ROLE (no JWT yet): the guard's own first branch allows system
    writes, and a new request may otherwise only be born 'requested'/'broadcasting', so walking the
    whole chain to reach 'on_site' would test the walk instead of the transition under scrutiny.

    THE PROVIDER'S AVAILABILITY MUST MATCH THE JOB STATE, or the fixture tests an unreachable world.
    `accept_service_request` sets the provider to 'on_job' as part of accepting (under the
    `workhive.service_system_write` bypass), so a request in an ACTIVE state always has an on_job
    provider in production. Planting 'online' instead made `sync_provider_availability` attempt the
    flip, which `guard_service_provider_writes` correctly refuses for a user-initiated write — and
    that looked exactly like a product bug until the accept RPC was read
    ([[feedback_verify_the_instrument_before_the_page]]).
    """
    avail = "on_job" if from_state in ACTIVE else "online"
    # The admin fixture makes A a real platform admin who is a party to NOTHING: not the client, not the
    # matched provider, and not a member of a hive that owns the provider profile (the probe provider is
    # a `freelancer`, so the hive branch of v_is_matched_provider cannot fire). That is the assertion
    # these cells actually make — *a non-party admin cannot fire this transition* — and it is true for a
    # reason worth naming: `service_requests_party_update` RLS has NO admin clause, so the row is
    # filtered away before the guard is consulted. The STRONGER case, a PARTY-admin, is not expressible
    # as a derived one-UPDATE cell and is banked separately as the authored
    # TB-I2-admin-bypass-only-for-non-parties probe. Neither cell substitutes for the other.
    return (
        "begin;\n" + mint() + (make_admin(A) if as_uid == A else "") +
        "insert into public.service_providers(id, provider_type, auth_uid, display_name, categories, "
        "base_location, availability) values "
        f"('d1bbbbbb-0000-4000-8000-000000000001','freelancer','{P}','TB Probe Prov','{{Plumbing}}',{LOC},'{avail}');\n"
        "insert into public.service_requests(id, client_auth_uid, mode, custom_scope, location, status, "
        "matched_provider_id) values "
        f"('d1cccccc-0000-4000-8000-000000000001','{C}','instant','tb probe',{LOC},'{from_state}',"
        "'d1bbbbbb-0000-4000-8000-000000000001');\n"
        # RELEASE NOW REQUIRES A PAYMENT RECORD (mig 20260731000015). `guard_settle_requires_payment`
        # refuses `-> settled` unless the job carries what was actually paid, so without this the
        # completed->settled cell reports "rows=0 REFUSED" and reads as a broken transition when the
        # transition is fine and the PRECONDITION is new. Seeded only for the settled target, so no other
        # cell's setup changes.
        + ("insert into public.service_payments(request_id, amount_paid, method, confirmed_by) values "
           f"('d1cccccc-0000-4000-8000-000000000001', 2000, 'cash', '{C}');\n"
           if to_state == "settled" else "")
        # `as_uid=None` means the ANON partition: not a different identity, the ABSENCE of one. It needs
        # the `anon` role with no JWT claims at all, so nothing about the row can authorise the caller.
        # This partition was enumerated as 18 obligations and skipped for want of a uid to mint - the
        # partition with the largest blast radius (an unauthenticated stranger) was the one never run.
        + ("set local role anon;\n" if as_uid is None else jwt(as_uid)) +
        f"update public.service_requests set status='{to_state}' "
        "where id='d1cccccc-0000-4000-8000-000000000001';\n"
        "rollback;\n")


WORKER_NAME = {C: "TB Probe Owner", P: "TB Probe Counter", X: "TB Probe Member", A: "TB Probe Admin"}


def name_the_actors():
    """Every probe identity needs a worker_name, because the three DENY-shape machines resolve identity
    through names, not uids: `auth_worker_names()` maps auth.uid() -> hive_members.worker_name, and
    listings/orders carry `seller_name` / `buyer_name` as free text
    ([[feedback_free_text_identity_is_a_claim]] — the name is the claim, this mapping is the proof)."""
    rows = ",".join(f"((select id from public.hives order by id limit 1),'{n}','worker','active','{u}')"
                    for u, n in WORKER_NAME.items())
    # AND A REAL marketplace_sellers ROW for the seller identity, because a listing's seller is one.
    # Without it the fixture planted listings under a name that no seller record backed, which was
    # invisible until the credit economy landed: guard_listing_requires_reservation calls
    # seller_credit_balance(seller_name), which resolves the wallet through marketplace_sellers.auth_uid
    # and got NULL -- so the seller had a balance of zero no matter how the probe was funded, and the
    # authorised `any -> published` transition began failing for a reason that had nothing to do with
    # authority. Same shape as the wallet bug earlier in this arc, where the balance joined on
    # display_name and matched nobody: a wallet is keyed to a PERSON, so the person has to exist.
    sellers = ",".join(
        f"('{WORKER_NAME[u]}','{u}',(select id from public.hives order by id limit 1))"
        for u in (C, P))
    return ("insert into public.hive_members(hive_id, worker_name, role, status, auth_uid) values "
            f"{rows};\n"
            "insert into public.marketplace_sellers(worker_name, auth_uid, hive_id) values "
            f"{sellers};\n"
            "insert into public.marketplace_platform_admins(worker_name, granted_by) values "
            f"('{WORKER_NAME[A]}','tb-probe');\n")


# The three deny-shape machines: `from` is '*' because the guard names only the FORBIDDEN target, so the
# obligation is "who may arrive at this state", not "from where".
DENY_FIXTURES = {
    "marketplace_listings": {
        "plant": lambda st: (
            "insert into public.marketplace_listings"
            "(id, hive_id, seller_name, section, title, category, price, status) values "
            "('d1ffffff-0000-4000-8000-0000000000f1',"
            "(select id from public.hives order by id limit 1),"
            f"'{WORKER_NAME[C]}','parts','TB deny probe','Tools',600,'{st}');\n"),
        "pre": "draft", "id": "d1ffffff-0000-4000-8000-0000000000f1"},
    "marketplace_orders": {
        "plant": lambda st: (
            "insert into public.marketplace_orders"
            "(id, hive_id, buyer_name, seller_name, price, status) values "
            "('d1eeeeee-0000-4000-8000-0000000000f1',"
            "(select id from public.hives order by id limit 1),"
            f"'{WORKER_NAME[P]}','{WORKER_NAME[C]}',100,'{st}');\n"),
        "pre": "buyer_confirmed", "id": "d1eeeeee-0000-4000-8000-0000000000f1"},
    "service_credit_topups": {
        "plant": lambda st: (
            "insert into public.service_providers(id, provider_type, auth_uid, display_name, categories,"
            " base_location, availability) values "
            "('d1bbbbbb-0000-4000-8000-0000000000f1','freelancer',"
            f"'{P}','TB deny prov','{{Plumbing}}',{LOC},'online');\n"
            "insert into public.service_credit_topups"
            "(id, account_type, account_id, payer_auth_uid, amount, gcash_ref, status) values "
            "('d1aaaaab-0000-4000-8000-0000000000f1','provider',"
            "'d1bbbbbb-0000-4000-8000-0000000000f1',"
            f"'{P}',500,'900000000009','{st}');\n"),
        "pre": "pending_verification", "id": "d1aaaaab-0000-4000-8000-0000000000f1"},
}


def build_sql_deny(table: str, to_state: str, as_uid: str | None, plant_state: str):
    """A deny-shape cell: plant a row, become `as_uid`, attempt to arrive at `to_state`, read the row BACK.

    The read-back is not decoration. On a deny machine the guard blocks the TRANSITION into the forbidden
    state (`NEW.status='published' AND OLD.status IS DISTINCT FROM 'published'`), so re-firing at a row
    that is ALREADY there raises nothing and reports `UPDATE 1` — a row count alone would read that as the
    guard having failed, when the state never moved. `FINAL=` is what distinguishes *refused*,
    *idempotent* and *actually changed it*.
    """
    f = DENY_FIXTURES[table]
    return (
        "begin;\n" + mint() + name_the_actors() + f["plant"](plant_state) +
        ("set local role anon;\n" if as_uid is None else jwt(as_uid)) +
        f"update public.{table} set status='{to_state}' where id='{f['id']}';\n"
        "reset role;\n"
        f"select 'FINAL='||status from public.{table} where id='{f['id']}';\n"
        # The status column is NOT the oracle on the money machine. `guard_service_topup_status` mints a
        # ledger credit inline when a top-up reaches `verified`, so what a re-fire really asks is *did it
        # mint AGAIN* — and a second credit is invisible in `status`, which reads `verified` either way
        # ([[feedback_records_that_outlive_the_action]]: check what the write LEFT BEHIND).
        + (f"select 'LEDGER='||count(*) from public.service_credit_ledger "
           f"where ref_kind='topup' and ref_id='{f['id']}';\n"
           if table == "service_credit_topups" else "") +
        "rollback;\n")


def run_deny_cell(cell, verbose=False):
    """-> (ok, detail) for a `from: '*'` cell on one of the three deny-shape machines."""
    t = cell["transition"]
    table, to = t["table"], t["to"]
    if table not in DENY_FIXTURES:
        return None, f"no deny fixture for {table}"
    uid = actor_uid(cell["authority"]) if cell["authority"] != "admin-or-system" else A
    if uid is None and cell["authority"] != "anon":
        return None, f"authority '{cell['authority']}' has no probe identity"

    # For the out-of-order variant the row is planted ALREADY in the target state, so "arriving" there is
    # a no-op and the honest expectation is *nothing moved*, not *an error was raised*.
    ooo = str(cell.get("kind", "")) == "sneak-path:out-of-order"
    plant = to if ooo else DENY_FIXTURES[table]["pre"]
    out, err = psql_script(build_sql_deny(table, to, uid, plant))
    if out is None:
        return None, "docker/psql unavailable"
    blob = out + err
    refused = ("Not allowed" in blob) or ("ERROR" in blob)
    m = re.search(r"UPDATE (\d+)", out)
    rows = int(m.group(1)) if m else 0
    fm = re.search(r"FINAL=([a-z_]+)", out)
    final = fm.group(1) if fm else None
    detail = f"rows={rows} refused={refused} final={final} planted={plant}"

    exp = cell["expect"]
    if exp == "allowed":
        return (rows == 1 and not refused and final == to), detail
    if exp == "refused":
        # a refusal is an exception, 0 rows, OR the state simply not having moved
        return (refused or rows == 0 or final != to), detail
    # refused-or-idempotent: either it was refused, or nothing about the state changed — AND, on the money
    # machine, the re-fire minted no second credit.
    lm = re.search(r"LEDGER=(\d+)", out)
    if lm is not None:
        detail += f" ledger={lm.group(1)}"
        if int(lm.group(1)) > 1:
            return False, detail + "  <- a re-fire MINTED AGAIN"
    return (refused or rows == 0 or final == plant), detail


# ── BIRTH lane: what state may a row be BORN in? ─────────────────────────────────────────────────────────
# Every other cell in this runner is an UPDATE, which is exactly why each guard's `TG_OP = 'INSERT'` branch
# went untested across 247 obligations - a transition-shaped runner cannot express "this row must not exist
# in this state to begin with". The guard mutation score found it mechanically (delete a birth rule, watch no
# cell object), and the consequences are one statement each: a top-up born `verified` MINTS CREDIT without
# entering the verification path, an order born `released` skips escrow.
#
# The caller is always an ORDINARY authenticated client filing their OWN row, so the only thing under test is
# the status. Identity is set to the caller deliberately: the attribution rules (`client_auth_uid must be the
# caller`, `payer_auth_uid must be the caller`, `buyer_name IN auth_worker_names()`) are ALSO enforced by RLS
# WITH CHECK, so a cell that violated them could not tell which layer refused
# ([[feedback_using_preempts_a_trigger_withcheck_does_not]] - and TB-BIRTH asserts that ordering separately).
BIRTH_FIXTURES = {
    "service_requests": {
        "pre": "",
        "id": "d1cccccc-0000-4000-8000-0000000000b1",
        "sql": lambda st, uid: (
            "insert into public.service_requests"
            "(id, client_auth_uid, mode, status, custom_scope) values "
            f"('d1cccccc-0000-4000-8000-0000000000b1','{uid}','instant','{st}','TB birth probe');\n"),
    },
    "service_credit_topups": {
        # The destination account is planted as postgres (the vetted backend path), so the INSERT under test
        # is the only client write in the transaction.
        "pre": ("insert into public.service_providers(id, provider_type, auth_uid, display_name, categories,"
                " base_location, availability) values "
                "('d1bbbbbb-0000-4000-8000-0000000000b1','freelancer',"
                f"'{P}','TB birth prov','{{Plumbing}}',{LOC},'online');\n"),
        "id": "d1aaaaab-0000-4000-8000-0000000000b1",
        "sql": lambda st, uid: (
            "insert into public.service_credit_topups"
            "(id, account_type, account_id, payer_auth_uid, amount, gcash_ref, status) values "
            "('d1aaaaab-0000-4000-8000-0000000000b1','provider','d1bbbbbb-0000-4000-8000-0000000000b1',"
            f"'{uid}',500,'900000000021','{st}');\n"),
    },
    "marketplace_orders": {
        "pre": "",
        "id": "d1eeeeee-0000-4000-8000-0000000000b1",
        "sql": lambda st, uid: (
            "insert into public.marketplace_orders"
            "(id, hive_id, buyer_name, seller_name, price, status) values "
            "('d1eeeeee-0000-4000-8000-0000000000b1',"
            "(select id from public.hives order by id limit 1),"
            f"'{WORKER_NAME[C]}','{WORKER_NAME[P]}',100,'{st}');\n"),
    },
    "marketplace_listings": {
        "pre": "",
        "id": "d1ffffff-0000-4000-8000-0000000000b1",
        "sql": lambda st, uid: (
            "insert into public.marketplace_listings"
            "(id, hive_id, seller_name, section, title, category, price, status) values "
            "('d1ffffff-0000-4000-8000-0000000000b1',"
            "(select id from public.hives order by id limit 1),"
            f"'{WORKER_NAME[C]}','parts','TB birth probe','Tools',600,'{st}');\n"),
    },
}


def build_sql_birth(table: str, to_state: str, as_uid: str):
    """Attempt to CREATE a row already in `to_state`, as an ordinary client, then read it BACK.

    `BORN=` is the oracle rather than the INSERT's own row count, for the same reason `FINAL=` is used on the
    deny lane: an INSERT that is refused mid-statement and one that never ran look different in psql output
    but identical in intent, and reading the table back answers the only question that matters — does the row
    exist in that state now?
    """
    f = BIRTH_FIXTURES[table]
    # THE INSERT IS WRAPPED IN A plpgsql EXCEPTION BLOCK, and the first version was not — which made every
    # REFUSAL unscoreable. A guard that raises aborts the transaction, so the `BORN=` read-back could not run
    # and returned "current transaction is aborted": 6 of 10 cases came back SKIP rather than PASS. Catching
    # the exception keeps the transaction alive so the read-back ALWAYS executes, which turns the oracle from
    # "did psql print an error" into "does the row exist in that state now" — the stronger question, and the
    # only one that separates a refusal from a silent RLS filter ([[feedback_zero_row_write_is_not_an_error]]).
    #
    # Caught by the executor's own "no BORN= read-back" SKIP branch rather than by a green run: a cell that
    # could not execute must never be scored as a refusal, which is precisely how a broken injection once
    # fabricated a 100% mutation score out of syntax failures.
    return (
        "begin;\n" + mint() + name_the_actors() + f["pre"] +
        jwt(as_uid) +
        "do $birth$\nbegin\n  " + f["sql"](to_state, as_uid).strip() +
        "\nexception when others then\n  raise notice 'REFUSED=%', sqlstate;\nend\n$birth$;\n"
        "reset role;\n"
        f"select 'BORN='||count(*) from public.{table} where id='{f['id']}' and status='{to_state}';\n"
        "rollback;\n")


def run_birth_cell(cell, verbose=False):
    """-> (ok, detail) for a `from: '(insert)'` cell."""
    t = cell["transition"]
    table, to = t["table"], t["to"]
    if table not in BIRTH_FIXTURES:
        return None, f"no birth fixture for {table}"
    uid = actor_uid(cell["authority"])
    if uid is None:
        return None, f"authority '{cell['authority']}' has no probe identity"

    out, err = psql_script(build_sql_birth(table, to, uid))
    if out is None:
        return None, "docker/psql unavailable"
    blob = out + err
    # `REFUSED=<sqlstate>` comes from the probe's own exception handler. It is CORROBORATION, never the
    # oracle — the row read-back below is, because a refusal and a silent RLS filter are indistinguishable
    # from an error string alone.
    #
    # And the sqlstate must not be over-read as a layer identifier, which is a trap this lane walked into
    # immediately: `marketplace_listings` born-as-`published` returns **42501**, which looks like RLS refusing
    # (the mapping used elsewhere in this file), yet `mkt_listings_insert` only checks `seller_name` and
    # `draft`/`sold` inserts by the same identity succeed. The guard itself raises
    # `USING ERRCODE = '42501'` by choice. An errcode is a message the AUTHOR selected, not evidence of which
    # layer produced it — it only distinguishes layers where the guards happen to use a different code, as the
    # service_requests guard does (`check_violation` throughout, which is what makes TB-BIRTH's attribution
    # assertion sound).
    refused = ("REFUSED=" in blob) or ("Not allowed" in blob) or ("ERROR" in blob)
    sm = re.search(r"REFUSED=(\w+)", blob)
    bm = re.search(r"BORN=(\d+)", out)
    if bm is None:
        # The read-back never ran, so the cell proved nothing. Reported as a SKIP with its cause rather
        # than scored - a cell that could not execute must never be counted as a refusal, which is the
        # error that once fabricated a 100% mutation score out of syntax failures.
        return None, f"no BORN= read-back ({blob.strip().splitlines()[-1][:80] if blob.strip() else 'empty'})"
    born = int(bm.group(1))
    detail = f"born={born} refused={refused}{' sqlstate=' + sm.group(1) if sm else ''} status={to}"
    if cell["expect"] == "allowed":
        return (born == 1 and not refused), detail
    return (born == 0), detail        # refused: the row must NOT exist in that state


def run_cell(cell, verbose=False, legal=None):
    """-> (ok, detail). A refusal is an exception OR 0 rows; a permission is exactly 1 row."""
    t = cell["transition"]
    if t["table"] != "service_requests" or t["from"] == "*":
        return None, "not a service_requests transition (other machines are deny-shape)"
    uid = actor_uid(cell["authority"])
    if uid is None and cell["authority"] != "anon":
        return None, f"authority '{cell['authority']}' has no probe identity in the SQL lane"

    origin = t["from"]
    if str(cell.get("kind", "")) == "sneak-path:out-of-order":
        # Same one-UPDATE shape, but planted TWO states earlier so reaching `to` skips the chain. The
        # guard authorises single steps from a named `old.status`, so a jump lands in the `not v_legal`
        # branch and must raise. This is the sneak path the runner used to exclude wholesale.
        origin = out_of_order_origin(cell["authority"], t["to"], legal or {})
        if origin is None:
            return None, (f"out-of-order is not expressible for {t['to']} as {cell['authority']}: "
                          f"the guard authorises it from EVERY state, so no illegal origin exists")
    out, err = psql_script(build_sql(origin, t["to"], uid))
    if out is None:
        return None, "docker/psql unavailable"
    blob = out + err
    refused = ("Not allowed" in blob) or ("ERROR" in blob)
    m = re.search(r"UPDATE (\d+)", out)
    rows = int(m.group(1)) if m else 0
    if verbose:
        print(f"      {DIM}rows={rows} refused={refused}{RST}")

    if cell["expect"] == "allowed":
        return (rows == 1 and not refused), f"rows={rows}{' REFUSED' if refused else ''}"
    # refused / refused-or-idempotent
    return (refused or rows == 0), f"rows={rows} refused={refused}"


PROBES = os.path.join(ROOT, "tests", "bank_probes")


def run_probe(cell):
    """Execute an AUTHORED sql cell: a .sql file that emits `RESULT <key>=<value>` lines.

    Derived cells are one UPDATE each, so the runner can build them. An authored cell is a scenario —
    three identities watching one live location, five providers filtered down to one push recipient —
    and no generator describes it. Without this lane those cells were WALKED, not banked: I ran them by
    hand, wrote 'banked' into the JSON, and left behind exactly the artifact-free evidence this whole
    arc exists to replace (the J2 note that read 'W: done' beside 'round trip NOT yet walked').

    The probe owns its own begin/rollback and mints its own identities; the runner only diffs the
    RESULT lines against the cell's declared `expect`.
    """
    p = cell.get("probe") or {}
    path = os.path.join(PROBES, p.get("file", ""))
    if not p.get("file") or not os.path.exists(path):
        return None, f"probe file missing: {p.get('file')!r}"
    with open(path, encoding="utf-8") as f:
        sql = f.read()
    # -At: unaligned + tuples-only. Table formatting pads every value with a leading space, so the
    # RESULT lines parse to nothing and every assertion reads `got None` — a probe that ran perfectly
    # would be reported as a total failure.
    out, err = psql_script(sql, timeout=120, args=("-At",))
    if out is None:
        return None, f"could not execute the probe: {err[:110]}"
    # BOTH streams, and tolerate a NOTICE prefix. A probe that must survive a 42501 has to wrap each
    # read in a plpgsql exception block, and the only way to emit from inside one is RAISE NOTICE —
    # which psql writes to STDERR as "NOTICE:  RESULT k=v". Parsing stdout alone reported a
    # fully-passing probe as having emitted nothing at all.
    blob = (out + "\n" + (err or "")).replace("\r", "")
    got = dict(re.findall(r"^(?:NOTICE:\s*)?RESULT ([A-Za-z0-9_]+)=(.*?)\s*$", blob, re.M))
    if not got:
        first = next((l for l in (err or "").splitlines() if "ERROR" in l), "")
        return False, f"probe emitted NO RESULT lines{' — ' + first[:100] if first else ''}"
    bad = []
    for k, want in (p.get("expect") or {}).items():
        if got.get(k) != str(want):
            bad.append(f"{k}: want {want!r} got {got.get(k)!r}")
    if bad:
        return False, "; ".join(bad[:4])
    return True, f"{len(p.get('expect') or {})} assertions held"


def selftest():
    """Teeth: the runner must call a permission that lands PASS and a refusal that lands PASS —
    and must NOT call a silent 0-row update a success for a positive cell."""
    ok = True
    pos = {"transition": {"table": "service_requests", "from": "accepted", "to": "en_route"},
           "authority": "counterparty", "expect": "allowed"}
    neg = {"transition": {"table": "service_requests", "from": "accepted", "to": "en_route"},
           "authority": "member", "expect": "refused"}
    r1, d1 = run_cell(pos)
    r2, d2 = run_cell(neg)
    if r1 is None or r2 is None:
        print(f"  {YEL}SKIP{RST} selftest needs the local DB ({d1 or d2})")
        return 0
    if not r1:
        print(f"  {RED}FAIL{RST} the matched provider could NOT advance accepted->en_route ({d1})"); ok = False
    else:
        print(f"  {GREEN}PASS{RST} permission proven: matched provider advances accepted->en_route ({d1})")
    if not r2:
        print(f"  {RED}FAIL{RST} an unrelated member WAS allowed to advance the job ({d2})"); ok = False
    else:
        print(f"  {GREEN}PASS{RST} refusal proven: an unrelated member cannot advance it ({d2})")

    # ── BIRTH lane teeth, in BOTH directions ────────────────────────────────────────────────────────────
    # A one-directional check would pass on a lane that always reports "refused" — and this lane very nearly
    # was exactly that: its first cut could not score a refusal at all, because a raising guard aborts the
    # transaction and the `BORN=` read-back never ran (6 of 10 cases came back SKIP). So both directions are
    # asserted, and a legal birth must come back BORN.
    b_legal = {"transition": {"table": "service_credit_topups", "from": "(insert)",
                              "to": "pending_verification"}, "authority": "owner", "expect": "allowed"}
    b_illegal = {"transition": {"table": "service_credit_topups", "from": "(insert)", "to": "verified"},
                 "authority": "owner", "expect": "refused"}
    # The INVERTED pair: the same two writes with the expectations swapped must both FAIL, which is what
    # proves the oracle reads the row rather than echoing the expectation back.
    b_legal_inv = dict(b_legal, expect="refused")
    b_illegal_inv = dict(b_illegal, expect="allowed")
    r4, d4 = run_birth_cell(b_legal)
    r5, d5 = run_birth_cell(b_illegal)
    r6, _ = run_birth_cell(b_legal_inv)
    r7, _ = run_birth_cell(b_illegal_inv)
    if r4 is None or r5 is None:
        print(f"  {YEL}note{RST} birth-lane teeth skipped ({d4 or d5})")
    elif r4 and r5 and r6 is False and r7 is False:
        print(f"  {GREEN}PASS{RST} birth lane proven BOTH ways: a top-up may be born pending_verification "
              f"({d4}) and may NOT be born verified ({d5}); inverting either expectation FAILS")
    else:
        print(f"  {RED}FAIL{RST} birth lane does not discriminate — legal={r4} illegal={r5} "
              f"inverted(legal)={r6} inverted(illegal)={r7}. A lane that cannot fail proves nothing "
              f"about the guard's INSERT branch."); ok = False

    # The AUTHORED lane needs its own teeth, or a probe whose SQL silently stopped emitting RESULT
    # lines would read as "every assertion held" over an empty expectation set.
    real = os.path.join(PROBES, "TB-S5-edge-push-audience-selection.sql")
    if os.path.exists(real):
        liar = {"probe": {"file": "TB-S5-edge-push-audience-selection.sql",
                          "expect": {"offline_in_payload": "1"}}}   # deliberately wrong
        r3, d3 = run_probe(liar)
        # A FAIL is not enough. The first cut of this teeth-check went green while the probe was not
        # executing at all (`got None`) — a red for the wrong reason, which is how a lane that proves
        # nothing looks healthy. Demand that the probe RAN and that the observed value is the real one.
        bit_for_the_right_reason = (r3 is False and "got '0'" in d3)
        if r3 is None:
            print(f"  {YEL}SKIP{RST} authored-lane teeth ({d3})")
        elif not bit_for_the_right_reason:
            print(f"  {RED}FAIL{RST} authored-lane teeth did not bite on the real value ({r3}: {d3})"); ok = False
        else:
            print(f"  {GREEN}PASS{RST} authored-lane teeth: a wrong expectation FAILS against the "
                  f"OBSERVED value ({d3})")
        missing = {"probe": {"file": "no-such-probe.sql", "expect": {"x": "1"}}}
        if run_probe(missing)[0] is not False and run_probe(missing)[0] is not None:
            print(f"  {RED}FAIL{RST} a missing probe file was treated as a pass"); ok = False
        else:
            print(f"  {GREEN}PASS{RST} a missing probe file is never silently green")
    print(f"\n  SELFTEST: {GREEN + 'PASS' + RST if ok else RED + 'FAIL' + RST}")
    return 0 if ok else 1


def main():
    verbose = "--verbose" in sys.argv
    if "--selftest" in sys.argv:
        return selftest()
    if not os.path.exists(BANK):
        print("  SKIP: marketplace_test_bank.json not built — run tools/build_test_bank.py")
        return 0
    with open(BANK, encoding="utf-8") as f:
        bank = json.load(f)
    if psql_script("select 1;")[0] is None:
        print("  SKIP: docker/psql unavailable")
        return 0

    print("=" * 80)
    print(f"  {BOLD}Marketplace test bank — SQL lane (Runner B){RST}")
    print("=" * 80)

    # A `sql`-lane cell is not necessarily a TRANSITION cell: an authored cell (the realtime
    # publisher x watcher data-path proof) also runs at SQL altitude but has no from/to pair. Assuming
    # every sql cell carries `transition` crashed the whole lane the moment one was banked — use .get()
    # and let this runner claim only what it actually knows how to execute.
    runnable = [c for c in bank["tests"]
                if c.get("lane") == "sql" and c.get("status") != "covered"
                and isinstance(c.get("transition"), dict)
                and (c["transition"].get("table") == "service_requests"
                     or c["transition"].get("table") in DENY_FIXTURES)
                # `has_identity`, not `actor_uid(...) is not None`. The raw form dropped
                # `admin-or-system` here — BEFORE the loop, so it never even reached the skip reporter and
                # printed nothing at all. A filter that excludes is exactly as silent as a bare
                # `continue`, which is the whole lesson of this arc: 36 cells hid in the loop's None
                # branch, and 7 more were hiding one layer earlier, in the comprehension.
                and has_identity(c.get("authority"))
                # `out-of-order` is a plain one-UPDATE from an earlier state, so this runner CAN execute
                # it. The other three sneak paths are deliberately not here and are not silently dropped
                # either — each is recorded `covered_by` an existing gate that already proves the class
                # live, with teeth (anti-duplication, §10.2):
                #   replay       -> service-idempotency        (4 partial UNIQUE indexes; every replay
                #                                               attempted live and required to be REFUSED)
                #   concurrency  -> service-dispatch-isolation (the accept race has EXACTLY ONE winner;
                #                                               2nd caller gets lost_race_or_closed)
                #   session-switch -> client-singleton / idle-refresh (the stale-token identity-cache
                #                                               class, found live 2026-07-06)
                and (not str(c.get("kind", "")).startswith("sneak-path")
                     or str(c.get("kind", "")) == "sneak-path:out-of-order")]

    legal = legal_origins(bank)

    passed = failed = 0
    fails = []
    skipped = []
    for c in runnable:
        if c["transition"].get("from") == "(insert)":
            ok, detail = run_birth_cell(c, verbose)
        elif c["transition"].get("from") == "*":
            ok, detail = run_deny_cell(c, verbose)
        else:
            ok, detail = run_cell(c, verbose, legal)
        if ok is None:
            # NEVER a silent continue. Two authority partitions (anon, admin — 36 cells) hid behind this
            # exact branch for the whole arc: enumerated as obligations, reported as owed, never once
            # executed, and indistinguishable on the board from covered. A skip must name itself.
            skipped.append((c["id"], detail))
            continue
        if ok:
            passed += 1
            c["status"] = "banked"
        else:
            failed += 1
            fails.append((c["id"], detail))
        if verbose or not ok:
            mark = GREEN + "PASS" + RST if ok else RED + "FAIL" + RST
            t = c["transition"]
            print(f"  {mark}  {(t['from'] if t['from'] != '*' else 'any'):>14} -> "
                  f"{t['to']:<22} as {c['authority']:<13} "
                  f"({EXPECT_LABEL.get(c['expect'], 'must not move the state')})  {DIM}{detail}{RST}")

    # ── AUTHORED lane: scenario probes that no generator describes ──────────────────────────────
    authored = [c for c in bank["tests"] if isinstance(c.get("probe"), dict)]
    for c in authored:
        ok, detail = run_probe(c)
        if ok is None:
            print(f"  {YEL}SKIP{RST}  {c['id']}  {DIM}{detail}{RST}")
            continue
        if ok:
            passed += 1
            c["status"] = "banked"
        else:
            failed += 1
            fails.append((c["id"], detail))
            # A cell whose probe no longer holds must STOP claiming coverage, or the board keeps
            # counting a proof that has since broken.
            c["status"] = "owed"
        mark = GREEN + "PASS" + RST if ok else RED + "FAIL" + RST
        print(f"  {mark}  {c['id']:<52} {DIM}{detail}{RST}")

    with open(BANK, "w", encoding="utf-8") as f:
        json.dump(bank, f, indent=2, ensure_ascii=False)

    total = passed + failed
    print(f"\n  executed {total} SQL-lane cells: {GREEN}{passed} pass{RST} · "
          f"{(RED if failed else DIM)}{failed} fail{RST}")
    if skipped:
        # Printed, grouped, and counted — so "executed" and "owed" can be compared at a glance instead of
        # a skip masquerading as coverage. Each reason is the runner saying what it cannot express YET.
        byreason: dict[str, list[str]] = {}
        for cid, d in skipped:
            byreason.setdefault(d.split(":")[0], []).append(cid)
        print(f"  {YEL}{len(skipped)} cell(s) NOT executed{RST} {DIM}(named, never swallowed){RST}")
        for reason, ids in sorted(byreason.items(), key=lambda kv: -len(kv[1])):
            print(f"    {YEL}{len(ids):>3}{RST}  {reason}")
            if verbose:
                for cid in ids[:6]:
                    print(f"         {DIM}{cid}{RST}")
    if fails:
        print(f"\n  {RED}FAIL{RST} — the bank's assertions did not hold:")
        for cid, d in fails[:12]:
            print(f"    {cid}  [{d}]")
        return 1
    print(f"  {GREEN}PASS{RST} — every executed transition behaves as the guard promises, "
          f"in BOTH directions (permission and refusal)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
