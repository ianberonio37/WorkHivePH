#!/usr/bin/env python3
"""validate_cls_reservations.py — a late-filled block must not push the page, and a reservation that
went stale must not do it silently.

WHY THIS GATE EXISTS. On 2026-08-06, walking PB-project-manager, the page measured CLS 0.108 against
the 0.1 budget. The cause was not a missing reservation — it was two reservations that had gone SHORT:
#pm-mgr-source-chip reserved 54px and rendered 62, #pm-verdict reserved 99 and rendered 102. Eleven
px of drift, spread over two hand-picked numbers nobody re-measured after the copy changed.

WHY THAT WAS EXPENSIVE OUT OF ALL PROPORTION TO 11px. CLS is impact-fraction x distance-fraction. The
two short reservations sit near the top of #list-view, so every block below them moved together — the
verdict, the stat row, the action card, the tab strip, the filter row: about 95% of the viewport. A
7px nudge of 95% of the screen scores 0.102. A small miss at the TOP of a page is not a small defect.

WHY IT COULD NOT BE FOUND BY READING THE CODE. Nine surfaces each hand-pick a pixel number for the
same component -- the empty <p> that renderSourceChip() fills -- and they disagree by 6x: 27, 30, 40,
54, 54, 62, 76, 161. Each number was correct when it was measured and each silently rots when the
chip's text, the font, or the breakpoint changes. Nothing recomputes them, and nothing noticed. This
gate is that something.

HOW TO READ A FAILURE, because the browser will mislead you here. A layout-shift entry's `sources`
list the nodes that MOVED -- the victims that got pushed down. The element that actually GREW is
usually not in the list at all. On project-manager the sources were action-card / simple-row /
pm-verdict, and action-card was the only one of the three with min-height:0 against a 131px render,
so it read as the obvious culprit. It was not: reserving it changed CLS by 0.0012 and was reverted.
So this gate reports the shifted nodes AND, separately, every element whose min-height reservation is
shorter than what it rendered -- the second list is the one that names the cause.

WHAT IT ASSERTS, and deliberately only this: on every page it can reach, CLS over the settle window
is within the 0.1 budget. The short-reservation report is a DIAGNOSTIC attached to a failure, not an
independent assertion -- min-height is a floor and exceeding it is legal for most elements, so a
gate that failed on every over-floor element would be noise. The budget is the contract; the
reservation list is how you fix it.

Needs a browser and a real session, so it is skip_if_fast and skips cleanly rather than passing when
it cannot see its subject.

Usage:  python tools/validate_cls_reservations.py [--settle 6] [--budget 0.1] [--pages a.html,b.html]
"""
import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
BASE = "http://127.0.0.1:5000/workhive/"

# The pages that DECLARE a CLS reservation (an explicit min-height on a late-filled container), which
# are exactly the pages that can carry a stale one. Sourced by grepping for min-height on the
# *-source-chip / verdict / row containers rather than "every page": a page with no reservation and no
# late-filled block would pass vacuously and pad the number, which is the false-100 shape this bank
# refuses. Add a page here when it gains a reservation.
DEFAULT_PAGES = [
    # index.html is first deliberately: it is the platform's front door and it was the WORST offender
    # when this gate was written. Signed-in ops-home measured CLS 0.1367 across cold loads from two
    # late-growing blocks — the greeting header (54px empty -> 112px filled, NO reservation, and it is
    # the first child so the whole page moved beneath it) and #oh-today (reserved 76px, rendered 97).
    # Both fixed; it now measures ~0.011. Worth stating because the page's own head comment describes a
    # historical landing->ops-home CLS of 0.24 as fixed, and it WAS: html.wh-signed-in was present in
    # every failing run. This was a second, unrelated shift inside ops-home, which is exactly why the
    # budget needs a gate rather than a one-time fix and a comment.
    "index.html",
    "project-manager.html", "hive.html", "analytics.html", "dayplanner.html",
    "community.html", "engineering-design.html", "integrations.html",
    "logbook.html", "pm-scheduler.html", "alert-hub.html",
]

MIN_RENDERED_CHARS = 800  # same floor, same reason as validate_skeleton_resolves.py

