"""
Validator cp1252-Guard Validator -- WorkHive Platform
======================================================
Second validator graduated from L-1 Convention Mining (after
validate_loads_utils_js.py). Enforces an implicit rule that the codebase
already follows at 100% conformance AFTER the 2026-05-18 patch pass:
every `validate_*.py` file must install the Windows cp1252 stdout guard.

Why the guard matters:
  Windows consoles default to the cp1252 codepage. When a validator prints
  a Unicode character that cp1252 cannot encode (em-dash, emoji, arrow,
  Greek symbol), Python raises UnicodeEncodeError and the validator
  CRASHES mid-run. This used to take down Mega Gate runs silently. See
  [[feedback-console-encoding]] for the historical incident.

The canonical fix is the 3-line block at the top of every validator:

    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

(The `sys.stdout.detach()` variant is equivalent and also accepted.)

Promotion source: tools/mine_validator_patterns.py surfaced this as the
82%-conformance candidate (33 outliers out of 188 files). All 33 were
patched on 2026-05-18; this validator locks the rule in so a future new
validator authored without the guard fails Mega Gate immediately.

Layer 1 -- every validate_*.py installs the cp1252 guard                [FAIL]
  An `io.TextIOWrapper` reassignment of `sys.stdout` (in either the
  .buffer or .detach() form) must appear somewhere in the file.

Layer 2 -- allowlist sanity (always empty by design)                    [WARN]
  If a validator legitimately must not have the guard (e.g., it
  intentionally writes binary to stdout), document it here. Today: none.

Layer 3 -- guard appears BEFORE the first print() call                  [INFO]
  Informational: the line-count threshold isn't meaningful (long
  docstrings push the guard well past line 30). What MATTERS is that
  the guard installs BEFORE any print() can crash. We compare guard line
  to the line of the first `print(` outside the docstring -- if guard
  comes first, you're safe; if not, that print is exposed.

Skills consulted: qa-tester (validator skeleton, the existing
feedback_console_encoding rule), devops (Windows-specific runtime
quirks), architect (graduation pattern from L-1 mining).
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path


if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import format_result


ROOT = Path(__file__).resolve().parent

# Match either canonical guard form:
#   sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", ...)
#   sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", ...)
GUARD_RE = re.compile(r"sys\.stdout\s*=\s*io\.TextIOWrapper")

# Validators that genuinely must skip the guard. Empty today -- all 188
# scripts comply. Add an entry here ONLY if the validator writes binary
# to stdout intentionally and the guard would corrupt its output. Each
# entry needs a documented reason.
ALLOWLIST: dict[str, str] = {}

# L3 check: locate the first executable `print(` that's NOT inside the
# module docstring. The guard must install BEFORE that line, otherwise
# the print is exposed to cp1252 crashes.
PRINT_CALL_RE = re.compile(r"^\s*print\s*\(")


def _list_validators() -> list[Path]:
    return sorted([p for p in ROOT.glob("validate_*.py") if p.is_file()])


def _check_file(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines()

    # Find guard line.
    guard_line = None
    for idx, ln in enumerate(lines, start=1):
        if GUARD_RE.search(ln):
            guard_line = idx
            break

    # Find first print() outside the leading docstring. The leading
    # docstring is the first `"""..."""` block at file top -- skip its
    # content. After it, any print() is "executable".
    in_docstring = False
    docstring_quote = None
    first_print_line = None
    for idx, ln in enumerate(lines, start=1):
        stripped = ln.lstrip()
        if not in_docstring:
            # Look for opening docstring at top of file (lines 1-3 typically).
            if idx <= 3 and (stripped.startswith('"""') or stripped.startswith("'''")):
                docstring_quote = stripped[:3]
                # Same-line close? e.g., """one-liner""" — rare for module docstrings.
                if stripped.count(docstring_quote) >= 2 and len(stripped) > 6:
                    continue
                in_docstring = True
                continue
            # Outside docstring -- is this an executable print()?
            if PRINT_CALL_RE.match(ln):
                first_print_line = idx
                break
        else:
            if docstring_quote and docstring_quote in stripped:
                in_docstring = False

    return {
        "has_guard":        guard_line is not None,
        "guard_line":       guard_line,
        "first_print_line": first_print_line,
        "total_lines":      len(lines),
    }


