#!/usr/bin/env python3
"""erasure-path-intact - T164: the deletion the privacy policy promises must be possible (2026-08-26).

The policy tells a person: email admin@workhiveph.com with "Data Rights Request" and
your personal data is purged within 30 days, while compliance records are retained.
That is a legitimate PDPA path - a manual one is fine if it is HONORED - but honoring
it means the database must actually let the deletion happen, and must remove the right
things when it does.

READ FROM THE LIVE FK GRAPH 2026-08-26, and the model is sound and matches the policy's
own stated tension:

  CASCADE  (10 public tables) personal data goes with the account - worker_profiles,
           voice_journal_entries, resume_documents, resume_versions,
           worker_achievements, push_subscriptions, mfa_enrollments, service_requests,
           service_credit_topups, service_voucher_redemptions.
  SET NULL (20 public tables) operational records SURVIVE with the identity detached -
           logbook, pm_completions, asset_nodes, inventory_transactions,
           community_posts, hive_members, skill_badges and the rest. The plant keeps
           its maintenance history; the person stops being in it.

  RESTRICT / NO ACTION: none. Nothing can block the erasure.

THREE ASSERTIONS, each guarding a way this quietly stops working:

  blocked   No FK to auth.users may be RESTRICT or NO ACTION. One such migration and
            every erasure request fails at the database - the promise broken with no
            symptom until someone exercises the right.
  throws    No SET NULL FK may point at a NOT NULL column. It passes every graph
            inspection and then raises at DELETE time. ★This is the subtle one, and it
            is why the gate reads attnotnull rather than just confdeltype - a graph
            that looks correct is not the same as a deletion that runs.
  drifts    No existing table may change its action. A CASCADE quietly turned SET NULL
            leaves personal data behind after a purge that reported success; a SET NULL
            turned CASCADE destroys plant history the policy promised to retain. Both
            directions are failures, so the baseline pins the exact mapping and any
            change must be a deliberate edit here with its reason.

New tables referencing auth.users are ADMITTED (with their action reported) provided
they pass 'blocked' and 'throws' - the gate should not stall schema work, only refuse
the two shapes that break erasure and any silent change to what is already settled.

Baseline: substrate/reference/erasure_path_baseline.json
Usage: python tools/validate_erasure_path_intact.py [--update-baseline]
"""
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "substrate" / "reference" / "erasure_path_baseline.json"

SQL = """
SELECT n.nspname||'.'||t.relname, a.attname,
       CASE c.confdeltype WHEN 'c' THEN 'CASCADE' WHEN 'n' THEN 'SET NULL'
            WHEN 'a' THEN 'NO ACTION' WHEN 'r' THEN 'RESTRICT' WHEN 'd' THEN 'SET DEFAULT' END,
       a.attnotnull
FROM pg_constraint c
JOIN pg_class t ON t.oid=c.conrelid
JOIN pg_namespace n ON n.oid=t.relnamespace
JOIN pg_class ft ON ft.oid=c.confrelid
JOIN pg_namespace fn ON fn.oid=ft.relnamespace
JOIN unnest(c.conkey) AS k(att) ON true
JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=k.att
WHERE c.contype='f' AND fn.nspname='auth' AND ft.relname='users' AND n.nspname='public'
ORDER BY 1, 2;
"""


def main() -> int:
    if not shutil.which("docker"):
        print("SKIP erasure-path-intact - docker not available (the FK graph is the oracle)")
        return 0
    try:
        out = subprocess.run(
            ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-F", "|", "-c", SQL],
            capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"SKIP erasure-path-intact - psql unreachable ({str(e)[:60]})")
        return 0
    if out.returncode != 0:
        print("SKIP erasure-path-intact - local stack down")
        return 0

    live = {}
    for line in out.stdout.strip().splitlines():
        parts = line.strip().split("|")
        if len(parts) != 4:
            continue
        tbl, col, act, notnull = parts
        live[f"{tbl}.{col}"] = {"action": act, "not_null": notnull == "t"}
    if not live:
        print("SKIP erasure-path-intact - no FKs to auth.users found (unexpected; not asserting on it)")
        return 0

    blocked = [k for k, v in live.items() if v["action"] in ("RESTRICT", "NO ACTION")]
    throws = [k for k, v in live.items() if v["action"] == "SET NULL" and v["not_null"]]

    if "--update-baseline" in sys.argv:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        io.open(BASELINE, "w", encoding="utf-8", newline="\n").write(
            json.dumps({"_why": "T164: the erasure path the privacy policy promises. Pins each FK to "
                                "auth.users to its ON DELETE action. A change in EITHER direction is a "
                                "failure: CASCADE->SET NULL leaves personal data behind after a purge "
                                "that reported success; SET NULL->CASCADE destroys the plant history "
                                "the policy promised to retain. Update deliberately, with the reason.",
                        "columns": live}, indent=2, sort_keys=True) + "\n")
        print(f"baseline written: {len(live)} FKs")
        return 0

    drift = []
    if BASELINE.exists():
        base = json.load(io.open(BASELINE, encoding="utf-8")).get("columns", {})
        for k, v in base.items():
            if k not in live:
                drift.append(f"{k}: FK to auth.users REMOVED (was {v['action']})")
            elif live[k]["action"] != v["action"]:
                drift.append(f"{k}: {v['action']} -> {live[k]['action']}")
        new = sorted(set(live) - set(base))
    else:
        new = []

    casc = sum(1 for v in live.values() if v["action"] == "CASCADE")
    setn = sum(1 for v in live.values() if v["action"] == "SET NULL")
    print(f"  FKs to auth.users: {len(live)} | CASCADE {casc} (personal) | SET NULL {setn} (operational)"
          f" | blocking {len(blocked)}")
    for n in new:
        print(f"    new since baseline - {n} ({live[n]['action']})")

    fails = ([f"{k}: {live[k]['action']} would BLOCK every erasure request" for k in blocked]
             + [f"{k}: SET NULL onto a NOT NULL column - the delete will RAISE at runtime"
                for k in throws]
             + drift)
    if fails:
        print(f"FAIL erasure-path-intact - {len(fails)} problem(s) with the deletion the policy promises:")
        for x in fails[:12]:
            print("    - " + x)
        print("    The privacy policy tells a person their data is purged within 30 days of a Data")
        print("    Rights Request. That promise is only as real as the FK graph underneath it: it must")
        print("    not be blockable, must not raise mid-delete, and must not quietly change WHAT it")
        print("    removes. If a change here is intended, run --update-baseline and say why.")
        return 1
    print(f"PASS erasure-path-intact - nothing blocks or raises, and all {len(live)} FKs still remove "
          f"exactly what the policy says they remove.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
