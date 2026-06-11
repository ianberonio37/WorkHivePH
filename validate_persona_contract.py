"""
Persona Contract Validator -- WorkHive Platform
================================================
Forward-only gate on the WorkHive Persona Contract (Hezekiah / Zaniah across
every worker-facing AI surface). See WORKHIVE_PERSONA_CONTRACT.md.

The contract has five modes:

  conversational       - Voice Journal (long-form, server-side only)
  companion            - Floating AI / Personal Assistant
  narrated-specialist  - visual-defect, voice-router, asset-brain
  briefing-signature   - AMC orchestrator (autonomous)
  silent               - utility specialists that never speak to a worker

This validator enforces that:

  L1  The canonical persona modules exist and export the required symbols.
      - supabase/functions/_shared/persona.ts (server-side source of truth)
      - wh-persona.js                          (client-side mirror)

  L2  Every server surface declared in SERVER_PERSONA_ADOPTION imports
      from _shared/persona.ts and calls buildPersonaBlock(..) with its
      declared mode.

  L3  Every client surface declared in CLIENT_PERSONA_ADOPTION either
      loads wh-persona.js via a <script> tag OR relies on nav-hub.js
      (which lazy-loads it), and uses window.getCompanionBlock() to
      prepend the block to its system prompt.

  L4  Account-level wiring: ai-gateway hydrates ctx.persona from
      worker_profiles.preferred_persona so downstream specialists
      inherit the worker's chosen voice.

  L5  Hive-level wiring: amc-orchestrator reads hives.preferred_persona
      and signs each brief with that persona (Phase 6).

  L6  Migrations present:
        20260513000020_persona_contract.sql  (worker_profiles column)
        20260513000022_hive_preferred_persona.sql (hives column)

  L7  Server <-> client persona key parity: both modules MUST expose the
      same set of persona keys (today: { hezekiah, zaniah }) -- divergence
      means a worker's choice on one device doesn't render on another.

Usage:  python validate_persona_contract.py

This is a snapshot validator, not a ratcheted one -- the persona surface
list is small and finite; new adopters extend the list intentionally.

Skills consulted: ai-engineer (prompt patterns), frontend (script load
order), qa (cross-surface adoption), platform-guardian (gate registration).
"""
from __future__ import annotations

import os
import re
import sys

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


# -- Paths ---------------------------------------------------------------------

SHARED_PERSONA_TS  = os.path.join("supabase", "functions", "_shared", "persona.ts")
CLIENT_PERSONA_JS  = "wh-persona.js"
AI_GATEWAY_TS      = os.path.join("supabase", "functions", "ai-gateway", "index.ts")
AMC_ORCH_TS        = os.path.join("supabase", "functions", "amc-orchestrator", "index.ts")
NAV_HUB_JS         = "nav-hub.js"
MIGRATIONS_DIR     = os.path.join("supabase", "migrations")

REQUIRED_MIGRATIONS = [
    "20260513000020_persona_contract.sql",
    "20260513000022_hive_preferred_persona.sql",
]


# -- Adoption matrix (server) --------------------------------------------------
#
# Each entry: edge-fn dir => declared persona mode.
# When a new surface adopts persona, add it here. The validator will then
# check that the file actually imports + calls buildPersonaBlock with the
# right mode literal.

SERVER_PERSONA_ADOPTION = {
    "voice-journal-agent":    "conversational",
    "visual-defect-capture":  "narrated-specialist",
    "voice-action-router":    "narrated-specialist",
    "asset-brain-query":      "narrated-specialist",
    # 2026-06-07 Phase 5 persona pass: the two JSON specialists now emit a
    # `narration` field in the worker's voice (additive; their output
    # contracts set no additionalProperties:false). See WORKHIVE_PERSONA_CONTRACT.md.
    "analytics-orchestrator": "narrated-specialist",
    "project-orchestrator":   "narrated-specialist",
    # 2026-06-07 Phase 5 rotation 2: engineering-calc-agent narrates the report
    # layer only (math stays bare, WAT split); shift-planner is an autonomous
    # hive-level briefing so it signs the footer (amc pattern, hive persona).
    "engineering-calc-agent": "narrated-specialist",
    "shift-planner-orchestrator": "briefing-signature",
    "amc-orchestrator":       "briefing-signature",
}

