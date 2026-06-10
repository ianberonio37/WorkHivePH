"""
WorkHive Platform Intelligence
Pulls real maintenance data from Supabase + defines the feature ecosystem and WorkHive Loop.
Falls back gracefully if Supabase is offline.

Used by the video marketing tool to generate ideas rooted in the actual platform,
not generic marketing copy.
"""

import os
import re
import json
import requests
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent

# ── Env loading ───────────────────────────────────────────────────────────────

def _load_env():
    for p in [
        ROOT / "test-data-seeder/.env",
        ROOT / "supabase/functions/.env",
        ROOT / ".env",
    ]:
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

_load_env()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_KEY", "")

# ── WorkHive feature ecosystem ────────────────────────────────────────────────

FEATURE_ECOSYSTEM = {
    "Maintenance Logbook": {
        "connects_to": ["AI Maintenance Assistant", "Shift Handover Report", "PM Checklist", "Community Forum", "Asset Brain", "Achievements", "Predictive Analytics", "Audit Log & Compliance"],
        "tables":       ["logbook"],
        "edge_fns":     ["failure-signature-scan", "embed-entry", "voice-logbook-entry", "voice-transcribe", "voice-action-router"],
        "loop_role":    "Foundation layer. Every repair, every failure, every fix recorded — by typing, by voice, or by voice command. Without it everything else is guesswork.",
        "audience":     ["Field Technician", "Supervisor", "Plant Manager"],
    },
    "PM Checklist": {
        "connects_to": ["Inventory Management", "Maintenance Logbook", "Hive Dashboard", "Skill Matrix", "Shift Brain", "Asset Brain", "Achievements"],
        "tables":       ["pm_assets", "pm_completions", "pm_scope_items"],
        "edge_fns":     [],
        "loop_role":    "Prevention layer. Stops failures before they happen. Each completed PM feeds the logbook, the dashboard, and the shift plan.",
        "audience":     ["Field Technician", "Supervisor"],
    },
    "Inventory Management": {
        "connects_to": ["PM Checklist", "Marketplace", "Hive Dashboard", "Predictive Analytics", "Shift Brain", "Alert Hub"],
        "tables":       ["inventory_items", "inventory_transactions", "parts_staged_reservations"],
        "edge_fns":     [],
        "loop_role":    "Readiness layer. Maintenance only works if the part is there. Low stock alerts before surprises happen — and Auto-Staging now reserves parts in advance for predicted failures.",
        "audience":     ["Supervisor", "Plant Manager"],
    },
    "AI Maintenance Assistant": {
        "connects_to": ["Maintenance Logbook", "PM Checklist", "Skill Matrix", "Asset Brain"],
        "tables":       ["logbook", "fault_knowledge", "pm_knowledge"],
        "edge_fns":     ["ai-orchestrator", "semantic-search", "scheduled-agents"],
        "loop_role":    "Intelligence layer. Turns recorded data into answers. The more the logbook grows, the smarter the AI gets.",
        "audience":     ["Field Technician", "Engineer", "Plant Manager"],
    },
    "Hive Dashboard": {
        "connects_to": ["Maintenance Logbook", "PM Checklist", "Inventory Management", "Skill Matrix", "Analytics & OEE Dashboard", "Alert Hub"],
        "tables":       ["hive_analytics_cache", "hive_audit_log"],
        "edge_fns":     ["analytics-orchestrator", "benchmark-compute"],
        "loop_role":    "Visibility layer. The manager sees everything in real time: open work, downtime, PM rate, all in one screen.",
        "audience":     ["Supervisor", "Plant Manager"],
    },
    "Shift Handover Report": {
        "connects_to": ["Maintenance Logbook", "PM Checklist", "Shift Brain"],
        "tables":       ["logbook"],
        "edge_fns":     [],
        "loop_role":    "Continuity layer. Nothing falls through the cracks between shifts. Open issues, hot machines, pending PMs all transferred.",
        "audience":     ["Supervisor", "Field Technician"],
    },
    "Day Planner": {
        "connects_to": ["PM Checklist", "Skill Matrix", "Shift Handover Report", "Shift Brain"],
        "tables":       ["dayplanner_events"],
        "edge_fns":     [],
        "loop_role":    "Scheduling layer. Right person, right task, right time. Plans the week so PMs never pile up.",
        "audience":     ["Supervisor", "Plant Manager"],
    },
    "Engineering Design Calculator": {
        "connects_to": ["Maintenance Logbook", "Asset Brain", "Project Manager"],
        "tables":       ["calc_knowledge", "bom_knowledge"],
        "edge_fns":     ["engineering-calc-agent", "engineering-bom-sow"],
        "loop_role":    "Standards layer. Every calculation done to Philippine engineering standards. Results saved as permanent reference.",
        "audience":     ["Engineer", "Plant Manager"],
    },
    "Skill Matrix": {
        "connects_to": ["PM Checklist", "Day Planner", "AI Maintenance Assistant", "Achievements", "Project Manager"],
        "tables":       ["skill_profiles", "skill_badges"],
        "edge_fns":     [],
        "loop_role":    "Competency layer. Knows who can do what. Prevents assigning a job to someone untrained. Identifies gaps before they become safety risks.",
        "audience":     ["Supervisor", "Plant Manager"],
    },
    "Marketplace": {
        "connects_to": ["Inventory Management", "PH Industry Intelligence"],
        "tables":       ["marketplace_sellers", "marketplace_orders"],
        "edge_fns":     ["marketplace-checkout", "marketplace-webhook", "marketplace-connect-onboard", "marketplace-connect-status", "marketplace-release"],
        "loop_role":    "Supply layer. When inventory hits critical, the marketplace connects you to verified sellers across Philippine plants.",
        "audience":     ["Supervisor", "Plant Manager"],
    },
    "Community Forum": {
        "connects_to": ["AI Maintenance Assistant", "Maintenance Logbook", "Achievements"],
        "tables":       ["community_posts", "community_replies", "community_xp"],
        "edge_fns":     [],
        "loop_role":    "Knowledge layer. Plant workers sharing solutions. Best answers feed the AI and the knowledge base.",
        "audience":     ["Field Technician", "Engineer"],
    },

    # ── New features added 2026-05 ──────────────────────────────────────────

    "Analytics & OEE Dashboard": {
        "connects_to": ["Maintenance Logbook", "PM Checklist", "Predictive Analytics", "Hive Dashboard", "PH Industry Intelligence"],
        "tables":       ["hive_analytics_cache", "logbook"],
        "edge_fns":     ["analytics-orchestrator", "benchmark-compute"],
        "loop_role":    "Insight layer. Turns raw maintenance data into OEE, MTBF, downtime trends across 4 phases — Descriptive, Diagnostic, Predictive, Prescriptive.",
        "audience":     ["Plant Manager", "Supervisor", "Engineer"],
    },
    "Predictive Analytics": {
        "connects_to": ["Maintenance Logbook", "Inventory Management", "Asset Brain", "Alert Hub", "Analytics & OEE Dashboard"],
        "tables":       ["asset_risk_scores", "logbook", "inventory_transactions", "parts_staged_reservations"],
        "edge_fns":     ["batch-risk-scoring", "trigger-ml-retrain", "parts-staging-recommender", "weibull-fitter", "pf-calculator", "fmea-populator"],
        "loop_role":    "Foresight layer. ML scores every asset by failure risk, real reliability math (Weibull, P-F intervals, FMEA) backs the model, and Auto-Staging reserves the parts before the failure happens. Predict, prepare, prevent.",
        "audience":     ["Plant Manager", "Supervisor", "Engineer"],
    },
    "Asset Brain": {
        "connects_to": ["Maintenance Logbook", "PM Checklist", "Predictive Analytics", "Engineering Design Calculator", "AI Maintenance Assistant"],
        "tables":       ["asset_nodes", "asset_edges", "asset_brain_overview"],
        "edge_fns":     ["asset-brain-query"],
        "loop_role":    "Asset memory layer. Every machine's full lifetime in one Asset 360 view — failures, PMs, parts, sister assets, parent plant. ISO 14224 hierarchy.",
        "audience":     ["Engineer", "Plant Manager", "Field Technician"],
    },
    "Shift Brain": {
        "connects_to": ["Shift Handover Report", "PM Checklist", "Predictive Analytics", "Day Planner", "Inventory Management"],
        "tables":       ["shift_plans"],
        "edge_fns":     ["shift-planner-orchestrator"],
        "loop_role":    "Shift intelligence layer. AI generates the next shift's plan before sign-on: top risks, due PMs, carry-overs from previous shift, parts to pre-stage, who does what.",
        "audience":     ["Supervisor", "Plant Manager"],
    },
    "Achievements": {
        "connects_to": ["Maintenance Logbook", "Skill Matrix", "Community Forum", "PM Checklist"],
        "tables":       ["achievements", "skill_badges"],
        "edge_fns":     [],
        "loop_role":    "Recognition layer. Levels, XP, and badges for every closed logbook entry, completed PM, helpful community answer. Makes maintenance work feel like progress.",
        "audience":     ["Field Technician", "Engineer"],
    },
    "Alert Hub": {
        "connects_to": ["Predictive Analytics", "PM Checklist", "Inventory Management", "Maintenance Logbook"],
        "tables":       ["alert_log"],
        "edge_fns":     ["scheduled-agents", "failure-signature-scan"],
        "loop_role":    "Attention layer. One inbox for everything that needs action: critical risk spikes, overdue PMs, low stock, failure signature alerts.",
        "audience":     ["Supervisor", "Plant Manager", "Field Technician"],
    },
    "PH Industry Intelligence": {
        "connects_to": ["Hive Dashboard", "Analytics & OEE Dashboard", "Marketplace"],
        "tables":       ["ph_intelligence_reports"],
        "edge_fns":     ["intelligence-report", "intelligence-api"],
        "loop_role":    "Benchmark layer. Compares your plant's KPIs against Philippine industry peers. Shows where you lead and where you lag.",
        "audience":     ["Plant Manager"],
    },
    "CMMS Integrations": {
        "connects_to": ["Maintenance Logbook", "PM Checklist", "Inventory Management", "Asset Brain"],
        "tables":       [],
        "edge_fns":     ["cmms-sync", "cmms-push-completion", "cmms-webhook-receiver"],
        "loop_role":    "Bridge layer. Two-way sync with SAP PM, IBM Maximo, Fiix and other CMMS systems. Use WorkHive without abandoning existing investment.",
        "audience":     ["Plant Manager", "IT/OT Manager"],
    },
    "Project Manager": {
        "connects_to": ["Maintenance Logbook", "Inventory Management", "Skill Matrix", "Engineering Design Calculator"],
        "tables":       ["projects", "project_tasks"],
        "edge_fns":     ["project-orchestrator", "project-progress"],
        "loop_role":    "Coordination layer. Long-running maintenance projects (overhauls, shutdowns, capex) tracked end-to-end with milestones, parts staging, skill assignments.",
        "audience":     ["Plant Manager", "Engineer"],
    },
    "Resume Builder": {
        "connects_to": ["Skill Matrix", "Maintenance Logbook", "Achievements"],
        "tables":       ["resumes"],
        "edge_fns":     ["resume-extract", "resume-polish"],
        "loop_role":    "Career layer. Turns real logged work and verified skills into an ATS-ready resume. Every repair you log becomes proof on paper - career protection in the AI era.",
        "audience":     ["Field Technician", "Engineer", "OFW-track Engineer"],
    },
    "Audit Log & Compliance": {
        "connects_to": ["Maintenance Logbook", "PM Checklist", "Inventory Management", "Hive Dashboard", "CMMS Integrations"],
        "tables":       ["cmms_audit_log", "hive_audit_log"],
        "edge_fns":     [],
        "loop_role":    "Trust layer. Every supervisor action and worker action recorded with timestamp + actor. Auditable for ISO/regulator review, transparent for the team, defensible if anything is ever questioned.",
        "audience":     ["Plant Manager", "Supervisor", "Compliance Officer"],
    },
}