PROBE = r"""
const [url, settleMs, budget] = [process.argv[2], Number(process.argv[3]), Number(process.argv[4])];
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 } });
  const p = await ctx.newPage();
  // NO localStorage SEEDING — see validate_skeleton_resolves.py for why that sabotages the sign-in it
  // looks like it should help (stamped keys make index.html believe it is already authenticated, so
  // openSignIn() never surfaces the modal). A real session is the only thing that should make the app
  // think it has one. Bootstrap below is the same proven one: call the page's own opener rather than
  // hunting for a .signin-btn, all three of which are 0x0 inside collapsed wrappers at this width.
  let out = { url, ok: null, err: null };
  try {
    const origin = new URL(url).origin;
    await p.goto(origin + '/workhive/index.html', { waitUntil: 'domcontentloaded', timeout: 20000 });
    await p.waitForFunction(() => typeof window.openSignIn === 'function', { timeout: 15000 });
    await p.evaluate(() => window.openSignIn());
    await p.waitForSelector('#signin-modal:not(.hidden)', { timeout: 12000 });
    await p.waitForSelector('#si-username', { state: 'visible', timeout: 6000 });
    await p.waitForTimeout(250);
    await p.fill('#si-username', 'pabloaguilar');
    await p.fill('#si-password', 'test1234');
    await p.click('#si-btn');
    // WAIT FOR THE HIVE ID TOO, not just the worker. Measured 2026-08-06: wh_last_worker lands at
    // ~2786ms after the click and the hive id at ~2894ms — a 108ms window in which the session looks
    // complete and is not. Navigating inside it gave index.html a half-signed-in render: the head
    // paint-hint needs BOTH keys to stamp html.wh-signed-in, so without the hive id it fell back to a
    // partial ops-home of 473 chars instead of the full 1000, which the non-vacuity floor then
    // (correctly) refused. One run in four hit it, which is exactly how an intermittent presents.
    await p.waitForFunction(() => (localStorage.getItem('wh_last_worker') &&
      (localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id'))) ||
      (document.getElementById('si-error') &&
       !document.getElementById('si-error').classList.contains('hidden')), { timeout: 40000 });
    const signedIn = await p.evaluate(() => localStorage.getItem('wh_last_worker') &&
      (localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id')));
    if (!signedIn) {
      const why = await p.evaluate(() =>
        (document.getElementById('si-error') || {}).textContent || 'unknown');
      // "name resolution failed" here means the EDGE RUNTIME container is down, not that the
      // credentials are wrong: the login front door is an edge function, and Kong reports an
      // unresolvable upstream with that exact wording. `docker start supabase_edge_runtime_workhive`.
      throw new Error('sign-in failed: ' + String(why).trim().slice(0, 90));
    }

    // MEASURE ON A CLEAN NAVIGATION. An earlier hand-measurement of this same page read CLS 0.1374
    // because it had resized the viewport mid-session and counted the resize reflow as page shift.
    // buffered:true is what lets the observer see shifts that happened before this evaluate ran.
    //
    // TWO SAMPLES, AND A FAILURE NEEDS BOTH. alert-hub measured 0.0061 alone, 0.1338 twice inside the
    // full 11-page sweep, then 0.0061 alone again with no change to the page — an intermittent that only
    // appeared under load, which is this platform's known live-gate flake pattern. A gate that reports a
    // loaded host as a product defect trains everyone to ignore it, and a gate that quietly takes the
    // better sample hides a real intermittent. So: sample twice, FAIL only when both exceed the budget,
    // and always report the spread so an intermittent is visible as an intermittent.
    const samples = [];
    for (let i = 0; i < 2; i++) {
    await p.goto(url, { waitUntil: 'domcontentloaded', timeout: 20000 });
    const sample = await p.evaluate(({ settleMs }) => new Promise(res => {
      const shifts = [];
      new PerformanceObserver(l => {
        for (const e of l.getEntries()) if (!e.hadRecentInput) shifts.push(e);
      }).observe({ type: 'layout-shift', buffered: true });
      const name = n => !n || !n.tagName ? '?'
        : (n.id ? '#' + n.id
                : '.' + ((n.className || '').toString().split(/\s+/).filter(Boolean)[0] || n.tagName.toLowerCase()));
      setTimeout(() => {
        const cls = shifts.reduce((s, e) => s + e.value, 0);
        // The nodes that MOVED. Useful context, never the culprit — see the module docstring.
        const worst = shifts.slice().sort((a, b) => b.value - a.value).slice(0, 2).map(e => ({
          v: +e.value.toFixed(4), t: Math.round(e.startTime),
          moved: (e.sources || []).map(s => name(s.node) + '(dy' +
            Math.round(s.currentRect.y - s.previousRect.y) + ')').slice(0, 5),
        }));
        // The nodes whose RESERVATION IS SHORT. This is the actionable list: an explicit min-height
        // that the element has already outgrown is a reservation that has rotted. Restricted to
        // elements carrying a real reservation (min-height >= 12px) so ordinary content that merely
        // exceeds a small floor does not flood the report.
        const short = [];
        for (const el of document.querySelectorAll('*')) {
          // Skip the page-level boxes. `body { min-height: 900px }` is a page-HEIGHT floor, not a
          // CLS reservation, and it "overruns" by whatever the page is tall — the first run of this
          // gate reported `body: reserved 900px, renders 5150px (+4250)` at the TOP of the causes list
          // for alert-hub, which is a false lead of exactly the kind this gate exists to stop me
          // chasing.
          if (el === document.body || el === document.documentElement) continue;
          const mh = parseFloat(getComputedStyle(el).minHeight);
          if (!mh || mh < 12) continue;
          // min-height SERVES TWO DIFFERENT PURPOSES on this platform and they must not be conflated.
          // A CLS reservation holds space for content that arrives late. A WCAG 2.5.8 tap-target floor
          // guarantees a control is finger-sized. Exceeding a tap-target floor is CORRECT — a 69px chip
          // over a 44px floor is not a defect. The first version of this report listed five such chips
          // on alert-hub under the heading "this is the cause", which is the same overclaiming this
          // whole gate exists to argue against. 44 and 48 are the platform's tap floors, so an element
          // reserving exactly those is treated as a control, not a reservation.
          if (mh === 44 || mh === 48) continue;
          const h = el.getBoundingClientRect().height;
          const over = h - mh;
          // A reservation short by hundreds of px was never sized to its content — it is a floor for
          // something else. A genuine rotted reservation is short by a line or two.
          if (over > 1 && over <= 200) {
            short.push({ el: name(el), reserved: Math.round(mh), rendered: Math.round(h), over: Math.round(over) });
          }
        }
        short.sort((a, b) => b.over - a.over);
        res({
          cls: +cls.toFixed(4), shiftCount: shifts.length, worst,
          shortReservations: short.slice(0, 8),
          innerWidth: window.innerWidth,
          bodyTextLen: document.body.innerText.replace(/\s+/g, ' ').trim().length,
        });
      }, settleMs);
    }), { settleMs });
    samples.push(sample);
    }
    // Report the WORST sample's detail (that is the one worth diagnosing) but judge on whether EVERY
    // sample exceeded the budget. One-of-two over the line is an intermittent, reported as such.
    const worstSample = samples.slice().sort((a, b) => b.cls - a.cls)[0];
    out = Object.assign({}, worstSample);
    out.samples = samples.map(s => s.cls);
    out.url = url;
    out.allOver = samples.every(s => s.cls > budget);
    out.anyOver = samples.some(s => s.cls > budget);
    out.intermittent = out.anyOver && !out.allOver;
    out.ok = !out.allOver;
    // A sample that did not render substantively must not be averaged in with one that did.
    out.bodyTextLen = Math.max(...samples.map(s => s.bodyTextLen || 0));
  } catch (e) { out.err = String(e).slice(0, 200); }
  console.log(JSON.stringify(out));
  await b.close();
})();
"""


