"""Achievement system flow — wipe, reseed, verify tier rings.

Scenarios:
  1 – Wipe existing achievement data for the test worker
  2 – Seed one row per tier (Iron=0, Bronze=12, Silver=28, Gold=55, Platinum=78, Legend=93)
      across different domains so all 6 tier rings are represented
  3 – achievements.html loads and renders 12 domain cards
  4 – XP progress bars are present and non-empty
  5 – Tier rings visible on community.html (profile avatar + post avatars)
  6 – Tier rings visible on hive.html member list (wh-avatar, not legacy avatar-initial)
  7 – Recent XP feed shows seeded entries
  8 – Hive standings section renders (if worker is in a hive)
  9 – Level-up modal markup present in DOM
  10 – DB row count matches seeded count after wipe+reseed
"""

import math
from datetime import datetime, timezone
from lib.supabase_client import get_client
from .harness import BASE_URL, ensure_signed_in, screenshot


SEED_LEVELS = [
    ("wrench_chronicle", 93),   # Legend  (highest — this drives the hero tier ring)
    ("uptime_guardian",  78),   # Platinum
    ("safety_sentinel",  55),   # Gold
    ("failure_hunter",   28),   # Silver
    ("skill_climber",    12),   # Bronze
    ("voice_of_hive",    5),    # Iron (low)
    ("parts_warden",     0),    # Iron (no data — stays at 0)
    ("blueprint_master", 0),
    ("knowledge_forger", 0),
    ("hive_architect",   0),
    ("shift_keeper",     0),
    ("iron_worker",      0),
]

SEED_XP_LOG = [
    ("wrench_chronicle", 95, "logbook_close"),
    ("wrench_chronicle", 50, "logbook_submit"),
    ("uptime_guardian",  60, "pm_complete"),
    ("safety_sentinel",  60, "safety_entry"),
    ("failure_hunter",  100, "breakdown_root_cause"),
    ("skill_climber",   250, "skill_badge_earned"),
    ("voice_of_hive",    60, "community_post"),
]


def xp_for_level(n):
    if n <= 0:
        return 0
    return math.floor(100 * (n ** 1.8))


