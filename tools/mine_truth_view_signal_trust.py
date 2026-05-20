"""
Truth-View Signal-Trust Miner (Layer -1).
==========================================
Sister to mine_canonical_drift_platform.py. That miner catches when two
surfaces read DIFFERENT sources for the same KPI. This miner catches
the next class: two surfaces read the SAME canonical column but
INTERPRET it differently before display.

The 2026-05-20 bug:
  - hive.html reads v_pm_scope_items_truth.is_overdue, counts true → 21.
  - pm-scheduler.html reads v_pm_scope_items_truth.is_overdue but ALSO
    checks next_due_date; if next_due_date is null it tags 'nodata' and
    drops the row → 0.
  Same view, same column, different filter, different number.

Detection
  For every consumer of `db.from('v_<...>_truth').select(...)`, extract:
    1. The list of columns the consumer projects from that view.
    2. For each `is_*` boolean / status-flag column, the AST-ish shape
       of how it's used:
         direct        item.is_overdue                  trust signal
         and_other     item.is_overdue && item.other    re-gating (anti-pattern)
         ternary_pure  item.is_overdue ? A : B          trust signal
         ternary_or    item.next_due_date ? ... :       skip when other field null
                       (item.is_overdue inside this gate is `gated-by-other`)

  If two consumers of the same `(view, column)` pair have DIFFERENT
  usage shapes, the (view, column) row is flagged AT_RISK.

Output
  truth_view_signal_trust_report.json     machine
  truth_view_signal_trust_report.md       human punch list

Exit code: 0 if no AT_RISK pairs; 1 otherwise (gate failure).
"""
from __future__ import annotations

import io
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent.parent


# Match `db.from('v_<name>_truth')` then scan ahead for the next .select(...)
# (the chain often spans multiple lines, so we extract in two passes).
FROM_TRUTH_RE = re.compile(
    r"""\.from\(\s*['"](?P<view>v_[a-z0-9_]+_truth)['"]\s*\)""",
    re.IGNORECASE,
)
SELECT_RE = re.compile(
    r"""\.select\(\s*['"`](?P<cols>[^'"`]+)['"`]""",
    re.DOTALL,
)

# Columns we always skip — pure plumbing / FKs / timestamps that consumers
# legitimately use however they want.
PLUMBING_COLS = {
    "id", "hive_id", "user_id", "auth_uid", "created_at", "updated_at",
    "inserted_at", "deleted_at",
}

# "Smell" patterns inside a consumer that suggest local re-derivation of
# something the canonical view should already expose. Each smell is a
# (label, regex) pair; the regex runs against the file body.
LOCAL_MATH_SMELLS: list[tuple[str, re.Pattern]] = [
    ("re_computes_overdue",
     re.compile(r"(Date\.now\(\)|new Date\(\))\s*[-<>]\s*new Date\(\s*\w+\.(last_completed|completed_at|next_due)")),
    ("hardcoded_freq_days",
     re.compile(r"\bFREQ_DAYS\s*\[|\bcalcNextDue\s*\(|\bgetItemStatus\s*\(")),
    ("manual_qty_threshold",
     re.compile(r"\bqty_on_hand\b[^;\n]*<\s*\w+\.reorder_point|qty_on_hand\s*<=\s*reorder_point")),
    ("manual_risk_band",
     re.compile(r"\brisk_score\b[^;\n]*[<>]=?\s*(?:60|70|80|90)|\bscore\s*[<>]=?\s*(?:60|70|80|90)")),
    ("manual_age_days",
     re.compile(r"\bdays_until\s*\(|\bdaysUntil\s*\(|Math\.floor\(\s*\(\s*now\s*-\s*\w+\.\w+\s*\)\s*/\s*86400000")),
    ("nodata_fallback",
     re.compile(r"['\"]nodata['\"]")),
]


def _strip_html_comments(t: str) -> str:
    return re.sub(r"<!--[\s\S]*?-->", "", t)


