#!/usr/bin/env python3
"""
AI Self-Improvement Loop Orchestrator

Runs all 4 layers in sequence:
  Layer 0: Playwright scenarios (all surfaces)
  Layer 1: Claude analyzes failures → extract findings
  Layer 2: Auto-fix issues
  Layer 3: Create/extend validators
  Layer 4: Meta-validator checks loop integrity
  Final: Fast mega gate validation (all validators)

Mirrors unified gates pattern but dynamic (failure-driven vs schema-driven).

Usage:
  python tools/ai_self_improvement_loop.py                   # all surfaces
  python tools/ai_self_improvement_loop.py --surface VOICE   # voice only
  python tools/ai_self_improvement_loop.py --fast            # fewer scenarios

Exit codes:
  0 = loop completed successfully, all validators pass
  1 = loop encountered error
  2 = meta-validator found issues
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Load .env file if it exists
def load_env():
    env_path = Path(".env")
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip().strip('"').strip("'")

load_env()

PYTHON = sys.executable

# Color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

def banner(text, color="cyan"):
    """Print colored banner."""
    colors = {"cyan": CYAN, "green": GREEN, "red": RED, "yellow": YELLOW}
    c = colors.get(color, "")
    r = RESET if c else ""
    print(f"\n{c}{'=' * 70}{r}")
    print(f"{c}{text:^70}{r}")
    print(f"{c}{'=' * 70}{r}")

def step(text):
    """Print step indicator."""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {text}")

def ok(text):
    """Print success."""
    print(f"  {GREEN}[PASS]{RESET} {text}")

def fail(text):
    """Print failure."""
    print(f"  {RED}[FAIL]{RESET} {text}")

def warn(text):
    """Print warning."""
    print(f"  {YELLOW}[WARN]{RESET} {text}")

def run_layer(layer_num, name, script, args=None, timeout=300) -> tuple[int, dict]:
    """
    Run a layer script and capture output.
    Returns: (exit_code, output_data)
    """
    step(f"Layer {layer_num}: {name}")

    cmd = [PYTHON, f"tools/{script}"] + (args or [])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),  # Pass environment variables to subprocess
        )

        # Print output
        for line in result.stdout.split("\n"):
            if line.strip():
                print(f"    {line}")

        if result.returncode != 0 and result.stderr:
            print(f"    {RED}Error:{RESET}")
            for line in result.stderr.split("\n")[:10]:
                if line.strip():
                    print(f"      {line}")

        return result.returncode, {"script": script, "returncode": result.returncode}

    except subprocess.TimeoutExpired:
        fail(f"Layer timeout (5m)")
        return 1, {"script": script, "error": "timeout"}
    except Exception as e:
        fail(f"Layer error: {e}")
        return 1, {"script": script, "error": str(e)}

def check_prerequisites() -> bool:
    """Verify Flask and local services are running."""
    step("Prerequisites Check")

    import socket

    services = [
        ("Flask seeder", "127.0.0.1", 5000),
        ("Local Supabase", "127.0.0.1", 54321),
    ]

    all_good = True
    for name, host, port in services:
        try:
            with socket.create_connection((host, port), timeout=2):
                ok(f"{name} reachable ({host}:{port})")
        except OSError:
            fail(f"{name} not running ({host}:{port})")
            all_good = False

    return all_good

def load_layer_results(filename: str) -> dict:
    """Load results from a layer output file."""
    path = Path(filename)
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def run_fast_gate() -> int:
    """Run fast mega gate to validate all (including new validators)."""
    step("Final: Fast Mega Gate")

    cmd = [PYTHON, "run_platform_checks.py", "--fast"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        # Extract summary line
        lines = result.stdout.split("\n")
        for line in lines:
            if "PASS" in line or "FAIL" in line or "Summary" in line:
                print(f"    {line}")

        return result.returncode

    except subprocess.TimeoutExpired:
        fail("Fast gate timeout")
        return 1
    except Exception as e:
        fail(f"Fast gate error: {e}")
        return 1

def save_metadata(loop_results: dict):
    """Save loop metadata for tracking."""
    metadata = {
        "loop_start": loop_results.get("start_time"),
        "loop_end": datetime.now().isoformat(),
        "duration_seconds": (datetime.now() - datetime.fromisoformat(loop_results["start_time"])).total_seconds(),
        "surface_filter": loop_results.get("surface_filter"),
        "layer_results": loop_results.get("layers"),
        "final_gate_result": loop_results.get("final_gate_result"),
    }

    # Compute summary
    scenario_results = load_layer_results("SCENARIO_RESULTS.json")
    if scenario_results:
        metadata["scenarios_run"] = scenario_results.get("summary", {}).get("total", 0)
        metadata["scenarios_passed"] = scenario_results.get("summary", {}).get("passed", 0)

    findings_path = Path("SCENARIO_FINDINGS.jsonl")
    if findings_path.exists() and findings_path.stat().st_size > 0:
        finding_count = sum(1 for line in open(findings_path) if line.strip())
        metadata["findings_extracted"] = finding_count

    registry = load_layer_results("VALIDATOR_REGISTRY.json")
    if registry:
        metadata["validators_generated"] = registry.get("validators_generated", 0)
        metadata["validators_registered"] = registry.get("validators_registered", 0)

    # Save
    with open("LOOP_METADATA.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nMetadata saved to: LOOP_METADATA.json")

def main(surface_filter=None, fast=False) -> int:
    """Run full improvement loop."""
    banner("AI SELF-IMPROVEMENT LOOP (Playwright-Driven)", "cyan")

    loop_start = datetime.now()
    loop_results = {
        "start_time": loop_start.isoformat(),
        "surface_filter": surface_filter,
        "layers": {},
    }

    # Prerequisites
    if not check_prerequisites():
        banner("LOOP BLOCK — Prerequisites failed", "red")
        print("Start Flask seeder and local Supabase, then retry.")
        return 1

    # Layer 0: Playwright Scenarios (UI)
    args_0 = ["--fast"] if fast else []
    if surface_filter:
        args_0.extend([f"--surface={surface_filter}"])

    rc0, res0 = run_layer(0, "Scenario Execution", "playwright_scenario_executor.py", args_0)
    loop_results["layers"][0] = res0

    scenario_results = load_layer_results("SCENARIO_RESULTS.json")
    passed = scenario_results.get("summary", {}).get("passed", 0)
    failed = scenario_results.get("summary", {}).get("failed", 0)

    print(f"\n  Results: {passed} PASS | {failed} FAIL")

    # Layer 0.5: Cron Job Testing (skip if surface filtered or fast mode)
    if not surface_filter and not fast:
        step("Layer 0.5: Cron Job Testing")
        rc0b, res0b = run_layer(0.5, "Cron Job Validation", "test_cron_jobs.py", [])
        loop_results["layers"]["0.5"] = res0b

        cron_results = load_layer_results("CRON_JOB_RESULTS.json")
        cron_passed = cron_results.get("summary", {}).get("passed", 0)
        cron_failed = cron_results.get("summary", {}).get("failed", 0)
        print(f"\n  Cron Jobs: {cron_passed} PASS | {cron_failed} FAIL")

    if failed == 0:
        print(f"  {GREEN}All scenarios passing!{RESET} Skipping to meta-validator.")
    else:
        # Layer 1: Failure Analysis (needs longer timeout for many findings)
        rc1, res1 = run_layer(1, "Failure Analysis", "analyze_scenario_findings.py", [], timeout=900)
        loop_results["layers"][1] = res1

        if rc1 != 0:
            fail("Layer 1 failed, stopping.")
            loop_results["final_gate_result"] = "BLOCKED"
            save_metadata(loop_results)
            return 1

        # Layer 2: Auto-Remediation
        rc2, res2 = run_layer(2, "Auto-Remediation", "auto_fix_findings.py", [])
        loop_results["layers"][2] = res2

        if rc2 != 0:
            warn("Layer 2 had issues, but continuing.")

        # Layer 3: Validator Generator
        rc3, res3 = run_layer(3, "Validator Generation", "generate_and_register_validator.py", [])
        loop_results["layers"][3] = res3

        if rc3 != 0:
            fail("Layer 3 failed, stopping.")
            loop_results["final_gate_result"] = "BLOCKED"
            save_metadata(loop_results)
            return 1

    # Layer 4: Meta-Validator
    rc4, res4 = run_layer(4, "Meta-Validator (Loop Guardian)", "validate_improvement_loop_integrity.py", [])
    loop_results["layers"][4] = res4

    if rc4 != 0:
        fail("Meta-validator found issues.")
        loop_results["final_gate_result"] = "BLOCKED"
        save_metadata(loop_results)
        return 2

    # Final: Fast Mega Gate
    print()
    rc_gate = run_fast_gate()
    loop_results["final_gate_result"] = "PASS" if rc_gate == 0 else "FAIL"

    # Summary
    print()
    if rc_gate == 0:
        banner("LOOP PASS — Ready for deployment", "green")
        print(f"\nStaged changes ready:")
        print(f"  git diff --stat")
        print(f"\nTo review all changes:")
        print(f"  git diff")
        print(f"\nTo approve and commit:")
        print(f"  git add -A")
        print(f'  git commit -m "Auto-improvement from AI self-learning loop"')
        print(f"  git push origin master")
    else:
        banner("LOOP BLOCKED — Validators failed", "red")
        print(f"\nFix the validation failures above, then re-run the loop.")

    save_metadata(loop_results)
    return rc_gate

if __name__ == "__main__":
    surface_filter = None
    fast = False

    for arg in sys.argv[1:]:
        if arg == "--fast":
            fast = True
        elif arg.startswith("--surface"):
            surface_filter = arg.split("=")[1] if "=" in arg else None
        elif arg.startswith("--all-surfaces"):
            surface_filter = None

    exit_code = main(surface_filter=surface_filter, fast=fast)
    sys.exit(exit_code)
