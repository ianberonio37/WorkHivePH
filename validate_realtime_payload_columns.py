"""
Realtime Payload Column Validator (L0, ratcheted).
===================================================
Sibling to validate_realtime_subscription_consistency.py. That one
checks the SUBSCRIBED TABLE is real and read by the page. This one
goes deeper:

  For each `.on('postgres_changes', { table: T }, (payload) => { ... })`
  callback body, every `payload.new.<col>` and `payload.old.<col>`
  reference must be a column that actually exists on table T.

Caught the related class 2026-05-20: hive.html had
`payload.new.asset_id` in its asset-approval callback, but the
subscribed table is `asset_nodes` whose column is `tag` (not
`asset_id`). The toast would say "Your asset undefined was approved"
because asset_id is undefined on the payload.

Detection
  1. Find every `.on('postgres_changes', { ... table: 'T' ... }, callback)`
     site. Extract T and the callback body up to the matching closing
     paren (callback can span 30+ lines).
  2. Inside the callback body, find every `payload.new.COL` /
     `payload.old.COL` reference.
  3. Look up T in canonical_registry.json → its columns set.
  4. For each COL not in the set:
     - If COL is a JS-reserved property (`length`, `toString`, `valueOf`),
       skip — Postgres rows don't expose these.
     - Otherwise flag as DRIFT.

  Tolerated patterns: `payload.new.A || payload.new.B` is fine if
  EITHER A or B is a real column (the writer is being defensive about
  schema transitions). This validator counts it as OK when at least
  one alternative is a real column.

Allow markers
  Inline `// payload-column-allow: <reason>` near the callback.

Output
  realtime_payload_columns_report.json
  Exit 1 when drift > baseline; 0 otherwise.
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path


if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "realtime_payload_columns_report.json"
BASELINE_PATH = ROOT / "realtime_payload_columns_baseline.json"


PAGES = [
    "index.html", "hive.html", "logbook.html", "inventory.html",
    "pm-scheduler.html", "analytics.html", "analytics-report.html",
    "skillmatrix.html", "community.html", "public-feed.html",
    "marketplace.html", "marketplace-seller.html", "dayplanner.html",
    "engineering-design.html", "assistant.html", "report-sender.html",
    "platform-health.html", "project-manager.html", "integrations.html",
    "ph-intelligence.html", "project-report.html", "predictive.html",
    "ai-quality.html", "plant-connections.html", "achievements.html",
    "asset-hub.html", "shift-brain.html", "alert-hub.html",
    "audit-log.html", "voice-journal.html",
]

# JS object properties that aren't DB columns
JS_RESERVED = {
    "length", "toString", "valueOf", "constructor", "hasOwnProperty",
    "isPrototypeOf", "propertyIsEnumerable", "__proto__",
}

# Universal columns Postgres always exposes via realtime (we tolerate them
# even if not explicitly in the table's column list — they're always there)
UNIVERSAL_COLUMNS = {
    "id", "created_at", "updated_at", "inserted_at", "deleted_at",
    "user_id", "auth_uid", "hive_id",
}

# Pattern: `.on('postgres_changes', { ... table: 'X' ... }, <callback>)`
# We find the `.on(` site, walk forward to find the closing `)` matching
# the open `(`, and split into config object + callback body.
ON_RE = re.compile(r"\.on\(\s*['\"`]postgres_changes['\"`]\s*,\s*\{")

TABLE_FIELD_RE = re.compile(r"""\btable\s*:\s*['"`](?P<table>[a-z_][\w]*)['"`]""")

# `payload.new.COL` or `payload.old.COL`
PAYLOAD_COL_RE = re.compile(r"""\bpayload\.(?:new|old)\.(?P<col>[a-z_][\w]*)\b""")

ALLOW_RE = re.compile(r"payload-column-allow", re.IGNORECASE)
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")


def _walk_to_matching(body: str, start: int, open_ch: str = "(", close_ch: str = ")") -> int:
    """Walk forward from `start` (positioned at an open_ch) to find the
    matching close_ch. Returns position AFTER the close_ch, or len(body)."""
    depth = 0
    i = start
    while i < len(body):
        ch = body[i]
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(body)


def _bold(s):   return f"\033[1m{s}\033[0m"
def _red(s):    return f"\033[91m{s}\033[0m"
def _green(s):  return f"\033[92m{s}\033[0m"
def _yellow(s): return f"\033[93m{s}\033[0m"


