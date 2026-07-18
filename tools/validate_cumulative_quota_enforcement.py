#!/usr/bin/env python3
# DEEPWALK-CELL: ai:* D12
"""validate_cumulative_quota_enforcement.py — FREE_TIER_QUOTA_ROADMAP Q1 ratchet.

Q2 caps per-DAY floods; this proves the CUMULATIVE per-hive quota is ENFORCED (not
log-only) — the abuse ceiling that stops sustained runaway growth (a broken loop that
stays under the daily rate for weeks). The retention layer (Q5-b) holds the steady-state
500 MB line; this holds the runaway line.

Checks the EFFECTIVE (last-wins) definition across all migrations — the old 000003/000007
files still contain the pre-fix 'warn' text, so a naive grep would false-positive; migrations
apply in order, so only the LAST CREATE OR REPLACE of each fn (and the last un-dropped
CREATE TRIGGER) is live. This is the same "replay DDL order" discipline as the coverage gate.

  C1 enforce-default   hive_quotas.enforce_blocking DEFAULT flipped to true
  C2 backfill          every existing hive backfilled with a generous, enforcing quota row
  C3 five-triggers     all 5 cumulative-quota triggers ATTACHED (drift class: 000003's
                       logbook+inv_tx had silently detached from the live DB)
  C4 new-hive-trigger  new hives auto-seed a quota row (else NULL cap = unbounded)
  C5 status-fixed      each fn's LAST def RAISEs with ERRCODE 54000 + has NO invalid 'warn'
                       automation_log status (the bug: automation_log allows only
                       success/failed/skipped, and log-before-RAISE was futile)

USAGE:      python tools/validate_cumulative_quota_enforcement.py
Self-test:  python tools/validate_cumulative_quota_enforcement.py --self-test
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

# fn name -> (trigger name, table it must be attached to)
FNS = {
    "check_hive_quota_logbook":        ("trg_hive_quota_logbook",        "logbook"),
    "check_hive_quota_inv_tx":         ("trg_hive_quota_inv_tx",         "inventory_transactions"),
    "check_hive_quota_pm_completions": ("trg_hive_quota_pm_completions", "pm_completions"),
    "check_hive_quota_ai_reports":     ("trg_hive_quota_ai_reports",     "ai_reports"),
    "check_hive_quota_community":      ("trg_hive_quota_community_posts", "community_posts"),
}


def _migrations_text() -> str:
    if not MIGRATIONS.is_dir():
        return ""
    return "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in sorted(MIGRATIONS.glob("*.sql")))


def last_fn_body(text: str, fn: str) -> str:
    """The LAST CREATE OR REPLACE FUNCTION body for `fn` (last-wins under ordered apply)."""
    pat = re.compile(
        r"CREATE OR REPLACE FUNCTION public\." + re.escape(fn) + r"\b.*?\$\$;",
        re.S | re.I)
    matches = pat.findall(text)
    return matches[-1] if matches else ""


def trigger_attached(text: str, trg: str, table: str) -> bool:
    """True if the LAST DDL for `trg` is a CREATE (not a DROP) on the right table."""
    create = re.compile(r"CREATE TRIGGER " + re.escape(trg) +
                        r"\b[^;]*?ON public\." + re.escape(table) + r"\b", re.I | re.S)
    last_create = max((m.start() for m in create.finditer(text)), default=-1)
    # a bare DROP with no following CREATE would detach it
    drop = re.compile(r"DROP TRIGGER (?:IF EXISTS )?" + re.escape(trg) + r"\b", re.I)
    last_drop = max((m.start() for m in drop.finditer(text)), default=-1)
    return last_create > last_drop


def evaluate(text: str) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []

    # C1 — enforce default flipped
    c1 = bool(re.search(r"ALTER TABLE public\.hive_quotas\s+ALTER COLUMN enforce_blocking\s+SET DEFAULT true", text, re.I))
    checks.append(("C1 enforce-default", c1, "enforce_blocking DEFAULT true" if c1 else "flip missing"))

    # C2 — backfill of existing hives from public.hives with enforce
    c2 = bool(re.search(r"INSERT INTO public\.hive_quotas\b.*?FROM public\.hives\b", text, re.S | re.I)) \
        and bool(re.search(r"enforce_blocking\s*=\s*true", text, re.I))
    checks.append(("C2 backfill", c2, "existing hives backfilled + enforcing" if c2 else "backfill missing"))

    # C4 — new-hive auto-seed trigger (checked before C3 loop for output order clarity)
    c4 = trigger_attached(text, "trg_seed_hive_quota_defaults", "hives") \
        and bool(last_fn_body(text, "seed_hive_quota_defaults"))
    # C3 — all 5 cumulative triggers attached; C5 — each fn's last def is status-fixed
    missing_trg, unfixed = [], []
    for fn, (trg, tbl) in FNS.items():
        if not trigger_attached(text, trg, tbl):
            missing_trg.append(trg)
        body = last_fn_body(text, fn)
        has_54000 = "54000" in body
        no_warn = not re.search(r"automation_log[^;]*?'warn'", body, re.S | re.I) and "'warn'" not in body
        if not (body and has_54000 and no_warn):
            unfixed.append(fn)
    c3 = not missing_trg
    c5 = not unfixed
    checks.append(("C3 five-triggers", c3, "all 5 cumulative triggers attached"
                   if c3 else f"detached: {', '.join(missing_trg)}"))
    checks.append(("C4 new-hive-trig", c4, "new hives auto-seed a quota row" if c4 else "seed trigger missing"))
    checks.append(("C5 status-fixed", c5, "all 5 fns RAISE 54000 + no invalid 'warn' status"
                   if c5 else f"unfixed fn(s): {', '.join(unfixed)}"))
    return checks


def main() -> int:
    self_test = "--self-test" in sys.argv[1:]
    text = _migrations_text()
    checks = evaluate(text)

    print("=" * 74)
    print("  FREE_TIER_QUOTA_ROADMAP Q1 — cumulative per-hive quota ENFORCED")
    print("=" * 74)
    passed = sum(1 for _, ok, _ in checks if ok)
    for name, ok, detail in checks:
        tag = f"{GREEN}ok{RST}  " if ok else f"{RED}FAIL{RST}"
        print(f"  {tag} {name:18s} {detail}")
    print(f"\n  {passed}/{len(checks)} checks green")

    if self_test:
        empty_all_fail = all(not ok for _, ok, _ in evaluate(""))
        # a fn whose LAST def reintroduces the 'warn' status bug -> C5 fails
        warn_regression = text + (
            "\nCREATE OR REPLACE FUNCTION public.check_hive_quota_logbook() RETURNS trigger AS $$"
            "\nBEGIN INSERT INTO public.automation_log(job_name,status) VALUES('x','warn'); RETURN NEW; END; $$;")
        c5_tooth = dict((n, ok) for n, ok, _ in evaluate(warn_regression)).get("C5 status-fixed") is False
        # a bare DROP of a trigger after its create -> C3 fails
        drop_regression = text + "\nDROP TRIGGER IF EXISTS trg_hive_quota_logbook ON public.logbook;"
        c3_tooth = dict((n, ok) for n, ok, _ in evaluate(drop_regression)).get("C3 five-triggers") is False
        good = empty_all_fail and c5_tooth and c3_tooth
        print(f"  TEETH [{GREEN+'PASS'+RST if good else RED+'FAIL'+RST}] "
              f"empty=all-fail:{empty_all_fail}  warn-regress->C5-fail:{c5_tooth}  drop-regress->C3-fail:{c3_tooth}")
        if not good:
            return 1

    print()
    failed = [n for n, ok, _ in checks if not ok]
    if failed:
        print(f"  {RED}FAIL{RST} — {len(failed)} check(s) regressed: {', '.join(failed)}")
        return 1
    print(f"  {GREEN}PASS{RST} — cumulative per-hive quota is enforced, backfilled, attached, and status-fixed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
