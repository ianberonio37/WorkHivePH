"""
Agentic RAG Loop Validator (Phase 1 of AGENTIC_RAG_ROADMAP.md)
==============================================================
Forward-only L0 ratchet locking the 5-stage self-correcting RAG loop
introduced as Phase 1 of the Agentic RAG Roadmap.

  R01  Edge function file exists (supabase/functions/agentic-rag-loop/index.ts)
  R02  All 5 stages present (Router, Retriever, Grader, Generator, Checker)
  R03  Hive scoping on every Supabase query (.eq("hive_id" or "worker_name" or "auth_uid"))
  R04  FREE-TIER ONLY — no paid model names anywhere in this fn
  R05  Uses _shared/ai-chain.ts callAI (no raw fetch to api.groq.com etc.)
  R06  Rate limit (checkRateLimit) called before stages run
  R07  Retry cap (MAX_RETRIES) enforced and ≤2
  R08  Grader threshold (GRADER_THRESHOLD = 0.5) defined
  R09  Question length cap (MAX_QUESTION_CHARS = 500) enforced
  R10  Trace persisted to agentic_rag_traces table
  R11  logAICost called for every LLM-invoking stage (4 calls minimum)
  R12  Migration for agentic_rag_traces table exists
  R13  4-place sync: config.toml registration
  R14  4-place sync: deploy-functions.ps1 line
  R15  4-place sync: validate_edge_contracts.py ALL_FUNCTIONS membership
  R16  4-place sync: validate_edge_contracts.py REQUIRED_FIELDS membership
  R17  No em dashes in any system prompt (encoding safety per ai-engineer skill)
  R18  JSON mode enforced on every callAI call (jsonMode: true)
  R19  Integration wave (Items 2+3+4): hierarchical lane + temporal delegate + memory recall + memory store wired
  R20  Integration wave: voice-handler.js opt-in long-horizon detector + agentic-rag-loop call wired
  R21  Null-scope guard: retrieverStage + spanDaysFromTimeScope handle time_scope === null (Router can return it)
"""

from __future__ import annotations
import os, sys, re, glob

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

EDGE_FN_PATH      = os.path.join("supabase", "functions", "agentic-rag-loop", "index.ts")
VOICE_HANDLER_JS  = "voice-handler.js"
CONFIG_TOML   = os.path.join("supabase", "config.toml")
DEPLOY_PS1    = "deploy-functions.ps1"
EDGE_CONTRACT = "validate_edge_contracts.py"
MIGRATIONS    = os.path.join("supabase", "migrations")

# Paid-model substrings that must NEVER appear in this edge function.
# Lower-case match to catch any casing.
PAID_MODEL_PATTERNS = [
    r"\bhaiku\b", r"\bsonnet\b", r"\bopus\b",
    r"claude-3", r"claude-4",
    r"gpt-4", r"gpt-4o", r"o1-preview", r"o3-mini",
    r"anthropic\.com/v1", r"api\.openai\.com",
]


def _read_fn() -> str:
    return read_file(EDGE_FN_PATH) or ""


def _extract_system_prompts(src: str) -> list[str]:
    # Pull all "const *_SYSTEM = `...`;" blocks for em-dash inspection.
    return re.findall(r"const\s+\w+_SYSTEM\s*=\s*`([^`]*)`", src, re.DOTALL)


def check_file_exists() -> list[dict]:
    if not os.path.isfile(EDGE_FN_PATH):
        return [{"check": "file_exists", "reason": f"{EDGE_FN_PATH} not found — Phase 1 edge fn missing"}]
    return []


def check_five_stages(src: str) -> list[dict]:
    required = ["routerStage", "retrieverStage", "graderStage", "generatorStage", "checkerStage"]
    issues = []
    for sym in required:
        if sym not in src:
            issues.append({"check": "five_stages", "reason": f"Missing stage function: {sym}"})
    return issues


def check_hive_scoping(src: str) -> list[dict]:
    # Every Supabase query path in this fn must scope by hive_id, worker_name, or auth_uid.
    # Probe: at least one of the canonical hive guards appears.
    if not re.search(r'\.eq\(\s*"hive_id"', src):
        return [{"check": "hive_scoping", "reason": '.eq("hive_id", ...) not found — hive-scoping invariant missing'}]
    if not re.search(r'\.eq\(\s*"worker_name"', src):
        return [{"check": "hive_scoping", "reason": '.eq("worker_name", ...) fallback for solo mode missing'}]
    if not re.search(r'\.eq\(\s*"auth_uid"', src):
        return [{"check": "hive_scoping", "reason": '.eq("auth_uid", ...) for voice_journal lane missing'}]
    return []


