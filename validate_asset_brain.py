"""
Asset Brain Validator - WorkHive Platform
==========================================
Foundation-layer validator for the Asset Brain feature. Runs in three layers:

  Layer 1 - Schema migration completeness
    1.  asset_nodes table defined with required columns                   [FAIL]
    2.  asset_edges table defined with required columns                   [FAIL]
    3.  asset_embeddings table with vector(384) for nomic-embed-text-v1_5 [FAIL]
    4.  asset_brain_overview view defined                                 [FAIL]

  Layer 2 - Multi-tenant safety
    5.  RLS enabled on every new table                                    [FAIL]
    6.  GRANT statements present for anon and authenticated               [FAIL]
    7.  Hive-membership-join policy on every read policy                  [FAIL]

  Layer 3 - Realtime and audit plumbing
    8.  asset_nodes and asset_edges in supabase_realtime publication      [FAIL]
    9.  REPLICA IDENTITY FULL on asset_nodes for DELETE filter support    [FAIL]
   10.  sync_auth_uid_on_signup trigger updates asset_nodes               [FAIL]

Skills consulted before writing: architect, multitenant-engineer,
data-engineer, realtime-engineer, security, devops.

Usage:  python validate_asset_brain.py
Output: asset_brain_report.json
"""
import re
import json
import sys
import os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

MIGRATION_PATH = os.path.join(
    "supabase", "migrations", "20260508000009_asset_brain_foundation.sql"
)
BACKFILL_PATH = os.path.join(
    "supabase", "migrations", "20260508000010_asset_brain_backfill.sql"
)
EDGE_FN_PATH = os.path.join(
    "supabase", "functions", "asset-brain-query", "index.ts"
)
SHIFT_MIGRATION_PATH = os.path.join(
    "supabase", "migrations", "20260508000011_shift_brain_foundation.sql"
)
SHIFT_FN_PATH = os.path.join(
    "supabase", "functions", "shift-planner-orchestrator", "index.ts"
)
SHIFT_PAGE_PATH = "shift-brain.html"

CHECK_NAMES = [
    "asset_nodes_schema",
    "asset_edges_schema",
    "asset_embeddings_schema",
    "asset_brain_overview_view",
    "rls_enabled",
    "grants_present",
    "hive_membership_join_rls",
    "realtime_publication",
    "replica_identity_full",
    "auth_uid_sync_trigger",
    "backfill_idempotent",
    "backfill_hive_scoped",
    "backfill_dual_source",
    "backfill_criticality_mapping",
    "edge_fn_exists",
    "edge_fn_uses_callai",
    "edge_fn_rate_limit_gate",
    "edge_fn_hive_scoped",
    "edge_fn_question_capped",
    "shift_plans_schema",
    "shift_plans_rls_supervisor_publish",
    "shift_orchestrator_exists",
    "shift_orchestrator_parallel_subagents",
    "shift_brain_page_exists",
]

