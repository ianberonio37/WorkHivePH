"""
Env Secret Coverage Validator — WorkHive Platform
==================================================
Edge functions read secrets via `Deno.env.get('FOO')`. When a function
references a secret that isn't declared in supabase/functions/.env (or
production secrets dashboard), the value is undefined: the function then
either throws on a `!` assertion, makes a request with empty bearer
header (401 from upstream), or silently produces wrong results.

Same silent-failure class as cron config drift and edge caller contract:
the contract between code and config has two sides; neither side knows
the other has drifted until a user reports a broken feature.

  Layer 1 — Declared coverage
    1.  Every `Deno.env.get('FOO')` and `envKey: 'FOO'` reference in
        supabase/functions/ is declared in supabase/functions/.env, OR
        is a built-in Supabase var (auto-injected: SUPABASE_URL,
        SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_DB_URL).
    [FAIL] Function will read undefined; 500 / 401 / silent wrong result.

  Layer 2 — Hard-required coverage
    2.  Every var read with `Deno.env.get('FOO')!` (TypeScript non-null
        assertion = function declares it required) MUST be in .env or
        built-ins. Same as L1 but stricter — catches the case where the
        var is declared optional in .env (commented out) but the function
        treats it as required.
    [FAIL] Function will throw "TypeError: cannot read properties of null".

  Layer 3 — Orphan .env keys
    3.  Every key in supabase/functions/.env is referenced somewhere in
        supabase/functions/ source. Catches keys left over from removed
        features that still appear in .env (developer confusion + leak
        risk if .env ever gets accidentally committed).
    [WARN] Orphan keys — review whether they should be removed.

  Layer 4 — Hardcoded secret detection
    4.  No source file under supabase/functions/ contains a string that
        looks like a real API key (Stripe sk_, Groq gsk_, Cerebras csk-,
        Voyage pa-, Jina jina_, OpenRouter sk-or-, Resend re_, generic
        bearer tokens). Secrets must live in .env, not in source.
    [FAIL] Hardcoded secret in source — gitignore won't catch it.

Usage:  python validate_env_secret_coverage.py
Output: env_secret_coverage_report.json
"""
import json
import os
import re
import sys
from collections import defaultdict

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT          = os.path.dirname(os.path.abspath(__file__))
FUNCTIONS_DIR = os.path.join(ROOT, "supabase", "functions")
ENV_FILE      = os.path.join(FUNCTIONS_DIR, ".env")


# Built-in Supabase env vars auto-injected into every edge function runtime.
# Source: https://supabase.com/docs/guides/functions/secrets
BUILT_IN_SUPABASE_VARS: set = {
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_DB_URL",
    "SUPABASE_PUBLISHABLE_KEY",
}

# Keys that live in supabase/functions/.env but are intentionally consumed
# by other parts of the codebase (Python services, build scripts, etc.).
# Documented case-by-case so the L3 orphan check doesn't false-flag them.
EXTERNAL_USE_KEYS: dict = {
    "JAMENDO_CLIENT_ID": "Used by video_marketing_app/app.py for Jamendo music search",
    "PEXELS_API_KEY":    "Used by video_marketing_app/app.py for Pexels stock video",
}

