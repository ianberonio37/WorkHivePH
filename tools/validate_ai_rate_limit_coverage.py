#!/usr/bin/env python3
"""validate_ai_rate_limit_coverage.py — Arc H H7/I: every frontend-direct AI fn must rate-limit (LLM10).

OWASP LLM10 Unbounded Consumption: an LLM-invoking edge function that the FRONTEND calls DIRECTLY (not via
ai-gateway, which rate-limits upstream) and that has NO rate-limit check lets any user spam expensive model
calls — cost-drain / DoS. Arc H H0 measured rate-limit at 50% of AI edge fns; triage showed the real gap was
5 frontend-direct fns (ai-orchestrator, engineering-calc-agent, intelligence-report, voice-transcribe,
voice-semantic-rag) — now fixed with checkAIRateLimit / checkUserRateLimit / checkSoloRateLimit.

RULE: an edge fn that (a) makes an LLM/ASR call AND (b) is invoked directly from the frontend
(`functions.invoke('<fn>')` or `/functions/v1/<fn>` in any .html/.js) must contain a rate-limit check.
Gateway-fronted fns (called only by ai-gateway) are exempt — the gateway rate-limits. Baseline 0.

USAGE:      python tools/validate_ai_rate_limit_coverage.py
Self-test:  python tools/validate_ai_rate_limit_coverage.py --self-test
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FUNCS = ROOT / "supabase" / "functions"
GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"; RST = "\033[0m"

LLM_MARKERS = re.compile(r"callAI|callGroq|ai-chain|transcribeAudio|audio-chain|generateContent|chat/completions|/calculate\b|generateNarrative|generateReportNarrative", re.I)
# shared helpers OR an inline limiter (a local checkRateLimit fn / direct ai_rate_limits counter access —
# e.g. agentic-rag-loop rolls its own per-hive limiter; credit the PATTERN, not just the shared name).
RL_MARKERS = re.compile(r"checkAIRateLimit|checkUserRateLimit|checkSoloRateLimit|checkRouteRateLimit|checkRateLimit\s*\(|ai_rate_limits", re.I)

# Frontend-direct LLM fns that legitimately need NO own RL (evidence-curated). Empty = none yet.
EXEMPT: dict[str, str] = {}


def _comment_stripped(body: str) -> str:
    return re.sub(r"//.*", "", body)


def frontend_invokes(fn: str) -> list[str]:
    """Files (.html/.js) that invoke this edge fn DIRECTLY."""
    hits = []
    pat = re.compile(rf"functions\.invoke\(['\"]{re.escape(fn)}['\"]|/functions/v1/{re.escape(fn)}\b")
    for p in list(ROOT.glob("*.html")) + list(ROOT.glob("*.js")):
        try:
            if pat.search(p.read_text(encoding="utf-8", errors="replace")):
                hits.append(p.name)
        except Exception:
            continue
    return hits


def scan():
    findings, ok, exempt, gateway_fronted = [], [], [], []
    for d in sorted(FUNCS.iterdir()):
        if not d.is_dir() or d.name == "_shared":
            continue
        idx = d / "index.ts"
        if not idx.exists():
            continue
        body = idx.read_text(encoding="utf-8", errors="replace")
        nc = _comment_stripped(body)
        if not LLM_MARKERS.search(nc):
            continue  # not an LLM/ASR surface
        fe = frontend_invokes(d.name)
        has_rl = bool(RL_MARKERS.search(nc))
        if not fe:
            gateway_fronted.append(d.name)  # not frontend-direct -> gateway/edge/cron-fronted (RL upstream)
            continue
        if d.name in EXEMPT:
            exempt.append((d.name, EXEMPT[d.name])); continue
        if has_rl:
            ok.append(d.name)
        else:
            findings.append((d.name, fe))
    return findings, ok, exempt, gateway_fronted


def main() -> int:
    self_test = "--self-test" in sys.argv[1:]
    findings, ok, exempt, gw = scan()

    print("=" * 74)
    print("  Arc H H7/I — AI rate-limit coverage (frontend-direct LLM fns must limit; LLM10)")
    print("=" * 74)
    print(f"  frontend-direct LLM fns rate-limited: {len(ok)} · gateway-fronted (RL upstream): {len(gw)} · exempt: {len(exempt)}")
    for n in ok:
        print(f"    {GREEN}ok{RST}   {n} (rate-limited)")

    if self_test:
        # teeth: a synthetic frontend-direct LLM fn with no RL must be caught by the logic
        synth_ok = ("callAI" and not RL_MARKERS.search("const x = callAI()")) and bool(LLM_MARKERS.search("callAI"))
        print(f"\n  TEETH [{GREEN+'PASS'+RST if synth_ok else RED+'FAIL'+RST}] an LLM fn body with no rate-limit marker is detectable")
        if not synth_ok:
            return 1

    print()
    if findings:
        for n, fe in findings:
            print(f"  {RED}FAIL{RST}  {n} — LLM fn called DIRECTLY by {', '.join(fe)} with NO rate-limit (LLM10 unbounded consumption)")
        print(f"\n  {RED}{len(findings)} frontend-direct LLM fn(s) without a rate-limit{RST} (baseline 0)")
        return 1
    print(f"  {GREEN}PASS{RST} — every frontend-direct LLM fn rate-limits; gateway-fronted fns limited upstream")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
