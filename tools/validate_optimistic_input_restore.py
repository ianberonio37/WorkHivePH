#!/usr/bin/env python3
"""
validate_optimistic_input_restore.py - DEEPWALK D4 optimistic-input-restore gate (2026-07-22).
================================================================================================
DEEPWALK FINDING #3 (live, assistant chat): `sendMessage` clears the chat input OPTIMISTICALLY
(`input.value = ''`) at the TOP - before the async AI turn - so it can immediately show the user bubble
+ typing indicator. But the `catch` block never restored it, so on a 429 / timeout / network failure the
user's typed question was WIPED from the input even though the error said "please wait a moment and try
again" - forcing a full retype to retry. (The `finally` correctly reset isLoading/send-btn - no UI-lock -
and the question survived as a bubble, just not in the input.)

FIX: the failure path reverts the optimistic clear - `if (!input.value.trim()) { input.value = text; }` -
so "try again" is one tap, guarded so it never clobbers a NEW question the user started typing during the
async wait. Live-verified both cases (restore-on-empty; preserve-a-new-question).

Sibling sweep (METHOD LAW): community `submitReply`/other send handlers clear their input AFTER a
successful write (only on `!error`), so a failure preserves the text - correct, not this class. The
optimistic clear-BEFORE-await is unique to the chat send (it must show the bubble first). Isolated.

THIS GATE locks the invariant on the curated optimistic-clear send handlers: a handler that clears its
input BEFORE the await MUST restore it on the failure path. Static (reads the fn body); `--selftest`
proves teeth. Adding a new optimistic-clear chat send is a conscious decision that must restore-on-fail
and extend the curated list.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"
CHECK_NAMES = ["validate_optimistic_input_restore"]
ROOT = Path(__file__).resolve().parent.parent

# page -> [(send fn, input var, text var)] — handlers that clear the input BEFORE the await.
OPTIMISTIC_SEND_HANDLERS = {
    "assistant.html": [("sendMessage", "input", "text")],
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


def _clears_optimistically(body: str, input_var: str) -> bool:
    # `<input_var>.value = ''` (the optimistic clear before the async work)
    return bool(re.search(re.escape(input_var) + r"\.value\s*=\s*['\"]['\"]", body))


def _restores_on_fail(body: str, input_var: str, text_var: str) -> bool:
    # a restore of the input from the captured text var, AFTER a catch. Accept the guarded form
    # `if (!input.value.trim()) { input.value = text; }` or a bare `input.value = text` in the catch.
    ci = body.find("catch")
    if ci == -1:
        return False
    tail = body[ci:]
    return bool(re.search(re.escape(input_var) + r"\.value\s*=\s*" + re.escape(text_var) + r"\b", tail))


def _check(body: str, input_var: str, text_var: str) -> tuple[bool, str]:
    if not _clears_optimistically(body, input_var):
        # no optimistic clear => not this class (handler must clear-after-success); pass by non-applicability
        return True, f"no optimistic `{input_var}.value=''` clear (clears-after-success pattern) - N/A"
    if _restores_on_fail(body, input_var, text_var):
        return True, f"clears optimistically AND restores `{input_var}.value={text_var}` on the failure path"
    return False, (f"clears `{input_var}.value=''` BEFORE the await but does NOT restore it in catch - a "
                   f"failed send WIPES the user's text (D4 recovery regression)")


def self_test() -> bool:
    ok = True
    good = ("input.value=''; addUserBubble(text); try{ await ask(); }catch(e){ addBubble(e); "
            "if(!input.value.trim()){ input.value = text; } }finally{}")
    bad = ("input.value=''; addUserBubble(text); try{ await ask(); }catch(e){ addBubble(e); "
           "showToast('failed'); }finally{}")
    na = ("const {error}=await db.from('t').insert(x); if(error){return;} "
          "document.getElementById('reply-content').value='';")  # clears a NAMED field after success, not `input`
    if not _check(good, "input", "text")[0]:
        print(f"{R}self-test FAIL: restoring handler wrongly FAILED.{X}"); ok = False
    if _check(bad, "input", "text")[0]:
        print(f"{R}self-test FAIL: no-restore handler wrongly PASSED.{X}"); ok = False
    if not _check(na, "input", "text")[0]:
        print(f"{R}self-test FAIL: clear-after-success handler wrongly FAILED (should be N/A-pass).{X}"); ok = False
    if not OPTIMISTIC_SEND_HANDLERS:
        print(f"{R}self-test FAIL: curated list empty.{X}"); ok = False
    print((G + "self-test PASS - optimistic-input-restore check has teeth." + X) if ok else (R + "self-test FAILED." + X))
    return ok


def main() -> int:
    if "--selftest" in sys.argv or "--self-test" in sys.argv:
        return 0 if self_test() else 1
    print(f"{B}DEEPWALK D4 gate: an optimistic input-clear on a chat send MUST be restored on failure{X}")
    fails = []
    for page, handlers in sorted(OPTIMISTIC_SEND_HANDLERS.items()):
        p = ROOT / page
        if not p.exists():
            print(f"  SKIP  {page} (absent)"); continue
        src = p.read_text(encoding="utf-8", errors="replace")
        for fn, input_var, text_var in handlers:
            body = _fn_body(src, fn)
            if body is None:
                print(f"  {R}FAIL{X}  {page}:{fn}() not found - renamed? re-point the gate."); fails.append(page); continue
            good, why = _check(body, input_var, text_var)
            if good:
                print(f"  {G}PASS{X}  {page}:{fn}() - {why}.")
            else:
                print(f"  {R}FAIL{X}  {page}:{fn}() - {why}."); fails.append(page)
    if fails:
        print(f"{R}FAIL: {len(fails)} optimistic-clear send handler(s) lose the user's text on failure.{X}")
        return 1
    print(f"{G}PASS - every curated optimistic-clear send handler restores the input on failure.{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