# Common env vars that may legitimately be optional / set per-environment.
# When missing, the function should branch gracefully (CORS fallback to *,
# feature disabled banner, etc.). Documented case-by-case.
OPTIONAL_VARS: dict = {
    "ALLOWED_ORIGIN": "CORS allowlist; falls back to '*' when unset (dev)",
    "STRIPE_SECRET_KEY": "Marketplace contact-only mode runs without it; payments require it",
    "STRIPE_WEBHOOK_SECRET": "Same — webhooks rejected without it but marketplace works in contact-only",
    "RESEND_API_KEY": "Email sends silently noop without it; report-sender shows 'email not configured'",
    "GEMINI_API_KEY": "AI fallback chain — Groq is primary; Gemini only used if explicitly configured",
    "AZURE_SPEECH_KEY": "Persona Contract Phase 7 TTS — tts-speak returns 500 when unset; wh-tts.js client falls back to browser SpeechSynthesis. Set in cloud secrets only (Azure F0 free tier).",
    "AZURE_SPEECH_REGION": "Persona Contract Phase 7 TTS — defaults to 'southeastasia' when unset; co-required with AZURE_SPEECH_KEY for the Azure path.",
    "AZURE_DOC_INTELLIGENCE_ENDPOINT": "Equipment-label-ocr (Azure Day 3) — function returns `azure_not_configured` envelope when unset, caller falls back to manual asset entry. Set in cloud secrets only.",
    "AZURE_DOC_INTELLIGENCE_KEY": "Equipment-label-ocr companion to AZURE_DOC_INTELLIGENCE_ENDPOINT; same graceful-fallback path when missing.",
    "WH_RATE_LIMIT_OVERRIDE": "RAG Flywheel rate-limit knob (agentic-rag-loop). Falls back to compiled default (50 prod / 300 dev) when unset; only set during multi-turn synthetic walks to lift the in-process token bucket.",
    "WH_RATE_LIMIT_RESET": "RAG Flywheel rate-limit reset flag (agentic-rag-loop). When set to '1' on a single request, clears the in-process token bucket; absent means bucket persists across requests. Pure dev/test knob.",
    "WH_USER_RATE_LIMIT_OVERRIDE": "P1 roadmap 2026-05-26: per-user soft cap inside the per-hive rate-limit bucket (_shared/rate-limit.ts checkUserRateLimit). Falls back to compiled default 25 when unset.",
    "WH_LOG_LEVEL": "P1 roadmap 2026-05-26: structured-logger threshold (_shared/logger.ts). Values: debug | info | warn | error. Falls back to 'info' when unset.",
    "WH_VOICE_QUOTA_RATIO": "P1 roadmap 2026-05-27 turn 7: voice quota share inside the per-hive rate-limit bucket (_shared/rate-limit.ts checkClassedRateLimit). 0.0-1.0; falls back to 0.7 when unset.",
}

# API-key-prefix patterns that indicate a real secret. The trailing length
# requirement keeps short identifier strings out of the false-positive net.
SECRET_PATTERNS: list = [
    (r"\bsk_live_[A-Za-z0-9]{20,}",                     "Stripe LIVE secret key"),
    (r"\bsk_test_[A-Za-z0-9]{20,}",                     "Stripe TEST secret key"),
    (r"\bgsk_[A-Za-z0-9]{30,}",                         "Groq API key"),
    (r"\bcsk-[A-Za-z0-9]{30,}",                         "Cerebras API key"),
    (r"\bpa-[A-Za-z0-9_-]{30,}",                        "Voyage API key"),
    (r"\bjina_[A-Za-z0-9]{30,}",                        "Jina API key"),
    (r"\bsk-or-v1-[A-Za-z0-9]{30,}",                    "OpenRouter API key"),
    (r"\bre_[A-Za-z0-9]{30,}",                          "Resend API key"),
    (r"\beyJ[A-Za-z0-9_-]{40,}\.[A-Za-z0-9_-]{40,}\.",  "JWT (likely Supabase service-role or signed token)"),
]


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _list_function_source_files() -> list[str]:
    """All .ts files under supabase/functions/ (including _shared/)."""
    out: list[str] = []
    if not os.path.isdir(FUNCTIONS_DIR):
        return out
    for root, _dirs, files in os.walk(FUNCTIONS_DIR):
        for fname in files:
            if not fname.endswith(".ts"):
                continue
            out.append(os.path.join(root, fname))
    return out


def _parse_env_keys() -> set[str]:
    """Returns the set of keys declared in supabase/functions/.env (active,
    non-commented lines only). Comments use `#`."""
    out: set[str] = set()
    src = _read(ENV_FILE)
    if not src:
        return out
    for raw in src.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if re.fullmatch(r"[A-Z_][A-Z0-9_]*", key):
            out.add(key)
    return out


# ─── Env reference extraction ────────────────────────────────────────────────

# Direct: Deno.env.get('FOO') / get("FOO") / get(`FOO`)
DIRECT_RE = re.compile(r"""Deno\.env\.get\(\s*['"`]([A-Z_][A-Z0-9_]*)['"`]\s*\)""")
# Indirect: envKey: 'FOO' (used by ai-chain.ts and similar provider configs)
INDIRECT_RE = re.compile(r"""envKey\s*:\s*['"`]([A-Z_][A-Z0-9_]*)['"`]""")
# Required marker: get('FOO')! (TypeScript non-null assertion)
REQUIRED_RE = re.compile(r"""Deno\.env\.get\(\s*['"`]([A-Z_][A-Z0-9_]*)['"`]\s*\)\s*!""")


