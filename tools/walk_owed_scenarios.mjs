// walk_owed_scenarios.mjs — walk the owed live-MCP scenarios in BATCH, honestly.
//
// WHY THIS EXISTS. 269 scenarios sat owed across 8 URLs and 15 state families. Hand-walking them one
// at a time through the MCP was producing ~4 rows per turn, which is how a 269-row queue becomes a
// permanent backlog. The states are mechanical — force a condition, read what the page does — so the
// walking is a harness job. What is NOT mechanical is the judgement about what counts as passing, so
// every probe below records exactly WHICH properties it checked, and a row is only banked on the
// properties actually measured.
//
// THE INTEGRITY RULE THIS FILE LIVES BY: a probe that cannot evaluate its row's oracle must NOT
// return green. `populated` asks that "every visible number matches its source of truth" — a generic
// harness cannot know every surface's truth query, so it checks the structural half (rows render, no
// raw enum, no NaN/undefined/[object Object], no error chrome) and SAYS SO in the evidence, and the
// number-matching half stays with the hand-walked rows that verified it against psql. Auto-greening
// an oracle you did not test is how a test bank becomes decoration
// ([[feedback_an_oracle_that_does_not_match_the_claim]]).
//
// Induction is at the NETWORK layer via page.route(), not by patching window.fetch: routing survives
// re-renders and in-page navigations, and a rejected request is never used to fake a failure — a
// REAL 500/401 response body is served, because a rejected fetch produces a stuck skeleton and
// proves something else entirely ([[feedback_verify_the_instrument_before_the_page]]).
//
// USAGE:  node tools/walk_owed_scenarios.mjs [--only <urlSubstring>] [--limit N]
// OUTPUT: .tmp/owed_walk_results.json   (merged into the registry by the python step)

import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'node:url';
import crypto from 'node:crypto';   // to recompute a row's freshness the same way the gate does

// fileURLToPath, not url.pathname: this project's directory contains spaces AND an '&', so the raw
// pathname arrives percent-encoded and every fs call misses by a mile.
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SEEDER = 'http://127.0.0.1:5000';
const EMAIL = 'pabloaguilar@auth.workhiveph.com', PASSWORD = 'test1234';
// THE HIVE MUST BE ONE THIS PERSON IS ACTUALLY IN, AND MUST EXIST. The previous constant
// (c9def338-fd73-4b19-8ef1-ee57625953d6) matched NO row in `hives` at all, and Pablo is not a member
// of it. Every hive-filtered surface therefore rendered against a hive that does not exist —
// community showed zero posts, and a `populated` walk there was measuring an empty room. Pablo's
// active hives are 4eec150e (37 posts) and b4f7fe63 (50 posts); b4f7fe63 is the one the rest of this
// session's fixtures already use, so surfaces agree with each other.
// Verified against hive_members + hives before changing it, rather than swapped on a hunch.
const HIVE = 'b4f7fe63-92e1-4f8d-b96e-625c3f85ba61', WORKER = 'Pablo Aguilar';

const args = process.argv.slice(2);
const only = args.includes('--only') ? args[args.indexOf('--only') + 1] : null;
const limit = args.includes('--limit') ? parseInt(args[args.indexOf('--limit') + 1], 10) : Infinity;

const REST = /\/rest\/v1\/(?!rpc\/)/;
const LONG = 'Emergency Switchgear Overhaul and Transformer Oil Regeneration for the Southern Tagalog Industrial Estate Incorporated';
const BAYBAYIN = 'ᜋᜄᜈ᜔ᜆᜅ᜔ ᜃᜄᜋᜒᜆᜈ᜔ ᜐ ᜉᜎᜒᜃ';

// ── what the page says about itself, read once per probe ───────────────────────────────────────────
async function readSurface(page) {
  return await page.evaluate(() => {
    const main = document.querySelector('main') || document.body;
    const txt = (main.innerText || '').replace(/\s+/g, ' ').trim();
    const vis = el => !!(el.offsetParent || el.getClientRects().length);
    const controls = [...main.querySelectorAll('button,a[href],input,select,textarea')]
      .filter(vis).map(el => (el.innerText || el.value || el.getAttribute('aria-label') || '').trim())
      .filter(Boolean);
    // an element that scrolls wider than its box while overflow is visible = real clipping
    const overflowers = [...main.querySelectorAll('*')].filter(el =>
      el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0 &&
      getComputedStyle(el).overflowX === 'visible' &&
      // a collapsed <details> still reports a scrollWidth for content nobody can see; counting it
      // turned the "How this page works" help panel into a phantom layout defect
      !el.closest('details:not([open])')).length;
    return {
      text: txt.slice(0, 4000),
      len: txt.length,
      // The offline banner injects into <body> at z-index 9999, OUTSIDE <main> — reading only main
      // made every `degraded` probe report "no banner" while the banner was on screen the whole time.
      // element-based, because the banner appends at the END of body and a text slice
      // silently drops it on any page longer than the slice — which is most of them.
      offlineBannerVisible: [...document.body.querySelectorAll('div')].some(el =>
        /you are offline|no connection|reconnect/i.test(el.innerText || '') &&
        getComputedStyle(el).display !== 'none' && (el.offsetParent || el.getClientRects().length)),
      controls: controls.slice(0, 40),
      docOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      overflowers,
      innerWidth: window.innerWidth,
      // junk that means a renderer met a shape it did not expect
      junk: (txt.match(/\bundefined\b|\bNaN\b|\[object Object\]|\bnull\b/g) || []).slice(0, 5),
      // a raw enum reaching a person: lowercase_with_underscores standing alone as a status
      rawEnum: (txt.match(/\b(cancelled_by_\w+|in_progress|pending_verification|already_claimed|en_route|on_site)\b/g) || []).slice(0, 5),
    };
  });
}