def _strip_js_comments(t: str) -> str:
    out = re.sub(r"/\*[\s\S]*?\*/", "", t)
    out = re.sub(r"^[ \t]*//[^\n]*$", "", out, flags=re.MULTILINE)
    return out


def _gather_files() -> dict[str, str]:
    blobs: dict[str, str] = {}
    for p in sorted(ROOT.glob("*.html")):
        if ".backup" in p.name or p.name.endswith("-test.html"):
            continue
        blobs[p.name] = _strip_html_comments(p.read_text(encoding="utf-8", errors="replace"))
    for subdir in sorted(ROOT.iterdir()):
        if not subdir.is_dir() or subdir.name.startswith(".") or subdir.name in {
            "node_modules", "test-results", "playwright-report", ".tmp",
            "supabase", "tools", "python-api", "tests",
        }:
            continue
        for p in sorted(subdir.rglob("*.html")):
            rel = p.relative_to(ROOT).as_posix()
            blobs[rel] = _strip_html_comments(p.read_text(encoding="utf-8", errors="replace"))
    for p in sorted(ROOT.glob("*.js")):
        if p.name == "sw.js":
            continue
        blobs[p.name] = _strip_js_comments(p.read_text(encoding="utf-8", errors="replace"))
    edge = ROOT / "supabase" / "functions"
    if edge.exists():
        for ts in sorted(edge.rglob("*.ts")):
            rel = ts.relative_to(ROOT).as_posix()
            blobs[rel] = _strip_js_comments(ts.read_text(encoding="utf-8", errors="replace"))
    return blobs


def _extract_cols(select_str: str) -> list[str]:
    """Pull bare column names from a .select() projection. Handles
    `col` and `alias:col` and trims whitespace/newlines."""
    cols = []
    for raw in select_str.split(","):
        token = raw.strip()
        if not token:
            continue
        # `alias:col_name` → use col_name (the real column)
        if ":" in token:
            token = token.split(":", 1)[1].strip()
        # Strip any function call like count(*) — leave as-is
        m = re.match(r"^([a-z_][\w]*)", token, re.IGNORECASE)
        if m:
            cols.append(m.group(1).lower())
    return cols


def _classify_usage(code: str, col: str) -> str:
    """Return the dominant shape of how `col` is used in the file's body.

    Heuristics (first match wins):
      gated_by_other  - inside `if (X.OTHER) { ... item.COL ... } else { ... 'nodata' ... }`
                        where OTHER comes from the same `_truth` view's select list
                        (we approximate: any `next_due_date` / `next_*` / `last_*` gate)
      direct          - `r.COL` / `item.COL` / `.COL` used unconditionally
                        or in `filter(r => r.COL)` / `if (r.COL)`
      mapped_enum     - `COL ? 'overdue' : COL2 ? 'duesoon' : 'ontrack'` style
      unknown         - column projected but never referenced (suspicious in itself)
    """
    # Pattern 1: explicit `... ? 'nodata'` or `else { st = 'nodata' }` near col use
    # We detect the bug shape: the column appears inside an `if (otherField)` block.
    bug_re = re.compile(
        r"if\s*\(\s*\w+\.(?P<gate>(next_due_date|next_\w*|last_\w*|due_\w*|started_\w*|completed_\w*))\s*\)"
        r"\s*\{[^}]*\b" + re.escape(col) + r"\b[^}]*\}\s*else\s*\{[^}]*['\"]nodata['\"]",
        re.DOTALL,
    )
    if bug_re.search(code):
        return "gated_by_other"

    # Pattern 2: direct ternary `r.COL ? ... : r.COL2 ? ... : ...`
    if re.search(r"\b" + re.escape(col) + r"\s*\?\s*['\"]", code):
        # is it INSIDE an outer `if (other_field)` block? approx via above
        if re.search(
            r"if\s*\([^)]*\bnext_due_date\b[^)]*\)\s*\{[^}]*?\b" + re.escape(col) + r"\b\s*\?",
            code, re.DOTALL,
        ):
            return "gated_by_other"
        return "mapped_enum"

    # Pattern 3: direct boolean use — `if (r.COL)`, `.filter(... r.COL)`, etc.
    if re.search(r"\b(?:if|filter|some|every)\s*\([^)]*\b" + re.escape(col) + r"\b", code):
        return "direct"

    # Pattern 4: bare reference `.COL` somewhere
    if re.search(r"\b" + re.escape(col) + r"\b", code):
        return "direct"

    return "unknown"


