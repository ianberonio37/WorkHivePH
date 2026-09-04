"""T199: does a write in flight survive a migration landing on top of it? (2026-08-28)

The deploy runbook assumes migrations run when nobody is working. One day one will not. The
question this answers is narrow and checkable: with writes actively in flight against a table,
apply a migration, and check that every write either fully landed or fully failed — never half.

★A REFUSED WRITE IS NOT THE FAILURE. A write rejected during the lock is fine and arguably
correct: the caller gets an error and can retry. What must never happen is a row that exists with
some of its values missing, or a count of "written" rows that the table does not actually hold. So
each probe row carries its own invariant — qty_on_hand equals the index it was written with — and
the run compares three numbers that must agree: reported-OK, rows-present, rows-INTACT.

MEASURED, both migration shapes, 24 concurrent writers against inventory_items:
  * CREATE OR REPLACE VIEW (locks the view)  — applied 1.16s · 24 reported · 24 present · 24 intact
  * ALTER TABLE ADD COLUMN (locks the TABLE) — applied 0.69s · 24 reported · 24 present · 24 intact
Zero refused in either. The additive lock is brief enough that writes simply queue behind it rather
than being rejected, which is the behaviour the additive-migration discipline is banking on.

★THE VIEW SHAPE ALONE WOULD HAVE BEEN A WEAKER CLAIM, and running only it was the first mistake
here: replacing a view takes ACCESS EXCLUSIVE on the VIEW, not on the table being written, so it
never contends with the writers at all. The ALTER TABLE run is the one that actually tests the
contention this trajectory is about.

★NOT A BOARD GATE, deliberately. It writes rows and (for the ALTER shape) mutates schema; running
that on every board pass would make the fixture noisier than the signal is worth. It is a harness to
run against a candidate migration BEFORE shipping it — which is what a migration window discipline
actually needs.

USAGE:  python tools/prove_mid_migration_writes.py <path-to-migration.sql>
Exit 1 if the three counts disagree or the fixture is not restored.
"""
import concurrent.futures as cf
import subprocess
import sys
import time

DOCKER = ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres"]
HIVE = "084c113b-99c0-45c6-a8e8-b4b8349da46d"
TAG = "WH-PROBE-T199"
N = 24


def psql(sql: str, timeout: int = 90):
    return subprocess.run(DOCKER + ["-v", "ON_ERROR_STOP=1", "-c", sql],
                          capture_output=True, text=True, timeout=timeout,
                          encoding="utf-8", errors="replace")


def write_one(i: int):
    """One insert, with the value that must survive intact."""
    sql = (f"insert into inventory_items (hive_id, worker_name, part_number, part_name, "
           f"category, unit, qty_on_hand, min_qty, status) values "
           f"('{HIVE}', 'Leandro Marquez', '{TAG}-{i:03d}', 'probe part {i}', 'General', 'pcs', "
           f"{i}, 0, 'approved');")
    r = psql(sql)
    return {"i": i, "ok": r.returncode == 0, "err": (r.stderr or "").strip()[:80]}


def migrate():
    """The migration lands mid-flight: CREATE OR REPLACE VIEW over the table being written."""
    time.sleep(0.35)                      # let some writes get going first
    with open(sys.argv[1], encoding="utf-8") as fh:
        sql = fh.read()
    t0 = time.time()
    r = subprocess.run(DOCKER, input=sql, capture_output=True, text=True,
                       timeout=120, encoding="utf-8", errors="replace")
    return {"ok": r.returncode == 0, "secs": round(time.time() - t0, 2),
            "err": (r.stderr or "").strip()[:120]}


def main() -> int:
    psql(f"delete from inventory_items where part_number like '{TAG}%';")
    before = psql("select count(*) from inventory_items;").stdout.split()[2]

    with cf.ThreadPoolExecutor(max_workers=10) as ex:
        mig = ex.submit(migrate)
        writes = [ex.submit(write_one, i) for i in range(N)]
        results = [w.result() for w in writes]
        m = mig.result()

    landed = sum(1 for r in results if r["ok"])
    refused = [r for r in results if not r["ok"]]

    # What actually exists, and is it INTACT?
    q = psql(f"select count(*), count(*) filter (where qty_on_hand::text = "
             f"substring(part_number from '[0-9]+$')::int::text) "
             f"from inventory_items where part_number like '{TAG}%';")
    rows = q.stdout.split("\n")[2].strip() if q.returncode == 0 else "?"
    present, intact = [x.strip() for x in rows.split("|")] if "|" in rows else ("?", "?")

    print("mid-migration-write-integrity - does a write in flight survive a migration?\n")
    print(f"  migration        : {'applied' if m['ok'] else 'FAILED'} in {m['secs']}s {m['err']}")
    print(f"  writes attempted : {N}")
    print(f"  reported OK      : {landed}")
    print(f"  refused          : {len(refused)}"
          + (f"  e.g. {refused[0]['err']}" if refused else "  (none)"))
    print(f"  rows present     : {present}")
    print(f"  rows INTACT      : {intact}  (qty_on_hand still equals the index it was written with)")

    ok = (m["ok"] and str(present) == str(landed) and str(intact) == str(present))
    print()
    if ok:
        print("  PASS: every write either landed WHOLE or was refused - none half-landed,")
        print("        and the count the callers were given matches what the table holds.")
    else:
        print("  FAIL: reported-OK, rows-present and rows-intact disagree - a write tore.")

    psql(f"delete from inventory_items where part_number like '{TAG}%';")
    after = psql("select count(*) from inventory_items;").stdout.split()[2]
    print(f"  cleanup          : {before} -> {after} (baseline restored: {before == after})")
    return 0 if ok and before == after else 1


if __name__ == "__main__":
    raise SystemExit(main())