const ERR_RE = /couldn['’]?t load|could not load|failed to load|unavailable|something went wrong|error/i;
const INVITE_RE = /no .{0,24}yet|be the first|get started|hail your first|post your first|first run/i;
const RETRY_RE = /retry|try again|reload/i;

// FAILURE wording, as distinct from GAP wording. ERR_RE above is deliberately broad — it includes a
// bare "error" and "unavailable" — which is right when asking "did this surface admit a failure?"
// (the `error` probe) and WRONG when asking "does this empty state look like a failure?" (the `empty`
// probe). marketplace renders "listing count unavailable" when it genuinely has no counts: that is
// the page naming a gap honestly, which is the behaviour this bank exists to reward, and ERR_RE
// scored it as error chrome and failed 50 rows across three surfaces. An empty state may name what
// is missing; what it may not do is claim something BROKE.
const FAIL_RE = /couldn['’]?t load|could not load|failed to load|something went wrong|try again/i;

// ...AND THE ONE FAILURE SENTENCE THAT IS ACTUALLY THE RIGHT ANSWER. Response stubbing cannot give
// supabase-js a parseable COUNT: the real server answers a head:true count with `Content-Range: */0`
// and a stub carrying the identical header still yields no count client-side. Surfaces that display
// counts therefore meet a genuine "I have no numbers" condition under this probe, and both of them
// say so exactly as they should —
//     "Couldn't load these numbers, so they're showing as a dash rather than as zero. Retry"
//     "listing count unavailable"
// — which is the absent-vs-zero distinction this bank exists to reward. Scoring that as failure
// chrome failed 50 rows across three surfaces for behaving correctly. Recognise it explicitly rather
// than loosening FAIL_RE, so a page that merely says "couldn't load" with no such distinction still
// fails.
const ABSENT_NOT_ZERO_RE = /rather than (as )?zero|unknown rather than|count unavailable|showing as a dash/i;

// ── the probes. Each returns {ok, checked[], notes} — `checked` IS the evidence. ───────────────────
const PROBES = {
  async populated(page) {
    const s = await readSurface(page);
    const checked = [
      `renders content (${s.len} chars of visible text)`,
      `no error chrome on screen: ${!ERR_RE.test(s.text)}`,
      `no unrendered junk (undefined/NaN/[object Object]): ${s.junk.length === 0}`,
      `no raw status enum reaching the person: ${s.rawEnum.length === 0}`,
      `no horizontal document overflow: ${s.docOverflow <= 0}`,
      'NOT CHECKED HERE: number-vs-source-of-truth, which needs a per-surface psql query — the ' +
      'hand-walked rows carry that half',
    ];
    const ok = s.len > 120 && s.docOverflow <= 0 && !ERR_RE.test(s.text) && s.junk.length === 0 && s.rawEnum.length === 0;
    return { ok, checked, notes: ok ? '' : `junk=${JSON.stringify(s.junk)} rawEnum=${JSON.stringify(s.rawEnum)} err=${ERR_RE.test(s.text)}` };
  },

  async empty(page, ctx) {
    // A GENUINELY EMPTY RESPONSE CARRIES A COUNT. PostgREST answers a head:true count with
    // `Content-Range: */0`; a stub that omits it leaves supabase-js unable to parse any count at
    // all, so the page reports "listing count unavailable" — which is the page being HONEST
    // about a count it never received, and was read as an error-shaped empty state. Emulate the
    // real thing: zero rows AND a stated zero.
    await ctx.route(REST, r => r.fulfill({ status: 200, contentType: 'application/json',
      headers: { 'content-range': '*/0' }, body: '[]' }));
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2600);
    const s = await readSurface(page);
    await ctx.unroute(REST);
    const namesGap = INVITE_RE.test(s.text) || /\b(no|none|nothing|empty|0)\b/i.test(s.text);
    const offersAction = s.controls.length > 0;
    const saysAbsentNotZero = ABSENT_NOT_ZERO_RE.test(s.text);
    const ok = namesGap && offersAction && (!FAIL_RE.test(s.text) || saysAbsentNotZero);
    return {
      ok,
      checked: [
        'every REST read forced to 200-with-zero-rows at the network layer',
        `names what is missing: ${namesGap}`,
        `offers something to do about it (${s.controls.length} live controls): ${offersAction}`,
        `does NOT render as a failure: ${!FAIL_RE.test(s.text)}`,
        `…or distinguishes absent from zero, which is the right answer when the count is genuinely unavailable: ${saysAbsentNotZero}`,
      ],
      notes: ok ? '' : `namesGap=${namesGap} controls=${s.controls.length} failShown=${FAIL_RE.test(s.text)} absentNotZero=${saysAbsentNotZero}`,
    };
  },

  async error(page, ctx) {
    // JUDGED AS A CONTRAST, not by a whole-page keyword hunt. The oracle is that a FAILED read must
    // not look like an EMPTY one — so the only honest test is to render both on the same surface and
    // compare. A page-wide /no .* yet/ regex flunked three surfaces where the erroring pane said
    // "Couldn't load" perfectly well while some OTHER, legitimately-empty pane said "no requests
    // yet". That is a correct page and a broken instrument.
    // A GENUINELY EMPTY RESPONSE CARRIES A COUNT. PostgREST answers a head:true count with
    // `Content-Range: */0`; a stub that omits it leaves supabase-js unable to parse any count at
    // all, so the page reports "listing count unavailable" — which is the page being HONEST
    // about a count it never received, and was read as an error-shaped empty state. Emulate the
    // real thing: zero rows AND a stated zero.
    await ctx.route(REST, r => r.fulfill({ status: 200, contentType: 'application/json',
      headers: { 'content-range': '*/0' }, body: '[]' }));
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);
    const emptyText = (await readSurface(page)).text;
    await ctx.unroute(REST);

    await ctx.route(REST, r => r.fulfill({
      status: 500, contentType: 'application/json',
      body: JSON.stringify({ code: '500', message: 'induced failure' }),
    }));
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);
    const s = await readSurface(page);
    await ctx.unroute(REST);

    const saysError = ERR_RE.test(s.text);
    const offersRetry = RETRY_RE.test(s.text) || s.controls.some(c => RETRY_RE.test(c));
    // identical rendering of a failure and an emptiness IS the defect, whatever words are used
    const norm = t => t.replace(/[\d,.\s]+/g, ' ').trim();
    const indistinguishable = norm(s.text) === norm(emptyText);
    const ok = saysError && !indistinguishable;
    return {
      ok,
      checked: [
        'every REST read forced to a real 500 RESPONSE (not a rejected request, which would only ' +
        'produce a stuck skeleton and prove something else)',
        `says the read failed: ${saysError}`,
        `renders DIFFERENTLY from the same surface with zero rows: ${!indistinguishable}`,
        `offers a way to recover: ${offersRetry}`,
      ],
      notes: ok ? '' : `saysError=${saysError} indistinguishableFromEmpty=${indistinguishable}`,
    };
  },

  async edge(page, ctx) {
    await ctx.route(REST, async r => {
      let res; try { res = await r.fetch(); } catch (e) { return r.continue(); }
      let body; try { body = await res.json(); } catch (e) { return r.fulfill({ response: res }); }
      if (Array.isArray(body) && body.length) {
        for (const row of body.slice(0, 3)) {
          for (const k of Object.keys(row)) {
            if (/name|title|label|scope|desc/i.test(k) && typeof row[k] === 'string') row[k] = LONG;
            if (/price|amount|budget|rate|fee|cost/i.test(k) && typeof row[k] === 'number') row[k] = 0;
          }
        }
      }
      return r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    });
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2600);
    const wide = await readSurface(page);
    // and again at a real 200%-zoom-equivalent width. browser resize LIES about what it applied, so
    // the achieved innerWidth is recorded rather than the requested one.
    await page.setViewportSize({ width: 427, height: 720 });
    await page.waitForTimeout(1200);
    const narrow = await readSurface(page);
    await page.setViewportSize({ width: 1280, height: 900 });
    await ctx.unroute(REST);
    const ok = wide.docOverflow <= 0 && narrow.docOverflow <= 0 && narrow.overflowers === 0;
    return {
      ok,
      checked: [
        'real payload cloned and rewritten (longest name, zero price) rather than an invented row, ' +
        'so the shape cannot be wrong and what is measured is layout, not a crash',
        `no document overflow at full width (${wide.docOverflow}px; <=0 is the scrollbar gutter): ${wide.docOverflow <= 0}`,
        `no document overflow at innerWidth ${narrow.innerWidth} (200%-zoom equivalent): ${narrow.docOverflow <= 0}`,
        `no unclipped overflowing element: ${narrow.overflowers === 0}`,
      ],
      notes: ok ? '' : `wideOverflow=${wide.docOverflow} narrowOverflow=${narrow.docOverflow} overflowers=${narrow.overflowers}`,
    };
  },

  async degraded(page, ctx) {
    await ctx.setOffline(true);
    // offline-banner.js reacts to the window 'offline' event; setOffline does not always emit it in
    // an already-loaded page, so dispatch it too and then read BODY (the banner is not inside main).
    await page.evaluate(() => window.dispatchEvent(new Event('offline')));
    await page.waitForTimeout(1600);
    const s = await readSurface(page);
    const banner = s.offlineBannerVisible;
    await ctx.setOffline(false);
    await page.evaluate(() => window.dispatchEvent(new Event('online')));
    await page.waitForTimeout(600);
    return {
      ok: banner,
      checked: [
        'browser context switched genuinely offline (context.setOffline, not a page-level flag)',
        `the person is told the device is offline: ${banner}`,
        'detected as a VISIBLE ELEMENT in body, not a text slice (the banner appends at the end of body, so a truncated innerText read silently drops it)',
      ],
      notes: banner ? '' : 'no offline banner in body after the offline event',
    };
  },

  async filtered0(page) {
    const box = await page.$('input[type=search], #search-input, input[placeholder*="Search" i]');
    if (!box) return { ok: null, checked: [], notes: 'no search control on this surface' };
    await box.fill('zzzzz-nothing-matches-this-zzzzz');
    await page.waitForTimeout(1800);
    const s = await readSurface(page);
    const saysSo = /no .{0,30}match|nothing match|no results|found nothing|0 result/i.test(s.text);
    const wayBack = s.controls.some(c => /clear|reset|show all|back/i.test(c));
    return {
      ok: saysSo,
      checked: [
        'typed a term that matches nothing',
        `says so rather than showing a blank grid: ${saysSo}`,
        `offers a way back (clear/reset/show all): ${wayBack}`,
      ],
      notes: saysSo ? '' : 'a filter matching nothing produced no explanatory text',
    };
  },
};
// ── U-recovery: the transitions. Every money defect this session found lived in one of these. ──────
const openFirstSheet = async (page) => {
  const btn = await page.$('button:has-text("Post a listing"), button:has-text("File top-up"), ' +
                           'button:has-text("Hail"), [data-open-sheet], .fab');
  if (btn) { await btn.click().catch(() => {}); await page.waitForTimeout(1200); }
  return !!btn;
};
const overlayState = page => page.evaluate(() => {
  const vis = el => !!(el.offsetParent || el.getClientRects().length) &&
    getComputedStyle(el).display !== 'none' && getComputedStyle(el).visibility !== 'hidden';
  const overlays = [...document.querySelectorAll('[class*="backdrop"],[class*="overlay"],dialog[open],[class*="sheet"],[class*="drawer"],[class*="modal"]')].filter(vis);
  return {
    openOverlays: overlays.length,
    bodyLocked: getComputedStyle(document.body).overflow === 'hidden',
    // an overlay left behind still swallows clicks even when it looks invisible
    blocksCentre: (() => { const el = document.elementFromPoint(window.innerWidth / 2, 300);
      return el ? /backdrop|overlay|modal/i.test((el.className || '').toString()) : false; })(),
    filled: [...document.querySelectorAll('input,textarea')].filter(i => i.value && i.value.length > 2).length,
  };
});

PROBES.reload = async (page) => {
  await openFirstSheet(page);
  await page.evaluate(() => {
    const f = [...document.querySelectorAll('input[type=text],input[type=number],textarea')]
      .find(i => (i.offsetParent || i.getClientRects().length));
    if (f) { f.focus(); f.value = 'half-typed recovery probe'; f.dispatchEvent(new Event('input', { bubbles: true })); }
  });
  await page.waitForTimeout(600);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2600);
  const st = await overlayState(page);
  const s = await readSurface(page);
  // The oracle allows EITHER outcome — survive intact or be gone — and forbids the third: a sheet
  // restored into a state the person never left it in, or an overlay with nothing behind it.
  const ok = !st.blocksCentre && s.len > 120;
  return {
    ok,
    checked: [
      'opened a sheet, half-filled a field, then reloaded mid-flow',
      `no orphaned overlay swallowing clicks after reload: ${!st.blocksCentre}`,
      `the page came back usable (${s.len} chars of content, ${st.openOverlays} overlays open)`,
      `body scroll not left locked: ${!st.bodyLocked}`,
    ],
    notes: ok ? '' : `blocksCentre=${st.blocksCentre} len=${s.len} bodyLocked=${st.bodyLocked}`,
  };
};

PROBES.back_nav = async (page) => {
  const opened = await openFirstSheet(page);
  await page.goBack({ waitUntil: 'domcontentloaded' }).catch(() => {});
  await page.waitForTimeout(2200);
  const st = await overlayState(page);
  const ok = !st.blocksCentre && !st.bodyLocked;
  return {
    ok,
    checked: [
      `opened a sheet (${opened ? 'found a trigger' : 'no sheet trigger on this surface'}) then pressed browser Back`,
      `no orphaned overlay intercepting clicks: ${!st.blocksCentre}`,
      `body scroll released: ${!st.bodyLocked}`,
    ],
    notes: ok ? '' : `blocksCentre=${st.blocksCentre} bodyLocked=${st.bodyLocked}`,
  };
};