def _collect_env_references() -> dict:
    """Returns:
        references: {var_name: [(file, line)]}  — every read site
        required:   set of var names that have a `!` assertion somewhere
    """
    references: dict[str, list[tuple[str, int]]] = defaultdict(list)
    required: set[str] = set()
    for path in _list_function_source_files():
        src = _read(path)
        if not src:
            continue
        rel = os.path.relpath(path, ROOT)
        for m in DIRECT_RE.finditer(src):
            line = src[:m.start()].count("\n") + 1
            references[m.group(1)].append((rel, line))
        for m in INDIRECT_RE.finditer(src):
            line = src[:m.start()].count("\n") + 1
            references[m.group(1)].append((rel, line))
        for m in REQUIRED_RE.finditer(src):
            required.add(m.group(1))
    return {"references": references, "required": required}


# ─── Layer checks ────────────────────────────────────────────────────────────

def check_declared_coverage(refs: dict, env_keys: set[str]) -> list[dict]:
    issues: list[dict] = []
    declared = env_keys | BUILT_IN_SUPABASE_VARS | set(OPTIONAL_VARS)
    for var, sites in sorted(refs["references"].items()):
        if var in declared:
            continue
        site_str = "; ".join(f"{p}:{ln}" for p, ln in sites[:3])
        more = f" (and {len(sites)-3} more)" if len(sites) > 3 else ""
        issues.append({
            "check":  "env_var_declared",
            "var":    var,
            "sites":  [{"file": p, "line": ln} for p, ln in sites],
            "reason": (
                f"Env var '{var}' is referenced by edge fn(s) ({site_str}{more}) "
                f"but is NOT in supabase/functions/.env, NOT a Supabase built-in, "
                f"and NOT in OPTIONAL_VARS allowlist. Function will read undefined "
                f"and fail (500 / 401 / wrong result). Either add `{var}=...` to "
                f".env, or add to OPTIONAL_VARS with the graceful-fallback behavior."
            ),
        })
    return issues


def check_required_coverage(refs: dict, env_keys: set[str]) -> list[dict]:
    """A var with a `!` assertion is the function declaring it MUST exist —
    if it's missing AND not feature-gated as optional, the assertion will
    throw at runtime. Two severity bands:
      - FAIL: not in .env / built-ins / OPTIONAL_VARS — function will throw.
      - WARN: in OPTIONAL_VARS — feature is gated off elsewhere (e.g.,
        STRIPE_SECRET_KEY for contact-only marketplace), function won't
        actually be invoked yet, but the moment the gate flips the var
        MUST be set or the function 500s. Tracked as a pre-flight
        checklist item.
    """
    issues: list[dict] = []
    declared = env_keys | BUILT_IN_SUPABASE_VARS
    for var in sorted(refs["required"]):
        if var in declared:
            continue
        if var in OPTIONAL_VARS:
            issues.append({
                "check":  "env_var_required_declared", "skip": True,
                "var":    var,
                "reason": (
                    f"Env var '{var}' uses `!` assertion in function code "
                    f"(declared required) but is NOT in .env. Currently safe "
                    f"because OPTIONAL_VARS marks it as feature-gated "
                    f"({OPTIONAL_VARS[var]}). The moment the gating feature "
                    f"enables, '{var}' MUST be set or the function will throw. "
                    f"Pre-flight checklist item."
                ),
            })
            continue
        issues.append({
            "check":  "env_var_required_declared",
            "var":    var,
            "reason": (
                f"Env var '{var}' is read with a `!` assertion (function "
                f"requires it to exist), but is NOT in .env or Supabase "
                f"built-ins. The function will throw `TypeError: cannot read "
                f"properties of null (reading ...)` on first invocation. Add "
                f"`{var}=...` to .env immediately."
            ),
        })
    return issues


def check_orphan_env_keys(refs: dict, env_keys: set[str]) -> list[dict]:
    """Keys in .env that no edge function references. Often residue from
    removed features. Not breakage but worth cleaning to avoid leak risk
    + developer confusion."""
    issues: list[dict] = []
    referenced = set(refs["references"].keys())
    for key in sorted(env_keys):
        if key in referenced:
            continue
        if key in EXTERNAL_USE_KEYS:
            continue  # intentionally consumed outside supabase/functions/
        issues.append({
            "check":  "env_key_orphan", "skip": True,
            "var":    key,
            "reason": (
                f"Env var '{key}' is declared in .env but no edge function "
                f"reads it (no Deno.env.get('{key}') or envKey:'{key}' anywhere "
                f"under supabase/functions/). Likely residue from a removed "
                f"feature. Remove from .env to reduce leak risk + developer "
                f"confusion. If consumed elsewhere (Python, build scripts), "
                f"add to EXTERNAL_USE_KEYS with a justification."
            ),
        })
    return issues


