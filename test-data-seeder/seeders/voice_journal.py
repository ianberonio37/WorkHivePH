"""Seed voice_journal_entries - private worker journal entries.

Without this, voice-journal.html shows an empty history feed on every
fresh seed and the semantic recall (search_voice_journal_entries RPC)
can't be exercised because there's nothing in the index.

Per the migration, this is a PRIVATE journal (RLS: own rows only via
auth.uid()). Seeding requires each row to have a valid auth_uid that
maps to a real auth.users entry; we look those up via worker_profiles
where the linked auth_uid is set. Workers without a linked auth_uid
(rare on test seeds) are skipped.

We leave the embedding column NULL - semantic recall degrades gracefully
to plain text retrieval, which is enough for UI verification. The
production voice-journal-agent fills embedding on real inserts.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone


# Templated transcript phrases - vary by topic so the journal feels real.
# Tone matches a Filipino plant worker's voice log (mix of English + Tagalog).
TOPICS = [
    {
        "transcripts": [
            "Bearing noise sa Conveyor 2, parang nagsisimula na ulit yung problema last week.",
            "I checked the bearings on Conveyor 2 this morning, slight grinding sound returning.",
            "Conveyor 2 bearing - replaced 6 months ago, vibration creeping back up.",
        ],
        "reply_hint": "logbook entry suggested",
    },
    {
        "transcripts": [
            "Lubrication PM done on PMP-103, took 45 min, grease was almost dry.",
            "Finished lubrication round for the pump section. PMP-103 grease was depleted - flagging for shorter interval.",
            "PMP-103 lubed today, recommend dropping the PM interval from 90d to 60d.",
        ],
        "reply_hint": "PM frequency review",
    },
    {
        "transcripts": [
            "Spare V-belt for VB-220 - stock is at 1 pc, dapat may 3 minimum.",
            "Checked the stockroom, V-belts for VB-220 below safety stock. Reorder na agad.",
            "Inventory low alert - 22kV insulator gloves, 1 pair left for the whole shift.",
        ],
        "reply_hint": "inventory restock",
    },
    {
        "transcripts": [
            "Inspection ng panel CCB-04, smelled like burning insulation pero walang trip.",
            "CCB-04 thermal scan today, hotspot at terminal block #3 - 87 degC.",
            "Electrical panel 4 has loose ground - tightened, will reinspect next week.",
        ],
        "reply_hint": "predictive flag",
    },
    {
        "transcripts": [
            "Toolbox talk this morning - covered LOTO procedure with new hires.",
            "Safety stand-down done, all 8 workers signed the attendance.",
            "Reviewed near-miss from yesterday's pump room, no injuries pero close.",
        ],
        "reply_hint": "training log",
    },
    {
        "transcripts": [
            "Hyd power pack PMP-105 - oil sample sent for analysis, sticky pa rin.",
            "Followed up on the oil sample report for PMP-105, Cu particles within tolerance.",
            "PMP-105 oil temperature higher than usual, cooler fan may be weak.",
        ],
        "reply_hint": "trend monitoring",
    },
    {
        "transcripts": [
            "End of shift, no major issues. Production line ran clean for 8 hours.",
            "Smooth shift, only 2 minor alarms - both auto-cleared. Good day.",
            "Shift summary: 0 breakdowns, 2 PMs closed, 1 inventory check, 0 safety events.",
        ],
        "reply_hint": "shift end summary",
    },
    {
        "transcripts": [
            "Walkdown Bay 3 today, nakita ko leak sa drain line ng compressor.",
            "Compressor area walkdown - oil weep at flange connection, marked for next PM.",
            "Bay 3 floor has water seepage near pump foundation, may be drain issue.",
        ],
        "reply_hint": "walkdown finding",
    },
]

LANG_DIST = ["tl", "tl", "en", "en", "en", None]  # Tagalog, English, sometimes null


def seed_voice_journal(client, log, ctx: dict) -> dict:
    log("Seeding voice_journal_entries (5-10 per worker, last 30 days)...")

    # Pull workers who have a linked auth_uid (needed for RLS-keyed inserts).
    # The hive_members table is the canonical place worker auth_uid lives;
    # worker_profiles.username is the natural key, display_name is the
    # human label.
    members = client.table("hive_members").select(
        "auth_uid, worker_name, hive_id",
    ).eq("status", "active").not_.is_("auth_uid", "null").execute().data or []

    if not members:
        log("  no hive_members with auth_uid - voice_journal skipped (expected on fresh stack)")
        return {"voice_journal_count": 0}

    rows = []
    now = datetime.now(timezone.utc)
    # Group by (auth_uid, worker_name) to avoid duplicate-per-worker creation
    # when the same worker is a member of multiple hives.
    seen_workers = set()
    for m in members:
        auth_uid = m.get("auth_uid")
        if not auth_uid or auth_uid in seen_workers:
            continue
        seen_workers.add(auth_uid)
        worker_name = m.get("worker_name") or ""
        hive_id     = m.get("hive_id")

        n_entries = random.randint(5, 10)
        for _entry_idx in range(n_entries):
            topic = random.choice(TOPICS)
            transcript = random.choice(topic["transcripts"])
            # Spread across the last 30 days, weighted toward the recent week
            days_back = int(random.triangular(0, 30, 5))
            created_at = now - timedelta(
                days=days_back,
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
            )
            rows.append({
                "auth_uid":    auth_uid,
                "worker_name": worker_name,
                "hive_id":     hive_id,
                "transcript":  transcript,
                # Deterministic worked-state: the FIRST entry per worker ALWAYS gets an AI reply so the
                # voice-journal page renders the replied/worked state on EVERY reseed (was pure 65% random ->
                # a worker could roll 0 replies -> empty page). Makes the UFAI DB-only fix (entry c64fd9ce
                # got a manual reply) reseed-durable. 2026-07-19.
                "reply":       f"Noted: {topic['reply_hint']} ({len(transcript)} chars)" if (_entry_idx == 0 or random.random() < 0.65) else None,
                "lang":        random.choice(LANG_DIST),
                "meta":        {"source": "seed", "topic": topic["reply_hint"]},
                "created_at":  created_at.isoformat(),
            })

    if not rows:
        return {"voice_journal_count": 0}

    from .utils import batch_insert
    try:
        inserted = batch_insert(client, "voice_journal_entries", rows, chunk=500)
    except Exception as e:
        log(f"  voice_journal insert failed: {e}")
        return {"voice_journal_count": 0}
    log(f"  inserted {inserted} voice_journal_entries across {len(seen_workers)} workers")
    return {"voice_journal_count": inserted}
