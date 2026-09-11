#!/usr/bin/env python3
"""backfill_fleet_seed_gaps - the rows a fleet hive was never given, found by walking its journeys.

WHY THIS EXISTS (2026-09-09). Walking the Tier-A journeys turned up the same shape three times, always in
the three hives the vehicle-seed arc created and never in the three plant hives it did not:

    hive                          items  inventory_transactions  report_contacts
    Baguio Textile Mills             27         176                     1
    Manila Electronics Assembly      27         133                     1
    Lucena Pharmaceutical Mfg.       27         149                     0   <- contacts only
    Dela Cruz Delivery Fleet          6           0                     0
    Ramos Jeepney Line                5           0                     0
    Tan Delivery Vans                 5           0                     0

Two gaps, each the reason a whole journey archetype could not be true in those verticals:

  J23 "parts exist and have moved" - a fleet hive holds parts and has NEVER MOVED ONE. Nothing was ever
      received, issued against a job, or returned, so inventory.html shows stock that has no history,
      analytics can show no parts spend, and a supervisor cannot answer "where did that filter go".
  J29 "work recorded and a report contact to send it to" - four hives have nobody to send a report TO, so
      report-sender has an empty recipient list and the whole reporting arc dead-ends at its last step.

This is the same class as the missing skill_profiles ([[tools/backfill_skill_profiles.py]]): a vertical
seeded through a path that never called part of the seeder inherits gaps its own lane never notices,
because every page still renders - it just renders nothing, for ever, and only a journey that asks whether
the STORY is true in this hive can see it.

Deterministic, never random: quantities and dates come from a hash of the item id, so re-running writes the
same history and a database diff stays empty. Only hives with ZERO of a thing are touched; a hive that has
its own history is never edited.

    python tools/backfill_fleet_seed_gaps.py --check     # report the gaps, write nothing
    python tools/backfill_fleet_seed_gaps.py             # fill them
"""
import hashlib
import io
import os
import subprocess
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

CONTAINER = os.environ.get("WH_DB_CONTAINER", "supabase_db_workhive")
CHECK = "--check" in sys.argv
LAST_ERR = ""

# ★THIS COMMENT WAS FALSE FOR TWO OF THE FIVE ENTRIES (corrected 2026-09-11). inventory.html writes
# exactly four types - 'use' (1860, issuing a part), 'restock' (1973), 'adjustment' (1665, an edit-driven
# quantity change) and 'add' (1713, initial stock entry) - which is also validate_inventory_integrity's
# VALID_TXN_TYPES, derived from those same lines. It writes NEITHER 'receive' NOR 'adjust'. So this
# seeder was the source of a non-canonical vocabulary in the ledger, and the gate had been red on
# "27 transactions with invalid type ['adjust', 'receive']" ever since: 18 of those rows are this
# script's (11 'adjust' + 7 'receive'), the other 9 came from the 2026-09-09 opening-balance repair
# writing the same misspelling.
# THE TELL WAS IN THE RENDERER: inventory.html:894/896 accepts BOTH spellings of each concept
# ('add'|'restock' for one icon, 'adjust'|'adjustment' for another) - somebody met the drift downstream
# and accommodated it at the display layer instead of at the writer. Widening the gate's vocabulary
# would have been the same mistake a third time; the writers are what had to agree.
TXN_TYPES = ["restock", "use", "restock", "use", "adjustment"]


