#!/usr/bin/env python3
"""
validate_qty_input_contract.py - DEEPWALK D5 number-input-contract gate (qty + price, 2026-07-22).
==================================================================================================
Locks ONE class across TWO central parsers: "a `<input type=number>`'s DECLARED min/step/bounds are not
enforced on the WRITE path" — because the modal submits via a button (native form validation never fires)
OR the form is `novalidate`. Findings + fixes (both live 2026-07-22):
  • FINDING #2 (qty, inventory Use/Restock): 2.5 / 1e-9 slipped past a bare parseFloat()>0 => a fractional
    stock deduction. Fixed via central `whParseQty` (honors integer step + min).
  • FINDING #4 (price, marketplace post/edit): the `novalidate` forms let a negative price hit the DB
    price_nonneg CHECK (raw 23514) and an over-precision value hit numeric(14,2) overflow — both cryptic
    DB errors to the seller. Fixed via central `whParsePrice` (blank=negotiable, 0=free, 2dp, ₱10M cap).
Both are the same METHOD-LAW shape: one central parser adopted on N surfaces, not N per-page checks.

DEEPWALK FINDING #2 (live, inventory Use/Restock): a qty `<input type="number" min="1" step="1">`
DECLARES an integer >= 1 contract, but the modal submits via a BUTTON handler, not a native <form>, so
the browser NEVER enforces min/step. `submitUse`/`submitRestock` read the value with a bare
`parseFloat(el.value) || 0` and only checked `qty <= 0` / `qty > on_hand` - so a typed/pasted **2.5** or
**1e-9** sailed through and deducted a FRACTIONAL / absurd quantity, corrupting the integer stock count
(which feeds analytics parts-consumption, stock alerts, and the stockout forecast). `submitRestock` was
worse: `if (qty <= 0) return;` silently no-op'd with ZERO feedback.

FIX (central, METHOD LAW - one gap on 2 surfaces, not 2 per-page patches): `window.whParseQty(inputEl)`
in utils.js honors the input's OWN declared min/step (integer step => whole numbers only; min => a floor)
and returns {ok, qty, error}; `submitUse` + `submitRestock` adopt it (the on-hand CEILING stays with the
caller, which owns the unit). Live-verified: 2.5 and 1e-9 now blocked ("Enter a whole number"), a valid
integer still reaches the RPC, the on-hand ceiling still fires.

THIS GATE locks the invariant: (1) the central `whParseQty` helper EXISTS in utils.js; (2) every curated
qty-write handler ADOPTS it; (3) no curated handler still reads its qty input with a bare
`parseFloat(document.getElementById('<id>')...)` outside the whParseQty fallback (a naive revert). Adding
a new qty-write modal is a conscious decision that must adopt whParseQty and extend the curated list.
Static (reads HTML/JS source); `--selftest` proves teeth.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"
CHECK_NAMES = ["validate_qty_input_contract"]
ROOT = Path(__file__).resolve().parent.parent

CENTRAL_HELPERS = [("utils.js", "whParseQty"), ("utils.js", "whParsePrice")]
# page -> [(handler fn, input id, central helper)] — every number-write handler that must validate its
# input's DECLARED contract via the named central parser. Two helpers, same class ("a number input's
# min/step/bounds aren't enforced on the write path — native form validation is off or bypassed"):
#   whParseQty   = integer qty (inventory Use/Restock, step=1 min=1)
#   whParsePrice = currency (marketplace post/edit, min=0 step=0.01, `novalidate` form → cryptic DB error)
NUMBER_WRITE_HANDLERS = {
    "inventory.html":          [("submitUse", "use-qty", "whParseQty"), ("submitRestock", "restock-qty", "whParseQty")],
    "marketplace.html":        [("handlePostSubmit", "post-price", "whParsePrice")],
    "marketplace-seller.html": [("handleEditSubmit", "edit-price", "whParsePrice")],
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


def _helper_defined(helper_file: str, helper: str) -> bool:
    p = ROOT / helper_file
    if not p.exists():
        return False
    src = p.read_text(encoding="utf-8", errors="replace")
    return bool(re.search(r"function\s+" + re.escape(helper) + r"\s*\(", src)
                and re.search(r"window\.\s*" + re.escape(helper) + r"\s*=", src))


def _check_handler(body: str, input_id: str, helper: str) -> tuple[bool, str]:
    adopts = helper in body
    # a BARE parseFloat/Number read of THIS input via an inline getElementById, not inside the helper's
    # fallback expression (which reads a captured `_qEl`/`_priceEl` var, so it won't match this pattern).
    bare = re.search(r"(parseFloat|Number)\s*\(\s*document\.getElementById\(\s*['\"]" + re.escape(input_id) + r"['\"]", body)
    if not adopts:
        return False, f"does NOT call {helper} (bare number read = the D5 unenforced-contract hole)"
    if bare:
        return False, f"still has a bare parseFloat/Number read of #{input_id} outside the {helper} fallback"
    return True, f"adopts {helper}"


def self_test() -> bool:
    ok = True
    good = ("const _qr = window.whParseQty(_qEl,{label:'Q'}); if(!_qr.ok){return;} const qty=_qr.qty;")
    bad_bare = ("const qty = parseFloat(document.getElementById('use-qty').value)||0; if(qty<=0){return;}")
    bad_leftover = ("const _qr = window.whParseQty(_qEl); const legacy = parseFloat(document.getElementById('use-qty').value);")
    good_price = ("const _priceRes = window.whParsePrice(_priceEl); if(!_priceRes.ok){return;} const price=_priceRes.value;")
    if not _check_handler(good, "use-qty", "whParseQty")[0]:
        print(f"{R}self-test FAIL: adopting qty handler wrongly FAILED.{X}"); ok = False
    if _check_handler(bad_bare, "use-qty", "whParseQty")[0]:
        print(f"{R}self-test FAIL: bare-parseFloat handler wrongly PASSED.{X}"); ok = False
    if _check_handler(bad_leftover, "use-qty", "whParseQty")[0]:
        print(f"{R}self-test FAIL: leftover-bare-read handler wrongly PASSED.{X}"); ok = False
    if not _check_handler(good_price, "post-price", "whParsePrice")[0]:
        print(f"{R}self-test FAIL: adopting price handler wrongly FAILED.{X}"); ok = False
    if _check_handler(good, "use-qty", "whParsePrice")[0]:  # wrong helper for the body => must FAIL
        print(f"{R}self-test FAIL: helper-mismatch wrongly PASSED.{X}"); ok = False
    if not NUMBER_WRITE_HANDLERS:
        print(f"{R}self-test FAIL: curated handler list empty.{X}"); ok = False
    print((G + "self-test PASS - number-input-contract check has teeth." + X) if ok else (R + "self-test FAILED." + X))
    return ok


def main() -> int:
    if "--selftest" in sys.argv or "--self-test" in sys.argv:
        return 0 if self_test() else 1
    print(f"{B}DEEPWALK D5 gate: every number-write handler must honor its input's declared contract via a central parser{X}")
    fails = []
    for helper_file, helper in CENTRAL_HELPERS:
        if not _helper_defined(helper_file, helper):
            print(f"  {R}FAIL{X}  central helper {helper}() missing/unexposed in {helper_file}.")
            fails.append(helper_file)
        else:
            print(f"  {G}PASS{X}  central {helper}() defined + window-exposed in {helper_file}.")
    for page, handlers in sorted(NUMBER_WRITE_HANDLERS.items()):
        p = ROOT / page
        if not p.exists():
            print(f"  SKIP  {page} (absent)"); continue
        src = p.read_text(encoding="utf-8", errors="replace")
        for fn, input_id, helper in handlers:
            body = _fn_body(src, fn)
            if body is None:
                print(f"  {R}FAIL{X}  {page}:{fn}() not found - renamed? re-point the gate."); fails.append(page); continue
            good, why = _check_handler(body, input_id, helper)
            if good:
                print(f"  {G}PASS{X}  {page}:{fn}() ({input_id}) - {why}.")
            else:
                print(f"  {R}FAIL{X}  {page}:{fn}() ({input_id}) - {why}. DEEPWALK D5 regression.")
                fails.append(page)
    if fails:
        print(f"{R}FAIL: {len(fails)} number-write surface(s) do not enforce the input's declared contract - "
              f"a fractional/absurd qty or a negative/over-precision price can reach the DB.{X}")
        return 1
    print(f"{G}PASS - the central number parsers exist and every curated number-write handler enforces its "
          f"input's declared contract.{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
