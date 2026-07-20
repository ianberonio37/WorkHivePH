#!/usr/bin/env python3
"""
validate_approval_lock.py - PER_PAGE_BUGHUNT P6/P7 approval-lock class gate (2026-07-19).
==========================================================================================
Locks the "approval write MUST carry an optimistic lock" invariant platform-wide, so the
asset-hub FMEA/strategy approval-lock gap (found + fixed 2026-07-19) can't recur on any page.

THE BUG CLASS: a client approve-write that stamps `approved_at: new Date()` WITHOUT an
optimistic guard is a last-write-wins race — a concurrent approve / double-click / stale card
silently OVERWRITES the first supervisor's approval attribution (approved_by/approved_at), an
accountability leak. Live-proven on `rcm_fmea_modes`: writerB's guard-less re-approve affected
1 row and overwrote 'Supervisor A'. The fix (mirroring approveAssetNode / approveCO) adds either
`.eq('status','pending')` or `.is('approved_at', null)` to the SAME chained update + a 0-row
no-op check.

THE RULE: every `db.from(...).update({ ... approved_at: new Date()... })` that SETS an approval
(positive stamp — NOT a clear/restore where `approved_at: null`) must, within the same chained
statement (bounded by `;`), carry `.eq('status', 'pending')` OR `.is('approved_at', null)`.

Exit 0 = all approval writes guarded. `--self-test` proves the check has teeth. Static (no stack).
"""
from __future__ import annotations
import io, sys, re
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"
CHECK_NAMES = ["validate_approval_lock"]

# A positive approval stamp inside an .update({...}) object literal: `approved_at: new Date(`.
POSITIVE_STAMP = re.compile(r"approved_at\s*:\s*new\s+Date\s*\(")
# A clear/restore (approved_at reset to null) is NOT an approval -> exempt.
CLEAR_STAMP = re.compile(r"approved_at\s*:\s*null")
# The optimistic lock: either a status='pending' filter or an approved_at IS NULL filter.
LOCK = re.compile(r"""\.eq\(\s*['"]status['"]\s*,\s*['"]pending['"]\s*\)|\.is\(\s*['"]approved_at['"]\s*,\s*null\s*\)""")


def _statements(html: str) -> list[str]:
    """Split into `.update(` ... `;` chained-statement slices (each a candidate approval write)."""
    out = []
    for m in re.finditer(r"\.update\(", html):
        start = m.start()
        semi = html.find(";", start)
        # cap the slice so a missing `;` can't swallow the rest of the file
        end = semi if 0 <= semi - start <= 1200 else start + 1200
        out.append(html[start:end])
    return out


def scan_html(html: str, label: str) -> list[str]:
    fails = []
    for stmt in _statements(html):
        if not POSITIVE_STAMP.search(stmt):
            continue                      # not an approval stamp
        if CLEAR_STAMP.search(stmt):
            continue                      # a restore/clear (approved_at: null) — exempt
        if not LOCK.search(stmt):
            snippet = re.sub(r"\s+", " ", stmt).strip()[:90]
            fails.append(f"{label}: approval write lacks an optimistic lock "
                         f"(need .eq('status','pending') or .is('approved_at',null)) -> {snippet}...")
    return fails


def self_test() -> bool:
    ok = True
    good = "await db.from('t').update({ approved_by: WN, approved_at: new Date().toISOString() }).eq('id', id).eq('status', 'pending').select('id');"
    good2 = "await db.from('t').update({ approved_at: new Date().toISOString() }).eq('id', id).is('approved_at', null).select('id');"
    clear = "await db.from('t').update({ status: 'pending', approved_by: null, approved_at: null }).eq('id', id);"
    bad = "await db.from('t').update({ approved_by: WN, approved_at: new Date().toISOString() }).eq('id', id).eq('hive_id', H);"
    if scan_html(good, "good"): print(f"{R}self-test FAIL: flagged a status-pending-locked approval.{X}"); ok = False
    if scan_html(good2, "good2"): print(f"{R}self-test FAIL: flagged an approved_at-null-locked approval.{X}"); ok = False
    if scan_html(clear, "clear"): print(f"{R}self-test FAIL: flagged a clear/restore write.{X}"); ok = False
    if not scan_html(bad, "bad"): print(f"{R}self-test FAIL: missed an UNLOCKED approval write.{X}"); ok = False
    print((G + "self-test PASS - approval-lock gate has teeth." + X) if ok else (R + "self-test FAILED." + X))
    return ok


def main() -> int:
    if "--self-test" in sys.argv or "--selftest" in sys.argv:
        return 0 if self_test() else 1
    print(f"{B}Approval-lock class gate (P6/P7 optimistic-lock on every approve-write){X}")
    fails = []
    scanned = 0
    for p in sorted(ROOT.glob("*.html")):
        try:
            html = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        scanned += 1
        fails.extend(scan_html(html, p.name))
    for f in fails:
        print(f"  {R}FAIL{X} {f}")
    if fails:
        print(f"{R}FAIL: {len(fails)} unlocked approval write(s) across {scanned} pages.{X}")
        return 1
    print(f"{G}PASS - every approval write across {scanned} pages carries an optimistic lock.{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