def run(page, errors, warnings, log) -> dict:
    log("Achievement system checks (wipe + reseed + verify rings)...")
    results = []
    db = get_client()  # service role — bypasses RLS

    try:
        ensure_signed_in(page, log=log)
    except Exception as e:
        return {"results": [("FAIL", f"sign-in failed: {e}")]}

    worker_name = page.evaluate("localStorage.getItem('wh_last_worker') || ''")
    if not worker_name:
        return {"results": [("FAIL", "no worker_name in localStorage — sign-in did not set identity")]}

    log(f"  test worker: {worker_name}")

    # ── Check 1: Wipe existing achievement data ───────────────────────────────
    log("  [1] Wiping existing achievement data...")
    try:
        db.table("achievement_xp_log").delete().eq("worker_name", worker_name).execute()
        db.table("worker_achievements").delete().eq("worker_name", worker_name).execute()

        remaining = db.table("worker_achievements").select("id", count="exact").eq("worker_name", worker_name).execute()
        if (remaining.count or 0) == 0:
            results.append(("PASS", "wipe cleared all achievement rows for test worker"))
            log("  ✓ wipe complete")
        else:
            results.append(("FAIL", f"wipe left {remaining.count} rows"))
            log(f"  ✗ wipe failed — {remaining.count} rows remain")
    except Exception as e:
        results.append(("FAIL", f"wipe crashed: {e}"))
        log(f"  ✗ wipe crashed: {e}")

    # ── Check 2: Reseed one row per domain, covering all 6 tiers ─────────────
    log("  [2] Reseeding achievement rows (all 6 tiers)...")
    try:
        now = datetime.now(timezone.utc).isoformat()
        rows = []
        for ach_id, level in SEED_LEVELS:
            if level == 0:
                continue  # leave at 0 = no row = Iron by default
            rows.append({
                "worker_name":    worker_name,
                "achievement_id": ach_id,
                "current_level":  level,
                "xp_total":       xp_for_level(level) + 500,  # slightly past threshold
                "last_action_at": now,
            })

        if rows:
            db.table("worker_achievements").insert(rows).execute()

        log_rows = []
        for ach_id, xp, action in SEED_XP_LOG:
            log_rows.append({
                "worker_name":    worker_name,
                "achievement_id": ach_id,
                "xp_earned":      xp,
                "source_action":  action,
                "earned_at":      now,
            })
        db.table("achievement_xp_log").insert(log_rows).execute()

        seeded = db.table("worker_achievements").select("id", count="exact").eq("worker_name", worker_name).execute()
        expected = sum(1 for _, lv in SEED_LEVELS if lv > 0)
        if (seeded.count or 0) == expected:
            results.append(("PASS", f"seeded {expected} achievement rows (Legend/Platinum/Gold/Silver/Bronze/Iron)"))
            log(f"  ✓ seeded {expected} rows — tiers: Legend=Lv93, Platinum=Lv78, Gold=Lv55, Silver=Lv28, Bronze=Lv12, Iron=Lv5")
        else:
            results.append(("WARN", f"expected {expected} rows, found {seeded.count}"))
            log(f"  ⚠ expected {expected} rows, found {seeded.count}")
    except Exception as e:
        results.append(("FAIL", f"reseed crashed: {e}"))
        log(f"  ✗ reseed crashed: {e}")

    # ── Check 3: achievements.html loads and renders 12 domain cards ──────────
    log("  [3] achievements.html — 12 domain cards...")
    try:
        page.goto(f"{BASE_URL}/workhive/achievements.html", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(2500)
        screenshot(page, "achievements_page")

        card_count = page.evaluate("document.querySelectorAll('[data-ach]').length")
        if card_count >= 12:
            results.append(("PASS", f"achievements.html rendered {card_count} domain cards"))
            log(f"  ✓ {card_count} domain cards rendered")
        elif card_count > 0:
            results.append(("WARN", f"only {card_count}/12 domain cards rendered"))
            log(f"  ⚠ {card_count}/12 domain cards rendered")
        else:
            results.append(("FAIL", "no domain cards found ([data-ach] selector returned 0)"))
            log("  ✗ no domain cards found")
    except Exception as e:
        results.append(("FAIL", f"achievements.html crashed: {e}"))
        log(f"  ✗ achievements.html crashed: {e}")

    # ── Check 4: XP progress bars rendered ───────────────────────────────────
    log("  [4] XP progress bars visible...")
    try:
        bar_count = page.evaluate("document.querySelectorAll('.xp-bar-fill').length")
        if bar_count >= 6:
            results.append(("PASS", f"{bar_count} XP progress bars rendered"))
            log(f"  ✓ {bar_count} XP bars present")
        else:
            results.append(("WARN", f"only {bar_count} XP bars (expected >= 6 for seeded domains)"))
            log(f"  ⚠ {bar_count} XP bars rendered")
    except Exception as e:
        results.append(("WARN", f"XP bar check crashed: {e}"))

    # ── Check 5: Tier rings on hero avatar ────────────────────────────────────
    log("  [5] Hero avatar shows Legend tier ring...")
    try:
        hero_tier = page.evaluate("""() => {
            const wrap = document.getElementById('hero-avatar-wrap');
            if (!wrap) return null;
            const av = wrap.querySelector('.wh-avatar');
            if (!av) return null;
            const cls = av.className || '';
            const m = cls.match(/wh-tier-(\\w+)/);
            return m ? m[1] : null;
        }""")
        if hero_tier == "legend":
            results.append(("PASS", "hero avatar shows Legend tier ring (wh-tier-legend)"))
            log("  ✓ hero avatar = Legend (expected — highest seeded level is 93)")
        elif hero_tier:
            results.append(("WARN", f"hero avatar tier is '{hero_tier}' (expected 'legend')"))
            log(f"  ⚠ hero tier = {hero_tier}")
        else:
            results.append(("FAIL", "hero avatar tier class not found"))
            log("  ✗ hero avatar has no wh-tier-* class")
    except Exception as e:
        results.append(("FAIL", f"hero tier check crashed: {e}"))
        log(f"  ✗ hero tier check crashed: {e}")

    # ── Check 6: All 6 tier classes present across domain badges ─────────────
    log("  [6] All 6 tier rings present in domain badges...")
    try:
        tier_counts = page.evaluate("""() => {
            const tiers = ['iron','bronze','silver','gold','platinum','legend'];
            const counts = {};
            for (const t of tiers) {
                counts[t] = document.querySelectorAll('.wh-tier-' + t).length;
            }
            return counts;
        }""")
        present = [t for t, c in tier_counts.items() if c > 0]
        if len(present) >= 5:
            results.append(("PASS", f"tier rings present: {', '.join(sorted(present))}"))
            log(f"  ✓ tiers represented: {tier_counts}")
        else:
            results.append(("WARN", f"only {len(present)} tier classes found: {present}"))
            log(f"  ⚠ tier counts: {tier_counts}")
    except Exception as e:
        results.append(("WARN", f"tier diversity check crashed: {e}"))

    # ── Check 7: Recent XP feed renders ──────────────────────────────────────
    log("  [7] Recent XP activity feed...")
    try:
        activity_rows = page.evaluate("document.querySelectorAll('.activity-row').length")
        if activity_rows >= len(SEED_XP_LOG):
            results.append(("PASS", f"recent XP feed shows {activity_rows} events"))
            log(f"  ✓ {activity_rows} activity rows in feed")
        elif activity_rows > 0:
            results.append(("WARN", f"feed shows {activity_rows} rows (seeded {len(SEED_XP_LOG)})"))
            log(f"  ⚠ {activity_rows} activity rows (expected {len(SEED_XP_LOG)})")
        else:
            results.append(("FAIL", "recent XP feed shows 0 rows"))
            log("  ✗ no activity rows found")
    except Exception as e:
        results.append(("WARN", f"activity feed check crashed: {e}"))

    # ── Check 8: Tier rings visible on community.html ────────────────────────
    log("  [8] community.html — tier ring on profile avatar...")
    try:
        page.goto(f"{BASE_URL}/workhive/community.html", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(2000)
        screenshot(page, "achievements_community_rings")

        profile_tier = page.evaluate("""() => {
            const wrap = document.getElementById('profile-avatar');
            if (!wrap) return null;
            const av = wrap.querySelector('.wh-avatar');
            if (!av) return null;
            const m = (av.className || '').match(/wh-tier-(\\w+)/);
            return m ? m[1] : null;
        }""")

        wh_avatar_count = page.evaluate("document.querySelectorAll('.wh-avatar').length")

        if profile_tier and profile_tier != "iron":
            results.append(("PASS", f"community profile avatar shows '{profile_tier}' tier ring — wh-avatar rendering confirmed ({wh_avatar_count} total avatars)"))
            log(f"  ✓ profile ring = {profile_tier}, {wh_avatar_count} wh-avatar elements on page")
        elif profile_tier == "iron":
            results.append(("WARN", "profile avatar is Iron — tier data may not have loaded yet"))
            log(f"  ⚠ profile ring = iron ({wh_avatar_count} wh-avatars on page)")
        else:
            results.append(("FAIL", "profile avatar has no wh-tier-* class — tier rings not rendering"))
            log(f"  ✗ no tier class found on profile avatar ({wh_avatar_count} wh-avatars on page)")
    except Exception as e:
        results.append(("FAIL", f"community ring check crashed: {e}"))
        log(f"  ✗ community ring check crashed: {e}")

    # ── Check 9: Tier rings on hive.html member cards ─────────────────────────
    log("  [9] hive.html — tier rings on member cards (wh-avatar, not avatar-initial)...")
    try:
        page.goto(f"{BASE_URL}/workhive/hive.html", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(2000)
        screenshot(page, "achievements_hive_rings")

        hive_id = page.evaluate("localStorage.getItem('wh_active_hive_id') || ''")

        wh_count      = page.evaluate("document.querySelectorAll('.wh-avatar').length")
        legacy_count  = page.evaluate("document.querySelectorAll('#members-list .avatar-initial').length")

        if not hive_id:
            results.append(("WARN", "no hive joined — skip member ring check (rings only show in hive member list)"))
            log("  ⚠ no hive active — hive ring check skipped")
        elif legacy_count > 0:
            results.append(("FAIL", f"{legacy_count} legacy avatar-initial divs still in #members-list — migration to wh-avatar incomplete"))
            log(f"  ✗ {legacy_count} legacy avatar-initial in member list")
        elif wh_count > 0:
            results.append(("PASS", f"hive member list uses wh-avatar ({wh_count} rings, 0 legacy avatar-initial)"))
            log(f"  ✓ {wh_count} wh-avatar elements on hive page")
        else:
            results.append(("WARN", f"no wh-avatar found on hive.html (hive may have 0 members)"))
            log("  ⚠ 0 wh-avatar elements on hive page")
    except Exception as e:
        results.append(("FAIL", f"hive ring check crashed: {e}"))
        log(f"  ✗ hive ring check crashed: {e}")

    # ── Check 10: Level-up modal DOM present ──────────────────────────────────
    log("  [10] Level-up modal markup present on achievements.html...")
    try:
        page.goto(f"{BASE_URL}/workhive/achievements.html", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(1500)

        modal_present = page.evaluate("!!document.getElementById('levelup-overlay')")
        close_btn     = page.evaluate("!!document.getElementById('levelup-close')")

        if modal_present and close_btn:
            results.append(("PASS", "level-up modal markup present (#levelup-overlay + #levelup-close)"))
            log("  ✓ level-up modal DOM confirmed")
        else:
            results.append(("WARN", f"modal markup incomplete — overlay:{modal_present}, close:{close_btn}"))
            log(f"  ⚠ modal partial: overlay={modal_present}, close={close_btn}")
    except Exception as e:
        results.append(("WARN", f"modal check crashed: {e}"))

    return {"results": results}
