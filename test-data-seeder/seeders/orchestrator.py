"""Top-level orchestrator that runs all seeders in dependency order."""
import random

from .catalogs import seed_catalogs
from .hives_workers import seed_hives_and_workers
from .assets import seed_assets
from .pm import seed_pm
from .logbook import seed_logbook, link_logbook_to_asset_nodes
from .inventory import seed_inventory
from .skill_matrix import seed_skill_matrix
from .marketplace import (seed_marketplace, seed_marketplace_sellers,
                          seed_marketplace_orders, seed_marketplace_inquiries)
from .services import seed_services
from .community import seed_community
from .projects import seed_projects
from .dayplanner import seed_dayplanner
from .engineering import seed_engineering
from .companion_memory import seed_companion_memory
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
from .embed_corpus import run_post_seed_embed
from .probe_fixtures import seed_probe_fixtures
from .fleets import seed_fleets
from .analytics_history import seed_analytics_history


# Fixed RNG seed so each full reseed produces the same volume of rows per hive.
# Stable seed = stable page heights = visual regression baselines stay valid.
# If you need fresh randomness for ad-hoc exploration, override before calling.
SEEDER_RNG_SEED = 20260503


def rebind_platform_admins(client, log) -> None:
    """Point each platform admin row at its person's CURRENT account (2026-10-26). marketplace_platform_admins has no
    `id`, so reset.py cannot clear it and its rows outlive every reseed - while the accounts they name are recreated
    with new ids, and is_platform_admin() matches auth_uid. After a reseed nobody was an admin: the founder console
    refused both seeded admins. Rows are bound by name to worker_profiles; a name with no profile is left as it is."""
    try:
        admins = client.table("marketplace_platform_admins").select("worker_name, auth_uid").execute().data or []
        bound = 0
        for a in admins:
            prof = client.table("worker_profiles").select("auth_uid").eq("display_name", a["worker_name"]).limit(1).execute().data
            uid = prof[0]["auth_uid"] if prof else None
            if uid and uid != a.get("auth_uid"):
                client.table("marketplace_platform_admins").update({"auth_uid": uid}).eq("worker_name", a["worker_name"]).execute()
                bound += 1
        log(f"  platform admins: {len(admins)} on record, {bound} re-bound to their current account")
    except Exception as e:  # never fail a seed over an admin binding; say so
        log(f"  WARN: could not re-bind platform admins: {e}")


# Tables whose seeded rows name a person and carry no account (the seeder writes as the service role, which the binding
# triggers leave alone). The live database got its auth_uid from one-time backfill migrations; a CLEAN seed never did,
# so a reseed left 56 achievements, 160 cost rows and 60 gateway rows authorless - and every psql probe that grounds on
# "a member with rows here" found no fixture (2026-10-27). A row with no worker_name stays unbound: that is a visitor.
AUTHOR_BOUND_TABLES = ("worker_achievements", "ai_cost_log", "gateway_audit_log", "agent_memory",
                       "agent_episodic_memory", "client_errors")


def bind_seeded_authors(client, log) -> None:
    """Give each seeded row that names a person that person's account, by their profile name."""
    try:
        profiles = client.table("worker_profiles").select("auth_uid, display_name").limit(2000).execute().data or []
        uid_of = {p["display_name"]: p["auth_uid"] for p in profiles if p.get("display_name") and p.get("auth_uid")}
        for t in AUTHOR_BOUND_TABLES:
            names = {r["worker_name"] for r in (client.table(t).select("worker_name").is_("auth_uid", "null")
                                                 .not_.is_("worker_name", "null").limit(5000).execute().data or [])}
            bound = 0
            for n in sorted(names):
                if n in uid_of:
                    res = client.table(t).update({"auth_uid": uid_of[n]}).eq("worker_name", n).is_("auth_uid", "null").execute()
                    bound += len(res.data or [])
            log(f"  {t}: {bound} seeded row(s) bound to their author's account ({len(names)} name(s) unbound before)")
    except Exception as e:  # never fail a seed over a binding; say so
        log(f"  WARN: could not bind seeded authors: {e}")