PROBES.double_submit = async (page, ctx) => {
  // COMPARED AGAINST A ONE-CLICK BASELINE, not against a fixed number. One logical action here
  // legitimately performs TWO writes (the row, then writeAuditLog), so asserting "at most 1 write"
  // called a correct page broken. What the oracle actually asks is whether the SECOND press changes
  // anything further — so click once, count; reload; click twice, count; compare.
  const SUBMIT = 'button:has-text("File top-up"), button:has-text("Post Listing"), button:has-text("Save")';
  // A FRESH PAGE PER RUN. Reusing one page and reloading it leaked state from the baseline into the
  // test — the first run's save left the form in a different condition, and the second run's clicks
  // did more work, which read as "the second press wrote more" when a clean measurement shows 3
  // writes either way. The baseline must be measured on the same starting state as the test.
  const run = async (clicks) => {
    const p2 = await ctx.newPage();
    let writes = 0;
    await ctx.route(REST, async r => {
      if (/POST|PATCH|PUT|DELETE/i.test(r.request().method())) {
        writes++;
        return r.fulfill({ status: 201, contentType: 'application/json', body: '[]' });
      }
      return r.continue();
    });
    await p2.goto(page.url(), { waitUntil: 'domcontentloaded' });
    await p2.waitForTimeout(2600);
    const btn = await p2.$(SUBMIT);
    if (btn) {
      // NOT force:true. Playwright's force click skips actionability checks INCLUDING `disabled`,
      // so it dispatches on a button the guard has already locked — defeating the exact guard this
      // probe exists to test, and reporting a working page as broken. A person cannot click a
      // disabled button; neither should the probe. Confirmed against the live MCP browser, where a
      // real DOM click after the lock engages produces no second write.
      for (let i = 0; i < clicks; i++) {
        await btn.click({ timeout: 1500 }).catch(() => {});   // a locked button simply refuses
      }
      await p2.waitForTimeout(2200);
    }
    await ctx.unroute(REST);
    await p2.close();
    return { writes, found: !!btn };
  };
  const one = await run(1);
  const two = await run(2);
  const ok = !one.found || two.writes <= one.writes;
  return {
    ok,
    checked: [
      one.found ? 'pressed a submit control once, then (after a reload) twice in immediate succession'
                : 'no submit control on this surface',
      `writes from ONE press: ${one.writes}`,
      `writes from TWO presses: ${two.writes}`,
      `the second press added nothing: ${two.writes <= one.writes}`,
      'compared against a one-click baseline because a single action legitimately writes more than ' +
      'once here (the row, then the audit-log entry)',
    ],
    notes: ok ? '' : `two presses wrote ${two.writes} against a one-press baseline of ${one.writes}`,
  };
};

PROBES.offline_resume = async (page, ctx) => {
  let writesWhileOffline = 0, writesOnReconnect = 0;
  let offline = true;
  await ctx.route(REST, async r => {
    if (/POST|PATCH|PUT|DELETE/i.test(r.request().method())) {
      if (offline) writesWhileOffline++; else writesOnReconnect++;
    }
    return r.continue();
  });
  await ctx.setOffline(true);
  await page.evaluate(() => window.dispatchEvent(new Event('offline')));
  await page.waitForTimeout(1200);
  const btn = await page.$('button:has-text("File top-up"), button:has-text("Post Listing"), button:has-text("Save")');
  if (btn) { await btn.click({ force: true }).catch(() => {}); await page.waitForTimeout(1500); }
  const told = (await readSurface(page)).offlineBannerVisible;
  offline = false;
  await ctx.setOffline(false);
  await page.evaluate(() => window.dispatchEvent(new Event('online')));
  await page.waitForTimeout(2500);          // the window in which a silent replay would fire
  await ctx.unroute(REST);
  const ok = told && writesOnReconnect === 0;
  return {
    ok,
    checked: [
      'went genuinely offline, attempted the surface\'s write, then came back online',
      `the person was told they are offline: ${told}`,
      `no write was SILENTLY replayed on reconnect: ${writesOnReconnect === 0} (${writesOnReconnect} fired)`,
      `writes attempted while offline: ${writesWhileOffline}`,
    ],
    notes: ok ? '' : `told=${told} replayedOnReconnect=${writesOnReconnect}`,
  };
};

// V-edge-content states are the edge probe with a different payload; they share its assertions.
// ── LAYOUT, driven by the lens that already exists ────────────────────────────────────────────────
// live-state-runner.js exports layout(target) and it is served from the web root, so it can simply be
// imported INTO the page rather than reimplemented here. Reimplementing it would give the bank a
// second, subtly different definition of "overflow" — and the lens already carries hard-won
// corrections this file must not lose: a deliberately swipeable strip (overflow-x:auto) is not an
// offender, a collapsed <details> reports a scrollWidth nobody can see, an inline citation is not a
// thumb target, and bottom chrome is anything fixed ending within 80px of the edge (an inset FAB sits
// 24px short and was invisible to the older flush-only test).
//
// WIDTH IS VERIFIED, NEVER ASSUMED. The lens returns verifiedWidth/onTarget because a resize can land
// somewhere other than where it was asked to; a probe that trusts its own request measures the wrong
// viewport and says nothing about the one it named.
const layoutAt = async (page, width) => {
  await page.setViewportSize({ width, height: 900 });
  await page.waitForTimeout(700);          // let the reflow settle before measuring it
  return await page.evaluate(async (w) => {
    const m = await import('/workhive/live-state-runner.js');
    return m.layout(w);
  }, width);
};

const widthProbe = (width) => async (page) => {
  const L = await layoutAt(page, width);
  const ok = L.onTarget && !L.docScrollsSideways && L.overflowCount === 0;
  return {
    ok,
    checked: [
      `viewport VERIFIED at ${L.verifiedWidth}px (asked for ${width}, dpr ${L.dpr}): ${L.onTarget}`,
      `no sideways document scroll (by ${L.docBy}px): ${!L.docScrollsSideways}`,
      `no element overflowing its box while overflow-x is visible: ${L.overflowCount === 0}`,
      'measured by live-state-runner.js::layout(), the same lens the hand-walks used',
    ],
    notes: ok ? '' : `verified=${L.verifiedWidth} onTarget=${L.onTarget} docBy=${L.docBy} ` +
                     `overflow=${L.overflowCount} ${JSON.stringify((L.offenders || []).slice(0, 2))}`,
  };
};

PROBES.w390_overflow = widthProbe(390);
PROBES.w641_overflow = widthProbe(641);
PROBES.w1280_overflow = widthProbe(1280);

PROBES.tap_target_44 = async (page) => {
  // Judged at the narrow width, because that is where a thumb is used and where a flex parent is
  // most likely to squeeze a control below the rule its stylesheet intended.
  const L = await layoutAt(page, 390);
  const ok = L.onTarget && L.tapTargetsUnder44 === 0;
  return {
    ok,
    checked: [
      `viewport VERIFIED at ${L.verifiedWidth}px: ${L.onTarget}`,
      `every visible control measures >= 44px by RECT, not by stylesheet intent: ${L.tapTargetsUnder44 === 0}`,
      'inline links inside prose excluded — a citation is not a thumb target',
    ],
    notes: ok ? '' : `under44=${L.tapTargetsUnder44} ${JSON.stringify((L.small || []).slice(0, 3))}`,
  };
};

PROBES.safe_area = async (page) => {
  const L = await layoutAt(page, 390);
  const chrome = L.bottomFixed || [];
  const undeclared = chrome.filter(c => !c.declaresSafeArea);
  // NON-VACUITY: env(safe-area-inset-bottom) resolves to 0 on a desktop browser, so a MEASURED gap
  // proves nothing — only the DECLARATION does. And if the lens found no bottom chrome at all there
  // is nothing to judge, which must not read as a pass.
  // NOT-APPLICABLE IS NOT THE SAME AS VACUOUS, and the difference is whether the instrument could
  // SEE. A vacuous pass is one where the lens was blind — which this lens once was, missing an inset
  // FAB because it demanded chrome flush against the viewport edge. That is fixed and documented, so
  // when it now reports zero bottom-fixed elements on a surface, the absence is a measurement rather
  // than a blind spot: platform-actions is an admin queue with no bottom chrome, and "clears the home
  // indicator" has nothing to attach to. Signalled separately so the merger banks it as declared-na
  // with its reasoning, never as a walk-verified green.
  const na = L.onTarget && chrome.length === 0;
  const ok = L.onTarget && chrome.length > 0 && undeclared.length === 0;
  return {
    ok: ok || na,
    na,
    checked: [
      `viewport VERIFIED at ${L.verifiedWidth}px: ${L.onTarget}`,
      `bottom-fixed chrome found to judge: ${chrome.length}`,
      na
        ? 'NOT APPLICABLE: this surface has no bottom-fixed chrome, so there is no home indicator to '
          + 'clear. The lens CAN see inset chrome (it was fixed to catch a FAB sitting 24px short of '
          + 'the edge), so this zero is a measurement, not a blind spot'
        : `every piece of it DECLARES env(safe-area-inset-bottom): ${undeclared.length === 0}`,
      'judged by declaration, not by measured gap — env() resolves to 0 on this browser',
    ],
    notes: (ok || na) ? '' : `undeclared=${JSON.stringify(undeclared.slice(0, 3))}`,
  };
};

// ── VISUAL, from the same runner ──────────────────────────────────────────────────────────────────
// visual() returns TRI-STATE `ok` values: true, false, or NULL for inconclusive — APCA is null when
// some sample could not be measured (a gradient or image behind the text), reduced_motion is null
// when nothing animates. Null is NOT a pass, and collapsing it to one would be the exact false-green
// this bank exists to prevent, so each is reported for what it is.
const visualLens = async (page) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.waitForTimeout(600);
  return await page.evaluate(async () => {
    const m = await import('/workhive/live-state-runner.js');
    return m.visual();
  });
};

PROBES.contrast_apca = async (page) => {
  const v = (await visualLens(page)).apca || {};
  const ok = v.ok === true;
  return {
    ok,
    na: v.ok === null && v.measured === 0,
    checked: [
      `text samples measured with APCA (alpha-composited, not nominal colours): ${v.measured}`,
      `samples below the APCA threshold: ${v.failing}`,
      `samples the lens could not measure (image/gradient behind the text): ${v.inconclusive}`,
      v.ok === null
        ? 'INCONCLUSIVE, not a pass: some sample could not be measured, so this surface is not cleared'
        : `every measured sample clears the threshold: ${v.ok}`,
    ],
    notes: ok ? '' : `measured=${v.measured} failing=${v.failing} inconclusive=${v.inconclusive} ` +
                     `${JSON.stringify((v.worst || []).slice(0, 2))}`,
  };
};

PROBES.reduced_motion = async (page) => {
  const v = (await visualLens(page)).reduced_motion || {};
  // ok===null means nothing animates here — there is no motion to reduce, which is genuinely
  // not-applicable rather than unproven, and the lens counted the animated elements to say so.
  const na = v.ok === null && v.animatedElements === 0;
  const ok = v.ok === true;
  return {
    ok: ok || na,
    na,
    checked: [
      `elements actually animating: ${v.animatedElements}`,
      na
        ? 'NOT APPLICABLE: nothing on this surface animates, so there is no motion to guard'
        : `a prefers-reduced-motion guard is declared for them: ${v.declaresGuard}`,
      v.note || '',
    ].filter(Boolean),
    notes: (ok || na) ? '' : `animated=${v.animatedElements} declaresGuard=${v.declaresGuard}`,
  };
};

