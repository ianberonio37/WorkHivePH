#!/usr/bin/env python3
"""
validate_companion_source_coverage.py
Layer 0 - Forward-only ratchet (THE SOURCES GATEWAY enforcement).

Enforce: every platform v_*_truth source view is TRIAGED in companion_source_registry.json
- either status:"served" (wired into the companion's ops-snapshot),
- or status:"candidate" (worker-relevant, queued for Pillar R on-demand) with a reason,
- or status:"out_of_scope" with a reason.

A NEW v_*_truth view added to the platform that is NOT in the registry => FAIL, forcing a
deliberate decision (serve it / queue it / exclude it). This is the self-improving loop pointed
at DATA COVERAGE: the companion's reachable-source set can never silently fall behind the platform.

Also keeps the AI gate honest: every status:"served" entry MUST declare ground_truth_keys, so the
fabrication grader (companion_fabrication_sweep.py ground_truth) is wired to credit it as grounded.

Discovery is static (CI-safe): scans canonical_registry.json + canonical_registry.md for v_*_truth
tokens (the platform's own declared view inventory). If a live local DB is reachable it is unioned
in as a belt-and-suspenders check, but its absence never fails the gate.
"""
import io
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / "supabase" / "functions" / "_shared" / "companion_source_registry.json"
TRUTH_RE = re.compile(r"\bv_[a-z0-9]+(?:_[a-z0-9]+)*_truth\b")
VALID_STATUS = {"served", "served_on_demand", "candidate", "out_of_scope"}


def discover_platform_truth_views() -> set[str]:
    """Static discovery from the platform's own canonical registry files (CI-safe)."""
    found: set[str] = set()
    for fn in ("canonical_registry.json", "canonical_registry.md"):
        p = ROOT / fn
        if p.exists():
            found |= set(TRUTH_RE.findall(p.read_text(encoding="utf-8", errors="replace")))
    # Optional: union the live DB if reachable (never fatal on failure).
    try:
        import subprocess
        out = subprocess.run(
            ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-t", "-c",
             "SELECT table_name FROM information_schema.views WHERE table_name LIKE 'v\\_%\\_truth' "
             "UNION SELECT matviewname FROM pg_matviews WHERE matviewname LIKE 'v\\_%\\_truth';"],
            capture_output=True, text=True, timeout=15)
        found |= set(TRUTH_RE.findall(out.stdout))
    except Exception:
        pass
    return found


def main() -> int:
    print("\n" + "=" * 80)
    print("  Companion Source Coverage Validator (Layer 0) - the Sources Gateway")
    print("=" * 80 + "\n")

    if not REGISTRY.exists():
        print(f"  FAIL: {REGISTRY.name} missing - the sources gateway registry must exist.")
        return 1

    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    entries = reg.get("sources", [])
    by_source = {e["source"]: e for e in entries}

    # 1) Registry self-consistency: valid status; served needs ground_truth_keys; non-served needs reason.
    self_errs = []
    for e in entries:
        st = e.get("status")
        if st not in VALID_STATUS:
            self_errs.append(f"{e.get('source','?')}: invalid status '{st}'")
        if st == "served" and not e.get("ground_truth_keys"):
            self_errs.append(f"{e['source']}: status 'served' but no ground_truth_keys (gate would not credit it)")
        if st == "served_on_demand":
            if not e.get("engine"):
                self_errs.append(f"{e['source']}: 'served_on_demand' but no engine spec (Pillar R can't fetch it)")
            if not e.get("match"):
                self_errs.append(f"{e['source']}: 'served_on_demand' but no `match` keywords (router can't trigger it)")
            if not e.get("ground_truth_keys"):
                self_errs.append(f"{e['source']}: 'served_on_demand' but no ground_truth_keys")
        if st in ("candidate", "out_of_scope") and not e.get("reason"):
            self_errs.append(f"{e['source']}: status '{st}' but no reason given")

    # 2) Coverage: every discovered platform v_*_truth view must be triaged in the registry.
    discovered = discover_platform_truth_views()
    untriaged = sorted(v for v in discovered if v not in by_source)

    served = [e["source"] for e in entries if e.get("status") == "served"]
    cand = [e["source"] for e in entries if e.get("status") == "candidate"]
    oos = [e["source"] for e in entries if e.get("status") == "out_of_scope"]

    print(f"  Discovered platform v_*_truth views : {len(discovered)}")
    print(f"  Registry entries                    : {len(entries)} (served={len(served)}, candidate={len(cand)}, out_of_scope={len(oos)})")
    print(f"  Served (always-on snapshot)          : {', '.join(sorted(served))}\n")

    ok = True
    if self_errs:
        ok = False
        print("  REGISTRY SELF-CONSISTENCY ERRORS:")
        for m in self_errs:
            print(f"    - {m}")
        print()
    if untriaged:
        ok = False
        print("  UNTRIAGED SOURCES (in the platform, missing from the registry) - DECIDE each:")
        for v in untriaged:
            print(f"    - {v}  -> add to companion_source_registry.json as served / candidate / out_of_scope")
        print()

    if ok:
        print("  PASS: every platform truth view is triaged in the sources gateway; "
              "all served sources declare ground_truth_keys.\n")
        return 0
    print("  FAIL: the sources gateway is out of sync with the platform (see above).\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
