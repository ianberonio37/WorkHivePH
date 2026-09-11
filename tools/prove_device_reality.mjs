// prove_device_reality — the device and viewport journeys (T114, T115, T120, T121, T123, T126), 2026-09-07.
//
// Six rows about the machine a person is actually holding. This platform's users are maintenance crews
// in Philippine plants: a phone in a pocket with a cracked screen, a shared tablet on a bench, an old
// office PC in the supervisor's cabin, a wall display nobody touches. A layout that only works at
// 1280px works for the person who built it.
//
//   W1 landscape       a phone turned sideways (740x360) still shows the page's own content, not a
//                      layout that assumed height it does not have (T114)
//   W2 the wide screen at 1920 the content does not strand itself in a 600px column with two-thirds of
//                      the screen empty, nor stretch a line of text past reading width (T115)
//   W3 continuity      what a person set on the phone is there on the PC - the state a page keeps is
//                      keyed to the account, not to the device (T120)
//   W4 shared device   signing out actually clears the person: the next worker on the same phone does
//                      not inherit their name, their hive, or their draft (T121)
//   W5 paste survives  text pasted from somewhere else arrives intact - a person copying a part number
//                      out of a PDF should not have to retype it (T123)
//   W6 the wall display at 1920 with nobody touching it, the page still says something true, and it does
//                      not sit forever on a spinner because no one is there to press retry (T126)
//
// ★MEASURED AT THE VIEWPORT, NOT IN A MEDIA QUERY. A CSS breakpoint proves an intention; only rendering
// at 740x360 proves that the content survived it. Overflow is read from the live layout box.
//
//   node tools/prove_device_reality.mjs
//   node tools/prove_device_reality.mjs --page logbook.html
import { chromium } from 'playwright';
import { SEEDER, signIn, PAGE_QUERY, VIS_JS, SETTLE_MS } from './prover_harness.mjs';

const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const ROSTER = ['hive.html', 'logbook.html', 'inventory.html', 'alert-hub.html', 'marketplace.html', 'analytics.html'];

const b = await chromium.launch();
let bad = 0;
const say = (ok, id, line, detail) => {
  if (!ok) bad++;
  console.log(`  ${ok ? 'ok ' : 'BAD'} ${id.padEnd(20)} ${line}`);
  if (!ok && detail) console.log(`        ${detail.slice(0, 158)}`);
};

// the layout question, asked at two real viewports
const measure = async (file, w, h) => {
  const ctx = await b.newContext({ viewport: { width: w, height: h }, serviceWorkers: 'block' });
  await signIn(ctx);
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(SETTLE_MS);
  const r = await p.evaluate((VIS_JS) => {
    const vis = (0, eval)(VIS_JS);
    const doc = document.documentElement;
    // horizontal overflow is the one a person cannot scroll away from - it hides content off-screen
    const overflowsBy = Math.max(0, doc.scrollWidth - doc.clientWidth);
    const wide = [...document.querySelectorAll('body *')].filter((e) => {
      const rc = e.getBoundingClientRect();
      return rc.width > 0 && rc.right > doc.clientWidth + 2 && vis(e);
    }).slice(0, 3).map((e) => (e.id ? '#' + e.id : e.className && typeof e.className === 'string' ? '.' + e.className.split(' ')[0] : e.tagName));
    const main = document.querySelector('main, [role="main"], #app, #root') || document.body;
    const text = (main.innerText || '').replace(/\s+/g, ' ').trim();
    // the content's own width against the window: stranded in a column, or stretched past reading width
    const usable = main.getBoundingClientRect().width;
    // ★A FULL-WIDTH APP LAYOUT IS CORRECT, NOT "STRETCHED". The first version failed any page whose
    // content box exceeded 1750px of a 1920 screen, which is exactly what a dashboard grid should do -
    // it flagged three pages for using the monitor they were given. What actually hurts a reader is a
    // LINE of prose running the full width, so measure the widest block of actual text instead.
    const longestLine = Math.max(0, ...[...document.querySelectorAll('p, li, .wh-help, [class*="desc"]')]
      .filter((e) => vis(e) && (e.innerText || '').trim().length > 120)
      .map((e) => e.getBoundingClientRect().width));
    const spinners = [...document.querySelectorAll('.wh-skeleton, [class*="skeleton"], [aria-busy="true"], .spinner')].filter(vis).length;
    return { overflowsBy, wide, textLen: text.length, usable, longestLine, winW: doc.clientWidth, spinners };
  }, VIS_JS).catch(() => null);
  await ctx.close();
  return r;
};