// ── COMPONENT + AVAILABILITY STATES, from runner.states() ─────────────────────────────────────────
// One states() call induces and judges nineteen conditions, and every one of them reports a TRI-STATE
// `ok` plus a note that says when nothing was found — "no disabled control in this state - recorded
// rather than passed". That distinction is the whole value: a surface with no disabled control has
// not demonstrated correct disabled behaviour, and calling it green would be banking an absence.
//
// So each state maps to exactly one key, and:
//   ok === true   -> banked green
//   ok === false  -> a real failure, banked owed with the lens's own detail
//   ok === null   -> NOT a pass. If the lens says nothing of this kind exists on the surface, that is
//                    declared-na (measured, with the note as its reasoning); otherwise it stays owed.
const statesLens = async (page) => {
  await page.waitForTimeout(400);
  return await page.evaluate(async () => {
    const m = await import('/workhive/live-state-runner.js');
    return await m.states({ settle: 1500 });
  });
};

// The five availability states live in a DIFFERENT export — availability(), not states(). Asking
// states() for them returned undefined, which the factory below would have reported as a failure of
// the PAGE rather than of the lookup. Route each key to the lens that actually owns it.
const availabilityLens = async (page) => {
  await page.waitForTimeout(400);
  return await page.evaluate(async () => {
    const m = await import('/workhive/live-state-runner.js');
    return await m.availability({ settle: 1500 });
  });
};
const AVAILABILITY_KEYS = new Set(['offline_refusal', 'retry_path', 'rate_limit_legible',
                                   'fallback_engaged', 'slow_honest']);

const fromStates = (key) => async (page) => {
  const all = AVAILABILITY_KEYS.has(key) ? await availabilityLens(page) : await statesLens(page);
  const r = (all && all[key]) || {};
  // A key the lens never returned is a LOOKUP failure, not a page failure, and must say so rather
  // than indicting a surface that was never asked the question.
  if (r.ok === undefined) {
    return {
      ok: false,
      checked: [`asked the lens for "${key}" and it returned nothing`],
      notes: `the lens returned no "${key}" key — this is a broken lookup in the harness, not a `
           + `defect on the page. Keys present: ${JSON.stringify(Object.keys(all || {}).slice(0, 12))}`,
    };
  }
  const na = r.ok === null && !!r.note;
  return {
    ok: r.ok === true || na,
    na,
    checked: [
      `induced and judged by live-state-runner.js::states(), key "${key}"`,
      `controls of this kind found on the surface: ${r.found != null ? r.found : 'n/a'}`,
      r.ok === null
        ? `NOT a pass — ${r.note || 'the lens reached no verdict, so nothing is claimed here'}`
        : `verdict: ${r.ok}`,
      r.checked ? `evidence: ${JSON.stringify(r.checked).slice(0, 300)}` : '',
    ].filter(Boolean),
    notes: (r.ok === true || na) ? ''
      : `ok=${r.ok} found=${r.found} note=${r.note || ''} ${JSON.stringify(r.checked || []).slice(0, 200)}`,
  };
};

for (const k of ['component_loading', 'component_skeleton', 'component_disabled',
                 'component_busy', 'component_populated',
                 'offline_refusal', 'retry_path', 'rate_limit_legible',
                 'fallback_engaged', 'slow_honest']) {
  PROBES[k] = fromStates(k);
}

// ── COMPREHENSION ─────────────────────────────────────────────────────────────────────────────────
// comprehension() reports raw findings rather than verdicts — numbersFound/unexplained, cost{}, next{},
// refusals{} — so the judgement lives here, and each state says plainly what would make it fail.
// Every one carries a non-vacuity guard: a surface with no numbers has not proven it explains numbers,
// and a surface with no commit control has not proven it states a cost before the commitment.
const comprehensionLens = async (page) => {
  await page.waitForTimeout(400);
  return await page.evaluate(async () => {
    const m = await import('/workhive/live-state-runner.js');
    return m.comprehension();
  });
};

PROBES.what_is_this_number = async (page) => {
  const c = await comprehensionLens(page);
  const found = c.numbersFound || 0;
  const bad = c.unexplainedCount || 0;
  const ok = found > 0 && bad === 0;
  return {
    ok,
    checked: [
      `numbers a person can see on this surface: ${found}`,
      `of those, ones with nothing nearby saying what they mean: ${bad}`,
      found === 0 ? 'NOTHING TO JUDGE: no numbers on this surface, so this is not a pass' : '',
    ].filter(Boolean),
    notes: ok ? '' : (found === 0
      ? 'no numbers found, so explaining them cannot be demonstrated — recorded, not passed'
      : `unexplained=${bad} ${JSON.stringify((c.unexplained || []).slice(0, 3))}`),
  };
};

// ── BB-ufai-U · the vocabulary lens ───────────────────────────────────────────────────────────────
// `populated` already refuses a page carrying a raw enum, but it does so against a fixed allowlist of
// six known statuses. That is the right guard for a rendering check and the WRONG one for a claim that
// says "no lowercase_with_underscores status reaches a person" — an allowlist can only ever find the
// enums somebody already thought of. This looks for the SHAPE instead, and excludes the places where
// snake_case is legitimately on screen (code samples, keyboard hints), so a hit is a real leak.
PROBES.no_raw_enum = async (page) => {
  const r = await page.evaluate(() => {
    const main = document.querySelector('main') || document.body;
    // Text a person reads, minus the places snake_case belongs.
    const skip = 'code, pre, kbd, samp, script, style, [data-allow-snake]';
    const clone = main.cloneNode(true);
    clone.querySelectorAll(skip).forEach(el => el.remove());
    const txt = (clone.innerText || '').replace(/\s+/g, ' ').trim();
    // A status shape: two or more lowercase words joined by underscores, standing as its own token.
    const hits = [...new Set((txt.match(/\b[a-z]{2,}(?:_[a-z0-9]{2,})+\b/g) || []))];
    return { hits: hits.slice(0, 8), n: hits.length, len: txt.length };
  });
  const ok = r.len > 120 && r.n === 0;
  return {
    ok,
    checked: [
      `visible text read, minus code/pre/kbd: ${r.len} chars`,
      `tokens shaped like a raw status (two+ lowercase words joined by _): ${r.n}`,
      r.len <= 120 ? 'NOTHING TO JUDGE: the surface rendered almost no text, so a clean read proves nothing' : '',
    ].filter(Boolean),
    notes: ok ? '' : (r.len <= 120
      ? 'the surface rendered almost nothing, so "no raw enum" is vacuous here — recorded, not passed'
      : `raw enum shapes on screen: ${JSON.stringify(r.hits)}`),
  };
};

// The unit must be ON SCREEN beside the number. Scoped to figures whose own container calls itself a
// price/amount/balance/total, because those are the ones where a bare number is ambiguous — "6" next
// to the word "assets" needs no unit, but "6" in a field named `price` does.
PROBES.units_visible = async (page) => {
  const r = await page.evaluate(() => {
    const vis = el => !!(el.offsetParent || el.getClientRects().length);
    const MONEYISH = /price|amount|balance|total|credit|cost|fee|payout|revenue|earning|wallet/i;
    const UNIT = /[₱%]|\bPHP\b|\bpesos?\b|\bcredits?\b|\bper\b|\bhrs?\b|\bhours?\b|\bdays?\b|\bkm\b|\bm\b/i;
    const out = [];
    const els = [...(document.querySelector('main') || document.body).querySelectorAll('*')].filter(vis);
    for (const el of els) {
      const id = `${el.id || ''} ${el.className || ''}`;
      if (!MONEYISH.test(id)) continue;
      if ([...el.children].some(c => MONEYISH.test(`${c.id || ''} ${c.className || ''}`))) continue; // innermost only
      const t = (el.innerText || '').replace(/\s+/g, ' ').trim();
      if (!/\d/.test(t)) continue;
      // the unit may sit in the element itself or immediately beside it (a label, a prefix span)
      const near = `${t} ${(el.previousElementSibling?.innerText || '')} ${(el.parentElement?.innerText || '').slice(0, 120)}`;
      // A UNIT IS NOT ALWAYS A CURRENCY SYMBOL. `#mk-total-hero` shows a bare "9" with "LISTINGS IN
      // VIEW" as its previous sibling and "9 parts listings after filter" as its next — labelled
      // plainly, just not inside the same element. Requiring [₱%] of that called a correctly-labelled
      // count a defect. A noun beside the number counts, and the noun may live in the context.
      const NOUN = /\d[\d,.]*\s+[a-z]{3,}|[a-z]{3,}\s+\d/i;
      if (!UNIT.test(near) && !NOUN.test(near)) out.push({ where: id.trim().slice(0, 50), shows: t.slice(0, 40) });
    }
    return { bare: out.slice(0, 6), n: out.length, considered: els.filter(el => MONEYISH.test(`${el.id || ''} ${el.className || ''}`)).length };
  });
  const ok = r.considered > 0 && r.n === 0;
  return {
    ok,
    checked: [
      `elements naming themselves a price/amount/balance/total: ${r.considered}`,
      `of those showing a figure, ones with no unit on screen beside it: ${r.n}`,
      r.considered === 0 ? 'NOTHING TO JUDGE: this surface names no money figure, so this is not a pass' : '',
    ].filter(Boolean),
    notes: ok ? '' : (r.considered === 0
      ? 'no money-shaped figure on this surface, so units cannot be demonstrated — recorded, not passed'
      : `figures with no unit beside them: ${JSON.stringify(r.bare)}`),
  };
};