CHECK_LABELS = {
    "asset_nodes_schema":          "L1  asset_nodes table with required columns                       [FAIL]",
    "asset_edges_schema":          "L1  asset_edges table with required columns                       [FAIL]",
    "asset_embeddings_schema":     "L1  asset_embeddings has vector(384) matching nomic-embed-text-v1_5 [FAIL]",
    "asset_brain_overview_view":   "L1  asset_brain_overview view defined                              [FAIL]",
    "rls_enabled":                 "L2  RLS enabled on every new table                                [FAIL]",
    "grants_present":              "L2  GRANT to anon and authenticated on every new table            [FAIL]",
    "hive_membership_join_rls":    "L2  Hive membership join present in every read policy             [FAIL]",
    "realtime_publication":        "L3  asset_nodes and asset_edges added to supabase_realtime         [FAIL]",
    "replica_identity_full":       "L3  REPLICA IDENTITY FULL on asset_nodes and asset_edges           [FAIL]",
    "auth_uid_sync_trigger":       "L3  sync_auth_uid_on_signup updates asset_nodes                    [FAIL]",
    "backfill_idempotent":         "L4  Backfill uses ON CONFLICT (hive_id, tag) DO UPDATE            [FAIL]",
    "backfill_hive_scoped":        "L4  Backfill skips solo-mode rows (hive_id IS NOT NULL filter)    [FAIL]",
    "backfill_dual_source":        "L4  Backfill covers both pm_assets and legacy assets              [FAIL]",
    "backfill_criticality_mapping":"L4  Backfill maps criticality vocabulary across both sources       [FAIL]",
    "edge_fn_exists":              "L5  asset-brain-query edge function exists                          [FAIL]",
    "edge_fn_uses_callai":         "L5  Edge fn imports callAI and getCorsHeaders from _shared           [FAIL]",
    "edge_fn_rate_limit_gate":     "L5  Edge fn calls checkAIRateLimit before any model call             [FAIL]",
    "edge_fn_hive_scoped":         "L5  Every Supabase query in edge fn carries hive_id                  [FAIL]",
    "edge_fn_question_capped":     "L5  Question truncated to MAX_QUESTION_CHARS before AI call          [FAIL]",
    "shift_plans_schema":          "L6  shift_plans table with shift_window CHECK and unique key         [FAIL]",
    "shift_plans_rls_supervisor_publish": "L6  shift_plans write policy restricts to supervisor role     [FAIL]",
    "shift_orchestrator_exists":   "L6  shift-planner-orchestrator edge function exists                  [FAIL]",
    "shift_orchestrator_parallel_subagents": "L6  Orchestrator runs sub-agents via Promise.allSettled    [FAIL]",
    "shift_brain_page_exists":     "L6  shift-brain.html page exists and reads shift_plans               [FAIL]",
}


def _read_migration():
    text = read_file(MIGRATION_PATH)
    return text or ""


def _read_backfill():
    text = read_file(BACKFILL_PATH)
    return text or ""


def _read_edge_fn():
    text = read_file(EDGE_FN_PATH)
    return text or ""


def _read_shift_migration():
    return read_file(SHIFT_MIGRATION_PATH) or ""


def _read_shift_fn():
    return read_file(SHIFT_FN_PATH) or ""


def _read_shift_page():
    return read_file(SHIFT_PAGE_PATH) or ""


# Layer 1 - Schema completeness ---------------------------------------------

REQUIRED_NODE_COLS = {
    "id", "hive_id", "auth_uid", "parent_id", "level", "tag", "name",
    "iso_class", "criticality", "location", "external_ids",
    "legacy_asset_id", "pm_asset_id", "status",
    "submitted_by", "approved_by", "approved_at", "created_at", "updated_at",
}

REQUIRED_EDGE_COLS = {
    "id", "hive_id", "from_node_id", "to_node_id", "edge_type",
    "properties", "created_at",
}

REQUIRED_EMBED_COLS = {"node_id", "hive_id", "summary", "embedding", "refreshed_at"}


def _columns_in_create_table(text, table_name):
    pattern = re.compile(
        r"CREATE TABLE IF NOT EXISTS public\." + re.escape(table_name) +
        r"\s*\((.*?)\);", re.DOTALL | re.IGNORECASE,
    )
    m = pattern.search(text)
    if not m:
        return set()
    body = m.group(1)
    cols = set()
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("--") or line.upper().startswith("CONSTRAINT"):
            continue
        first = line.split()[0].strip("\",`")
        if first.upper() in {"CHECK", "UNIQUE", "FOREIGN", "PRIMARY"}:
            continue
        cols.add(first.lower())
    return cols


def check_asset_nodes_schema(text):
    cols = _columns_in_create_table(text, "asset_nodes")
    missing = REQUIRED_NODE_COLS - cols
    if missing:
        return [{
            "check": "asset_nodes_schema",
            "reason": (
                f"asset_nodes is missing required columns: "
                f"{sorted(missing)}. Asset Brain hub queries depend on these "
                f"to render the timeline, hierarchy, and approval state."
            ),
        }]
    return []