# ── The WorkHive Loop (embedded in every script) ──────────────────────────────

WORKHIVE_LOOP = """
THE WORKHIVE LOOP — required structure in every video:

1. THE GAP
   Show the specific human moment when the pain hits.
   Not generic. Specific. "The bearing failed at 2am. Third time this month. Nobody knew why."

2. THE COST
   Make the cost concrete and relatable to a working plant.
   Production stopped. Client order delayed. Overtime pay. Management pressure. Safety near-miss.

3. THE FEATURE
   Show WorkHive solving it with the simplest possible action.
   One tap to log. One screen to see. One alert that saves the shift.

4. THE RIPPLE
   Name one connected feature that ALSO improves because of this one.
   "Because it is in the logbook, the AI can now predict the next one."
   "And the shift handover writes itself from that same record."
   This shows the platform is a system, not just a collection of tools.

5. THE PLATFORM PROMISE
   End every video with why this matters beyond one machine, one plant, one shift.
   "This is WorkHive. Free industrial intelligence for every worker."
   "Because your plant deserves the same tools the big ones have."
"""

# ── Supabase query helper ─────────────────────────────────────────────────────

def _sb_get(table: str, select: str = "*", params: dict = None, limit: int = 20):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    try:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        }
        p = {"select": select, "limit": limit, **(params or {})}
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=headers, params=p, timeout=4
        )
        if r.ok:
            return r.json() if isinstance(r.json(), list) else []
        return []
    except Exception:
        return []

