"""run_sentinel_review.py - Sentinel orchestrator.

Mirrors run_platform_checks.py but for the Layer 0 -> Layer 2 sentinel layer.
Reads SENTINEL_REGISTRY.json and runs each registered sentinel as a subprocess.

Usage:
  python run_sentinel_review.py             # run all sentinels
  python run_sentinel_review.py --json      # JSON-only output (no human banner)

Exit codes:
  0 = all sentinels passed
  1 = one or more failed

This is the v0+ shell. v0 has one sentinel (coverage_map). v3 adds more
(freshness, depth, pattern consistency). See SENTINEL_ARCHITECTURE.md.
"""

import sys
import json
import subprocess
import datetime
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PYTHON = sys.executable
ROOT = Path(__file__).resolve().parent
REGISTRY_FILE = ROOT / "SENTINEL_REGISTRY.json"
HEALTH_FILE = ROOT / "sentinel_health.json"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

JSON_ONLY = "--json" in sys.argv


def log(msg=""):
    if not JSON_ONLY:
        print(msg)


def load_registry():
    if not REGISTRY_FILE.exists():
        return []
    try:
        data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
        return data.get("sentinels", [])
    except json.JSONDecodeError as e:
        log(f"  {RED}SENTINEL_REGISTRY.json malformed: {e}{RESET}")
        return []


def run_sentinel(entry):
    script = ROOT / entry["script"]
    if not script.exists():
        return {"id": entry["id"], "status": "MISSING", "duration": 0,
                "error": f"script not found: {entry['script']}"}
    t0 = datetime.datetime.now()
    try:
        result = subprocess.run(
            [PYTHON, "-u", str(script)],
            capture_output=True, text=True, timeout=300,
            encoding="utf-8", errors="replace",
        )
        ok = result.returncode == 0
    except subprocess.TimeoutExpired:
        return {"id": entry["id"], "status": "TIMEOUT", "duration": 300}
    dur = round((datetime.datetime.now() - t0).total_seconds(), 1)
    return {
        "id": entry["id"],
        "status": "PASS" if ok else "FAIL",
        "duration": dur,
        "stdout": result.stdout,
        "stderr": result.stderr if not ok else "",
    }


def main():
    log()
    log(f"{BOLD}{CYAN}SENTINEL REVIEW - Layer 0 -> Layer 2 Bridge{RESET}")
    log("=" * 60)

    registry = load_registry()
    if not registry:
        log(f"  {YELLOW}No sentinels registered. Check SENTINEL_REGISTRY.json{RESET}")
        return 1

    log(f"  Running {len(registry)} sentinel(s)...")
    log()

    results = []
    for entry in registry:
        log(f"  {CYAN}>{RESET} {entry['label']}  ({entry['tier']}, {entry['axis']})")
        r = run_sentinel(entry)
        results.append(r)
        status_color = GREEN if r["status"] == "PASS" else RED
        log(f"    {status_color}{r['status']}{RESET}  ({r['duration']}s)")
        if r.get("stdout") and not JSON_ONLY:
            for line in r["stdout"].rstrip().split("\n"):
                log(f"    {line}")
        if r.get("stderr"):
            log(f"    {RED}stderr:{RESET} {r['stderr'][:500]}")
        log()

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] != "PASS")
    log("─" * 60)
    summary_color = GREEN if failed == 0 else RED
    log(f"  {BOLD}Totals:{RESET} {summary_color}{passed} PASS / {failed} FAIL{RESET} "
        f"({len(results)} sentinel(s))")
    log()

    health = {
        "timestamp": datetime.datetime.now().isoformat(),
        "passed": passed,
        "failed": failed,
        "results": [
            {k: v for k, v in r.items() if k != "stdout"}
            for r in results
        ],
    }
    HEALTH_FILE.write_text(json.dumps(health, indent=2), encoding="utf-8")

    # Append to history JSONL for the Tester UI climb chart.
    # One line per successful run; kept tiny (just the headline numbers).
    history_path = ROOT / "sentinel_history.jsonl"
    coverage_path = ROOT / "sentinel_coverage_report.json"
    if coverage_path.exists():
        try:
            coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
            s = coverage.get("summary", {})
            entry = {
                "timestamp": health["timestamp"],
                "raw_pct": s.get("validator_coverage_pct"),
                "effective_pct": s.get("effective_coverage_pct"),
                "check_pct": s.get("check_coverage_pct"),
                "behavioral_pct": s.get("behavioral_coverage_pct"),
                "covered_validators": s.get("covered_validators"),
                "covered_behavioral_checks": s.get("covered_per_page_behavioral_checks"),
                "total_behavioral_checks": s.get("total_per_page_behavioral_checks"),
                "sentinels_passed": passed,
                "sentinels_failed": failed,
            }
            with history_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        except (OSError, json.JSONDecodeError):
            pass

    if JSON_ONLY:
        print(json.dumps(health, indent=2))

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