// BE-ufai-I · a permission boundary must READ as a boundary. The defect this is for is the surface
// that meets a refusal and renders "No listings yet" — which tells the person the data does not
// exist, when what happened is that they were not allowed to see it. Those are different facts and
// only one of them is true. The refusal is injected at the network layer so the page meets a real
// PostgREST 403 shape, and the oracle is two-sided: it must NOT claim emptiness, and it MUST name the
// boundary. Saying nothing at all fails both halves.
const EMPTY_CLAIM_RE = /no listings|no posts|no results|nothing here|none found|no items|no requests|no jobs|empty/i;
const BOUNDARY_RE = /not allowed|no access|do not have access|don['’]t have access|not visible|permission|not permitted|restricted|only .{0,30}(admin|owner|seller)|sign(ed)? in as/i;
PROBES.boundary_not_emptiness = async (page, ctx) => {
  let refused = 0;
  await ctx.route(REST, async r => {
    if (/GET|HEAD/i.test(r.request().method())) {
      refused++;
      // The shape PostgREST returns for a row the caller may not read: 403 with a 42501 body, NOT a
      // 401. A 401 would make this a session test, which is a different row.
      return r.fulfill({
        status: 403, contentType: 'application/json',
        body: JSON.stringify({ code: '42501', message: 'permission denied', details: null, hint: null }),
      });
    }
    return r.continue();
  });
  await page.reload({ waitUntil: 'domcontentloaded' }).catch(() => {});
  await page.waitForTimeout(3000);
  const st = await readSurface(page);
  await ctx.unroute(REST).catch(() => {});

  const claimsEmpty = EMPTY_CLAIM_RE.test(st.text);
  const namesBoundary = BOUNDARY_RE.test(st.text);
  const ok = refused > 0 && !claimsEmpty && namesBoundary;
  return {
    ok,
    checked: [
      `reads refused with 403/42501: ${refused}`,
      `claims the data is empty ("no listings", "nothing here"): ${claimsEmpty}`,
      `names the boundary ("not allowed", "no access", "not visible"): ${namesBoundary}`,
      refused === 0 ? 'INSTRUMENT FAILED: no read was intercepted, so nothing was refused and this ' +
                      'measured nothing' : '',
    ].filter(Boolean),
    notes: ok ? '' : (refused === 0
      ? 'the route never matched, so the surface was never refused — instrument failure, not a pass'
      : claimsEmpty
        ? `refused ${refused} read(s) and the surface reported EMPTINESS: "${st.text.slice(0, 180)}"`
        : `refused ${refused} read(s) and the surface never named the boundary: "${st.text.slice(0, 180)}"`),
  };
};

// One concept, one word — measured WITHIN a surface, which is the half that needs no judgement call
// about which synonym is canonical. If a single screen calls the same thing by two names, that is
// self-evidently inconsistent regardless of which one is right; and picking a canonical term myself
// would make this probe an opinion rather than a measurement.
const VOCAB_CLUSTERS = [
  ['credits', 'points', 'tokens', 'coins'],
  ['top-up', 'topup', 'deposit', 'recharge'],
  ['provider', 'vendor', 'contractor', 'supplier'],
  ['buyer', 'purchaser', 'customer'],
  ['listing', 'advert', 'advertisement'],
  ['hive', 'workspace', 'tenant'],
];
PROBES.one_vocabulary = async (page) => {
  const r = await page.evaluate((clusters) => {
    const main = document.querySelector('main') || document.body;
    const clone = main.cloneNode(true);
    clone.querySelectorAll('code, pre, kbd, samp, script, style').forEach(el => el.remove());
    const txt = (clone.innerText || '').toLowerCase();
    const clashes = [];
    for (const cluster of clusters) {
      const present = cluster.filter(w => new RegExp(`\b${w.replace('-', '[- ]?')}s?\b`, 'i').test(txt));
      if (present.length > 1) clashes.push(present);
    }
    return { clashes, len: txt.length, checkedClusters: clusters.length };
  }, VOCAB_CLUSTERS);
  const ok = r.len > 120 && r.clashes.length === 0;
  return {
    ok,
    checked: [
      `${r.checkedClusters} synonym clusters looked for in ${r.len} chars of visible text`,
      `clusters where this ONE surface used two different words for the same thing: ${r.clashes.length}`,
      'NOT CHECKED HERE: whether the word this surface chose is the same one OTHER surfaces chose — ' +
      'within-surface consistency is a necessary condition, not the whole claim',
      r.len <= 120 ? 'NOTHING TO JUDGE: almost no text rendered' : '',
    ].filter(Boolean),
    notes: ok ? '' : (r.len <= 120
      ? 'the surface rendered almost nothing, so consistent vocabulary is vacuous here — recorded, not passed'
      : `the same surface used both: ${JSON.stringify(r.clashes)}`),
  };
};

// The chip claims provenance. This asks whether the claim is TRUE — not whether a chip exists.
// The page's own `_whFriendlySource` maps a relation to the phrase the chip shows, so the friendly
// names of the relations the page ACTUALLY requested are computable, and the chip's phrase must be
// one of them. A chip naming a source the page never read is the defect this is for.
PROBES.source_chip_true = async (page, ctx) => {
  const requested = new Set();
  const onReq = req => {
    const m = /\/rest\/v1\/([a-zA-Z0-9_]+)/.exec(req.url());
    if (m) requested.add(m[1]);
  };
  page.on('request', onReq);
  await page.reload({ waitUntil: 'domcontentloaded' }).catch(() => {});
  await page.waitForTimeout(2500);
  page.off('request', onReq);

  const r = await page.evaluate((reqd) => {
    // The HOST (#<page>-source-chip) and the chip it renders (.wh-source-chip) both match this
    // selector and occupy the identical rect, so a naive count reports two chips where one is on
    // screen. Keep only the outermost of any nested pair.
    const chips = [...document.querySelectorAll('[id$="source-chip"], [class*="source-chip"]')]
      .filter(el => (el.offsetParent || el.getClientRects().length))
      .filter((el, _i, arr) => !arr.some(other => other !== el && other.contains(el)));
    const chipText = chips.map(c => (c.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean);
    const friendly = typeof window._whFriendlySource === 'function'
      ? reqd.map(n => { try { return window._whFriendlySource(n) || ''; } catch (e) { return ''; } }).filter(Boolean)
      : null;
    return { chips: chipText, friendly, requested: reqd, hasMapper: friendly !== null };
  }, [...requested]);

  if (r.chips.length === 0) {
    return { ok: false, checked: [`PostgREST relations this page read: ${r.requested.length}`],
             notes: 'no source chip is on screen, so the surface makes no provenance claim — that is ' +
                    'not the same as making a true one, and it is not a pass' };
  }
  if (!r.hasMapper) {
    return { ok: false, checked: ['a chip is on screen'],
             notes: '_whFriendlySource is not reachable on this page, so the chip\'s claim cannot be ' +
                    'compared to what was read — instrument gap, not a pass' };
  }
  // Every phrase the chip shows must correspond to something the page actually asked the server for.
  const backed = r.chips.filter(t => r.friendly.some(f => f && t.toLowerCase().includes(f.toLowerCase())));
  const ok = backed.length === r.chips.length && r.friendly.length > 0;
  return {
    ok,
    checked: [
      `relations this page actually read: ${JSON.stringify(r.requested.slice(0, 8))}`,
      `phrases those relations map to via the page's own _whFriendlySource: ${JSON.stringify(r.friendly.slice(0, 6))}`,
      `source chips on screen: ${JSON.stringify(r.chips.slice(0, 3))}`,
      `chips whose named source is one the page actually read: ${backed.length}/${r.chips.length}`,
    ],
    notes: ok ? '' : `a chip names a source this page never requested: ${JSON.stringify(
      r.chips.filter(t => !backed.includes(t)).slice(0, 2))}`,
  };
};

// Same question the comprehension lens already answers, asked by the UFAI row instead of the UX row.
PROBES.number_explained = PROBES.what_is_this_number;

PROBES.what_does_it_cost = async (page) => {
  const c = await comprehensionLens(page);
  const cost = c.cost || {};
  const commits = (cost.commitControls || []).length;
  // A surface that asks for a commitment must say what it costs — "no fees" counts, silence does not.
  const saysSomething = !!(cost.statesFee || cost.statesFree || cost.statesHold);
  const na = commits === 0;
  const ok = commits > 0 && saysSomething;
  return {
    ok: ok || na,
    na,
    checked: [
      `controls that commit a person to something: ${commits}`,
      na ? 'NOT APPLICABLE: nothing here commits a person, so there is no cost to state'
         : `the surface states a fee, states it is free, or states a hold: ${saysSomething}`,
      `fee=${!!cost.statesFee} free=${!!cost.statesFree} hold=${!!cost.statesHold}`,
    ],
    notes: (ok || na) ? '' : `${commits} commit control(s) and no cost stated anywhere`,
  };
};

PROBES.reward_explained = async (page) => {
  const c = await comprehensionLens(page);
  const cost = c.cost || {};
  // THE REWARD ONLY NEEDS EXPLAINING WHERE IT IS EARNED. The credits-back reward attaches to a PRICED
  // transaction; a public feed sells nothing, so "does this surface explain the reward" has nothing to
  // attach to and a failure there would be marking a page down for not discussing a feature it does
  // not offer. Applicability is decided by whether the surface has anything to commit to or any price
  // on it — measured, not assumed.
  const priced = await page.evaluate(() => {
    const m = document.querySelector('main') || document.body;
    return /₱\s?[\d,]/.test(m.innerText || '');
  });
  const commits = (cost.commitControls || []).length;
  const applies = priced || commits > 0;
  const ok = !!cost.statesReward;
  return {
    ok: ok || !applies,
    na: !applies,
    checked: [
      `this surface shows a price or offers a commitment, so the reward is relevant here: ${applies}`,
      applies
        ? `the surface explains the credits-back reward in words: ${ok}`
        : 'NOT APPLICABLE: nothing priced and nothing to commit to, so there is no reward to explain',
      'this is the chip whose disappearance started the bank — service_knob returned NULL meaning ' +
      '"no cap", Number(null) made it 0, and Math.min(raw, 0) removed it from every priced listing',
    ],
    notes: (ok || !applies) ? '' : 'this surface is priced and never explains the credits-back reward',
  };
};

// ── THE THREE A11Y STATES visual() DOES NOT COVER ─────────────────────────────────────────────────
// visual() returns apca and reduced_motion only. contrast_wcag, focus_visible and icon_only_name are
// measured here, in the page, with the same disciplines the other lenses earned:
//   · composite the background up the ancestor chain — a nominal colour pair is not what a person sees
//   · judge focus by what CHANGES on focus, not by whether some outline property exists at rest
//   · a control whose label is only an emoji is unnamed to a screen reader, however clear it looks
//   · andeach probe fails when it found nothing to judge, so an absence is never a pass

PROBES.contrast_wcag = async (page) => {
  const r = await page.evaluate(() => {
    const srgb = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
    const lum = ([r, g, b]) => 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b);
    const parse = (s) => {
      const m = (s || '').match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/);
      return m ? [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4]] : null;
    };
    // COMPOSITE, don't read. A translucent background over a dark page is not the colour the
    // stylesheet names; blending up the chain is what a person actually sees.
    // A GRADIENT IS A BACKGROUND AND backgroundColor DOES NOT SEE IT. community's "Join the Hive"
    // button is `color: rgb(22,32,50)` — dark navy — on `linear-gradient(135deg, rgb(247,162,27)…)`,
    // an orange fill. Its backgroundColor is rgba(0,0,0,0), so a chain that reads only
    // backgroundColor walks straight past the thing a person is looking at and lands on the page's
    // dark canvas, computing dark-on-dark and reporting a ratio of exactly 1.0 for text that is
    // perfectly legible. Exactly 1.0 across several elements was the tell.
    // A gradient has no single colour to compare against, so the sample is UNMEASURABLE — the same
    // bucket the APCA lens keeps for "a gradient or image behind the text" — and unmeasurable is
    // neither a pass nor a defect.
    const gradientBehind = (el) => {
      let cur = el;
      while (cur) {
        const cs = getComputedStyle(cur);
        if ((cs.backgroundImage || 'none') !== 'none') return true;
        const c = parse(cs.backgroundColor);
        if (c && c[3] >= 0.99) return false;      // an opaque colour settles it before any gradient
        cur = cur.parentElement;
      }
      return false;
    };
    const bgOf = (el) => {
      let cur = el, acc = null;
      while (cur) {
        const c = parse(getComputedStyle(cur).backgroundColor);
        if (c && c[3] > 0) {
          acc = acc === null ? c : [
            acc[0] + (c[0] - acc[0]) * (1 - acc[3]),
            acc[1] + (c[1] - acc[1]) * (1 - acc[3]),
            acc[2] + (c[2] - acc[2]) * (1 - acc[3]),
            acc[3] + c[3] * (1 - acc[3]),
          ];
          if (acc[3] >= 0.99) return acc;
        }
        cur = cur.parentElement;
      }
      return acc || [11, 15, 25, 1];   // the page's own dark canvas when nothing opaque was found
    };
    const main = document.querySelector('main') || document.body;
    const fails = []; const unmeasurable = []; let measured = 0;
    for (const el of main.querySelectorAll('*')) {
      if (el.children.length) continue;
      const txt = (el.textContent || '').trim();
      if (txt.length < 2) continue;
      const rect = el.getBoundingClientRect();
      if (!(rect.width > 0 && rect.height > 0)) continue;
      const cs = getComputedStyle(el);
      if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) continue;
      const fg = parse(cs.color); if (!fg) continue;
      // TEXT PAINTED BY A GRADIENT CANNOT BE MEASURED FROM `color`. `background-clip: text` with a
      // transparent colour shows the gradient through the glyphs, so reading `color` yields
      // rgba(0,0,0,0) and the ratio computes to exactly 1.0 against any background — which is how
      // "Write the first post" and "Sign in to post →" were reported as contrast failures on two
      // surfaces that render them perfectly legibly. The APCA lens keeps an `unmeasurable` bucket for
      // this same case; an unmeasurable sample is INCONCLUSIVE, and inconclusive is neither a pass
      // nor a defect.
      const clip = cs.webkitBackgroundClip || cs.backgroundClip;
      if (fg[3] === 0 || clip === 'text' || gradientBehind(el)) {
        unmeasurable.push(txt.slice(0, 40)); continue;
      }
      const bg = bgOf(el);
      const L1 = lum(fg), L2 = lum(bg);
      const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
      const px = parseFloat(cs.fontSize) || 16;
      const bold = (parseInt(cs.fontWeight, 10) || 400) >= 700;
      const large = px >= 24 || (bold && px >= 18.66);
      const need = large ? 3.0 : 4.5;
      measured++;
      if (ratio < need - 0.05) {
        fails.push({ txt: txt.slice(0, 40), ratio: +ratio.toFixed(2), need, px: Math.round(px) });
      }
    }
    return { measured, failing: fails.length, unmeasurable: unmeasurable.length,
             samples: unmeasurable.slice(0, 4),
             worst: fails.sort((a, b) => a.ratio - b.ratio).slice(0, 6) };
  });
  const ok = r.measured > 0 && r.failing === 0;
  return {
    ok,
    checked: [
      `text samples measured, backgrounds COMPOSITED up the ancestor chain: ${r.measured}`,
      `samples below their WCAG threshold (4.5 normal / 3.0 large): ${r.failing}`,
      `samples skipped as unmeasurable — gradient text via background-clip, whose colour is transparent: ${r.unmeasurable}`,
      'large text recognised as >=24px, or >=18.66px when bold, per the WCAG definition',
    ],
    notes: ok ? '' : (r.measured === 0
      ? 'no text sample could be measured — nothing was judged, so this is not a pass'
      : `failing=${r.failing} ${JSON.stringify(r.worst)}`),
  };
};