# Intentionally NOT persona-adopted (Phase 5 decision, 2026-06-07) — documented
# so a future session does not "close the gap" by force-fitting a narration:
#   - intelligence-report:  a network/industry benchmarking report aggregated
#     across ALL hives. No individual worker recipient, so a worker-voice
#     narration is a category mismatch. Stays impersonal.
#   - engineering-bom-sow:  a strict ~8000-token BOM/SOW document contract;
#     adding a top-level field risks the downstream document schema. Stays bare.
PERSONA_INTENTIONALLY_ABSENT = {
    "intelligence-report":  "network industry report — no per-worker recipient",
    "engineering-bom-sow":  "strict doc contract — extra field risks the schema",
}


# -- Adoption matrix (client) --------------------------------------------------
#
# Each entry: client surface => evidence that it consumes the companion
# block. value is the substring that must appear in the file. For inline
# script surfaces (assistant.html) we look for window.getCompanionBlock().
# For shared client modules (companion-launcher.js) we look for the same call.

CLIENT_PERSONA_ADOPTION = {
    "companion-launcher.js":  "getCompanionBlock",
    "assistant.html":  "getCompanionBlock",
}


# -- Layer 1: canonical modules exist + export required symbols ---------------

SERVER_REQUIRED_EXPORTS = (
    "PERSONAS",
    "DEFAULT_PERSONA",
    "clampPersona",
    "buildPersonaBlock",
    "personaName",
)

CLIENT_REQUIRED_GLOBALS = (
    "window.PERSONAS",
    "window.DEFAULT_PERSONA",
    "window.clampPersona",
    "window.getCompanionBlock",
    "window.buildCompanionBlock",
    "window.getPersonaKey",
)

def check_canonical_modules() -> list[dict]:
    issues = []
    server = read_file(SHARED_PERSONA_TS)
    if server is None:
        issues.append({
            "check": "canonical_modules",
            "reason": f"Server-side persona module missing: {SHARED_PERSONA_TS}",
        })
    else:
        missing = [s for s in SERVER_REQUIRED_EXPORTS if s not in server]
        if missing:
            issues.append({
                "check": "canonical_modules",
                "reason": (f"{SHARED_PERSONA_TS} is missing required exports: "
                           f"{', '.join(missing)}"),
            })
    client = read_file(CLIENT_PERSONA_JS)
    if client is None:
        issues.append({
            "check": "canonical_modules",
            "reason": f"Client-side persona mirror missing: {CLIENT_PERSONA_JS}",
        })
    else:
        missing = [s for s in CLIENT_REQUIRED_GLOBALS if s not in client]
        if missing:
            issues.append({
                "check": "canonical_modules",
                "reason": (f"{CLIENT_PERSONA_JS} is missing required globals: "
                           f"{', '.join(missing)}"),
            })
    return issues


# -- Layer 2: server adoption -------------------------------------------------

def check_server_adoption() -> list[dict]:
    issues = []
    for fn_dir, mode in SERVER_PERSONA_ADOPTION.items():
        path = os.path.join("supabase", "functions", fn_dir, "index.ts")
        content = read_file(path)
        if content is None:
            issues.append({
                "check": "server_adoption",
                "reason": (f"Declared persona adopter '{fn_dir}' has no "
                           f"index.ts at {path} -- remove from "
                           f"SERVER_PERSONA_ADOPTION or restore the file."),
            })
            continue
        if "_shared/persona.ts" not in content:
            issues.append({
                "check": "server_adoption",
                "reason": (f"{fn_dir}/index.ts does not import from "
                           f"_shared/persona.ts -- add `import { ... } from "
                           f"'../_shared/persona.ts'` so the persona overlay "
                           f"is centralised."),
            })
            continue
        # buildPersonaBlock call with declared mode literal somewhere in file.
        mode_re = re.compile(
            r'buildPersonaBlock\s*\([^)]*["\']' + re.escape(mode) + r'["\']'
        )
        if not mode_re.search(content):
            issues.append({
                "check": "server_adoption",
                "reason": (f"{fn_dir}/index.ts imports persona but does not "
                           f"call buildPersonaBlock(..., \"{mode}\") -- the "
                           f"adoption matrix says this surface is "
                           f"{mode}-mode."),
            })
    return issues


