"""
Canonical Overlap Validator -- Layer 2 of the Canonical-Registry triad
======================================================================
The L-1 Canonical Registry (`tools/mine_canonical_registry.py`) walks
the codebase and produces `canonical_registry.json` containing
`duplicate_signals`: surface-pair overlaps (Jaccard >= 0.5), near-
duplicate column pairs, dead tables, and phantom tables.

This validator wraps those signals in a Mega Gate check:

  L1  Phantom tables                       [FAIL]
      Any table referenced in HTML / edge fn code but never defined
      in any migration. These are real `relation does not exist` bugs.

  L2  Undocumented surface-pair overlap    [FAIL]
      Any surface pair with Jaccard >= 0.5 NOT in
      `canonical_overlap_allowlist.json` `overlaps`. New duplicates get
      blocked at the gate; the dev must either consolidate or document
      the overlap as a role-view in the allowlist.

  L3  Undocumented near-duplicate columns  [WARN/SKIP]
      Pairs flagged by the registry that aren't in the allowlist
      `near_duplicate_columns`. Doesn't fail the gate, but surfaces.

  L4  Dead-table census                    [INFO]
      Defined-but-unreferenced tables. Informational -- pure
      observability, never blocks.

  L5  Allowlist freshness                  [WARN/SKIP]
      Any allowlist entry where the overlap NO LONGER exists in the
      current registry (the surfaces changed). Time to clean up.

How to add a new legitimate overlap:
  1. Open `canonical_overlap_allowlist.json`
  2. Add an entry to `overlaps` with surfaces + reason + reviewed date
  3. Re-run -- the validator now treats it as documented and passes

Skills consulted: architect (canonical-source doctrine), qa-tester (allowlist
freshness pattern from validate_loads_utils_js).
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import format_result


ROOT = Path(__file__).resolve().parent
REGISTRY_PATH  = ROOT / "canonical_registry.json"
ALLOWLIST_PATH = ROOT / "canonical_overlap_allowlist.json"
REPORT_PATH    = ROOT / "canonical_overlap_report.json"


def _normalize_pair(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted([a, b]))


def _load() -> tuple[dict, dict]:
    if not REGISTRY_PATH.exists():
        print(f"  Registry not found at {REGISTRY_PATH.name} -- run tools/mine_canonical_registry.py first.")
        sys.exit(2)
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    allowlist = {"overlaps": [], "near_duplicate_columns": []}
    if ALLOWLIST_PATH.exists():
        allowlist = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    return registry, allowlist


def check() -> tuple[list, dict]:
    registry, allowlist = _load()
    issues = []

    # Build allowlist sets for fast lookup.
    allowed_overlaps = {
        _normalize_pair(*entry["surfaces"])
        for entry in allowlist.get("overlaps", [])
        if len(entry.get("surfaces", [])) == 2
    }
    allowed_near_dup_cols = {
        (entry["table"], tuple(sorted(entry["columns"])))
        for entry in allowlist.get("near_duplicate_columns", [])
        if "table" in entry and len(entry.get("columns", [])) == 2
    }

    signals = registry.get("duplicate_signals", [])
    phantom_tables = registry.get("phantom_tables", {})

    # L1: phantom tables (real bugs).
    for tname, info in phantom_tables.items():
        refs = info.get("read_by_surfaces", []) + info.get("read_by_edge_fns", []) + \
               info.get("written_by_surfaces", []) + info.get("written_by_edge_fns", [])
        issues.append({
            "check": "phantom_table",
            "reason": f"`{tname}` referenced in code but NOT defined in any migration. "
                      f"Referenced by: {', '.join(refs[:5])}. Either fix the table name, "
                      f"add a migration that creates it, or remove the dead reference.",
        })

    # L2: undocumented surface overlaps.
    surface_overlaps_seen = set()
    undocumented_overlaps = []
    for sig in signals:
        if sig.get("kind") != "surface_overlap":
            continue
        pair = _normalize_pair(sig["surface_a"], sig["surface_b"])
        surface_overlaps_seen.add(pair)
        if pair not in allowed_overlaps:
            undocumented_overlaps.append(sig)
            issues.append({
                "check": "documented_overlap",
                "reason": (
                    f"NEW surface-pair overlap: `{sig['surface_a']}` and `{sig['surface_b']}` "
                    f"share {len(sig['shared_tables'])} tables (Jaccard {sig['jaccard']}). "
                    f"Shared: {', '.join(sig['shared_tables'][:5])}. "
                    f"Either consolidate the surfaces, OR add to "
                    f"`canonical_overlap_allowlist.json` with a documented reason."
                ),
            })

    # L3: undocumented near-duplicate columns.
    undocumented_near_dup = []
    for sig in signals:
        if sig.get("kind") != "near_duplicate_column":
            continue
        key = (sig["table"], tuple(sorted(sig["columns"])))
        if key not in allowed_near_dup_cols:
            undocumented_near_dup.append(sig)
            issues.append({
                "check": "documented_column_pair",
                "skip":  True,  # WARN, not FAIL
                "reason": (
                    f"Near-duplicate columns in `{sig['table']}`: "
                    f"`{sig['columns'][0]}` vs `{sig['columns'][1]}`. "
                    f"If intentional (e.g., bool/timestamp pair), document in "
                    f"`canonical_overlap_allowlist.json` `near_duplicate_columns`."
                ),
            })

    # L4: dead tables (informational only -- the registry's count is the signal).
    dead_table_count = sum(1 for s in signals if s.get("kind") == "dead_table")

    # L5: allowlist freshness -- entries that are no longer real overlaps.
    stale_allowlist = []
    for entry in allowlist.get("overlaps", []):
        if len(entry.get("surfaces", [])) != 2:
            continue
        pair = _normalize_pair(*entry["surfaces"])
        if pair not in surface_overlaps_seen:
            stale_allowlist.append(entry)
            issues.append({
                "check": "allowlist_freshness",
                "skip":  True,
                "reason": (
                    f"Allowlist entry [{entry['surfaces'][0]} <-> {entry['surfaces'][1]}] "
                    f"no longer matches a real overlap in the registry. "
                    f"Either the surfaces changed or one was retired. "
                    f"Remove the entry from canonical_overlap_allowlist.json."
                ),
            })

    census = {
        "phantom_tables":             len(phantom_tables),
        "surface_overlaps_total":     len(surface_overlaps_seen),
        "surface_overlaps_allowlisted": len(allowed_overlaps & surface_overlaps_seen),
        "surface_overlaps_undocumented": len(undocumented_overlaps),
        "near_dup_cols_total":        sum(1 for s in signals if s.get("kind") == "near_duplicate_column"),
        "near_dup_cols_allowlisted":  len(allowed_near_dup_cols),
        "near_dup_cols_undocumented": len(undocumented_near_dup),
        "dead_tables":                dead_table_count,
        "stale_allowlist_entries":    len(stale_allowlist),
    }
    return issues, census


CHECK_NAMES = [
    "phantom_table",
    "documented_overlap",
    "documented_column_pair",
    "allowlist_freshness",
]
CHECK_LABELS = {
    "phantom_table":          "L1  No phantom tables (refs in code but undefined in migrations)",
    "documented_overlap":     "L2  Every surface-pair overlap is in canonical_overlap_allowlist.json",
    "documented_column_pair": "L3  Near-duplicate column pairs are documented (warn-only)",
    "allowlist_freshness":    "L5  Allowlist entries still match real overlaps (warn-only)",
}


def main() -> int:
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nCanonical Overlap Validator (L-1 Layer 2)"))
    print("=" * 55)
    issues, census = check()
    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    print("\nCensus:")
    for k, v in census.items():
        print(f"  {k:<32} {v}")

    report = {"census": census, "issues": issues}
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if n_fail == 0:
        print(f"\n\033[92m  PASS  ({n_pass}/{len(CHECK_NAMES)} checks)\033[0m")
        return 0
    print(f"\n\033[91m  FAIL  ({n_fail} issues -- see above)\033[0m")
    return 1


if __name__ == "__main__":
    sys.exit(main())
