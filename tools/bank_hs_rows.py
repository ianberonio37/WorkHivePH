"""bank_hs_rows.py - bank Wave HS rows (the hive at thirty) on the walk their lens names (2026-10-30).

An HS row closes "walked on <page> against a 30-member hive with a receipt, the fix landed, a gate holds it". The walk is
tools/prove_hive_scale_lists.mjs (gate hive-scale-lists): two browser contexts signed in as a worker and a supervisor of
the seeded full hive, every list item read at phone-390 and desktop-1280, every action an item offers replayed as that
person against the database. Its receipt is hive_scale_lists_report.json; this banks the rows that receipt passed.

A row is banked only when ALL hold:
  1. the receipt is this walk's own (not a --teeth run), read against the full hive (>= 30 members), under 3 hours old;
  2. the row is in the receipt and passed, and it is an HS row of lens L1 or L2 that is not already locked;
  3. with --run, the gate is re-run first on the pages named, and a red gate banks nothing.
A failing or missing row is left as it is and printed with the reason.

    python tools/bank_hs_rows.py [--run community.html ...] [--dry]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import bank_sl_walk as bsw  # noqa: E402

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPORT = ROOT / "hive_scale_lists_report.json"
PROVER = "tools/prove_hive_scale_lists.mjs"
# W1 (two members change the same item at once) has its own prover and receipt - a database replay, not a page reading
W_REPORT = ROOT / "hive_scale_writes_report.json"
W_PROVER = "tools/prove_hive_scale_writes.mjs"
# ...and its BROWSER half: two people, two browsers, the page's own controls
R_REPORT = ROOT / "hive_scale_races_report.json"
R_PROVER = "tools/prove_hive_scale_races.mjs"
MAX_AGE_H = 3
# W2 (a shift of thirty writes at once) has two receipts: the BURST (29 members' writes at once, then staggered, through
# PostgREST as each member) and the SHIFT (the page a person then opens, read at phone-390 and desktop-1280)
B_REPORT = ROOT / "hive_scale_burst_report.json"
B_PROVER = "tools/prove_hive_scale_burst.mjs"
S_REPORT = ROOT / "hive_scale_shift_report.json"
S_PROVER = "tools/prove_hive_scale_shift.mjs"
FIXED_W2 = {
    "HS464": "FOUND AND FIXED: at once, 4 of 29 new projects saved - the page asks generate_project_code for the next code "
             "and then inserts, and the function answered MAX(issued)+1, so everyone who asked before anyone saved got the SAME "
             "code and projects_code_per_hive refused 24 of them (and the person was told the project was not created). The "
             "next number now comes from a counter row under its own lock, never behind the codes already issued (migration "
             "20261030000009); at once 29/29. Probe project-manager__two_presses_two_codes (teeth: fails with MAX+1 put back). "
             "And the shared daily cap told a member 'You have reached today's free limit' when the HIVE's limit was spent by "
             "the others - it now says 'Your hive has reached ...' (20261030000008, probe project-manager__a_hive_limit_is_not_yours).",
    "HS456": "FOUND AND FIXED: at once, 1 of 29 change orders saved - generate_change_order_number answered MAX+1 and "
             "project_change_orders_co_number refused 28. Same counter fix (migration 20261030000009), at once 29/29; the "
             "function was also callable by anon and PUBLIC with no membership check, and is now a member-of-the-project's-hive "
             "definer (probe: an outsider is refused). The hive cap's sentence names the hive (20261030000008).",
    "HS439": "The shift is the page's own upsert on worker_name: the hive's two sellers edited their row, the other 27 became "
             "sellers by it; each member's profile holds their own handle and no teammate's.",
    "HS428": "The logbook's PM panel for the tank read the task as 'next: <date>' from the shift's newest completion (it was 83 "
             "days overdue before), the same words the view gives; the burst's completions pay XP and queue an embedding - "
             "both put back exactly after each run.",
    "HS412": "FOUND AND FIXED: a supervisor importing a plant-sized register (150 machines) landed NONE - an import chunk is one "
             "statement, the daily row caps count the rows before it in the same statement, so row 101 met the person's limit "
             "of 100 and Postgres refused all 150; the screen said '150 rows failed. Check console for details.' (walked on the "
             "committed page: 0 of 150). integrations.html now splits a chunk a limit refuses until every row that fits has "
             "landed, writes the CMMS ledger only for those, and says '<n> assets were not imported: <the limit's own sentence> "
             "The <n> imported are kept. Importing the same file again adds only the ones not yet in.' Walked after the shift: "
             "the first supervisor 99 of 150 (her own 100, verified spent), the second 71 of 150 (the hive's 200, which the shift "
             "and the first import spent, verified). Teeth: prove_hive_scale_shift.mjs --teeth walks the committed page and fails. "
             "Gate cmms-import-rollback still passes. Whether a supervisor's CMMS import should count against the free daily "
             "limits at all is a pricing question, raised to Ian beside the logbook's 200/day.",
    "HS414": "Same import fix (integrations.html lands what fits and says the limit's sentence); 150 parts per supervisor fit "
             "under the person's 200 and the hive's 500, so both imports landed whole after the shift, the screen matching.",
    "HS416": "Same import fix; the work-order import counts against this hive's logbook quota (20,000 / 8,000 a person), so "
             "both 150-order imports landed whole after the shift, and the ledger rows of any order the logbook refuses are "
             "taken back, so the same file again brings it in.",
    "HS418": "Same import fix: a PM program import met the person's limit of 80 for each supervisor (79 landed - one of their "
             "80 was the shift's - verified spent), and the screen said so; a PM import adds programs fresh each time, so it "
             "says to import the rest in a file of their own rather than the same file again (which would add the first 79 twice).",
    "HS394": "The hive's alert hub held 14 alerts, so the shift's 29 marks cycled through them: an alert keeps ONE record per "
             "hive (written insert-unless-present - HS393's fix), so 14 rows is every write accounted for, at once and "
             "staggered, with none refused. Both readers' feeds showed all 14 dimmed, each 'Seen by' the member who acted "
             "first; the 15 later marks replaced none.",
    "HS445": "A member cannot self-publish (guard_marketplace_listing_status): the shift's 29 were submitted as drafts, the "
             "review published them, and the marketplace listed all 29 newest first across its 24-a-page Load More.",
}
# what the browser races found and fixed, each reproduced failing before its fix (the HEAD page served for the walk)
FIXED_RACE = {
    "HS421": "FIXED: inventory.html submitPart took its guard's snapshot (updated_at and the count) from the LIVE cache, which "
             "the realtime feed refreshes - so a second supervisor's save reached the cache first, the guard matched THEIR stamp "
             "and this form silently overwrote their bin with 'Part updated.' (walked failing before the fix, both pairings), and "
             "an untouched count undid a teammate's use through inventory_adjust. The snapshot is now taken when the form opens.",
    "HS461": "FIXED: the second supervisor was told 'Something here already uses that name or code ... change it to something "
             "different' - advice for a form with nothing to change; saveRole now says '<name> already has the <role> role on "
             "this project - another supervisor assigned it while this form was open. Nothing more to do.'",
    "HS427": "FIXED: logbook's PM completions were one atomic batch, so a task the person had already completed today refused "
             "EVERY ticked task, and the toast said 'Its PM tasks did NOT record, so those PMs still count as due' - false for the "
             "one already done (walked on HEAD: that sentence beside '1 PM task -> compliance'). Each task is written alone now "
             "and told by kind. And a recognised refresh-retry ('no duplicate created') went on to write the PM completions and "
             "run the parts deduction again - a retry took the same parts off the shelf twice; it now stops there.",
    "HS419": "FIXED: the offline machine merge minted a FRESH uuid each run, so two tabs or devices merging the same local list "
             "each wrote a copy (walked on HEAD: 2 rows in both pairings); the id is now a function of the account and the tag, "
             "upserted with ignoreDuplicates - 1 row.",
    "HS436": "FIXED: the conflict sentence said 'Someone else saved this listing' - only the owner may edit a listing (the policy "
             "asks the account), so the earlier save was theirs from another tab or device; it now says so.",
    "HS411": "FIXED copy: '1 assets are in your Asset Hub' -> '1 asset is in your Asset Hub'.",
    "HS413": "FIXED copy: '1 inventory items are' -> '1 inventory item is'.",
    "HS415": "FIXED copy: '1 work orders are in your Logbook, and they count' -> '1 work order is ..., and it counts'.",
}

# what each row's walk found and fixed, said once per row (the receipt holds the readings; this is the change)
FIXED = {
    "HS100": "FOUND AND FIXED: a worker could publish their own post to every hive and a worker's edit un-shared a post "
             "their supervisor had shared (tg_community_posts_moderation_fields now holds `public` for members on insert "
             "and update, as SECURITY INVOKER so publish_service_showcase still publishes; community.html's worker save "
             "no longer sends `public`); a supervisor could rewrite a member's words under the member's name (a post's "
             "content, category and mentions are now its author's); a worker could not report an announcement - the "
             "announcement guard refused the report's flag (it now fires only when a post BECOMES one). Migrations "
             "20261030000001/2; probes community__sharing_is_the_supervisors + community__a_posts_words_are_its_authors.",
    "HS121": "FIXED: the reason line said the stored code ('unsafe'); it now says the reporter's words ('Unsafe or wrong "
             "information'), read off the report form's own options.",
    "HS160": "FOUND AND FIXED: a PM card said only a time of day ('04:41 PM') beside job cards saying '3d ago', so a PM done "
             "weeks ago read as today's; buildPMCard now uses the feed's own timeAgo.",
    "HS211": "FOUND AND FIXED: an asset's part uses and its fault history said nothing of who - 50 uses by 24 members read "
             "as nobody's - and dated each with toLocaleDateString(undefined), the phone's locale (10/3 is March on a "
             "US-locale phone). logbook.html now reads worker_name on both and says 'Taken by' / 'Logged by', dated with "
             "whFmtDate. The walk needed the full hive's asset register, which the seed lacked: full_hive.py now registers "
             "its ten machines and links every entry and part to them (existing rows linked once, triggers off).",
    "HS187": "FOUND AND FIXED: a hive part's Transaction History was the VIEWER'S movements only - the page reads "
             "transactions .or(_MINE()) - so Joel Cruz saw 8 of the hive's 220 movements and a shared part's 'Stock after' "
             "jumped wherever a teammate had moved stock, under rows built to say 'by <name>' that never got another "
             "name. The detail now reads that part's own newest 20 across the hive (_loadItemHistory), keeping a movement "
             "still in the offline queue; walked: 8 movements by 8 members.",
    "HS59": "FOUND AND FIXED: a failure mode read created_by / approved_by / created_at and showed none, so a supervisor "
            "asked to approve one could not tell whose judgement it was; each row now says 'proposed by X · date; approved "
            "by Y · date'. The full hive held no reliability record - full_hive.py now seeds two modes per machine from six "
            "proposers, most approved (trail attributed to the proposer).",
    "HS60": "FOUND AND FIXED: rcm_fmea_modes_write let ANY active member write ANY mode - measured as Joel Cruz (worker): "
            "rewrote another member's APPROVED mode (severity, wording; still marked approved), rewrote and deleted their "
            "pending ones. tg_rcm_fmea_modes_member_scope (migration 20261030000003): a supervisor changes any mode, a "
            "member only one they proposed while it waits for approval. Probe asset-hub__a_failure_mode_is_its_proposers "
            "(8 expectations, teeth: fails with the guard dropped).",
    "HS45": "FOUND AND FIXED: the machine detail's marketplace card matched listings by category ILIKE iso_class - "
            "listings are filed Pumps / Compressors / VFDs, machines Mechanical / Electrical - so 83 of the platform's "
            "machines matched nothing and a crude pump never saw a pump for sale; it now matches what the machine is (from "
            "its name and tag), keeps the discipline as a fallback, and each listing says when it was listed.",
    "HS32": "The approval queue walked on a machine the worker submitted through the API (an insert as the member, the "
            "register form's write); the supervisor's Approve / Reject replayed and taken, the worker shown no queue and "
            "refused by tg_guard_approval.",
    "HS321": "FOUND AND FIXED: the link picker THREW ('Assignment to constant variable') once a hive held more than 50 "
             "logbook entries - loadLinkOptions trimmed a `const { data }` - so a thirty-member hive could link no logbook "
             "entry or PM to a project; and each option read 'BRM-P-101: Seal leak' with no who or when, dozens alike, saved "
             "as the link's name. Now `let`, and every option says who and when (FD1a date). New static gate "
             "const-not-reassigned (validate_const_not_reassigned.py, self-test plants the shape; it finds the HEAD bug).",
    "HS335": "FOUND AND FIXED with HS321: the PM option read 'PM 10/3/2026' in the phone's locale with no machine or person "
             "(and the picker threw past 50); it now names the machine, who and when - 50 options, 50 distinct.",
    "HS300": "FOUND AND FIXED: a calculation option said its type and project only; it now says who ran it and when. The "
             "full hive's engineers' calculations are seeded (12, two disciplines).",
    "HS307": "FOUND AND FIXED: the project, scope and role owner pickers offered Rodel Ignacio, who LEFT the hive - the read "
             "promised 'active membership' in its comment and never filtered it. New work goes to active members (29); "
             "the owner filter still finds a departed member's projects (30).",
    "HS356": "FOUND AND FIXED: a project's own team could not read its roster - project_roles_supervisor_all is FOR ALL, so "
             "the safety officer on 'Instrument air upgrade' saw only the owner. Migration 20261030000004 adds "
             "project_roles_project_member_read (project membership, as tools/tenant_declarations.mjs states) through the "
             "definer helper user_project_ids(); writes stay supervisor-only. Probe project-manager__a_team_reads_its_roster "
             "(fails on the old policy). Walked: a worker on no team reads none; the supervisor reads five, each 'by X <date>'.",
    "HS363": "Walked on projects the seed now gives an owner and dates (every other project on the platform had both; the "
             "full hive's four read 'owner -'), with teams, change orders, progress reports and planned scope.",
    "HS287": "Walked on PM programs the seed now gives tasks (three per machine, the platform's frequency vocabulary) - "
             "the full hive's 220 completions read 'Unknown task' and every card '0 PM tasks'; each completion is linked to "
             "one of its machine's tasks (existing rows once, triggers off). The page was right: task, who, when.",
    "HS167": "FOUND AND FIXED: a CMMS conflict card said SAP's status and WorkHive's but not whose entry the WorkHive side "
             "was, or when it was logged - and offered 'Use SAP' on it, a write the logbook refuses for anyone but the "
             "author (the page then told the supervisor so). The card now names who logged it and when; 'Use SAP' is "
             "offered on the viewer's own entry, otherwise it says who sets it. No hive held a synced work order: the seed "
             "now syncs six SAP work orders onto the full hive's machines, three disagreeing - the list's first exercise.",
    "HS168": "FOUND AND FIXED: external_sync_hive_rw let ANY member write the sync table pushed to the plant CMMS (SAP) - "
             "a worker could change, add or delete work orders through the API. Migration 20261030000005: every member "
             "reads, only a supervisor writes; the CMMS edge functions run as the service role. Probe "
             "integrations__only_a_supervisor_writes_the_cmms_sync (fails on the old policy).",
    "HS24": "FOUND AND FIXED: a low-stock alert's dismissal key was the part's NAME ('stock:' + part_name) - two bins of a "
            "same-named part shared it, so handling or seeing one bin's alert silently hid the other's (the dismissal filter "
            "and the seen-mark match on the key). The key is now the part's id. Walked with a second same-named bin of an "
            "at-risk part (the fixture a plant really has): 3 alerts, 3 distinct keys.",
    "HS370": "FOUND AND FIXED: the report's project chooser listed code, name and status - not whose project or when it "
             "last moved, though the read fetched updated_at; it now says the owner and 'updated <when>'. The seed dated each "
             "project's last update to its latest progress report (a backfill had stamped all four 'updated 34m ago').",
    "HS66": "MEASURED, not assumed: the census counted this ordered read inside buildSystemPrompt, whose call was removed (K1, 2026-07-12) - every request the page sends on load was captured and no list of the relation is read or drawn, so nothing of the other members' work enters the assistant here. The dead function still holds the reads (a cleanup in the queue).",
    "HS67": "MEASURED, not assumed: the census counted this ordered read inside buildSystemPrompt, whose call was removed (K1, 2026-07-12) - every request the page sends on load was captured and no list of the relation is read or drawn, so nothing of the other members' work enters the assistant here. The dead function still holds the reads (a cleanup in the queue).",
    "HS73": "MEASURED, not assumed: the census counted this ordered read inside buildSystemPrompt, whose call was removed (K1, 2026-07-12) - every request the page sends on load was captured and no list of the relation is read or drawn, so nothing of the other members' work enters the assistant here. The dead function still holds the reads (a cleanup in the queue).",
    "HS74": "MEASURED, not assumed: the census counted this ordered read inside buildSystemPrompt, whose call was removed (K1, 2026-07-12) - every request the page sends on load was captured and no list of the relation is read or drawn, so nothing of the other members' work enters the assistant here. The dead function still holds the reads (a cleanup in the queue).",
    "HS80": "MEASURED, not assumed: the census counted this ordered read inside buildSystemPrompt, whose call was removed (K1, 2026-07-12) - every request the page sends on load was captured and no list of the relation is read or drawn, so nothing of the other members' work enters the assistant here. The dead function still holds the reads (a cleanup in the queue).",
    "HS81": "MEASURED, not assumed: the census counted this ordered read inside buildSystemPrompt, whose call was removed (K1, 2026-07-12) - every request the page sends on load was captured and no list of the relation is read or drawn, so nothing of the other members' work enters the assistant here. The dead function still holds the reads (a cleanup in the queue).",
    "HS252": "FOUND AND FIXED: a marketplace listing card said what, where, price and seller - never when it was listed, though the read fetched created_at; a two-month-old part may be gone. Each card now says 'listed <when>'.",
    "HS232": "FOUND AND FIXED with HS252: a seller profile's listing cards said what and where, never when; each now says 'listed <when>'. Walked on Joel Cruz's profile - the seed now has two members selling the plant's surplus.",
    "HS238": "Walked on the seller inbox the seed now holds: Joel Cruz (worker) and Ernesto Villareal (supervisor) sell five surplus parts, and 17 inquiries came from 13 buyers (teammates and outside buyers), some answered - each named and dated.",
    "HS245": "MEASURED by request capture: the provider profile is read only by the viewer's own ids (my_service_provider_ids); Joel Cruz is now a freelance provider in the seed, so the read is exercised, and no other provider is asked for.",
    "HS1": "MEASURED by request capture: the achievements standing card reads only the viewer's own provider profile (Joel Cruz, seeded as a freelance provider); the supervisor, not a provider, reads none.",
    "HS393": "FOUND AND FIXED: an alert dismissal was an upsert on (hive, alert) - when two members acted on one alert the second silently REPLACED the first's record and actor, both were told 'recorded under your name', both wrote an audit row, and the first one's Undo deleted the second's record. Now insert-unless-present (an expired snooze may be renewed); the second is told who already acted; Undo deletes only one's own record.",
    "HS401": "FOUND AND FIXED: the edit's concurrency guard fired correctly but the composer then CLOSED, throwing away what the author had typed; the text now stays, the snapshot moves to the post as it is, and a second Save is their choice.",
    "HS407": "FOUND AND FIXED: two supervisors removing one member both 'succeeded' and the trail recorded it twice (now: only a member not yet removed; the second is told); 'transfer supervisor and leave' promoted with no status filter and checked only for an error - a removed member could be promoted and the hive left with no active supervisor (now: only an active member, the promotion confirmed before anyone leaves).",
    "HS425": "FOUND AND FIXED: logbook's asset edit wrote the whole form with .eq('id') only - a teammate's edit made while it was open was silently overwritten. It now saves only the row the form was opened on (updated_at snapshot) and says 'Someone changed this asset while you were editing it' with the form kept.",
    "HS457": "FOUND AND FIXED: the scope status button computed the next status from the screen and wrote it unguarded - when a teammate had marked the task done, the tap set it back to pending. It now moves only from the status the person saw, and says who moved it otherwise.",
    "HS415": "FOUND AND FIXED: 'already imported' was a client snapshot taken before the import loop, so two supervisors importing the same CMMS file at once both wrote every work order into the logbook. Each chunk now CLAIMS its new ledger rows (insert-only, the ledger's unique key decides) and writes logbook entries for exactly those.",
    "HS205": "Walked on the asset register the seed now holds (full_hive.py, 2026-10-30): an asset's linked parts.",
    "HS217": "FOUND AND FIXED: in the Team Feed every teammate's entry carried their name and the viewer's own carried "
             "none; it now says 'You'. The detail offers Edit and Delete to the author only, and the database agrees "
             "(logbook_update / wh_trash: auth_uid = auth.uid()).",
    "HS87": "FOUND AND FIXED: the voice trail (ai_audit_log) that audit-log.html shows supervisors was readable through the API by "
            "ANY membership row of ANY status - a worker, and a member who had been deactivated, read the hive's whole voice "
            "trail (the cost log, feedback and agentic traces were narrowed to supervisors on 2026-10-14; this one was left). "
            "Migration 20261030000010: read by the hive's active supervisor or a platform admin. Probe "
            "audit-log__the_voice_trail_is_the_supervisors (teeth: fails with the old policies). Walked: twelve members' voice "
            "actions, each named and dated; a worker is shown 'Supervisors only' and the database returns none.",
    "HS88": "FOUND AND FIXED with HS87: any membership row (a deactivated member's included) could WRITE into the hive's voice "
            "trail under any name - a member could enter a compliance record as their supervisor. Now an active member writes, "
            "and trg_bind_ai_audit_log_actor sets the name to the writer's own (probe: a forged name is stored as Joel Cruz; "
            "the deactivated member is refused). The entries offer a supervisor only Show/Hide details.",
    "HS12": "The page lists no member's item - it totals the hive's AI calls (its reads select no worker_name). Walked against "
            "50 calls by 25 members laid down for the walk: 'AI calls (30d)' read 91, the table's count. The full hive sits "
            "below the page's Stair 2 lock, so the lock was recorded as this hive gets it (a lock card, no figure) and the "
            "totals read with the readiness view answered as Stair 2.",
    "HS18": "Totals only, like HS12: 30 ratings by 20 members laid down; the card read 23 up / 7 down, the table's.",
    "HS140": "FOUND AND FIXED IN THE SEED, not the product: 40 of the full hive's 43 audit rows read 'the platform', stamped "
             "the seed day - the project triggers bind the actor to the signed-in caller and the seeder writes with the "
             "service key. orchestrator.attribute_seeded_trail gives each seeded project row's trail to the project's "
             "lead, dated to the change; the page draws the actor on every row and was right all along.",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", nargs="*", help="re-run the gate on these pages first (none = every page in the prover)")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--again", action="store_true", help="bank a row this prover already banked today (a re-walk after a fix)")
    a = ap.parse_args()

    if a.run is not None:
        ok, last = bsw._run_gate(str(ROOT / PROVER), *a.run)
        print(f"  gate hive-scale-lists ({PROVER} {' '.join(a.run)}): {'PASS' if ok else 'FAIL'} - {last}")
        if not ok:
            print("  refused: a row is never banked on a red gate")
            return 1
    # the L1/L2 receipt refused is said and skipped - the W1/W2 receipts below have their own checks and are banked on
    # their own (a stale lists receipt used to end the run before them)
    rep, why = {"rows": {}}, ""
    if not REPORT.exists():
        why = f"no receipt - run {PROVER}"
    else:
        rep = json.loads(REPORT.read_text(encoding="utf-8"))
        age_h = (datetime.now(timezone.utc) - datetime.fromisoformat(rep["generated"].replace("Z", "+00:00"))).total_seconds() / 3600
        if rep.get("teeth"):
            why = "the receipt is a --teeth run (an expectation was flipped on purpose)"
        elif (rep.get("members") or 0) < 30:
            why = f"the receipt was read against {rep.get('members')} members, not a full hive"
        elif age_h > MAX_AGE_H:
            why = f"the receipt is {age_h:.1f} h old - walk again"
    if why:
        print(f"  L1/L2 refused: {why}")
        rep = {"rows": {}}

    reg = bsw._load_registry()
    by_id = {t["id"]: t for t in reg["trajectories"]}
    banked, left = 0, []
    for rid, r in sorted(rep.get("rows", {}).items()):
        t = by_id.get(rid)
        hs = (t or {}).get("hs") or {}
        if not t or hs.get("kind") != "hive-scale":
            if rid != "*":
                left.append(f"{rid}: not an HS row of the registry")
            continue
        if t.get("status") in ("locked", "descoped"):
            continue
        # L5 (a member who has left) and L6 (thirty names) are read in the same walk, item by item; a list whose window held
        # no departed member's item fails L5 as unjudged and is left open, never banked on silence
        # L7 (a member of two hives) is read by the --l7 walk: the active hive's list holds none of the other's items, and
        # switching hives (the active hive set, the page reloaded) replaces the list whole
        if hs.get("key") not in ("L1", "L2", "L5", "L6", "L7"):
            left.append(f"{rid}: lens {hs.get('key')} is not walked by this prover")
            continue
        # a FAILING re-walk is said before anything else - even of a row banked earlier today, which the skip below
        # would otherwise have hidden (the full run's four reds went unmentioned until this was reordered)
        if not r.get("ok"):
            already = f"[{date.today().isoformat()}] pct -> " in (t.get("basis") or "") and PROVER in (t.get("basis") or "")
            left.append(f"{rid}: the walk failed{' (banked earlier today - re-walk it)' if already else ''} - "
                        f"{r['failures'][0][:140] if r.get('failures') else 'no reading'}")
            continue
        # a row this prover banked today is already evidenced - a second entry from the next page's run is noise
        if not a.again and f"[{date.today().isoformat()}] pct -> " in (t.get("basis") or "") and PROVER in (t.get("basis") or ""):
            continue
        readings = "; ".join(r.get("notes", [])[:4])
        basis = (f"[{date.today().isoformat()}] pct -> {{pct}}. WALKED LIVE {rep['generated'][:16]}Z via {PROVER} (gate "
                 f"hive-scale-lists): playwright, two browser contexts signed in as Joel Cruz (worker) and Ernesto "
                 f"Villareal (supervisor) of the seeded {rep['members']}-member hive Batangas Refinery Maintenance, at "
                 f"phone-390 and desktop-1280, each item scrolled to the centre and read; postgres: every action an "
                 f"item's menu offers replayed as that person in a rolled-back transaction. Lens {hs['key']} "
                 f"({hs['lens']}) on {hs['page']} / {hs['unit']}: {readings}."
                 + (f" {FIXED[rid]}" if rid in FIXED else " Clean as walked - nothing to fix."))
        if a.dry:
            print(f"  would bank {rid} ({hs['key']} {hs['page']} {hs['unit']})")
        else:
            bsw._bank(reg, rid, basis, ["hive-scale-lists"])
        banked += 1
    # W1 - the DATABASE half of a two-member race, from its own receipt. A W1 row declares playwright + postgres: the
    # race is measured here, and the sentence the second member sees is held statically (oc-guard-speaks, and each
    # scenario names it) - not watched in a browser. So it is recorded as `fixing` at 45%, saying exactly that, never as
    # a live walk: the two-context browser walk is the half still owed.
    w_banked = 0
    if W_REPORT.exists():
        w = json.loads(W_REPORT.read_text(encoding="utf-8"))
        w_age = (datetime.now(timezone.utc) - datetime.fromisoformat(w["generated"].replace("Z", "+00:00"))).total_seconds() / 3600
        if w.get("teeth") or w_age > MAX_AGE_H:
            left.append(f"W1 receipt refused ({'a --teeth run' if w.get('teeth') else f'{w_age:.1f} h old'})")
        else:
            for rid, r in sorted(w.get("rows", {}).items()):
                t = by_id.get(rid)
                if not t or ((t.get("hs") or {}).get("key") != "W1") or t.get("status") in ("locked", "descoped", "locking"):
                    continue
                if not a.again and f"[{date.today().isoformat()}] pct -> 45" in (t.get("basis") or "") and W_PROVER in (t.get("basis") or ""):
                    continue
                if not r.get("ok"):
                    left.append(f"{rid}: the race failed - {r['failures'][0][:140]}")
                    continue
                basis = (f"[{date.today().isoformat()}] pct -> 45. DATABASE HALF MEASURED {w['generated'][:16]}Z via {W_PROVER} "
                         f"(gate hive-scale-writes): postgres - the two members' race replayed in one rolled-back transaction as "
                         f"each person (role authenticated, their JWT claims) with {r['page']}'s own write and guard on "
                         f"{r['unit']}; shape {r['shape']}, read {json.dumps(r['got'])}. What the second member is told: "
                         f"{r['told']}. NOT YET WALKED in a browser - the two-context walk that watches that sentence is the "
                         f"half still owed." + (f" {FIXED[rid]}" if rid in FIXED else ""))
                if a.dry:
                    print(f"  would record {rid} (W1 {r['page']} {r['unit']}) at 45%")
                else:
                    old = t.get("basis") or ""
                    t["status"], t["pct"] = "fixing", 45
                    t["basis"] = (old + " || " if old else "") + basis
                    t.setdefault("artifacts", {})["gates"] = sorted(set((t.get("artifacts") or {}).get("gates") or []) | {"hive-scale-writes"})
                w_banked += 1
    # W1 - the BROWSER half (2026-10-30): tools/prove_hive_scale_races.mjs walks each race with two people in two browsers
    # (phone-390 against desktop-1280, then swapped), through the page's own controls. A row whose race passed at BOTH
    # pairings is banked to locking on that receipt, beside the database half above.
    r_banked = 0
    if R_REPORT.exists():
        rr = json.loads(R_REPORT.read_text(encoding="utf-8"))
        r_age = (datetime.now(timezone.utc) - datetime.fromisoformat(rr["ran"].replace("Z", "+00:00"))).total_seconds() / 3600
        if r_age > MAX_AGE_H:
            left.append(f"W1 browser receipt refused ({r_age:.1f} h old)")
        else:
            for rid, r in sorted(rr.get("rows", {}).items()):
                t = by_id.get(rid)
                if not t or ((t.get("hs") or {}).get("key") != "W1") or t.get("status") in ("locked", "descoped"):
                    continue
                if not a.again and R_PROVER in (t.get("basis") or "") and t.get("status") == "locking":
                    continue
                walks = r.get("walks") or []
                if not r.get("ok") or len(walks) < 2 or not all(w.get("ok") for w in walks):
                    left.append(f"{rid}: the browser race failed - {(walks[0].get('why') if walks else 'not walked')[:140]}")
                    continue
                said = "; ".join(f"{w['a']} against {w['b']}: {w['why']}" for w in walks)
                basis = (f"[{date.today().isoformat()}] LOCKING pct -> {{pct}}. Measured live {rr['ran'][:16]}Z - {R_PROVER} walked the "
                         f"race with two people in two browsers, each through {r['page']}'s own controls ({r['claim']}). {said}. "
                         f"Every row the race touched was snapshotted and restored. The database half (gate hive-scale-writes) "
                         f"holds the same race as the two people's own writes." + (f" {FIXED_RACE[rid]}" if rid in FIXED_RACE else ""))
                if a.dry:
                    print(f"  would bank {rid} (W1 browser, {r['page']} {r['table']})")
                else:
                    bsw._bank(reg, rid, basis, ["hive-scale-races", "hive-scale-writes"])
                r_banked += 1
    # W2 - the burst receipt (does every write land, at once and staggered) and the shift receipt (the page a member then
    # opens keeps every item in its order). A row is banked only when its shift walk passed at BOTH viewports with every
    # write landed, and - for a page that writes - the burst passed for its table.
    s_banked = 0
    if S_REPORT.exists() and B_REPORT.exists():
        sr = json.loads(S_REPORT.read_text(encoding="utf-8"))
        br = json.loads(B_REPORT.read_text(encoding="utf-8"))
        ages = [(datetime.now(timezone.utc) - datetime.fromisoformat(x["ran"].replace("Z", "+00:00"))).total_seconds() / 3600 for x in (sr, br)]
        if br.get("teeth") or max(ages) > MAX_AGE_H:
            left.append(f"W2 receipts refused ({'the burst is a --teeth run' if br.get('teeth') else f'{max(ages):.1f} h old'})")
        else:
            for rid, r in sorted(sr.get("rows", {}).items()):
                t = by_id.get(rid)
                if not t or ((t.get("hs") or {}).get("key") != "W2") or t.get("status") in ("locked", "descoped"):
                    continue
                if not a.again and S_PROVER in (t.get("basis") or "") and t.get("status") == "locking":
                    continue
                walks = r.get("walks") or []
                if not r.get("ok") or len(walks) < 2 or not all(w.get("ok") for w in walks):
                    left.append(f"{rid}: the shift walk failed - {(walks[0].get('says') if walks else 'not walked')[:140]}")
                    continue
                said = "; ".join(f"{w['reader']}: {w['says']}" for w in walks)
                retired = r.get("landed") == 0 and r.get("wrote", 0) == 0
                if retired:
                    basis = (f"[{date.today().isoformat()}] LOCKING pct -> {{pct}}. Measured live {sr['ran'][:16]}Z - {S_PROVER} opened "
                             f"{r['page']} (a retired admin page) as members of the {sr['members']}-member hive: {said}. "
                             f"Gate hive-scale-shift.")
                    gates = ["hive-scale-shift"]
                else:
                    u = (br.get("units") or {}).get(r["table"])
                    if not u or not u.get("ok"):
                        left.append(f"{rid}: no passing burst for {r['table']} - run {B_PROVER} {r['table']}")
                        continue
                    basis = (f"[{date.today().isoformat()}] LOCKING pct -> {{pct}}. Measured live - the burst {br['ran'][:16]}Z: "
                             f"{u['sent']} members wrote {r['table']} at once ({u['burst_landed']} landed) and one after another "
                             f"({u['staggered_landed']} landed), none refused ({B_PROVER}, through PostgREST as each member). Then "
                             f"{S_PROVER} walked {r['page']} after a shift of {r['wrote']} writes ({r['landed']} landed): {said}. "
                             f"Gates hive-scale-burst, hive-scale-shift.")
                    gates = ["hive-scale-burst", "hive-scale-shift"]
                basis += f" {FIXED_W2[rid]}" if rid in FIXED_W2 else ""
                if a.dry:
                    print(f"  would bank {rid} (W2 {r['page']} {r['table']})")
                else:
                    bsw._bank(reg, rid, basis, gates)
                s_banked += 1
    if (banked or w_banked or r_banked or s_banked) and not a.dry:
        bsw._write_registry(reg)
    if s_banked:
        print(f"{'would bank' if a.dry else 'banked'} {s_banked} W2 row(s) on the burst and the shift")
    if r_banked:
        print(f"{'would bank' if a.dry else 'banked'} {r_banked} W1 row(s) on the browser race")
    for line in left:
        print("  left open: " + line)
    print(f"{'would bank' if a.dry else 'banked'} {banked} HS row(s); {'would record' if a.dry else 'recorded'} {w_banked} W1 row(s) at 45%; {len(left)} left open")
    return 0


if __name__ == "__main__":
    sys.exit(main())