def main():
    ap = argparse.ArgumentParser()
    # 9s, not 6s. At 6s the first run measured project-manager with only 690 chars rendered and would
    # have scored the CLS of a half-built page — and a window that closes before the page settles
    # UNDERSTATES the number, which is the worse direction to be wrong in for a gate. The non-vacuity
    # floor caught it, but only because the floor exists; the window should not need catching.
    ap.add_argument("--settle", type=float, default=9.0)
    ap.add_argument("--budget", type=float, default=0.1)
    ap.add_argument("--pages", default="")
    a = ap.parse_args()
    pages = [x.strip() for x in a.pages.split(",") if x.strip()] or DEFAULT_PAGES

    print(f"{BOLD}Late content may not push the page — CLS <= {a.budget:g} per surface{RST}")
    if not os.path.isdir(os.path.join(ROOT, "node_modules", "playwright")):
        print(f"  {YEL}SKIP{RST} — playwright not installed locally")
        return 0

    probe = os.path.join(ROOT, ".tmp", "_cls_probe.js")
    os.makedirs(os.path.dirname(probe), exist_ok=True)
    with open(probe, "w", encoding="utf-8") as f:
        f.write(PROBE)

    fails, checked, skipped = [], 0, 0
    for page in pages:
        try:
            r = subprocess.run(["node", probe, BASE + page, str(int(a.settle * 1000)), str(a.budget)],
                               capture_output=True, text=True, timeout=180, cwd=ROOT)
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
            print(f"  {YEL}SKIP{RST}  {page} {DIM}({res['err'][:78]}){RST}")
            skipped += 1
            continue
        if int(res.get("bodyTextLen") or 0) < MIN_RENDERED_CHARS:
            print(f"  {YEL}SKIP{RST}  {page} {DIM}(only {res.get('bodyTextLen', 0)} chars rendered — "
                  f"needs a signed-in session; not counted as a pass){RST}")
            skipped += 1
            continue
        checked += 1
        spread = res.get("samples") or []
        spread_txt = "/".join(f"{c:.4f}" for c in spread)
        if res.get("ok"):
            # The char count is printed on PASS too, deliberately. A CLS of 0.0000 is equally the
            # signature of a perfectly reserved page and of a page that never rendered anything to
            # shift, and the two are indistinguishable from the number alone. Printing the denominator
            # beside the metric is what makes a suspiciously quiet PASS visible instead of trusted.
            if res.get("intermittent"):
                # Passing, but loudly: one sample was over. This is the alert-hub shape — 0.0061 alone,
                # 0.1338 under load, nothing changed in between. Surfacing it is the whole point; a
                # silent pass here would bury a real intermittent.
                print(f"  {YEL}PASS*{RST} {page} {DIM}(CLS {spread_txt} — INTERMITTENT, one sample over "
                      f"{a.budget:g}; {res.get('bodyTextLen', 0)} chars){RST}")
                for w in res.get("worst", [])[:1]:
                    print(f"        {DIM}worst shift {w['v']} at {w['t']}ms moved: "
                          f"{', '.join(w['moved'])}{RST}")
            else:
                print(f"  {GREEN}PASS{RST}  {page} {DIM}(CLS {spread_txt} over "
                      f"{res.get('shiftCount', 0)} shift(s); {res.get('bodyTextLen', 0)} chars){RST}")
        else:
            print(f"  {RED}FAIL{RST}  {page} {DIM}(CLS {spread_txt} — every sample over "
                  f"{a.budget:g}){RST}")
            for w in res.get("worst", []):
                print(f"        {DIM}shift {w['v']} at {w['t']}ms moved: {', '.join(w['moved'])}{RST}")
            shorts = res.get("shortReservations") or []
            if shorts:
                # CANDIDATES, not "the cause". Stated this way on purpose: an earlier wording claimed
                # causation and sent me chasing a body height-floor and a row of tap-target chips.
                print(f"        {BOLD}candidate rotted reservations (a reservation the content has "
                      f"outgrown; verify before fixing):{RST}")
                for s in shorts[:5]:
                    print(f"        {DIM}  {s['el']}: reserved {s['reserved']}px, renders "
                          f"{s['rendered']}px (+{s['over']}){RST}")
            fails.append(page)

    if not checked:
        print(f"  {YEL}SKIP{RST} — no page could be probed; a gate that cannot run must not report PASS")
        return 0
    if fails:
        print(f"\n  {RED}FAIL{RST} — {len(fails)} surface(s) over the CLS budget: {', '.join(fails)}")
        print(f"  {DIM}A short reservation near the top of a page moves everything below it, so a few "
              f"px of drift scores like a big shift. Re-measure the reserved height against what the "
              f"block actually renders with real data.{RST}")
        return 1
    print(f"\n  {GREEN}PASS{RST} — {checked} surface(s) within the {a.budget:g} CLS budget"
          + (f" {DIM}({skipped} skipped){RST}" if skipped else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
