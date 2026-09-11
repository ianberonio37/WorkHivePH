#!/usr/bin/env python3
"""seed_community_answers.py — the community has questions and not one answer.

FOUND BY A CHAIN THAT LEARNED TO NAME ITS MISSING LINK (2026-09-08). J7, the knowledge loop
(question -> best answer -> skill-content -> skillmatrix -> achievements), reads
`least(community_posts, community_replies)` and came back 0 in ALL SIX hives. Until the walk could
decompose a `least()` it could only say "the chain is empty in this hive", which is the finding with
the finding removed. Decomposed, it says the same thing six times over:

    the missing link is community_replies, while this hive does hold community_posts 52
                                            ... 32 ... 15 ... 15 ...

**Over a hundred questions on this platform and zero replies.** That is not one journey failing; it is
the whole reputation surface standing on an empty table. `v_community_reputation_truth` derives
trust_tier and xp_total from posts AND replies, `skill_badges` hangs off participation, and the
"accepted answer" is the event the knowledge loop turns on. None of it has ever had an input.

Not RLS, and worth ruling out before writing anything: the reply read policy is a plain hive-membership
check, the same shape as the post policy, and the chain is read AS the person - a member who can see 52
posts can see their replies. The absence is real.

WHY THIS FILE EXISTS. There is no community seeder. `test-data-seeder/flows/community.py` is a UI test
flow, it asserts against posts and never writes a reply. Missing data is a seeding job, never a blocker
(and where recall comes up empty, the move is to BUILD the structure, not to file the target down to
"covered by nature").

★IT ANSWERS THE QUESTION THAT WAS ASKED. A canned reply pasted under an unrelated question is incoherent
data that teaches a walk to expect something the product would never hold, so answers are chosen by the
post's own `category` (general / safety / technical / marketplace / announcement - the five the composer
offers) and written by a DIFFERENT member of the same hive than the one who asked. A person answering
their own question is not the knowledge loop.

★THE ANSWERER IS A REAL MEMBER, with their real `auth_uid`. `bind_community_reply_submitter` only
overrides the author when `auth.uid()` is set, so a psql insert keeps what it is given - which means the
choice of who wrote this is mine to get right, not the trigger's to fix.

★THERE IS NO MARKER COLUMN, so the marker is the CONTENT ITSELF. community_replies has no `meta` or
`notes` to hide a token in, and putting one in `content` would print it on the card in front of a person.
Instead --revert deletes exactly the sentences this file writes, scoped to the hives it wrote them in.
That is narrower than a token, not looser: it cannot match a reply somebody actually typed unless they
typed one of these sentences word for word.

  python tools/seed_community_answers.py --check     # posts vs replies per hive
  python tools/seed_community_answers.py --apply     # write the answers
  python tools/seed_community_answers.py --revert    # remove exactly what this wrote
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys

DB = "supabase_db_workhive"

# One answer per category, plus a shorter second voice for the accepted-answer leg. Every sentence is
# Philippine-plant plausible and none of them names a machine, so an answer can never contradict the
# question it sits under.
ANSWERS: dict[str, list[str]] = {
    "general": [
        "We hit the same thing last quarter. What worked for us was writing it into the shift handover so the next crew starts from where you stopped, instead of re-diagnosing it every morning.",
        "Log it against the asset even if it turns out to be nothing - the history is what makes the next one quick.",
    ],
    "safety": [
        "Do not work it live. Apply LOTO, tag the isolation point, and get a second person to verify before anyone puts a hand in. If the guard is missing the machine stays down; that is a DOLE finding waiting to happen, not a judgement call.",
        "Record it as an incident even if nobody was hurt. A near miss with no record is a repeat waiting for a different person.",
    ],
    "technical": [
        "Check the simple side first - supply voltage at the terminal, then the belt tension, then the alignment. Most of the ones that look electrical here have been mechanical, and the meter costs you two minutes.",
        "Take a reading before and after the fix and put both in the entry. Without the before, nobody can tell later whether it actually worked.",
    ],
    "marketplace": [
        "We source that locally rather than waiting on an import - a shop in the next town usually has the common sizes on the shelf, and the lead time beats the price difference when the line is down.",
        "Ask for the part number off the old one before ordering. Two of ours came back wrong because we ordered from the model name.",
    ],
    "announcement": [
        "Noted, thank you for putting it up here. I have passed it to the crew on the opposite shift so nobody misses it at handover.",
        "Received - we will follow it from Monday.",
    ],
}


# ★A HIVE WITH PEOPLE AND NO CONVERSATION CANNOT HOST THE KNOWLEDGE LOOP EITHER. Three fleets held zero
# community posts, so there was nothing to answer - and answering is only half of J7, which is asker AND
# answerer. Two of them have ONE member each, and a person cannot be both, so those stay honestly empty.
# Dela Cruz has three, which is a crew, so it gets the conversation a crew has. The questions below are
# what a delivery fleet actually asks, in the composer's own categories, and each is posted by a real
# member - never by the same person who will answer it.
QUESTIONS = [
    ("technical", "Our HiAce is going through front pads every six weeks on the same route. Anyone seen a caliper slide pin seize like this, or is it the loading?"),
    ("safety", "What is the right way to chock a van on the ramp when we are working underneath it? We only have two chocks between three units."),
    ("marketplace", "Where does everyone source Isuzu Traviz brake discs locally? The importer quote is two weeks out and the unit is off the road."),
]

def psql(sql: str, tries: int = 2) -> str | None:
    """None means the database could not answer. That is never the same as an empty result, and this
    file must never write on the strength of a read that failed."""
    for _ in range(tries):
        try:
            r = subprocess.run(
                ["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-tA", "-c", sql],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
            if r.returncode == 0:
                # ★"INSERT 0 6" IS NOT A ROW. `-tA` drops the header but psql still prints its command
                # status after a RETURNING result, so a six-row insert came back as seven lines and this
                # file reported "wrote 7 answer(s)" when the table held six. seed_fleet_history.py had
                # already learned this - a logbook entry was once written about a van called "INSERT 0 2" -
                # and the fix lived only in that file's own psql(). Same fix, same place, so both seeders
                # read a result the same way.
                kept = [l for l in r.stdout.strip().splitlines()
                        if not re.match(r"^(INSERT|UPDATE|DELETE|SELECT|COPY)\s+\d+(\s+\d+)?$", l.strip())]
                return "\n".join(kept).strip()
        except Exception:
            pass
    return None


def q(s: str) -> str:
    return s.replace("'", "''")




def report() -> int:
    rows = psql("select h.name||'|'||(select count(*) from community_posts p where p.hive_id=h.id and p.deleted_at is null)"
                "||'|'||(select count(*) from community_replies r where r.hive_id=h.id)"
                "||'|'||(select count(*) from community_replies r where r.hive_id=h.id and r.is_accepted) from hives h order by h.name")
    if rows is None:
        print("  the database did not answer - nothing is reported rather than reported as zero")
        return 1
    print("  %-32s %7s %8s %9s" % ("hive", "posts", "replies", "accepted"))
    for line in rows.splitlines():
        if line.count("|") == 3:
            name, posts, reps, acc = line.split("|")
            print("  %-32s %7s %8s %9s" % (name[:32], posts, reps, acc))
    return 0


def apply(revert: bool) -> int:
    every = [s for group in ANSWERS.values() for s in group]
    in_list = ",".join("'%s'" % q(s) for s in every)
    q_list = ",".join("'%s'" % q(body) for _cat, body in QUESTIONS)
    hives = psql("select id||'|'||name from hives order by name")
    if hives is None:
        print("  the database did not answer - nothing written")
        return 1
    total = 0
    for line in hives.splitlines():
        if "|" not in line:
            continue
        hid, name = line.split("|", 1)
        if revert:
            # answers first: a post with replies cannot be removed while they point at it, and the
            # questions this file writes are its own to take back too - a revert that leaves half of what
            # it wrote is not a revert
            n = psql(f"with d as (delete from community_replies where hive_id = '{hid}' and content in ({in_list}) returning 1) select count(*) from d")
            qn = psql(f"with d as (delete from community_posts where hive_id = '{hid}' and content in ({q_list}) returning 1) select count(*) from d")
            print(f"  {name}: removed {n} seeded answer(s) and {qn} seeded question(s)")
            total += int(n or 0) + int(qn or 0)
            continue

        already = psql(f"select count(*) from community_replies where hive_id = '{hid}' and content in ({in_list})")
        if already is None:
            print(f"  {name}: could not ask whether it is already seeded - skipped rather than risk doubling")
            continue
        if already.isdigit() and int(already) > 0:
            print(f"  {name}: already carries {already} seeded answer(s) - not writing them again")
            continue

        # the people: every active member with a real auth row, so an answerer is somebody who exists
        members = [m for m in (psql(
            f"select worker_name||'|'||coalesce(auth_uid::text,'') from hive_members "
            f"where hive_id = '{hid}' and status = 'active' order by role, worker_name") or "").splitlines() if "|" in m]
        if len(members) < 2:
            print(f"  {name}: fewer than two members - nobody here can answer somebody else, skipped")
            continue

        # the questions: real posts, oldest first, so the answers sit under the conversation that started it
        posts = [p for p in (psql(
            f"select id||'|'||author_name||'|'||coalesce(category,'general') from community_posts "
            f"where hive_id = '{hid}' and deleted_at is null order by created_at limit 6") or "").splitlines() if p.count("|") == 2]
        if not posts:
            # a crew with nothing to talk about yet gets the conversation a crew has; a one-person hive
            # does not, because there is nobody for them to be asking
            if len(members) < 2:
                print(f"  {name}: holds no posts and has one member - nobody here to ask anybody, skipped")
                continue
            asker, a_uid = (members[0].split("|", 1) + [""])[:2]
            qrows = []
            for i, (cat, body) in enumerate(QUESTIONS):
                uid_sql = f"'{a_uid}'" if a_uid.strip() else "null"
                qrows.append(f"('{hid}','{q(asker)}','{q(body)}','{cat}',false,false,false,{uid_sql},"
                             f"now() - (interval '1 day' * {6 - i}))")
            made_q = psql("insert into community_posts (hive_id, author_name, content, category, pinned, "
                          "flagged, public, auth_uid, created_at) values " + ",".join(qrows) + " returning id")
            if made_q is None:
                print(f"  {name}: the question insert did not answer - nothing written here")
                continue
            print(f"  {name}: no conversation yet - wrote {len([x for x in made_q.splitlines() if x.strip()])} "
                  f"question(s) from {asker} so the crew has something to answer")
            posts = [p for p in (psql(
                f"select id||'|'||author_name||'|'||coalesce(category,'general') from community_posts "
                f"where hive_id = '{hid}' and deleted_at is null order by created_at limit 6") or "").splitlines()
                if p.count("|") == 2]
            if not posts:
                print(f"  {name}: the questions did not come back - skipped")
                continue

        rows = []
        for i, p in enumerate(posts):
            pid, asker, cat = p.split("|", 2)
            pool = [m for m in members if m.split("|", 1)[0] != asker]
            if not pool:
                continue                      # only the asker is here; answering yourself is not the loop
            who, uid = (pool[i % len(pool)].split("|", 1) + [""])[:2]
            body = ANSWERS.get(cat, ANSWERS["general"])[0]
            accept = "true" if i < 2 else "false"
            acc_by = f"'{q(asker)}'" if accept == "true" else "null"
            acc_at = "now()" if accept == "true" else "null"
            uid_sql = f"'{uid}'" if uid.strip() else "null"
            rows.append(
                f"('{pid}','{hid}','{q(who)}','{q(body)}',{uid_sql},{accept},{acc_by},{acc_at},"
                f"now() - (interval '1 day' * {i + 1}))")
        if not rows:
            print(f"  {name}: every post here was written by the only member - skipped")
            continue
        got = psql("insert into community_replies (post_id, hive_id, author_name, content, auth_uid, "
                   "is_accepted, accepted_by, accepted_at, created_at) values " + ",".join(rows) + " returning id")
        if got is None:
            print(f"  {name}: the insert did not answer - nothing written here")
            continue
        made = len([x for x in got.splitlines() if x.strip()])
        print(f"  {name}: wrote {made} answer(s), 2 of them accepted, from members other than each asker")
        total += made
    return 0 if total or revert else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    if a.revert:
        return apply(revert=True)
    if a.apply:
        return apply(revert=False)
    return report()


if __name__ == "__main__":
    sys.exit(main())
