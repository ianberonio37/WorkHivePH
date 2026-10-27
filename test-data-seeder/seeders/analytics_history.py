"""Analytics history - 90 days of visits and uses, so the outcome figures have something to count (T2 OUT, 2026-10-27).

WHY: founder_outcomes answers "did anyone come back?" per page - from analytics_events, which a clean reseed leaves
empty (reset_all clears it; nothing wrote it but live walks). On an empty ledger every return and repeat-use figure is
0 of 0, and tools/prove_outcome_figures.py would compare 0 with 0 and prove nothing. This writes a ledger with the
shapes the figures must tell apart: accounts that came back within a week, within a month, or never; uses on one day
and on several; a follow-up still running (first seen this week); signed-out sessions, which use but cannot return.

WHAT: for each active hive member (bound auth_uid), a few of the pages a person of the platform uses, a first day on
each in the last 85 days, and later visits at gaps the person's habit decides. A visit is one page_view plus 0-3 uses
named after the page's real actions (tools/validate_usage_events.py USES). Times are working hours in Manila, never in
the future. The service role writes the identity fields as given (bind_analytics_events_submitter keeps a service-role
row as stated). Deterministic: the same seed writes the same ledger.
"""
import datetime as dt
import hashlib
import random

from .utils import batch_insert

MANILA = dt.timezone(dt.timedelta(hours=8))

# page key (as logPageView/whUse write it) -> the page's real actions
ACTIONS = {
    "achievements": ["achievement_opened"],
    "alert-hub": ["alert_handled", "alert_snoozed", "alert_seen"],
    "analytics-report": ["report_generated", "report_exported"],
    "analytics": ["phase_opened", "period_changed"],
    "asset-hub": ["asset_opened", "fmea_mode_added", "rcm_strategy_saved"],
    "assistant": ["question_answered", "answer_rated"],
    "community": ["post_published", "reply_posted", "reaction_added"],
    "dayplanner": ["item_added", "item_edited", "item_removed"],
    "engineering-design": ["calc_run", "calc_saved", "report_exported"],
    "hive": ["hive_joined", "hive_renamed"],
    "index": ["stage_opened", "all_tools_opened"],
    "integrations": ["tab_opened", "import_run"],
    "inventory": ["part_used", "part_restocked", "part_added"],
    "logbook": ["entry_logged", "entry_edited", "entry_closed"],
    "marketplace-seller-profile": ["section_opened", "seller_contacted"],
    "marketplace-seller": ["inquiry_replied", "listing_edited"],
    "marketplace": ["listing_opened", "listing_watched", "inquiry_sent"],
    "ph-intelligence": ["report_generated"],
    "plant-connections": ["connections_refreshed"],
    "pm-scheduler": ["pm_completed", "pm_task_added"],
    "project-manager": ["project_created", "project_edited", "project_status_set"],
    "project-report": ["report_exported", "narrative_generated"],
    "public-feed": ["more_loaded"],
    "report-sender": ["report_sent", "recipient_added"],
    "resume": ["resume_saved", "resume_export"],
    "shift-brain": ["plan_published", "plan_rerun"],
    "skillmatrix": ["lesson_opened", "exam_started", "exam_graded"],
}
# what a signed-out visitor can reach and use
PUBLIC = ["public-feed", "marketplace", "marketplace-seller-profile", "index"]
# how often a person of the platform comes back to a page, in days between visits (None = one visit and never again)
HABITS = [(1, 3), (2, 6), (4, 12), (10, 25), None]


def _at(day: dt.date, rng: random.Random, now: dt.datetime) -> str | None:
    """A working-hours moment on a Manila day, as UTC ISO - or None if that moment has not happened yet."""
    t = dt.datetime(day.year, day.month, day.day, rng.randint(7, 18), rng.randint(0, 59), rng.randint(0, 59), tzinfo=MANILA)
    return None if t >= now else t.astimezone(dt.timezone.utc).isoformat()


def _visit(rows, page, day, rng, now, *, uid=None, hive=None, name=None, session=None, max_uses=3):
    seen = _at(day, rng, now)
    if not seen:
        return
    base = {"auth_uid": uid, "hive_id": hive, "worker_name": name, "session_id": session, "user_agent": "seed"}
    rows.append({**base, "event_name": "page_view", "page": page, "props": {"page": page}, "created_at": seen})
    for _ in range(rng.choice([0, 0, 1, 1, 2, max_uses])):
        at = _at(day, rng, now)
        if at and at > seen:
            rows.append({**base, "event_name": "feature_use", "page": page,
                         "props": {"page": page, "action": rng.choice(ACTIONS[page])}, "created_at": at})


def seed_analytics_history(client, log) -> dict:
    log("Seeding analytics history (90 days of visits and uses, for the outcome figures)...")
    rng = random.Random(20261027)
    now = dt.datetime.now(MANILA)
    today = now.date()
    members = (client.table("hive_members").select("auth_uid, hive_id, worker_name")
               .eq("status", "active").limit(2000).execute().data or [])
    people: dict = {}
    for m in sorted(members, key=lambda x: (x.get("worker_name") or "", x.get("hive_id") or "")):
        if m.get("auth_uid") and m["auth_uid"] not in people:
            people[m["auth_uid"]] = m
    rows: list = []
    pages = sorted(ACTIONS)
    uids = sorted(people)
    picks = {uid: rng.sample(pages, rng.randint(3, 8)) for uid in uids}
    # ★EVERY PAGE GETS PEOPLE, NOT ONLY THE ONES THE DRAW HAPPENED TO PICK. A random 3-8 pages per account left
    # integrations with no visitor at all on the first run, so its figures did not exist (2026-10-27). Each page is
    # topped up to two accounts, round-robin, so every outcome row has a ledger to be computed from.
    for i, page in enumerate(pages):
        j = i * 2
        while sum(page in picks[u] for u in uids) < min(2, len(uids)):
            u = uids[j % len(uids)]
            j += 1
            if page not in picks[u]:
                picks[u].append(page)
    for uid in uids:
        m = people[uid]
        for page in picks[uid]:
            habit = rng.choice(HABITS)
            day = today - dt.timedelta(days=rng.randint(0, 85))
            session = "seed-" + hashlib.sha1(f"{uid}{page}".encode()).hexdigest()[:16]
            while day <= today:
                _visit(rows, page, day, rng, now, uid=uid, hive=m["hive_id"], name=m.get("worker_name"),
                       session=f"{session}-{day.isoformat()}")
                if habit is None:
                    break
                day += dt.timedelta(days=rng.randint(*habit))
    for n in range(40):
        page = rng.choice(PUBLIC)
        day = today - dt.timedelta(days=rng.randint(0, 30))
        _visit(rows, page, day, rng, now, session=f"seed-visitor-{n:03d}", max_uses=1)
    written = batch_insert(client, "analytics_events", rows) if rows else 0
    log(f"  analytics_events: {written} rows ({len(people)} accounts, 40 signed-out sessions)")
    return {"analytics_events": written}
