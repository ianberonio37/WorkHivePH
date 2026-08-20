#!/usr/bin/env python3
"""validate_offline_write_guard.py — every USER-TRIGGERED write must refuse honestly when offline.

THE DEFECT THIS LOCKS (found 2026-07-29 while building the test bank's S2-pwa cell). marketplace.html
already had `svcRequireOnline()` — a one-line guard that toasts *"You're offline. <action> needs a
connection - nothing was sent, so nothing is half-done."* — and it was wired into exactly TWO of its
seven client-side writes. The other five fired straight into a dead network:

  svcSettle        the client taps "I paid" and receives a raw fetch error, with no statement of
                   whether the settlement landed. This is money.
  svcApplyVoucher  a voucher code redeemed into the void.
  svcPickQuote     choosing a provider - a race the client thinks they won.
  svcPickStar      a review that evaporates.
  svcClientCancel  worst shape of all: the CONFIRM DIALOG appears, the person commits to cancelling,
                   and then an opaque error leaves them unsure whether the job is cancelled.

marketplace-seller.html was the same story: `svcAccept` reasons carefully about the offline case in a
comment, and the other eight writes — including `svcFileTopup`, where the provider may have ALREADY
sent the GCash payment — had nothing.

WHY THE EXISTING GATES DID NOT CATCH IT. `degraded-state-central` proves every page adopts the shared
offline BANNER, and both pages did — the whole time. A passive banner is not a refusal: the button
still submits. `offline-queue-confirm` proves a queue drain does not treat 0 rows as synced, but these
surfaces deliberately do not queue (a hail or an accept is a race; a queued accept would claim a job
someone else already took). Adoption of a warning and correctness of a drain both passed while every
individual write was unguarded. This gate asserts the third thing: the WRITE ITSELF refuses.

THE INVARIANT: in a user-invokable function that performs a supabase write, an offline check must
appear BEFORE the first write call. Position matters — a check after the write is a post-mortem.

Usage:  python tools/validate_offline_write_guard.py [--selftest]
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

# The service-hailing surfaces. Deliberately narrow: these are the pages where a write commits money,
# claims a job, or closes a request, and where a silent failure costs a person something real.
PAGES = ["marketplace.html", "marketplace-seller.html"]

WRITE = re.compile(r"\.(insert|update|upsert|delete)\s*\(|db\.rpc\s*\(")
# ★THE NEGATION FORM WAS MISSING, AND IT IS THE COMMON ONE. This matched `navigator.onLine === false`
# but not `!navigator.onLine`, so a correctly-guarded write read as unguarded. Found 2026-08-18 on
# resume.html's saveCloud, which does better than refuse - `if (!navigator.onLine) { toast('Offline:
# saved on this device, will sync later.'); await saveLocal(); return; }` - and was still reported as a
# missing guard while sweeping the roster. A validator that cannot see the idiomatic spelling of the
# thing it demands manufactures work and erodes trust in its own red.
# The AFTER-the-write check below still applies, so broadening this cannot excuse a post-mortem guard.
GUARD = re.compile(r"RequireOnline\s*\(|!\s*navigator\.onLine\b|navigator\.onLine\s*===?\s*false")
FUNC = re.compile(r"async\s+function\s+([A-Za-z_$][\w$]*)\s*\(")

# RPCs that only READ. A read failing offline is a stale screen, not a lost commitment — the page's
# empty/error state covers it. Listed by name so the exemption is auditable rather than a heuristic.
READ_ONLY_RPC = {
    "my_service_provider_ids", "auth_worker_names",
    # Added 2026-08-18 after this list's incompleteness produced two false "unguarded write" findings
    # while sweeping the 22 roster pages: community's openPersonCard was flagged for calling
    # get_community_reputation, and index's submitSignUp matched on check_username_available. Both only
    # READ. A read failing offline is a stale screen, not a lost commitment, and the page's empty/error
    # state covers it - the same reason the original two are exempt. Listed by NAME so every exemption
    # stays auditable rather than becoming a name-shaped heuristic that quietly excuses real writes.
    "get_community_reputation", "check_username_available",
    "find_hive_by_code", "get_project_budget", "get_hive_trade_peers",
    "search_voice_journal_entries",
}


def body_of(src: str, start: int) -> tuple[str, int]:
    """Balanced-brace extraction. A fixed character window would silently truncate whenever a comment
    or a new branch grew the function ([[feedback_fixed_char_window_validator_is_brittle]])."""
    i = src.find("{", start)
    if i < 0:
        return "", start
    depth, j, n = 0, i, len(src)
    while j < n:
        c = src[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1], j
        j += 1
    return src[i:], n


def user_invokable(src: str, name: str) -> bool:
    """Reachable from a person: an inline handler or a window attachment. Internal loaders that write
    (a background sync, a render helper) are a different problem with a different fix."""
    return (f'window.{name} =' in src or f'window.{name}=' in src
            or f'onclick="{name}(' in src or f"onclick='{name}(" in src
            or f'onchange="{name}(' in src or f'onsubmit="{name}(' in src)


def scan(src: str, path: str):
    """-> (checked, [(fn, why)])"""
    findings, checked = [], 0
    for m in FUNC.finditer(src):
        name = m.group(1)
        body, _end = body_of(src, m.end())
        if not body:
            continue
        w = WRITE.search(body)
        if not w:
            continue
        if w.group(0).startswith("db.rpc"):
            after = body[w.end():w.end() + 60]
            rpc = re.search(r"['\"]([\w]+)['\"]", after)
            if rpc and rpc.group(1) in READ_ONLY_RPC:
                continue
        if not user_invokable(src, name):
            continue
        checked += 1
        g = GUARD.search(body)
        if not g:
            findings.append((name, "writes with NO offline check at all"))
        elif g.start() > w.start():
            findings.append((name, "the offline check sits AFTER the write — a post-mortem, not a refusal"))
    return checked, findings


def main():
    if "--selftest" in sys.argv:
        return selftest()
    total, bad = 0, []
    print("=" * 84)
    print(f"  {BOLD}Offline write guard — a user-triggered write must refuse before it fires{RST}")
    print("=" * 84)
    for page in PAGES:
        p = os.path.join(ROOT, page)
        if not os.path.exists(p):
            print(f"  {YEL}SKIP{RST} {page} not found")
            continue
        with open(p, encoding="utf-8") as f:
            src = f.read()
        checked, findings = scan(src, page)
        total += checked
        mark = GREEN + "OK  " + RST if not findings else RED + "FAIL" + RST
        print(f"  {mark}  {page}  {DIM}{checked} user-triggered write function(s){RST}")
        for fn, why in findings:
            print(f"        {RED}{fn}{RST} — {why}")
            bad.append((page, fn, why))
    print()
    if bad:
        print(f"{RED}FAIL{RST} — {len(bad)} of {total} user-triggered writes can fire into a dead "
              f"network. The person is told nothing, or told a raw fetch error.")
        return 1
    print(f"{GREEN}PASS{RST} — all {total} user-triggered writes on the service surfaces check "
          f"connectivity BEFORE writing, and say so in the user's own terms")
    return 0


def selftest():
    """Teeth in both directions, plus the ORDER check — the subtle half."""
    ok = True
    guarded = ('async function svcX(){ if(!svcRequireOnline("Doing it")) return; '
               'await db.from("t").insert({}); } window.svcX = svcX;')
    naked = 'async function svcY(){ await db.from("t").insert({}); } window.svcY = svcY;'
    late = ('async function svcZ(){ await db.from("t").insert({}); '
            'if (navigator.onLine === false) return; } window.svcZ = svcZ;')
    internal = 'async function _loadThing(){ await db.from("t").update({}); }'
    for src, want, label in ((guarded, 0, "a guarded write PASSES"),
                             (naked, 1, "an UNGUARDED write is caught"),
                             (late, 1, "a check placed AFTER the write is caught (order matters)"),
                             (internal, 0, "an internal, non-user-invokable writer is not flagged")):
        _c, f = scan(src, "selftest")
        if len(f) != want:
            print(f"  {RED}FAIL{RST} {label} (found {len(f)}, expected {want})"); ok = False
        else:
            print(f"  {GREEN}PASS{RST} {label}")
    print(f"\n  SELFTEST: {GREEN + 'PASS' + RST if ok else RED + 'FAIL' + RST}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