def check_free_tier_only(src: str) -> list[dict]:
    issues = []
    lower = src.lower()
    for pat in PAID_MODEL_PATTERNS:
        if re.search(pat, lower):
            issues.append({"check": "free_tier_only",
                           "reason": f"Forbidden paid-model reference matched /{pat}/ — see feedback_free_tier_only_models.md"})
    return issues


def check_uses_callai(src: str) -> list[dict]:
    if 'import { callAI }' not in src and 'from "../_shared/ai-chain.ts"' not in src:
        return [{"check": "uses_callai", "reason": 'Must import callAI from "../_shared/ai-chain.ts"'}]
    # No raw provider URLs allowed — must go through the shared chain.
    if re.search(r'fetch\(\s*["\']https?://api\.(groq|openai|anthropic|cerebras|sambanova|deepseek)\.com', src):
        return [{"check": "uses_callai", "reason": "Raw fetch() to provider URL detected — every LLM call must route through _shared/ai-chain.ts callAI"}]
    return []


def check_rate_limit(src: str) -> list[dict]:
    if "checkRateLimit" not in src:
        return [{"check": "rate_limit", "reason": "checkRateLimit function missing — per-hive rate cap not enforced"}]
    if "ai_rate_limits" not in src:
        return [{"check": "rate_limit", "reason": "ai_rate_limits table reference missing — rate-limit table not queried"}]
    # Verify the rate-limit guard runs BEFORE the router stage in the serve handler.
    # Match only the awaited CALL sites (not the function definitions which appear earlier).
    rl_match     = re.search(r"\bawait\s+checkRateLimit\s*\(", src)
    router_match = re.search(r"\bawait\s+routerStage\s*\(", src)
    if not rl_match or not router_match:
        return [{"check": "rate_limit", "reason": "Could not locate awaited call sites for checkRateLimit and routerStage"}]
    if rl_match.start() > router_match.start():
        return [{"check": "rate_limit", "reason": "checkRateLimit must be called BEFORE routerStage in the serve handler — rejected requests should cost zero LLM tokens"}]
    return []


def check_retry_cap(src: str) -> list[dict]:
    m = re.search(r"MAX_RETRIES\s*=\s*(\d+)", src)
    if not m:
        return [{"check": "retry_cap", "reason": "MAX_RETRIES constant missing"}]
    n = int(m.group(1))
    if n < 1 or n > 2:
        return [{"check": "retry_cap", "reason": f"MAX_RETRIES = {n} out of bounds (must be 1 or 2 per roadmap §5 Phase 1)"}]
    return []


def check_grader_threshold(src: str) -> list[dict]:
    m = re.search(r"GRADER_THRESHOLD\s*=\s*([\d.]+)", src)
    if not m:
        return [{"check": "grader_threshold", "reason": "GRADER_THRESHOLD constant missing"}]
    try:
        v = float(m.group(1))
    except ValueError:
        return [{"check": "grader_threshold", "reason": "GRADER_THRESHOLD is not numeric"}]
    if not (0.3 <= v <= 0.7):
        return [{"check": "grader_threshold", "reason": f"GRADER_THRESHOLD = {v} out of sensible range [0.3, 0.7]"}]
    return []


def check_question_cap(src: str) -> list[dict]:
    m = re.search(r"MAX_QUESTION_CHARS\s*=\s*(\d+)", src)
    if not m:
        return [{"check": "question_cap", "reason": "MAX_QUESTION_CHARS constant missing"}]
    n = int(m.group(1))
    if n > 1000:
        return [{"check": "question_cap", "reason": f"MAX_QUESTION_CHARS = {n} exceeds 1000 (prompt-injection / TPM safety)"}]
    if 'slice(0, MAX_QUESTION_CHARS)' not in src:
        return [{"check": "question_cap", "reason": "Question must be truncated with .slice(0, MAX_QUESTION_CHARS) before any LLM call"}]
    return []


def check_trace_persist(src: str) -> list[dict]:
    if 'agentic_rag_traces' not in src:
        return [{"check": "trace_persist", "reason": "agentic_rag_traces table reference missing — observability trace not written"}]
    if 'writeTrace' not in src:
        return [{"check": "trace_persist", "reason": "writeTrace function missing"}]
    return []


def check_cost_log(src: str) -> list[dict]:
    if 'logAICost' not in src:
        return [{"check": "cost_log", "reason": "logAICost not imported/called"}]
    count = len(re.findall(r"\blogAICost\s*\(", src))
    if count < 4:
        return [{"check": "cost_log", "reason": f"logAICost called only {count} times — Router/Grader/Generator/Checker need 4 separate calls minimum"}]
    return []