# ── Live platform data ────────────────────────────────────────────────────────

def _top_failure_modes() -> list:
    rows = _sb_get("logbook", select="failure_mode", params={"failure_mode": "neq.null"}, limit=200)
    counts = {}
    for r in rows:
        fm = (r.get("failure_mode") or "").strip()
        if fm:
            counts[fm] = counts.get(fm, 0) + 1
    return [k for k, _ in sorted(counts.items(), key=lambda x: -x[1])[:5]]


def _overdue_pm_count() -> int:
    rows = _sb_get(
        "pm_assets",
        select="id",
        params={"next_due": f"lt.{datetime.utcnow().date()}", "is_active": "eq.true"},
        limit=500
    )
    return len(rows)


def _low_stock_count() -> int:
    rows = _sb_get(
        "inventory_items",
        select="id,qty_on_hand,reorder_point",
        params={"qty_on_hand": "lte.reorder_point"},
        limit=500
    )
    return len(rows)


def _recent_failure_alerts() -> list:
    rows = _sb_get(
        "failure_signature_alerts",
        select="machine_name,alert_type,severity",
        params={"order": "created_at.desc"},
        limit=5
    )
    return [
        f"{r.get('machine_name','Unknown')} — {r.get('alert_type','')}"
        for r in rows if r.get("machine_name")
    ]


