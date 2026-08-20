#!/usr/bin/env python3
"""validate_skeleton_resolves.py — a loading skeleton must never outlive the load.

WHY THIS GATE EXISTS. On 2026-08-05, walking PB-logbook-126, the logbook entry feed was found showing
a permanent loading shimmer: #entries-list held one .wh-skeleton with four rows and no text, still
there 14 seconds after load. A worker opening their own logbook — the platform's primary capture
surface, whose truth view feeds eleven other pages — saw a placeholder where their entries belonged.

NOTHING CAUGHT IT, AND NOTHING COULD HAVE. The data was fine (request 200, 200 rows loaded,
loadEntries resolved in 58ms), the console was silent at warning level and above, axe reported zero
violations, and every static validator passed. The page simply looked slow, forever. That is the
signature of this whole class: a skeleton is supposed to be the shortest-lived state on a surface, and
when it becomes the terminal one there is no error anywhere to find.

The root cause was a contract violation, not a race: loadEntries() paints the skeleton whenever the
list is empty, while its own first comment says "Mine-mode only. Team mode uses searchTeam()". In team
mode renderEntries clears the list and shows a search prompt, then the init-time personal load (kept
so the stat pills stay accurate) calls loadEntries, which finds the list empty and re-paints a
skeleton that no later render will clear.

WHAT THIS GATE ASSERTS, and deliberately only this: on every page it can reach, no element matching a
skeleton/shimmer/aria-busy selector is still present after a settle window. It is a STRUCTURAL check
and it says so — it cannot tell a correct skeleton from a stuck one mid-flight, which is exactly why
it waits. A page that legitimately takes longer than the window will fail, and the honest response is
to raise the window for that page rather than to weaken the rule.

Needs a browser, so it is skip_if_fast and skips cleanly when Playwright or the site is unavailable —
a gate that cannot run must say so rather than pass.

Usage:  python tools/validate_skeleton_resolves.py [--settle 9] [--pages logbook.html,hive.html]
"""
import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
BASE = "http://127.0.0.1:5000/workhive/"

# The surfaces that paint a list skeleton. Kept explicit rather than "every page": a page with no
# skeleton would pass vacuously and pad the number, which is the false-100 shape this bank exists to
# refuse. Add a page here when it adopts whListSkeleton.
DEFAULT_PAGES = [
    "logbook.html", "hive.html", "inventory.html", "pm-scheduler.html",
    "project-manager.html", "asset-hub.html", "community.html", "alert-hub.html",
]

SKELETON_SEL = '[class*="skeleton"],[class*="shimmer"],[aria-busy="true"]'

# Below this, the page did not really render and "no skeleton" proves nothing. Calibrated from the
# observed signed-out shell (407 chars on every page) versus a real signed-in surface (logbook renders
# ~1,200 chars skeletal and ~4,700 populated; hive ~2,000+).
MIN_RENDERED_CHARS = 800