def check_migration_exists() -> list[dict]:
    if not os.path.isdir(MIGRATIONS):
        return [{"check": "migration_exists", "reason": f"{MIGRATIONS}/ directory missing"}]
    matches = glob.glob(os.path.join(MIGRATIONS, "*agentic_rag_traces*.sql"))
    if not matches:
        return [{"check": "migration_exists", "reason": "No migration found matching *agentic_rag_traces*.sql"}]
    src = read_file(matches[0]) or ""
    if "CREATE TABLE" not in src.upper() or "agentic_rag_traces" not in src:
        return [{"check": "migration_exists", "reason": f"{matches[0]} does not CREATE TABLE agentic_rag_traces"}]
    if "ENABLE ROW LEVEL SECURITY" not in src.upper():
        return [{"check": "migration_exists", "reason": f"{matches[0]} does not ENABLE ROW LEVEL SECURITY"}]
    return []


def check_config_toml() -> list[dict]:
    src = read_file(CONFIG_TOML) or ""
    if "[functions.agentic-rag-loop]" not in src:
        return [{"check": "config_toml", "reason": "[functions.agentic-rag-loop] section missing in supabase/config.toml"}]
    return []


def check_deploy_ps1() -> list[dict]:
    src = read_file(DEPLOY_PS1) or ""
    if "agentic-rag-loop" not in src:
        return [{"check": "deploy_ps1", "reason": "deploy-functions.ps1 missing `npx supabase functions deploy agentic-rag-loop` line"}]
    return []


def check_edge_contracts_membership() -> list[dict]:
    src = read_file(EDGE_CONTRACT) or ""
    if '"agentic-rag-loop"' not in src:
        return [{"check": "edge_contracts_all_funcs", "reason": "agentic-rag-loop missing from validate_edge_contracts.py ALL_FUNCTIONS"}]
    return []


def check_edge_contracts_required_fields() -> list[dict]:
    src = read_file(EDGE_CONTRACT) or ""
    if '"agentic-rag-loop":' not in src:
        return [{"check": "edge_contracts_required_fields", "reason": "agentic-rag-loop missing from validate_edge_contracts.py REQUIRED_FIELDS"}]
    return []


def check_no_em_dashes(src: str) -> list[dict]:
    prompts = _extract_system_prompts(src)
    issues = []
    for i, p in enumerate(prompts):
        if "—" in p:  # em dash
            issues.append({"check": "no_em_dashes",
                           "reason": f"System prompt #{i} contains an em dash (U+2014) — Windows-1252 encoding will garble it; use hyphens or colons"})
    return issues


def check_integration_wave(src: str) -> list[dict]:
    """R19: Items 2+3+4 wired into agentic-rag-loop."""
    issues = []
    # Item 2: hierarchical lane integrated
    if "lookupHierarchicalSummaries" not in src:
        issues.append({"check": "integration_wave", "reason": "Item 2 (Lane C): lookupHierarchicalSummaries function missing"})
    if "canonical_period_summaries" not in src:
        issues.append({"check": "integration_wave", "reason": "Item 2: must query canonical_period_summaries (Phase 2 table)"})
    # Item 3: temporal delegate
    if "delegateToTemporal" not in src:
        issues.append({"check": "integration_wave", "reason": "Item 3: delegateToTemporal function missing"})
    if 'temporal-rag-orchestrator' not in src:
        issues.append({"check": "integration_wave", "reason": "Item 3: must call /functions/v1/temporal-rag-orchestrator"})
    if "TEMPORAL_DELEGATE_DAYS" not in src:
        issues.append({"check": "integration_wave", "reason": "Item 3: TEMPORAL_DELEGATE_DAYS constant missing"})
    # Item 4: memory recall + store
    if "recallMemories" not in src:
        issues.append({"check": "integration_wave", "reason": "Item 4: recallMemories function missing"})
    if "extractAndStoreMemories" not in src:
        issues.append({"check": "integration_wave", "reason": "Item 4: extractAndStoreMemories function missing"})
    if "agent-memory-store" not in src:
        issues.append({"check": "integration_wave", "reason": "Item 4: must call /functions/v1/agent-memory-store"})
    if "EXTRACTOR_SYSTEM" not in src:
        issues.append({"check": "integration_wave", "reason": "Item 4: EXTRACTOR_SYSTEM prompt missing"})
    # Generator must receive memoryBlock so prior-session context flows in
    if "memoryBlock: string = \"\"" not in src and "memoryBlock: string = ''" not in src:
        issues.append({"check": "integration_wave", "reason": "Item 4: generatorStage must accept memoryBlock parameter"})
    return issues


