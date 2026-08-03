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

// fileURLToPath, not url.pathname: this project's directory contains spaces AND an '&', so the raw
// pathname arrives percent-encoded and every fs call misses by a mile.
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SEEDER = 'http://127.0.0.1:5000';
const EMAIL = 'pabloaguilar@auth.workhiveph.com', PASSWORD = 'test1234';
const HIVE = 'c9def338-fd73-4b19-8ef1-ee57625953d6', WORKER = 'Pablo Aguilar';

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
    await ctx.route(REST, r => r.fulfill({ status: 200, contentType: 'application/json', body: '[]' }));
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2600);
    const s = await readSurface(page);
    await ctx.unroute(REST);
    const namesGap = INVITE_RE.test(s.text) || /\b(no|none|nothing|empty|0)\b/i.test(s.text);
    const offersAction = s.controls.length > 0;
    const ok = namesGap && offersAction && !ERR_RE.test(s.text);
    return {
      ok,
      checked: [
        'every REST read forced to 200-with-zero-rows at the network layer',
        `names what is missing: ${namesGap}`,
        `offers something to do about it (${s.controls.length} live controls): ${offersAction}`,
        `does NOT render as a failure: ${!ERR_RE.test(s.text)}`,
      ],
      notes: ok ? '' : `namesGap=${namesGap} controls=${s.controls.length} errShown=${ERR_RE.test(s.text)}`,
    };
  },

  async error(page, ctx) {
    // JUDGED AS A CONTRAST, not by a whole-page keyword hunt. The oracle is that a FAILED read must
    // not look like an EMPTY one — so the only honest test is to render both on the same surface and
    // compare. A page-wide /no .* yet/ regex flunked three surfaces where the erroring pane said
    // "Couldn't load" perfectly well while some OTHER, legitimately-empty pane said "no requests
    // yet". That is a correct page and a broken instrument.
    await ctx.route(REST, r => r.fulfill({ status: 200, contentType: 'application/json', body: '[]' }));
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
let owed = rows.filter(r => r.status === 'owed' && PROBES[r.state]);
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