# -- Layer 3: client adoption -------------------------------------------------

def check_client_adoption() -> list[dict]:
    issues = []
    nav_hub = read_file(NAV_HUB_JS) or ""
    has_lazy_load = "wh-persona.js" in nav_hub
    for surface, needle in CLIENT_PERSONA_ADOPTION.items():
        content = read_file(surface)
        if content is None:
            issues.append({
                "check": "client_adoption",
                "reason": (f"Declared client adopter '{surface}' missing -- "
                           f"remove from CLIENT_PERSONA_ADOPTION or restore "
                           f"the file."),
            })
            continue
        if needle not in content:
            issues.append({
                "check": "client_adoption",
                "reason": (f"{surface} does not call window.getCompanionBlock "
                           f"-- the companion block is not being prepended "
                           f"to the system prompt; Hezekiah/Zaniah overlay is "
                           f"missing on this surface."),
            })
            continue
        # Must also load wh-persona.js either explicitly or via nav-hub.js.
        explicit = bool(re.search(r'<script[^>]*src=["\']wh-persona\.js', content))
        if not explicit and not has_lazy_load:
            issues.append({
                "check": "client_adoption",
                "reason": (f"{surface} uses getCompanionBlock but neither "
                           f"loads wh-persona.js directly nor relies on "
                           f"nav-hub.js (which currently does not lazy-load "
                           f"it). getCompanionBlock will be undefined at "
                           f"runtime."),
            })
    return issues


# -- Layer 4: account-level wiring (ai-gateway) -------------------------------

def check_gateway_hydration() -> list[dict]:
    issues = []
    content = read_file(AI_GATEWAY_TS)
    if content is None:
        issues.append({
            "check": "gateway_hydration",
            "reason": f"ai-gateway/index.ts missing at {AI_GATEWAY_TS}",
        })
        return issues
    if "preferred_persona" not in content:
        issues.append({
            "check": "gateway_hydration",
            "reason": ("ai-gateway/index.ts does not read "
                       "worker_profiles.preferred_persona -- downstream "
                       "specialists will not inherit the worker's chosen "
                       "voice on devices other than the one where it was "
                       "set. Hydrate ctx.persona from the profile row."),
        })
    if not re.search(r"context\.persona|ctx\.persona|\.persona\s*=\s*", content):
        issues.append({
            "check": "gateway_hydration",
            "reason": ("ai-gateway/index.ts reads preferred_persona but does "
                       "not inject it into the routed context object. "
                       "Specialists will not see the persona."),
        })
    return issues


# -- Layer 5: hive-level wiring (amc-orchestrator) ----------------------------

def check_amc_hive_persona() -> list[dict]:
    issues = []
    content = read_file(AMC_ORCH_TS)
    if content is None:
        issues.append({
            "check": "amc_hive_persona",
            "reason": f"amc-orchestrator/index.ts missing at {AMC_ORCH_TS}",
        })
        return issues
    if "preferred_persona" not in content:
        issues.append({
            "check": "amc_hive_persona",
            "reason": ("amc-orchestrator/index.ts does not read "
                       "hives.preferred_persona -- the brief signature falls "
                       "back to the platform default and ignores the hive's "
                       "configured voice (Phase 6 contract)."),
        })
    if "briefing-signature" not in content:
        issues.append({
            "check": "amc_hive_persona",
            "reason": ("amc-orchestrator/index.ts does not call "
                       "buildPersonaBlock(..., \"briefing-signature\") -- "
                       "briefings are unsigned."),
        })
    return issues


# -- Layer 6: migration presence ---------------------------------------------

def check_migrations_present() -> list[dict]:
    issues = []
    if not os.path.isdir(MIGRATIONS_DIR):
        issues.append({
            "check": "migrations_present",
            "reason": f"Migrations dir missing: {MIGRATIONS_DIR}",
        })
        return issues
    existing = set(os.listdir(MIGRATIONS_DIR))
    for fname in REQUIRED_MIGRATIONS:
        if fname not in existing:
            issues.append({
                "check": "migrations_present",
                "reason": (f"Required persona migration missing: {fname} -- "
                           f"the column the validator relies on never lands "
                           f"in production."),
            })
    return issues


# -- Layer 7: key parity ------------------------------------------------------

