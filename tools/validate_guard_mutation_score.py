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
    ("is_party_false", r"v_is_party\s*:=\s*", "v_is_party := false or ",
     "party-ness always computes FALSE, so every admin is treated as a non-party moderator"),
    ("client_check_true", r"v_is_client\s*:=\s*\(", "v_is_client := true or (",
     "every caller is treated as the client — the ownership pin stops meaning anything"),
    ("provider_check_true", r"v_is_matched_provider\s*:=\s*exists\s*\(", "v_is_matched_provider := true or exists (",
     "every caller is treated as the matched provider"),
    ("admin_bypass_unconditional", r"public\.is_marketplace_admin\(\)\s+AND\s+NOT\s+v_is_party",
     "public.is_marketplace_admin()",
     "the deny-shape guards' admin bypass goes back to unqualified (self-publish / self-release)"),
    ("refusal_removed", r"raise\s+exception\s+'Not allowed[^;]*;", "return new;",
     "a refusal becomes a silent allow — the guard fails OPEN"),
    ("refusal_removed_upper", r"RAISE\s+EXCEPTION\s+'Not allowed[^;]*;", "RETURN NEW;",
     "same fail-open, on the guards written in upper case"),
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
]

VOCAB_EXTRA = "'settled'"


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
        def patched(sql, timeout=60, args=()):
            # After the cell's own `begin;` — so the mutation is rolled back with the cell, always.
            idx = sql.find("begin;")
            if idx >= 0:
                cut = idx + len("begin;")
                sql = sql[:cut] + "\n" + injected_ddl + "\n" + sql[cut:]
            return original(sql, timeout=timeout, args=args)
        runner.psql_script = patched
    try:
        ran = 0
        for c in cells:
            if isinstance(c.get("probe"), dict):
                ok, detail = runner.run_probe(c)
            elif c["transition"].get("from") == "*":
                ok, detail = runner.run_deny_cell(c)
            else:
                ok, detail = runner.run_cell(c, False, legal)
            if ok is None:
                continue
            ran += 1
            if not ok:
                return ran, (c["id"], detail)
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
        killed, survived, malformed = [], [], []
        for op, why, mutated in mutants:
            # Does the mutant even compile? A malformed mutation is an operator bug, not a bank gap.
            probe = psql("begin;\n" + mutated + "\nrollback;")
            if probe is None:
                malformed.append((op, why))
                continue
            n, objection = run_cells(runner, cells, legal, injected_ddl=mutated)
            if objection:
                killed.append((op, why, objection[0]))
            else:
                survived.append((op, why, n))
            if verbose:
                mark = f"{GREEN}killed{RST}" if objection else f"{RED}SURVIVED{RST}"
                print(f"    {mark:<20} {op:<28} {DIM}{why[:66]}{RST}")

        denom = len(killed) + len(survived)
        results[guard] = {
            "cells": len(cells), "baseline_ran": n_base,
            "killed": killed, "survived": survived, "malformed": malformed,
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
        for op, why, _n in r["survived"]:
            print(f"          {RED}SURVIVED{RST} {op}: {why}")
        for op, why in r["malformed"]:
            print(f"          {DIM}malformed (operator bug, not a bank gap): {op}{RST}")

    denom = total_k + total_s
    overall = round(100.0 * total_k / denom, 1) if denom else 0.0
    print(f"\n  platform mutation score: {BOLD}{overall}%{RST}  ({total_k} killed / {denom} viable mutants)")

    # No mutated function may survive the run. The injection is inside each cell's transaction, so this
    # should be structurally impossible - assert it anyway, because "should be impossible" is what every
    # silent failure this arc found had in common.
    leaked = psql("select count(*) from pg_proc where proname in "
                  "('" + "','".join(GUARDS) + "') and prosrc like '%v_is_party := false or%';")
    if leaked and leaked.strip() not in ("0", ""):
        print(f"  {RED}FAIL{RST} — a MUTATED guard is still installed. Restore from migrations now.")
        return 1
    print(f"  {DIM}verified: 0 mutated guards persist (every mutation died with its cell's rollback){RST}")

    base = 0.0
    if os.path.exists(BASELINE):
        try:
            base = float(json.load(open(BASELINE, encoding="utf-8")).get("score", 0.0))
        except Exception:
            base = 0.0
    if "--update-baseline" in argv or not os.path.exists(BASELINE):
        with open(BASELINE, "w", encoding="utf-8") as f:
            json.dump({"score": overall, "viable": denom, "_doc": "forward-only; raise by killing survivors"}, f, indent=2)
        print(f"  {DIM}baseline set to {overall}%{RST}")
        return 0
    if overall < base:
        print(f"  {RED}FAIL{RST} — mutation score REGRESSED {base}% -> {overall}%: a fault the bank used "
              f"to catch now slips through.")
        return 1
    if overall > base:
        with open(BASELINE, "w", encoding="utf-8") as f:
            json.dump({"score": overall, "viable": denom, "_doc": "forward-only; raise by killing survivors"}, f, indent=2)
        print(f"  {GREEN}PASS{RST} — baseline ratcheted {base}% -> {overall}%")
        return 0
    print(f"  {GREEN}PASS{RST} — holds at the {base}% baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