def check_asset_edges_schema(text):
    cols = _columns_in_create_table(text, "asset_edges")
    missing = REQUIRED_EDGE_COLS - cols
    if missing:
        return [{
            "check": "asset_edges_schema",
            "reason": f"asset_edges is missing required columns: {sorted(missing)}.",
        }]
    return []


def check_asset_embeddings_schema(text):
    cols = _columns_in_create_table(text, "asset_embeddings")
    missing = REQUIRED_EMBED_COLS - cols
    issues = []
    if missing:
        issues.append({
            "check": "asset_embeddings_schema",
            "reason": f"asset_embeddings is missing required columns: {sorted(missing)}.",
        })
    if "vector(384)" not in text:
        issues.append({
            "check": "asset_embeddings_schema",
            "reason": (
                "asset_embeddings.embedding must be vector(384) to match "
                "nomic-embed-text-v1_5 dimension declared in _shared/ai-chain.ts. "
                "A mismatched dimension throws a Postgres type error on insert."
            ),
        })
    return issues


def check_asset_brain_overview_view(text):
    pattern = re.compile(
        r"CREATE\s+OR\s+REPLACE\s+VIEW\s+public\.asset_brain_overview",
        re.IGNORECASE,
    )
    if not pattern.search(text):
        return [{
            "check": "asset_brain_overview_view",
            "reason": (
                "asset_brain_overview view is not defined. The asset hub renders "
                "from this view; without it the hub header has no aggregate counts."
            ),
        }]
    return []


# Layer 2 - Multi-tenant safety --------------------------------------------

def check_rls_enabled(text):
    issues = []
    for table in ("asset_nodes", "asset_edges", "asset_embeddings"):
        pat = re.compile(
            rf"ALTER TABLE\s+public\.{table}\s+ENABLE ROW LEVEL SECURITY",
            re.IGNORECASE,
        )
        if not pat.search(text):
            issues.append({
                "check": "rls_enabled",
                "reason": f"RLS not enabled on public.{table}. Anon access would be wide open.",
            })
    return issues


def check_grants_present(text):
    issues = []
    for table in ("asset_nodes", "asset_edges", "asset_embeddings"):
        pat = re.compile(
            rf"GRANT[^;]*ON\s+public\.{table}[^;]*TO[^;]*authenticated",
            re.IGNORECASE | re.DOTALL,
        )
        if not pat.search(text):
            issues.append({
                "check": "grants_present",
                "reason": (
                    f"GRANT to anon, authenticated missing on public.{table}. "
                    f"Without GRANT, every query returns 401 even when RLS would allow it."
                ),
            })
    return issues


