#!/usr/bin/env python3
"""
validate_hive_board.py - Hive Board Deep Arc (PDDA, 2026-07-10) regression gate.
=================================================================================
Locks the structural fixes made this arc so they can't silently regress:

  L1  hive.html must NOT write to the DROPPED `assets` table. Asset approve/reject
      was calling `db.from('assets')` (dropped by 20260512000009_phase_5c_drop_assets)
      -> 100%-broken approvals. The queue reads `asset_nodes`; the write must too.
  L2  The supervisor-only CLS reserve for #supervisor-summary must be ROLE-SCOPED
      (`html.is-supervisor #supervisor-summary.hidden`) + the `is-supervisor` stamp
      script must exist. Un-scoped, it left a ~636px empty VOID on the WORKER board.
  L3  The I-axis RLS hardening migration must be present (audit-log append-only +
      actor-bind, inventory owner/supervisor-write, anon_insert_hives dropped) so a
      rebuild-from-migrations keeps the holes closed (they were live-only = drift).

Exit 0 = all invariants hold. `--self-test` proves the checks have teeth.
"""
from __future__ import annotations
import io, sys, re
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
HIVE = ROOT / "hive.html"
MIGRATIONS = ROOT / "supabase" / "migrations"
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"

CHECK_NAMES = ["validate_hive_board"]

# L1: any db.from('assets') / db.from("assets") — the dropped table.
DROPPED_ASSETS = re.compile(r"""\.from\(\s*['"]assets['"]\s*\)""")
# L2: role-scoped reserve + the stamp.
ROLE_RESERVE = re.compile(r"html\.is-supervisor\s+#supervisor-summary\.hidden")
STAMP = re.compile(r"classList\.add\(\s*['\"]is-supervisor['\"]\s*\)")
# L4: hive CREATION must NOT chain .select() on the `hives` insert — an INSERT ... RETURNING
# applies the `hives` SELECT policy (id IN user_hive_ids()) to the brand-new hive, which the
# creator can't read yet (membership is inserted afterwards), so it 403s and hive creation
# breaks. Match a `.from('hives').insert(...)` whose chain then hits `.select(`.
CREATE_RETURNING = re.compile(r"""\.from\(\s*['"]hives['"]\s*\)\s*\.insert\((?:[^;]{0,400}?)\.select\(""", re.S)


def check_text(html: str) -> list[str]:
    """Return a list of failure messages for the hive.html invariants."""
    fails = []
    if DROPPED_ASSETS.search(html):
        fails.append("L1 hive.html writes to the DROPPED `assets` table (use `asset_nodes`)")
    if not ROLE_RESERVE.search(html):
        fails.append("L2 #supervisor-summary reserve is NOT role-scoped to `html.is-supervisor` "
                     "(worker board gets a ~636px empty void)")
    if not STAMP.search(html):
        fails.append("L2 the `html.is-supervisor` stamp script is missing")
    if CREATE_RETURNING.search(html):
        fails.append("L4 hive creation chains `.select()` on the `hives` insert — INSERT...RETURNING "
                     "hits the SELECT policy on a hive the creator can't read yet (403). "
                     "Client-generate the id and insert WITHOUT .select().")
    return fails


def migration_present() -> bool:
    if not MIGRATIONS.exists():
        return False
    for p in MIGRATIONS.glob("*hive_board_security_hardening*.sql"):
        t = p.read_text(encoding="utf-8", errors="replace")
        if "wh_bind_audit_actor" in t and "anon_insert_hives" in t:
            return True
    return False


def self_test() -> bool:
    ok = True
    good = """<script>if(_role==='supervisor')document.documentElement.classList.add('is-supervisor');</script>
    <style>html.is-supervisor #supervisor-summary.hidden { min-height:618px; }</style>
    <script>approveItem('asset_nodes', id)</script>"""
    if check_text(good):
        print(f"{R}self-test FAIL: flagged a compliant page.{X}"); ok = False
    if not check_text("""<script>db.from('assets').update({})</script>"""):
        print(f"{R}self-test FAIL: missed a db.from('assets') write.{X}"); ok = False
    if not check_text("<style>#supervisor-summary.hidden{min-height:618px}</style>"):
        print(f"{R}self-test FAIL: missed an un-role-scoped reserve.{X}"); ok = False
    # L4 tests the CREATE_RETURNING regex directly (check_text also runs the L2 presence
    # checks, which fire on any bare snippet lacking the reserve/stamp).
    if not CREATE_RETURNING.search("const {data} = await db.from('hives').insert({name}).select().single();"):
        print(f"{R}self-test FAIL: missed hives insert chaining .select() (403 create bug).{X}"); ok = False
    if CREATE_RETURNING.search("await db.from('hives').insert({id, name});"):
        print(f"{R}self-test FAIL: flagged a correct no-RETURNING hives insert.{X}"); ok = False
    print((G + "self-test PASS - hive-board gate has teeth." + X) if ok else (R + "self-test FAILED." + X))
    return ok


def main() -> int:
    if "--self-test" in sys.argv:
        return 0 if self_test() else 1

    print(f"{B}Hive Board regression gate (PDDA 2026-07-10){X}")
    if not HIVE.exists():
        print(f"  {R}FAIL{X} hive.html not found"); return 1
    fails = check_text(HIVE.read_text(encoding="utf-8", errors="replace"))
    if not migration_present():
        fails.append("L3 the hive_board_security_hardening migration is missing or incomplete "
                     "(needs wh_bind_audit_actor + anon_insert_hives drop)")

    for f in fails:
        print(f"  {R}FAIL{X} {f}")
    if fails:
        print(f"{R}FAIL: {len(fails)} hive-board invariant(s) regressed.{X}")
        return 1
    print(f"{G}PASS - asset write on asset_nodes, reserve role-scoped, RLS migration present.{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
