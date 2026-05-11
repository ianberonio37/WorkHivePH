"""
Validator Self-Coverage Meta-Gate -- WorkHive Platform
=======================================================
A meta-validator that audits the validator suite itself. Catches the
"new validator written but never wired into the guardian" gap, plus
inconsistencies between how a validator is registered and what it
actually does on disk.

Layer 1 -- Registered script does not exist                              [FAIL]
  Any entry in `run_platform_checks.py` whose `script` field points
  to a file that doesn't exist. Hard FAIL because the guardian will
  blow up on the missing file.

Layer 2 -- validate_*.py exists but isn't registered                     [WARN]
  Any validate_*.py at the project root that does NOT appear in the
  registry AND is not in `STANDALONE_OK` (engineering-calc layer
  validators run via run_all_checks.py belong here).

Layer 3 -- Declared report.json doesn't match what script writes         [WARN]
  Each registry entry has a `report` field naming the JSON file
  the validator writes. Parse each validator's source for the
  `open("X.json", "w")` line and compare. Mismatch = orchestrator
  reads a stale path on regression check.

Layer 4 -- Validator coverage census (informational)                     [INFO]
  Count of registered validators by group; total existing files;
  ratio. Useful for tracking "are we adding gates faster than we're
  retiring duplicates?".

Skills consulted: devops (orchestrator wiring discipline), architect
(meta-architecture: the validator suite is the platform's nervous
system; gaps in coverage are silent like any other bug).
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob
from collections import defaultdict

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


ORCHESTRATOR_FILE = "run_platform_checks.py"

# Validators that legitimately run outside the guardian. Each entry needs
# a one-line justification.
STANDALONE_OK = {
    "validate_bom_sow.py":     "engineering-calc layer 2b -- run via run_all_checks.py after BOM/SOW changes",
    "validate_fields.py":      "engineering-calc layer 1 -- run via run_all_checks.py after Python handler changes",
    "validate_renderers.py":   "engineering-calc layer 2a -- run via run_all_checks.py after renderer changes",
}


REGISTRY_ENTRY_RE = re.compile(
    r"""\{[^{}]*?
        "id"\s*:\s*"(?P<id>[^"]+)"[^{}]*?
        "script"\s*:\s*"(?P<script>validate_\w+\.py)"[^{}]*?
        (?:"report"\s*:\s*"(?P<report>[\w_]+\.json)")?
        [^{}]*?\}""",
    re.VERBOSE | re.DOTALL,
)
REPORT_WRITE_RE = re.compile(
    r"""open\s*\(\s*['"`](?P<file>[\w_./\\-]+\.json)['"`]\s*,\s*['"`]w['"`]""",
)


def parse_registry() -> list[dict]:
    src = read_file(ORCHESTRATOR_FILE) or ""
    # Strip Python `# comment` lines BEFORE the regex match so braces in
    # commentary (`body{animation}`, `{ ... }` examples) don't break the
    # `[^{}]*?` non-greedy match.
    src = re.sub(r"^\s*#[^\n]*$", "", src, flags=re.MULTILINE)
    rows: list[dict] = []
    for m in REGISTRY_ENTRY_RE.finditer(src):
        rows.append({
            "id":     m.group("id"),
            "script": m.group("script"),
            "report": m.group("report"),
        })
    return rows


def list_validator_files() -> list[str]:
    return sorted(os.path.basename(p) for p in glob.glob("validate_*.py"))


def find_report_writes(path: str) -> list[str]:
    src = read_file(path) or ""
    return [m.group("file") for m in REPORT_WRITE_RE.finditer(src)]


# -- Layer 1: Registered script does not exist -----------------------------

def check_missing_script(registry: list[dict]) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for r in registry:
        if not os.path.isfile(r["script"]):
            report.append({"id": r["id"], "script": r["script"]})
            issues.append({
                "check": "missing_script", "skip": False,
                "reason": (
                    f"Registry entry id='{r['id']}' references "
                    f"`{r['script']}` which does not exist on disk. The "
                    f"guardian will fail to launch. Either restore the "
                    f"file or remove the registry entry."
                ),
            })
    return issues, report


# -- Layer 2: Existing validator not registered ----------------------------

def check_unregistered(
    registry: list[dict],
    files: list[str],
) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    registered = {r["script"] for r in registry}
    self_file = os.path.basename(__file__)
    for f in files:
        if f in registered:
            continue
        if f in STANDALONE_OK:
            continue
        if f == self_file:
            continue
        report.append({"file": f})
        issues.append({
            "check": "unregistered", "skip": True,
            "reason": (
                f"`{f}` exists but is not registered in run_platform_checks.py. "
                f"Either add a registry entry, or list it in STANDALONE_OK "
                f"with a justification (e.g., engineering-calc layer "
                f"validator run via run_all_checks.py)."
            ),
        })
    return issues, report


# -- Layer 3: Declared vs actual report.json ------------------------------

def check_report_mismatch(registry: list[dict]) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for r in registry:
        if not r["report"]:
            continue
        if not os.path.isfile(r["script"]):
            continue
        actual = find_report_writes(r["script"])
        if not actual:
            # Validator doesn't write a report file -- that's a separate
            # signal but lower stakes; flag at INFO level via the report
            # but skip the WARN.
            continue
        if r["report"] in actual:
            continue
        report.append({
            "id":       r["id"],
            "script":   r["script"],
            "declared": r["report"],
            "actual":   actual,
        })
        issues.append({
            "check": "report_mismatch", "skip": True,
            "reason": (
                f"`{r['script']}` (id='{r['id']}'): registry declares "
                f"report='{r['report']}' but the script writes "
                f"{actual}. The orchestrator's regression-check reads "
                f"the wrong file. Align the registry `report` field "
                f"with the actual write target."
            ),
        })
    return issues, report


# -- Layer 4: Validator census (informational) ----------------------------

def check_census(
    registry: list[dict],
    files: list[str],
) -> tuple[list[dict], list[dict]]:
    src = read_file(ORCHESTRATOR_FILE) or ""
    by_group: dict[str, int] = defaultdict(int)
    for m in re.finditer(
        r"""\{[^{}]*?"id"\s*:\s*"(?P<id>[^"]+)"[^{}]*?"group"\s*:\s*"(?P<group>[^"]+)"[^{}]*?\}""",
        src, re.VERBOSE | re.DOTALL,
    ):
        by_group[m.group("group")] += 1
    rows: list[dict] = []
    for group, count in sorted(by_group.items(), key=lambda kv: -kv[1]):
        rows.append({"group": group, "count": count})
    rows.append({"group": "_total_registered", "count": len(registry)})
    rows.append({"group": "_total_files",      "count": len(files)})
    rows.append({"group": "_standalone_ok",    "count": len(STANDALONE_OK)})
    return [], rows


# -- Runner ----------------------------------------------------------------

CHECK_NAMES = [
    "missing_script",
    "unregistered",
    "report_mismatch",
    "census",
]
CHECK_LABELS = {
    "missing_script":    "L1  No registered script is missing on disk                       [FAIL]",
    "unregistered":      "L2  No validate_*.py exists outside registry (or STANDALONE_OK)   [WARN]",
    "report_mismatch":   "L3  Every registry `report` field matches the script's write      [WARN]",
    "census":            "L4  Validator count by group + total existing (informational)     [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nValidator Self-Coverage Meta-Gate (4-layer)"))
    print("=" * 60)

    registry = parse_registry()
    files    = list_validator_files()
    print(f"  {len(registry)} registered, {len(files)} validate_*.py files on disk "
          f"(STANDALONE_OK={len(STANDALONE_OK)}).\n")

    l1_issues, l1_report = check_missing_script(registry)
    l2_issues, l2_report = check_unregistered(registry, files)
    l3_issues, l3_report = check_report_mismatch(registry)
    l4_issues, l4_report = check_census(registry, files)

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l4_report:
        print(f"\n{bold('VALIDATOR CENSUS (informational)')}")
        print("  " + "-" * 56)
        for r in l4_report:
            print(f"  {r['group']:<28}  {r['count']}")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":       "validator_self_coverage",
        "total_checks":    total,
        "passed":          n_pass,
        "warned":          n_warn,
        "failed":          n_fail,
        "n_registered":    len(registry),
        "n_files":         len(files),
        "missing_script":  l1_report,
        "unregistered":    l2_report,
        "report_mismatch": l3_report,
        "census":          l4_report,
        "issues":          [i for i in all_issues if not i.get("skip")],
        "warnings":        [i for i in all_issues if i.get("skip")],
    }
    with open("validator_self_coverage_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