def main() -> int:
    blobs = _gather_files()

    # (view, col) -> [{file, usage_shape}, ...]
    pair_consumers: dict[tuple[str, str], list[dict]] = defaultdict(list)

    # SCOPE-level smell detection — for each `db.from('v_*')` site, scan a
    # window around the call (the enclosing function body, approximated as
    # ±2000 chars). If a smell appears in that window, attach it to the
    # (view, col) pair — not to every pair in the file.
    SCOPE_BEFORE = 800
    SCOPE_AFTER  = 2500

    for fname, body in blobs.items():
        for m in FROM_TRUTH_RE.finditer(body):
            view = m.group("view").lower()
            # Window around the .from() call
            wstart = max(0, m.start() - SCOPE_BEFORE)
            wend   = min(len(body), m.end() + SCOPE_AFTER)
            window = body[wstart:wend]
            # .select() lookup
            tail = body[m.end(): m.end() + 800]
            sm = SELECT_RE.search(tail)
            if not sm:
                continue
            cols = _extract_cols(sm.group("cols"))
            # Per-scope smells
            scope_smells = [label for label, pat in LOCAL_MATH_SMELLS if pat.search(window)]
            for col in cols:
                if col in PLUMBING_COLS:
                    continue
                shape = _classify_usage(window, col)
                pair_consumers[(view, col)].append({
                    "file":   fname,
                    "shape":  shape,
                    "smells": scope_smells,
                })

    pair_rows: list[dict] = []
    at_risk = 0
    review = 0
    for (view, col), consumers in sorted(pair_consumers.items()):
        # Collapse consumers per file (keep richer shape over plain "direct")
        per_file: dict[str, dict] = {}
        for c in consumers:
            cur = per_file.get(c["file"])
            if cur is None or (cur["shape"] == "direct" and c["shape"] != "direct"):
                per_file[c["file"]] = {"shape": c["shape"], "smells": c["smells"]}

        shapes = {info["shape"] for info in per_file.values()}
        smells_any = sorted({s for info in per_file.values() for s in info["smells"]})

        # AT_RISK — at least one consumer re-gates the signal by another column
        risk = "OK"
        if len(per_file) >= 2 and "gated_by_other" in shapes:
            risk = "AT_RISK"
        # REVIEW — multiple consumers AND at least one shows local-math smell
        # (probable local re-derivation of a canonical signal)
        elif len(per_file) >= 2 and smells_any:
            risk = "REVIEW"

        if risk == "AT_RISK": at_risk += 1
        if risk == "REVIEW":  review  += 1

        pair_rows.append({
            "view":      view,
            "column":    col,
            "consumers": [{"file": f, **info} for f, info in sorted(per_file.items())],
            "smells":    smells_any,
            "risk":      risk,
        })

    report = {
        "summary": {
            "view_column_pairs": len(pair_rows),
            "at_risk":           at_risk,
            "review":            review,
            "files_scanned":     len(blobs),
        },
        "pairs": pair_rows,
    }

    (ROOT / "truth_view_signal_trust_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    # Markdown punch list
    md: list[str] = []
    md.append("# Truth-View Signal-Trust Miner (L-1)\n")
    md.append("Catches **semantic drift inside the same canonical column** —")
    md.append("two surfaces read the same `v_*_truth` column but interpret it")
    md.append("differently (one trusts it; one re-gates on another field).\n")
    md.append("## Summary\n")
    md.append(f"- View/column pairs scanned: **{len(pair_rows)}**")
    md.append(f"- AT_RISK pairs (re-gating detected): **{at_risk}**")
    md.append(f"- REVIEW pairs (local-math smell on at least one consumer): **{review}**")
    md.append(f"- Files scanned: **{len(blobs)}**\n")
    md.append("## Smell legend\n")
    md.append("Smells are file-level hints that the consumer may be locally")
    md.append("re-deriving what the canonical view should expose:")
    md.append("- `re_computes_overdue` — `Date.now() - new Date(last_completed)` arithmetic")
    md.append("- `hardcoded_freq_days` — `FREQ_DAYS[...]` / `calcNextDue(...)` / `getItemStatus(...)`")
    md.append("- `manual_qty_threshold` — `qty_on_hand < reorder_point` instead of `is_low_stock`")
    md.append("- `manual_risk_band` — `risk_score > 80` instead of view-exposed band")
    md.append("- `manual_age_days` — `daysUntil(...)` / floor(now - x / 86400000) arithmetic")
    md.append("- `nodata_fallback` — `'nodata'` string literal (re-gating signature)\n")

    if at_risk:
        md.append("## ❌ AT_RISK pairs (re-gating across consumers)\n")
        md.append("| View | Column | Consumers (file → shape) | File-level smells |")
        md.append("|---|---|---|---|")
        for r in pair_rows:
            if r["risk"] != "AT_RISK":
                continue
            cons = "<br>".join(
                f"`{c['file']}` → `{c['shape']}`"
                + (f" 🚩{','.join(c['smells'])}" if c.get('smells') else "")
                for c in r["consumers"]
            )
            md.append(f"| `{r['view']}` | `{r['column']}` | {cons} | {', '.join(r['smells']) or '—'} |")
        md.append("")

    if review:
        md.append("## ⚠️ REVIEW pairs (multiple consumers with local-math smell)\n")
        md.append("| View | Column | Consumers (file → shape) | File-level smells |")
        md.append("|---|---|---|---|")
        for r in pair_rows:
            if r["risk"] != "REVIEW":
                continue
            cons = "<br>".join(
                f"`{c['file']}` → `{c['shape']}`"
                + (f" 🚩{','.join(c['smells'])}" if c.get('smells') else "")
                for c in r["consumers"]
            )
            md.append(f"| `{r['view']}` | `{r['column']}` | {cons} | {', '.join(r['smells']) or '—'} |")
        md.append("")

    md.append("## All pairs (informational)\n")
    md.append("| View | Column | Risk | Consumer count | Distinct shapes |")
    md.append("|---|---|:---:|---:|---|")
    for r in pair_rows:
        shapes = sorted({c["shape"] for c in r["consumers"]})
        risk_emoji = {"AT_RISK": "❌", "REVIEW": "⚠️", "OK": "✅"}[r["risk"]]
        md.append(
            f"| `{r['view']}` | `{r['column']}` | "
            f"{risk_emoji} {r['risk']} | "
            f"{len(r['consumers'])} | "
            f"{', '.join(shapes)} |"
        )
    md.append("")

    (ROOT / "truth_view_signal_trust_report.md").write_text("\n".join(md), encoding="utf-8")

    print()
    print("Truth-View Signal-Trust Miner")
    print(f"  pairs scanned:   {len(pair_rows)}")
    print(f"  AT_RISK:         {at_risk}")
    print(f"  REVIEW:          {review}")
    print(f"  files scanned:   {len(blobs)}")
    if at_risk:
        print()
        print("AT_RISK pairs (re-gating):")
        for r in pair_rows:
            if r["risk"] != "AT_RISK":
                continue
            shapes = sorted({c["shape"] for c in r["consumers"]})
            print(f"  {r['view']}.{r['column']}  shapes={shapes}  consumers={len(r['consumers'])}")
    if review:
        print()
        print("REVIEW pairs (local-math smell on a consumer):")
        for r in pair_rows[:20]:
            if r["risk"] != "REVIEW":
                continue
            print(f"  {r['view']}.{r['column']}  smells={r['smells']}  consumers={len(r['consumers'])}")
    return 1 if at_risk > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