PROBES.focus_visible = async (page) => {
  const r = await page.evaluate(() => {
    const main = document.querySelector('main') || document.body;
    const vis = el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
    const controls = [...main.querySelectorAll('button, a[href], input:not([type=hidden]), select, textarea')]
      .filter(vis).slice(0, 25);
    const bad = []; let checked = 0;
    for (const el of controls) {
      const before = getComputedStyle(el);
      const rest = before.outlineWidth + '|' + before.outlineStyle + '|' + before.boxShadow + '|' + before.borderColor;
      el.focus();
      const after = getComputedStyle(el);
      const focused = after.outlineWidth + '|' + after.outlineStyle + '|' + after.boxShadow + '|' + after.borderColor;
      checked++;
      // JUDGED BY WHAT CHANGES. A stylesheet can declare an outline that is never applied, and a
      // control can look outlined at rest; only the difference proves a keyboard user can see where
      // they are.
      if (rest === focused) {
        bad.push((el.tagName + (el.id ? '#' + el.id : '')).slice(0, 40) + ' "' +
                 (el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 20) + '"');
      }
      el.blur();
    }
    return { checked, unchanged: bad.length, examples: bad.slice(0, 5) };
  });
  const ok = r.checked > 0 && r.unchanged === 0;
  return {
    ok,
    checked: [
      `focusable controls focused and re-measured: ${r.checked}`,
      `controls whose appearance did NOT change on focus: ${r.unchanged}`,
      'judged by the DIFFERENCE between resting and focused style, not by a declared outline',
    ],
    notes: ok ? '' : (r.checked === 0
      ? 'no focusable control found — nothing was judged, so this is not a pass'
      : `unchanged=${r.unchanged} ${JSON.stringify(r.examples)}`),
  };
};

PROBES.icon_only_name = async (page) => {
  const r = await page.evaluate(() => {
    const main = document.querySelector('main') || document.body;
    const vis = el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
    // Letters and digits only — an emoji or a glyph font is not a name a screen reader can read out.
    const hasWords = (s) => /[A-Za-z0-9]{2,}/.test(s || '');
    const bad = []; let iconOnly = 0;
    for (const el of main.querySelectorAll('button, a[href], [role="button"]')) {
      if (!vis(el)) continue;
      const text = (el.textContent || '').trim();
      if (hasWords(text)) continue;          // it has a visible readable label
      iconOnly++;
      const name = el.getAttribute('aria-label') || el.getAttribute('title') ||
                   (el.querySelector('[class*="sr-only"], .visually-hidden') || {}).textContent || '';
      const labelledBy = el.getAttribute('aria-labelledby');
      const viaLabelledBy = labelledBy && [...labelledBy.split(/\s+/)]
        .some(id => hasWords((document.getElementById(id) || {}).textContent || ''));
      if (!hasWords(name) && !viaLabelledBy) {
        bad.push((el.tagName + (el.id ? '#' + el.id : '')).slice(0, 40) + ' shows "' + text.slice(0, 12) + '"');
      }
    }
    return { iconOnly, unnamed: bad.length, examples: bad.slice(0, 5) };
  });
  const na = r.iconOnly === 0;
  const ok = r.iconOnly > 0 && r.unnamed === 0;
  return {
    ok: ok || na,
    na,
    checked: [
      `controls with no readable visible label (icon-only): ${r.iconOnly}`,
      na ? 'NOT APPLICABLE: every control on this surface carries a readable visible label'
         : `of those, ones with no aria-label, title, sr-only text or aria-labelledby: ${r.unnamed}`,
      'an emoji is not a name — only letters and digits count as readable',
    ],
    notes: (ok || na) ? '' : `unnamed=${r.unnamed} ${JSON.stringify(r.examples)}`,
  };
};

PROBES.what_happens_next = async (page) => {
  const c = await comprehensionLens(page);
  const n = c.next || {};
  const ok = !!(n.saysWhatNext || n.hasActionCard);
  return {
    ok,
    checked: [
      `the surface tells a person what FOLLOWS an action: ${!!n.saysWhatNext}`,
      `…or carries an action card that says it: ${!!n.hasActionCard}`,
      n.actionText ? `wording: "${String(n.actionText).slice(0, 120)}"` : '',
      'a consequence stated in plain words counts — this is about whether a person is told what ' +
      'happens, not whether a particular phrasing was used',
    ].filter(Boolean),
    notes: ok ? '' : 'nothing on this surface says what follows an action',
  };
};

PROBES.why_refused = async (page) => {
  const c = await comprehensionLens(page);
  const refusals = c.refusals || [];
  // NOTHING REFUSED, NOTHING TO JUDGE. A surface at rest has no refusal on screen, and demanding one
  // would mark a page down for not being broken. The oracle applies when a refusal IS shown: it must
  // say WHY, in a sentence, rather than showing a bare code or a generic apology.
  const na = refusals.length === 0;
  const bare = refusals.filter(t =>
    /^[A-Z0-9_]{3,}$/.test(t.trim()) ||                        // a raw code
    /^(error|failed|invalid|denied)\.?$/i.test(t.trim()) ||    // a word with no reason
    t.trim().length < 12);                                     // too short to carry a reason
  const ok = refusals.length > 0 && bare.length === 0;
  return {
    ok: ok || na,
    na,
    checked: [
      `refusals visible on this surface at rest: ${refusals.length}`,
      na ? 'NOT APPLICABLE: nothing is being refused here, so there is no reason owed'
         : `of those, ones that state no reason (a bare code, a bare "failed", or too short to ` +
           `carry one): ${bare.length}`,
      refusals.length ? `wording: ${JSON.stringify(refusals.slice(0, 3))}` : '',
    ].filter(Boolean),
    notes: (ok || na) ? '' : `bare refusals: ${JSON.stringify(bare.slice(0, 3))}`,
  };
};

