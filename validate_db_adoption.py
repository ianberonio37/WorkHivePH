"""
API-Adoption Ratchet (L0) — FULLSTACK_COMPONENT_LIBRARY_ROADMAP Layer D, D-P2.
================================================================================
The Layer-A instantiation of the forward-only adoption ratchet proven on Layer F
(validate_component_adoption.py). Canonical `_shared/` module adoption per
db_component_registry.json row, recomputed LIVE over the substrate's live-DB-derived chunks (never a stale report):

  A1  ADOPTION FLOOR (FAIL) — live adopter count >= the floor in
      db_adoption_baseline.json for every measured row. A function dropping
      its RLS/policy/invoker pattern is a regression.
  A2  AUTO-TIGHTEN — adoption above the floor re-baselines UPWARD.
  A3  REGISTRY INTEGRITY (FAIL) — floors ↔ measured registry rows match 1:1;
      retiring a module = an explicit registry+floors edit in one change.

Exemptions live in the registry with documented reasons (voice-model-call =
deprecated orphan; the 4 fixed-endpoint outbound fns — see A6's triage test).

Output: db_adoption_gate_report.json (+ rewrites db_adoption_baseline.json on
tighten; floors only ever rise from ANY writer). Exit 1 on A1/A3, else 0.
"""
from __future__ import annotations

import datetime
import io
import json
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
from db_adoption_census import run_census  # noqa: E402

BASELINE = ROOT / "db_adoption_baseline.json"
REPORT = ROOT / "db_adoption_gate_report.json"


def write_baseline(rows, n_fns):
    measured = [r for r in rows if r["mode"] == "measured"]
    prior = {}
    if BASELINE.exists():
        try:
            prior = json.loads(BASELINE.read_text(encoding="utf-8")).get("floors", {})
        except Exception:
            prior = {}
    floors = {r["id"]: max(r["adopters_n"], prior.get(r["id"], 0)) for r in measured}
    BASELINE.write_text(json.dumps({
        "_doc": "Layer D adoption baseline. Floors are FORWARD-ONLY from any writer (Layer F law).",
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "surfaces": n_fns, "rows": rows, "floors": floors,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    rows, n_t, n_v = run_census()
    n_fns = n_t + n_v
    measured = {r["id"]: r for r in rows if r["mode"] == "measured"}
    failures: list[str] = []
    tightened: list[str] = []

    if not BASELINE.exists():
        write_baseline(rows, n_fns)
        print(f"db-adoption: first run — baseline created ({len(measured)} floors). PASS")
        return 0

    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    floors: dict = base.get("floors", {})
    base_rows = {r["id"]: r for r in base.get("rows", []) if r.get("mode") == "measured"}

    for cid in floors:
        if cid not in measured:
            failures.append(f"A3: floor '{cid}' has NO registry row (module deleted/renamed without explicit re-baseline)")
    for cid, r in measured.items():
        floor = floors.get(cid)
        if floor is None:
            tightened.append(f"{cid} (new row, floor={r['adopters_n']})")
            continue
        if r["adopters_n"] < floor:
            lost = sorted(set(base_rows.get(cid, {}).get("adopters", [])) - set(r["adopters"]))
            failures.append(f"A1: {cid} ({r['name']}) adoption fell {floor} -> {r['adopters_n']}"
                            + (f" — dropped by: {', '.join(lost[:6])}" if lost else ""))
        elif r["adopters_n"] > floor:
            tightened.append(f"{cid} {floor} -> {r['adopters_n']}")

    ok = not failures
    if ok:
        write_baseline(rows, n_fns)

    REPORT.write_text(json.dumps({
        "ok": ok, "checked": len(measured), "failures": failures, "tightened": tightened,
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"db-adoption: {len(measured)} measured rows"
          + (f", tightened {len(tightened)}" if tightened else ""))
    for f in failures:
        print(f"  FAIL {f}")
    print("  " + ("PASS (forward-only floors held)" if ok else f"{len(failures)} FAILURE(S)"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
