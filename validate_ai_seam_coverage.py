"""
AI Seam Contract-Test Coverage Validator (C4 Phase 2a of SELF_IMPROVING_GATE_ROADMAP.md).
==========================================================================================
Forward-only ratchet on the number of AI seams that lack a contract test.
A "contract test" pins the WIRE FORMAT at the seam (request shape,
response envelope, error codes, hive_id propagation, rate-limit fields).
Journey tests that incidentally invoke a seam don't qualify — contract
tests must FAIL if the format changes silently.

How it works:
  1. Re-run the seam miner (so the catalog reflects current code).
  2. Read `ai_seams_catalog.json` `_meta.contracts.uncovered` count.
  3. Compare to `ai_seam_coverage_baseline.json` floor.
     - uncovered > baseline -> FAIL ("a new uncovered seam landed; either
       wire its contract test in ai_seam_contracts.json or accept the
       baseline rise by re-baselining").
     - uncovered <= baseline -> auto-lower the baseline (forward-only
       ratchet: every contract test written sticks; we never let the gap
       silently grow back).

This is the C5 + envelope_return_shape pattern: the floor only drops.
The seam catalog ratchets *inventory*; this ratchets *contract coverage*.

Today: 118 uncovered (all of them). The baseline locks at 118. As a
contract test gets wired per seam (Phase 2a payoff work), the baseline
ratchets down.

Exit codes:
  0  uncovered count <= baseline (or first run; baseline auto-set).
  1  uncovered count rose without an explicit baseline update.
"""
from __future__ import annotations
import io, json, subprocess, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT      = Path(__file__).resolve().parent
MINER     = ROOT / "tools" / "mine_ai_seams.py"
CATALOG   = ROOT / "ai_seams_catalog.json"
CONTRACTS = ROOT / "ai_seam_contracts.json"
BASELINE  = ROOT / "ai_seam_coverage_baseline.json"

CHECK_NAMES = ["ai_seam_coverage"]

# P3 freshness anchors — wake this validator the day the miner stops
# emitting the `_meta.contracts.uncovered` field, or the contracts sidecar
# schema moves.
FRESHNESS_ANCHORS = [
    ("tools/mine_ai_seams.py",   r"contracts.*covered",  "Miner stopped emitting contracts.covered; coverage gate is silent."),
    ("ai_seam_contracts.json",   r"\"contracts\"",       "Contracts sidecar lost its `contracts` map; coverage is meaningless."),
]


def main() -> int:
    if not MINER.exists():
        print(f"\033[91mFAIL: {MINER} missing\033[0m")
        return 2
    proc = subprocess.run(
        [sys.executable, "-u", str(MINER)],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    if proc.returncode != 0:
        sys.stdout.write(proc.stdout); sys.stderr.write(proc.stderr)
        print(f"\033[91mFAIL: miner exited {proc.returncode}\033[0m")
        return proc.returncode

    try:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"\033[91mFAIL: catalog parse error: {e}\033[0m")
        return 2

    contracts_meta = catalog.get("_meta", {}).get("contracts", {})
    uncovered = int(contracts_meta.get("uncovered", -1))
    covered   = int(contracts_meta.get("covered", 0))
    total     = int(catalog.get("_meta", {}).get("seam_count", uncovered + covered))
    if uncovered < 0:
        print(f"\033[91mFAIL: catalog missing _meta.contracts.uncovered (mine_ai_seams.py drift)\033[0m")
        return 2

    if not BASELINE.exists():
        BASELINE.write_text(json.dumps({
            "_meta": {
                "description": "C4 Phase 2a — frozen floor on uncovered seam count. Forward-only ratchet; baseline only ever drops as contract tests get wired in ai_seam_contracts.json.",
            },
            "uncovered": uncovered,
            "covered":   covered,
            "total":     total,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\033[96mFIRST RUN\033[0m — baselined uncovered={uncovered} (covered={covered}, total={total}).")
        print("        Wire seam_id → test_path entries in ai_seam_contracts.json to ratchet down.")
        return 0

    try:
        base = json.loads(BASELINE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"\033[91mFAIL: baseline parse error: {e}\033[0m")
        return 2

    base_uncov = int(base.get("uncovered", 0))

    if uncovered > base_uncov:
        print(f"\033[91mFAIL\033[0m  AI seam contract-test coverage gap GREW: "
              f"{base_uncov} -> {uncovered} uncovered (covered {covered}/{total}).")
        print(f"  Fix: either wire a contract test for the new seam(s) in {CONTRACTS.name}")
        print(f"        and re-run (baseline auto-drops), OR delete {BASELINE.name} to")
        print(f"        accept the higher floor (explicit choice — a contract gap is real risk).")
        return 1

    if uncovered < base_uncov:
        base["uncovered"] = uncovered
        base["covered"]   = covered
        base["total"]     = total
        BASELINE.write_text(json.dumps(base, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\033[92mOK\033[0m  AI seam contract-test coverage tightened: "
              f"baseline {base_uncov} -> {uncovered} uncovered "
              f"(covered {covered}/{total}). Floor locked at {uncovered}.")
        return 0

    print(f"\033[92mOK\033[0m  AI seam contract-test coverage stable: "
          f"{uncovered} uncovered of {total} (covered {covered}, baseline {base_uncov}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
