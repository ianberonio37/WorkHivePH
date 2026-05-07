"""Seed worker_achievements — wipe then reseed all hive members with varied tiers.

Gives every worker a different tier mix so the hive board, community page,
and marketplace all show a visible spread of ring colours (Iron through Legend).
Re-runnable: wipes existing data for known workers before inserting fresh rows.
"""
import math
import random
from datetime import datetime, timezone


def xp_for_level(n):
    if n <= 0:
        return 0
    return math.floor(100 * (n ** 1.8))


ALL_ACHIEVEMENTS = [
    "wrench_chronicle",
    "uptime_guardian",
    "parts_warden",
    "blueprint_master",
    "failure_hunter",
    "safety_sentinel",
    "skill_climber",
    "knowledge_forger",
    "hive_architect",
    "voice_of_hive",
    "shift_keeper",
    "iron_worker",
]

# Each worker profile gets one of these tier mixes.
# The first domain in each mix gets the highest level (drives the ring colour).
TIER_PROFILES = [
    # Legend worker  — one domain at 93, scattered others
    [("wrench_chronicle", 93), ("uptime_guardian", 55), ("safety_sentinel", 28),
     ("failure_hunter", 12), ("skill_climber", 5)],
    # Platinum worker
    [("uptime_guardian", 80), ("wrench_chronicle", 45), ("safety_sentinel", 20),
     ("parts_warden", 8)],
    # Gold worker
    [("safety_sentinel", 60), ("wrench_chronicle", 30), ("failure_hunter", 14),
     ("knowledge_forger", 6)],
    # Silver worker
    [("skill_climber", 35), ("wrench_chronicle", 18), ("voice_of_hive", 9)],
    # Bronze worker
    [("wrench_chronicle", 15), ("uptime_guardian", 7)],
    # Iron worker (low XP, still showing a ring)
    [("wrench_chronicle", 5)],
]

XP_LOG_TEMPLATES = [
    ("wrench_chronicle",  95, "logbook_close"),
    ("wrench_chronicle",  50, "logbook_submit"),
    ("uptime_guardian",   60, "pm_complete"),
    ("safety_sentinel",   60, "safety_entry"),
    ("failure_hunter",   100, "breakdown_root_cause"),
    ("skill_climber",    250, "skill_badge_earned"),
    ("voice_of_hive",     60, "community_post"),
    ("knowledge_forger",  20, "detailed_entry"),
    ("parts_warden",      30, "logbook_submit"),
]


def seed_achievements(client, log):
    """Wipe and reseed worker_achievements for all known hive members."""
    now = datetime.now(timezone.utc).isoformat()

    # Collect all unique worker names from hive_members
    members_res = client.table("hive_members").select("worker_name").execute()
    worker_names = list({m["worker_name"] for m in (members_res.data or []) if m.get("worker_name")})

    if not worker_names:
        log("  no hive members found — seeding skipped")
        return

    log(f"  found {len(worker_names)} workers: {worker_names}")

    # Wipe existing data for these workers
    client.table("achievement_xp_log").delete().in_("worker_name", worker_names).execute()
    client.table("worker_achievements").delete().in_("worker_name", worker_names).execute()
    log(f"  wiped existing achievement data for {len(worker_names)} workers")

    # Seed achievements
    ach_rows = []
    log_rows = []

    for i, worker_name in enumerate(worker_names):
        profile = TIER_PROFILES[i % len(TIER_PROFILES)]

        for ach_id, level in profile:
            ach_rows.append({
                "worker_name":    worker_name,
                "achievement_id": ach_id,
                "current_level":  level,
                "xp_total":       xp_for_level(level) + random.randint(50, 499),
                "last_action_at": now,
            })

        # XP log: give each worker 3-5 recent events from the templates
        sample_logs = random.sample(XP_LOG_TEMPLATES, min(5, len(XP_LOG_TEMPLATES)))
        for ach_id, xp, action in sample_logs:
            log_rows.append({
                "worker_name":    worker_name,
                "achievement_id": ach_id,
                "xp_earned":      xp,
                "source_action":  action,
                "earned_at":      now,
            })

    if ach_rows:
        client.table("worker_achievements").insert(ach_rows).execute()
    if log_rows:
        client.table("achievement_xp_log").insert(log_rows).execute()

    # Summary
    tier_labels = {
        range(91, 101): "Legend",
        range(76, 91):  "Platinum",
        range(51, 76):  "Gold",
        range(26, 51):  "Silver",
        range(11, 26):  "Bronze",
        range(0, 11):   "Iron",
    }

    def tier_name(level):
        for r, label in tier_labels.items():
            if level in r:
                return label
        return "Iron"

    summary = []
    for i, worker_name in enumerate(worker_names):
        profile = TIER_PROFILES[i % len(TIER_PROFILES)]
        top_level = max(lv for _, lv in profile)
        summary.append(f"{worker_name}={tier_name(top_level)}(Lv{top_level})")

    log(f"  seeded {len(ach_rows)} achievement rows, {len(log_rows)} XP log rows")
    log(f"  rings: {', '.join(summary)}")
    log("  done — refresh hive.html / community.html / achievements.html to see rings")