def run_history_tools(log) -> None:
    """The tools/ seeders that give the fleets an operating life and every hive five years of history (2026-10-27).

    They were run by hand once, so a reset erased what they wrote and nothing ran them again: the fleets came back
    empty and validate_fixture_depth found no 'year-2', 'month-3' or 'day-1' in any hive. Each is idempotent (it checks
    what a hive already holds) and is run here with this interpreter; a failure is said, never fatal."""
    import os
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    if not env.get("SUPABASE_SERVICE_ROLE_KEY"):
        try:   # the local edge runtime's own service key (never printed, never stored)
            r = subprocess.run(["docker", "exec", "supabase_edge_runtime_workhive", "printenv", "SUPABASE_SERVICE_ROLE_KEY"],
                               capture_output=True, text=True, timeout=20)
            if r.returncode == 0 and r.stdout.strip():
                env["SUPABASE_SERVICE_ROLE_KEY"] = r.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    for args in (["tools/seed_fleet_history.py", "--apply"], ["tools/backfill_fleet_seed_gaps.py"],
                 ["tools/seed_multi_hive_worker.py", "--apply"], ["tools/seed_5y_synthetic_history.py", "--commit"]):
        try:
            r = subprocess.run([sys.executable, *args], cwd=root, env=env, capture_output=True, text=True, timeout=1200)
            tail = (r.stdout or r.stderr or "").strip().splitlines()[-1:] or [""]
            log(f"  {args[0]}: {'ok' if r.returncode == 0 else 'WARN exit ' + str(r.returncode)} - {tail[0][:140]}")
        except Exception as e:
            log(f"  WARN: {args[0]} did not run: {str(e)[:140]}")


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
    seed_companion_memory(client, log, ctx)  # >=1 episodic + agent_memory row so a fresh reseed leaves companion_memory_health_gate GREEN (dead-on-reset fix)
    step11 = seed_engineering(client, log, ctx)  # before projects: eng-design calcs must exist for the project_links design-basis bundle (PM X-keystone)
    step9  = seed_projects(client, log, ctx)   # Phase 6.5 — projects after logbook/pm/inventory/engineering so ALL bundle parents exist
    step10 = seed_dayplanner(client, log, ctx)
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
    # Community<->Marketplace bridge: seller profiles LINKED to community reputation
    # (grants each hive's top voice-of-hive badge + gold seller). Runs AFTER community
    # + achievements so a seller's community standing already exists.
    step_ms = seed_marketplace_sellers(client, log, ctx)
    # T96 (2026-08-27): the goods lifecycle needs rows to be walkable at all.
    # marketplace_orders enumerates a real escrow flow in a CHECK constraint and had
    # never held a row - reset.py could truncate orders, nothing could create one - so
    # no state transition on it had ever been exercised. One order per state, seeded
    # after listings and sellers exist because each order references a real listing.
    step_mo = seed_marketplace_orders(client, log, ctx)
    # ...and the LIVE goods path, which is contact-only: buyers send inquiries against a
    # listing and sellers reply. marketplace-seller's Inquiries tab reads this in six
    # places and never reads orders, so this is the table the two-sided goods walk needs.
    step_mi = seed_marketplace_inquiries(client, log, ctx)
    # Service-hailing substrate (SERVICE_HAILING_ROADMAP.md P1) — after marketplace
    # sellers + workers/hives exist (providers are built from both).
    step_sv = seed_services(client, log, ctx)
    # Wave A+B features (AMC orchestrator + Physical AI). Run after assets +
    # PMs + inventory + workers exist (these seeders read them for context).
    step12g = seed_sensor_readings(client, log, ctx)
    step12h = seed_amc(client, log, ctx)             # reads assets/pms/inventory/workers
    step12i = seed_voice_journal(client, log, ctx)   # needs hive_members.auth_uid
    # Day 2 Azure sprint: extend industry_standards beyond the 10 migration-seeded rows
    step12j = seed_industry_standards(client, log)   # hive-agnostic catalog, no ctx needed
    step13 = run_post_seed_edges(client, log, ctx)   # depends on logbook + assets
    step13b = run_post_seed_embed(client, log, ctx)  # §10.5 co-land: populate RAG index (skips if bge :8901 down)
    seed_fleets(client, log)                         # the vehicle vertical (history: the tools/ fleet seeders after)
    rebind_platform_admins(client, log)
    bind_seeded_authors(client, log)
    seed_probe_fixtures(client, log)                 # the rows tools/psql_probes ground on (after authors are bound)
    seed_analytics_history(client, log)              # 90 days of visits and uses: the outcome figures' ledger (T2 OUT)
    run_history_tools(log)                           # fleets' operating life + five years of history in every hive

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
        **step_ms,
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
