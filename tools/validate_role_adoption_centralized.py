#!/usr/bin/env python3
"""
validate_role_adoption_centralized.py — HK3: a page may adopt the canonical role from exactly ONE
place.

WHY THIS EXISTS (hive deepwalk H8b / H8d / H3, 2026-07-27). Adopting a role is not one assignment,
it is three things that must stay in lockstep: the module variable, the stored hint
(`wh_hive_role`), and any PAINT derived from it. hive.html painted `html.is-supervisor` from the
cached role at parse (a deliberate CLS optimisation) and the supervisor rules are FUNCTIONAL, not
cosmetic — they set `#my-work-card{display:none}` and hide `#pm-overdue-alert` / `#stock-alert`.

hive.html had SEVEN role-adoption sites and only TWO of them repainted. Each unreconciled site was
its own door onto the same defect, and three were confirmed live before being fixed:
  - DEMOTION — role synced down, marker stayed, so a demoted worker lost their own work card and
    their overdue-PM and stock alerts while the page otherwise looked normal;
  - SWITCH   — a switch never reloads (it calls initBoard() in place), so the page-load fix never ran;
  - JOIN     — joining a hive where you are a worker while holding supervisor paint from another.

The lesson is not "remember to repaint". It is that a value with invariants attached needs ONE
adopter, so the invariant is written once instead of remembered seven times. hive.html now routes
every adoption through `applyHiveRole(role)`.

THE ASSERTION: at most one `localStorage.setItem('wh_hive_role', …)` per file. One write is the
adopter (or a page that simply syncs the role and paints nothing). Two or more means the invariant
has been duplicated, which is the precondition for the next door.

Verified as an instrument, not assumed: run against pre-fix hive.html it FAILS with 7 sites; against
the centralized version it passes with 1.

Self-test: `--selftest` (pure text analysis, no files).
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
GREEN, RED, YELLOW, BOLD, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"

WRITE_RE = re.compile(r"localStorage\s*\.\s*setItem\(\s*['\"]wh_hive_role['\"]")
MAX_ADOPTERS = 1

# Test/scan harnesses legitimately plant a role to set up a scenario; they are not product surfaces.
EXEMPT = {"axe_scan_live.js", "axe_scan.js", "ufai_battery.js", "companion_battery.js",
          "request_budget_scan.js"}


def count_sites(text: str) -> list[int]:
    """1-indexed line numbers of every direct wh_hive_role write."""
    return [i for i, line in enumerate(text.splitlines(), 1) if WRITE_RE.search(line)]


def _iter_files():
    for path in sorted(ROOT.glob("*.html")) + sorted(ROOT.glob("*.js")) + sorted(ROOT.glob("tools/*.js")):
        if path.name in EXEMPT:
            continue
        yield path


def selftest() -> int:
    ok = True

    def chk(label, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {GREEN+'PASS'+RESET if good else RED+'FAIL'+RESET}  {label}: got {got}, want {want}")

    one = "function applyHiveRole(r){ localStorage.setItem('wh_hive_role', r); }"
    chk("a single adopter is clean", len(count_sites(one)), 1)

    # The exact pre-fix hive.html shape: the same invariant restated at several call sites.
    many = ("localStorage.setItem('wh_hive_role', membership.role);\n"
            "localStorage.setItem('wh_hive_role', first.role);\n"
            "localStorage.setItem('wh_hive_role', 'supervisor');\n")
    chk("duplicated adoption is caught", count_sites(many), [1, 2, 3])

    chk("a page that never writes it is clean", count_sites("const r = localStorage.getItem('wh_hive_role');"), [])
    # A READ must never be mistaken for a write — that would fail every page on the platform.
    chk("reads are not counted", len(count_sites("if (localStorage.getItem('wh_hive_role') === 'supervisor') {}")), 0)
    chk("double-quoted writes are counted", len(count_sites('localStorage.setItem("wh_hive_role", r);')), 1)

    print(f"\n  SELFTEST: {GREEN+'PASS'+RESET if ok else RED+'FAIL'+RESET}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()

    offenders, scanned, adopters = [], 0, 0
    for path in _iter_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        scanned += 1
        sites = count_sites(text)
        adopters += len(sites)
        if len(sites) > MAX_ADOPTERS:
            offenders.append((path.name, sites))

    print(f"{BOLD}Role adoption is centralized (one adopter per page){RESET}")
    if offenders:
        for name, sites in offenders:
            print(f"  {RED}FAIL{RESET}  {name}: {len(sites)} role-adoption sites (lines {', '.join(map(str, sites))})")
        print(f"\n  {YELLOW}Adopting a role means the variable, the stored hint AND any paint derived from it"
              f" must move together.{RESET}")
        print(f"  {YELLOW}Fix:{RESET} route every site through ONE adopter (see applyHiveRole() in hive.html), "
              f"so the invariant is written once instead of remembered at each call site.")
        return 1
    print(f"  {GREEN}PASS{RESET}  {adopters} adoption site(s) across {scanned} file(s), never more than "
          f"{MAX_ADOPTERS} per file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
