"""
C-track Self-Coverage Validator (SELF_IMPROVING_GATE_ROADMAP.md meta-check).
=============================================================================
The C-track of the Self-Improving Mega Gate (C1 → C2 → C5 → C3 → C4) shipped
across 6 in-session phases. Each phase added artifacts (catalogs, baselines,
ledgers, manifests, decision logs) and validators. Once the stack is in place,
the next risk is silent erosion: somebody deletes a baseline, edits a manifest
without bumping its version, or the meta-gate's decision file gets gitignored
by accident.

This meta-validator asserts the C-track stack is intact:

  1. Every C-track ARTIFACT file exists, parses as the right shape, and is
     non-empty enough to be load-bearing.
  2. Every C-track VALIDATOR script exists at the project root.
  3. Every C-track validator is REGISTERED in `run_platform_checks.py`
     (catches the "shipped but unwired" gap for these specifically).
  4. The roadmap itself is present (the architectural source of truth).

This is the C-track analogue of `validate_validator_self_coverage.py` — but
scoped to a small explicit set rather than the whole suite, so it FAILs loud
on the precise stack that took 6 phases to build.

P3 freshness anchors: when the roadmap changes the canonical name of an
artifact or validator, this check wakes (declared anchors fail the literal
match), forcing an update here before the silent rename can bury the stack.

Exit codes:
  0  every C-track artifact + validator + roadmap present and well-formed.
  1  one or more elements missing / malformed / unregistered.
"""
from __future__ import annotations
import io, json, sys, re
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent

CHECK_NAMES = ["c_track_self_coverage"]

# P3 freshness anchors — wake this validator the day the roadmap renames a
# C-track artifact or the run_platform_checks.py registration key.
FRESHNESS_ANCHORS = [
    ("SELF_IMPROVING_GATE_ROADMAP.md",  r"C4 Phase 2c",                          "Roadmap may have re-numbered phases."),
    ("run_platform_checks.py",          r"\"meta-gate\"",                        "Meta-gate validator id moved."),
    ("run_platform_checks.py",          r"\"ai-asset-versioning\"",              "AI asset validator id moved."),
]


# --- The C-track manifest ------------------------------------------------------
#
# Each entry: (key, kind, repo-relative path or registry id, optional shape check).
# kinds:
#   "json"          file must exist + parse as a JSON object/array + be non-empty.
#   "jsonl"         file must exist (one decision line per gate run; new file is OK).
#   "py"            validator script must exist at project root.
#   "registered"    validator id must appear in run_platform_checks.py VALIDATORS.
#   "roadmap"       file must exist + reference the named phase.
ARTIFACTS: list[tuple[str, str, str, dict | None]] = [
    # P1 + P6 + C1: efficacy ledger + eval splits (the verdict substrate)
    ("ledger",            "json", "gate_efficacy_ledger.json", {"required_keys": ["validators"], "min_validators": 100}),
    ("eval_splits",       "json", "gate_eval_splits.json",     {"required_keys": ["test_seal"], "min_units": 100}),
    # C5: AI asset versioning
    ("asset_baseline",    "json", "ai_asset_baseline.json",    {"required_keys": ["assets"], "min_assets": 4}),
    # C4 Phase 1 + 2a: seam catalog + contracts sidecar + coverage baseline
    ("seams_catalog",     "json", "ai_seams_catalog.json",     {"required_keys": ["seams", "ai_fns"], "min_seams": 50}),
    ("seam_contracts",    "json", "ai_seam_contracts.json",    {"required_keys": ["contracts"]}),
    ("seams_baseline",    "json", "ai_seams_baseline.json",    {"required_keys": ["seam_count"]}),
    ("coverage_baseline", "json", "ai_seam_coverage_baseline.json", {"required_keys": ["uncovered"]}),
    # C4 Phase 2c: meta-gate decision log (jsonl; empty is OK on a fresh checkout)
    ("meta_decisions",    "jsonl", "meta_gate_decisions.jsonl", None),
    # The architecture-of-record
    ("roadmap",           "roadmap", "SELF_IMPROVING_GATE_ROADMAP.md",
        {"must_reference": ["C1", "C2", "C5", "C3", "C4"]}),
]

VALIDATORS: list[tuple[str, str, str]] = [
    # (registry_id, script filename, phase label for reporting)
    ("ai-asset-versioning", "validate_ai_asset_versioning.py", "C5"),
    ("ai-eval-regression",  "validate_ai_eval_regression.py",  "C3 P1"),
    ("ai-seams-inventory",  "validate_ai_seams_inventory.py",  "C4 P1"),
    ("ai-seam-coverage",    "validate_ai_seam_coverage.py",    "C4 P2a"),
    ("meta-gate",           "validate_meta_gate.py",           "C4 P2c"),
]


