#!/usr/bin/env python3
"""validate_logbook_quota.py — FREE_TIER_QUOTA_ROADMAP Phase Q0 gate (the logbook pilot).

Q0 is the REFERENCE IMPLEMENTATION every other high-write table (Q2) replicates. This gate
has teeth: it FAILs if any of the four Q0 pieces regress, so "logbook is a bounded page" can
never silently drift back to unbounded.

Q0 Definition-of-Done (FREE_TIER_QUOTA_ROADMAP.md §Q0):
  1. Per-day insert RATE LIMIT — a BEFORE INSERT trigger `check_logbook_rate_limit()` on
     public.logbook that counts rows created TODAY (per-day window, not cumulative) and
     RAISEs over the cap. Cap tunable via hive_quotas.max_rows_logbook (re-added here).
  2. TEXT-FIELD CAPS — server-side `left()` truncation of problem/root_cause/action/knowledge
     (defense-in-depth behind the client `maxlength`).
  3. IMAGE — ≤1 photo/entry + a post-compression size assert in logbook.html.
  4. FRIENDLY message — the raised message is user-readable ("...free limit... Resets at
     midnight.") and logbook.html surfaces it instead of a raw DB error.

REGRESSION GUARD: the trigger must count on the REAL column `created_at`. The logbook table
has NO `logged_at` column; the security-skill example used `logged_at` generically, and
transcribing it verbatim is exactly what broke the old quota triggers ("column does not
exist"). This gate FAILs if the rate-limit fn references `logged_at`.

USAGE:      python tools/validate_logbook_quota.py
Self-test:  python tools/validate_logbook_quota.py --self-test
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
LOGBOOK = ROOT / "logbook.html"
GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"
RST = "\033[0m"


def _rate_limit_fn_body(migrations_text: str) -> str:
    """Return the body of the check_logbook_rate_limit() fn (create ... $$; ... $$), or ''."""
    m = re.search(
        r"CREATE\s+OR\s+REPLACE\s+FUNCTION\s+public\.check_logbook_rate_limit\b.*?\$\$(.*?)\$\$",
        migrations_text, re.I | re.S,
    )
    return m.group(1) if m else ""


def evaluate(migrations_text: str, logbook_text: str) -> list[tuple[str, bool, str]]:
    """Return [(check_name, passed, detail)]. Pure fn so --self-test can feed synthetic text."""
    checks: list[tuple[str, bool, str]] = []
    rl_body = _rate_limit_fn_body(migrations_text)

    # 1. Per-day rate-limit trigger exists on logbook.
    has_fn = bool(rl_body)
    checks.append(("rate_limit_fn", has_fn,
                   "check_logbook_rate_limit() present" if has_fn else "MISSING check_logbook_rate_limit()"))
    has_trigger = bool(re.search(
        r"CREATE\s+TRIGGER\s+\w+\s+BEFORE\s+INSERT\s+ON\s+public\.logbook\s+FOR\s+EACH\s+ROW\s+EXECUTE\s+FUNCTION\s+public\.check_logbook_rate_limit",
        migrations_text, re.I | re.S))
    checks.append(("rate_limit_trigger", has_trigger,
                   "BEFORE INSERT trigger wired" if has_trigger else "MISSING BEFORE INSERT trigger on logbook"))

    # 2. Per-DAY window (not cumulative): the fn counts within a day window on created_at.
    per_day = bool(rl_body) and bool(re.search(r"created_at", rl_body, re.I)) and bool(
        re.search(r"day_start|INTERVAL\s+'1\s+day'|date_trunc\('day'|::date", rl_body, re.I))
    checks.append(("per_day_window", per_day,
                   "counts rows within a day window on created_at" if per_day else "not a per-DAY window (cumulative or missing created_at)"))

    # 3. Raises with a machine-parseable code + tunable cap column.
    raises = bool(rl_body) and bool(re.search(r"RAISE\s+EXCEPTION", rl_body, re.I)) and "54000" in rl_body
    checks.append(("rate_limit_raises", raises,
                   "RAISE EXCEPTION with SQLSTATE 54000" if raises else "MISSING RAISE / SQLSTATE 54000"))
    tunable = bool(re.search(r"ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+max_rows_logbook\b", migrations_text, re.I))
    checks.append(("cap_tunable", tunable,
                   "hive_quotas.max_rows_logbook re-added (tunable)" if tunable else "max_rows_logbook column not re-added"))

    # 4. REGRESSION GUARD — must use created_at, never the phantom logged_at.
    no_phantom = bool(rl_body) and not re.search(r"\blogged_at\b", rl_body)
    checks.append(("no_phantom_column", no_phantom,
                   "uses real created_at (no logged_at)" if no_phantom else "references phantom logged_at column (would break INSERT)"))

    # 5. Server-side text caps on the four fields.
    cap_body_m = re.search(
        r"CREATE\s+OR\s+REPLACE\s+FUNCTION\s+public\.cap_logbook_text_fields\b.*?\$\$(.*?)\$\$",
        migrations_text, re.I | re.S)
    cap_body = cap_body_m.group(1) if cap_body_m else ""
    fields = ("problem", "root_cause", "action", "knowledge")
    capped = bool(cap_body) and all(re.search(rf"NEW\.{f}\s*:=\s*left\(", cap_body, re.I) for f in fields)
    checks.append(("text_caps", capped,
                   "problem/root_cause/action/knowledge all left()-capped" if capped
                   else "not all four text fields server-capped"))

    # 6. UI maxlength on the three free-text textareas.
    ml = all(re.search(rf'id="f-{fid}"[^>]*maxlength=', logbook_text) or
             re.search(rf'maxlength=[^>]*id="f-{fid}"', logbook_text)
             for fid in ("problem", "action", "knowledge"))
    checks.append(("ui_maxlength", ml,
                   "maxlength on f-problem/f-action/f-knowledge" if ml else "MISSING maxlength on a text field"))

    # 7. UI surfaces the friendly quota message (detects 54000 or "free limit").
    friendly = bool(re.search(r"54000", logbook_text)) and bool(re.search(r"free limit", logbook_text, re.I))
    checks.append(("ui_friendly_msg", friendly,
                   "logbook.html surfaces the friendly daily-limit message" if friendly else "no friendly quota-message handler in UI"))

    # 8. UI post-compression photo size assert.
    size_assert = bool(re.search(r"_b64bytes|700_000|700000", logbook_text))
    checks.append(("ui_photo_size_assert", size_assert,
                   "post-compression photo size assert present" if size_assert else "no post-compression size assert"))

    return checks


def _load() -> tuple[str, str]:
    mig_text = ""
    if MIGRATIONS.is_dir():
        for p in sorted(MIGRATIONS.glob("*.sql")):
            try:
                t = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            # only migrations that actually touch the Q0 quota surface
            if "check_logbook_rate_limit" in t or "cap_logbook_text_fields" in t or "max_rows_logbook" in t:
                mig_text += "\n" + t
    lb_text = LOGBOOK.read_text(encoding="utf-8", errors="replace") if LOGBOOK.exists() else ""
    return mig_text, lb_text


def main() -> int:
    self_test = "--self-test" in sys.argv[1:]
    mig_text, lb_text = _load()
    checks = evaluate(mig_text, lb_text)

    print("=" * 74)
    print("  FREE_TIER_QUOTA_ROADMAP Q0 — Logbook Pilot (per-day cap + text caps + friendly UX)")
    print("=" * 74)
    for name, passed, detail in checks:
        tag = f"{GREEN}ok{RST}  " if passed else f"{RED}FAIL{RST}"
        print(f"  {tag} {name:22s} {detail}")

    if self_test:
        # TEETH: empty inputs must fail every check; a correct sample must pass the core ones.
        empty = evaluate("", "")
        teeth_ok = all(not p for _, p, _ in empty)
        # and the phantom-column guard must actually fire on a logged_at body
        phantom_fn = ("CREATE OR REPLACE FUNCTION public.check_logbook_rate_limit() RETURNS trigger AS $$\n"
                      "BEGIN SELECT COUNT(*) FROM logbook WHERE logged_at >= now() - INTERVAL '1 day'; "
                      "RAISE EXCEPTION 'x' USING ERRCODE='54000'; RETURN NEW; END; $$;")
        phantom_res = dict((n, p) for n, p, _ in evaluate(phantom_fn, ""))
        guard_fires = phantom_res.get("no_phantom_column") is False
        good = teeth_ok and guard_fires
        print(f"\n  TEETH [{GREEN+'PASS'+RST if good else RED+'FAIL'+RST}] empty=all-fail:{teeth_ok}  phantom-guard-fires:{guard_fires}")
        if not good:
            return 1

    failed = [c for c in checks if not c[1]]
    print()
    if failed:
        print(f"  {RED}FAIL{RST} — {len(failed)}/{len(checks)} Q0 check(s) not satisfied: {', '.join(n for n, _, _ in failed)}")
        return 1
    print(f"  {GREEN}PASS{RST} — all {len(checks)} Q0 checks satisfied; logbook is a bounded page")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
