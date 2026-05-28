"""
add_validator_skill_tags.py — one-shot migration tool.
====================================================
Walks run_platform_checks.py's VALIDATORS list and adds a `"skill"` field
to every entry that doesn't already have one. The skill is inferred from
the validator's id/label using heuristic matching against the project's
skill roster (frontend, architect, security, data-engineer, etc.).

Closes Layer 0 #3.4 ("Per-skill validator tagging").

Default skill = "architect" (catch-all). Future passes can refine via
manual edit.

Idempotent.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "run_platform_checks.py"

# Heuristic id-substring → skill mapping. Ordered: most-specific first.
SKILL_HINTS = [
    # Security / auth / RLS
    ("xss",                  "security"),
    ("auth_",                "security"),
    ("rls",                  "multitenant-engineer"),
    ("tenant",               "multitenant-engineer"),
    ("hive",                 "multitenant-engineer"),
    ("hardcoded_secret",     "security"),
    ("cors",                 "security"),
    ("service_role",         "security"),
    ("pii_",                 "security"),
    ("security_definer",     "security"),
    ("password",             "security"),

    # AI / LLM / agentic
    ("ai_companion",         "ai-engineer"),
    ("ai_chain",             "ai-engineer"),
    ("agentic_rag",          "ai-engineer"),
    ("agent_memory",         "ai-engineer"),
    ("ai_gateway",           "ai-engineer"),
    ("voice_",               "ai-engineer"),
    ("llm_",                 "ai-engineer"),
    ("groq_",                "ai-engineer"),
    ("model_router",         "ai-engineer"),
    ("hierarchical_",        "ai-engineer"),
    ("temporal_orchest",     "ai-engineer"),
    ("rag_",                 "ai-engineer"),
    ("ai_eval",              "ai-engineer"),
    ("ai_cost",              "ai-engineer"),
    ("ai_safety",            "ai-engineer"),
    ("dialog_",              "ai-engineer"),
    ("rate_limit",           "ai-engineer"),
    ("multilingual",         "ai-engineer"),
    ("tts_",                 "ai-engineer"),

    # Data engineer / schema / DB
    ("migration_",           "data-engineer"),
    ("schema",               "data-engineer"),
    ("table_collision",      "data-engineer"),
    ("trigger",              "data-engineer"),
    ("fk_on_delete",         "data-engineer"),
    ("truth_view",           "data-engineer"),
    ("phantom_column",       "data-engineer"),
    ("realtime",             "realtime-engineer"),
    ("canonical",            "data-engineer"),
    ("jsonb_",               "data-engineer"),
    ("index_",               "data-engineer"),
    ("query_column",         "data-engineer"),
    ("rpc_",                 "data-engineer"),
    ("view_select",          "data-engineer"),
    ("drop_if_exists",       "data-engineer"),
    ("add_column_default",   "data-engineer"),
    ("vector_",              "data-engineer"),
    ("pgvector",             "data-engineer"),
    ("date_arithmetic",      "data-engineer"),
    ("filter_case",          "data-engineer"),
    ("like_escape",          "data-engineer"),
    ("unbounded_query",      "data-engineer"),
    ("optimistic",           "data-engineer"),
    ("soft_delete",          "data-engineer"),
    ("cascade",              "data-engineer"),

    # Analytics
    ("analytics",            "analytics-engineer"),
    ("kpi_",                 "analytics-engineer"),
    ("benchmark",            "analytics-engineer"),
    ("predictive",           "predictive-analytics"),
    ("weibull",              "predictive-analytics"),
    ("pattern_alerts",       "predictive-analytics"),

    # Frontend / UI
    ("html_",                "frontend"),
    ("innerhtml",            "frontend"),
    ("eschtml",              "frontend"),
    ("css_",                 "frontend"),
    ("dom_",                 "frontend"),
    ("duplicate_html",       "frontend"),
    ("duplicate_script",     "frontend"),
    ("img_alt",              "frontend"),
    ("aria_label",           "frontend"),
    ("heading_hierarchy",    "frontend"),
    ("table_accessible",     "frontend"),
    ("native_dialog",        "frontend"),
    ("tabindex",             "frontend"),
    ("javascript_href",      "frontend"),
    ("inline_onclick",       "frontend"),
    ("loads_utils_js",       "frontend"),
    ("renderer",             "frontend"),
    ("nav_registry",         "frontend"),
    ("link_target",          "frontend"),
    ("button_type",          "frontend"),
    ("form_submission",      "frontend"),
    ("input_guards",         "frontend"),
    ("icon_button_label",    "frontend"),
    ("loading_state",        "frontend"),
    ("ux_contract",          "designer"),
    ("partial_label",        "frontend"),
    ("displayed_values",     "frontend"),
    ("render_budget",        "performance"),
    ("performance",          "performance"),
    ("bundle_bloat",         "performance"),
    ("cold_start",           "performance"),

    # Mobile / PWA
    ("pwa",                  "mobile-maestro"),
    ("service_worker",       "mobile-maestro"),
    ("mobile",               "mobile-maestro"),
    ("viewport_user",        "mobile-maestro"),
    ("sw_offline",           "mobile-maestro"),
    ("offline_resilience",   "mobile-maestro"),

    # Edge fn / API contracts
    ("edge_",                "architect"),
    ("envelope",             "architect"),
    ("health_endpoint",      "architect"),
    ("trace_id",             "architect"),
    ("idempotency",          "architect"),
    ("agent_handoff",        "architect"),
    ("structured_log",       "devops"),

    # DevOps / hosting
    ("pre_deploy",           "devops"),
    ("reproducible_build",   "devops"),
    ("env_",                 "devops"),
    ("cron",                 "devops"),
    ("readiness",            "devops"),
    ("cache_name",           "devops"),
    ("validator_self_cover", "devops"),
    ("validator_cp1252",     "devops"),

    # QA / testing
    ("playwright",           "qa-tester"),
    ("test_page",            "qa-tester"),
    ("tester_coverage",      "qa-tester"),

    # Domain
    ("logbook",              "maintenance-expert"),
    ("inventory",            "inventory-validator"),
    ("pm_",                  "pm-validator"),
    ("dayplanner",           "maintenance-expert"),
    ("skillmatrix",          "skillmatrix-validator"),
    ("standards",            "standards-validator"),
    ("drawing",              "drawing-standards"),
    ("engineering",          "engineering-calc-validator"),
    ("calc_",                "engineering-calc-validator"),
    ("formula",              "engineering-calc-validator"),
    ("assistant",            "assistant-validator"),
    ("hive_validator",       "hive-validator"),
    ("achievements",         "community"),
    ("community",            "community"),
    ("marketplace",          "marketplace"),
    ("notebooklm",           "knowledge-manager"),
    ("knowledge",            "knowledge-manager"),
    ("plant_connections",    "integration-engineer"),
    ("integrations",         "integration-engineer"),
    ("cmms",                 "integration-engineer"),
    ("iot",                  "integration-engineer"),
    ("sensor",               "integration-engineer"),

    # SEO / content
    ("seo",                  "seo-content"),
    ("llms_sync",            "seo-content"),
    ("sitemap",              "seo-content"),
    ("meta_description",     "seo-content"),

    # Compliance
    ("audit_log",            "enterprise-compliance"),
    ("audit_trail",          "enterprise-compliance"),
    ("compliance",           "enterprise-compliance"),
    ("data_retention",       "enterprise-compliance"),
    ("data_governance",      "enterprise-compliance"),
    ("data_quality",         "enterprise-compliance"),
    ("sso",                  "enterprise-compliance"),
    ("enterprise",           "enterprise-compliance"),

    # Substrate / platform
    ("substrate",            "architect"),
    ("fullstack_gate",       "architect"),
    ("sentinel",             "qa-tester"),
    ("auto_discovery",       "architect"),
    ("capability_dedup",     "architect"),
    ("tier_",                "architect"),
    ("seed_consumer",        "architect"),
]

ID_RE = re.compile(r'"id":\s*"([a-z0-9_\-]+)"')


def skill_for(vid: str) -> str:
    v = vid.lower()
    for h, s in SKILL_HINTS:
        if h in v: return s
    return "architect"  # catch-all


def find_enclosing_dict(text: str, pos: int) -> tuple[int, int] | None:
    depth = 0
    i = pos
    while i >= 0:
        c = text[i]
        if c == "}": depth += 1
        elif c == "{":
            if depth == 0:
                start = i; break
            depth -= 1
        i -= 1
    else:
        return None
    depth = 0
    j = start
    while j < len(text):
        c = text[j]
        if c == "{": depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return (start, j + 1)
        j += 1
    return None


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    # Locate the VALIDATORS = [ ... ] block boundaries explicitly. Everything
    # we want to tag lives strictly inside this block.
    v_start_m = re.search(r"^VALIDATORS\s*=\s*\[", text, re.MULTILINE)
    if not v_start_m:
        print("No VALIDATORS list found.")
        return 0
    v_start = v_start_m.end()
    # Walk to the matching closing bracket of the top-level list.
    depth = 1
    i = v_start
    while i < len(text) and depth > 0:
        c = text[i]
        if c == "[": depth += 1
        elif c == "]": depth -= 1
        i += 1
    v_end = i  # one past the closing ]
    block_text = text[v_start:v_end]

    # Now run ID_RE only within block_text, with offsets translated.
    positions: list[tuple[int, str]] = [(m.start() + v_start, m.group(1)) for m in ID_RE.finditer(block_text)]
    n_added, n_skipped = 0, 0
    out = text
    for pos, vid in reversed(positions):
        bounds = find_enclosing_dict(out, pos)
        if not bounds: continue
        start, end = bounds
        block = out[start:end]
        if '"skill"' in block:
            n_skipped += 1
            continue
        sk = skill_for(vid)
        id_line_start = out.rfind("\n", 0, pos) + 1
        indent = out[id_line_start:pos]
        injection = f'{indent}"skill": "{sk}",\n'
        close_pos = end - 1
        insert_pos = close_pos
        while insert_pos > start and out[insert_pos - 1] in " \t":
            insert_pos -= 1
        if insert_pos > 0 and out[insert_pos - 1] != "\n":
            injection = "\n" + injection
        out = out[:insert_pos] + injection + out[insert_pos:]
        n_added += 1

    if out == text:
        print(f"No changes. {n_skipped} already had skill.")
        return 0
    TARGET.write_text(out, encoding="utf-8")
    print(f"Added skill tag to {n_added} validator(s). {n_skipped} already had one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
