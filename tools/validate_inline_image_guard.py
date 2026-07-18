#!/usr/bin/env python3
"""validate_inline_image_guard.py - FREE_TIER_QUOTA_ROADMAP Q5-a ratchet.

GROUNDED: photo blob-offload was assumed the #1 lever; measured attach-rate is 0%, so a full
Storage pipeline is speculative. This is the right-sized DETECTOR-GUARD:
  C1 size-guard   check_inline_image_size() caps inline base64 photos server-side (RAISE 54000)
  C2 triggers     the guard fires BEFORE INSERT OR UPDATE OF photo on logbook + inventory_items
  C3 telemetry    photo_attach_stats() exposes attach-rate (the signal for WHEN to build offload)

USAGE:      python tools/validate_inline_image_guard.py
Self-test:  python tools/validate_inline_image_guard.py --self-test
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


def _migrations_text() -> str:
    if not MIGRATIONS.is_dir():
        return ""
    return "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in sorted(MIGRATIONS.glob("*.sql")))


def trigger_attached(text: str, trg: str, table: str) -> bool:
    create = re.compile(r"CREATE TRIGGER " + re.escape(trg) + r"\b[^;]*?ON public\." + re.escape(table) + r"\b", re.I | re.S)
    last_create = max((m.start() for m in create.finditer(text)), default=-1)
    drop = re.compile(r"DROP TRIGGER (?:IF EXISTS )?" + re.escape(trg) + r"\b", re.I)
    last_drop = max((m.start() for m in drop.finditer(text)), default=-1)
    return last_create > last_drop


def evaluate(mig: str) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []
    fn = ""
    m = re.search(r"CREATE OR REPLACE FUNCTION public\.check_inline_image_size.*?\$\$;", mig, re.S | re.I)
    if m:
        fn = m.group(0)
    c1 = bool(fn) and ("octet_length(NEW.photo)" in fn) and ("54000" in fn) and bool(re.search(r"v_cap\s*integer\s*:=\s*\d+", fn))
    checks.append(("C1 size-guard", c1, "check_inline_image_size caps inline base64 (RAISE 54000)"
                   if c1 else "size guard fn missing/incomplete"))

    c2 = trigger_attached(mig, "trg_inline_image_size_logbook", "logbook") \
        and trigger_attached(mig, "trg_inline_image_size_inventory", "inventory_items") \
        and mig.count("BEFORE INSERT OR UPDATE OF photo") >= 2
    checks.append(("C2 triggers", c2, "guard fires on logbook + inventory_items (INSERT/UPDATE OF photo)"
                   if c2 else "triggers not attached to both tables"))

    c3 = bool(re.search(r"CREATE OR REPLACE FUNCTION public\.photo_attach_stats", mig, re.I)) \
        and bool(re.search(r"GRANT EXECUTE ON FUNCTION public\.photo_attach_stats", mig, re.I))
    checks.append(("C3 telemetry", c3, "photo_attach_stats() attach-rate signal present + granted"
                   if c3 else "attach-rate telemetry fn missing"))
    return checks


def main() -> int:
    self_test = "--self-test" in sys.argv[1:]
    mig = _migrations_text()
    checks = evaluate(mig)

    print("=" * 74)
    print("  FREE_TIER_QUOTA_ROADMAP Q5-a - inline base64 image detector-guard")
    print("=" * 74)
    passed = sum(1 for _, ok, _ in checks if ok)
    for name, ok, detail in checks:
        tag = f"{GREEN}ok{RST}  " if ok else f"{RED}FAIL{RST}"
        print(f"  {tag} {name:14s} {detail}")
    print(f"\n  {passed}/{len(checks)} checks green")

    if self_test:
        empty_all_fail = all(not ok for _, ok, _ in evaluate(""))
        drop_regress = mig + "\nDROP TRIGGER IF EXISTS trg_inline_image_size_logbook ON public.logbook;"
        c2_tooth = dict((n, ok) for n, ok, _ in evaluate(drop_regress)).get("C2 triggers") is False
        good = empty_all_fail and c2_tooth
        print(f"  TEETH [{GREEN+'PASS'+RST if good else RED+'FAIL'+RST}] "
              f"empty=all-fail:{empty_all_fail}  drop-regress->C2-fail:{c2_tooth}")
        if not good:
            return 1

    print()
    failed = [n for n, ok, _ in checks if not ok]
    if failed:
        print(f"  {RED}FAIL{RST} - {len(failed)} check(s) regressed: {', '.join(failed)}")
        return 1
    print(f"  {GREEN}PASS{RST} - inline base64 photos are size-guarded + attach-rate is measured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