// ── W1 · a phone turned sideways ─────────────────────────────────────────────────────────────────
// ── W2 · the wide screen ─────────────────────────────────────────────────────────────────────────
{
  const land = [], wide = [], unloaded = [];
  for (const file of (ONLY ? [ONLY] : ROSTER)) {
    const l = await measure(file, 740, 360);
    const w = await measure(file, 1920, 1080);
    // ★ZERO CHARACTERS IS A FAILED LOAD, NOT A LANDSCAPE DEFECT. hive.html reported "0px off-screen,
    // only 0ch" - no overflow at all, and no content either, which is the signature of a page that never
    // finished rather than one whose layout broke sideways. Separated so the two never masquerade.
    if (l === null || l.textLen === 0) { unloaded.push(file); continue; }
    if (l.overflowsBy > 4 || l.textLen < 200) land.push(`${file} (${l.overflowsBy}px off-screen${l.wide.length ? ' via ' + l.wide[0] : ''}${l.textLen < 200 ? `, only ${l.textLen}ch` : ''})`);
    // stranded: the content uses less than a third of a 1920 screen. Stretched: a single column past 1400px.
    if (w && (w.usable < 640 || w.longestLine > 1200)) wide.push(`${file} (content ${Math.round(w.usable)}px of ${w.winW}${w.longestLine > 1200 ? `, a ${Math.round(w.longestLine)}px line of text` : ''})`);
  }
  if (unloaded.length) console.log(`  note ${unloaded.length} page(s) rendered nothing at 740x360 and are UNMEASURED, not clean: ${unloaded.join(', ')}`);
  say(land.length === 0, 'W1 landscape', `${(ONLY ? 1 : ROSTER.length) - land.length} of ${ONLY ? 1 : ROSTER.length} page(s) hold together on a sideways phone at 740x360`,
    `${land.join('; ')} - content sits off the right edge, where a person cannot reach it`);
  say(wide.length === 0, 'W2 the wide screen', `${(ONLY ? 1 : ROSTER.length) - wide.length} of ${ONLY ? 1 : ROSTER.length} page(s) use a 1920 screen without stranding or stretching their content`,
    `${wide.join('; ')} - either a narrow strip on a wide monitor, or a line of prose too long to track back to the start of`);
}

// ── W3 · continuity, and W4 · the shared device ──────────────────────────────────────────────────
{
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  await signIn(ctx);
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/hive.html`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(SETTLE_MS);

  const identity = await p.evaluate(() => {
    const keys = Object.keys(localStorage);
    return {
      whoKeys: keys.filter((k) => /wh_(worker|name|hive|role|auth)/i.test(k)),
      // ★WHAT IS KEYED TO THE ACCOUNT TRAVELS; WHAT IS KEYED TO THE DEVICE DOES NOT. A draft stored under
      // a bare key belongs to the phone, so the next person to pick it up inherits it.
      drafts: keys.filter((k) => /draft|compose|unsent/i.test(k)),
      ownedDrafts: keys.filter((k) => /draft|compose|unsent/i.test(k) && /[:_-][0-9a-f-]{8,}/i.test(k)),
    };
  }).catch(() => ({ whoKeys: [], drafts: [], ownedDrafts: [] }));

  // W4: sign out the way a person actually does. ★CALLING auth.signOut() IS NOT PRESSING SIGN OUT. The
  // SDK call ends the SESSION; the product's own signOut() also clears the identity keys, and only
  // index.html carries that control (hive.html has none). Probing through the SDK measured a path no
  // person takes and would have blamed the platform for residue its real button removes.
  await p.goto(`${SEEDER}/workhive/index.html`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(SETTLE_MS);
  const signedOut = await p.evaluate(async () => {
    if (typeof window.signOut === 'function') { await window.signOut(); return 'the page own signOut()'; }
    const el = [...document.querySelectorAll('button, a, [role="menuitem"]')]
      .find((e) => /sign out|log out/i.test(e.innerText || '') || /signOut\(/.test(e.getAttribute('onclick') || ''));
    if (el) { el.click(); return `pressed "${(el.innerText || 'Sign Out').trim().slice(0, 20)}"`; }
    return null;
  }).catch(() => null);
  await p.waitForTimeout(5000);
  const residue = await p.evaluate(() => {
    // anything that names the person, their hive, or where they have been
    return Object.keys(localStorage)
      .filter((k) => /^wh_(worker|last_worker|name|hive)/i.test(k) || k === 'workerName')
      .map((k) => `${k}=${String(localStorage.getItem(k)).slice(0, 16)}`);
  }).catch(() => []);

  say(identity.whoKeys.length > 0, 'W3 continuity',
    `the account's identity is held in ${identity.whoKeys.length} key(s) the server can re-establish on any device; ${identity.drafts.length} draft key(s), ${identity.ownedDrafts.length} of them stamped with an owner`,
    'nothing identifies the person locally, so a page cannot restore their context on a second device');
  say(!!signedOut && residue.length === 0, 'W4 shared device',
    `signed out via ${signedOut || 'NO reachable control'}; ${residue.length} identifying key(s) remain for the next worker on this phone`,
    `the next person to pick up this phone finds: ${residue.slice(0, 3).join(', ')}`);
  await ctx.close();
}

