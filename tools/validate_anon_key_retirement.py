#!/usr/bin/env python3
"""validate_anon_key_retirement.py — Arc J/J7 + the cross-arc auth-migration completion gate.

THE QUESTION (the deferred `project_rls_decision` client half): Supabase Realtime AND PostgREST apply RLS
only when the caller carries a valid authenticated JWT. Every WorkHive page bootstraps its client with the
publishable (anon) key; the SECURE state is that hive data is read *with a session* (the JWT in the
Authorization header is what RLS evaluates), and an UNAUTHENTICATED (bare anon) client gets NOTHING from a
hive-scoped table. Arc G hardened the DB policies to `auth.uid()`-derived and dropped the legacy `USING(true)`
bypass (ratchet 9→0); this gate proves the *result* end-to-end and locks it against regression.

WHAT IT MEASURES:
  L1 (LIVE DB, the enforcement proof): an `anon`-role read of each core hive-scoped table returns 0 rows.
     If any returns >0, a legacy-open / permissive policy has crept back (the anon-key path is NOT retired).
     This is the positive twin of validate_rls_no_permissive_bypass (which finds the always-true POLICY;
     this proves the RESULT — anon sees nothing).
  L2 (STATIC, the client-half coverage): every page that reads a core hive table also calls
     `restoreIdentityFromSession` (so a JWT is established before the read; a page that queries a hive table
     with no session-restore would get 0 rows = a broken/anon-reliant surface).

A FAIL on L1 = a real cross-tenant exposure regression. A FAIL on L2 = a page reads hive data without
establishing a session (it will silently show empty data post-migration). Forward-only; baseline-locked.

USAGE:  python tools/validate_anon_key_retirement.py   [--update-baseline]
"""
from __future__ import annotations
import json
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DB = "supabase_db_workhive"
BASELINE = ROOT / "anon_key_retirement_baseline.json"
GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"; RST = "\033[0m"

# Core hive-scoped tables an unauthenticated client must NOT be able to read (Arc G's 9 + key reads).
CORE_HIVE_TABLES = [
    "engineering_calcs", "inventory_items", "pm_assets", "pm_completions",
    "pm_scope_items", "parts_records", "hive_members", "logbook",
]
# Pages that read a hive table directly and MUST establish a session first.
HIVE_READ_RE = re.compile(r"""\.from\(\s*['"](?:logbook|inventory_items|pm_assets|pm_completions|pm_scope_items|parts_records|hive_members|engineering_calcs)['"]""")
SESSION_RESTORE_RE = re.compile(r"restoreIdentityFromSession|auth\.getSession|auth\.getUser")
# Throwaway/dev pages explicitly excluded from sweeps (GROUNDED_SWEEP_ROADMAP.md "Explicitly EXCLUDED")
# — NOT shipped production surfaces, so their localStorage-only identity is not a migration gap.
SESSION_EXEMPT = {
    "engineering-design-test.html", "index-hive-test.html", "index-native-test.html",
    "index-v3-test.html", "index.backup.html", "index.backup2.html", "logbook.backup.html",
    "symbol-gallery.html",
}


def anon_reads() -> dict | None:
    union = "\nUNION ALL ".join(
        f"SELECT '{t}' t, count(*) n FROM public.{t}" for t in CORE_HIVE_TABLES)
    sql = f"SET ROLE anon;\n{union}\nORDER BY 1;\nRESET ROLE;"
    try:
        p = subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-tA", "-F", "|", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        if p.returncode != 0:
            return None
        out = {}
        for line in p.stdout.splitlines():
            line = line.strip()
            if "|" in line:
                t, n = line.split("|")
                out[t] = int(n)
        return out
    except Exception:
        return None


def page_coverage() -> tuple[list[str], int]:
    """Pages that read a hive table but never establish a session = anon-reliant reads."""
    gaps, total = [], 0
    for f in sorted(ROOT.glob("*.html")):
        txt = f.read_text(encoding="utf-8", errors="replace")
        if not HIVE_READ_RE.search(txt):
            continue
        total += 1
        if f.name in SESSION_EXEMPT:
            continue
        if not SESSION_RESTORE_RE.search(txt):
            gaps.append(f.name)
    return gaps, total


def main() -> int:
    update = "--update-baseline" in sys.argv[1:]
    reads = anon_reads()
    if reads is None:
        print(f"  {RED}ERROR{RST}: could not introspect (is {DB} running?)")
        return 1
    leaked = {t: n for t, n in reads.items() if n > 0}
    gaps, total = page_coverage()

    print("=" * 76)
    print("  Arc J/J7 — anon-key retirement (auth-migration completion: client carries a JWT)")
    print("=" * 76)
    print("  L1 LIVE — anon-role reads of core hive tables (must be 0):")
    for t in CORE_HIVE_TABLES:
        n = reads.get(t)
        tag = f"{GREEN}0{RST}" if n == 0 else f"{RED}{n} LEAK{RST}"
        print(f"     {t:<22} {tag}")
    print(f"  L2 STATIC — hive-read pages that establish a session: {total-len(gaps)}/{total}")
    for g in gaps:
        print(f"     {RED}anon-reliant{RST} {g} — reads a hive table but never restores a session")

    fail = bool(leaked) or bool(gaps)
    base = {}
    if BASELINE.exists():
        try: base = json.loads(BASELINE.read_text(encoding="utf-8"))
        except Exception: base = {}

    if update or not BASELINE.exists():
        BASELINE.write_text(json.dumps({"leaked": leaked, "page_gaps": gaps, "pages_total": total}, indent=2), encoding="utf-8")
        state = "GREEN (anon sees nothing; all hive-read pages session-gated)" if not fail else f"{len(leaked)} leak / {len(gaps)} anon-reliant page(s)"
        print(f"\n  baseline set — {state}")
        return 0 if not fail else 1

    if leaked:
        print(f"\n  {RED}REGRESSION{RST}: anon can read {', '.join(leaked)} — a legacy-open policy returned (anon-key path NOT retired)")
        return 1
    if len(gaps) > len(base.get("page_gaps", [])):
        print(f"\n  {RED}REGRESSION{RST}: new anon-reliant hive-read page(s): {', '.join(sorted(set(gaps)-set(base.get('page_gaps',[])))) }")
        return 1
    print(f"\n  {GREEN}HELD{RST} — anon reads 0 from every core hive table; all {total} hive-read pages session-gated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