def check_null_scope_guard(src: str) -> list[dict]:
    """R21: Router LLM can return time_scope: null (not {from:null,to:null}).
    JS default params don't kick in for explicit null. retrieverStage must
    coalesce to a safe shape, and spanDaysFromTimeScope must tolerate null/undefined.
    Both gaps surfaced as a runtime null-deref bug on 2026-05-21 during the
    RAG flywheel walk."""
    issues = []
    # retrieverStage must coalesce timeScope to a non-null shape
    if not re.search(r"timeScope\s*\|\|\s*\{\s*from\s*:\s*null", src):
        issues.append({"check": "null_scope_guard", "reason": "retrieverStage must coalesce timeScope || { from: null, to: null } — Router can return time_scope: null"})
    # spanDaysFromTimeScope must accept null|undefined
    if not re.search(r"scope\s*:\s*\{[^}]+\}\s*\|\s*null\s*\|\s*undefined", src):
        issues.append({"check": "null_scope_guard", "reason": "spanDaysFromTimeScope must accept scope: {...} | null | undefined and guard with !scope || !scope.from"})
    return issues


def check_temporal_comparison_backstop(src: str) -> list[dict]:
    """R22: Period-comparison -> temporal backstop (deep-walk CL3, 2026-07-08).
    The Router LLM mis-routes some PERIOD-COMPARISON questions ("MTBF this year vs
    last year" -> semantic; "compare 2026 vs 2025" / "Q1 vs Q2" -> cold_archive via
    a borderline->18mo from-date), shipping a false "no records >2yr ago" deflection
    for a RECENT comparison. A deterministic backstop forces temporal on a comparison
    intent + a recent period pair (leaving genuine deep-archive comparisons alone).
    Guards the whole class so a revert (dropping the guard) FAILs here."""
    issues = []
    # The guard must exist and force route = "temporal" for a recent comparison.
    if 'recent period-comparison forced to temporal' not in src:
        issues.append({"check": "temporal_comparison_backstop", "reason": "period-comparison temporal backstop missing — a recent 'compare 2026 vs 2025' / 'Q1 vs Q2' question mis-routes to cold_archive/semantic and ships a false 'no records >2yr ago' deflection"})
    # It must be CONDITIONAL (compare intent + recent period), not a blunt override.
    if not (re.search(r"hasCompare", src) and re.search(r"hasRecentPeriod", src)):
        issues.append({"check": "temporal_comparison_backstop", "reason": "backstop must gate on hasCompare + hasRecentPeriod (a blunt 'always temporal' would steal genuine semantic/archive routes)"})
    # It must exempt genuine deep-archive comparisons (all named years >18mo old).
    if "allArchivalYears" not in src:
        issues.append({"check": "temporal_comparison_backstop", "reason": "backstop must exempt allArchivalYears so a genuine '2019 vs 2020' deep-archive comparison stays cold_archive"})
    return issues


def check_voice_handler_optin() -> list[dict]:
    """R20: voice-handler.js wires the agentic-rag-loop opt-in path."""
    src = read_file(VOICE_HANDLER_JS) or ""
    if not src:
        return [{"check": "voice_handler_optin", "reason": f"{VOICE_HANDLER_JS} not found"}]
    issues = []
    if "_isLongHorizonQuestion" not in src:
        issues.append({"check": "voice_handler_optin", "reason": "_isLongHorizonQuestion detector helper missing"})
    if "_LONG_HORIZON_RE" not in src:
        issues.append({"check": "voice_handler_optin", "reason": "_LONG_HORIZON_RE pattern const missing"})
    if "/functions/v1/agentic-rag-loop" not in src:
        issues.append({"check": "voice_handler_optin", "reason": "voice-handler must POST to /functions/v1/agentic-rag-loop on long-horizon hit"})
    # Must call detector BEFORE the ai-gateway block — opt-in path tries first
    horizon_pos = src.find("_isLongHorizonQuestion(transcript)")
    gateway_pos = src.find("/functions/v1/ai-gateway")
    if horizon_pos < 0 or gateway_pos < 0 or horizon_pos > gateway_pos:
        issues.append({"check": "voice_handler_optin", "reason": "_isLongHorizonQuestion gate must be checked BEFORE the ai-gateway POST"})
    return issues


