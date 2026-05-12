"""
Tier F capture-contract regression validator
============================================
Sibling of validate_tier_c_contracts.py — but for INPUT schemas instead
of brain-output schemas.

Runs each canonical_capture_contracts.contract_schema against synthetic
good + bad payload fixtures and confirms the JSON Schema correctly
accepts/rejects each.

This is the tripwire that catches **input contract drift**: if someone
edits a capture schema (or registers a new capture) without keeping the
fixture in sync, the validator FAILs. Equivalent of the Tier C gate but
sitting at the BOTTOM of the canonical chain (Layer 0) instead of the
top (Brain outputs).

Three layers:
  L1  Every registered capture has a fixture pair
  L2  Every good fixture validates against its schema
  L3  Every bad fixture is rejected by its schema

Fixtures mirror real production form payloads:
  - logbook_add_entry_v1: 14-field add-entry form
  - inventory_add_part_v1: 10-field add-part form
  - pm_completion_v1: 6-field PM completion
  - voice_journal_capture_v1: Whisper+Groq extracted journal entry
  - qr_asset_lookup_v1: scanned QR payload "wh-asset-v1:..."

Usage:  python validate_capture_contracts.py
Output: capture_contracts_report.json
"""
from __future__ import annotations

import json
import os
import re
import sys
import glob

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    from jsonschema import Draft7Validator
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False

from validator_utils import format_result, read_file


# Fixtures: capture_id → (good_example, bad_example, why_bad)
# The bad fixture must violate the schema in a way that mirrors a real
# regression class (missing required, wrong type, invalid enum, oversize).
FIXTURES = {
    "logbook_add_entry_v1": (
        {"worker_name": "Pablo Aguilar",
         "date": "2026-05-12T14:30:00Z",
         "machine": "PMP-001",
         "category": "Mechanical",
         "maintenance_type": "Breakdown / Corrective",
         "status": "Open",
         "problem": "Bearing housing leaking oil",
         "action": "Replaced seal kit",
         "downtime_hours": 2.5},
        {"worker_name": "Pablo Aguilar", "date": "2026-05-12T14:30:00Z",
         "machine": "PMP-001",
         "category": "WrongCategory",   # invalid enum
         "maintenance_type": "Breakdown / Corrective",
         "status": "Open", "problem": "x"},
        "category enum violation — 'WrongCategory' isn't in the canonical 7-value list; dashboard filters would silently drop these rows",
    ),
    "inventory_add_part_v1": (
        {"part_number": "BRG-6203",
         "part_name": "Deep groove ball bearing 6203",
         "qty_on_hand": 12,
         "min_qty": 4,
         "bin_location": "A-3-12"},
        {"part_name": "Bearing only, no part_number"},
        "missing required part_number + qty_on_hand — would write NULL to NOT NULL columns",
    ),
    "pm_completion_v1": (
        {"asset_id": "00000000-0000-0000-0000-000000000abc",
         "worker_name": "Maria Santos",
         "completed_at": "2026-05-12T08:15:00Z",
         "status": "done",
         "notes": "All checks pass; refilled grease cups"},
        {"asset_id": "00000000-0000-0000-0000-000000000abc",
         "worker_name": "Maria Santos",
         "completed_at": "2026-05-12T08:15:00Z",
         "status": "almost_done"},     # invalid enum
        "status enum violation — 'almost_done' isn't done/skipped/partial; PM compliance computation breaks",
    ),
    "voice_journal_capture_v1": (
        {"worker_name": "Pablo Aguilar",
         "transcript": "Today I checked the chiller compressor and noticed the discharge pressure was 1450 kPa, slightly above the 1400 target.",
         "summary": "Chiller compressor running 50 kPa above target discharge pressure",
         "category": "Mechanical",
         "machine": "CH-001"},
        {"worker_name": "", "transcript": "valid transcript"},
        "empty worker_name fails minLength:1 — would create orphaned voice entries",
    ),
    "qr_asset_lookup_v1": (
        {"qr_payload": "wh-asset-v1:acme-mfg:PMP-001",
         "asset_tag": "PMP-001"},
        {"qr_payload": "https://example.com/random-url",
         "asset_tag": "PMP-001"},
        "qr_payload doesn't match wh-asset-v1: pattern — scanner accepting random URLs would break offline lookup",
    ),
}


def _extract_capture_schemas() -> dict:
    """Parse canonical_capture_contracts INSERTs across migrations and
    return contract_id -> contract_schema (latest registered)."""
    schemas: dict[str, dict] = {}
    # Quote-aware scan: walk INSERT VALUES tuples, the contract_schema is
    # column index 7 (capture_id, surface, source_page, fields, target_table,
    # target_columns, validates_at, contract_schema, consumers, notes).
    # Easier approach: extract each tuple and look for the literal '{...'
    # JSONB at column position 7.
    # Match INSERT INTO ... VALUES up to the next ON CONFLICT clause or
    # end-of-file. Avoiding `(...);` non-greedy because semicolons inside
    # SQL string literals (e.g. notes column "today; should be...") would
    # truncate the block early.
    INSERT_RE = re.compile(
        r"INSERT\s+INTO\s+(?:public\.)?canonical_capture_contracts[^;]*?\bVALUES\b([\s\S]*?)(?:\bON\s+CONFLICT\b|\Z)",
        re.IGNORECASE,
    )
    for path in sorted(glob.glob(os.path.join("supabase", "migrations", "*.sql"))):
        sql = read_file(path) or ""
        if "canonical_capture_contracts" not in sql:
            continue
        sql_clean = re.sub(r"--[^\n]*", "", sql)
        sql_clean = re.sub(r"/\*[\s\S]*?\*/", "", sql_clean)
        for m in INSERT_RE.finditer(sql_clean):
            block = m.group(1)
            for cid, schema_json in _walk_tuples_for_schema(block):
                try:
                    schemas[cid] = json.loads(schema_json)
                except (json.JSONDecodeError, TypeError):
                    pass
    return schemas


