"""validate_intelligence_jsonb_shape.py — LIVE jsonb array/object-shape gate for the
intelligence/aggregation layer (Asset Hub · Alert Hub · Shift Brain).

The asset/alert/shift pages COMPOSE from jsonb payloads and read array fields with an
`Array.isArray(x) ? x : []` guard. If a producer (or a seeder) writes a jsonb ARRAY as a
double-encoded JSON *string* (`json.dumps(list)` into a jsonb column → jsonb_typeof='string'),
the guard silently reads it as EMPTY — the staging card renders 0 parts while the rationale
says "3 parts", and alert-hub prints "0 parts recommended … 3 parts appear" (self-contradicting).
Found + fixed in the Asset/Alert/Shift arc (2026-07-12, ASSET_ALERT_SHIFT_DEEP_ARC.md F1):
seeder `test-data-seeder/seeders/parts_staging.py` did `json.dumps(parts)`; the producer
`parts-staging-recommender` correctly writes the array. Static jsonb key-drift analysis
(validate_jsonb_drift.py) can't see this — the KEYS are fine, the TYPE is wrong — so this is
a LIVE type-shape assertion.

Asserts, in the running local DB, that each intelligence-layer jsonb column that a consumer
treats as an array is actually stored as a jsonb `array` (never a `string` scalar), and each
object payload is an `object`. Skips cleanly (exit 0) when docker/db is absent or the table
has no rows (a shape assertion needs a row to inspect), matching the other *_live gates.

Exit 0 = every populated column holds the expected jsonb type (or skipped).  Exit 1 = a
column holds a string scalar (double-encoded) or the wrong container type.
"""

import sys, json, subprocess
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"; RESET = "\033[0m"; BOLD = "\033[1m"
ROOT = Path(__file__).resolve().parent.parent
DB = "supabase_db_workhive"
REPORT = ROOT / "intelligence_jsonb_shape_report.json"

# (table, column, expected jsonb_typeof, why) — each is a field a consumer reads as that shape.
CHECKS = [
    ("parts_staging_recommendations", "parts", "array",
     "asset-hub staging card + alert-hub 'N parts recommended' read Array.isArray(parts)"),
    ("anomaly_signals", "top_reasons", "array",
     "alert-hub anomaly row renders top_reasons as a list"),
    ("shift_plans", "payload", "object",
     "shift-brain reads payload.{risk_top,pms_due,carry_forward,parts_prestage} arrays"),
    ("asset_risk_scores", "top_factors", "array",
     "asset-hub/shift-brain risk factor bars iterate top_factors"),
]


def _psql(sql: str):
    """Run SQL in the local docker Postgres. Returns text output, or None if docker/db absent."""
    try:
        p = subprocess.run(
            ["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres",
             "-X", "-A", "-t", "-c", sql],
            capture_output=True, text=True, timeout=40)
        return (p.stdout or "") + (p.stderr or "")
    except Exception:
        return None


def _skip(reason: str) -> int:
    print(f"{YELLOW}  SKIP  {reason}{RESET}")
    REPORT.write_text(json.dumps({"validator": "intelligence_jsonb_shape", "skipped": True,
                                  "reason": reason}, indent=2), encoding="utf-8")
    return 0


def main() -> int:
    print(f"\n{BOLD}INTELLIGENCE JSONB SHAPE (live){RESET}")
    print("─" * 44)

    ping = _psql("SELECT 1;")
    if ping is None:
        return _skip("docker psql unavailable")

    fails = 0
    checked = 0
    results = {}
    for table, col, want, why in CHECKS:
        # Does the table/column exist? (survive schema evolution — skip a check, don't fail.)
        exists = _psql(
            f"SELECT 1 FROM information_schema.columns "
            f"WHERE table_name='{table}' AND column_name='{col}' AND data_type='jsonb' LIMIT 1;")
        if exists is None:
            return _skip("docker psql unavailable (mid-run)")
        if "1" not in exists:
            print(f"  {YELLOW}n/a {RESET}  {table}.{col}: not a jsonb column here (skipped)")
            results[f"{table}.{col}"] = "absent"
            continue

        # Count rows whose jsonb_typeof != the expected shape (ignoring SQL/JSON null).
        out = _psql(
            f"SELECT count(*) FILTER (WHERE {col} IS NOT NULL AND jsonb_typeof({col}) <> '{want}'), "
            f"count(*) FILTER (WHERE {col} IS NOT NULL) "
            f"FROM {table};")
        if out is None:
            return _skip("docker psql unavailable (probe)")
        parts = [c.strip() for c in out.strip().splitlines()[0].split("|")] if out.strip() else ["", ""]
        try:
            bad, populated = int(parts[0] or 0), int(parts[1] or 0)
        except ValueError:
            print(f"  {YELLOW}n/a {RESET}  {table}.{col}: unreadable count (skipped)")
            continue

        if populated == 0:
            print(f"  {YELLOW}n/a {RESET}  {table}.{col}: no populated rows to shape-check (skipped)")
            results[f"{table}.{col}"] = "empty"
            continue

        checked += 1
        if bad == 0:
            print(f"  {GREEN}PASS{RESET}  {table}.{col}: all {populated} rows are jsonb '{want}'  ({why})")
            results[f"{table}.{col}"] = {"ok": True, "populated": populated}
        else:
            fails += 1
            # Identify the wrong types actually present, for the failure message.
            types = _psql(
                f"SELECT DISTINCT jsonb_typeof({col}) FROM {table} "
                f"WHERE {col} IS NOT NULL AND jsonb_typeof({col}) <> '{want}';")
            got = ", ".join(sorted(t.strip() for t in (types or "").splitlines() if t.strip()))
            print(f"  {RED}FAIL{RESET}  {table}.{col}: {bad}/{populated} rows are NOT jsonb '{want}' "
                  f"(found: {got or '?'}) — double-encoded/mis-shaped payload; consumer reads it as empty")
            results[f"{table}.{col}"] = {"ok": False, "bad": bad, "populated": populated, "got": got}

    if checked == 0:
        return _skip("no populated intelligence jsonb columns to shape-check")

    print(f"\n  Summary: {checked - fails} pass · {fails} fail  (of {checked} populated columns checked)")
    REPORT.write_text(json.dumps({"validator": "intelligence_jsonb_shape", "skipped": False,
                                  "fail": fails, "results": results}, indent=2), encoding="utf-8")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
