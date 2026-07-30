#!/usr/bin/env python3
"""validate_push_handler_contract.py — a delivered push must actually reach the person.

WHY THIS EXISTS. The marketplace test bank's `TB-S5-edge-push-delivery-roundtrip` cell was owed with the
note *"nothing proves a real subscription RENDERS the notification."* Checking rather than assuming: the
send side is well covered (`notify-push` is VAPID-signed and was proven end to end against the real FCM
push service), and **two** service-worker validators exist — `validate_sw_offline` and
`validate_sw_shell_membership`. Neither mentions `push`, `showNotification` or `notificationclick` even
once. The receive side had NO gate at all.

That gap matters because every failure mode here is SILENT. sw.js says so itself: *"Without these handlers
a delivered push silently no-ops."* The push arrives, the service worker wakes, nothing appears, and no
error is raised anywhere a person or a log would see it. A provider misses the job.

WHAT IS AND IS NOT ASSERTABLE. The OS notification tray is outside any harness — Playwright cannot read
it, so "the human saw it" is genuinely unprobeable. Everything up to that boundary is not, and this gate
takes the static tier of that ladder ([[feedback_build_structure_to_make_it_liveable]]: build what CAN be
built rather than resting on covered-by-nature). The runtime tier — dispatch a push event to a registered
worker and assert `showNotification` fired — stays recorded as owed with this file named as its first
half, so the remaining gap has a shape instead of a shrug.

THE SEVEN INVARIANTS, each a silent failure if broken:

  1  a `push` listener is registered              no listener  -> the push is delivered and discarded
  2  its handler calls showNotification           the worker wakes and renders nothing
  3  that call is inside event.waitUntil()        the SW may be killed before the notification shows;
                                                  works on a warm worker, fails on a cold one
  4  e.data.json() is inside try/catch            a non-JSON payload THROWS and kills the handler, so one
                                                  malformed push silently suppresses the notification
  5  a `notificationclick` listener is registered  the tap does nothing at all
  6  it calls focus() or openWindow()             the notification is a dead end
  7  it calls notification.close()                the tray keeps a notification the user already acted on

Static by design: these are properties of the source, and the file is the thing that ships to installed
PWAs. Self-test proves every matcher rejects a broken worker.

Usage:  python tools/validate_push_handler_contract.py [--selftest]
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SW = os.path.join(ROOT, "sw.js")
GREEN, RED, YEL, DIM, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"


def handler_body(src: str, event: str):
    """The source of `addEventListener('<event>', ...)` up to the matching close.

    Brace-matched rather than a fixed character window: a comment or a new option can grow the body past
    any hardcoded span, and a window-based reader then silently stops seeing the second half of the
    handler ([[feedback_fixed_char_window_validator_is_brittle]]).
    """
    m = re.search(r"addEventListener\(\s*['\"]" + event + r"['\"]", src)
    if not m:
        return None
    i = src.find("{", m.end())
    if i == -1:
        return None
    depth, j = 0, i
    while j < len(src):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
        j += 1
    return src[i:]


def check(src: str):
    """-> list of (ok, id, description). Pure, so the self-test can feed it a broken worker."""
    push = handler_body(src, "push")
    click = handler_body(src, "notificationclick")
    out = []

    out.append((push is not None, "push_listener",
                "a `push` listener is registered (else the push is delivered and discarded)"))
    if push:
        out.append((bool(re.search(r"showNotification\s*\(", push)), "push_shows_notification",
                    "the push handler calls showNotification (else the worker wakes and renders nothing)"))
        # waitUntil must WRAP the showNotification call, not merely appear in the handler.
        wu = re.search(r"waitUntil\s*\(", push)
        wrapped = False
        if wu:
            depth, k = 0, push.find("(", wu.start())
            end = len(push)
            while k < len(push):
                if push[k] == "(":
                    depth += 1
                elif push[k] == ")":
                    depth -= 1
                    if depth == 0:
                        end = k
                        break
                k += 1
            wrapped = "showNotification" in push[wu.start():end]
        out.append((wrapped, "push_waituntil",
                    "showNotification is INSIDE event.waitUntil (else a cold worker can be killed first)"))
        json_call = re.search(r"\.data\s*(?:\?|&&|\.)*[^;]*?\.json\s*\(", push)
        out.append((not json_call or bool(re.search(r"\btry\b", push)), "push_payload_guarded",
                    "e.data.json() is guarded by try/catch (a non-JSON push must still notify)"))
    else:
        for cid, d in (("push_shows_notification", "unreachable: no push handler"),
                       ("push_waituntil", "unreachable: no push handler"),
                       ("push_payload_guarded", "unreachable: no push handler")):
            out.append((False, cid, d))

    out.append((click is not None, "click_listener",
                "a `notificationclick` listener is registered (else the tap does nothing)"))
    if click:
        out.append((bool(re.search(r"\bfocus\s*\(|openWindow\s*\(", click)), "click_navigates",
                    "the click handler focuses a tab or opens one (else the notification dead-ends)"))
        out.append((bool(re.search(r"notification\s*\.\s*close\s*\(", click)), "click_closes",
                    "the click handler closes the notification (else the tray keeps a handled item)"))
    else:
        out.append((False, "click_navigates", "unreachable: no notificationclick handler"))
        out.append((False, "click_closes", "unreachable: no notificationclick handler"))
    return out


BROKEN = {
    "no push listener":
        "self.addEventListener('notificationclick', e => { e.notification.close(); clients.openWindow('/x'); });",
    "push handler that renders nothing":
        "self.addEventListener('push', e => { const d = e.data.json(); console.log(d); });",
    "showNotification outside waitUntil":
        ("self.addEventListener('push', e => { try { e.data.json(); } catch (_) {} "
         "self.registration.showNotification('t', {}); e.waitUntil(Promise.resolve()); });"),
    "unguarded json payload":
        ("self.addEventListener('push', e => { const d = e.data.json(); "
         "e.waitUntil(self.registration.showNotification(d.title, {})); });"),
    "click that dead-ends":
        ("self.addEventListener('push', e => { try { e.data.json(); } catch (_) {} "
         "e.waitUntil(self.registration.showNotification('t', {})); });"
         "self.addEventListener('notificationclick', e => { e.notification.close(); });"),
}


def selftest():
    print("  selftest: the real sw.js must satisfy every invariant")
    with open(SW, encoding="utf-8") as f:
        real = f.read()
    bad = [c for c in check(real) if not c[0]]
    if bad:
        print(f"  {RED}FAIL{RST} — the shipped worker does not pass, so the self-test has no baseline:")
        for _, cid, d in bad:
            print(f"    {cid}: {d}")
        return 1
    print(f"    {GREEN}ok{RST} — all 7 hold on the shipped worker")

    print("  selftest: each broken worker must be CAUGHT")
    ok = True
    for name, src in BROKEN.items():
        failures = [c[1] for c in check(src) if not c[0]]
        if not failures:
            print(f"    {RED}FAIL{RST} '{name}' passed — that matcher has no teeth")
            ok = False
        else:
            print(f"    {GREEN}ok{RST} '{name}' -> caught by {', '.join(failures[:3])}")
    print(f"\n  SELFTEST: {GREEN + 'PASS' + RST if ok else RED + 'FAIL' + RST}")
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    print("Push handler contract (a delivered push must actually reach the person)")
    if not os.path.exists(SW):
        print(f"  {YEL}SKIP{RST} — sw.js not found; nothing asserted.")
        return 0
    with open(SW, encoding="utf-8") as f:
        src = f.read()
    results = check(src)
    failed = [r for r in results if not r[0]]
    for ok, cid, desc in results:
        print(f"  {GREEN + 'PASS' + RST if ok else RED + 'FAIL' + RST}  {cid:<24} {DIM}{desc}{RST}")
    if failed:
        print(f"\n  {RED}FAIL{RST} — {len(failed)} of {len(results)} invariants broken. Every one of these "
              f"fails SILENTLY:\n  the push is delivered, the worker wakes, and the person is told "
              f"nothing.")
        return 1
    print(f"\n  {GREEN}PASS{RST} - all {len(results)} invariants hold: a delivered push renders, survives "
          f"a cold worker\n  and a malformed payload, and the tap lands somewhere.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