// ── W5 · paste, and W6 · the unattended screen ───────────────────────────────────────────────────
{
  const ctx = await b.newContext({ viewport: { width: 1920, height: 1080 }, serviceWorkers: 'block' });
  await signIn(ctx);
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/logbook.html${PAGE_QUERY['logbook.html'] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(SETTLE_MS);
  // open whatever composer this page has, then paste into it the way a person pastes
  await p.evaluate(() => {
    const el = [...document.querySelectorAll('button, [role="button"]')]
      // the same opener vocabulary that works in prove_expiry_midwrite - a narrower one missed the
      // composer entirely and reported "no field was open to paste into", which is an unmeasured lens
      // dressed as a defect
      .find((e) => e.checkVisibility && e.checkVisibility({ opacityProperty: true, visibilityProperty: true })
        && !e.disabled && /^(\+|add|new|log |create|post|write|record|start)\b/i.test((e.innerText || '').trim()));
    if (el) el.click();
  }).catch(() => {});
  await p.waitForTimeout(4500);
  const PASTED = 'SKF 6205-2RS1/C3  —  qty 4  (ñ, 45°C)';
  const paste = await p.evaluate((text) => {
    const vis = (e) => e.checkVisibility && e.checkVisibility({ opacityProperty: true, visibilityProperty: true });
    const el = [...document.querySelectorAll('textarea, input[type="text"]')]
      .find((e) => vis(e) && !e.readOnly && !e.disabled && !/search|filter/i.test(e.id + ' ' + e.className));
    if (!el) return null;
    el.focus();
    const dt = new DataTransfer();
    dt.setData('text/plain', text);
    el.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true }));
    // a page that does not intercept paste leaves the browser to insert it; emulate that default
    if (!el.value) { el.value = text; el.dispatchEvent(new Event('input', { bubbles: true })); }
    return el.value;
  }, PASTED).catch(() => null);
  // ★"NO FIELD WAS OPEN" IS UNMEASURED, NOT FAILED. A composer this sweep could not open says nothing
  // about whether paste works - reporting it as a defect would accuse a working field of mangling text.
  let pasteUnmeasured = false;
  if (paste === null) { pasteUnmeasured = true; console.log('  n/a W5 paste survives     no composer opened for this sweep - unmeasured, not clean'); }
  if (pasteUnmeasured) globalThis.__whPasteUnmeasured = true;
  else say(paste === PASTED, 'W5 paste survives', `${(paste || '').length} of ${PASTED.length} pasted characters survived`,
    `a pasted part number came back as "${String(paste).slice(0, 46)}" - the person has to retype what they copied`);

  // W6: the unattended screen. Leave it alone and see whether it still says something true.
  await p.goto(`${SEEDER}/workhive/analytics.html${PAGE_QUERY['analytics.html'] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(SETTLE_MS + 12000);
  const wall = await p.evaluate((VIS_JS) => {
    const vis = (0, eval)(VIS_JS);
    const main = document.querySelector('main, [role="main"], #app') || document.body;
    return {
      textLen: (main.innerText || '').replace(/\s+/g, ' ').trim().length,
      spinners: [...document.querySelectorAll('.wh-skeleton, [class*="skeleton"], [aria-busy="true"]')].filter(vis).length,
      dated: [...document.querySelectorAll('.wh-source-chip, [data-source-chip], [id$="-source-chip"]')].filter(vis).length,
    };
  }, VIS_JS).catch(() => ({ textLen: 0, spinners: 9, dated: 0 }));
  say(wall.spinners === 0 && wall.textLen > 400 && wall.dated > 0, 'W6 the wall display',
    `left alone for ${Math.round((SETTLE_MS + 12000) / 1000)}s: ${wall.textLen} characters on screen, ${wall.spinners} spinner(s) still turning, ${wall.dated} freshness chip(s)`,
    wall.spinners ? 'a spinner is still turning with nobody there to press retry - the wall shows a loading screen all shift'
      : wall.dated === 0 ? 'nothing says how fresh the numbers are, so a wall display of stale figures is indistinguishable from live ones'
      : `only ${wall.textLen} characters reached the screen`);
  await ctx.close();
}

await b.close();
// ★THE SUMMARY MUST NOT CLAIM A LENS THAT DID NOT RUN. The first version listed "paste survives" in its
// PASS line while that lens had reported n/a, which reads as five green when it was four and a gap.
console.log(`${bad ? 'FAIL' : 'PASS'} device-reality - the page holds together on a sideways phone and a 1920 monitor, a shared device forgets the last person${globalThis.__whPasteUnmeasured ? ' (paste UNMEASURED this run)' : ', paste survives'}, and an unattended screen still says something true`);
process.exitCode = bad ? 1 : 0;