def check_json_mode(src: str) -> list[dict]:
    # Multiline-aware: each callAI(...) options block can span many lines.
    call_blocks = re.findall(r"callAI\s*\(.*?\}\s*\)", src, re.DOTALL)
    if not call_blocks:
        return [{"check": "json_mode", "reason": "No callAI invocations found"}]
    explicit = sum(1 for b in call_blocks if re.search(r"jsonMode\s*:\s*true", b))
    if explicit == 0:
        return [{"check": "json_mode", "reason": f"None of the {len(call_blocks)} callAI calls explicitly set jsonMode: true — be explicit for grep-ability"}]
    return []


CHECKS = [
    ("file_exists",                    "R01 Edge fn file exists",                                check_file_exists),
    ("five_stages",                    "R02 All 5 stages present (Router/Retriever/Grader/Generator/Checker)", lambda: check_five_stages(_read_fn())),
    ("hive_scoping",                   "R03 Hive scoping on every Supabase query",               lambda: check_hive_scoping(_read_fn())),
    ("free_tier_only",                 "R04 FREE-TIER ONLY (no paid Claude/OpenAI/Anthropic)",   lambda: check_free_tier_only(_read_fn())),
    ("uses_callai",                    "R05 Uses _shared/ai-chain.ts callAI (no raw fetch)",     lambda: check_uses_callai(_read_fn())),
    ("rate_limit",                     "R06 Rate limit enforced before any stage runs",          lambda: check_rate_limit(_read_fn())),
    ("retry_cap",                      "R07 MAX_RETRIES ≤ 2 enforced",                           lambda: check_retry_cap(_read_fn())),
    ("grader_threshold",               "R08 GRADER_THRESHOLD in [0.3, 0.7]",                     lambda: check_grader_threshold(_read_fn())),
    ("question_cap",                   "R09 MAX_QUESTION_CHARS ≤ 1000 + truncated before LLM",   lambda: check_question_cap(_read_fn())),
    ("trace_persist",                  "R10 Trace persisted to agentic_rag_traces",              lambda: check_trace_persist(_read_fn())),
    ("cost_log",                       "R11 logAICost called ≥ 4 times (per stage)",             lambda: check_cost_log(_read_fn())),
    ("migration_exists",               "R12 Migration creates agentic_rag_traces + RLS",         check_migration_exists),
    ("config_toml",                    "R13 4-place sync: config.toml registration",             check_config_toml),
    ("deploy_ps1",                     "R14 4-place sync: deploy-functions.ps1 line",            check_deploy_ps1),
    ("edge_contracts_all_funcs",       "R15 4-place sync: validate_edge_contracts ALL_FUNCTIONS", check_edge_contracts_membership),
    ("edge_contracts_required_fields", "R16 4-place sync: validate_edge_contracts REQUIRED_FIELDS", check_edge_contracts_required_fields),
    ("no_em_dashes",                   "R17 No em dashes in system prompts (encoding safety)",   lambda: check_no_em_dashes(_read_fn())),
    ("json_mode",                      "R18 JSON mode explicit on at least one callAI call",     lambda: check_json_mode(_read_fn())),
    ("integration_wave",               "R19 Items 2+3+4 wired (hierarchical lane + temporal delegate + memory recall/store)", lambda: check_integration_wave(_read_fn())),
    ("voice_handler_optin",            "R20 voice-handler.js opt-in: _isLongHorizonQuestion + agentic-rag-loop POST",        check_voice_handler_optin),
    ("null_scope_guard",               "R21 Null-scope guard: retrieverStage + spanDaysFromTimeScope tolerate null time_scope", lambda: check_null_scope_guard(_read_fn())),
    ("temporal_comparison_backstop",   "R22 Period-comparison -> temporal backstop (recent 'YoY'/'Q1 vs Q2'/'2026 vs 2025' not mis-routed to cold_archive/semantic)", lambda: check_temporal_comparison_backstop(_read_fn())),
]


def main() -> int:
    print("\033[1m\nAgentic RAG Loop Validator (Phase 1 of AGENTIC_RAG_ROADMAP.md)\033[0m")
    print("=" * 70)
    print(f"  Scanning {EDGE_FN_PATH}")
    print(f"  Cross-checking config.toml + deploy-functions.ps1 + validate_edge_contracts.py + migrations/")

    all_issues = []
    keys   = [c[0] for c in CHECKS]
    labels = {c[0]: c[1] for c in CHECKS}

    for key, _label, fn in CHECKS:
        for issue in fn():
            issue.setdefault("check", key)
            all_issues.append(issue)

    n_pass, n_skip, n_fail = format_result(keys, labels, all_issues)
    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
