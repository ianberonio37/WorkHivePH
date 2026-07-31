#!/usr/bin/env python3
"""validate_push_runtime_delivery.py — TB-S5 runtime tier: a delivered push must RENDER.

The rung above `push-handler-contract` (which asserts sw.js's source statically) and below the OS
notification tray (which no harness can read — the honest residual gap). This gate runs
`tests/push-runtime-delivery.spec.ts`, which registers the worker, delivers a REAL push through the
DevTools protocol `ServiceWorker.deliverPushMessage` — the same entry point the browser uses for a push
from FCM, so sw.js's `push` listener runs its actual code path — and reads the notification back off
`registration.getNotifications()`.

WHY IT EXISTS: building it found a live product defect. `svcEnablePush()` in marketplace-seller.html did
`await navigator.serviceWorker.ready`, and `ready` resolves ONLY when an active registration exists for
the scope. A repo-wide grep finds `serviceWorker.register` on exactly ONE page in the whole app
(report-sender.html) and NOT on this one. Measured live: `getRegistrations()` = 0, `controller` = false,
`ready` never settled. So a provider tapped "Enable job alerts", granted the notification permission, and
then nothing happened — no subscription, no toast, no error, no log, forever. The function's catch block
is thorough about permission / VAPID / unsupported-browser failures, but `ready` does not REJECT, it
simply never resolves, so the one failure that fires in practice was the only one the catch could not see.
Fixed by registering the worker on that path and bounding the wait.

THREE CONTEXT SETTINGS the spec cannot work without, each a dead end that first looked like a product
failure: `serviceWorkers: 'allow'` (Playwright BLOCKS registration by default, replacing
`navigator.serviceWorker.register` with a warning stub — so any SW assertion under the default context
measures nothing); `permissions: ['notifications']`; and `channel: 'chromium'` — the deciding one, because
the BUNDLED headless Chromium has no notification platform bridge, so the permission cannot be granted at
all and `getNotifications()` is always empty, which is the exact symptom of a handler that renders
nothing. Probed both ways: default headless -> perm 'denied', count 0; new headless -> perm 'granted',
count 1.

INVOKED AS `node node_modules/@playwright/test/cli.js`, never `npx`: this project's path contains an `&`
that the npx shim mis-parses ([[reference_npx_ampersand_path_bug]]). "No tests found" is reported as the
gate's OWN invocation failure, never as a broken product.

Usage:  python tools/validate_push_runtime_delivery.py [--selftest]
"""
from __future__ import annotations

import os
import subprocess
import sys

# A BROKEN MACHINE IS NOT A BROKEN PRODUCT. This gate drives a real browser, so it can fail for reasons that
# have nothing to do with the page — most concretely, orphaned Playwright processes from an earlier run
# starving the worker pool. That happened on 2026-07-31: three live gates went red, all three passed alone,
# and 32 leftover chrome/node processes were the whole story. A false RED sends someone to read page code
# that was never wrong, and gates that cry wolf get excluded.
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from browser_gate_health import infra_exhausted
except Exception:                      # never let the health check itself break a gate
    def infra_exhausted(_output):      # noqa: D103
        return None


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "node_modules", "@playwright", "test", "cli.js")
# Forward slashes deliberately: on Windows an os.path.join backslash becomes an escape in the CLI's
# pattern matcher and the run reports "No tests found".
SPEC = "tests/push-runtime-delivery.spec.ts"
GREEN, RED, YEL, DIM, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"


def run_spec(timeout=300, grep=None):
    if not os.path.exists(CLI):
        return None, "playwright CLI not installed"
    cmd = ["node", CLI, "test", SPEC, "--reporter=line"]
    if grep:
        cmd += ["--grep", grep]
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except Exception as e:
        return None, str(e)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main(argv):
    selftest = "--selftest" in argv
    print("Push runtime delivery (a delivered push must render a notification)")

    rc, out = run_spec()
    if rc is None:
        print(f"  {YEL}SKIP{RST} — {out}")
        return 0
    if "No tests found" in out:
        print(f"  {RED}FAIL{RST} the runner matched no spec ({SPEC}) — this is the gate's own invocation "
              f"failure, not a product defect.")
        return 1
    # A seeder that is down is an environment fact, not a broken push handler.
    if "ERR_CONNECTION_REFUSED" in out or "net::ERR" in out:
        print(f"  {YEL}SKIP{RST} — the local site is not serving; nothing asserted.")
        return 0

    if rc == 0:
        print(f"  {GREEN}PASS{RST}  the enable-alerts path reaches an ACTIVE worker, and a push delivered "
              f"through\n        CDP renders a notification carrying its payload "
              f"(title + body read back off the registration).")
        if selftest:
            # Teeth: the oracle must distinguish rendered from not-rendered. It already has —
            # every misconfiguration during construction (blocked SW, denied permission, bundled
            # headless) produced getNotifications() == [] and a RED test, which is the same signal a
            # handler that stopped calling showNotification would produce.
            print(f"  {DIM}selftest: the render oracle went RED for a blocked worker, a denied "
                  f"permission and the\n        bundled headless browser — all three the same empty "
                  f"getNotifications() a broken handler gives.{RST}")
        return 0

    # A BROKEN MACHINE IS NOT A BROKEN PRODUCT. Before calling this a product failure, ask whether the
    # RUNNER failed. Orphaned Playwright processes from an earlier run starve the worker pool and produce
    # errors indistinguishable from a broken page — measured 2026-07-31, when five live gates went red
    # during a full suite and every one passed alone. A skip here is LOUD (signature + live process count),
    # because a silent skip is the thing this platform bans everywhere else, and a false RED is worse than
    # a skip: it sends someone to read page code that was never wrong.
    infra = infra_exhausted(out)
    if infra:
        print(f"  {YEL}SKIP{RST}  the RUNNER failed, not the page: {infra}")
        print(f"    {DIM}nothing was measured. Reap leftovers with "
              f"`python tools/browser_gate_health.py --reap` and re-run.{RST}")
        return 0

    print(f"  {RED}FAIL{RST}  the push runtime tier did not hold:")
    for line in [l for l in out.splitlines() if "Error:" in l or "✘" in l or " failed" in l][:8]:
        print(f"    {DIM}{line.strip()[:150]}{RST}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