PERSONA_KEY_RE = re.compile(
    r"(?:PERSONAS\s*[:=]?\s*\{|window\.PERSONAS\s*=\s*PERSONAS)",
)

def _extract_persona_keys(content: str) -> set[str]:
    """Find top-level keys inside the PERSONAS = { ... } object literal.
    Heuristic: locate the `PERSONAS = {` opening (any TypeScript type
    annotation between `PERSONAS` and `=` is skipped), then extract every
    identifier-followed-by-`: {` pair inside the brace-balanced body."""
    if content is None:
        return set()
    # `PERSONAS` (optionally followed by a TS type annotation `: Record<...>`)
    # then `=` then `{`. The non-greedy [^=]* swallows the type annotation
    # without leaking past the assignment.
    m = re.search(r"PERSONAS\b[^=]{0,200}=\s*\{", content)
    if not m:
        return set()
    start = m.end()
    depth = 1
    end = start
    while end < len(content) and depth > 0:
        ch = content[end]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        end += 1
    body = content[start:end - 1]
    # Match identifier:  at depth 1 (rough: line-leading or comma-leading).
    keys = set()
    for line_match in re.finditer(
        r"(?:^|[,{\n])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*\{",
        body,
    ):
        keys.add(line_match.group(1))
    return keys


def check_key_parity() -> list[dict]:
    issues = []
    server = read_file(SHARED_PERSONA_TS)
    client = read_file(CLIENT_PERSONA_JS)
    server_keys = _extract_persona_keys(server) if server else set()
    client_keys = _extract_persona_keys(client) if client else set()
    if not server_keys:
        issues.append({
            "check": "key_parity",
            "reason": (f"Could not extract PERSONAS keys from "
                       f"{SHARED_PERSONA_TS} -- parity check inconclusive."),
        })
        return issues
    if not client_keys:
        issues.append({
            "check": "key_parity",
            "reason": (f"Could not extract PERSONAS keys from "
                       f"{CLIENT_PERSONA_JS} -- parity check inconclusive."),
        })
        return issues
    only_server = server_keys - client_keys
    only_client = client_keys - server_keys
    if only_server or only_client:
        parts = []
        if only_server:
            parts.append(f"only in {SHARED_PERSONA_TS}: {sorted(only_server)}")
        if only_client:
            parts.append(f"only in {CLIENT_PERSONA_JS}: {sorted(only_client)}")
        issues.append({
            "check": "key_parity",
            "reason": ("Server and client persona maps diverged -- a "
                       "worker's choice on one device will not render on "
                       "another. " + "; ".join(parts)),
        })
    return issues


# -- Layer 8: domain differentiation -----------------------------------------

# 2026-05-19 Companion Streamline Step D guardrail. The persona toggle is
# only meaningful if Hezekiah (technical) and Zaniah (strategist) actually
# DIFFER in lens. This check fails the build if:
#   - either persona drops its DOMAIN_LENS entry,
#   - tone bullets become identical / nearly identical (>50% lexical
#     overlap signals the differentiation was undone),
#   - example replies stop using lane-specific vocabulary,
#   - DEFAULT_PERSONA stops being "zaniah" (first-time-visitor default).

HEZEKIAH_KEYWORDS = (
    "torque", "sop", "iso 14224", "loto", "ir gun", "ppe",
    "regrease", "lube", "manual", "failure mode",
)
ZANIAH_KEYWORDS = (
    "oee", "backlog", "planned-vs-reactive", "planned vs reactive",
    "recurrence", "mtbf", "kpi", "weekly", "escalation", "pattern",
)


def _extract_persona_field(content: str, persona_key: str, field: str) -> str:
    """Pull a `tone: [ ... ]` or `examples: [ ... ]` array body out of the
    persona record. Returns the joined string for keyword scanning."""
    if not content:
        return ""
    # Anchor on the persona key declaration: `james: {` or `rosa: {`.
    open_match = re.search(
        rf"\b{re.escape(persona_key)}\s*:\s*\{{",
        content,
    )
    if not open_match:
        return ""
    # Walk inside the persona block, find the field name, take everything
    # between the next `[` and matching `]`.
    persona_body_start = open_match.end()
    depth = 1
    i = persona_body_start
    while i < len(content) and depth > 0:
        if content[i] == "{":
            depth += 1
        elif content[i] == "}":
            depth -= 1
        i += 1
    persona_body = content[persona_body_start:i - 1]
    field_match = re.search(rf"\b{re.escape(field)}\s*:\s*\[", persona_body)
    if not field_match:
        return ""
    arr_start = field_match.end()
    bracket_depth = 1
    j = arr_start
    while j < len(persona_body) and bracket_depth > 0:
        if persona_body[j] == "[":
            bracket_depth += 1
        elif persona_body[j] == "]":
            bracket_depth -= 1
        j += 1
    return persona_body[arr_start:j - 1].lower()


