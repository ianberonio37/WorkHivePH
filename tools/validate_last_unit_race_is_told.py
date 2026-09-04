#!/usr/bin/env python3
"""last-unit-race-is-told - T11: a deduction that moved nothing must not read as success (2026-08-27).

Two workers finish repairs on the same part. inventory_deduct locks the item FOR UPDATE, so the race
is serialised: the winner takes the last one, and the loser's call runs against an empty shelf.

★WHAT THE LOSER GETS, MEASURED: `v_qty := GREATEST(0, v_qty - p_qty)` clamps instead of refusing, so
asking for 1 when 0 remain RETURNS NORMALLY. Driven live against a real item set to 0 inside a
rolled-back transaction: return 0, a ledger row written with qty_change 0, shelf unchanged, and NO
error raised. A caller checking only `error` cannot see it. logbook did exactly that, so the worker
was told "Entry saved" while their entry claimed a part the shelf never gave up - the shelf and the
system disagreeing silently, which is the one thing this trajectory exists to prevent.

★AND THE RETURN VALUE CANNOT TELL THEM. It is the new quantity, and "took the last one" and "there
were none" both end at 0. The LEDGER row can, because it records what actually moved - so the client
passes p_txn_id (the function has always accepted one) and reads that row back. Verified under RLS
that a member can read their own hive's inventory_transactions row.

TWO ASSERTIONS: the DB still behaves as measured (clamp, no raise, honest ledger), and the client
still checks what moved rather than only what errored.

SAFETY: the DB half runs inside a transaction and ROLLS BACK; the shelf is re-read afterwards.

Self-test: `--selftest` (the client-side assertions).
"""
import io
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DB = "supabase_db_workhive"
PAGES = [ROOT / "logbook.html", ROOT / "inventory.html"]   # every page that deducts
MARKER = "WH-T11-RACE-GATE"


def psql(sql: str):
    r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres",
                        "-t", "-A", "-v", "ON_ERROR_STOP=1"],
                       input=sql, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=90)
    return (r.stdout or "").strip(), (r.stderr or "").strip(), r.returncode


def check_client(src: str, label: str = "source") -> list:
    """EVERY caller must pass a txn id and check what MOVED, not only what errored.

    Every site, not the first one found. The first version of this gate searched with re.search and
    graded a single call - and logbook has TWO deduct paths (save and edit) while inventory has a
    third. Checking one and reporting on all of them is how two of the three kept the defect while
    the gate went green; "fix every path that mutates, not just the walked one" applies to the
    instrument as much as to the code.
    """
    problems = []
    calls = list(re.finditer(r"rpc\(\s*'inventory_deduct'[\s\S]{0,500}?\)\s*;", src))
    if not calls:
        return []                      # a page that does not deduct owes nothing
    for n, call in enumerate(calls, 1):
        where = f"{label} deduct #{n}"
        if "p_txn_id" not in call.group(0):
            problems.append(f"{where}: passes no p_txn_id, so nothing can identify the ledger row "
                            f"that says what actually moved")
            continue
        after = src[call.end():call.end() + 1600]
        if not re.search(r"whDeductMoved\s*\(|inventory_transactions", after):
            problems.append(f"{where}: nothing reads back what moved, so a clamped deduct that moved "
                            f"0 is indistinguishable from one that moved everything asked for")
        elif not re.search(r"\.short\b|moved\s*<|<\s*Number\(", after):
            problems.append(f"{where}: what moved is read but never COMPARED to what was requested")
    return problems