def main() -> int:
    reg_path = ROOT / "canonical_registry.json"
    if not reg_path.exists():
        print("FAIL: canonical_registry.json missing")
        return 2
    reg = json.loads(reg_path.read_text(encoding="utf-8"))

    # Build (table_name → set of columns) lookup
    table_cols: dict[str, set[str]] = {}
    for tname, meta in reg.get("tables", {}).items():
        cols = meta.get("columns", [])
        if isinstance(cols, list):
            table_cols[tname.lower()] = {c.lower() for c in cols}
        elif isinstance(cols, str):
            table_cols[tname.lower()] = {c.strip().lower() for c in cols.split(",") if c.strip()}

    per_page: list[dict] = []
    total_drift = 0
    total_refs  = 0

    for name in PAGES:
        page = ROOT / name
        if not page.exists():
            continue
        try:
            raw = page.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        body = HTML_COMMENT_RE.sub("", raw)

        drift: list[dict] = []

        # Find each .on('postgres_changes', { ... }, callback) site
        for m in ON_RE.finditer(body):
            # Position of the open `(` of the .on(
            paren_open = body.rfind("(", 0, m.end())
            # Walk to matching close paren — that's the end of the .on(...) call
            call_end = _walk_to_matching(body, paren_open, "(", ")")

            # Inside: parse out the config object's table field
            on_block = body[m.start():call_end]
            tm = TABLE_FIELD_RE.search(on_block)
            if not tm:
                continue
            table = tm.group("table").lower()

            # Allow window
            win = body[max(0, m.start() - 300):m.end() + 300]
            if ALLOW_RE.search(win):
                continue

            # Extract payload.new.X / payload.old.X references inside the
            # callback portion (we treat the whole .on call body as scope).
            # Group by column reference; defer "tolerated alternative" check.
            refs = list(PAYLOAD_COL_RE.finditer(on_block))
            total_refs += len(refs)

            # Get the table's column set
            cols = table_cols.get(table, set())

            # If table isn't in registry, skip (validate_realtime_subscription
            # already catches subscribe-to-nonexistent-table case differently).
            if not cols:
                continue

            # Tolerated alternative: when the same payload.X is written as
            # `payload.new.A || payload.new.B`, accept if at least one of
            # {A, B} is in the column set. We approximate by, for each col
            # reference, checking the ±60-char window for ANOTHER payload ref
            # that IS valid.
            for ref_m in refs:
                col = ref_m.group("col").lower()
                if col in cols or col in UNIVERSAL_COLUMNS or col in JS_RESERVED:
                    continue
                # Tolerated alternative scan
                local_window = on_block[max(0, ref_m.start() - 80):ref_m.end() + 80]
                local_refs = PAYLOAD_COL_RE.findall(local_window)
                if any(r.lower() in cols or r.lower() in UNIVERSAL_COLUMNS for r in local_refs):
                    continue
                drift.append({
                    "table":  table,
                    "column": col,
                    "char_offset": m.start() + ref_m.start(),
                })

        per_page.append({"page": name, "drift": drift})
        total_drift += len(drift)

    # Baseline ratchet
    baseline = 0
    if BASELINE_PATH.exists():
        try:
            baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("drift", 0)
        except Exception:
            baseline = 0
    else:
        baseline = total_drift
        BASELINE_PATH.write_text(
            json.dumps({"drift": baseline, "established": True}, indent=2),
            encoding="utf-8",
        )

    if total_drift < baseline:
        baseline = total_drift
        BASELINE_PATH.write_text(
            json.dumps({"drift": baseline, "tightened": True}, indent=2),
            encoding="utf-8",
        )

    report = {
        "summary": {
            "pages_scanned":   len(per_page),
            "total_refs":      total_refs,
            "total_drift":     total_drift,
            "baseline":        baseline,
        },
        "per_page": per_page,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print()
    print(_bold("Realtime Payload Column Validator (L0)"))
    print("=" * 56)
    print(f"  pages scanned:           {len(per_page)}")
    print(f"  payload.* references:    {total_refs}")
    print(f"  drift:                   {total_drift}  (baseline: {baseline})")

    if total_drift == 0:
        print()
        print(_green("PASS — every payload.new/old.X column is real on the subscribed table."))
        return 0

    print()
    print("Drift candidates:")
    for entry in per_page:
        if not entry["drift"]:
            continue
        print(f"  {entry['page']}")
        for d in entry["drift"]:
            print(f"    table='{d['table']}'  payload.X='{d['column']}'  (not a column)")

    if total_drift > baseline:
        print()
        print(_red(f"FAIL — drift {total_drift} > baseline {baseline}"))
        print("Fix options:")
        print("  1. Update the payload.X reference to the actual column name.")
        print("  2. Defensive read: `payload.new.A || payload.new.B` if migrating.")
        print("  3. Add `// payload-column-allow: <reason>` near the .on() call.")
        return 1

    print()
    print(_yellow(f"At baseline ({baseline}) — punch list above; tighten by fixing one."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