def _bullet_overlap_ratio(a_text: str, b_text: str) -> float:
    """Crude lexical overlap on a set of significant words. Stop-words
    stripped. Returns share of A's tokens also present in B."""
    stop = {
        "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for",
        "is", "are", "was", "were", "be", "been", "with", "by", "from", "as",
        "you", "your", "yours", "i", "me", "my", "we", "us", "our", "they",
        "them", "their", "this", "that", "these", "those", "it", "its",
        "do", "don't", "doesn't", "not", "no", "yes", "if", "then", "so",
        "when", "what", "which", "who", "how", "why", "where",
        "would", "could", "should", "can", "will", "may", "might", "must",
        "one", "two", "three", "more", "less", "some", "any", "every",
        "worker", "filipino", "english",
    }
    def _tokens(s: str) -> set[str]:
        return {
            t for t in re.findall(r"[a-z0-9-]{3,}", s.lower())
            if t not in stop
        }
    a = _tokens(a_text)
    b = _tokens(b_text)
    if not a:
        return 0.0
    return len(a & b) / len(a)


def check_domain_differentiation() -> list[dict]:
    issues = []
    server = read_file(SHARED_PERSONA_TS)
    client = read_file(CLIENT_PERSONA_JS)

    # 8a. DOMAIN_LENS exists in both, with both persona entries.
    # Accept either TS-style identifier keys (`hezekiah:`) or JS-style
    # string keys (`'hezekiah':` / `"hezekiah":`) inside the LENS object.
    for path, content in (("server", server), ("client", client)):
        if not content:
            continue
        if "DOMAIN_LENS" not in content:
            issues.append({
                "check": "domain_differentiation",
                "reason": f"{path} persona module is missing the DOMAIN_LENS const — Step D persona differentiation is undone.",
            })
            continue
        # Look at the whole DOMAIN_LENS object body (not a fixed slice).
        # Strategy: locate `DOMAIN_LENS` then walk braces to find the
        # matching close — same trick as _extract_persona_keys.
        lens_open = re.search(r"DOMAIN_LENS\b[^=]{0,200}=\s*\{", content)
        lens_body = ""
        if lens_open:
            start = lens_open.end()
            depth = 1
            j = start
            while j < len(content) and depth > 0:
                if content[j] == "{":
                    depth += 1
                elif content[j] == "}":
                    depth -= 1
                j += 1
            lens_body = content[start:j - 1]
        if not re.search(r"['\"]?hezekiah['\"]?\s*:", lens_body):
            issues.append({
                "check": "domain_differentiation",
                "reason": f"{path} DOMAIN_LENS does not have a hezekiah entry.",
            })
        if not re.search(r"['\"]?zaniah['\"]?\s*:", lens_body):
            issues.append({
                "check": "domain_differentiation",
                "reason": f"{path} DOMAIN_LENS does not have a zaniah entry.",
            })

    # 8b. DEFAULT_PERSONA must be 'zaniah' (Step D decision: strategist for
    # first-time visitors). Skip optional TS type annotation between the
    # identifier and the `=`.
    for path, content in (
        (SHARED_PERSONA_TS, server),
        (CLIENT_PERSONA_JS, client),
    ):
        if not content:
            continue
        m = re.search(
            r"DEFAULT_PERSONA(?:\s*:\s*\w+)?\s*=\s*['\"]([^'\"]+)['\"]",
            content,
        )
        if not m:
            issues.append({
                "check": "domain_differentiation",
                "reason": f"{path}: DEFAULT_PERSONA not found.",
            })
            continue
        if m.group(1) != "zaniah":
            issues.append({
                "check": "domain_differentiation",
                "reason": (
                    f"{path}: DEFAULT_PERSONA is '{m.group(1)}' but Step D "
                    "set it to 'zaniah' so first-time visitors land on the "
                    "strategist lens. Update or document the override."
                ),
            })

    # 8c. tone bullets must be differentiated (no >50% lexical overlap).
    if server:
        hez_tone = _extract_persona_field(server, "hezekiah", "tone")
        zan_tone = _extract_persona_field(server, "zaniah",   "tone")
        if hez_tone and zan_tone:
            overlap = _bullet_overlap_ratio(hez_tone, zan_tone)
            if overlap > 0.5:
                issues.append({
                    "check": "domain_differentiation",
                    "reason": (
                        f"Hezekiah and Zaniah tone bullets share {overlap:.0%} of "
                        "significant tokens — the differentiation has eroded. "
                        "Step D requires distinct technical-vs-strategist "
                        "voicing. Re-divide the tone[] lists."
                    ),
                })

    # 8d. examples must use lane-specific keywords.
    if server:
        hez_ex = _extract_persona_field(server, "hezekiah", "examples")
        zan_ex = _extract_persona_field(server, "zaniah",   "examples")
        hez_hits = [k for k in HEZEKIAH_KEYWORDS if k in hez_ex]
        zan_hits = [k for k in ZANIAH_KEYWORDS   if k in zan_ex]
        if len(hez_hits) < 3:
            issues.append({
                "check": "domain_differentiation",
                "reason": (
                    "Hezekiah's examples must reference at least 3 technical-lane "
                    f"keywords (torque/SOP/ISO/LOTO/IR gun/etc). Found: {hez_hits}."
                ),
            })
        if len(zan_hits) < 3:
            issues.append({
                "check": "domain_differentiation",
                "reason": (
                    "Zaniah's examples must reference at least 3 strategist-lane "
                    f"keywords (OEE/backlog/planned-vs-reactive/recurrence/MTBF/etc). Found: {zan_hits}."
                ),
            })

    return issues