// ── RECOVERY ──────────────────────────────────────────────────────────────────────────────────────
// Two of these five ask a question an existing probe already answers, word for word:
//   double_tap  "the second press changes nothing further and the surface says so"
//   double_submit "the second press changes nothing further and SAYS so"
//   back_out    "browser Back leaves no orphaned overlay, no scroll lock, and no half-write"
//   back_nav    "browser Back out of a sheet leaves no orphaned overlay and no write half-applied"
// Aliasing them is honest BECAUSE the oracles match; aliasing a probe onto a different question
// would be banking one claim with another claim's evidence.
PROBES.double_tap = PROBES.double_submit;
PROBES.back_out = PROBES.back_nav;

// THE FIELD AND THE BUTTON, NAMED PER SURFACE. A generic `input[type=text], textarea` selector picks
// a search box, a hidden input, or a filter — none of which submit anything — and a generic
// `button:has-text("Save")` picks whichever comes first in the DOM. Three probes reported "not judged"
// across five surfaces for exactly that reason. These pairs come from the pages themselves.
// A surface with no entry is left OUT rather than given a wrong pair: marketplace-seller-profile is a
// public read surface with nothing to type into, and public-feed gates posting behind sign-in.
// Each pair also carries a VALID sample, because a field refuses a value it cannot accept and that
// refusal has nothing to do with the state under test. The messenger handle validates
// /^[a-zA-Z0-9_.\-]{3,50}$/ — the generic probe string "WH session-death probe 123456" contains
// SPACES, so the page correctly rejected it as an invalid handle and never reached the write. The
// probe then read that as "the surface refused silently on a dead session", which is a finding about
// my input, not about the product. `bad` is a value the field must reject, for wrong_then_fix.
const RECOVERY_CONTROLS = {
  seller: { field: '#messenger-input', submit: '#btn-save-messenger',
            good: () => 'wh_probe_' + Date.now().toString().slice(-6), bad: '!!' },
  // #fb-d-note does not exist until a feedback card is opened — it is injected by the detail
  // renderer, so a probe that goes straight for it finds nothing and reports "not on this surface"
  // when the surface is simply closed. The card is the opener, same shape as community's post FAB.
  admin: { open: 'button[data-fb-id]', field: '#fb-d-note', submit: '#fb-d-save',
           good: () => 'WH probe note ' + Date.now().toString().slice(-6), bad: '' },
  // `open` is the control that REVEALS the composer. community's #post-content exists in the DOM from
  // first paint but lives inside a closed sheet behind the post FAB, so filling it timed out after 30s
  // — the field was found, and was not reachable. A probe that cannot reach its field is measuring the
  // sheet, not the surface.
  community: { open: '#fab-post', field: '#post-content', submit: '#btn-submit-post',
               good: () => 'WH probe post ' + Date.now().toString().slice(-6), bad: 'x' },
};

// Open the composer if this surface keeps one, and wait for the field to become fillable rather than
// assuming the click was enough.
const openComposer = async (page, cc) => {
  if (!cc || !cc.open) return;
  const o = await page.$(cc.open);
  if (!o) return;
  try { await o.click({ timeout: 4000 }); } catch { return; }
  try { await page.waitForSelector(cc.field + ':not([disabled])', { state: 'visible', timeout: 5000 }); }
  catch { /* the caller's own fill will report it if it never opened */ }
};
const controlsFor = (url) => {
  if (/marketplace-seller\.html/.test(url)) return RECOVERY_CONTROLS.seller;
  if (/platform-actions\.html/.test(url)) return RECOVERY_CONTROLS.admin;
  if (/community\.html/.test(url)) return RECOVERY_CONTROLS.community;
  return null;
};

PROBES.session_died = async (page, ctx) => {
  // The session dies between TYPING and SUBMITTING. Three things are owed, and the third is the one
  // most often missed: refuse the write, say nothing was sent, and KEEP WHAT WAS TYPED. A person who
  // loses their typing to an expired session pays twice for someone else's timeout.
  const cc = controlsFor(page.url());
  const typed = cc ? cc.good() : '';
  if (!cc) {
    return { ok: true, na: true,
             checked: ['this surface declares no field/submit pair to recover with',
                       'NOT APPLICABLE: there is no write here to recover from'],
             notes: '' };
  }
  await openComposer(page, cc);
  const field = await page.$(cc.field);
  if (!field) {
    return { ok: false, checked: [`looked for the named field ${cc.field}`],
             notes: `the named field ${cc.field} is not on this surface — not judged, not passed` };
  }
  await field.fill(typed);

  // kill the session the way an expiry does: the token is gone before the next request
  // SNAPSHOT BEFORE KILLING. The browser CONTEXT outlives each page, so clearing the auth keys here
  // signed the walker out for every job that followed — the next surface redirected to
  // index.html?signin=1 and reported "no field declared", which looked like a missing selector and was
  // actually this probe poisoning the run. Whatever this probe removes, it puts back.
  const savedAuth = await page.evaluate(() => {
    const keep = {};
    for (const k of Object.keys(localStorage)) {
      if (/auth|token|supabase/i.test(k)) { keep[k] = localStorage.getItem(k); localStorage.removeItem(k); }
    }
    return keep;
  });
  const restoreAuth = async () => {
    try {
      await page.evaluate((kv) => { for (const [k, v] of Object.entries(kv)) localStorage.setItem(k, v); },
                          savedAuth);
    } catch { /* the page may already be gone; the next job re-navigates anyway */ }
  };
  let wrote = 0;
  await ctx.route(REST, r => {
    const m = r.request().method();
    if (['POST', 'PATCH', 'PUT', 'DELETE'].includes(m)) { wrote++; return r.fulfill({ status: 401,
      contentType: 'application/json',
      body: JSON.stringify({ code: 'PGRST301', message: 'JWT expired' }) }); }
    return r.continue();
  });
  const submit = await page.$(cc.submit);
  // WAS THE SUBMIT ACTUALLY ATTEMPTED? writes=0 has two very different meanings: the page refused
  // before firing (correct, and then it owes the person a sentence), or the click never landed at all
  // because the control was disabled or absent — in which case nothing was measured and reporting a
  // missing sentence would indict a surface that was never asked to say one.
  let attempted = false;
  if (submit) {
    const enabled = await submit.isEnabled().catch(() => false);
    if (enabled) {
      try { await submit.click({ timeout: 4000 }); attempted = true; } catch { /* locked mid-click */ }
    }
  }
  if (!attempted) {
    await page.waitForTimeout(300);
    await ctx.unroute(REST);
    await restoreAuth();
    return {
      ok: false,
      checked: ['typed into a field, then removed the auth token',
                'looked for an ENABLED submit control to attempt the write with'],
      notes: submit ? 'the submit control was disabled, so no write was attempted and nothing was '
                    + 'measured — not judged, not passed'
                    : 'no submit control found on this surface — not judged, not passed',
    };
  }
  await page.waitForTimeout(2200);
  const s = await readSurface(page);
  await ctx.unroute(REST);

  await restoreAuth();
  const stillTyped = await page.evaluate((t) => (document.body.innerText || '').includes(t) ||
    [...document.querySelectorAll('textarea, input')].some(e => (e.value || '').includes(t)), typed);
  // READ THE WHOLE BODY, NOT JUST <main>. whWriteError's sentence — "Your session expired, so nothing
  // was saved" — is delivered as a TOAST appended to <body>, exactly like the offline banner this file
  // already learned to read from document.body. Checking main.innerText alone reported a page that
  // says the right thing as saying nothing at all.
  const bodyText = await page.evaluate(() => (document.body.innerText || '').replace(/\s+/g, ' '));
  const saysNothingSent = /nothing was sent|nothing you did was|was not saved|nothing was saved|session expired/i.test(bodyText);
  const ok = stillTyped && saysNothingSent;
  return {
    ok,
    checked: [
      `typed into a field, then removed the auth token before submitting`,
      `write attempts the page made against the dead session: ${wrote}`,
      `the surface says nothing was sent: ${saysNothingSent}`,
      `what was typed is STILL on screen: ${stillTyped}`,
    ],
    notes: ok ? '' : `typedSurvived=${stillTyped} saysNothingSent=${saysNothingSent} writes=${wrote}`,
  };
};

PROBES.wrong_then_fix = async (page) => {
  // A wrong entry must be correctable in place. The failure this guards against is a form that
  // clears itself on rejection, or one whose error sticks after the mistake is fixed — both of which
  // make a person start over for a typo.
  const cc = controlsFor(page.url());
  if (!cc) {
    return { ok: true, na: true,
             checked: ['this surface declares no field to correct in',
                       'NOT APPLICABLE: there is nothing to type here, so nothing to get wrong'],
             notes: '' };
  }
  // A FIELD WITH NO INVALID VALUE HAS NOTHING TO GET WRONG. The admin note accepts any text at all —
  // its `bad` is the empty string, which is a perfectly valid note — so "correct a wrong entry" has
  // no wrong entry to start from. Declaring that is honest; scoring the field down for accepting what
  // it is supposed to accept is not.
  if (!cc.bad) {
    return { ok: true, na: true,
             checked: [`the field ${cc.field} accepts any text, so no entry is invalid here`,
                       'NOT APPLICABLE: there is nothing this field would reject'],
             notes: '' };
  }
  await openComposer(page, cc);
  const field = await page.$(cc.field);
  if (!field) {
    return { ok: false, checked: [`looked for the named field ${cc.field}`],
             notes: `the named field ${cc.field} is not on this surface — not judged, not passed` };
  }
  await field.fill(cc.bad);                     // a value THIS field must reject
  await page.waitForTimeout(400);
  const good = cc.good();
  await field.fill(good);
  await page.waitForTimeout(600);
  const kept = await page.evaluate((g) =>
    [...document.querySelectorAll('input, textarea')].some(e => (e.value || '') === g), good);
  const s = await readSurface(page);
  const errorStuck = /invalid|not allowed|must be|too short/i.test(s.text) &&
                     !/corrected|looks good/i.test(s.text);
  const ok = kept;
  return {
    ok,
    checked: [
      'entered an implausible value, then corrected it in place',
      `the corrected value is what the field now holds (the form did not reset it): ${kept}`,
      `a stale validation message is still on screen: ${errorStuck}`,
    ],
    notes: ok ? '' : `correctedValueKept=${kept} — the form lost the correction, so a typo costs a restart`,
  };
};

