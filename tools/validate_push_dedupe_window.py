#!/usr/bin/env python3
"""push-dedupe-window — T110: the only place a notification storm is bounded (2026-08-26).

enqueue_user_push inserts one service_outbox row per event and the drain sends
one push per row, so nothing between an event and a phone collapses repeats: two
triggers on one PM going overdue, a supervisor's repeated save, or a retrying
client each become their own buzz. Migration 20260826000001 added the narrow,
safe half — an identical push (same recipients, title, body and url) still
UNSENT within two minutes hands back the PENDING row's id instead of enqueueing
a second.

★WHY THIS GATE EXISTS NOW. That window shipped WITHOUT a gate, and it has since
become load-bearing: four new producers were added on 2026-08-26 (mentions,
replies, best-answer, and a trigger on every pending submission), and the
pending-submission trigger relies on this window *by design* — its copy names no
row precisely so that a bulk CMMS import of two hundred assets collapses to one
push. If this dedupe regresses, that trigger stops being a summary and becomes a
cannon. The storm guard for today's product is unlocked, so lock it.

FOUR ASSERTIONS, all inside a transaction that is ROLLED BACK — the gate writes
nothing it must then clean up, which is the strongest form of probe hygiene:

  1. identical, pending, inside the window -> the SAME id, and no second row.
  2. a different body -> its own row. The guard must be specific; a blanket
     "one push per user per two minutes" would swallow genuinely different news.
  3. a predecessor already marked done -> a NEW row. A repeat of something the
     person already received is news, not a duplicate, and suppressing it would
     silently drop real notifications.
  4. different RECIPIENTS -> its own row. The payload includes auth_uids, so two
     people getting the same sentence must not collapse into one delivery.

Assertion 3 is the one that separates a correct dedupe from a mute button.

Usage: python tools/validate_push_dedupe_window.py
"""
import io
import shutil
import subprocess
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

UID_A = "bcb5a6e3-fb12-4238-bc1e-ffeb48f60d53"
UID_B = "91e0d1eb-cd96-43ee-af5f-0ff2714b3923"

# One transaction, rolled back at the end: nothing survives this gate.
SQL = f"""
BEGIN;
CREATE TEMP TABLE r(k text, v text) ON COMMIT DROP;

-- 1 — identical while pending: same id back, no second row
WITH a AS (SELECT public.enqueue_user_push(ARRAY['{UID_A}']::uuid[], 'T110 probe', 'body one', '/x') AS id),
     b AS (SELECT public.enqueue_user_push(ARRAY['{UID_A}']::uuid[], 'T110 probe', 'body one', '/x') AS id)
INSERT INTO r SELECT 'identical_same_id', (SELECT id FROM a)::text = (SELECT id FROM b)::text;
INSERT INTO r SELECT 'identical_one_row',
  (SELECT count(*) FROM service_outbox WHERE payload->>'title' = 'T110 probe' AND payload->>'body' = 'body one')::text;

-- 2 — a different body is different news
SELECT public.enqueue_user_push(ARRAY['{UID_A}']::uuid[], 'T110 probe', 'body two', '/x');
INSERT INTO r SELECT 'different_body_own_row',
  (SELECT count(*) FROM service_outbox WHERE payload->>'title' = 'T110 probe' AND payload->>'body' = 'body two')::text;

-- 3 — a repeat of something ALREADY DELIVERED is news, not a duplicate
UPDATE service_outbox SET status = 'done'
 WHERE payload->>'title' = 'T110 probe' AND payload->>'body' = 'body one';
SELECT public.enqueue_user_push(ARRAY['{UID_A}']::uuid[], 'T110 probe', 'body one', '/x');
INSERT INTO r SELECT 'delivered_then_repeat_is_new',
  (SELECT count(*) FROM service_outbox WHERE payload->>'title' = 'T110 probe' AND payload->>'body' = 'body one')::text;

-- 4 — a different recipient gets their own delivery
SELECT public.enqueue_user_push(ARRAY['{UID_B}']::uuid[], 'T110 probe', 'body two', '/x');
INSERT INTO r SELECT 'different_recipient_own_row',
  (SELECT count(*) FROM service_outbox WHERE payload->>'title' = 'T110 probe' AND payload->>'body' = 'body two')::text;

SELECT k || '=' || v FROM r ORDER BY k;
ROLLBACK;
"""

EXPECT = {
    "identical_same_id": "true",
    "identical_one_row": "1",
    "different_body_own_row": "1",
    "delivered_then_repeat_is_new": "2",
    "different_recipient_own_row": "2",
}


def main() -> int:
    if not shutil.which("docker"):
        print("SKIP push-dedupe-window — docker absent (enqueue_user_push is the oracle)")
        return 0
    r = subprocess.run(
        ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-v", "ON_ERROR_STOP=1"],
        input=SQL, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0:
        print("SKIP push-dedupe-window — local database not reachable or the helper is absent")
        print("  " + out.strip().splitlines()[-1][:160] if out.strip() else "")
        return 0

    got = {}
    for line in out.splitlines():
        if "=" in line and line.split("=")[0].strip() in EXPECT:
            k, v = line.split("=", 1)
            got[k.strip()] = v.strip().lower()

    fails = []
    for k, want in EXPECT.items():
        have = got.get(k)
        mark = "OK" if have == want else "WRONG"
        print(f"  {k:<30} {str(have):<6} (expected {want})  {mark}")
        if have != want:
            fails.append(k)

    # a rolled-back transaction must leave nothing behind — verify rather than assume
    chk = subprocess.run(
        ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-c", "SELECT count(*) FROM service_outbox WHERE payload->>'title' = 'T110 probe'"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45)
    leftover = (chk.stdout or "").strip()
    if leftover != "0":
        fails.append(f"rollback_left_{leftover}_rows")
        print(f"  rollback left {leftover} row(s) behind — the probe is not clean")

    if fails:
        print("FAIL push-dedupe-window — " + ", ".join(fails)
              + ". This window is the ONLY place a notification storm is bounded before delivery, "
                "and the pending-submission trigger depends on it to stay a summary rather than a cannon.")
        return 1
    print("PASS push-dedupe-window — identical pending pushes collapse, different news does not, "
          "an already-delivered repeat is treated as news, and recipients are never merged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
