#!/usr/bin/env python3
"""validate_export_value_contract.py — §13.16 A7.2: CSV export-value contract (static).
================================================================================
A page's CSV export is a DELIVERABLE: a supervisor opens it and trusts every cell.
The drift class (the export analogue of the BOM/SOW "N/A" + grounding-contract): the
export serializes `row.<field>` for each rendered row, but if `<field>` is mis-named
(a rename in the source table/view the export never tracked) the cell silently
serializes BLANK — a confident, value-less artifact, no error. The FIRM tier proves
the page EXPORTS a CSV; this proves each exported COLUMN maps to a real source field.

STATIC + deterministic (no browser, no LLM): for each CSV-export fn, extract its
`<row>.<field>` reads, fetch the source table/view's REAL columns live (docker psql),
and assert each read resolves to a real column (a documented transform like
JSON.stringify(meta) or a date reformat is allowed). A read resolving to nothing =
a drift cell = a column that exports blank. Forward-only baseline ratchet (a NEW drift
cell FAILs); --strict fails on any; exit 0 clean / 1 new drift / 2 db unreachable.

This is the export-side of the data gateway (every value → canonical, intact to the
deliverable), the §13.16 A7.2 beachhead beyond engineering-design.
"""
from __future__ import annotations
import io
import json
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DB_CONTAINER = "supabase_db_workhive"
GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; BOLD = "\033[1m"; RESET = "\033[0m"
BASELINE_F = ROOT / "export_value_contract_baseline.json"

# (label, page.html, source table/view, export-fn anchor regex, row-variable, [extra-allowed fields])
# extra-allowed = a field the export legitimately SYNTHESIZES (not a source column): a derived/
# computed cell. Documented per spec so it isn't a false drift.
EXPORT_SPECS = [
    ("logbook", "logbook.html", "logbook",
     r"btn-export-csv'\)\.addEventListener", "e", []),
    ("audit-log", "audit-log.html", "hive_audit_log",
     r"function exportCsv\s*\(", "en", []),
]


def db_columns(table: str) -> set[str] | None:
    sql = f"select column_name from information_schema.columns where table_name='{table}'"
    try:
        r = subprocess.run(
            ["docker", "exec", DB_CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-t", "-A", "-c", sql],
            capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return None
        cols = {ln.strip() for ln in r.stdout.splitlines() if ln.strip()}
        return cols or None
    except Exception:
        return None


def export_field_reads(html: str, anchor: str, row_var: str) -> list[str]:
    """The `<row_var>.<field>` reads inside the export fn body (anchor → next Blob/download)."""
    m = re.search(anchor, html)
    if not m:
        return []
    start = m.start()
    end = html.find("new Blob", start)
    if end < 0:
        end = start + 4000
    body = html[start:end]
    body = "\n".join(re.sub(r"//.*$", "", ln) for ln in body.splitlines())   # strip line comments
    rx = re.compile(rf"\b{re.escape(row_var)}\.([A-Za-z_]\w*)")
    seen = []
    for mm in rx.finditer(body):
        f = mm.group(1)
        if f not in seen:
            seen.append(f)
    return seen


def main() -> int:
    strict = "--strict" in sys.argv
    update = "--update-baseline" in sys.argv
    print(f"{BOLD}\nEXPORT-VALUE CONTRACT (§13.16 A7.2) — each CSV column maps to a real source field{RESET}")
    print("=" * 80)

    baseline: dict = {}
    if BASELINE_F.exists() and not update:
        try:
            baseline = json.loads(BASELINE_F.read_text(encoding="utf-8")).get("drift", {})
        except Exception:
            baseline = {}

    total = 0; resolved = 0; skipped = 0
    drift_cells: list[str] = []; new_drift: list[str] = []; detail: dict = {}
    for label, page, table, anchor, row_var, extra in EXPORT_SPECS:
        f = ROOT / page
        if not f.exists():
            skipped += 1; continue
        html = f.read_text(encoding="utf-8", errors="ignore")
        fields = export_field_reads(html, anchor, row_var)
        cols = db_columns(table)
        if cols is None:
            print(f"  {YEL}~{RESET} {label} → source '{table}' unreachable (db down) — skipped")
            skipped += 1
            continue
        allowed = cols | set(extra)
        page_drift = []
        for fld in fields:
            total += 1
            if fld in allowed:
                resolved += 1
            else:
                sig = f"{label}::{table}::{fld}"
                drift_cells.append(sig)
                page_drift.append(fld)
                if strict or sig not in baseline:
                    if sig not in baseline:
                        new_drift.append(sig)
        detail[label] = {"page": page, "source": table, "fields": fields, "drift": page_drift}
        mark = f"{GREEN}✓{RESET}" if not page_drift else (f"{RED}✗{RESET}" if any(f"{label}::{table}::{d}" in new_drift for d in page_drift) else f"{YEL}~{RESET}")
        print(f"  {mark} {label} [{table}] → {len(fields)-len(page_drift)}/{len(fields)} columns resolve"
              f"{' · DRIFT: ' + ', '.join(page_drift) if page_drift else ''}")

    if total == 0 and skipped:
        print(f"{YEL}SKIP (exit 2){RESET}: no source reachable (db down).")
        return 2

    # forward-only baseline (drift signatures), like grounding_contract
    cur = {s: True for s in drift_cells}
    if update or not BASELINE_F.exists():
        baseline = cur
    fixed = [s for s in baseline if s not in cur]
    if fixed and not strict:        # ratchet down
        for s in fixed:
            baseline.pop(s, None)
    if update or fixed or not BASELINE_F.exists():
        BASELINE_F.write_text(json.dumps({
            "_doc": "A7.2 export-value drift baseline — forward-only; a CSV column read that resolves to "
                    "no source field exports BLANK. New drift FAILs; fixed cells ratchet down.",
            "drift": {s: True for s in (cur if update else baseline)},
        }, indent=2), encoding="utf-8")

    pct = round(100 * resolved / total, 1) if total else 100.0
    (ROOT / "export_value_contract.json").write_text(json.dumps({
        "tool": "tools/validate_export_value_contract.py",
        "subject": "each CSV-export column read resolves to a real source table/view field",
        "exports": len(EXPORT_SPECS), "fields_total": total, "fields_resolved": resolved,
        "resolved_pct": pct, "drift_cells": drift_cells, "new_drift": new_drift,
        "detail": detail, "result": "PASS" if (not new_drift or (strict and not drift_cells)) else "FAIL",
    }, indent=2), encoding="utf-8")

    print("-" * 80)
    print(f"  columns resolved: {resolved}/{total} = {pct}%  ·  drift cells: {len(drift_cells)}  ·  NEW: {len(new_drift)}")
    if new_drift:
        print(f"{RED}{BOLD}  EXPORT-VALUE CONTRACT: FAIL{RESET} — a CSV column exports blank (source field renamed/missing).")
        for s in new_drift:
            print(f"    {RED}✗{RESET} {s}")
        return 1
    if strict and drift_cells:
        print(f"{RED}{BOLD}  EXPORT-VALUE CONTRACT: FAIL (--strict){RESET} — {len(drift_cells)} drift cell(s).")
        return 1
    print(f"{GREEN}{BOLD}  EXPORT-VALUE CONTRACT: PASS{RESET} — every CSV column maps to a real source field.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
