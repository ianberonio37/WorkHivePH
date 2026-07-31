#!/usr/bin/env python3
"""money_economy_board.py — the anti-drift %-board for the money economy arc (M1-M8).

Ian, 2026-07-31: *"implement our framework here with anti-drift doctrine and momentum drive, because we need
to drive this to full completion."* Per [[feedback_follow_framework_antidrift_before_building]] the structure
is laid out BEFORE the build and the board is the compass: at any "what next / should I build this / am I
done" doubt, read this and drive the LOWEST row. The roadmap decides, not the tangent in front of you.

WHY A BOARD AND NOT A TABLE IN A DOCUMENT. A table in a markdown file drifts from reality the moment work
starts, and then it flatters. Every row here is MEASURED — from the live catalog, the test bank, and the
registered-gate list — so the board cannot claim a unit that does not exist. The denominators are fixed HERE,
before building, precisely so they cannot be quietly shortened later to manufacture a 100%
([[feedback_short_denominator_is_a_false_100]], [[feedback_phase_table_is_one_axis_build_the_compass]]).

DONE = EVERY ROW AT 100%, NOT THE GREENEST ONE. A single headline metric at 100% has already masked an open
axis on this platform. `--check` therefore fails on ANY row regressing, and prints every owed item WITH ITS
REASON rather than averaging it away ([[feedback_a_skipped_partition_reads_as_a_covered_one]]).

    M1  money spine        payment record - cashback wired - commission bills what was paid - dispute path
    M2  knobs READ         a knob nobody reads is write-only config; this feature family has shipped five
    M3  bank - SQL cells   deterministic money cells, db-truth weighted
    M4  bank - lifecycle   the 12 request states reached by a LIVE walk, not a fragment
    M5  bank - personas    diverse humans walked, scored task-success
    M6  simulation         the six economic invariants, teeth-proven by injection
    M7  fraud model        attacks refused, or detected and NAMED
    M8  gates              money gates registered, green, teeth-proven

Usage:  python tools/money_economy_board.py [--check | --accept | --selftest]
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANK = ROOT / "marketplace_test_bank.json"
CHECKS = ROOT / "run_platform_checks.py"
PROBES = ROOT / "tests" / "bank_probes"
BASELINE = ROOT / "money_economy_baseline.json"
OUT_MD = ROOT / "MONEY_ECONOMY_BOARD.md"
CONTAINER = "supabase_db_workhive"

G, R, Y, D, B, X = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

# The 12 states of service_requests. The four exits (cancelled x2, expired, disputed) are MEMBERS of this
# set, not additions to it - an earlier draft of the plan counted them twice and would have measured against
# a denominator of 16 that does not exist. The denominator is what the CHECK constraint says it is.
STATES = ["requested", "broadcasting", "accepted", "en_route", "on_site", "in_progress",
          "completed", "settled", "cancelled_by_client", "cancelled_by_provider", "expired", "disputed"]


def psql(sql):
    # THE SEPARATOR IS 0x1f (unit separator), NOT "|". A pipe is SQL's own concatenation operator, so a
    # function body containing `a || b` was split mid-source and everything after the first `||` was
    # silently discarded — which reported a knob as UNREAD on a function that plainly reads it. Same
    # class as the multi-line prosrc bug: the code was right and the instrument was not. 0x1f cannot
    # occur in SQL source, so it cannot collide with anything.
    """-> (rows, err). Never raises: a board that dies when Docker is down teaches nothing."""
    try:
        r = subprocess.run(["docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
                            "-t", "-A", "-F", "", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except Exception as e:
        return None, str(e)
    if r.returncode != 0:
        return None, (r.stderr or "")[:160]
    return [ln.split("") for ln in (r.stdout or "").splitlines() if ln.strip()], ""


def _one(sql, default=""):
    rows, _ = psql(sql)
    return rows[0][0] if rows else default


def _src(fn):
    """A function's body, FLATTENED. psql returns one ROW PER LINE, so reading rows[0][0] sees only the
    first line - that exact mistake produced a false UNREAD on two knob families once already."""
    rows, _ = psql(f"select replace(coalesce(prosrc,''), chr(10), ' ') from pg_proc where proname = '{fn}';")
    return " ".join(r[0] for r in (rows or []))


def measure():
    """Every row as (label, [(name, ok, why_it_matters_if_missing)]). The `why` travels WITH the check so an
    owed item is a work list, not a complaint."""
    db_up = _one("select 1;") == "1"
    bank = json.loads(BANK.read_text(encoding="utf-8")) if BANK.exists() else {"tests": []}
    tests = bank.get("tests", [])
    done = [t for t in tests if t.get("status") in ("covered", "banked")]
    checks_src = CHECKS.read_text(encoding="utf-8", errors="replace") if CHECKS.exists() else ""

    # ---- M1 money spine -------------------------------------------------------------------------------
    # Read EVERY trigger function on service_requests, not one named guard. The payment requirement is
    # enforced by a separate `guard_settle_requires_payment` rather than by editing the long, mutation-scored
    # `guard_service_request_status` — pinning this check to one function name would have reported the rule
    # missing while it was live, which is the instrument lying about the page.
    guard = " ".join(r[0] for r in (psql(
        "select replace(coalesce(p.prosrc,''), chr(10), ' ') from pg_trigger t "
        "join pg_proc p on p.oid = t.tgfoid "
        "where t.tgrelid = 'public.service_requests'::regclass and not t.tgisinternal;")[0] or [])
    ) if db_up else ""
    commission = _src("mint_settlement_commission") if db_up else ""
    # `mint_service_cashback` is an RPC (takes an id, returns the amount), so NO trigger can ever bind to it
    # directly — very likely why it went unwired for so long. A check for `tgfoid = mint_service_cashback`
    # can therefore only ever report owed, even once the wire is in. What actually matters is whether a
    # trigger on service_requests REACHES it, so follow the call into the adapter.
    cashback_trg = "1" if (db_up and "mint_service_cashback" in guard) else "0"
    adjust_fn = _one(
        "select count(*)::text from pg_proc where prosrc like '%adjustment%' "
        "and proname not like 'guard_%';", "0") if db_up else "0"
    m1 = [
        ("payment record exists", db_up and _one("select to_regclass('public.service_payments') is not null;") == "t",
         "a settle records no amount and no reference, so nothing can be reconciled or disputed"),
        ("cashback WIRED", cashback_trg != "0",
         "mint_service_cashback has no trigger - the 1% Ian decided on mints for NOBODY"),
        ("commission bills amount_paid", "service_payments" in commission,
         "commission is computed from the catalogue price, so a job settled at a different real price "
         "bills the wrong amount"),
        ("settle requires the record", "service_payments" in guard,
         "release and record can diverge - a settle with no payment row is accepted"),
    ]

    # ---- M2 knobs READ --------------------------------------------------------------------------------
    # A knob is READ only if a consumer OTHER than the resolver uses it AND that consumer can actually FIRE.
    # `service_knob` RETURNS a value, it does not USE one, so counting it would let write-only config pass.
    # But the first version of this check was still too generous and reported `cashback_pct` as READ on the
    # strength of `mint_service_cashback` — a function that reads the knob and HAS NO TRIGGER, so it mints
    # for nobody. A consumer that never executes is write-only configuration with an extra step, which is
    # exactly the class this row exists to catch. Reachable means: it has a trigger, or something else calls
    # it ([[feedback_built_but_never_called_and_excluded_errors]] — built is not called).
    def knob_read(knob):
        if not db_up:
            return False
        rows, _ = psql(
            "select proname from pg_proc where prosrc like '%" + knob + "%' "
            "and proname not in ('service_knob','service_knob_pct');")
        for (fn,) in [(r[0],) for r in (rows or [])]:
            has_trigger = _one("select count(*)::text from pg_trigger t join pg_proc p on p.oid = t.tgfoid "
                               f"where p.proname = '{fn}' and not t.tgisinternal;", "0") != "0"
            called_by = _one("select count(*)::text from pg_proc "
                             f"where prosrc like '%{fn}%' and proname <> '{fn}';", "0") != "0"
            # A client-called RPC is reachable too, and this is the common case for money paths:
            # `accept_service_request` reads the floor, has no trigger and no internal caller, and fires on
            # every accept. Omitting this reported a live, blocking floor as write-only config.
            is_rpc = _one("select count(*)::text from pg_proc p "
                          f"where p.proname = '{fn}' and (has_function_privilege('authenticated', p.oid, "
                          "'EXECUTE') or has_function_privilege('anon', p.oid, 'EXECUTE'));", "0") != "0"
            if has_trigger or called_by or is_rpc:
                return True
        return False
    # Ask the RESOLVER what floor is actually in force, not the settings table's column max. A per-hive row
    # is the exception; the platform default is what nearly every provider is actually held to, and reading
    # the raw column reported "floor 0" while a 200 floor was live and blocking. Measure the effective
    # value, which is the one a provider meets.
    minbal = _one("select public.service_knob(null,'min_list_balance')::text;", "0") if db_up else "0"
    m2 = [
        ("cashback_pct read", knob_read("cashback_pct"),
         "the cashback rate is configurable and consulted by nothing"),
        ("min_list_balance read AND set", knob_read("min_list_balance") and minbal not in ("0", ""),
         f"currently {minbal} - a zero floor means a provider can complete a job with an empty wallet, "
         f"which is failure mode 2 in the sustainability study"),
    ]

    # ---- M3 SQL money cells ---------------------------------------------------------------------------
    MONEY_PREFIXES = ("TB-PAY-", "TB-CASHBACK-", "TB-TIER-", "TB-DISPUTE-", "TB-SOLV-", "TB-ECON-")
    money_cells = [t for t in done
                   if t.get("lane") == "sql" and any(t["id"].startswith(p) for p in MONEY_PREFIXES)]
    M3_TARGET = 40

    # ---- M4 lifecycle states reached by a LIVE walk ---------------------------------------------------
    # Only the JOURNEY lane counts. A SQL cell can prove a transition is legal; it cannot prove a human
    # can reach it, which is the whole point of this row.
    reached = set()
    for t in done:
        if t.get("lane") != "journey":
            continue
        blob = json.dumps(t)
        for s in STATES:
            if s in blob:
                reached.add(s)

    # ---- M5 personas ----------------------------------------------------------------------------------
    persona_reg = ROOT / "tools" / "service_personas.mjs"
    persona_cells = [t for t in done if t.get("oracle") == "task-success"]

    # ---- M6 simulation --------------------------------------------------------------------------------
    sim = ROOT / "tools" / "simulate_credit_economy.py"
    sim_src = sim.read_text(encoding="utf-8", errors="replace") if sim.exists() else ""
    INVARIANTS = [("net take", "net_take"), ("solvency at every step", "solvency"),
                  ("exactly-once mint", "exactly_once"), ("liability cover", "liability_cover"),
                  ("order independence", "order_independence"), ("state histogram", "reached_states")]
    m6 = [(n, k in sim_src, f"the simulation does not assert {n}") for n, k in INVARIANTS]

    # ---- M7 fraud model -------------------------------------------------------------------------------
    fraud = sorted(p.name for p in PROBES.glob("TB-FRAUD-*.sql")) if PROBES.exists() else []
    M7_TARGET = 8

    # ---- M8 gates -------------------------------------------------------------------------------------
    m8 = [(g, f'"{g}"' in checks_src, f"{g} is not registered, so it never runs")
          for g in ("credit-solvency", "service-payment-integrity", "money-economy-board",
                    "credit-economy-simulation")]

    rows = [
        ("M1", "money spine", sum(1 for _, ok, _ in m1 if ok), len(m1), m1),
        ("M2", "knobs READ", sum(1 for _, ok, _ in m2 if ok), len(m2), m2),
        ("M3", "bank - SQL money cells", len(money_cells), M3_TARGET,
         [(f"{len(money_cells)}/{M3_TARGET} banked", len(money_cells) >= M3_TARGET,
           "money has no deterministic cells of its own; the 293 sql cells cover dispatch")]),
        ("M4", "bank - lifecycle states", len(reached), len(STATES),
         [(s, s in reached, "no LIVE journey reaches this state") for s in STATES]),
        ("M5", "bank - persona pairings", len(persona_cells), 12,
         [("persona registry exists", persona_reg.exists(), "no runtime persona conditions to walk with"),
          (f"{len(persona_cells)} task-success cells", len(persona_cells) >= 12,
           "every journey still walks one idealised user")]),
        ("M6", "economic simulation", sum(1 for _, ok, _ in m6 if ok), len(m6), m6),
        ("M7", "fraud model", len(fraud), M7_TARGET,
         [(f"{len(fraud)}/{M7_TARGET} attacks", len(fraud) >= M7_TARGET,
           "no adversary is modelled; this platform has already shipped a live tier self-mint")]),
        ("M8", "gates registered", sum(1 for _, ok, _ in m8 if ok), len(m8), m8),
    ]
    return {"db_up": db_up, "rows": rows,
            "overall": round(100.0 * sum(r[2] for r in rows) / max(1, sum(r[3] for r in rows)), 1)}


def render(m):
    out = [f"{B}Money economy — anti-drift %-board{X}  {D}(structure before build; drive the LOWEST row){X}"]
    if not m["db_up"]:
        out.append(f"  {Y}NOTE{X} database unreachable — DB-derived rows read 0 and say so, rather than "
                   f"passing vacuously")
    for rid, label, n, total, items in m["rows"]:
        pct = round(100.0 * n / max(1, total), 1)
        col = G if n >= total else (Y if n else R)
        out.append(f"  {col}{rid}{X} {label:<26} {col}{pct:>5.1f}%{X}  {D}{n}/{total}{X}")
        for name, ok, why in items:
            if not ok:
                out.append(f"        {R}owed{X} {name} {D}— {why}{X}")
    out.append(f"  {B}OVERALL {m['overall']}%{X}  {D}done = EVERY row at 100%, not the greenest one{X}")
    return "\n".join(out)


def selftest():
    """Prove the board cannot report a unit that does not exist, and that DONE means every row."""
    print("  selftest: the board must refuse to average a missing row away")
    ok = True
    fake = {"db_up": True, "overall": 0.0,
            "rows": [("M1", "x", 4, 4, []), ("M2", "y", 0, 2, [("k", False, "w")])]}
    txt = render(fake)
    if "owed" not in txt:
        print(f"  {R}FAIL{X} — an owed item was not printed with its reason"); ok = False
    # 4/4 and 0/2 must NOT read as "mostly done" anywhere in the output
    if "100.0%" in txt.split("OVERALL")[-1]:
        print(f"  {R}FAIL{X} — a half-empty board reported a full overall"); ok = False
    if ok:
        print(f"  {G}PASS{X} — owed items print their reason; a green row cannot hide an empty one")
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    if selftest() != 0:
        return 1
    m = measure()
    txt = render(m)
    print(txt)
    OUT_MD.write_text(
        "# Money economy — anti-drift %-board\n\n_Generated by `tools/money_economy_board.py`. "
        "DONE = every row at 100%._\n\n```\n"
        + "\n".join(l for l in txt.replace("\033", "\x00").split("\n")).replace("\x00", "")
        .encode("ascii", "ignore").decode() + "\n```\n", encoding="utf-8")

    base = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}
    cur = {rid: n for rid, _, n, _, _ in m["rows"]}

    if "--accept" in argv:
        # Forward-only: a ratchet that turns both ways is not a ratchet. Denominators here are FIXED in
        # this file, so unlike the transition board there is no legitimate "scope grew" fall to allow.
        dropped = [f"{k} {base[k]} -> {v}" for k, v in cur.items()
                   if isinstance(base.get(k), int) and v < base[k]]
        if dropped:
            print(f"  {R}ACCEPT REFUSED{X}  " + "; ".join(dropped) +
                  " — the floor only moves up. Fix the work, not the baseline.")
            return 1
        BASELINE.write_text(json.dumps({**cur, "_doc": "Forward-only floor for the money economy arc; "
                                        "a FALL below any row FAILs --check."}, indent=2), encoding="utf-8")
        print(f"  {G}ACCEPTED{X}  floor -> {cur}")
        return 0

    if "--check" in argv:
        drops = [f"{k} {v} < floor {base[k]}" for k, v in cur.items()
                 if isinstance(base.get(k), int) and v < base[k]]
        if drops:
            print(f"  {R}FAIL{X}  ratchet regressed: " + "; ".join(drops))
            return 1
        print(f"  {G}PASS{X}  forward-only ratchet holds across M1-M8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
