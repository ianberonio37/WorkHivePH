"""
Gate Observability Validator -- WorkHive Platform Guardian
==========================================================
Locks in the close-the-loop fix from 2026-06-09: the Mega Gate
(release_gate.py) MUST persist a durable record of every run, so a verdict
survives a Flask restart / crash and is inspectable after the fact.

Background (the gap this guards):
  A full Mega Gate run launched via the Tester left NO durable trace -- the
  only record was Flask's 200-line rolling in-memory buffer, which was wiped
  when Flask restarted mid-run (a concurrent session bounced it). persist_run()
  also silently no-op'd when its seeder-lib import failed, so run_history.json
  was never written. Net result: a ~40-min run evaporated. "You can't see the
  issues a gate surfaces if the gate doesn't persist them."

The fix wired release_gate.py to (a) Tee all console output into
.tmp/mega_gate_<ts>.log and (b) write a dependency-free verdict JSON
(.tmp/last_mega_gate_verdict.json) in EVERY terminal path -- preflight-fail,
reseed-fail, PASS, and BLOCK. This validator asserts that wiring stays present.

Checks:
  1. release_gate.py defines install_durable_log() AND write_durable_verdict()
  2. main() calls install_durable_log()
  3. write_durable_verdict() is invoked on BOTH the PASS and BLOCK paths
  4. the stable VERDICT_FILE pointer constant is defined

Usage:  python validate_gate_observability.py
Output: gate_observability_report.json

Sentinel binding: name the L2 test 'test('gate_observability: ...')' for
coverage credit (this is gate-infra, so the sentinel may classify it INFRA).
"""
import json, sys, re
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result  # noqa: E402

ROOT = Path(__file__).resolve().parent
GATE = ROOT / "release_gate.py"

CHECK_NAMES = [
    "durable_helpers_defined",
    "main_installs_log",
    "verdict_persisted_pass_and_block",
    "verdict_file_pointer",
]
CHECK_LABELS = {
    "durable_helpers_defined":          "L1  release_gate.py defines install_durable_log() + write_durable_verdict()",
    "main_installs_log":                "L2  main() installs the durable log (install_durable_log())",
    "verdict_persisted_pass_and_block": "L3  write_durable_verdict() runs on BOTH the PASS and BLOCK paths",
    "verdict_file_pointer":             "L4  stable VERDICT_FILE pointer constant is defined",
}


def main():
    print("Gate Observability Validator")
    print("============================")

    src = read_file(GATE)
    issues = []

    if src is None:
        # Hard fail every check if the gate file is missing.
        for c in CHECK_NAMES:
            issues.append({"check": c, "reason": f"release_gate.py not found at {GATE}"})
        _emit(issues)
        return

    # 1. helper definitions
    has_install = bool(re.search(r"def\s+install_durable_log\s*\(", src))
    has_verdict = bool(re.search(r"def\s+write_durable_verdict\s*\(", src))
    if not (has_install and has_verdict):
        missing = []
        if not has_install: missing.append("install_durable_log()")
        if not has_verdict: missing.append("write_durable_verdict()")
        issues.append({"check": "durable_helpers_defined",
                       "reason": f"release_gate.py is missing {', '.join(missing)} -- "
                                 "the durable-observability helpers must stay defined."})

    # 2. main() installs the durable log (look for a CALL, not the def)
    calls_install = bool(re.search(r"(?<!def )install_durable_log\s*\(", src))
    if not calls_install:
        issues.append({"check": "main_installs_log",
                       "reason": "install_durable_log() is never called -- main() must install the "
                                 "Tee so stdout is mirrored to .tmp/mega_gate_<ts>.log."})

    # 3. verdict persisted on BOTH PASS and BLOCK terminal paths
    has_pass_verdict = bool(re.search(r'write_durable_verdict\(\s*["\']PASS["\']', src))
    has_block_verdict = bool(re.search(r'write_durable_verdict\(\s*["\']BLOCK["\']', src))
    if not (has_pass_verdict and has_block_verdict):
        missing = []
        if not has_pass_verdict: missing.append("PASS")
        if not has_block_verdict: missing.append("BLOCK")
        issues.append({"check": "verdict_persisted_pass_and_block",
                       "reason": f"write_durable_verdict() not invoked on the {', '.join(missing)} path(s) -- "
                                 "every terminal verdict must be persisted dependency-free."})

    # 4. stable pointer constant
    if not re.search(r"VERDICT_FILE\s*=", src):
        issues.append({"check": "verdict_file_pointer",
                       "reason": "VERDICT_FILE constant is missing -- the stable pointer to the latest "
                                 "verdict JSON must be defined."})

    _emit(issues)


def _emit(issues):
    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)
    print(f"\nGate observability: {n_pass} PASS, {n_fail} FAIL, {n_skip} SKIP")
    report = {
        "checks_total": len(CHECK_NAMES),
        "n_pass": n_pass,
        "n_fail": n_fail,
        "issues": issues,
    }
    with open("gate_observability_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