# -- Layer 9: within-conversation recall guardrail ----------------------------
#
# 2026-06-12 Memory-recall fix (Probe Taxonomy family C). The floating launcher
# + voice journal load the last 10 turns into the memory block, but three older
# rules SUPPRESSED recall of a fact the worker stated earlier in the SAME
# conversation: the voice-journal GROUNDING rule refused "any specific number"
# as a record lookup, the DOMAIN_LENS reactive bridge deflected "what torque?"
# to the other persona's lane, and (unseen) the model confabulated a value from
# a persona example. The fix is a shared CONVERSATION_RECALL guardrail that
# OUTRANKS the lane + grounding rules, wired into BOTH worker-facing prose modes
# (conversational + companion), plus a narrowed voice-journal grounding rule.
# This layer guards that wiring forward-only so it cannot be silently unwound.
# The behavioural proof is the C6/C7 live probes; this is the static ratchet.

VOICE_JOURNAL_AGENT_TS = os.path.join(
    "supabase", "functions", "voice-journal-agent", "index.ts"
)


def check_conversation_recall() -> list[dict]:
    issues = []
    server = read_file(SHARED_PERSONA_TS)
    if server is None:
        issues.append({
            "check": "conversation_recall",
            "reason": f"{SHARED_PERSONA_TS} missing — cannot verify recall guardrail.",
        })
        return issues

    # 9a. The shared CONVERSATION_RECALL guardrail const must exist.
    if "CONVERSATION_RECALL" not in server:
        issues.append({
            "check": "conversation_recall",
            "reason": (
                f"{SHARED_PERSONA_TS} has no CONVERSATION_RECALL guardrail. "
                "Within-conversation recall regresses: the grounding rule + "
                "lane bridge will refuse/deflect a fact the worker stated "
                "earlier in the same conversation (Probe family C, C6/C7)."
            ),
        })
    else:
        # 9b. It must be interpolated into BOTH worker-facing prose modes
        #     (conversational + companion). The const definition is one
        #     mention; each mode wiring is a `${CONVERSATION_RECALL}`.
        wired = len(re.findall(r"\$\{CONVERSATION_RECALL\}", server))
        if wired < 2:
            issues.append({
                "check": "conversation_recall",
                "reason": (
                    "CONVERSATION_RECALL is defined but wired into "
                    f"{wired} prose block(s); it must appear in BOTH the "
                    "conversational and companion blocks (>=2 interpolations) "
                    "so the floating launcher and voice journal both carry it."
                ),
            })
        # 9c. The guardrail must reference the memory block (the mechanism) —
        #     guards against a hollow const that says nothing actionable.
        if "memory block" not in server.lower():
            issues.append({
                "check": "conversation_recall",
                "reason": (
                    "CONVERSATION_RECALL must point the model at the memory "
                    "block (where the worker's earlier turns live); without it "
                    "the directive is not actionable."
                ),
            })
        # 9e. The guardrail must FORBID fabricated recall (the C5 inverse bug:
        #     a clean live walk found the companion inventing a part number /
        #     fault code / torque for an asset never mentioned). Recall-on-empty
        #     must abstain, not confabulate.
        if "abstain" not in server.lower() or "fabricate" not in server.lower():
            issues.append({
                "check": "conversation_recall",
                "reason": (
                    "CONVERSATION_RECALL must tell the model to ABSTAIN (not "
                    "fabricate) when asked to recall something NOT in the memory "
                    "block. Without it the companion invents a plausible part "
                    "number/torque/fault code (C5 abstention failure) — the "
                    "dangerous inverse of the C6/C7 recall bug."
                ),
            })

    # 9d. The voice-journal grounding rule must carve out conversation recall,
    #     not blanket-refuse every number as a saved-record lookup.
    agent = read_file(VOICE_JOURNAL_AGENT_TS)
    if agent is None:
        issues.append({
            "check": "conversation_recall",
            "reason": f"{VOICE_JOURNAL_AGENT_TS} missing — cannot verify grounding carve-out.",
        })
    elif "GROUNDING" in agent and "in THIS conversation" not in agent:
        issues.append({
            "check": "conversation_recall",
            "reason": (
                f"{VOICE_JOURNAL_AGENT_TS} GROUNDING rule does not carve out "
                "conversation recall (no 'in THIS conversation' clause). It "
                "will refuse to recall a number the worker said earlier as if "
                "it were a database lookup — the original C6/C7 bug."
            ),
        })
    return issues