def psql(sql: str, tries: int = 3) -> str:
    """Retry: this runs on a host that may still have a browser walk on it, and a busy engine is not an
    absent one - the same lesson every prober in tools/ carries.

    ★AND THE RETRY MUST CATCH THE TIMEOUT IT SETS. The first version passed `timeout=180` to
    subprocess.run and caught nothing, so the TimeoutExpired it raised blew straight through the retry
    loop and out of the program - a helper written to survive a busy host, defeated by the one failure a
    busy host actually produces. Measured the first time it ran beside a browser walk.
    """
    global LAST_ERR
    for _ in range(tries):
        try:
            r = subprocess.run(
                ["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-tA",
                 "-v", "ON_ERROR_STOP=1"],
                input=sql, capture_output=True, text=True, timeout=180, encoding="utf-8", errors="replace")
        except (subprocess.TimeoutExpired, OSError) as e:
            LAST_ERR = f"{type(e).__name__}"
            continue
        if r.returncode == 0:
            LAST_ERR = ""
            return (r.stdout or "").strip()
        # ★KEEP THE REASON. Returning "" for every failure made a write that psql REFUSED look identical to
        # a write that returned nothing, so the caller announced success on a row the database had thrown
        # out. The reason is one attribute away; hold it so the caller can print it.
        LAST_ERR = " ".join((r.stderr or "").split())[:200]
    return ""


def h(seed: str, n: int) -> int:
    return int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16) % n


def q(s: str) -> str:
    return s.replace("'", "''")


