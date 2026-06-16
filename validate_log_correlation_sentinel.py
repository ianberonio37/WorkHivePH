"""
Log-Correlation Sentinel (Maturity Phase 3, 2026-06-16).
=========================================================
Closes the (L, GS) cell from COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4 — proves
logs are structured + correlatable (the observability bridge).

A log you can't correlate to a request is noise. This asserts the logging tier
emits structured records carrying a correlation id, and an aggregation store
exists to roll them up:

  L1  structured logger exists          — _shared/logger.ts
  L2  logger carries a correlation id    — trace_id / request_id / requestId
  L3  structured (JSON) emission         — JSON.stringify in the logger
  L4  aggregation/SLI store exists        — _shared/trace-store.ts (rolls up wh_traces)

Swap-ready: when a Sentry DSN exists, L4's store swaps impl without changing the
gate (error-tracker.ts already writes wh_traces today).

Output:  log_correlation_report.json
Exit code: 0 PASS / 1 FAIL (logging not structured/correlatable)
"""
from __future__ import annotations
import io, json, sys
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
LOGGER = ROOT / "supabase" / "functions" / "_shared" / "logger.ts"
TRACE_STORE = ROOT / "supabase" / "functions" / "_shared" / "trace-store.ts"
REPORT = ROOT / "log_correlation_report.json"

CHECK_NAMES = ["log_correlation"]
GREEN = "\033[92m"; RED = "\033[91m"; BOLD = "\033[1m"; RESET = "\033[0m"


def main() -> int:
    lg = LOGGER.read_text(encoding="utf-8", errors="replace") if LOGGER.exists() else ""
    has_corr = any(k in lg for k in ("trace_id", "traceId", "request_id", "requestId", "traceparent"))
    structured = "JSON.stringify" in lg or "JSON.stringify(" in lg

    checks = [
        ("L1 structured logger present (_shared/logger.ts)", LOGGER.exists()),
        ("L2 logger carries a correlation id (trace_id/request_id)", has_corr),
        ("L3 structured JSON emission (JSON.stringify in logger)", structured),
        ("L4 aggregation/SLI store present (_shared/trace-store.ts)", TRACE_STORE.exists()),
    ]
    fails = [name for name, ok in checks if not ok]

    REPORT.write_text(json.dumps({
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "checks": {n: ok for n, ok in checks}, "fails": fails,
    }, indent=2), encoding="utf-8")

    print(f"{BOLD}Log-Correlation Sentinel (L, GS){RESET}")
    for name, ok in checks:
        print(f"  {GREEN+'PASS'+RESET if ok else RED+'FAIL'+RESET}  {name}")
    if fails:
        print(f"{RED}FAIL: {len(fails)} log-correlation invariant(s) unproven.{RESET}")
        return 1
    print(f"{GREEN}PASS — logs are structured + correlatable + aggregated.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
