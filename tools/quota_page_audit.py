#!/usr/bin/env python3
"""quota_page_audit.py — per-PAGE proof that every production feature page's writes are capped.

Answers "does EVERY production feature page have appropriate quota?" with evidence, not assertion:
for each live feature page, it extracts every table the page writes (.insert/.upsert), then marks
each table against the caps actually defined in the migrations (per-day trigger and/or text-cap
trigger). Any user-content table with NEITHER cap AND not in the documented exclusion list is a GAP.

USAGE:      python tools/quota_page_audit.py
Gate mode:  python tools/quota_page_audit.py --check   # exit 1 if any production page has a gap
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / "supabase" / "migrations"
GREEN, RED, YEL, DIM = "\033[92m", "\033[91m", "\033[93m", "\033[2m"
RST = "\033[0m"

# Pages that are NOT production feature surfaces (test harnesses / internal admin dashboards).
NON_FEATURE = {"engineering-design-test.html"}

# Tables that legitimately need NO user-content quota — documented rationale.
# (system-generated audit, admin-gated config, or capped by a DIFFERENT mechanism.)
EXCLUDED = {
    "hive_audit_log": "audit log (system-generated on every action)",
    "cmms_audit_log": "audit log (system-generated)",
    "api_keys": "admin-gated integration credential",
    "integration_configs": "admin-gated connector config",
    "external_sync": "integration sync state (admin-configured, upsert-keyed)",
    "hives": "hive creation (rare, controlled)",
    "hive_members": "membership (invite flow, controlled)",
    "anomaly_signals": "system-generated analytics signal (update, not user insert)",
    "ai_reply_feedback": "already daily-capped (baseline trigger)",
}


def _mig_text() -> str:
    if not MIGRATIONS.is_dir():
        return ""
    return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in sorted(MIGRATIONS.glob("*.sql")))


def capped_sets(mig: str) -> tuple[set[str], set[str]]:
    """(tables with a per-day cap trigger, tables with a text-cap trigger) — from migrations."""
    day, text = set(), set()
    trig = re.compile(
        r"CREATE\s+TRIGGER\s+\w+\s+BEFORE\s+INSERT(?:\s+OR\s+UPDATE)?\s+ON\s+(?:public\.)?\"?(\w+)\"?"
        r".*?EXECUTE\s+FUNCTION\s+public\.(\w+)", re.I | re.S)
    for m in trig.finditer(mig):
        tbl, fn = m.group(1), m.group(2).lower()
        if fn in ("check_daily_row_cap", "check_logbook_rate_limit", "check_listing_rate"):
            day.add(tbl)
        elif fn.startswith("cap_") and fn.endswith("_text") or fn == "cap_logbook_text_fields":
            text.add(tbl)
    return day, text


def page_writes(html: str) -> set[str]:
    """Tables a page writes via .insert/.upsert (client-direct)."""
    out = set()
    for m in re.finditer(r"from\(['\"](\w+)['\"]\)\s*\.\s*(?:insert|upsert)\(", html):
        out.add(m.group(1))
    return out


def main() -> int:
    check = "--check" in sys.argv[1:]
    mig = _mig_text()
    day, text = capped_sets(mig)

    pages = sorted(p for p in ROOT.glob("*.html") if p.name not in NON_FEATURE)
    gaps: list[tuple[str, str]] = []
    rows_out = []
    for p in pages:
        writes = page_writes(p.read_text(encoding="utf-8", errors="replace"))
        if not writes:
            continue
        cells = []
        for t in sorted(writes):
            has_day, has_text = t in day, t in text
            if has_day or has_text:
                tag = f"{GREEN}✓{RST}"
                mark = ("day" if has_day else "") + ("+text" if has_text else "" if has_day else "text")
            elif t in EXCLUDED:
                tag = f"{DIM}—{RST}"
                mark = f"excl:{EXCLUDED[t][:24]}"
            else:
                tag = f"{RED}GAP{RST}"
                mark = "UNCAPPED"
                gaps.append((p.name, t))
            cells.append(f"{tag} {t} ({mark})")
        rows_out.append((p.name, cells))

    print("=" * 78)
    print("  PER-PAGE QUOTA AUDIT — every production feature page's write tables vs. caps")
    print("=" * 78)
    for name, cells in rows_out:
        print(f"\n  {name}")
        for c in cells:
            print(f"      {c}")
    print("\n" + "-" * 78)
    print(f"  per-day capped: {len(day)} tables · text capped: {len(text)} tables · "
          f"pages audited: {len(rows_out)}")
    if gaps:
        print(f"\n  {RED}GAPS — {len(gaps)} feature-page write table(s) with NO cap and not excluded:{RST}")
        for pg, t in gaps:
            print(f"      {RED}{pg} → {t}{RST}")
        return 1 if check else 0
    print(f"\n  {GREEN}PASS — every production feature page writes only capped or documented-excluded tables.{RST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
