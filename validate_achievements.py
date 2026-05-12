"""validate_achievements.py - Phase 1.9 of STRATEGIC_ROADMAP.md.

Architectural contract gate for the achievement system. Three latent bugs
have hit the achievement pipeline historically:

  1. badge_key column missing on skill_badges -> handle_community_post_xp
     trigger failed silently on the 10th post per author per hive
  2. achievement_definitions ended up in reset.py RESET_TABLES (catalog wipe)
     -> seeded data became orphan; FK from worker_achievements crashed
  3. worker_achievements not in supabase_realtime -> tier-frame badge UI
     never updated without manual refresh

Layers:
  L1  skill_badges.badge_key column exists (latent-bug guard)
  L2  achievement_definitions NOT in RESET_TABLES (catalog rule)
  L3  worker_achievements + achievement_xp_log child tables exist
  L4  worker_achievements is in supabase_realtime publication
  L5  handle_community_post_xp uses ON CONFLICT (worker_name, badge_key)

Skills consulted:
  data-engineer (catalog-vs-seeded distinction, ON CONFLICT requires matching
    unique index)
  realtime-engineer (tier badges need realtime fan-out)
  community (the 10-posts milestone is the entry achievement; if it silently
    fails, community feel collapses)
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).parent
MIGRATIONS = ROOT / "supabase" / "migrations"
RESET_PY   = ROOT / "test-data-seeder" / "seeders" / "reset.py"

LAYERS = [
    {"layer": "L1", "label": "skill_badges.badge_key column exists"},
    {"layer": "L2", "label": "achievement_definitions NOT in RESET_TABLES"},
    {"layer": "L3", "label": "worker_achievements + achievement_xp_log tables exist"},
    {"layer": "L4", "label": "worker_achievements is in supabase_realtime"},
    {"layer": "L5", "label": "handle_community_post_xp ON CONFLICT uses (worker_name, badge_key)"},
]


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _all_migrations() -> str:
    out: list[str] = []
    if not MIGRATIONS.exists():
        return ""
    for p in sorted(MIGRATIONS.glob("*.sql")):
        out.append(_read(p))
    return "\n".join(out)


def run() -> dict:
    issues: list[dict] = []
    blob = _all_migrations()

    # L1: skill_badges.badge_key column exists
    if "skill_badges" not in blob or "badge_key" not in blob:
        issues.append({"check": "l1", "layer": "L1",
                       "reason": "skill_badges.badge_key column not found in any "
                                 "migration. handle_community_post_xp trigger will "
                                 "fail with 42703 on the 10th post."})

    # L2: achievement_definitions must NOT be in reset.py
    if RESET_PY.exists():
        src = _read(RESET_PY)
        if '"achievement_definitions"' in src and "CATALOG" not in src:
            issues.append({"check": "l2", "layer": "L2",
                           "reason": "achievement_definitions appears in reset.py "
                                     "RESET_TABLES without a CATALOG_TABLES_IGNORED "
                                     "marker. It is a catalog/migration-seeded table; "
                                     "wiping it leaves worker_achievements FKs orphan."})
    else:
        issues.append({"check": "l2_reset_missing", "layer": "L2",
                       "reason": "test-data-seeder/seeders/reset.py not found; cannot "
                                 "verify catalog table protection."})

    # L3: child tables present
    if "worker_achievements" not in blob:
        issues.append({"check": "l3_worker_ach", "layer": "L3",
                       "reason": "worker_achievements table not in any migration."})
    if "achievement_xp_log" not in blob:
        issues.append({"check": "l3_xp_log", "layer": "L3",
                       "reason": "achievement_xp_log table not in any migration."})

    # L4: worker_achievements in supabase_realtime
    if ("ALTER PUBLICATION supabase_realtime" not in blob
            or "worker_achievements" not in blob):
        issues.append({"check": "l4", "layer": "L4",
                       "reason": "worker_achievements is not added to "
                                 "supabase_realtime. Tier frame badges will not "
                                 "live-update on level-ups."})

    # L5: ON CONFLICT shape
    if "ON CONFLICT (worker_name, badge_key)" not in blob:
        issues.append({"check": "l5", "layer": "L5",
                       "reason": "handle_community_post_xp must use "
                                 "ON CONFLICT (worker_name, badge_key) - that matches "
                                 "the unique index. Mismatch = trigger raises and "
                                 "community post fails."})

    failed_layers = {i.get("layer") for i in issues if i.get("layer")}
    failed = len(failed_layers)
    passed = len(LAYERS) - failed
    return {"validator": "achievements", "total_checks": len(LAYERS),
            "passed": passed, "failed": failed, "warned": 0,
            "layers": LAYERS, "issues": issues, "warnings": []}


def main() -> int:
    out = run()
    print(f"\nAchievements Validator ({len(out['layers'])}-layer)")
    print("=" * 55)
    for layer in out["layers"]:
        print(f"  [{layer['layer']}] {layer['label']}")
    print()
    if out["issues"]:
        print(f"  \033[91m{out['failed']} FAIL\033[0m")
        for i in out["issues"]:
            print(f"  [FAIL] [{i['check']}]  {i['reason']}")
    else:
        print(f"  \033[92mAll {out['total_checks']} checks passed.\033[0m")
    (ROOT / "achievements_report.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return 1 if out["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