def _latest_intel_stats() -> dict:
    rows = _sb_get(
        "ph_intelligence_reports",
        select="report_data",
        params={"order": "created_at.desc"},
        limit=1
    )
    if rows and rows[0].get("report_data"):
        return rows[0]["report_data"]
    return {}


# ── Coverage analysis ─────────────────────────────────────────────────────────

def compute_coverage(ideas: list) -> dict:
    """
    Returns per-feature coverage status based on the current backlog.
    Status: published > scripted > idea > uncovered
    """
    STATUS_RANK = {"published": 3, "produced": 2, "filming": 2, "scripted": 1, "idea": 0}
    coverage = {feat: {"status": "uncovered", "idea_ids": []} for feat in FEATURE_ECOSYSTEM}

    for idea in ideas:
        feat = idea.get("solution_feature", "")
        if feat in coverage:
            coverage[feat]["idea_ids"].append(idea["id"])
            current = STATUS_RANK.get(coverage[feat]["status"], -1)
            incoming = STATUS_RANK.get(idea.get("status", "idea"), 0)
            if incoming > current:
                coverage[feat]["status"] = idea.get("status", "idea")

    return coverage


def uncovered_features(ideas: list) -> list:
    cov = compute_coverage(ideas)
    return [feat for feat, data in cov.items() if data["status"] == "uncovered"]


