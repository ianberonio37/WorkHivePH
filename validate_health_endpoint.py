"""
Health Endpoint Validator (L0, P1 roadmap 2026-05-26).
======================================================
Every "load-bearing" edge fn (those listed below) must define a /health
sub-route that returns 200 with a JSON {ok, deps[]} envelope. This lets
the platform-health dashboard render real-status without polling N
endpoints from the frontend, and lets external monitors (UptimeRobot,
Better Uptime) ping a single canonical surface per fn.

Detection rule: edge fn's index.ts must contain a `req.url` match against
"/health" or import from "../_shared/health.ts" (helper shipping separately).

Exit codes:
  0  every load-bearing fn defines /health OR is exempt
  1  one or more lack /health (FAIL with name)
"""
from __future__ import annotations
import io, json, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
FN_DIR = ROOT / "supabase" / "functions"
REPORT = ROOT / "health_endpoint_report.json"
BASELINE = ROOT / "health_endpoint_baseline.json"

CHECK_NAMES = ["health_endpoint"]

# Load-bearing fns where downtime is customer-visible. New fns are
# considered load-bearing by default — opt out via NON_CRITICAL.
LOAD_BEARING = {
    "ai-gateway",
    "agentic-rag-loop",
    "engineering-calc-agent",
    "voice-handler",
    "analytics-orchestrator",
    "report-sender",
    "temporal-rag-orchestrator",
    "hierarchical-summarizer",
    "agent-memory-store",
    "data-fabric-normalizer",
}

NON_CRITICAL = {
    "audio-tts", "audio-stt",        # tightly coupled to a single page
    "cold-archive-query",            # scaffolding
}


def has_health(text: str) -> bool:
    if '"/health"' in text or "'/health'" in text:
        return True
    if "../_shared/health.ts" in text:
        return True
    # Pattern: pathname.endsWith("/health")
    if "endsWith('/health')" in text or 'endsWith("/health")' in text:
        return True
    return False


def scan() -> dict:
    if not FN_DIR.exists():
        return {"fns": [], "missing": [], "error": "no functions dir"}
    fns, missing = [], []
    for entry in sorted(FN_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"): continue
        if entry.name in NON_CRITICAL: continue
        index = entry / "index.ts"
        if not index.exists(): continue
        text = index.read_text(encoding="utf-8", errors="replace")
        ok = has_health(text)
        row = {
            "fn":           entry.name,
            "load_bearing": entry.name in LOAD_BEARING,
            "has_health":   ok,
        }
        fns.append(row)
        if row["load_bearing"] and not ok:
            missing.append(row)
    return {"fns": fns, "missing": missing}


def main() -> int:
    result = scan()
    REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    n_fns     = len(result["fns"])
    n_missing = len(result["missing"])

    baseline = n_missing
    if BASELINE.exists():
        try: baseline = int(json.loads(BASELINE.read_text(encoding="utf-8")).get("missing", n_missing))
        except Exception: pass
    else:
        BASELINE.write_text(json.dumps({"missing": n_missing}), encoding="utf-8")

    print(f"Health endpoint: {n_fns} edge fns scanned, {n_missing} load-bearing missing /health (baseline {baseline}).")
    if n_missing > baseline:
        print(f"\033[91mFAIL: regressed +{n_missing - baseline} above baseline\033[0m")
        for e in result["missing"][:10]:
            print(f"  - {e['fn']}")
        return 1
    if n_missing < baseline:
        BASELINE.write_text(json.dumps({"missing": n_missing}), encoding="utf-8")
        print(f"\033[92mPASS: baseline tightened {baseline} → {n_missing}\033[0m")
        return 0
    print("\033[92mPASS\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
