"""Seed skill_profiles + skill_badges + skill_exam_attempts."""
import random

from .utils import random_timestamp_in_last_n_days, to_iso

DISCIPLINES = [
    # Canonical platform disciplines, must match skill-content.js DISCIPLINES.
    # Don't add Hydraulics/HVAC/Welding/etc. here — those map back to one of these
    # 5 via CAT_TO_DISC in python-api/analytics/prescriptive.py.
    "Mechanical", "Electrical", "Instrumentation",
    "Facilities Management", "Production Lines",
]

PRIMARY_SKILLS = [
    "Rotating Equipment", "MV Switchgear", "PLC Programming", "Hydraulics & Pneumatics",
    "Refrigeration & HVAC", "Welding & Fabrication", "Steam Systems",
    "Vibration Analysis", "Process Safety", "Boiler Operation",
]


def seed_skill_matrix(client, log, ctx: dict) -> dict:
    workers = ctx["workers"]
    log(f"Seeding skill profiles + badges + exam attempts for {len(workers)} workers...")

    profile_rows = []
    for w in workers:
        primary = random.choice(PRIMARY_SKILLS)
        targets = {d: random.randint(1, 5) for d in random.sample(DISCIPLINES, k=4)}
        profile_rows.append({
            "worker_name": w["worker_name"],
            "primary_skill": primary,
            "targets": targets,
            "auth_uid": w.get("auth_uid"),
        })
    client.table("skill_profiles").insert(profile_rows).execute()
    log(f"  inserted {len(profile_rows)} skill_profiles")

    # Badges — supervisors get 3-5, active 2-3, light 0-2
    badge_rows = []
    attempt_rows = []
    badge_count_by_tier = {"heavy": (3, 5), "active": (2, 3), "light": (0, 2)}
    for w in workers:
        lo, hi = badge_count_by_tier.get(w["tier"], (0, 1))
        n_badges = random.randint(lo, hi)
        chosen_disciplines = random.sample(DISCIPLINES, k=n_badges) if n_badges else []
        for disc in chosen_disciplines:
            level = random.choices([1, 2, 3, 4, 5], weights=[20, 30, 30, 15, 5])[0]
            score = random.randint(70, 100)
            ts = random_timestamp_in_last_n_days(180)
            badge_rows.append({
                "worker_name": w["worker_name"],
                "discipline": disc,
                "level": level,
                "earned_at": to_iso(ts),
                "exam_score": score,
                "auth_uid": w.get("auth_uid"),
            })
            # Mirror an exam attempt that passed
            attempt_rows.append({
                "worker_name": w["worker_name"],
                "discipline": disc,
                "level": level,
                "score": score,
                "passed": True,
                "answers": {"summary": "auto-generated for seed"},
                "attempted_at": to_iso(ts),
                "auth_uid": w.get("auth_uid"),
            })
        # A few failed attempts for realism
        if random.random() < 0.4:
            disc = random.choice(DISCIPLINES)
            level = random.randint(2, 4)
            score = random.randint(40, 69)
            attempt_rows.append({
                "worker_name": w["worker_name"],
                "discipline": disc,
                "level": level,
                "score": score,
                "passed": False,
                "answers": {"summary": "failed - seed"},
                "attempted_at": to_iso(random_timestamp_in_last_n_days(180)),
                "auth_uid": w.get("auth_uid"),
            })

    if badge_rows:
        client.table("skill_badges").insert(badge_rows).execute()
    log(f"  inserted {len(badge_rows)} skill_badges")
    if attempt_rows:
        client.table("skill_exam_attempts").insert(attempt_rows).execute()
    log(f"  inserted {len(attempt_rows)} skill_exam_attempts")

    return {
        "skill_profiles_count": len(profile_rows),
        "skill_badges_count": len(badge_rows),
        "skill_attempts_count": len(attempt_rows),
    }
