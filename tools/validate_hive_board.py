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
# L5 (P6 concurrent-edit, 2026-07-19): approveItem/rejectItem MUST carry the P6-C1 optimistic lock
# — the status update is filtered `.eq('status','pending')` so a concurrent approve/reject (or a
# double-click / stale queue card) on an ALREADY-resolved item is a 0-row no-op, never a re-flip.
# Verified live (rolled-back DB race: writerA approve=1 row, writerB reject=0 rows, final=approved).
# `[^;]` (not `[\s\S]`) bounds the match to a SINGLE chained statement — the optimistic lock lives in
# the same `db...update(...).eq(...)` chain as the update, so it must not span across the `;` into the
# neighbouring approve/reject function (that would let a guard-less update pass by borrowing its sibling's).
P6_APPROVE_LOCK = re.compile(r"""status:\s*['"]approved['"][^;]{0,300}?\.eq\(\s*['"]status['"]\s*,\s*['"]pending['"]\s*\)""")
P6_REJECT_LOCK  = re.compile(r"""status:\s*['"]rejected['"][^;]{0,300}?\.eq\(\s*['"]status['"]\s*,\s*['"]pending['"]\s*\)""")
# L6 (P7 UI-locks + recovery, 2026-07-19): the approval-queue read must be HONEST-DEGRADED — a read
# FAILURE sets `_approvalReadErr` (vs a legitimately-empty queue) AND the render keeps the section
# visible on error (`total === 0 && !_approvalReadErr`) so a failed load shows "couldn't load", never
# a fake "All caught up" that would HIDE pending items awaiting supervisor approval (P2-01/P7-02).
P7_DEGRADED_SET      = re.compile(r"""_approvalReadErr\s*=\s*!!\(""")
P7_DEGRADED_CONSUMED = re.compile(r"""total\s*===\s*0\s*&&\s*!_approvalReadErr""")


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
    if not P6_APPROVE_LOCK.search(html):
        fails.append("L5 approveItem lost its P6-C1 optimistic lock (.eq('status','pending') on the "
                     "'approved' update) — a concurrent approve/reject can re-flip a resolved item.")
    if not P6_REJECT_LOCK.search(html):
        fails.append("L5 rejectItem lost its P6-C1 optimistic lock (.eq('status','pending') on the "
                     "'rejected' update) — a concurrent approve/reject can re-flip a resolved item.")
    if not P7_DEGRADED_SET.search(html):
        fails.append("L6 the approval-queue read no longer sets `_approvalReadErr` from a read error "
                     "(P7-02 honest-degraded) — a failed load could render a fake-empty 'All caught up'.")
    if not P7_DEGRADED_CONSUMED.search(html):
        fails.append("L6 renderApprovalQueue no longer keeps the queue visible on error "
                     "(`total === 0 && !_approvalReadErr`) — a failed read would HIDE pending items.")
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
    <script>
    async function approveItem(t,id){ await db.from(t).update({ status: 'approved', approved_by: WN })
      .eq('id', id).eq('hive_id', HIVE_ID).eq('status', 'pending').select('id'); }
    async function rejectItem(t,id){ await db.from(t).update({ status: 'rejected' })
      .eq('id', id).eq('hive_id', HIVE_ID).eq('status', 'pending').select('id'); }
    _approvalReadErr = !!(assetsRes.error || partsRes.error);
    queueEl.classList.toggle('hidden', total === 0 && !_approvalReadErr);
    </script>"""
    if check_text(good):
        print(f"{R}self-test FAIL: flagged a compliant page: {check_text(good)}{X}"); ok = False
    if not check_text("""<script>db.from('assets').update({})</script>"""):
        print(f"{R}self-test FAIL: missed a db.from('assets') write.{X}"); ok = False
    if not check_text("<style>#supervisor-summary.hidden{min-height:618px}</style>"):
        print(f"{R}self-test FAIL: missed an un-role-scoped reserve.{X}"); ok = False
    # L5: an approve update WITHOUT the pending guard must be caught (re-flip race open). Build a
    # standalone snippet that has the reject lock + degraded markers but NOT the approve lock, so
    # only the L5-approve failure fires.
    no_approve_lock = """<style>html.is-supervisor #supervisor-summary.hidden{min-height:618px}</style>
      <script>document.documentElement.classList.add('is-supervisor');
      db.from(t).update({ status: 'approved' }).eq('id', id).select('id');
      db.from(t).update({ status: 'rejected' }).eq('id', id).eq('status', 'pending').select('id');
      _approvalReadErr = !!(r.error); queueEl.classList.toggle('h', total === 0 && !_approvalReadErr);</script>"""
    if not any("L5 approveItem" in f for f in check_text(no_approve_lock)):
        print(f"{R}self-test FAIL: missed approveItem missing the P6 optimistic lock.{X}"); ok = False
    # L6: a render that hides the queue on a bare `total === 0` (no !_approvalReadErr) must be caught.
    no_degraded_consume = """<style>html.is-supervisor #supervisor-summary.hidden{min-height:618px}</style>
      <script>document.documentElement.classList.add('is-supervisor');
      db.from(t).update({ status: 'approved' }).eq('id', id).eq('status', 'pending').select('id');
      db.from(t).update({ status: 'rejected' }).eq('id', id).eq('status', 'pending').select('id');
      _approvalReadErr = !!(r.error); queueEl.classList.toggle('h', total === 0);</script>"""
    if not any("L6 renderApprovalQueue" in f for f in check_text(no_degraded_consume)):
        print(f"{R}self-test FAIL: missed the queue hiding on error (honest-degraded lost).{X}"); ok = False
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