def check_hardcoded_secrets() -> list[dict]:
    """Scan source files (NOT .env itself) for strings that look like real
    API keys. If a developer pasted a Stripe key into a fetch call instead
    of using Deno.env.get, that's a security incident."""
    issues: list[dict] = []
    for path in _list_function_source_files():
        src = _read(path)
        if not src:
            continue
        rel = os.path.relpath(path, ROOT)
        for pattern, kind in SECRET_PATTERNS:
            for m in re.finditer(pattern, src):
                line = src[:m.start()].count("\n") + 1
                # Skip if the match is inside a comment (// or */)
                line_start = src.rfind("\n", 0, m.start()) + 1
                line_text = src[line_start: src.find("\n", m.start())]
                if line_text.lstrip().startswith("//") or line_text.lstrip().startswith("*"):
                    continue
                issues.append({
                    "check":  "hardcoded_secret_in_source",
                    "file":   rel, "line": line, "kind": kind,
                    "match":  m.group(0)[:12] + "..." + m.group(0)[-4:],
                    "reason": (
                        f"{rel}:{line} contains what looks like a {kind} "
                        f"(matches '{m.group(0)[:12]}...{m.group(0)[-4:]}'). "
                        f"Hardcoded secrets in source are a security incident — "
                        f"the value is in git history forever. Move to "
                        f"supabase/functions/.env and use Deno.env.get('NAME')."
                    ),
                })
    return issues


# ─── Runner ────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    "env_var_declared",
    "env_var_required_declared",
    "env_key_orphan",
    "hardcoded_secret_in_source",
]
CHECK_LABELS = {
    "env_var_declared":            "L1  Every Deno.env.get('FOO') is declared in .env, built-ins, or OPTIONAL_VARS",
    "env_var_required_declared":   "L2  Every `!` -asserted env var is in .env or built-ins",
    "env_key_orphan":              "L3  Every key in .env is referenced by at least one edge function  [WARN]",
    "hardcoded_secret_in_source":  "L4  No real-looking API keys hardcoded in source (must use Deno.env.get)",
}


def main() -> None:
    def bold(s: str) -> str:
        return f"\033[1m{s}\033[0m"
    print(bold("\nEnv Secret Coverage Validator (4-layer)"))
    print("=" * 60)

    env_keys = _parse_env_keys()
    refs = _collect_env_references()
    print(f"  {len(env_keys)} keys in .env, {len(refs['references'])} unique env vars "
          f"referenced, {len(refs['required'])} marked required (`!` assertion).\n")

    all_issues: list[dict] = []
    all_issues += check_declared_coverage(refs, env_keys)
    all_issues += check_required_coverage(refs, env_keys)
    all_issues += check_orphan_env_keys(refs, env_keys)
    all_issues += check_hardcoded_secrets()

    by_check: dict = defaultdict(list)
    for i in all_issues:
        by_check[i["check"]].append(i)

    n_pass = n_warn = n_fail = 0
    for name in CHECK_NAMES:
        items = by_check.get(name, [])
        warns = [i for i in items if i.get("skip")]
        fails = [i for i in items if not i.get("skip")]
        label = CHECK_LABELS[name]
        if not items:
            print(f"  \033[92mPASS\033[0m  {label}")
            n_pass += 1
        elif not fails:
            print(f"  \033[93mSKIP\033[0m  {label}")
            n_warn += 1
        else:
            print(f"  \033[91mFAIL\033[0m  {label}")
            n_fail += 1

    if all_issues:
        print(f"\n\033[91mIssues:\033[0m")
        for i in all_issues:
            tag = "\033[93mSKIP\033[0m" if i.get("skip") else "\033[91mFAIL\033[0m"
            print(f"  [{tag}] [{i['check']}]  {i['reason']}")

    print(f"\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL")

    report = {
        "validator":       "env_secret_coverage",
        "env_keys":        sorted(env_keys),
        "referenced_vars": sorted(refs["references"].keys()),
        "required_vars":   sorted(refs["required"]),
        "summary":         {"pass": n_pass, "warn": n_warn, "fail": n_fail},
        "issues":          [i for i in all_issues if not i.get("skip")],
        "warnings":        [i for i in all_issues if i.get("skip")],
    }
    out = os.path.join(ROOT, "env_secret_coverage_report.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