def selftest() -> int:
    ok = True

    def chk(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {name}: got {got}, want {want}")

    bare = ("const { data: newQty, error: deductErr } = await db.rpc('inventory_deduct', {\n"
            "  p_item_id: p.partId, p_qty: p.qty });\n"
            "if (deductErr) { showToast('failed'); }\n")
    # one problem, not two: with no p_txn_id there is nothing to read back, so reporting the
    # readback separately would be telling someone to fix a consequence of the first problem.
    chk("the pre-fix shape (error-only) fails", len(check_client(bare)), 1)

    idonly = bare.replace("p_qty: p.qty }", "p_qty: p.qty, p_txn_id: t }")
    chk("passing an id but never reading it back still fails", len(check_client(idonly)), 1)

    full = (idonly + "const { data: mv } = await db.from('inventory_transactions')"
                     ".select('qty_change').eq('id', t).maybeSingle();\n"
                     "const moved = Math.abs(Number(mv.qty_change) || 0);\n"
                     "if (moved < Number(p.qty)) { showToast('only some was on the shelf'); }\n")
    chk("id + ledger read + comparison passes", len(check_client(full)), 0)

    live = []
    for pg in PAGES:
        live += check_client(io.open(pg, encoding='utf-8', errors='replace').read(), pg.name)
    chk("every live deduct site passes", live, [])
    print(f"\n  SELFTEST: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()

    print("T11 last-unit race is told")
    problems, sites = [], 0
    for pg in PAGES:
        src = io.open(pg, encoding="utf-8", errors="replace").read()
        sites += len(re.findall(r"rpc\(\s*'inventory_deduct'", src))
        problems += check_client(src, pg.name)
    print(f"  deduct call sites checked: {sites}")
    print(f"  all check what MOVED:      {'yes' if not problems else 'NO'}")

    row, err, _ = psql("""
SELECT i.id||'|'||m.auth_uid||'|'||i.qty_on_hand
FROM inventory_items i
JOIN hive_members m ON m.hive_id = i.hive_id AND m.status='active' AND m.auth_uid IS NOT NULL
WHERE i.hive_id IS NOT NULL LIMIT 1;""")
    if not row:
        print(f"  SKIP db half — no item/member pair ({err[:70]})")
        return 1 if problems else 0
    item_id, uid, before = row.split("|", 2)

    out, notices, _ = psql(f"""
begin;
update inventory_items set qty_on_hand = 0 where id = '{item_id}';
set local role authenticated;
set local request.jwt.claims = '{{"sub":"{uid}","role":"authenticated"}}';
do $$ declare v numeric; begin
  v := public.inventory_deduct('{item_id}', 1, '{MARKER}', 'gate');
  raise notice 'RET|%', v;
exception when others then raise notice 'RAISED|%', SQLERRM; end $$;
reset role;
select 'MOVED|'||coalesce(sum(abs(qty_change))::text,'none') from inventory_transactions where note='{MARKER}';
rollback;""")
    ret = re.search(r"RET\|([^\s]+)", notices)
    raised = re.search(r"RAISED\|(.*)", notices)
    moved = re.search(r"MOVED\|([^\s]+)", out or "")
    after, _, _ = psql(f"SELECT qty_on_hand FROM inventory_items WHERE id='{item_id}';")
    resid, _, _ = psql(f"SELECT count(*) FROM inventory_transactions WHERE note='{MARKER}';")

    print(f"  asking for 1 with 0 on the shelf: "
          f"{'raised ' + raised.group(1)[:40] if raised else 'returned ' + (ret.group(1) if ret else '?')}")
    print(f"  quantity actually moved:         {moved.group(1) if moved else '?'}")
    print(f"  shelf after rollback: {after} (was {before}), probe rows left: {resid}")

    if raised:
        problems.append("inventory_deduct now RAISES when short - the clamp this gate describes has "
                        "changed, so the client-side comparison may no longer be the right shape")
    if moved and moved.group(1) not in ("0", "none"):
        problems.append(f"a deduct against an empty shelf moved {moved.group(1)} - the clamp is not holding")
    if (after or "").strip() != (before or "").strip():
        problems.append("the probe did not roll back cleanly - the shelf was left changed")
    if (resid or "").strip() != "0":
        problems.append("probe ledger rows survived the rollback")

    if not problems:
        print("\n  PASS - the shelf clamps silently, and the client says so.")
        return 0
    print("\n  FAIL")
    for p in problems:
        print(f"    {p}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