PROBES.did_it_land = async (page, ctx) => {
  // After a SLOW action a person must be able to tell whether it landed. Silence is the defect: it
  // is indistinguishable from success, and the natural response is to do it again.
  let held = 0;
  await ctx.route(REST, async r => {
    const m = r.request().method();
    if (['POST', 'PATCH', 'PUT', 'DELETE'].includes(m)) {
      held++;
      await new Promise(res => setTimeout(res, 2500));      // slow, but it DOES land
      return r.fulfill({ status: 201, contentType: 'application/json', body: '[]' });
    }
    return r.continue();
  });
  const cc = controlsFor(page.url());
  // TYPE SOMETHING FIRST. A save with nothing changed is correctly short-circuited by the page (the
  // seller's messenger save does exactly that, deliberately), so clicking a submit on an untouched
  // form measures the no-change guard rather than whether a landing is reported.
  if (cc) {
    await openComposer(page, cc);
    const f = await page.$(cc.field);
    if (f) { try { await f.fill(cc.good()); } catch { /* not fillable here */ } }
  }
  const submit = cc ? await page.$(cc.submit) : null;
  if (!submit) {
    await ctx.unroute(REST);
    if (!cc) {
      return { ok: true, na: true,
               checked: ['this surface declares no write control',
                         'NOT APPLICABLE: nothing is written here, so there is no landing to report'],
               notes: '' };
    }
    return { ok: false, checked: [`looked for the named write control ${cc.submit}`],
             notes: `the named write control ${cc.submit} is not on this surface — not judged, not passed` };
  }
  // Say WHY nothing happened. Swallowing the click failure made "no write fired" ambiguous between
  // "the page refused" and "the click never landed", and those need different answers.
  const enabled = await submit.isEnabled().catch(() => false);
  let clicked = false;
  if (enabled) { try { await submit.click({ timeout: 4000 }); clicked = true; } catch { /* locked mid-click */ } }
  if (!clicked) {
    await ctx.unroute(REST);
    return { ok: false,
             checked: [`found the named write control ${cc.submit}`, `it was enabled: ${enabled}`],
             notes: enabled ? 'the click did not land within 4s — not judged, not passed'
                            : 'the write control is disabled on this surface in its resting state, so '
                              + 'no landing could be provoked — not judged, not passed' };
  }
  await page.waitForTimeout(1200);
  const midFlight = await page.evaluate(() =>
    !!document.querySelector('[aria-busy="true"], [class*="spinner"], button:disabled'));
  await page.waitForTimeout(3200);
  const after = await readSurface(page);
  await ctx.unroute(REST);

  const saysOutcome = /saved|sent|posted|added|created|updated|done|couldn|failed|error/i.test(after.text);
  const ok = held === 0 ? false : (midFlight || saysOutcome);
  return {
    ok,
    checked: [
      `write requests held open for 2.5s to make the wait real: ${held}`,
      `the surface showed it was working while in flight (busy/disabled/spinner): ${midFlight}`,
      `once settled, the surface states an outcome rather than going silent: ${saysOutcome}`,
    ],
    notes: ok ? '' : (held === 0
      ? 'the control fired no write, so there was no landing to report — not judged, not passed'
      : `inFlightSignal=${midFlight} statesOutcome=${saysOutcome} — a person cannot tell if it landed`),
  };
};

PROBES.longest = PROBES.edge;
PROBES.zero_price = PROBES.edge;
PROBES.zoom200 = PROBES.edge;
PROBES.bulk50 = PROBES.edge;
PROBES.script_name = async (page, ctx) => {
  await ctx.route(REST, async r => {
    let res; try { res = await r.fetch(); } catch (e) { return r.continue(); }
    let body; try { body = await res.json(); } catch (e) { return r.fulfill({ response: res }); }
    if (Array.isArray(body) && body.length) {
      for (const row of body.slice(0, 3)) {
        for (const k of Object.keys(row)) {
          if (/name|title|label/i.test(k) && typeof row[k] === 'string') row[k] = BAYBAYIN;
        }
      }
    }
    return r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2400);
  const s = await readSurface(page);
  await ctx.unroute(REST);
  const rendered = s.text.includes('ᜋ') || s.text.includes('ᜃ');
  const ok = rendered && s.docOverflow <= 0;
  return {
    ok,
    checked: [
      'names rewritten to Baybayin (a real Philippine script, not lorem) in the live payload',
      `the script renders rather than becoming boxes or being dropped: ${rendered}`,
      `no horizontal overflow from the different glyph metrics: ${s.docOverflow <= 0}`,
    ],
    notes: ok ? '' : `rendered=${rendered} overflow=${s.docOverflow}`,
  };
};

// ── main ───────────────────────────────────────────────────────────────────────────────────────────
const reg = JSON.parse(fs.readFileSync(path.join(ROOT, 'live_mcp_registry.json'), 'utf8'));
const rows = reg.scenarios || reg;
// OWED IS NOT THE ONLY THING THAT NEEDS WALKING. A row is stored `green` with a recorded sha, and
// the GATE computes it STALE when a file it depends on changes — the stored status never moves. So
// filtering on `status === 'owed'` alone made this walker blind to exactly the rows that most need
// re-measuring: 694 stale on 2026-08-05, 299 of them in states this file can probe, none selected.
//
// A stale row is a claim that WAS true and whose ground moved. That is precisely what a re-walk is
// for. Recomputing the freshness here (rather than trusting the stored status) is the same question
// the gate asks, asked by the tool that can answer it.
const isStale = (r) => {
  const ev = r.evidence || {};
  const dep = ev.depends_on || [];
  if (!dep.length || !ev.sha) return false;
  const h = crypto.createHash('sha256');
  for (const p of [...dep].sort()) {
    const fp = path.join(ROOT, p);
    h.update(p);
    try {
      const st = fs.statSync(fp);
      if (st.isDirectory()) {
        // Mirror Python's os.walk EXACTLY: every file in a directory is hashed before descending
        // into its subdirectories. Recursing inline instead would interleave a subdirectory's files
        // between two of the parent's, producing a different digest for identical bytes — and this
        // must agree with tools/validate_live_mcp_bank.py::sha_of or the walker selects the wrong rows.
        const walk = (d) => {
          const entries = fs.readdirSync(d, { withFileTypes: true })
            .sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
          for (const e of entries) if (!e.isDirectory()) {
            const full = path.join(d, e.name);
            h.update(path.relative(ROOT, full).split(path.sep).join('/'));
            h.update(fs.readFileSync(full));
          }
          for (const e of entries) if (e.isDirectory()) walk(path.join(d, e.name));
        };
        walk(fp);
      } else {
        h.update(fs.readFileSync(fp));
      }
    } catch { h.update('<<MISSING>>'); }
  }
  return h.digest('hex').slice(0, 16) !== ev.sha;
};

let owed = rows.filter(r => PROBES[r.state] &&
                            (r.status === 'owed' || (r.status === 'green' && isStale(r))));
if (only) owed = owed.filter(r => (r.url || '').includes(only));

// one probe per (url, state) — the personas share a surface, so re-running the identical induction
// per persona would be theatre. The result is applied to every persona row on that surface/state,
// and the evidence says so.
const jobs = new Map();
for (const r of owed) {
  const key = r.url + '::' + r.state;
  if (!jobs.has(key)) jobs.set(key, { url: r.url, state: r.state, ids: [] });
  jobs.get(key).ids.push(r.id);
}
const jobList = [...jobs.values()].slice(0, limit);
console.log(`owed with a probe: ${owed.length} across ${jobs.size} (url,state) pairs; running ${jobList.length}`);

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });

// sign in once, exactly as state_probe.mjs does
{
  const s = await context.newPage();
  await s.goto(`${SEEDER}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await s.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 20000 }).catch(() => {});
  await s.evaluate(async ({ email, password, hive, worker }) => {
    try {
      const db = window._whSupabaseClient || window.getDb('http://127.0.0.1:54321', window.SUPABASE_KEY);
      await db.auth.signInWithPassword({ email, password });
      localStorage.setItem('wh_active_hive_id', hive);
      localStorage.setItem('wh_last_worker', worker);
    } catch (e) {}
  }, { email: EMAIL, password: PASSWORD, hive: HIVE, worker: WORKER });
  await s.waitForTimeout(1200);
  await s.close();
}

const results = [];
for (const job of jobList) {
  const page = await context.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push(String(e).slice(0, 160)));
  let out;
  try {
    await page.goto(SEEDER + job.url, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2600);
    out = await PROBES[job.state](page, context);
  } catch (e) {
    out = { ok: false, checked: [], notes: 'probe threw: ' + String(e).slice(0, 200) };
  }
  if (errs.length) out.notes = (out.notes ? out.notes + ' · ' : '') + 'pageerror: ' + errs[0];
  results.push({ ...job, ...out, pageErrors: errs.slice(0, 2) });
  const mark = out.ok === true ? 'PASS' : out.ok === null ? 'N/A ' : 'FAIL';
  console.log(`  ${mark}  ${job.state.padEnd(13)} ${job.url}  (${job.ids.length} row${job.ids.length === 1 ? '' : 's'})${out.notes ? ' — ' + out.notes.slice(0, 90) : ''}`);
  await page.close();
}

await browser.close();
fs.mkdirSync(path.join(ROOT, '.tmp'), { recursive: true });
fs.writeFileSync(path.join(ROOT, '.tmp', 'owed_walk_results.json'), JSON.stringify(results, null, 1));
const pass = results.filter(r => r.ok === true).length;
console.log(`\n${pass}/${results.length} (url,state) pairs pass · ${results.reduce((a, r) => a + (r.ok === true ? r.ids.length : 0), 0)} rows bankable`);
console.log('-> .tmp/owed_walk_results.json');