def check_hive_membership_join_rls(text):
    issues = []
    read_policies = re.findall(
        r"CREATE POLICY\s+(\w+_read)\s+ON\s+public\.(\w+)[^;]+?USING\s*\((.*?)\);",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if not read_policies:
        issues.append({
            "check": "hive_membership_join_rls",
            "reason": "No SELECT policies found. Read access has no enforcement.",
        })
    for policy_name, table, body in read_policies:
        if "hive_members" not in body or "auth.uid()" not in body:
            issues.append({
                "check": "hive_membership_join_rls",
                "reason": (
                    f"Policy {policy_name} on {table} does not join hive_members "
                    f"or check auth.uid(). Use the canonical multitenant pattern."
                ),
            })
    return issues


# Layer 3 - Realtime and trigger plumbing ----------------------------------

def check_realtime_publication(text):
    issues = []
    for table in ("asset_nodes", "asset_edges"):
        pat = re.compile(
            rf"ALTER PUBLICATION supabase_realtime ADD TABLE public\.{table}",
            re.IGNORECASE,
        )
        if not pat.search(text):
            issues.append({
                "check": "realtime_publication",
                "reason": (
                    f"public.{table} is not added to supabase_realtime. "
                    f"Subscribers compile but receive zero events. "
                    f"Found by community-page realtime postmortem (May 2026)."
                ),
            })
    return issues


def check_replica_identity_full(text):
    issues = []
    for table in ("asset_nodes", "asset_edges"):
        pat = re.compile(
            rf"ALTER TABLE\s+public\.{table}\s+REPLICA IDENTITY FULL",
            re.IGNORECASE,
        )
        if not pat.search(text):
            issues.append({
                "check": "replica_identity_full",
                "reason": (
                    f"REPLICA IDENTITY FULL not set on public.{table}. "
                    f"DELETE realtime filters on hive_id will silently drop every event."
                ),
            })
    return issues


def check_auth_uid_sync_trigger(text):
    pat = re.compile(
        r"sync_auth_uid_on_signup[\s\S]+?asset_nodes\s+SET\s+auth_uid",
        re.IGNORECASE,
    )
    if not pat.search(text):
        return [{
            "check": "auth_uid_sync_trigger",
            "reason": (
                "sync_auth_uid_on_signup does not update public.asset_nodes. "
                "Pre-existing asset_nodes rows submitted before a worker signs up "
                "will stay invisible after C4-style RLS enforcement."
            ),
        }]
    return []


# Layer 4 - Backfill correctness -------------------------------------------

def check_backfill_idempotent(text):
    if not text:
        return [{
            "check": "backfill_idempotent",
            "reason": (
                f"{BACKFILL_PATH} missing. Phase 1 (backfill from pm_assets and "
                f"legacy assets) cannot be verified."
            ),
        }]
    pat = re.compile(r"ON CONFLICT\s*\(\s*hive_id\s*,\s*tag\s*\)\s*DO UPDATE", re.IGNORECASE)
    matches = pat.findall(text)
    if len(matches) < 2:
        return [{
            "check": "backfill_idempotent",
            "reason": (
                "Backfill must use ON CONFLICT (hive_id, tag) DO UPDATE on both "
                "the pm_assets and legacy assets inserts. Idempotency lets the "
                "migration re-run safely after partial failures."
            ),
        }]
    return []


def check_backfill_hive_scoped(text):
    if not text:
        return [{"check": "backfill_hive_scoped", "reason": f"{BACKFILL_PATH} missing."}]
    pm_scoped = re.search(r"FROM public\.pm_assets[\s\S]+?hive_id IS NOT NULL", text, re.IGNORECASE)
    legacy_scoped = re.search(r"FROM public\.assets[\s\S]+?hive_id IS NOT NULL", text, re.IGNORECASE)
    issues = []
    if not pm_scoped:
        issues.append({
            "check": "backfill_hive_scoped",
            "reason": (
                "pm_assets backfill is missing 'hive_id IS NOT NULL' filter. "
                "Solo-mode rows would violate the asset_nodes.hive_id NOT NULL constraint."
            ),
        })
    if not legacy_scoped:
        issues.append({
            "check": "backfill_hive_scoped",
            "reason": (
                "Legacy assets backfill is missing 'hive_id IS NOT NULL' filter. "
                "Solo-mode rows would violate the asset_nodes.hive_id NOT NULL constraint."
            ),
        })
    return issues


def check_backfill_dual_source(text):
    if not text:
        return [{"check": "backfill_dual_source", "reason": f"{BACKFILL_PATH} missing."}]
    has_pm = re.search(r"INSERT INTO public\.asset_nodes[\s\S]+?FROM public\.pm_assets", text, re.IGNORECASE)
    has_legacy = re.search(r"INSERT INTO public\.asset_nodes[\s\S]+?FROM public\.assets\b", text, re.IGNORECASE)
    issues = []
    if not has_pm:
        issues.append({
            "check": "backfill_dual_source",
            "reason": "Backfill missing INSERT FROM public.pm_assets. Skill-matrix-tied PM equipment will have no graph node.",
        })
    if not has_legacy:
        issues.append({
            "check": "backfill_dual_source",
            "reason": "Backfill missing INSERT FROM public.assets. Inventory-linked legacy assets will have no graph node.",
        })
    return issues


def check_backfill_criticality_mapping(text):
    if not text:
        return [{"check": "backfill_criticality_mapping", "reason": f"{BACKFILL_PATH} missing."}]
    required_tokens = ["'critical'", "'high'", "'medium'", "'low'", "%major%", "%minor%"]
    missing = [t for t in required_tokens if t not in text.lower() and t not in text]
    if missing:
        return [{
            "check": "backfill_criticality_mapping",
            "reason": (
                f"Criticality mapping is incomplete. Missing tokens: {missing}. "
                f"Both pm_assets vocabulary (Critical/Major/Minor) and legacy assets "
                f"free-text criticality must map to asset_nodes.criticality "
                f"(low/medium/high/critical) in the backfill CASE expression."
            ),
        }]
    return []


# Layer 5 - Edge function (asset-brain-query) -------------------------------

def check_edge_fn_exists(text):
    if not text:
        return [{
            "check": "edge_fn_exists",
            "reason": (
                f"{EDGE_FN_PATH} missing. Phase 3 (asset-brain-query GraphRAG "
                f"edge function) cannot be verified."
            ),
        }]
    return []


def check_edge_fn_uses_callai(text):
    if not text:
        return [{"check": "edge_fn_uses_callai", "reason": f"{EDGE_FN_PATH} missing."}]
    issues = []
    if 'callAI' not in text or '_shared/ai-chain' not in text:
        issues.append({
            "check": "edge_fn_uses_callai",
            "reason": (
                "Edge function must import callAI from ../_shared/ai-chain.ts. "
                "Direct fetch() to a model provider bypasses the multi-provider "
                "fallback chain and the banned-models guard."
            ),
        })
    if 'getCorsHeaders' not in text or '_shared/cors' not in text:
        issues.append({
            "check": "edge_fn_uses_callai",
            "reason": (
                "Edge function must import getCorsHeaders from ../_shared/cors.ts. "
                "Static CORS origins break local file:// testing and trip "
                "validate_integration_security.cors_dynamic_pattern."
            ),
        })
    return issues


def check_edge_fn_rate_limit_gate(text):
    if not text:
        return [{"check": "edge_fn_rate_limit_gate", "reason": f"{EDGE_FN_PATH} missing."}]
    # 2026-07-17 (FULLSTACK_COMPONENT_LIBRARY Layer A): the fn's local checkAIRateLimit copy
    # was DELEGATED to the canonical _shared/rate-limit.ts (which owns the ai_rate_limits SQL
    # and adds the daily ceiling). The canonical-import form satisfies this gate — the literal
    # table name now lives in the shared module, not the fn.
    delegated = "checkAIRateLimit" in text and "_shared/rate-limit.ts" in text
    if 'checkAIRateLimit' not in text or ('ai_rate_limits' not in text and not delegated):
        return [{
            "check": "edge_fn_rate_limit_gate",
            "reason": (
                "Edge function must call checkAIRateLimit against ai_rate_limits "
                "before any model call. Bots can otherwise drain the AI budget "
                "in minutes (ai-engineer skill)."
            ),
        }]
    # Must run before the callAI line
    rl_idx = text.find('checkAIRateLimit')
    ai_idx = text.find('callAI(')
    if rl_idx < 0 or ai_idx < 0 or rl_idx > ai_idx:
        return [{
            "check": "edge_fn_rate_limit_gate",
            "reason": (
                "checkAIRateLimit must be invoked BEFORE callAI(). A rejected "
                "request must cost zero model tokens."
            ),
        }]
    return []


def check_edge_fn_hive_scoped(text):
    if not text:
        return [{"check": "edge_fn_hive_scoped", "reason": f"{EDGE_FN_PATH} missing."}]
    # Every db.from(...) call (excluding ai_rate_limits which uses hive_id PK lookup)
    # must be followed within the same statement by .eq("hive_id", ...).
    issues = []
    # Crude scan: look for db.from("X") chains that don't include hive_id within the next 200 chars
    pattern = re.compile(r'db\.from\(["\'](\w+)["\']\)', re.IGNORECASE)
    for m in pattern.finditer(text):
        table = m.group(1)
        # Tables that are intentionally not hive-scoped or use .eq("hive_id") directly
        # ai_rate_limits is keyed by hive_id but uses .eq directly so it passes the check below
        window = text[m.start(): m.start() + 400]
        if '.eq("hive_id"' not in window and ".eq('hive_id'" not in window:
            issues.append({
                "check": "edge_fn_hive_scoped",
                "reason": (
                    f"db.from('{table}') call near offset {m.start()} does not "
                    f".eq('hive_id', ...) within the same chain. Cross-hive data "
                    f"could leak through the edge function. Add an explicit hive_id "
                    f"filter."
                ),
            })
    return issues


def check_edge_fn_question_capped(text):
    if not text:
        return [{"check": "edge_fn_question_capped", "reason": f"{EDGE_FN_PATH} missing."}]
    if 'MAX_QUESTION_CHARS' not in text or '.slice(0, MAX_QUESTION_CHARS' not in text:
        return [{
            "check": "edge_fn_question_capped",
            "reason": (
                "Edge function must truncate the user question to MAX_QUESTION_CHARS "
                "before passing to callAI(). Long transcripts can carry prompt-injection "
                "or burn TPM budget (ai-engineer skill)."
            ),
        }]
    return []


# Layer 6 - Shift Brain (Phase 4) ------------------------------------------

def check_shift_plans_schema(text):
    if not text:
        return [{"check": "shift_plans_schema", "reason": f"{SHIFT_MIGRATION_PATH} missing."}]
    issues = []
    if "CREATE TABLE IF NOT EXISTS public.shift_plans" not in text:
        issues.append({"check": "shift_plans_schema", "reason": "shift_plans table not declared in migration."})
    if "shift_window" not in text or "CHECK (shift_window IN" not in text:
        issues.append({
            "check": "shift_plans_schema",
            "reason": "shift_plans must constrain shift_window to ('06-14','14-22','22-06')."
        })
    if "UNIQUE (hive_id, shift_date, shift_window)" not in text:
        issues.append({
            "check": "shift_plans_schema",
            "reason": "shift_plans needs UNIQUE (hive_id, shift_date, shift_window) so the orchestrator can upsert idempotently per shift."
        })
    return issues


def check_shift_plans_rls_supervisor_publish(text):
    if not text:
        return [{"check": "shift_plans_rls_supervisor_publish", "reason": f"{SHIFT_MIGRATION_PATH} missing."}]
    if "shift_plans_supervisor_write" not in text or "role = 'supervisor'" not in text:
        return [{
            "check": "shift_plans_rls_supervisor_publish",
            "reason": (
                "shift_plans needs a write policy that restricts INSERT/UPDATE/DELETE "
                "to hive supervisors. Workers must be read-only. Without this, any "
                "worker can publish a plan to the whole crew."
            ),
        }]
    return []


def check_shift_orchestrator_exists(text):
    if not text:
        return [{
            "check": "shift_orchestrator_exists",
            "reason": f"{SHIFT_FN_PATH} missing. Phase 4 (Shift Brain orchestrator) cannot be verified.",
        }]
    if "callAI" not in text or "_shared/ai-chain" not in text:
        return [{
            "check": "shift_orchestrator_exists",
            "reason": "Orchestrator must import callAI from ../_shared/ai-chain.ts for the briefing synthesis lane.",
        }]
    return []


def check_shift_orchestrator_parallel_subagents(text):
    if not text:
        return [{"check": "shift_orchestrator_parallel_subagents", "reason": f"{SHIFT_FN_PATH} missing."}]
    if "Promise.allSettled" not in text:
        return [{
            "check": "shift_orchestrator_parallel_subagents",
            "reason": (
                "Sub-agents must run via Promise.allSettled so one failure does not block the rest "
                "(ai-engineer skill). Found Promise.all or sequential awaits instead."
            ),
        }]
    return []


def check_shift_brain_page_exists(text):
    if not text:
        return [{
            "check": "shift_brain_page_exists",
            "reason": f"{SHIFT_PAGE_PATH} missing. The page is the supervisor-facing surface for the shift plan.",
        }]
    issues = []
    if "shift_plans" not in text:
        issues.append({
            "check": "shift_brain_page_exists",
            "reason": "shift-brain.html must read from the shift_plans table.",
        })
    if "shift-planner-orchestrator" not in text:
        issues.append({
            "check": "shift_brain_page_exists",
            "reason": "shift-brain.html should call shift-planner-orchestrator for the manual rerun path.",
        })
    return issues


# Runner -------------------------------------------------------------------

def main():
    def bold(s):
        return f"\033[1m{s}\033[0m"

    print(bold("\nAsset Brain Validator"))
    print("=" * 40)

    text = _read_migration()
    if not text:
        print(f"\033[91m  Migration file not found: {MIGRATION_PATH}\033[0m")
        report = {
            "validator": "asset_brain",
            "total_checks": len(CHECK_NAMES),
            "passed": 0,
            "warned": 0,
            "failed": len(CHECK_NAMES),
            "issues": [{
                "check": name,
                "reason": f"{MIGRATION_PATH} missing - cannot validate",
            } for name in CHECK_NAMES],
            "warnings": [],
        }
        with open("asset_brain_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        sys.exit(1)

    backfill_text  = _read_backfill()
    edge_text      = _read_edge_fn()
    shift_mig_text = _read_shift_migration()
    shift_fn_text  = _read_shift_fn()
    shift_page_text = _read_shift_page()

    all_issues = []
    all_issues += check_asset_nodes_schema(text)
    all_issues += check_asset_edges_schema(text)
    all_issues += check_asset_embeddings_schema(text)
    all_issues += check_asset_brain_overview_view(text)
    all_issues += check_rls_enabled(text)
    all_issues += check_grants_present(text)
    all_issues += check_hive_membership_join_rls(text)
    all_issues += check_realtime_publication(text)
    all_issues += check_replica_identity_full(text)
    all_issues += check_auth_uid_sync_trigger(text)
    all_issues += check_backfill_idempotent(backfill_text)
    all_issues += check_backfill_hive_scoped(backfill_text)
    all_issues += check_backfill_dual_source(backfill_text)
    all_issues += check_backfill_criticality_mapping(backfill_text)
    all_issues += check_edge_fn_exists(edge_text)
    all_issues += check_edge_fn_uses_callai(edge_text)
    all_issues += check_edge_fn_rate_limit_gate(edge_text)
    all_issues += check_edge_fn_hive_scoped(edge_text)
    all_issues += check_edge_fn_question_capped(edge_text)
    all_issues += check_shift_plans_schema(shift_mig_text)
    all_issues += check_shift_plans_rls_supervisor_publish(shift_mig_text)
    all_issues += check_shift_orchestrator_exists(shift_fn_text)
    all_issues += check_shift_orchestrator_parallel_subagents(shift_fn_text)
    all_issues += check_shift_brain_page_exists(shift_page_text)

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "asset_brain",
        "total_checks": total,
        "passed":       n_pass,
        "warned":       n_warn,
        "failed":       n_fail,
        "issues":       [i for i in all_issues if not i.get("skip")],
        "warnings":     [i for i in all_issues if i.get("skip")],
    }
    with open("asset_brain_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