def main() -> int:
    if not psql("SELECT 1;"):
        print("SKIP backfill-fleet-seed-gaps - local database not reachable (or too busy to answer)")
        return 0

    rows = [r for r in psql(
        "SELECT h.id::text || '|' || h.name || '|' "
        "|| (SELECT count(*) FROM inventory_items i WHERE i.hive_id = h.id) || '|' "
        "|| (SELECT count(*) FROM inventory_transactions t WHERE t.hive_id = h.id) || '|' "
        "|| (SELECT count(*) FROM report_contacts c WHERE c.hive_id = h.id) "
        "FROM hives h ORDER BY h.name;").split("\n") if r.strip()]

    need_txn, need_contact = [], []
    print("  hive                          items  txns  contacts")
    for r in rows:
        hid, name, items, txns, contacts = r.split("|")
        print(f"  {name[:28]:<28}  {items:>5}  {txns:>4}  {contacts:>8}")
        if int(items) > 0 and int(txns) == 0:
            need_txn.append((hid, name))
        if int(contacts) == 0:
            need_contact.append((hid, name))

    # a hive with a connector configured but no record of it ever running - same family, asked HERE so the
    # early return cannot skip it (it did, the first time: the CMMS block sat below this guard and the run
    # reported PASS without ever reaching it)
    need_audit = [(r.split("|")[0], r.split("|")[1]) for r in psql(
        "SELECT h.id::text || '|' || h.name FROM hives h "
        "WHERE EXISTS (SELECT 1 FROM integration_configs c WHERE c.hive_id = h.id) "
        "AND NOT EXISTS (SELECT 1 FROM cmms_audit_log a WHERE a.hive_id = h.id) ORDER BY h.name;"
    ).split("\n") if r.strip()]

    # ★AND THE KNOWLEDGE LOOP NEEDS SOMEBODY TO HAVE ASKED SOMETHING (added 2026-09-09, found walking J7).
    # Four hives carry a real community - Manila 50 posts, Lucena 37, Baguio 24, Dela Cruz 3 - and Ramos
    # Jeepney Line and Tan Delivery Vans have ZERO posts and ZERO replies. So J7's story ("a question, its
    # best answer, and the standing that answer earns") has nothing to be about there, and community.html
    # shows those two hives an empty room. One real question with an accepted answer per hive, written as
    # that hive's own people would ask it - a jeepney line asks about jeepney things.
    need_community = [(r.split("|")[0], r.split("|")[1]) for r in psql(
        "SELECT h.id::text || '|' || h.name FROM hives h "
        "WHERE NOT EXISTS (SELECT 1 FROM community_posts p WHERE p.hive_id = h.id AND p.deleted_at IS NULL) "
        "OR NOT EXISTS (SELECT 1 FROM community_replies r WHERE r.hive_id = h.id) ORDER BY h.name;"
    ).split("\n") if r.strip()]

    if not need_txn and not need_contact and not need_audit and not need_community:
        print("\nPASS backfill-fleet-seed-gaps - every hive that holds parts has moved some, every hive has "
              "somebody to send a report to, and every configured connector has a sync on the record")
        return 0
    if need_audit:
        print(f"\n  {len(need_audit)} hive(s) have a connector configured that has never run: "
              f"{', '.join(n for _, n in need_audit)}")

    print(f"\n  {len(need_txn)} hive(s) hold parts that have never moved: {', '.join(n for _, n in need_txn) or '-'}")
    print(f"  {len(need_contact)} hive(s) have nobody to send a report to: {', '.join(n for _, n in need_contact) or '-'}")
    if CHECK:
        print("\n  --check: nothing written.")
        return 1

    made_txn = 0
    for hid, name in need_txn:
        # qty_on_hand, not qty - read from the baseline migration rather than guessed, because a wrong
        # column name here would have failed silently into "0 items" and looked like a clean run
        items = [i for i in psql(
            f"SELECT id || '|' || coalesce(qty_on_hand::text, '0') FROM inventory_items WHERE hive_id = '{hid}' ORDER BY id;"
        ).split("\n") if i.strip()]
        who = psql(f"SELECT worker_name FROM hive_members WHERE hive_id = '{hid}' AND status = 'active' ORDER BY worker_name LIMIT 1;") or "Supervisor"
        for item in items:
            iid, qty = item.split("|")[0], item.split("|")[1]
            try:
                on_hand = float(qty)
            except ValueError:
                on_hand = 10.0
            # a short, plausible history per part: received, then used against jobs, ending at the stock
            # the item actually reports, so the ledger and the count agree rather than contradict
            running = on_hand
            legs = []
            for k in range(3):
                kind = TXN_TYPES[h(iid + str(k), len(TXN_TYPES))]
                step = 1 + h(iid + "q" + str(k), 4)
                legs.append((kind, step))
            for k, (kind, step) in enumerate(reversed(legs)):
                # 'receive' is gone from TXN_TYPES (see the note there - it was never a type this
                # platform writes); 'restock' and 'add' are the two that INCREASE stock, and 'use' /
                # 'adjustment' decrease it, which is the same signing this line had before.
                delta = step if kind in ("restock", "add") else -step
                before = running - delta
                tid = "txn-" + hashlib.sha256((iid + str(k)).encode()).hexdigest()[:16]
                days = 5 + h(iid + "d" + str(k), 90)
                out = psql(
                    "INSERT INTO inventory_transactions (id, worker_name, item_id, type, qty_change, "
                    "qty_after, note, job_ref, created_at, hive_id) VALUES ("
                    f"'{tid}', '{q(who)}', '{q(iid)}', '{kind}', {delta}, {running}, "
                    f"'seeded history so this hive''s parts have a past', '', "
                    f"now() - interval '{days} days', '{hid}') ON CONFLICT (id) DO NOTHING RETURNING id;")
                if out:
                    made_txn += 1
                running = before
        print(f"    + {name}: {len(items)} part(s) now have a movement history")

    # ★AND THE CMMS SYNC STORY NEEDS A SYNC THAT HAPPENED (added 2026-09-09, found walking J15). Every hive
    # now holds an integration_config, but only Baguio Textile Mills has any cmms_audit_log rows - 41 of
    # them, left by a real import in July. The other five have a connector configured and no record that it
    # has ever run, so integrations.html can show a connection but never what it DID, and the J15 story
    # ("plant-connections -> cmms-sync -> ... -> audit-log") dead-ends at its last step. One import batch
    # per hive, shaped like the real Baguio row, is enough for the story to be about something.
    made_audit = 0
    for hid, name in [(h.split("|")[0], h.split("|")[1]) for h in psql(
        "SELECT h.id::text || '|' || h.name FROM hives h "
        "WHERE EXISTS (SELECT 1 FROM integration_configs c WHERE c.hive_id = h.id) "
        "AND NOT EXISTS (SELECT 1 FROM cmms_audit_log a WHERE a.hive_id = h.id) ORDER BY h.name;"
    ).split("\n") if h.strip()]:
        who = psql(f"SELECT worker_name FROM hive_members WHERE hive_id = '{hid}' AND role = 'supervisor' "
                   "AND status = 'active' ORDER BY worker_name LIMIT 1;") or "Supervisor"
        kind = psql(f"SELECT system_type FROM integration_configs WHERE hive_id = '{hid}' LIMIT 1;") or "generic"
        n = 2 + h(hid, 6)
        out = psql(
            "INSERT INTO cmms_audit_log (hive_id, batch_id, operation, entity_type, system_type, "
            "rows_attempted, rows_written, rows_failed, quality_score, triggered_by, created_at) VALUES "
            f"('{hid}', 'import-{abs(hash(hid)) % 10**13}', 'file_import', 'work_order', '{kind}', "
            f"{n}, {n}, 0, '{{\"pct_machine\": 100, \"pct_problem\": 100, \"pct_closed_at\": 50}}'::jsonb, "
            f"'{q(who)}', now() - interval '{6 + h(hid + 'd', 40)} days') RETURNING id;")
        if out:
            made_audit += 1
            print(f"    + {name}: its connector now has a sync on the record ({n} work orders imported)")

    # one real question and its accepted answer per empty hive, in that hive's own trade
    ASKED = {
        "Ramos Jeepney Line": (
            "technical",
            "Our jeepneys are burning through clutch plates faster than the schedule says. "
            "Anyone tracking clutch life by route? The Cubao line seems worse than the others.",
            "Route matters more than mileage for clutch wear - stop-start counts, not kilometres. "
            "We started logging stops per route in the logbook and the pattern showed up in a month. "
            "Move the heavy-stop routes to a shorter PM interval and leave the rest on the standard one."),
        "Tan Delivery Vans": (
            "technical",
            "What is everyone using to decide when to replace van brake pads - kilometres, or thickness? "
            "We keep pulling pads that still had life in them.",
            "Thickness, measured, never kilometres. Kilometres is a planning number; thickness is the "
            "condition. We record the measurement in the logbook at every PM, so the trend tells us which "
            "van is due before the pad is scrap. It cut our pad spend noticeably."),
        "_default": (
            "general",
            "How is everyone recording the small fixes that never make it onto a work order? "
            "Half our real maintenance history is in people's heads.",
            "Log them anyway, even one line. The logbook takes a short entry, and six months later the "
            "pattern in those short entries is what tells you which machine is actually costing you."),
    }
    made_community = 0
    for hid, name in need_community:
        cat, question, answer = ASKED.get(name, ASKED["_default"])
        asker = psql(f"SELECT worker_name FROM hive_members WHERE hive_id = '{hid}' AND status = 'active' "
                     "AND role = 'worker' ORDER BY worker_name LIMIT 1;") \
            or psql(f"SELECT worker_name FROM hive_members WHERE hive_id = '{hid}' AND status = 'active' "
                    "ORDER BY worker_name LIMIT 1;")
        # ★AND A PERSON ANSWERING THEIR OWN QUESTION IS NOT A KNOWLEDGE LOOP. The first run of this block
        # produced "Oscar Ramos asked, Oscar Ramos answered, and the answer was accepted" - because both
        # fleet hives have exactly ONE active member, so asker and answerer resolved to the same person.
        # That reads as fake to anybody who looks, and it proves nothing about the standing an answer earns.
        # A real community is CROSS-HIVE: you ask, and somebody at another plant who has hit it answers.
        # The reply still belongs to the asking hive (community_replies.hive_id is the POST's hive), so the
        # answer is scoped correctly while the voice is genuinely somebody else's.
        answerer = psql(f"SELECT worker_name FROM hive_members WHERE hive_id = '{hid}' AND status = 'active' "
                        f"AND worker_name <> '{q(asker)}' AND role = 'supervisor' ORDER BY worker_name LIMIT 1;") \
            or psql(f"SELECT worker_name FROM hive_members WHERE hive_id = '{hid}' AND status = 'active' "
                    f"AND worker_name <> '{q(asker)}' ORDER BY worker_name LIMIT 1;") \
            or psql("SELECT m.worker_name FROM hive_members m "
                    f"WHERE m.hive_id <> '{hid}' AND m.status = 'active' AND m.role = 'supervisor' "
                    "AND m.worker_name NOT IN (SELECT worker_name FROM marketplace_platform_admins) "
                    "ORDER BY m.worker_name LIMIT 1;")
        if not answerer or answerer == asker:
            print(f"    ! {name}: nobody but the asker could answer - not writing a self-answered question")
            continue
        if not asker:
            print(f"    ! {name}: nobody active to ask or answer")
            continue
        # ★ASK ONCE. The gap test fires on "no posts OR no replies", so a hive that already had a question
        # whose ANSWER failed got a SECOND question on the next run - a duplicate in a two-person community,
        # which is exactly the kind of thing a reader notices and a seeder should never produce. Re-use the
        # unanswered question if one is already there; only ask when the room is genuinely empty.
        pid = psql(f"SELECT p.id FROM community_posts p WHERE p.hive_id = '{hid}' "
                   "AND p.deleted_at IS NULL "
                   "AND NOT EXISTS (SELECT 1 FROM community_replies r WHERE r.post_id = p.id) "
                   "ORDER BY p.created_at LIMIT 1;")
        if not pid:
            pid = psql(
                "INSERT INTO community_posts (hive_id, author_name, content, category, pinned, flagged, "
                "public, mentions, created_at) VALUES "
                f"('{hid}', '{q(asker)}', '{q(question)}', '{cat}', false, false, false, '{{}}', "
                f"now() - interval '{9 + h(hid, 20)} days') RETURNING id;")
        if not pid or "ERROR" in pid:
            print(f"    ! {name}: the question could not be posted: {LAST_ERR}")
            continue
        # ...and the ANSWER is ACCEPTED, because J7's story is about the standing a good answer earns.
        # ★CHECK THE WRITE BEFORE ANNOUNCING IT. The first version fired this INSERT and printed
        # "asked, answered, and the answer was accepted" without looking at the result - so when the reply
        # did not land, the tool reported a knowledge loop that did not exist and the gap stayed open while
        # the run said PASS. A claim with no check behind it is the defect this whole program hunts.
        rid = psql(
            "INSERT INTO community_replies (post_id, hive_id, author_name, content, is_accepted, "
            "accepted_by, accepted_at, created_at) VALUES "
            f"('{pid}', '{hid}', '{q(answerer)}', '{q(answer)}', true, '{q(asker)}', "
            f"now() - interval '{4 + h(hid + 'a', 6)} days', "
            f"now() - interval '{9 + h(hid + 'r', 7)} days') RETURNING id;")
        if not rid or "ERROR" in rid:
            print(f"    ! {name}: the question was posted but the ANSWER did not land - "
                  f"a question with no answer is not the loop J7 asks about: {LAST_ERR}")
            continue
        made_community += 1
        print(f"    + {name}: {asker} asked, {answerer} answered, and the answer was accepted")

    made_contact = 0
    for hid, name in need_contact:
        sup = psql(f"SELECT worker_name FROM hive_members WHERE hive_id = '{hid}' AND role = 'supervisor' "
                   "AND status = 'active' ORDER BY worker_name LIMIT 1;") or "Plant Supervisor"
        slug = "".join(c for c in name.lower() if c.isalnum())[:20] or "hive"
        out = psql(
            "INSERT INTO report_contacts (hive_id, name, email, label) VALUES "
            f"('{hid}', '{q(sup)}', '{slug}.reports@example.invalid', 'Team') RETURNING id;")
        if out:
            made_contact += 1
            print(f"    + {name}: reports can now be sent to {sup}")

    print(f"\nOK backfill-fleet-seed-gaps - wrote {made_txn} inventory movement(s) and {made_contact} report "
          f"contact(s). Every hive that holds parts can now show where they went, and every hive has "
          f"somebody to send a report to.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
