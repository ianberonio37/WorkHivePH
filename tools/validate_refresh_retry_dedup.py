#!/usr/bin/env python3
"""
validate_refresh_retry_dedup.py - DEEPWALK D2 refresh-retry dedup gate (2026-07-22).
=====================================================================================
DEEPWALK FINDING #D2 (live-confirmed): a NON-idempotent client write (a fresh-id INSERT or a decrement/
increment RPC) carries no idempotency key, so a refresh-mid-submit then retry creates a DUPLICATE / double
effect. Live-confirmed self-cleaning probes:
  * logbook addEntry  -> a retry minted a fresh Date.now() id => a DUPLICATE logbook entry (2 rows).
  * inventory submitUse -> a retry ran inventory_deduct AGAIN => a DOUBLE stock deduction.
  * marketplace handlePostSubmit -> a retry => a DUPLICATE listing.
The button-lock (withButtonLock) only stops a SAME-PAGE double-tap; a refresh spawns a fresh page that
bypasses it. The FIRST write already landed server-side, so a pre-write check catches the retry.

FIX (central, METHOD LAW - one helper, N surfaces): `window.whRecentDuplicate(db, table, matchObj, opts)`
in utils.js queries for an identical row created within a tight window (returns its id or null; best-effort,
returns null on error so it never blocks a write). Each non-idempotent write handler calls it BEFORE the
write and, on a hit, skips + reassures the user. Live-verified all four: a retry dedups (no dup / no double
deduction); a different value is NOT matched (no false-block). Windows are tight (30s inserts / 15s stock
RPCs) and matches are SPECIFIC (exact qty_change, job_ref/note, title) so a legitimate rapid second write
is not false-blocked.

THIS GATE locks the invariant: (1) the central `whRecentDuplicate` helper EXISTS + is window-exposed in
utils.js; (2) every curated non-idempotent write handler CALLS it. Adding a new fresh-id-insert / decrement-
RPC handler is a conscious decision that must adopt the guard + extend the list. Static; `--selftest` proves
teeth.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"
CHECK_NAMES = ["validate_refresh_retry_dedup"]
ROOT = Path(__file__).resolve().parent.parent

CENTRAL_HELPER = ("utils.js", "whRecentDuplicate")
# page -> [(handler fn, what it writes)]  — every non-idempotent write vulnerable to refresh-retry.
DEDUP_HANDLERS = {
    "logbook.html":     [("addEntry", "logbook fresh-id insert")],
    "inventory.html":   [("submitUse", "inventory_deduct RPC"), ("submitRestock", "inventory_restock RPC")],
    "marketplace.html": [("handlePostSubmit", "marketplace_listings insert")],
}


def _fn_body(src: str, fn: str) -> str | None:
    m = re.search(r"(?:async\s+)?function\s+" + re.escape(fn) + r"\s*\([^)]*\)\s*\{", src)
    if not m:
        return None
    i = src.index("{", m.start())
    depth, j = 0, i
    while j < len(src):
        c = src[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
        j += 1
    return None


def _helper_defined() -> bool:
    p = ROOT / CENTRAL_HELPER[0]
    if not p.exists():
        return False
    src = p.read_text(encoding="utf-8", errors="replace")
    return bool(re.search(r"function\s+" + re.escape(CENTRAL_HELPER[1]) + r"\s*\(", src)
                and re.search(r"window\.\s*" + re.escape(CENTRAL_HELPER[1]) + r"\s*=", src))


def _check_handler(body: str) -> bool:
    return "whRecentDuplicate" in body


def self_test() -> bool:
    ok = True
    good = "const _d = await window.whRecentDuplicate(db,'logbook',{machine},{windowMs:30000}); if(_d){return;}"
    bad = "const {error} = await db.from('logbook').insert(payload).select();"
    if not _check_handler(good):
        print(f"{R}self-test FAIL: adopting handler wrongly FAILED.{X}"); ok = False
    if _check_handler(bad):
        print(f"{R}self-test FAIL: bare-insert handler wrongly PASSED.{X}"); ok = False
    if not DEDUP_HANDLERS:
        print(f"{R}self-test FAIL: curated handler list empty.{X}"); ok = False
    print((G + "self-test PASS - refresh-retry-dedup check has teeth." + X) if ok else (R + "self-test FAILED." + X))
    return ok


def main() -> int:
    if "--selftest" in sys.argv or "--self-test" in sys.argv:
        return 0 if self_test() else 1
    print(f"{B}DEEPWALK D2 gate: every non-idempotent write must guard against refresh-retry via whRecentDuplicate{X}")
    fails = []
    if not _helper_defined():
        print(f"  {R}FAIL{X}  central helper {CENTRAL_HELPER[1]}() missing/unexposed in {CENTRAL_HELPER[0]}.")
        fails.append(CENTRAL_HELPER[0])
    else:
        print(f"  {G}PASS{X}  central {CENTRAL_HELPER[1]}() defined + window-exposed in {CENTRAL_HELPER[0]}.")
    for page, handlers in sorted(DEDUP_HANDLERS.items()):
        p = ROOT / page
        if not p.exists():
            print(f"  SKIP  {page} (absent)"); continue
        src = p.read_text(encoding="utf-8", errors="replace")
        for fn, writes in handlers:
            body = _fn_body(src, fn)
            if body is None:
                print(f"  {R}FAIL{X}  {page}:{fn}() not found - renamed? re-point the gate."); fails.append(page); continue
            if _check_handler(body):
                print(f"  {G}PASS{X}  {page}:{fn}() ({writes}) - guards via whRecentDuplicate.")
            else:
                print(f"  {R}FAIL{X}  {page}:{fn}() ({writes}) - NO whRecentDuplicate guard; a refresh-retry "
                      f"duplicates/double-effects. DEEPWALK D2 regression.")
                fails.append(page)
    if fails:
        print(f"{R}FAIL: {len(fails)} non-idempotent write surface(s) lack a refresh-retry dedup guard.{X}")
        return 1
    print(f"{G}PASS - the central dedup helper exists and every curated non-idempotent write guards against "
          f"refresh-retry.{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
