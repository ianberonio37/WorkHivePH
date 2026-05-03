"""Seed community_posts."""
import random

from .utils import random_timestamp_in_last_n_days, to_iso

POST_CATEGORIES = ["general", "safety", "technical", "announcement"]

POST_TEMPLATES = [
    "What's your go-to method for aligning a coupling without a laser tool? Looking for tips.",
    "Just hit 1000 hrs no-LTI — proud of the team. Cake at 3 PM in the breakroom.",
    "Anyone else seeing the new ABB ACS580 firmware behaving weird on regen braking?",
    "Tip: keep a spare PSV always cert'd — saves you on shutdowns. Cost me a long weekend last month.",
    "How are you tracking grease frequency? Excel? CMMS? Anything better?",
    "Found a great supplier for SKF bearings in Cebu, DM me if interested.",
    "Reminder: MCCB recall notice from Schneider for batch # ABC123. Check yours.",
    "Toolbox talk on hot work permits this Friday 7am. Mandatory for all M-shift.",
    "Saved 20% on lube oil by switching to Shell Tellus from Mobil DTE — same spec.",
    "PM compliance hit 95% this month — first time we cracked 95. Big thanks to night shift.",
    "Looking for a vendor who can recondition Burckhardt Laby compressors locally.",
    "Quick question — anyone using Marley NC cooling tower drift eliminators? Pricing?",
    "Trick I learned: chalk on coupling halves to spot the high spot during alignment.",
    "Calling all reliability folks — what's your MTBF target on critical pumps?",
    "Tomorrow's outage: 06:00 to 14:00 on Line A. Plan accordingly, please.",
]


def seed_community(client, log, ctx: dict) -> dict:
    hives = ctx["hives"]
    workers = ctx["workers"]
    workers_by_hive: dict = {}
    for w in workers:
        workers_by_hive.setdefault(w["hive_id"], []).append(w)

    log(f"Seeding community posts across {len(hives)} hives...")

    POSTS_PER_AUTHOR_MAX = 14  # some authors will trip the 10-post badge trigger — that's intentional now

    rows = []
    for hive in hives:
        hive_workers = workers_by_hive.get(hive["id"], [])
        if not hive_workers:
            continue
        for author in hive_workers:
            n_posts = random.randint(3, POSTS_PER_AUTHOR_MAX)
            for _ in range(n_posts):
                ts = random_timestamp_in_last_n_days(90)
                rows.append({
                    "hive_id": hive["id"],
                    "author_name": author["display_name"],
                    "content": random.choice(POST_TEMPLATES),
                    "category": random.choices(POST_CATEGORIES, weights=[55, 15, 25, 5])[0],
                    "pinned": random.random() < 0.03,
                    "flagged": False,
                    "created_at": to_iso(ts),
                    "public": random.random() < 0.3,
                })

    client.table("community_posts").insert(rows).execute()
    log(f"  inserted {len(rows)} community_posts")

    return {"community_posts_count": len(rows)}
