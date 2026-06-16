"""
Log-Surface Discovery (Maturity Phase 3, 2026-06-16).
======================================================
Closes the (L, G-1) cell from COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4 — the
auto-discovery gate for the Error-Tracking & Logs layer.

validate_structured_log_adoption.py (G0) ratchets the COUNT of fns using the
structured logger UP. This is the complementary discovery gate: a forward-only
ratchet over the count of edge fns that still log with raw console.* and do NOT
import _shared/logger.ts. A new fn that ships raw console logging raises the
count and FAILs — the "we shipped an ungreppable log surface" catch.

Output:  log_surface_discovery_report.json
Baseline: log_surface_baseline.json   (unstructured count; only descends)
Exit code: 0 PASS / 1 FAIL (a new unstructured-logging fn)
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
FN_DIR = ROOT / "supabase" / "functions"
REPORT   = ROOT / "log_surface_discovery_report.json"
BASELINE = ROOT / "log_surface_baseline.json"

CHECK_NAMES = ["log_surface_discovery"]
GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; BOLD = "\033[1m"; RESET = "\033[0m"

CONSOLE_RE = re.compile(r"\bconsole\.(log|error|warn|info)\s*\(")


def _load(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> int:
    unstructured: list[str] = []
    if FN_DIR.exists():
        for entry in sorted(FN_DIR.iterdir()):
            if not entry.is_dir() or entry.name.startswith("_"):
                continue
            idx = entry / "index.ts"
            if not idx.exists():
                continue
            t = idx.read_text(encoding="utf-8", errors="replace")
            uses_console = bool(CONSOLE_RE.search(t))
            imports_logger = "_shared/logger.ts" in t or "from \"../_shared/logger" in t or "from '../_shared/logger" in t
            if uses_console and not imports_logger:
                unstructured.append(entry.name)
    unstructured = sorted(unstructured)
    cur = len(unstructured)

    base = _load(BASELINE)
    first_lock = base is None
    if first_lock:
        base = {"unstructured": cur, "fns": unstructured}
        BASELINE.write_text(json.dumps(base, indent=2), encoding="utf-8")
    baseline_n = int(base.get("unstructured", cur))
    new_fns = [f for f in unstructured if f not in set(base.get("fns", []))]

    if cur < baseline_n:
        base["unstructured"] = cur; base["fns"] = unstructured
        BASELINE.write_text(json.dumps(base, indent=2), encoding="utf-8")

    REPORT.write_text(json.dumps({
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "unstructured": cur, "baseline": baseline_n, "new_unstructured_fns": new_fns,
        "first_lock": first_lock,
    }, indent=2), encoding="utf-8")

    print(f"{BOLD}Log-Surface Discovery (L, G-1){RESET}")
    print(f"  edge fns logging raw console.* (no logger.ts): {cur}  (baseline {baseline_n})")
    if first_lock:
        print(f"{YEL}  baseline locked at {cur} (first run) — drive down by adopting logger.ts.{RESET}")
    if cur > baseline_n:
        print(f"{RED}FAIL: +{cur - baseline_n} new unstructured-logging fn(s): {', '.join(new_fns)}{RESET}")
        return 1
    if cur < baseline_n:
        print(f"{GREEN}PASS: structured-logging tightened {baseline_n} → {cur}.{RESET}")
        return 0
    print(f"{GREEN}PASS — no new ungreppable log surface.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
