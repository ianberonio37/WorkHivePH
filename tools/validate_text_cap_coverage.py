#!/usr/bin/env python3
"""validate_text_cap_coverage.py — FREE_TIER_QUOTA_ROADMAP Q3 ratchet (no unbounded text/upload).

Q3 DoD: no unbounded user text or upload. This gate FAILs if a table that should carry a
server-side text cap loses its trigger, or an upload surface loses its size/duration cap.
The server-side DB triggers are the SECURITY layer (client maxlength is only UX), so this
gate checks the DB triggers + the upload caps — the things whose loss actually reopens the
free-tier hole.

USAGE:      python tools/validate_text_cap_coverage.py
Self-test:  python tools/validate_text_cap_coverage.py --self-test
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
GREEN, RED = "\033[92m", "\033[91m"
RST = "\033[0m"

# table -> the cap function that left()-truncates its text fields.
TEXT_CAP = {
    "logbook": "cap_logbook_text_fields",
    "inventory_items": "cap_inventory_items_text",
    "inventory_transactions": "cap_inventory_transactions_text",
    "pm_completions": "cap_pm_completions_text",
    "asset_nodes": "cap_asset_nodes_text",
    "marketplace_listings": "cap_marketplace_listings_text",
    "marketplace_inquiries": "cap_marketplace_inquiries_text",
    "marketplace_sellers": "cap_marketplace_sellers_text",
    "pm_assets": "cap_pm_assets_text",
    "pm_scope_items": "cap_pm_scope_items_text",
    "rcm_fmea_modes": "cap_rcm_fmea_modes_text",
    "rcm_strategies": "cap_rcm_strategies_text",
    # Full write-surface audit (2026-07-05): previously-uncovered user-content tables.
    "projects": "cap_projects_text",
    "project_items": "cap_project_items_text",
    "project_change_orders": "cap_project_change_orders_text",
    "project_progress_logs": "cap_project_progress_logs_text",
    "project_links": "cap_project_links_text",
    "project_roles": "cap_project_roles_text",
    "engineering_calcs": "cap_engineering_calcs_text",
    "schedule_items": "cap_schedule_items_text",
    "skill_profiles": "cap_skill_profiles_text",
    "resume_documents": "cap_resume_documents_text",
    "resume_versions": "cap_resume_versions_text",
    "worker_profiles": "cap_worker_profiles_text",
    "parts_staged_reservations": "cap_parts_staged_reservations_text",
    "marketplace_saved_searches": "cap_marketplace_saved_searches_text",
}

# html file -> (marker regex, human label) for the upload cap that must be present.
UPLOAD_CAP = {
    "resume.html": (r"MAX_FILE_BYTES|10\s*\*\s*1024\s*\*\s*1024", "per-file upload size cap"),
    "inventory.html": (r"_b64bytes|70{4,}0", "post-compression photo size assert"),
    "logbook.html": (r"_b64bytes|70{4,}0", "post-compression photo size assert"),
    "voice-journal.html": (r"MAX_RECORD_MS", "audio max-duration cap"),
}


def _migrations_text() -> str:
    if not MIGRATIONS.is_dir():
        return ""
    return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in sorted(MIGRATIONS.glob("*.sql")))


def evaluate(mig_text: str, html: dict[str, str]) -> list[tuple[str, bool, str]]:
    rows: list[tuple[str, bool, str]] = []
    # 1. server-side text caps
    for tbl, fn in TEXT_CAP.items():
        fn_ok = bool(re.search(
            r"CREATE\s+OR\s+REPLACE\s+FUNCTION\s+public\." + re.escape(fn) + r"\b.*?\$\$(.*?)\$\$",
            mig_text, re.I | re.S))
        body = ""
        m = re.search(r"public\." + re.escape(fn) + r"\b.*?\$\$(.*?)\$\$", mig_text, re.I | re.S)
        if m:
            body = m.group(1)
        uses_left = "left(" in body.lower()
        trig_ok = bool(re.search(
            r"CREATE\s+TRIGGER\s+\w+\s+BEFORE\s+INSERT(?:\s+OR\s+UPDATE)?\s+ON\s+public\." + re.escape(tbl) +
            r"\b.*?EXECUTE\s+FUNCTION\s+public\." + re.escape(fn), mig_text, re.I | re.S))
        ok = fn_ok and uses_left and trig_ok
        rows.append((f"text:{tbl}", ok,
                     f"{fn} left()-caps + trigger wired" if ok else
                     f"MISSING (fn:{fn_ok} left:{uses_left} trigger:{trig_ok})"))
    # 2. upload caps
    for fname, (pat, label) in UPLOAD_CAP.items():
        ok = bool(re.search(pat, html.get(fname, "")))
        rows.append((f"upload:{fname}", ok, label if ok else f"MISSING {label}"))
    return rows


def _load_html() -> dict[str, str]:
    out = {}
    for fname in UPLOAD_CAP:
        p = ROOT / fname
        out[fname] = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
    return out


def main() -> int:
    self_test = "--self-test" in sys.argv[1:]
    mig = _migrations_text()
    html = _load_html()
    rows = evaluate(mig, html)

    print("=" * 74)
    print("  FREE_TIER_QUOTA_ROADMAP Q3 — text + upload cap coverage (no unbounded user input)")
    print("=" * 74)
    covered = sum(1 for _, ok, _ in rows if ok)
    for name, ok, detail in rows:
        tag = f"{GREEN}ok{RST}  " if ok else f"{RED}FAIL{RST}"
        print(f"  {tag} {name:32s} {detail}")
    print(f"\n  coverage: {covered}/{len(rows)} caps present")

    if self_test:
        empty_all_fail = all(not ok for _, ok, _ in evaluate("", {}))
        # a fn present but WITHOUT a trigger must fail
        partial = evaluate("CREATE OR REPLACE FUNCTION public.cap_logbook_text_fields() RETURNS trigger AS $$ BEGIN NEW.problem := left(NEW.problem,1); RETURN NEW; END; $$;", {})
        no_trigger_fails = dict((n, ok) for n, ok, _ in partial).get("text:logbook") is False
        good = empty_all_fail and no_trigger_fails
        print(f"  TEETH [{GREEN+'PASS'+RST if good else RED+'FAIL'+RST}] empty=all-fail:{empty_all_fail}  fn-without-trigger-fails:{no_trigger_fails}")
        if not good:
            return 1

    missing = [n for n, ok, _ in rows if not ok]
    print()
    if missing:
        print(f"  {RED}FAIL{RST} — {len(missing)} cap(s) missing: {', '.join(missing)}")
        return 1
    print(f"  {GREEN}PASS{RST} — every expected text + upload cap is present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
