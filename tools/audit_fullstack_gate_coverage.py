"""
Full-Stack × Gate Coverage Audit (P1 roadmap 2026-05-27).
==========================================================
Enforces the coverage matrix declared in COMPREHENSIVE_STUDY_FULLSTACK_GATE.md
§4. For every (production layer, gate layer) cell marked as "covered" in the
matrix, verify the corresponding validator/spec/tool exists. If a cell that
was filled becomes blank (i.e. someone deleted a validator), FAIL.

This is the *meta-gate*: the gate that protects the architecture from
silent collapse. Without it, validators can be deleted and the matrix
becomes stale fiction.

Inputs:
  COMPREHENSIVE_STUDY_FULLSTACK_GATE.md (parses §4 matrix)
  validate_*.py                          (verifies named validators exist)
  tests/journey-*.spec.ts                (verifies named specs exist)
  tools/*.py                             (verifies named tools exist)

Output:
  fullstack_gate_coverage_report.json    (machine-readable matrix state)

Exit codes:
  0  every named artefact in the matrix exists
  1  one or more referenced artefacts missing (matrix has drifted)
  2  COMPREHENSIVE_STUDY_FULLSTACK_GATE.md missing
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
STUDY = ROOT / "COMPREHENSIVE_STUDY_FULLSTACK_GATE.md"
REPORT = ROOT / "fullstack_gate_coverage_report.json"

CHECK_NAMES = ["fullstack_gate_coverage"]

# 13 production layers (rows) × 6 gate layers (columns). The matrix is the
# canonical declaration in the study. We parse §4 to extract per-cell
# artefacts. Any artefact that doesn't exist as a file FAILs the audit.

ARTEFACT_PATTERNS = [
    # validate_X.py  → expect ROOT/validate_X.py
    (re.compile(r"`(validate_[a-z0-9_]+(?:\.py)?)`"),
     lambda name: name if name.endswith(".py") else f"{name}.py"),
    # journey-X.spec.ts → expect ROOT/tests/journey-X.spec.ts
    (re.compile(r"`(journey-[a-z0-9\-_]+(?:\.spec\.ts)?)`"),
     lambda name: f"tests/{name}" if name.endswith(".ts") else f"tests/{name}.spec.ts"),
    # tools/X.py → expect ROOT/tools/X.py
    (re.compile(r"`(tools/[a-z0-9_/]+\.py)`"),
     lambda name: name),
    # *_report.json, *_baseline.json → expect ROOT/file
    (re.compile(r"`([a-z0-9_]+(?:_report|_baseline|_manifest)\.json)`"),
     lambda name: name),
    # X.html → expect ROOT/X.html
    (re.compile(r"`([a-z0-9_-]+\.html)`"),
     lambda name: name),
    # X.json (catalog files)
    (re.compile(r"`([A-Z_]+_REGISTRY\.json|canonical_registry\.json|VALIDATOR_REGISTRY\.json|SENTINEL_REGISTRY\.json)`"),
     lambda name: name),
]

# Filter: only consider rows BETWEEN the matrix header and the first line
# after the matrix table. The matrix ends at the "Coverage tally:" line.
MATRIX_START = "## 4. The coverage matrix"
MATRIX_END   = "Coverage tally:"


def extract_matrix_artefacts(text: str) -> set[str]:
    out: set[str] = set()
    in_matrix = False
    for line in text.splitlines():
        if MATRIX_START in line:
            in_matrix = True
            continue
        if in_matrix and MATRIX_END in line:
            break
        if not in_matrix:
            continue
        for pat, build in ARTEFACT_PATTERNS:
            for m in pat.finditer(line):
                out.add(build(m.group(1)))
    return out


def main() -> int:
    if not STUDY.exists():
        print("\033[91mFAIL: COMPREHENSIVE_STUDY_FULLSTACK_GATE.md missing — the meta-gate has nothing to enforce against.\033[0m")
        return 2

    text = STUDY.read_text(encoding="utf-8", errors="replace")
    artefacts = sorted(extract_matrix_artefacts(text))

    missing: list[str] = []
    present: list[str] = []
    for a in artefacts:
        p = ROOT / a
        if p.exists():
            present.append(a)
        else:
            missing.append(a)

    report = {
        "matrix_artefacts":  len(artefacts),
        "present":           len(present),
        "missing":           len(missing),
        "missing_list":      missing,
        "present_list":      present,
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Full-stack × gate coverage audit:")
    print(f"  artefacts referenced in matrix: {len(artefacts)}")
    print(f"  present: {len(present)}")
    print(f"  missing: {len(missing)}")
    if missing:
        print(f"\n\033[91mFAIL: matrix references {len(missing)} artefact(s) that don't exist.\033[0m")
        print("These are silent gaps — the matrix promises coverage that isn't there.")
        for m in missing[:15]:
            print(f"  - {m}")
        if len(missing) > 15:
            print(f"  - ... and {len(missing) - 15} more")
        print()
        print("Either restore the artefact or update the study's §4 matrix to")
        print("remove the reference. The matrix MUST match reality.")
        return 1

    print("\n\033[92mPASS — every artefact named in the matrix exists.\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
