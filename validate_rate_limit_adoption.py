"""
Rate-Limit Adoption Validator (L0, P1 roadmap 2026-05-27).
============================================================
Closes the (RL, G0) cell from COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4.

Every edge fn that calls `callAI()` (i.e. burns paid-or-free LLM tokens)
must also call ONE of:
  - checkAIRateLimit()        (per-hive bucket, existing helper)
  - checkUserRateLimit()      (per-hive + per-user, P1 helper)
  - checkRouteRateLimit()     (per-(hive, route))
  - checkSoloRateLimit()      (per-identity, no-hive solo/personal features)

Without one of these, a single noisy hive or worker can drain the entire
free-tier quota in seconds. Adoption is what makes the helper real;
without this validator, helpers exist on paper only.

Exit codes:
  0  every callAI-using fn calls a rate-limit helper OR is exempt
  1  one or more callAI fns lack rate-limit gating (baseline-ratcheted)
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
FN_DIR = ROOT / "supabase" / "functions"
REPORT = ROOT / "rate_limit_adoption_report.json"
BASELINE = ROOT / "rate_limit_adoption_baseline.json"

CHECK_NAMES = ["rate_limit_adoption"]

CALLAI_RE = re.compile(r"\bcallAI\s*\(")
GATE_RE   = re.compile(r"\bcheck(AIRateLimit|UserRateLimit|RouteRateLimit|SoloRateLimit)\s*\(")

# Exempt: fns that ARE the rate-limit helper itself, or that don't actually
# burn LLM tokens despite importing the chain (e.g. utilities).
EXEMPT = {
    # _shared and _audit are not deployed as fns
    "scheduled-agents",       # internal scheduler; runs as service role; no hive context
    "trigger-ml-retrain",     # batch trigger; no per-call cost
    "cron-runner",            # internal
    "semantic-fact-extractor",# pg_cron batch extractor; self-caps fan-out (MAX_GROUPS=6); no per-user request path
}


def scan() -> dict:
    if not FN_DIR.exists():
        return {"fns": [], "missing": [], "error": "no functions dir"}
    fns, missing = [], []
    for entry in sorted(FN_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"): continue
        if entry.name in EXEMPT: continue
        index = entry / "index.ts"
        if not index.exists(): continue
        text = index.read_text(encoding="utf-8", errors="replace")
        calls_callai = bool(CALLAI_RE.search(text))
        has_gate     = bool(GATE_RE.search(text))
        row = {
            "fn":          entry.name,
            "calls_callai": calls_callai,
            "has_gate":    has_gate,
        }
        fns.append(row)
        if calls_callai and not has_gate:
            missing.append(row)
    return {"fns": fns, "missing": missing}


def main() -> int:
    result = scan()
    REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    n_fns     = len(result["fns"])
    n_calls   = sum(1 for f in result["fns"] if f.get("calls_callai"))
    n_missing = len(result["missing"])

    baseline = n_missing
    if BASELINE.exists():
        try: baseline = int(json.loads(BASELINE.read_text(encoding="utf-8")).get("missing", n_missing))
        except Exception: pass
    else:
        BASELINE.write_text(json.dumps({"missing": n_missing}), encoding="utf-8")

    print(f"Rate-limit adoption: {n_calls} fns call callAI, {n_missing} missing rate-limit gate (baseline {baseline}).")
    if n_missing > baseline:
        print(f"\033[91mFAIL: regressed +{n_missing - baseline} above baseline\033[0m")
        for r in result["missing"][:10]:
            print(f"  - {r['fn']}")
        return 1
    if n_missing < baseline:
        BASELINE.write_text(json.dumps({"missing": n_missing}), encoding="utf-8")
        print(f"\033[92mPASS: baseline tightened {baseline} → {n_missing}\033[0m")
        return 0
    print("\033[92mPASS\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
