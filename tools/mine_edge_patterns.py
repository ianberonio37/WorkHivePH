"""
Edge-Function Pattern Miner -- WorkHive Platform
================================================
Mines `supabase/functions/<name>/index.ts` for emergent structural patterns
and flags outliers. This is the L-1 "Convention Mining" layer that feeds
candidate rules into Layer 0 (the 160+ explicit validators).

How it differs from existing validators:
  - Existing validators enforce rules you already wrote down.
  - This script discovers rules that the codebase already follows but
    nobody ever codified.

Workflow:
  1. Walk all supabase/functions/*/index.ts (skip _shared).
  2. For each fn, extract a structural feature vector (regex/text scan).
  3. Compute conformance % per feature.
  4. Surface features in the "promotion sweet spot": >= 80% conformance
     with <= 6 outliers. Those are candidates for real validators.
  5. Write tools/edge_pattern_mining_report.{json,md}.

Output is PROPOSALS, not gate failures. Human reviews each, then either:
  (a) writes a strict Layer 0 validator from the outlier list, or
  (b) allowlists the outliers as legit exceptions.

Skills consulted: architect (single-entry-point pattern, structural drift),
performance (cold-start memoization), security (CORS / auth-binding /
PII hygiene), devops (deploy / env / observability), ai-engineer (callAI
routing, rate-limit gating).
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent.parent
FN_ROOT = ROOT / "supabase" / "functions"

# Promotion thresholds.
PROMOTE_MIN_CONFORMANCE = 0.80   # >= 80% of fns conform
PROMOTE_MAX_OUTLIERS    = 6      # but no more than this many divergent fns


# ---------------------------------------------------------------------------
# Feature extractors.  Each takes (text, fn_name) -> bool.
# Name them in present-tense rule form: "has X", "uses Y", "calls Z".
# ---------------------------------------------------------------------------

def _strip_comments(text: str) -> str:
    """Strip // line comments and /* ... */ block comments so regexes don't
    fire on documentation. JSDoc above imports often *describes* a pattern
    in prose while the code itself doesn't follow it."""
    out = re.sub(r"/\*[\s\S]*?\*/", "", text)
    out = re.sub(r"^\s*//.*$", "", out, flags=re.MULTILINE)
    return out