def _walk_tuples_for_schema(block: str):
    """Yield (capture_id, contract_schema_json_str) per tuple in a VALUES
    block. Quote-aware walker that:
      - tracks single-quoted strings ('' escape)
      - tracks paren depth (() inside tuples)
      - tracks bracket depth ([] inside ARRAY[...])
    Only collects strings at top-level (paren=1, bracket=0) — strings
    inside ARRAY['x','y'] are SKIPPED so the column ordering stays
    consistent.

    Top-level column order for canonical_capture_contracts:
      0=capture_id, 1=surface, 2=source_page, 3=fields_jsonb,
      4=target_table, 5=validates_at, 6=contract_schema_jsonb, 7=notes
    """
    i = 0
    n = len(block)
    while i < n:
        # Find next opening paren at top level
        while i < n and block[i] != "(":
            i += 1
        if i >= n: break
        # Walk one tuple
        strings: list[str] = []
        paren_depth = 1
        bracket_depth = 0
        i += 1
        in_str = False
        cur: list[str] = []
        str_at_top_level = True   # was this string opened at the top level?
        while i < n and paren_depth > 0:
            c = block[i]
            if in_str:
                if c == "'" and i + 1 < n and block[i + 1] == "'":
                    cur.append("'"); i += 2; continue
                if c == "'":
                    if str_at_top_level:
                        strings.append("".join(cur))
                    cur = []
                    in_str = False
                else:
                    cur.append(c)
                i += 1; continue
            if c == "'":
                in_str = True
                str_at_top_level = (paren_depth == 1 and bracket_depth == 0)
                i += 1; continue
            if c == "(": paren_depth += 1
            elif c == ")":
                paren_depth -= 1
                if paren_depth == 0:
                    i += 1; break
            elif c == "[": bracket_depth += 1
            elif c == "]": bracket_depth = max(0, bracket_depth - 1)
            i += 1

        if len(strings) >= 7:
            cid = strings[0]
            contract_schema_str = strings[6]
            if re.match(r"^[a-z_][a-z0-9_]*$", cid):
                yield (cid, contract_schema_str)


def main():
    print("\nCapture Contract Regression Validator")
    print("=" * 60)

    if not JSONSCHEMA_AVAILABLE:
        print("\033[93m  SKIP: jsonschema package not installed\033[0m")
        with open("capture_contracts_report.json", "w", encoding="utf-8") as f:
            json.dump({"validator": "capture_contracts", "skipped": "jsonschema not installed"}, f)
        sys.exit(0)

    schemas = _extract_capture_schemas()
    print(f"  {len(schemas)} captures loaded from canonical_capture_contracts migrations")
    print(f"  {len(FIXTURES)} fixture pairs defined\n")

    CHECK_NAMES  = ["fixture_coverage", "good_accepted", "bad_rejected"]
    CHECK_LABELS = {
        "fixture_coverage": "L1  Every registered capture has a fixture pair",
        "good_accepted":    "L2  Every good fixture validates against its schema",
        "bad_rejected":     "L3  Every bad fixture is rejected by its schema",
    }
    issues: list[dict] = []
    failures = {"good_accepted": [], "bad_rejected": []}

    # L1: coverage
    missing = [c for c in schemas if c not in FIXTURES]
    if missing:
        issues.append({
            "check": "fixture_coverage", "skip": False,
            "reason": f"Registered captures without fixtures: {missing}. "
                      f"Add good + bad examples to FIXTURES in validate_capture_contracts.py.",
        })

    # L2 + L3: run each fixture pair
    for capture_id, (good, bad, why) in FIXTURES.items():
        schema = schemas.get(capture_id)
        if not schema:
            print(f"  \033[93mSKIP\033[0m {capture_id} — not registered yet")
            continue
        try:
            validator = Draft7Validator(schema)
        except Exception as e:
            issues.append({
                "check": "good_accepted", "skip": False,
                "reason": f"{capture_id} schema is itself malformed: {e}",
            })
            continue
        good_errs = list(validator.iter_errors(good))
        if good_errs:
            failures["good_accepted"].append({
                "capture_id": capture_id,
                "errors": [e.message for e in good_errs[:3]],
            })
        bad_errs = list(validator.iter_errors(bad))
        if not bad_errs:
            failures["bad_rejected"].append({
                "capture_id": capture_id,
                "expected_to_fail_because": why,
            })

    if failures["good_accepted"]:
        issues.append({
            "check": "good_accepted", "skip": False,
            "reason": f"{len(failures['good_accepted'])} good fixtures rejected — schema is too strict OR fixture is wrong: "
                      f"{json.dumps(failures['good_accepted'][:3])}",
        })
    if failures["bad_rejected"]:
        issues.append({
            "check": "bad_rejected", "skip": False,
            "reason": f"{len(failures['bad_rejected'])} bad fixtures NOT rejected — schema too lenient (regression slipped through): "
                      f"{json.dumps(failures['bad_rejected'][:3])}",
        })

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":      "capture_contracts",
        "total_checks":   total,
        "passed":         n_pass,
        "warned":         n_warn,
        "failed":         n_fail,
        "n_registered":   len(schemas),
        "n_fixtures":     len(FIXTURES),
        "missing_fixtures": missing,
        "failures":       failures,
        "issues":         [i for i in issues if not i.get("skip")],
    }
    with open("capture_contracts_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
