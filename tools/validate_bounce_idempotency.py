#!/usr/bin/env python3
"""bounce-idempotency — T112: one delivery id, one bounce row (2026-08-26).

THE DEFECT. resend-webhook-receiver ended in a bare INSERT into automation_log.
Svix (which Resend uses) delivers AT LEAST ONCE and retries on any non-2xx or
timeout, and it carries a stable delivery id in the `svix-id` header for exactly
this purpose — which the function read to verify the signature and then threw
away. A retried delivery wrote a SECOND bounce row. Not cosmetic: the
report-sender bounce surface would list one failed send twice, and any count
built on those rows over-reports how bad deliverability is — a metric that lies
in the alarming direction, which is the direction that gets acted on.

FOUR ASSERTIONS, driven against the real table:

  1. a first bounce row is accepted;
  2. the SAME svix id is REFUSED (23505) — the retry case;
  3. a DIFFERENT svix id is accepted — the guard is specific, not a blanket
     "one bounce per hive" that would swallow real repeat failures;
  4. two writers racing on the same id in CONCURRENT transactions end with
     exactly one row.

★4 IS WHY THIS IS AN INDEX AND NOT A CHECK-BEFORE-INSERT. A SELECT-then-INSERT
is a check-and-act race that two near-simultaneous retries both pass; this
codebase already carries a scar from that exact shape. The concurrency case is
the assertion that distinguishes the two designs, so it is measured rather than
argued.

★WHAT THIS DOES NOT CLAIM. The HTTP round trip — a real signed webhook reaching
the deployed function twice — stays owed: the function is not served locally and
its signing secret is Ian's to set. This gate proves the mechanism that makes
the endpoint idempotent under any timing, which is the half that a live smoke
could not prove anyway (a live test shows one duplicate handled; the index shows
none can ever be stored).

Probe rows are marked and deleted, and the deletion is re-counted.

Usage: python tools/validate_bounce_idempotency.py
"""
import io
import shutil
import subprocess
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

MARK = "WH-T112-PROBE"


def psql(sql: str, check: bool = True):
    r = subprocess.run(
        ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-c", sql],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
    )
    out = (r.stdout or "") + (r.stderr or "")
    if check and r.returncode != 0:
        raise RuntimeError(out.strip()[:200])
    return out.strip(), r.returncode


def insert(svix_id: str, check: bool = True):
    return psql(
        "INSERT INTO automation_log (job_name, status, detail) VALUES ("
        f"'report_email_bounce', 'failed', 'Report to {MARK}@example.com bounced "
        f"[resend_id=msg_{svix_id}] [svix_id={svix_id}]')", check=check)


def count_rows():
    out, _ = psql(f"SELECT count(*) FROM automation_log WHERE detail LIKE '%{MARK}%'")
    return int(out or 0)


def cleanup():
    psql(f"DELETE FROM automation_log WHERE detail LIKE '%{MARK}%'")
    return count_rows() == 0


def main() -> int:
    if not shutil.which("docker"):
        print("SKIP bounce-idempotency — docker absent (the index is the oracle)")
        return 0
    try:
        psql("SELECT 1")
    except Exception:
        print("SKIP bounce-idempotency — local database not reachable")
        return 0

    if count_rows():
        print(f"ABORT bounce-idempotency — {count_rows()} leftover probe row(s); refusing to measure on dirty state")
        return 1

    # the index itself must exist — without it every assertion below would pass vacuously on an
    # empty table and the gate would be measuring nothing
    idx, _ = psql("SELECT count(*) FROM pg_indexes WHERE indexname = 'automation_log_bounce_svix_once'")
    v = {"index_present": idx == "1"}

    try:
        _, rc1 = insert("wht112a")
        v["first_accepted"] = rc1 == 0 and count_rows() == 1

        out2, rc2 = insert("wht112a", check=False)
        v["retry_refused"] = rc2 != 0 and "23505" in out2 or "duplicate key" in out2.lower()
        v["retry_left_one_row"] = count_rows() == 1

        _, rc3 = insert("wht112b")
        v["different_id_accepted"] = rc3 == 0 and count_rows() == 2

        # 4 — two CONCURRENT transactions on one id. Both open, both insert, both commit: the
        # index decides, not the timing. A check-before-insert would let both through here.
        concurrent = (
            "BEGIN; INSERT INTO automation_log (job_name, status, detail) VALUES "
            f"('report_email_bounce','failed','Report to {MARK}@example.com bounced [svix_id=wht112c]'); "
            "COMMIT;"
        )
        procs = [subprocess.Popen(
            ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-c", concurrent],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8", errors="replace") for _ in range(2)]
        codes = [p.wait(timeout=60) for p in procs]
        out, _ = psql(f"SELECT count(*) FROM automation_log WHERE detail LIKE '%wht112c%'")
        v["race_wrote_one"] = out == "1"
        v["race_one_writer_refused"] = sorted(codes) == [0, 1]
    except Exception as e:
        v["error"] = str(e)[:180]
    finally:
        v["cleanup"] = cleanup()

    for k, val in v.items():
        print(f"  {k:<26} {val}")

    ok = all(v.get(k) for k in (
        "index_present", "first_accepted", "retry_refused", "retry_left_one_row",
        "different_id_accepted", "race_wrote_one", "race_one_writer_refused", "cleanup"))
    if not ok:
        print("FAIL bounce-idempotency — a retried webhook can write a second bounce row, or the "
              "guard is refusing rows it should accept. See mig 20260826000004.")
        return 1
    print("PASS bounce-idempotency — one delivery id, one bounce row, even when two retries race.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
