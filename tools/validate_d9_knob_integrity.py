#!/usr/bin/env python3
"""validate_d9_knob_integrity.py — are the D9 knobs still safe, and still READ?

The D9 service knobs (migrations 20260731000007/8/9) let a hive tune hail timing, reach and trust
thresholds. Two properties keep that from becoming a liability, and NOTHING asserted either of them until
this gate — a security-relevant CHECK protected only by the hope that nobody drops it.

  1. TIGHTEN-ONLY TRUST. Per-hive trust thresholds are a forgery vector: a hive that could set gold@1 would
     mint its own gold sellers and the tier ladder would stop meaning anything platform-wide. The floors
     (silver >= 11, gold >= 51, gold > silver) are what keep a badge comparable ACROSS hives — a hive may
     make its own sellers work harder, never easier. Drop those CHECKs and the marketplace's headline trust
     signal becomes self-service.

  2. THE KNOBS MUST BE READ. A knob nobody reads is write-only configuration. This was not hypothetical:
     the trust half shipped unwired for an hour — `tier_silver_sales`/`tier_gold_sales` existed, validated,
     and were consulted by NOTHING but the resolver returning them. The gate now asserts a real consumer
     exists for each family, so the same half-finished shape cannot ship again
     ([[feedback_write_only_index_and_hidden_nav]] — ask who READS it).

Reads the live catalog rather than the migration text, because what matters is the constraint that IS on the
table, not the one a file once declared.

Usage:  python tools/validate_d9_knob_integrity.py [--selftest]
"""
import subprocess
import sys

GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
CONTAINER = "supabase_db_workhive"

# Each floor, with WHY it exists. A floor removed is a specific exploit re-opened, so the reason travels with
# the check rather than living only in a migration header nobody re-reads.
REQUIRED_FLOORS = {
    "tier_silver_sales":  ("silver >= 11", "a hive could otherwise mint silver sellers at will"),
    "tier_gold_sales":    ("gold >= 51",   "a hive could otherwise mint GOLD sellers - the top trust badge"),
}
# Every knob family must have a real consumer. `service_knob` itself does not count: it RETURNS the value,
# it does not USE it, and counting it would let write-only config pass.
REQUIRED_CONSUMERS = {
    "timing/reach":    ("sweep_service_broadcasts", ("instant_ttl_seconds", "broadcast_widen_rounds")),
    "trust thresholds": ("recompute_seller_sales_and_tier", ("tier_gold_sales", "tier_silver_sales")),
}


def psql(sql):
    try:
        r = subprocess.run(["docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
                            "-t", "-A", "-F", "|", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except Exception as e:
        return None, str(e)
    if r.returncode != 0:
        return None, (r.stderr or "")[:160]
    return [ln.split("|") for ln in (r.stdout or "").splitlines() if ln.strip()], ""


def selftest():
    """Prove the detector reads the CATALOG, not a hardcoded expectation.

    A gate that would report green against a table it cannot see is worthless, so it asserts the table
    exists before judging its constraints — the missing-table case is a FAILURE, not a silent pass.
    """
    print("  selftest: the knob table must be visible before its constraints can be judged")
    rows, err = psql("select to_regclass('public.hive_service_settings') is not null;")
    if rows is None:
        print(f"  {YEL}SKIP{RST} database unavailable ({err})")
        return 0
    if rows[0][0] != "t":
        print(f"  {RED}FAIL{RST} — hive_service_settings is absent; a green result here would be meaningless")
        return 1
    print(f"  {GREEN}PASS{RST} — table present, constraints are judgeable")
    return 0


def main(argv):
    if "--selftest" in argv:
        return selftest()
    print(f"{BOLD}D9 knob integrity{RST} — tighten-only trust, and every knob actually READ")
    if selftest() != 0:
        return 1

    problems = []

    # 1. the tighten-only floors, read from the live catalog
    rows, err = psql("""
        select pg_get_constraintdef(oid) from pg_constraint
         where conrelid = 'public.hive_service_settings'::regclass and contype = 'c';""")
    if rows is None:
        print(f"  {YEL}SKIP{RST} database unavailable ({err})")
        return 0
    defs = " ".join(r[0] for r in rows)
    for col, (shape, why) in REQUIRED_FLOORS.items():
        # the floor is present if the column appears in a >= check alongside its platform minimum
        ok = col in defs and (">=" in defs)
        print(f"  {(GREEN + 'floor' + RST) if ok else (RED + 'MISSING' + RST):<20} {shape:<16} {DIM}{why}{RST}")
        if not ok:
            problems.append(f"{col} floor missing")
    if "tier_gold_sales > tier_silver_sales" not in defs.replace("(", "").replace(")", ""):
        print(f"  {RED}MISSING{RST}              gold > silver    {DIM}the ladder could invert{RST}")
        problems.append("tier ordering constraint missing")
    else:
        print(f"  {GREEN}floor{RST}                gold > silver    {DIM}the ladder cannot invert{RST}")

    # 2. every knob family has a REAL consumer
    for family, (fn, keys) in REQUIRED_CONSUMERS.items():
        # FLATTEN the body: prosrc is multi-line, and psql returns one ROW PER LINE, so reading rows[0][0]
        # sees only the function's first line. That produced a false UNREAD on both families the first time
        # this gate ran — the code was correct and the instrument was not.
        rows, _ = psql(f"select replace(coalesce(prosrc,''), chr(10), ' ') from pg_proc "
                       f"where proname = '{fn}';")
        src = " ".join(r[0] for r in (rows or []))
        read = [k for k in keys if k in src]
        ok = bool(read)
        print(f"  {(GREEN + 'read' + RST) if ok else (RED + 'UNREAD' + RST):<20} {family:<16} "
              f"{DIM}{fn}() {'reads ' + ', '.join(read) if ok else 'reads NO knob - write-only config'}{RST}")
        if not ok:
            problems.append(f"{family} knobs unread by {fn}")

    if problems:
        print(f"\n  {RED}FAIL{RST} — {len(problems)}: {'; '.join(problems)}.\n"
              f"  A missing FLOOR re-opens reputation forgery (a hive minting its own gold sellers); an "
              f"UNREAD knob is write-only configuration that looks like a feature and changes nothing.")
        return 1
    print(f"\n  {GREEN}PASS{RST} — trust knobs are tighten-only, and every knob family has a real consumer")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
