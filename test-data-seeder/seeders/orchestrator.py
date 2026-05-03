"""Top-level orchestrator that runs all seeders in dependency order."""
from .hives_workers import seed_hives_and_workers
from .assets import seed_assets
from .pm import seed_pm
from .logbook import seed_logbook
from .inventory import seed_inventory
from .skill_matrix import seed_skill_matrix
from .marketplace import seed_marketplace
from .community import seed_community


def seed_everything(client, log) -> dict:
    """Runs all seeders in correct order, sharing context between them."""
    log("=" * 50)
    log("SEEDING EVERYTHING — this takes 1-3 minutes")
    log("=" * 50)

    ctx: dict = {}

    step1 = seed_hives_and_workers(client, log)
    ctx.update(step1)

    step2 = seed_assets(client, log, ctx)
    ctx.update(step2)

    step3 = seed_pm(client, log, ctx)
    step4 = seed_logbook(client, log, ctx)
    step5 = seed_inventory(client, log, ctx)
    step6 = seed_skill_matrix(client, log, ctx)
    step7 = seed_marketplace(client, log, ctx)
    step8 = seed_community(client, log, ctx)

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
    }
