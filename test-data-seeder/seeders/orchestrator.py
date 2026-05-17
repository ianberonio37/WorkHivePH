"""Top-level orchestrator that runs all seeders in dependency order."""
import random

from .catalogs import seed_catalogs
from .hives_workers import seed_hives_and_workers
from .assets import seed_assets
from .pm import seed_pm
from .logbook import seed_logbook, link_logbook_to_asset_nodes
from .inventory import seed_inventory
from .skill_matrix import seed_skill_matrix
from .marketplace import seed_marketplace
from .community import seed_community
from .projects import seed_projects
from .dayplanner import seed_dayplanner
from .engineering import seed_engineering
from .fault_knowledge import seed_fault_knowledge
from .asset_brain import seed_asset_brain
from .reliability import seed_reliability
from .risk_scores import seed_risk_scores
from .shift_plans import seed_shift_plans
from .failure_alerts import seed_failure_alerts
from .parts_staging import seed_parts_staging
from .parts_reservations import seed_parts_reservations
from .achievements import seed_achievements
from .amc import seed_amc
from .sensor_readings import seed_sensor_readings
from .voice_journal import seed_voice_journal
from .industry_standards import seed_industry_standards
from .edge_post_seed import run_post_seed_edges


# Fixed RNG seed so each full reseed produces the same volume of rows per hive.
# Stable seed = stable page heights = visual regression baselines stay valid.
# If you need fresh randomness for ad-hoc exploration, override before calling.
SEEDER_RNG_SEED = 20260503


def seed_everything(client, log) -> dict:
    """Runs all seeders in correct order, sharing context between them."""
    random.seed(SEEDER_RNG_SEED)
    log("=" * 50)
    log("SEEDING EVERYTHING — this takes 1-3 minutes")
    log(f"  RNG seed: {SEEDER_RNG_SEED} (deterministic data shape)")
    log("=" * 50)

    ctx: dict = {}

    # Step 0: catalogs (must come before anything that triggers DB-side
    # achievement writes, which FK into achievement_definitions).
    step0 = seed_catalogs(client, log)

    step1 = seed_hives_and_workers(client, log)
    ctx.update(step1)

    step2 = seed_assets(client, log, ctx)
    ctx.update(step2)

    step3  = seed_pm(client, log, ctx)
    step4  = seed_logbook(client, log, ctx)
    step5  = seed_inventory(client, log, ctx)
    step6  = seed_skill_matrix(client, log, ctx)
    step7  = seed_marketplace(client, log, ctx)
    step8  = seed_community(client, log, ctx)
    step9  = seed_projects(client, log, ctx)   # Phase 6.5 — projects last so all parents exist
    step10 = seed_dayplanner(client, log, ctx)
    step11 = seed_engineering(client, log, ctx)
    step12 = seed_fault_knowledge(client, log, ctx)  # depends on seeded logbook
    # Phase A onward: graph + intelligence layers (depend on assets being in ctx)
    step12a = seed_asset_brain(client, log, ctx)
    # Phase 5b.1 bridge: backfill logbook.asset_node_id from the machine
    # tag now that asset_nodes exists. Without this, Asset Hub timeline
    # shows "No history rows tied to this asset yet."
    step12a_link = link_logbook_to_asset_nodes(client, log, ctx)
    # Phase R: Reliability Workbench (FMEA / RCM / Weibull / P-F).
    # Depends on asset_nodes existing (asset_brain inserts them).
    step12a2 = seed_reliability(client, log, ctx)
    step12b = seed_risk_scores(client, log, ctx)
    step12c = seed_shift_plans(client, log, ctx)
    step12d = seed_failure_alerts(client, log, ctx)
    # Auto-Staging surfaces (must run AFTER risk_scores + inventory exist)
    step12e = seed_parts_staging(client, log, ctx)
    step12f = seed_parts_reservations(client, log, ctx)
    seed_achievements(client, log)   # reads hive_members; no ctx, no return dict
    # Wave A+B features (AMC orchestrator + Physical AI). Run after assets +
    # PMs + inventory + workers exist (these seeders read them for context).
    step12g = seed_sensor_readings(client, log, ctx)
    step12h = seed_amc(client, log, ctx)             # reads assets/pms/inventory/workers
    step12i = seed_voice_journal(client, log, ctx)   # needs hive_members.auth_uid
    # Day 2 Azure sprint: extend industry_standards beyond the 10 migration-seeded rows
    step12j = seed_industry_standards(client, log)   # hive-agnostic catalog, no ctx needed
    step13 = run_post_seed_edges(client, log, ctx)   # depends on logbook + assets

    log("=" * 50)
    log("DONE")
    log("=" * 50)

    return {
        **step0,
        "hives": len(ctx["hives"]),
        "workers": len(ctx["workers"]),
        "assets": len(ctx["assets"]),
        **step3,
        **step4,
        **step5,
        **step6,
        **step7,
        **step8,
        **{f"projects_{k}": len(v) for k, v in step9.items()},
        **step10,
        **step11,
        **step12,
        **step12a,
        **step12a_link,
        **{f"reliability_{k}": v for k, v in step12a2.items()},
        **step12b,
        **step12c,
        **step12d,
        **step12e,
        **step12f,
        **step12g,
        **step12h,
        **step12i,
        **step12j,
        **step13,
    }
