#!/usr/bin/env python3
"""long-fetch-bounded — T146: a hang must end, not spin forever (2026-08-26).

A fetch to an AI or media edge function is the one a plant floor will hang: a
dead spot, a cold function, a slow uplink. Without a bound there is no failure —
just a control stuck in its working state, saying nothing, with no way back. That
is the eternal-skeleton shape wearing a spinner, and it is worse than an error,
because an error at least tells someone what to do next.

THE FINDING. voice-journal's transcribeBlob called fetch with NO timeout and NO
abort. A worker taps the mic in a noisy plant, speaks, and a stalled request
leaves the button in its rotating "processing" ring indefinitely. It is the most
hands-free surface the platform has and the one most likely to be used where the
signal is worst. It now goes through the platform's own fetchWithTimeout, which
already owns the AbortController, the transport-retry policy, and the
null-on-abort contract — the install-the-guard rule rather than a second
hand-rolled controller.

★45 SECONDS, NOT 10. A long spoken entry over a weak uplink is legitimately slow.
The bound exists to end a HANG, never to cut short a slow success — a timeout
tuned to a developer's patience turns working software into a lottery for the
people furthest from the server.

THE ASSERTION: every direct fetch to an AI or transcription edge function carries
a bound — fetchWithTimeout, an AbortController, or AbortSignal.timeout. Plain
`fetch(` to those endpoints fails this gate.

★NOT ALL FETCHES, deliberately. A quick REST read that hangs is already covered
by whQueryTimeout, and a gate demanding a timeout on every call in the codebase
would be noise. These are the calls that take seconds by nature and therefore
hide a hang inside a legitimate wait.

Usage: python tools/validate_long_fetch_bounded.py
"""
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# the slow-by-nature endpoints: AI generation and media transcription
SLOW = re.compile(r"functions/v1/(voice-transcribe|ai-gateway|[a-z\-]*(agent|orchestrator|summariz"
                  r"|assist|populator|extract|polish|narrat)[a-z\-]*)")
# ★A CONTROLLER IS NOT A CLOCK (2026-08-27, T40). This accepted a bare `AbortController` or a
# `signal:` as proof of a bound, and they are proof of a CANCEL BUTTON - somewhere for a person to
# press, not something that fires on its own. analytics-report had both and was still unbounded: the
# 22-page retry sweep graded it SILENT, sitting on "Compiling analytics across all 4 phases" forever
# under a read outage, because nothing was ever going to abort it if the reader simply waited. This
# gate passed that page every run.
#
# A real bound needs a TIMER: the shared wrapper, AbortSignal.timeout, a setTimeout that calls
# abort, or a Promise.race against a timed promise. The controller may still appear beside those -
# it is how the abort is delivered - but it cannot stand in for them.
BOUND = re.compile(r"fetchWithTimeout"
                   r"|AbortSignal\.timeout"
                   r"|setTimeout\((?:[^)]|\)(?!\s*;))*?abort"
                   r"|Promise\.race", re.S)


def main() -> int:
    unbounded, total = [], 0
    for f in sorted(glob.glob(str(ROOT / "*.html")) + glob.glob(str(ROOT / "*.js"))):
        name = Path(f).name
        lines = io.open(f, encoding="utf-8", errors="replace").read().split("\n")
        for i, line in enumerate(lines):
            if not SLOW.search(line):
                continue
            # only a direct browser fetch — a db.functions.invoke carries its own handling
            window = "\n".join(lines[max(0, i - 6): i + 8])
            if "fetch(" not in window and "fetchWithTimeout" not in window:
                continue
            total += 1
            if not BOUND.search(window):
                unbounded.append(f"{name}:{i + 1}  {line.strip()[:70]}")

    print(f"  slow-endpoint fetches found: {total}")
    if unbounded:
        print("FAIL long-fetch-bounded — a fetch to a slow-by-nature endpoint has no bound:")
        for u in unbounded[:8]:
            print("    - " + u)
        print("    Without one there is no failure, only a control stuck in its working state saying")
        print("    nothing. Use fetchWithTimeout (utils.js) - it owns the AbortController, the retry")
        print("    policy and the null-on-abort contract - and choose the bound for the SLOWEST")
        print("    legitimate success, not for a developer's patience.")
        return 1
    if total == 0:
        print("PASS long-fetch-bounded — no direct fetches to slow endpoints found. If that is a "
              "surprise, the endpoints were renamed; re-point this gate rather than trusting the zero.")
        return 0
    print(f"PASS long-fetch-bounded — all {total} fetch(es) to slow-by-nature endpoints are bounded, so "
          f"a hang ends in a message instead of a spinner.")
    return 0


def selftest() -> int:
    """The bound rule, pinned. Written after this gate passed a page that hung forever.

    Its BOUND pattern accepted a bare AbortController and a bare `signal:`, which are a CANCEL
    BUTTON - somewhere for a person to press - not a clock that fires on its own. analytics-report
    carried both and was graded SILENT by the 22-page retry sweep: under a read outage it sat on
    "Compiling analytics across all 4 phases" indefinitely, and this gate called it bounded on
    every run. The first case below is that exact source; it must be RED.
    """
    ok = True
    cases = [
        ("a controller and a signal with NO timer (the pre-fix analytics-report)",
         "_arAbort = new AbortController(); var res = await fetch(url, { signal: _arAbort.signal });", False),
        ("the shared wrapper", "await fetchWithTimeout(url, opts, 45000)", True),
        ("AbortSignal.timeout", "fetch(url, { signal: AbortSignal.timeout(9000) })", True),
        ("a controller PLUS a timer that aborts",
         "var t = setTimeout(function(){ c.abort(); }, 90000); await fetch(url, { signal: c.signal });", True),
        ("a race against a timed promise", "await Promise.race([fetch(url), timed])", True),
    ]
    for name, src, want in cases:
        got = bool(BOUND.search(src))
        good = got == want
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {name}: bounded={got}, want {want}")
    live = main()
    ok &= (live == 0)
    print(f"\n  SELFTEST: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else main())
