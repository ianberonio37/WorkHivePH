"""Top-level orchestrator that runs all seeders in dependency order."""
import random

from .hives_workers import seed_hives_and_workers
from .assets import seed_assets
from .pm import seed_pm
from .logbook import seed_logbook
from .inventory import seed_inventory
from .skill_matrix import seed_skill_matrix
from .marketplace import seed_marketplace
from .community import seed_community
from .projects import seed_projects
from .dayplanner import seed_dayplanner
from .engineering import seed_engineering
from .fault_knowledge import seed_fault_knowledge
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
    step13 = run_post_seed_edges(client, log, ctx)   # depends on logbook + assets

    log("=" * 50)
    log("DONE")
    log("=" * 50)

    return {
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
        **step13,
    }