def check_validators():
    """L1 + L2 + L3."""
    issues = []
    census = {"compliant": [], "allowlisted": [], "violating": [], "deep_placement": []}

    for path in _list_validators():
        name = path.name
        result = _check_file(path)
        on_allowlist = name in ALLOWLIST

        if result["has_guard"]:
            census["compliant"].append(name)
            guard_line = result["guard_line"]
            first_print = result["first_print_line"]
            # L3: if there's an executable print() ABOVE the guard, that
            # print is exposed. If guard comes first (or no print at all),
            # the file is safe.
            if guard_line and first_print and first_print < guard_line:
                census["deep_placement"].append((name, guard_line, first_print))
                issues.append({
                    "check":  "guard_placement",
                    "skip":   True,  # INFO, not FAIL
                    "reason": (
                        f"{name}: first print() at line {first_print} is BEFORE "
                        f"the guard at line {guard_line}. That print is exposed to "
                        f"cp1252 crashes. Move the guard above it."
                    ),
                })
            if on_allowlist:
                issues.append({
                    "check":  "allowlist_freshness",
                    "skip":   True,
                    "reason": f"{name} now has the guard -- remove from ALLOWLIST.",
                })
        else:
            if on_allowlist:
                census["allowlisted"].append(name)
            else:
                census["violating"].append(name)
                issues.append({
                    "check":  "cp1252_guard_present",
                    "reason": (
                        f"{name} is missing the cp1252 stdout guard. Add at the "
                        f"top of the file (after `import sys`):\n\n"
                        f"    if sys.platform == \"win32\":\n"
                        f"        import io\n"
                        f"        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, "
                        f"encoding=\"utf-8\", errors=\"replace\")\n\n"
                        f"Or run `python tools/patch_cp1252_guards.py` after "
                        f"mine_validator_patterns.py surfaces the gap."
                    ),
                })

    return issues, census


CHECK_NAMES  = ["cp1252_guard_present", "allowlist_freshness", "guard_placement"]
CHECK_LABELS = {
    "cp1252_guard_present": "L1  Every validate_*.py installs the cp1252 stdout guard",
    "allowlist_freshness":  "L2  Allowlist entries that now comply should be graduated off",
    "guard_placement":      "L3  Guard appears before the first executable print() (informational)",
}


def main() -> int:
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nValidator cp1252-Guard Validator"))
    print("=" * 55)

    validators = _list_validators()
    issues, census = check_validators()
    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    print(f"\nCensus:")
    print(f"  total validators:        {len(validators)}")
    print(f"  compliant:               {len(census['compliant'])}")
    print(f"  allowlisted (skipped):   {len(census['allowlisted'])}")
    print(f"  violating (missing):     {len(census['violating'])}")
    print(f"  deep-placement (INFO):   {len(census['deep_placement'])}")

    report = {
        "summary": {
            "total_validators": len(validators),
            "compliant":        len(census["compliant"]),
            "violating":        len(census["violating"]),
            "allowlisted":      len(census["allowlisted"]),
            "deep_placement":   len(census["deep_placement"]),
            "fail":             n_fail,
        },
        "allowlist":  ALLOWLIST,
        "census":     {**census, "deep_placement": [
            {"file": n, "guard_line": gl, "first_print_line": pl}
            for (n, gl, pl) in census["deep_placement"]
        ]},
        "issues":     issues,
    }
    (ROOT / "validator_cp1252_guard_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    if n_fail == 0:
        print(f"\n\033[92m  PASS  ({n_pass}/{len(CHECK_NAMES)} checks across {len(validators)} validators)\033[0m")
        return 0
    print(f"\n\033[91m  FAIL  ({n_fail} validators missing the guard)\033[0m")
    return 1


if __name__ == "__main__":
    sys.exit(main())
