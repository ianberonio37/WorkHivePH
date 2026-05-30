"""
Verified-State Wiring Validator (L0, ratcheted).
================================================
Memory-stack flywheel Turn 2 (layer 07 "Shared Memory"). Asserts the
conflict-resolution / verified-state surface over unified_events stays in place
and wired into the live gateway path.

unified_events had access-control + dedup but no conflict resolution: competing
events for the same asset coexisted and each agent could read a different
"truth". This flywheel added v_asset_state_truth (resolve by source trust
precedence then recency) + _shared/verified-state.ts + gateway injection. This
validator guards all three from silent regression.

Checks (each missing = a violation):
  1. A migration defines v_asset_state_truth AS a view, with security_invoker
     = true (so base-table hive RLS gates the reader), the
     unified_event_source_rank() resolver function, and a canonical_sources
     registration for domain 'asset_state_truth'.
  2. _shared/verified-state.ts exports resolveAssetState + formatVerifiedState.
  3. ai-gateway imports from _shared/verified-state.ts, calls resolveAssetState,
     and defines a non-empty VERIFIED_STATE_AGENTS set.

Output: verified_state_wiring_report.json. Exit 1 on regression vs baseline.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
FUNCS = ROOT / "supabase" / "functions"
MIGRATIONS = ROOT / "supabase" / "migrations"
SHARED = FUNCS / "_shared" / "verified-state.ts"
GATEWAY = FUNCS / "ai-gateway" / "index.ts"
REPORT_PATH = ROOT / "verified_state_wiring_report.json"
BASELINE_PATH = ROOT / "verified_state_wiring_baseline.json"


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""


def _all_migrations_text() -> str:
    if not MIGRATIONS.exists():
        return ""
    return "\n".join(_read(p) for p in sorted(MIGRATIONS.glob("*.sql")))


def main() -> int:
    violations: list[dict] = []

    def need(cond: bool, code: str, detail: str) -> None:
        if not cond:
            violations.append({"check": code, "detail": detail})

    mig = _all_migrations_text()
    need(bool(re.search(r"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+public\.v_asset_state_truth", mig, re.I)),
         "view-missing", "no migration defines view public.v_asset_state_truth")
    # security_invoker must be true on the verified-state view (RLS enforcement).
    need(bool(re.search(r"v_asset_state_truth\s*\n?\s*WITH\s*\(\s*security_invoker\s*=\s*true", mig, re.I)),
         "view-security-invoker",
         "v_asset_state_truth must be WITH (security_invoker = true)")
    need(bool(re.search(r"FUNCTION\s+public\.unified_event_source_rank", mig, re.I)),
         "rank-fn-missing", "unified_event_source_rank() resolver function not defined")
    need("'asset_state_truth'" in mig and "canonical_sources" in mig,
         "canonical-registration-missing",
         "v_asset_state_truth not registered in canonical_sources (domain asset_state_truth)")

    shared = _read(SHARED)
    need(bool(shared), "shared-missing", "_shared/verified-state.ts does not exist")
    for fn in ("resolveAssetState", "formatVerifiedState"):
        need(bool(re.search(rf"export\s+(?:async\s+)?function\s+{fn}\b", shared)),
             "shared-export-missing", f"_shared/verified-state.ts must export {fn}()")

    gw = _read(GATEWAY)
    need('from "../_shared/verified-state.ts"' in gw,
         "gateway-import-missing", "ai-gateway must import from ../_shared/verified-state.ts")
    need(bool(re.search(r"\bresolveAssetState\s*\(", gw)),
         "gateway-call-missing", "ai-gateway must call resolveAssetState()")
    m = re.search(r"VERIFIED_STATE_AGENTS[^=]*=\s*new\s+Set\(\s*\[(?P<body>.*?)\]", gw, re.DOTALL)
    agents = re.findall(r'"([^"]+)"', m.group("body")) if m else []
    need(len(agents) > 0, "gateway-agentset-empty",
         "ai-gateway must define a non-empty VERIFIED_STATE_AGENTS set")

    total = len(violations)
    baseline = 0
    if BASELINE_PATH.exists():
        try:
            baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("violations", 0)
        except Exception:
            baseline = total
    else:
        baseline = total
        BASELINE_PATH.write_text(json.dumps({"violations": baseline, "established": True}, indent=2), encoding="utf-8")
    if total < baseline:
        baseline = total
        BASELINE_PATH.write_text(json.dumps({"violations": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"violations": total, "baseline": baseline, "verified_state_agents": agents},
        "violations": violations,
    }, indent=2), encoding="utf-8")

    print("\nVerified-State Wiring Validator (L0)")
    print("=" * 56)
    print(f"  verified-state agents:    {', '.join(agents) or '(none)'}")
    print(f"  violations:               {total}  (baseline: {baseline})")
    if total == 0:
        print("\n  PASS — verified-state layer is wired end-to-end.")
        return 0
    for v in violations:
        print(f"    [{v['check']}] {v['detail']}")
    print(f"\n  {'PASS (at baseline)' if total <= baseline else 'FAIL (regression)'}")
    return 1 if total > baseline else 0


# Sentinel binding: name the L2 test `test('verified_state_wiring: ...')`.
CHECK_NAMES = ["verified_state_wiring"]

if __name__ == "__main__":
    sys.exit(main())