def extract_features(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8", errors="replace")
    code = _strip_comments(raw)
    fn_name = path.parent.name
    lines = raw.splitlines()
    nloc = len([ln for ln in lines if ln.strip() and not ln.strip().startswith("//")])

    features: dict = {"fn": fn_name, "nloc": nloc}

    # ---- imports -----------------------------------------------------------
    features["imports_serve_std"]      = bool(re.search(r"""import\s*\{\s*serve\s*\}\s*from\s*["']https://deno\.land/std""", code))
    features["imports_cors_shared"]    = bool(re.search(r"""from\s+["']\.\./_shared/cors\.ts["']""", code))
    features["imports_supabase_esm"]   = bool(re.search(r"""from\s+["']https://esm\.sh/@supabase/supabase-js""", code))
    features["imports_ai_chain"]       = bool(re.search(r"""from\s+["']\.\./_shared/ai-chain\.ts""", code))
    features["imports_redact_pii"]     = bool(re.search(r"""from\s+["']\.\./_shared/redactPII\.ts""", code))
    features["imports_memory"]         = bool(re.search(r"""from\s+["']\.\./_shared/memory\.ts""", code))
    features["imports_rate_limit"]     = bool(re.search(r"""from\s+["']\.\./_shared/rate-limit\.ts""", code))
    features["imports_cost_log"]       = bool(re.search(r"""from\s+["']\.\./_shared/cost-log\.ts""", code))
    features["imports_validate_contract"] = bool(re.search(r"""from\s+["']\.\./_shared/validate-contract\.ts""", code))

    # ---- handler wrapper ---------------------------------------------------
    features["wraps_in_serve"]         = bool(re.search(r"\bserve\s*\(\s*async\s*\(", code))
    features["handles_options"]        = bool(re.search(r"""req\.method\s*===\s*["']OPTIONS["']""", code))
    features["uses_get_cors_headers"]  = bool(re.search(r"\bgetCorsHeaders\s*\(", code))

    # First non-blank statement inside `serve(async (req) => {` should be
    # the corsHeaders binding. Sample the first 5 logical statements after
    # the serve opener.
    serve_match = re.search(r"serve\s*\(\s*async\s*\([^)]*\)\s*=>\s*\{", code)
    cors_first = False
    if serve_match:
        head = code[serve_match.end(): serve_match.end() + 600]
        head_lines = [l.strip() for l in head.splitlines() if l.strip()]
        cors_first = any("getCorsHeaders" in l for l in head_lines[:3])
    features["cors_headers_first_in_handler"] = cors_first

    # ---- method gate -------------------------------------------------------
    features["rejects_wrong_method"]   = bool(re.search(r"""req\.method\s*!==\s*["'](POST|GET|PUT|PATCH|DELETE)["']""", code))

    # ---- error envelope ----------------------------------------------------
    # Body shape `{ error: ... }` somewhere
    features["uses_error_envelope"]    = bool(re.search(r"\{\s*error\s*:", code))
    # Content-Type: application/json on at least one response
    features["sets_content_type_json"] = bool(re.search(r"""Content-Type["']?\s*:\s*["']application/json""", code))

    # ---- try / catch -------------------------------------------------------
    # The codebase uses BOTH `catch (err)` and bare `catch {` (no error
    # binding, allowed since TS 4.0). Earlier miner version only matched the
    # first form, producing false-positives on the 5 marketplace fns that
    # use the bare form. Now matches either.
    features["has_try_catch"] = bool(
        re.search(r"\btry\s*\{", code)
        and re.search(r"\bcatch\s*[({]", code)
    )

    # Top-level handler try/catch -- the WHOLE serve() body is wrapped.
    # Stronger guarantee than "any try anywhere": catches the case where
    # only an inner `await req.json()` is wrapped but the rest of the
    # handler can still throw to a 500 with no error envelope.
    features["wraps_handler_in_try"] = _handler_body_wrapped_in_try(code, serve_match)

    # ---- logging -----------------------------------------------------------
    # console.error or console.warn that prefixes the fn name (helps grep prod logs)
    has_named_log = False
    for m in re.finditer(r"""console\.(error|warn)\s*\(\s*["']\[?([^"'\]]+)\]?""", code):
        if fn_name in m.group(2):
            has_named_log = True
            break
    features["logs_with_fn_name_prefix"] = has_named_log
    features["has_any_console_error"]    = bool(re.search(r"console\.error\s*\(", code))

    # ---- module-scope warm client (cold-start memoization adoption) --------
    # createClient(...) appearing before the first `serve(` opener at brace-depth 0.
    features["memoizes_supabase_client"] = _has_module_scope_create_client(code, serve_match)

    # ---- createClient inside handler (anti-pattern) ------------------------
    features["createclient_in_handler"]  = _has_create_client_inside_serve(code, serve_match)

    # ---- identity binding --------------------------------------------------
    features["binds_jwt_identity"]     = bool(re.search(r"""getUser\s*\(\s*\)""", code) or re.search(r"req\.headers\.get\(\s*['\"]Authorization", code))

    # ---- AI surface fingerprint --------------------------------------------
    features["calls_callai"]           = bool(re.search(r"\bcallAI\s*\(", code))

    # ---- header comments (capability tag + skills-consulted) --------------
    features["has_capability_tag"]     = bool(re.search(r"//\s*capability\s*:", raw))
    features["has_skills_consulted"]   = bool(re.search(r"[Ss]kills\s+consulted", raw))
    features["has_jsdoc_header"]       = raw.lstrip().startswith("/**") or raw.lstrip().startswith("/*")

    # ---- env var conventions ----------------------------------------------
    features["reads_supabase_url_env"] = bool(re.search(r"""Deno\.env\.get\(\s*["']SUPABASE_URL""", code))
    features["reads_service_role_env"] = bool(re.search(r"""Deno\.env\.get\(\s*["']SUPABASE_SERVICE_ROLE_KEY""", code))

    # ---- abort / timeout discipline ----------------------------------------
    # Two distinct disciplines:
    #   - AbortController: manual abort wiring (older Deno pattern)
    #   - AbortSignal.timeout(ms): one-line modern timeout (newer pattern)
    # Codebase has both; separating them surfaces the migration progress.
    features["uses_abort_controller"]   = bool(re.search(r"\bnew\s+AbortController\s*\(", code))
    features["uses_abortsignal_timeout"] = bool(re.search(r"AbortSignal\.timeout\s*\(", code))

    # ---- env-prefix discipline ---------------------------------------------
    # ai-gateway and analytics-orchestrator use a `_WH_` prefix on module-
    # scope env constants (e.g., `const _WH_SUPABASE_URL_M = ...`). This is
    # an emergent naming convention -- it makes module-scope warm-client
    # variables easy to grep and distinguish from per-request locals.
    features["uses_wh_env_prefix"] = bool(re.search(r"\bconst\s+_WH_[A-Z_]+\s*=", code))

    # ---- response-shape consistency ----------------------------------------
    # Canonical response shape in this codebase:
    #   new Response(JSON.stringify({...}), { status, headers: { ...corsHeaders, "Content-Type": "application/json" } })
    # Outliers either omit Content-Type or omit the spread of corsHeaders.
    features["responses_spread_cors_headers"] = bool(re.search(r"\.\.\.corsHeaders|\.\.\.getCorsHeaders\s*\(", code))

    # ---- input validation 400 ---------------------------------------------
    features["returns_400_on_bad_input"] = bool(re.search(r"status\s*:\s*400", code))

    # ---- file ends with `});` (single serve() at the bottom) --------------
    tail = "".join(lines[-3:]).strip()
    features["ends_with_serve_close"]  = tail.endswith("});") or tail.endswith("})")

    return features


def _has_module_scope_create_client(code: str, serve_match) -> bool:
    """Return True if there's a `createClient(...)` call before the first
    `serve(` opener at brace-depth 0 (module top level)."""
    if not serve_match:
        # No serve() wrapper at all; check anywhere at depth 0.
        cutoff = len(code)
    else:
        cutoff = serve_match.start()
    pre = code[:cutoff]
    depth = 0
    for m in re.finditer(r"[{}]|createClient\s*\(", pre):
        token = m.group(0)
        if token == "{":
            depth += 1
        elif token == "}":
            depth -= 1
        else:
            if depth == 0:
                return True
    return False


def _handler_body_wrapped_in_try(code: str, serve_match) -> bool:
    """Return True if the FIRST executable statement inside the serve()
    handler body is `try {`. Tolerates short prelude lines like the
    corsHeaders binding and the OPTIONS preflight return -- those don't
    need to be inside the try because they can't throw.

    Heuristic: scan the first ~25 non-blank/non-comment lines of the
    handler. If a `try {` appears before any await/return that touches
    request data, the whole handler is wrapped.
    """
    if not serve_match:
        return False
    body = code[serve_match.end():]
    # Look in the first ~1500 chars of the handler body.
    head = body[:1500]
    lines = [l.strip() for l in head.splitlines() if l.strip()]
    for ln in lines[:25]:
        if ln.startswith("try"):
            return True
        # Heavy operation before any try -- handler is NOT top-wrapped.
        if re.search(r"\bawait\s+req\.(json|formData|text|arrayBuffer)\b", ln):
            return False
        if re.search(r"\bawait\s+\w+\.(from|rpc|invoke|insert|update|select)\b", ln):
            return False
    return False


def _has_create_client_inside_serve(code: str, serve_match) -> bool:
    """Return True if there's a `createClient(...)` call inside the serve()
    handler body (brace-depth > 0 relative to the serve opener)."""
    if not serve_match:
        return False
    body = code[serve_match.end():]
    return bool(re.search(r"createClient\s*\(", body))


# ---------------------------------------------------------------------------
# Mining pipeline.
# ---------------------------------------------------------------------------

def mine() -> dict:
    fns = sorted([p for p in FN_ROOT.iterdir()
                  if p.is_dir() and p.name != "_shared" and (p / "index.ts").exists()])
    rows = [extract_features(p / "index.ts") for p in fns]

    feature_keys = [k for k in rows[0].keys() if k not in ("fn", "nloc")]

    # Per-feature conformance.
    conformance = {}
    for key in feature_keys:
        positive = [r for r in rows if r[key]]
        negative = [r for r in rows if not r[key]]
        pct = len(positive) / len(rows) if rows else 0
        conformance[key] = {
            "positive_count": len(positive),
            "negative_count": len(negative),
            "total":          len(rows),
            "conformance":    round(pct, 3),
            "outliers":       [r["fn"] for r in negative],
            "positives":      [r["fn"] for r in positive],
        }

    # Promotion candidates -- the sweet spot.
    proposals = []
    for key, data in conformance.items():
        # For "anti-pattern" features (createclient_in_handler), the rule
        # is "stays FALSE". Flip the lens.
        is_anti = key in {"createclient_in_handler"}
        if is_anti:
            rate_correct = 1 - data["conformance"]
            outliers = data["positives"]   # the ones doing it WRONG
        else:
            rate_correct = data["conformance"]
            outliers = data["outliers"]

        if rate_correct >= PROMOTE_MIN_CONFORMANCE and 0 < len(outliers) <= PROMOTE_MAX_OUTLIERS:
            proposals.append({
                "feature":        key,
                "anti_pattern":   is_anti,
                "conformance":    round(rate_correct, 3),
                "outlier_count":  len(outliers),
                "outliers":       outliers,
            })
    # Sort: closest-to-promotion first (highest conformance, fewest outliers).
    proposals.sort(key=lambda p: (-p["conformance"], p["outlier_count"]))

    return {
        "summary": {
            "fns_scanned":            len(rows),
            "features_extracted":     len(feature_keys),
            "promotion_candidates":   len(proposals),
        },
        "promote_threshold": {
            "min_conformance":  PROMOTE_MIN_CONFORMANCE,
            "max_outliers":     PROMOTE_MAX_OUTLIERS,
        },
        "proposals":   proposals,
        "conformance": conformance,
        "per_fn":      rows,
    }


def write_markdown(report: dict, out_path: Path) -> None:
    lines = []
    lines.append("# Edge-Function Pattern Mining Report")
    lines.append("")
    lines.append(f"- Functions scanned: **{report['summary']['fns_scanned']}**")
    lines.append(f"- Features extracted: **{report['summary']['features_extracted']}**")
    lines.append(f"- Promotion threshold: >= {int(PROMOTE_MIN_CONFORMANCE*100)}% conformance, <= {PROMOTE_MAX_OUTLIERS} outliers")
    lines.append(f"- Promotion candidates: **{report['summary']['promotion_candidates']}**")
    lines.append("")
    lines.append("## Promotion candidates (sweet spot)")
    lines.append("")
    lines.append("These are emergent patterns ready to graduate into Layer 0 validators.")
    lines.append("Review each: write a real validator from the outlier list, or allowlist them.")
    lines.append("")
    lines.append("| Feature | Type | Conformance | Outliers (divergent fns) |")
    lines.append("|---|---|---:|---|")
    for p in report["proposals"]:
        kind = "anti-pattern (stays FALSE)" if p["anti_pattern"] else "convention (stays TRUE)"
        lines.append(f"| `{p['feature']}` | {kind} | {int(p['conformance']*100)}% | {', '.join(p['outliers']) or '—'} |")
    lines.append("")
    lines.append("## Full conformance ranking")
    lines.append("")
    lines.append("| Feature | Conformance | Positive / Total |")
    lines.append("|---|---:|---|")
    ranked = sorted(report["conformance"].items(), key=lambda kv: -kv[1]["conformance"])
    for key, data in ranked:
        lines.append(f"| `{key}` | {int(data['conformance']*100)}% | {data['positive_count']} / {data['total']} |")
    lines.append("")
    lines.append("## How to act on this report")
    lines.append("")
    lines.append("1. Pick a promotion candidate.")
    lines.append("2. Look at the outlier fns -- are they legitimate exceptions or real bugs?")
    lines.append("3a. **Real rule, real bugs** -> write `validate_<rule>.py`, register in `run_platform_checks.py`, fix the outliers.")
    lines.append("3b. **Real rule, legit exceptions** -> write the validator with an allowlist of the outlier fns.")
    lines.append("3c. **Accidental pattern** -> drop it; not a real rule.")
    lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    report = mine()
    json_path = ROOT / "edge_pattern_mining_report.json"
    md_path   = ROOT / "edge_pattern_mining_report.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(report, md_path)

    print(f"Edge-Function Pattern Miner")
    print(f"  fns scanned:           {report['summary']['fns_scanned']}")
    print(f"  features extracted:    {report['summary']['features_extracted']}")
    print(f"  promotion candidates:  {report['summary']['promotion_candidates']}")
    print(f"  report (json):         {json_path.name}")
    print(f"  report (md):           {md_path.name}")
    print()
    print("Top 10 candidates (sweet spot):")
    for p in report["proposals"][:10]:
        kind = "anti" if p["anti_pattern"] else "conv"
        olist = ", ".join(p["outliers"][:5]) + (" ..." if len(p["outliers"]) > 5 else "")
        print(f"  [{kind}] {int(p['conformance']*100):>3}%  {p['feature']:<35} outliers: {olist}")


if __name__ == "__main__":
    main()
