#!/usr/bin/env python3
# DEEPWALK-CELL: * D12P
"""
validate_rate_limit_handling.py - PER_PAGE SaaS-LAYER · Layer RL (Rate Limiting), 2026-07-22.
==============================================================================================
METHOD LAW (§0.4b): a page's AI/edge call that gets rate-limited (server `checkAIRateLimit` → structured
429) must show the user a SCOPE-CORRECT message ("you hit the rate limit, wait"), not a raw error or a
generic "failed". The mapping is ONE central helper — `window.whAiError(err, fallback)` in utils.js — so
this gate verifies ADOPTION of the central path, not a bespoke 429 check per page.

THE RULE: every page that INVOKES a rate-limited AI/edge fn (ai-gateway / *-orchestrator / *-assist /
voice-* / semantic-search / asset-brain / agentic-rag) must handle a 429 in its call path, via EITHER:
  * `whAiError(...)` — the central mapper (preferred, method-law), OR
  * an inline 429 / rate-limit / Retry-After check (a page that already handled it before the central
    helper existed — grandfathered, still correct).
A page that invokes AI but does NEITHER shows a raw/confusing error when the hive's AI budget is spent =
the RL per-page gap. Server-side resilience (429 → graceful) is separately gated by
`perf_l5_llm_resilience`; the companion widget's own 429 UX is central in companion-launcher.js.

Static + fast. Forward-only. `--selftest` proves teeth.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"
CHECK_NAMES = ["validate_rate_limit_handling"]
REPO = Path(__file__).resolve().parent.parent
EXCLUDE = ("node_modules", "remotion", "-test.", ".backup", "test-data-seeder")
# a rate-limited AI/edge fn invoked from the page (server-side checkAIRateLimit applies to these)
AI_INVOKE = re.compile(
    r"functions\.invoke\(\s*['\"]([a-z-]+)['\"]|/functions/v1/([a-z-]+)")
AI_FN = re.compile(r"ai-gateway|ai-orchestrator|agentic-rag|analytics-orchestrator|shift-planner|"
                   r"asset-brain|project-orchestrator|semantic-search|voice-|listing-assist|-assist|"
                   r"marketplace-listing|benchmark-compute")
# 429 handled: the central mapper OR an inline rate-limit check
HANDLED = re.compile(r"whAiError\s*\(|\b429\b|rate.?limit|too many|Retry-After|quota", re.I)
# BEST-EFFORT silent-degrade AI: the invoke is fire-and-forget (a 429 keeps the stored fallback, no raw
# error surfaced) — graceful by design, no user-facing 429 gap. Documented exemptions (verified live).
EXEMPT = {
    "alert-hub.html": "analytics-orchestrator action-brief is best-effort (empty-catch-allow) — a 429 keeps the stored amc_briefings.brief fallback, never surfaces a raw error",
}


def ai_pages() -> dict:
    out = {}
    for p in sorted(REPO.glob("*.html")):
        if any(x in p.name for x in EXCLUDE) or p.name in EXEMPT:
            continue
        src = p.read_text(encoding="utf-8", errors="ignore")
        fns = {(m.group(1) or m.group(2)) for m in AI_INVOKE.finditer(src)}
        ai = sorted(f for f in fns if f and AI_FN.search(f))
        if ai:
            out[p.name] = (ai, bool(HANDLED.search(src)))
    return out


def self_test() -> bool:
    ok = True
    if not AI_FN.search("ai-gateway"):
        print(f"{R}self-test FAIL: AI_FN misses ai-gateway.{X}"); ok = False
    if not HANDLED.search("showToast(whAiError(e, 'AI failed'))"):
        print(f"{R}self-test FAIL: HANDLED misses whAiError.{X}"); ok = False
    if not HANDLED.search("if (err.message.includes('429'))"):
        print(f"{R}self-test FAIL: HANDLED misses an inline 429 check.{X}"); ok = False
    if HANDLED.search("showToast('saved')"):
        print(f"{R}self-test FAIL: HANDLED false-matched a non-429 line.{X}"); ok = False
    print((G + "self-test PASS - rate-limit-handling check has teeth." + X) if ok else (R + "self-test FAILED." + X))
    return ok


def _emit_deepwalk_pages(dim: str, page_stems, all_pass: bool):
    """Emit this gate's EXACT per-page coverage for the deepwalk flywheel (PER_PAGE_ARCHITECTURAL_LAYER
    §4). The flywheel reads deepwalk_layer_pages.json to score the <dim> cell ONLY on the pages this gate
    actually covers (its dynamic invoke-detected scope) — never a regex approximation that over-matches a
    name-mention. Shared file: each layer gate contributes its own dim key. Best-effort (never fails main)."""
    import json
    f = REPO / "deepwalk_layer_pages.json"
    try:
        data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    data[dim] = {"pages": sorted(set(page_stems)), "pass": bool(all_pass)}
    try:
        f.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
    except Exception:
        pass


def main() -> int:
    if "--selftest" in sys.argv or "--self-test" in sys.argv:
        return 0 if self_test() else 1
    pages = ai_pages()
    missing = [(n, ai) for n, (ai, handled) in pages.items() if not handled]
    # Publish the exact AI-invoking page set for the deepwalk flywheel. Both the RL cell (D12P: does the
    # page handle 429) and the C cell (CP: does the page route AI through the gateway) apply to the SAME
    # AI-invoking pages — so this one authoritative invoke-detected set scopes both (each has its own
    # oracle: rate-limit-handling for D12P, no-ai-gateway-bypass for CP).
    _stems = [n[:-5] for n in pages]
    _emit_deepwalk_pages("D12P", _stems, not missing)
    _emit_deepwalk_pages("CP", _stems, not missing)
    print(f"{B}RL rate-limit handling — every AI-invoking page must handle 429 (whAiError or inline) ({len(pages)} AI pages){X}")
    for n, ai in missing:
        print(f"  {R}○{X} {n}: invokes {','.join(ai)[:44]} but has NO 429 handling — a rate-limited user gets a raw error. Use whAiError(err,'…').")
    if missing:
        print(f"{R}FAIL: {len(missing)} AI-invoking page(s) don't handle a 429. Adopt the central whAiError mapper.{X}")
        return 1
    print(f"{G}PASS - all {len(pages)} AI-invoking pages handle a 429 (central whAiError or inline check).{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