# -- Driver -------------------------------------------------------------------

CHECK_NAMES = [
    "canonical_modules",
    "server_adoption",
    "client_adoption",
    "gateway_hydration",
    "amc_hive_persona",
    "migrations_present",
    "key_parity",
    "domain_differentiation",
    "conversation_recall",
]

CHECK_LABELS = {
    "canonical_modules":      "L1  Shared persona modules exist + export required symbols",
    "server_adoption":        "L2  Every declared server surface imports persona.ts and uses its mode",
    "client_adoption":        "L3  Every declared client surface loads wh-persona.js and uses getCompanionBlock",
    "gateway_hydration":      "L4  ai-gateway hydrates ctx.persona from worker_profiles.preferred_persona",
    "amc_hive_persona":       "L5  amc-orchestrator reads hives.preferred_persona for brief signature",
    "migrations_present":     "L6  Persona migrations (worker + hive column) present",
    "key_parity":             "L7  Server and client persona key sets are identical",
    "domain_differentiation": "L8  Step D: Hezekiah=Technical / Zaniah=Strategist lens preserved (DOMAIN_LENS, tone, examples)",
    "conversation_recall":    "L9  Within-conversation recall guardrail wired into both prose modes + grounding carve-out",
}


def main() -> int:
    print("\033[1m\nPersona Contract Validator (9-layer)\033[0m")
    print("=" * 60)
    print(f"  Tracking {len(SERVER_PERSONA_ADOPTION)} server surface(s) + "
          f"{len(CLIENT_PERSONA_ADOPTION)} client surface(s).")

    issues = []
    issues += check_canonical_modules()
    issues += check_server_adoption()
    issues += check_client_adoption()
    issues += check_gateway_hydration()
    issues += check_amc_hive_persona()
    issues += check_migrations_present()
    issues += check_key_parity()
    issues += check_domain_differentiation()
    issues += check_conversation_recall()

    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m" if n_skip == 0
              else f"  \033[92m{n_pass} PASS  {n_skip} SKIP  0 FAIL\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")

    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