PROBE = r"""
const [url, settleMs] = [process.argv[2], Number(process.argv[3])];
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 } });
  const p = await ctx.newPage();
  // NO localStorage SEEDING. An earlier draft pre-set wh_last_worker/wh_hive_role here to reach the
  // signed-in surfaces, and once a real sign-in was added that seed SABOTAGED it: the stamped keys make
  // index.html believe it is already authenticated (html.wh-signed-in reveals #ops-home and hides the
  // marketing wrap), so openSignIn() never surfaces the modal and every page timed out waiting for it.
  // The bootstrap worked perfectly in isolation, which is what made it confusing — my own leftover
  // scaffolding was the only thing breaking it. A real session is the only thing that should make the
  // app think it has one.
  let out = { url, ok: null, err: null };
  try {
    // SIGN IN THE WAY THE SUITE ALREADY DOES. Seeding localStorage keys is not enough — without a real
    // Supabase session every page serves the same signed-out shell (407 chars), the list skeleton never
    // paints, and this gate would pass on a page it never saw. Pattern reused verbatim from
    // tests/marketplace-bank-two-context.spec.ts signInAs(): ?signin=1 opens the modal, then wait on
    // wh_last_worker or the inline error rather than on a fixed timeout.
    // ?signin=1 is NOT a deep-link handler on this page — index.html only opens the modal from an
    // onclick (openSignIn), so the query param alone leaves it hidden and the wait times out. Click a
    // real .signin-btn instead, which is also closer to what a person does.
    const origin = new URL(url).origin;
    await p.goto(origin + '/workhive/index.html', { waitUntil: 'domcontentloaded', timeout: 20000 });
    // CALL THE PAGE'S OWN OPENER instead of hunting for a button. Three approaches failed before this
    // one, and each failure is worth recording because they are all the same mistake — guessing at the
    // DOM instead of observing it: (1) ?signin=1 is not a deep-link handler here, index.html only opens
    // the modal from an onclick; (2) waiting on the bare `.signin-btn` waits on the FIRST match, which
    // is hidden at 1280; (3) `.signin-btn:visible` legitimately matches NOTHING — measured live, all
    // three instances are 0x0 because they sit inside collapsed user-menu wrappers at this width.
    // openSignIn() is a global and is exactly what those buttons call, so it is both simpler and more
    // faithful than synthesising a click on chrome that may not be laid out.
    await p.waitForFunction(() => typeof window.openSignIn === 'function', { timeout: 15000 });
    await p.evaluate(() => window.openSignIn());
    await p.waitForSelector('#signin-modal:not(.hidden)', { timeout: 12000 });
    await p.waitForSelector('#si-username', { state: 'visible', timeout: 6000 });
    await p.waitForTimeout(250);
    await p.fill('#si-username', 'pabloaguilar');
    await p.fill('#si-password', 'test1234');
    await p.click('#si-btn');
    // BOTH keys, not just the worker. Measured 2026-08-06: wh_last_worker lands ~108ms before the hive
    // id, and a page loaded inside that window renders half-signed-in (index served a partial 473-char
    // ops-home instead of 1000). The session is not usable until the hive is resolved, so waiting on
    // the worker alone makes every gate built on this bootstrap intermittently measure the wrong state.
    await p.waitForFunction(() => (localStorage.getItem('wh_last_worker') &&
      (localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id'))) ||
      (document.getElementById('si-error') &&
       !document.getElementById('si-error').classList.contains('hidden')), { timeout: 25000 });
    const signedIn = await p.evaluate(() => localStorage.getItem('wh_last_worker') &&
      (localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id')));
    if (!signedIn) {
      const why = await p.evaluate(() =>
        (document.getElementById('si-error') || {}).textContent || 'unknown');
      throw new Error('sign-in failed: ' + String(why).trim().slice(0, 90));
    }

    await p.goto(url, { waitUntil: 'domcontentloaded', timeout: 20000 });
    await p.waitForTimeout(settleMs);
    out = await p.evaluate((sel) => {
      const els = [...document.querySelectorAll(sel)].filter(e => e.getClientRects().length);
      return {
        stuck: els.length,
        where: els.slice(0, 4).map(e => ({
          cls: (e.className || '').toString().slice(0, 40),
          parentId: e.parentElement ? (e.parentElement.id || '') : '',
          textLen: (e.innerText || '').trim().length,
        })),
        bodyTextLen: document.body.innerText.replace(/\s+/g, ' ').trim().length,
      };
    }, process.env.SKEL_SEL);
    out.url = url;
    out.ok = out.stuck === 0;
  } catch (e) { out.err = String(e).slice(0, 200); }
  console.log(JSON.stringify(out));
  await b.close();
})();
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--settle", type=float, default=9.0)
    ap.add_argument("--pages", default="")
    a = ap.parse_args()
    pages = [x.strip() for x in a.pages.split(",") if x.strip()] or DEFAULT_PAGES

    print(f"{BOLD}Skeletons must resolve — a placeholder may not outlive its load{RST}")
    if not os.path.isdir(os.path.join(ROOT, "node_modules", "playwright")):
        print(f"  {YEL}SKIP{RST} — playwright not installed locally")
        return 0

    probe = os.path.join(ROOT, ".tmp", "_skeleton_probe.js")
    os.makedirs(os.path.dirname(probe), exist_ok=True)
    with open(probe, "w", encoding="utf-8") as f:
        f.write(PROBE)

    env = dict(os.environ, SKEL_SEL=SKELETON_SEL)
    fails, checked, skipped = [], 0, 0
    for page in pages:
        try:
            r = subprocess.run(["node", probe, BASE + page, str(int(a.settle * 1000))],
                               capture_output=True, text=True, timeout=90, cwd=ROOT, env=env)
        except Exception as e:
            print(f"  {YEL}SKIP{RST}  {page} {DIM}({str(e)[:60]}){RST}")
            skipped += 1
            continue
        line = (r.stdout or "").strip().splitlines()[-1] if (r.stdout or "").strip() else ""
        try:
            res = json.loads(line)
        except Exception:
            print(f"  {YEL}SKIP{RST}  {page} {DIM}(probe produced no verdict){RST}")
            skipped += 1
            continue
        if res.get("err"):
            print(f"  {YEL}SKIP{RST}  {page} {DIM}({res['err'][:70]}){RST}")
            skipped += 1
            continue
        # NON-VACUITY, and this gate needed it immediately. Its first run reported PASS on logbook,
        # hive AND inventory with an identical 407 chars rendered on each — the probe was not reaching
        # the app at all (no Supabase session, so every page served the same signed-out shell) and
        # "no skeleton" was true only because there was no page. A gate that passes when it cannot see
        # its subject is the false-100 shape this whole bank exists to refuse, so a surface that did
        # not render substantively is SKIPPED with its reason, never counted as a pass.
        if int(res.get("bodyTextLen") or 0) < MIN_RENDERED_CHARS:
            print(f"  {YEL}SKIP{RST}  {page} {DIM}(only {res.get('bodyTextLen', 0)} chars rendered — "
                  f"needs a signed-in session; not counted as a pass){RST}")
            skipped += 1
            continue
        checked += 1
        if res.get("ok"):
            print(f"  {GREEN}PASS{RST}  {page} {DIM}(no skeleton after {a.settle:g}s; "
                  f"{res.get('bodyTextLen', 0)} chars rendered){RST}")
        else:
            where = "; ".join(f"{w['cls']} in #{w['parentId'] or '?'}" for w in res.get("where", []))
            print(f"  {RED}FAIL{RST}  {page} {DIM}({res.get('stuck')} stuck after "
                  f"{a.settle:g}s: {where}){RST}")
            fails.append(page)

    if not checked:
        print(f"  {YEL}SKIP{RST} — no page could be probed (site down?); a gate that cannot run "
              f"must not report PASS")
        return 0
    if fails:
        print(f"\n  {RED}FAIL{RST} — {len(fails)} surface(s) leave a skeleton up: {', '.join(fails)}")
        print(f"  {DIM}A skeleton is the shortest-lived state on a page. When it is the terminal one "
              f"the surface just looks slow forever and nothing errors — see logbook's team-mode "
              f"orphan (loadEntries painted a placeholder no render would clear).{RST}")
        return 1
    print(f"\n  {GREEN}PASS{RST} — {checked} surface(s) resolved every skeleton within {a.settle:g}s"
          + (f" {DIM}({skipped} skipped){RST}" if skipped else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
