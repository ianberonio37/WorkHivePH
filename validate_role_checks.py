#!/usr/bin/env python3
"""
validate_role_checks.py — PLATFORM_CENTRALIZATION_ROADMAP +RBAC (forward-only ratchet).

The client-side role→capability truth drifted into scattered raw comparisons
(`role === 'supervisor'`, `HIVE_ROLE === 'supervisor'`, 125 raw 'supervisor' literals).
`wh-roles.js` (window.WHRoles) is the canonical SSOT: WHRoles.isSupervisor() / WHRoles.can(cap).

This gate counts the RAW role-string comparisons per file and ratchets forward-only: the count
may only FALL. A NEW raw `role === '<role>'` added to any file FAILs — new code must use
window.WHRoles. Existing raw comparisons are the convergence BACKLOG (tracked, adopted over time).

Modes:
  (default)         print the per-file board + total.
  --write-baseline  (re)write role_check_baseline.json from the current count.
  --check           forward-only ratchet vs the baseline.
"""
import io
import re
import sys
import json
import argparse
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
BASELINE = ROOT / "role_check_baseline.json"

# A role-ish identifier compared to a role literal — the raw drift pattern.
_ROLE_CMP = re.compile(
    r"\b[A-Za-z_]*[Rr]ole[A-Za-z_]*\s*(?:===|!==|==|!=)\s*['\"](?:supervisor|engineer|field|worker|admin|owner)['\"]"
)


def inventory():
    rows = {}
    for pat in ("*.js", "*.html"):
        for fp in ROOT.glob(pat):
            if fp.name.startswith(".") or fp.name == "wh-roles.js":
                continue  # wh-roles.js IS the canonical definition — its literals are the SSOT
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            # skip lines carrying `role-check-allow` (exempt-with-reason)
            text = "\n".join(ln for ln in text.splitlines() if "role-check-allow" not in ln)
            n = len(_ROLE_CMP.findall(text))
            if n:
                rows[fp.name] = n
    return rows


def do_board():
    rows = inventory()
    total = sum(rows.values())
    print("\n== Raw role-comparison inventory (SSOT: wh-roles.js / window.WHRoles) ==")
    for name, n in sorted(rows.items(), key=lambda kv: -kv[1]):
        print(f"  {n:>3}  {name}")
    print(f"  ----\n  TOTAL raw role comparisons: {total} across {len(rows)} files")
    print("  Convert to WHRoles.isSupervisor()/.can(cap); the ratchet holds the count from rising.")
    return rows, total


def do_write():
    rows = inventory()
    BASELINE.write_text(json.dumps({"files": rows, "total": sum(rows.values())}, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {BASELINE.name}: total={sum(rows.values())} across {len(rows)} files.")
    return 0


def do_check():
    rows = inventory()
    if not BASELINE.exists():
        BASELINE.write_text(json.dumps({"files": rows, "total": sum(rows.values())}, indent=2) + "\n", encoding="utf-8")
        print(f"role-checks: no baseline — seeded at total={sum(rows.values())}. PASS.")
        return 0
    base = json.loads(BASELINE.read_text(encoding="utf-8")).get("files", {})
    risen = [(n, base.get(n, 0), c) for n, c in rows.items() if c > base.get(n, 0)]
    if risen:
        print("role-checks: FAIL — raw role comparisons ROSE (use window.WHRoles.isSupervisor()/.can()):")
        for n, b, c in risen:
            print(f"  {n}: {b} -> {c}")
        return 1
    total, btotal = sum(rows.values()), sum(base.values())
    if total < btotal or any(c < base.get(n, 0) for n, c in rows.items()):
        BASELINE.write_text(json.dumps({"files": rows, "total": total}, indent=2) + "\n", encoding="utf-8")
        print(f"role-checks: PASS — improved, baseline tightened to total={total}.")
    else:
        print(f"role-checks: PASS — held at total={total} (convergence backlog).")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Client RBAC raw-role-comparison ratchet (+RBAC).")
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    if args.write_baseline:
        return do_write()
    if args.check:
        return do_check()
    do_board()
    return 0


if __name__ == "__main__":
    sys.exit(main())