# --- Helpers ------------------------------------------------------------------
def _check_json(path: Path, shape: dict | None) -> str | None:
    if not path.exists():
        return f"missing file: {path.name}"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return f"parse error: {e}"
    if not isinstance(doc, (dict, list)):
        return f"not an object/array"
    if not shape:
        return None
    if isinstance(doc, dict):
        for k in shape.get("required_keys", []):
            if k not in doc:
                return f"missing required key '{k}'"
    if (m := shape.get("min_validators")):
        n = len(doc.get("validators", {})) if isinstance(doc, dict) else 0
        if n < m:
            return f"only {n} validators (require >={m})"
    if (m := shape.get("min_units")):
        # eval_splits stores items under doc["items"] (id -> {kind, split, ...})
        # and a counts summary under doc["counts"] -> {train, val, test}.
        if isinstance(doc, dict):
            counts = doc.get("counts", {}) or {}
            total  = doc.get("total")
            if isinstance(total, int):
                n = total
            else:
                n = sum(int(v) for v in counts.values() if isinstance(v, int))
            if n < m:
                return f"only {n} units (require >={m})"
    if (m := shape.get("min_assets")):
        n = len(doc.get("assets", {})) if isinstance(doc, dict) else 0
        if n < m:
            return f"only {n} assets (require >={m})"
    if (m := shape.get("min_seams")):
        n = len(doc.get("seams", [])) if isinstance(doc, dict) else 0
        if n < m:
            return f"only {n} seams (require >={m})"
    return None


def _check_jsonl(path: Path) -> str | None:
    # jsonl just needs to exist (may be empty on a fresh checkout, but the file
    # is created on the first gate run; if it doesn't exist, the validator
    # never registered correctly).
    if not path.exists():
        return f"missing file: {path.name} (expected — created by meta-gate validator on first run)"
    return None


def _check_roadmap(path: Path, shape: dict | None) -> str | None:
    if not path.exists():
        return f"missing roadmap: {path.name}"
    text = path.read_text(encoding="utf-8")
    if shape:
        for label in shape.get("must_reference", []):
            if label not in text:
                return f"roadmap missing phase label '{label}'"
    return None


def _check_validator_registered(registry_text: str, vid: str) -> str | None:
    # Match: "id":      "vid"
    if not re.search(r'"id"\s*:\s*"' + re.escape(vid) + r'"', registry_text):
        return f"not registered in run_platform_checks.py"
    return None


# --- Main ---------------------------------------------------------------------
def main() -> int:
    errors: list[tuple[str, str]] = []   # (item_label, reason)
    ok_items: list[str] = []

    # Artifacts.
    for key, kind, rel, shape in ARTIFACTS:
        path = ROOT / rel
        if kind == "json":
            err = _check_json(path, shape)
        elif kind == "jsonl":
            err = _check_jsonl(path)
        elif kind == "roadmap":
            err = _check_roadmap(path, shape)
        else:
            err = f"unknown kind '{kind}'"
        if err:
            errors.append((f"artifact:{key}", err))
        else:
            ok_items.append(f"{key} ({rel})")

    # Validator scripts.
    for vid, script, phase in VALIDATORS:
        if not (ROOT / script).exists():
            errors.append((f"script:{vid}", f"missing {script}"))
        else:
            ok_items.append(f"validator-script:{vid} ({phase})")

    # Registry presence.
    reg_path = ROOT / "run_platform_checks.py"
    if not reg_path.exists():
        errors.append(("registry", "run_platform_checks.py missing"))
    else:
        reg_text = reg_path.read_text(encoding="utf-8")
        for vid, _script, phase in VALIDATORS:
            err = _check_validator_registered(reg_text, vid)
            if err:
                errors.append((f"registered:{vid} ({phase})", err))
            else:
                ok_items.append(f"registered:{vid} ({phase})")

    bar = "=" * 70
    print(bar)
    if errors:
        print(f"\033[91mFAIL\033[0m  C-track self-coverage: {len(errors)} problem(s)")
        for item, why in errors:
            print(f"  - {item:<40s}  {why}")
        print(bar)
        print(f"  Fix: restore the missing artifact, re-mine if it's a catalog,")
        print(f"        or re-register the validator in run_platform_checks.py.")
        return 1
    print(f"\033[92mOK\033[0m  C-track self-coverage: {len(ok_items)} items intact.")
    print(f"  {len(ARTIFACTS)} artifacts | {len(VALIDATORS)} validators | registry confirmed.")
    print(bar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