# ── Build prompt context ──────────────────────────────────────────────────────

def build_prompt_context(ideas: list = None) -> str:
    """
    Assembles all platform intelligence into a single rich context block
    to be injected into idea generation and script generation prompts.
    """
    ideas = ideas or []

    # Live data (best-effort)
    failure_modes = _top_failure_modes()
    overdue_pms   = _overdue_pm_count()
    low_stock     = _low_stock_count()
    alerts        = _recent_failure_alerts()
    intel         = _latest_intel_stats()
    uncovered     = uncovered_features(ideas)

    # Feature ecosystem summary
    ecosystem_lines = []
    for feat, data in FEATURE_ECOSYSTEM.items():
        connects = ", ".join(data["connects_to"][:3])
        ecosystem_lines.append(f"  - {feat}: {data['loop_role']} Connects to: {connects}.")

    ecosystem_block = "\n".join(ecosystem_lines)

    # Live data block (only include if we have data)
    live_lines = []
    if failure_modes:
        live_lines.append(f"TOP FAILURE MODES IN PLATFORM DATA: {', '.join(failure_modes)}")
    if overdue_pms:
        live_lines.append(f"OVERDUE PM TASKS IN LIVE DATA: {overdue_pms} assets past due date")
    if low_stock:
        live_lines.append(f"INVENTORY ALERTS IN LIVE DATA: {low_stock} items below reorder point")
    if alerts:
        live_lines.append(f"RECENT FAILURE SIGNATURE ALERTS: {'; '.join(alerts)}")
    if intel:
        for k, v in list(intel.items())[:3]:
            live_lines.append(f"INDUSTRY INTELLIGENCE: {k}: {v}")

    live_block = (
        "\n\nLIVE PLATFORM DATA (use these real numbers to make ideas specific):\n"
        + "\n".join(live_lines)
        if live_lines else ""
    )

    # Coverage gap block — make this imperative, not a suggestion
    coverage_block = ""
    if uncovered:
        coverage_block = (
            f"\n\nFEATURE COVERAGE GAPS — {len(uncovered)} of {len(FEATURE_ECOSYSTEM)} features have ZERO videos.\n"
            "These features represent breakthrough capabilities the audience has never seen marketed:\n"
            + "\n".join(f"  - {f}" for f in uncovered)
            + "\n\nThe goal is balanced coverage of the entire ecosystem. "
              "Generating yet another idea about a well-covered feature wastes a slot."
        )

    return f"""
PLATFORM: WorkHive
TAGLINE: Free Industrial Intelligence Tools for every worker
COUNTRY: Philippines (market) — but ALL copy in plain simple English
AUDIENCE: Industrial workers — field technicians, supervisors, engineers, plant managers
INDUSTRIES: Manufacturing, power generation, oil & gas, utilities, facilities management

WORKHIVE FEATURE ECOSYSTEM (21 interconnected features):
{ecosystem_block}
{live_block}
{coverage_block}

{WORKHIVE_LOOP}

LANGUAGE RULES (NON-NEGOTIABLE):
- ALL hooks, narration, text overlays, and CTA copy must be in PLAIN SIMPLE ENGLISH.
- NO Tagalog. NO Taglish. NO Filipino slang. NO code-switching.
- Use short, common English words a non-native speaker can immediately understand.
- Avoid idioms, regional expressions, or culture-specific references.

VIDEO RULES:
- 1 video = 1 pain point + 1 emotional hook + 1 WorkHive feature
- Every video must complete the WorkHive Loop (all 5 steps)
- Every script must name at least 1 connected feature in the Ripple step
- Duration: 60-90s organic, 15-30s paid ad cut
- Tone: Real, relatable, not corporate. Like talking to a fellow worker on the shop floor.
- Hook: any plant worker must feel it in the first 3 seconds
"""


def get_feature_info(feature_name: str) -> dict:
    return FEATURE_ECOSYSTEM.get(feature_name, {})


def all_features() -> list:
    return list(FEATURE_ECOSYSTEM.keys())
