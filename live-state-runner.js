// live-state-runner.js — induce each owed-scenario state in a REAL browser and report a verdict.
//
// Ian, 2026-08-04: "it should be live mcp walks on every owed". The batch harness
// (tools/walk_owed_scenarios.mjs) drives its own headless Chromium; this module runs the SAME
// inductions inside whatever browser is actually open, so the evidence behind a banked row comes
// from the live MCP session rather than a separate headless process.
//
// It is served from the web root on purpose: the MCP evaluates a one-line import instead of pasting
// a 60-line function per surface, which keeps each walk cheap and makes the walk reproducible by
// hand — open any page and run `(await import('/workhive/live-state-runner.js')).run()`.
//
// Two rules it inherits from the harness, both learned the hard way:
//   · a failure is served as a REAL 500 response, never a rejected promise (a rejection leaves a
//     stuck skeleton and proves something else entirely)
//   · `error` is judged as a CONTRAST against this same surface rendered with zero rows, because the
//     oracle is "a failed read must not look like an empty one" — a keyword hunt flunks pages whose
//     erroring pane is correct while some other pane is legitimately empty

const REST = /\/rest\/v1\/(?!rpc\/)/;
const LONG = 'Emergency Switchgear Overhaul and Transformer Oil Regeneration for the Southern Tagalog Industrial Estate Incorporated';
const BAYBAYIN = 'ᜋᜄᜈ᜔ᜆᜅ᜔ ᜃᜄᜋᜒᜆᜈ᜔ ᜐ ᜉᜎᜒᜃ';
const ERR = /couldn['’]?t load|could not load|failed to load|unavailable|something went wrong|error/i;
const INVITE = /no .{0,24}yet|be the first|get started|hail your first|post your first/i;

// Every page names its data path differently. A loader this list does NOT know simply never re-runs,
// so the induced condition never reaches the screen and the probe compares the page to itself —
// which is exactly how public-feed.html reported "error looks identical to empty" while its real
// behaviour (measured on a fresh load with the failure already in place) is a correct
// "Couldn't load the public feed ... Retry". The tell was longNameRendered=false: no re-fetch.
const LOADERS = ['loadListings', 'loadCounts', 'loadClientServices', 'loadServices', 'refreshQueues',
                 'loadFeed', 'loadPosts', 'loadAchievements', 'loadProfile', 'loadSeller',
                 'loadInitial', 'fetchPage', 'loadMore', 'init'];

function read() {
  const m = document.querySelector('main') || document.body;
  const t = (m.innerText || '').replace(/\s+/g, ' ').trim();
  const over = [...m.querySelectorAll('*')].filter(el =>
    el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0 &&
    getComputedStyle(el).overflowX === 'visible' &&
    !el.closest('details:not([open])')).length;
  return {
    t, len: t.length, over,
    doc: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    junk: (t.match(/\bundefined\b|\bNaN\b|\[object Object\]/g) || []).length,
    ctrls: [...m.querySelectorAll('button,a[href],input,select')].filter(e => e.offsetParent).length,
    innerWidth: window.innerWidth,
  };
}

async function rerun(ms) {
  document.dispatchEvent(new Event('DOMContentLoaded'));
  let ran = 0;
  for (const k of LOADERS) {
    if (typeof window[k] === 'function') {
      ran++;
      // empty-catch-allow: a page exposes several loaders and some throw when their pane is not
      // open. The probe wants whichever ones DO run; a throw from one must not stop the others.
      try { await window[k](); } catch (e) { /* empty-catch-allow: see above */ }
    }
  }
  await new Promise(r => setTimeout(r, ms || 1700));
  return ran;
}

export async function run() {
  const orig = window.__lsrFetch || window.fetch;
  window.__lsrFetch = orig;
  const set = fn => { window.fetch = fn; };
  const out = {};

  // POPULATED — the surface as it actually stands right now
  {
    const s = read();
    out.populated = {
      ok: s.len > 120 && s.doc <= 0 && s.junk === 0 && !ERR.test(s.t),
      len: s.len, docOverflow: s.doc, junk: s.junk, unclipped: s.over,
      note: 'structural half only: number-vs-source-of-truth is checked by the psql-backed rows',
    };
  }

  // EMPTY — every read returns zero rows
  set(async (i, x) => {
    const u = typeof i === 'string' ? i : (i && i.url) || '';
    return REST.test(u) ? new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } }) : orig(i, x);
  });
  await rerun();
  const emptyText = read().t;
  {
    const s = read();
    const namesGap = INVITE.test(s.t) || /\b(no|none|nothing|empty|0)\b/i.test(s.t);
    out.empty = { ok: namesGap && s.ctrls > 0 && !ERR.test(s.t), namesGap, controls: s.ctrls, renderedAsFailure: ERR.test(s.t) };
  }

  // ERROR — a real 500, judged against the empty render above
  set(async (i, x) => {
    const u = typeof i === 'string' ? i : (i && i.url) || '';
    return REST.test(u)
      ? new Response(JSON.stringify({ code: '500', message: 'induced failure' }), { status: 500, headers: { 'Content-Type': 'application/json' } })
      : orig(i, x);
  });
  await rerun();
  {
    const s = read();
    const norm = z => z.replace(/[\d,.\s]+/g, ' ').trim();
    const same = norm(s.t) === norm(emptyText);
    out.error = { ok: ERR.test(s.t) && !same, saysError: ERR.test(s.t), indistinguishableFromEmpty: same,
                  offersRetry: /retry|try again|reload/i.test(s.t) };
  }

  // EDGE — the real payload rewritten to its boundaries, then re-measured narrow
  const mutate = (mapper) => set(async (i, x) => {
    let u = typeof i === 'string' ? i : (i && i.url) || '';
    // KEYSET PAGINATION DEFEATS A NAIVE RE-RUN. public-feed.html's loadInitial() keeps its cursor in
    // module scope and queries .lt('created_at', cursor); calling it a second time therefore asks for
    // the page AFTER the last one and comes back with zero rows, so the mutated payload never reached
    // the screen and the boundary states passed on an empty render. The cursor is unreachable from
    // here, but the REQUEST is not: drop the cursor filter and the re-run asks for page one again.
    // Confirmed on public-feed — 0 rows and no marker before, 15 cards and the marker after.
    if (REST.test(u) && /created_at=(lt|gt)\./.test(u)) {
      u = u.replace(/[?&]created_at=(lt|gt)\.[^&]*/g, m => (m[0] === '?' ? '?' : ''));
      i = (typeof i === 'string') ? u : new Request(u, i);
    }
    const r = await orig(i, x);
    if (!REST.test(u)) return r;
    let b; try { b = await r.clone().json(); } catch (e) { return r; }
    if (Array.isArray(b) && b.length) b.slice(0, 3).forEach(mapper);
    return new Response(JSON.stringify(b), { status: 200, headers: { 'Content-Type': 'application/json' } });
  });
  // `content` and `body` carry the visible text on the feed surfaces the way `title` does on the
  // listing surfaces — public-feed.html renders escHtml(p.content), so a mutation that rewrote only
  // name/title/label left the longest string on the page untouched and the boundary untested.
  mutate(row => {
    for (const k of Object.keys(row)) {
      if (/name|title|label|scope|desc|content|body|message/i.test(k) && typeof row[k] === 'string') row[k] = LONG;
      if (/price|amount|budget|rate|fee|cost/i.test(k) && typeof row[k] === 'number') row[k] = 0;
    }
  });
  await rerun();
  {
    const s = read();
    const landed = /Southern Tagalog/.test(s.t);
    // A STATE THAT NEVER REACHED THE SCREEN IS NOT A STATE THAT PASSED. The header above already
    // named this tell — longNameRendered=false means no re-fetch, so the page was compared against
    // itself — but the verdict never used it, and `ok` was computed from overflow alone. A page
    // whose loader this module cannot re-run therefore reported a clean pass for a boundary it had
    // never rendered. That is the same shape as the structural-probe-answering-a-behavioural-oracle
    // defect the whole bank was rebuilt around, so it is reported as INCONCLUSIVE rather than as
    // either a pass or a failure: the walk must find the loader, not bank the silence.
    out.edge = { ok: landed && s.doc <= 0 && s.over === 0, inconclusive: !landed,
                 docOverflow: s.doc, unclipped: s.over, longNameRendered: landed, atWidth: s.innerWidth };
  }

  // SCRIPT_NAME — a real Philippine script, not lorem
  mutate(row => { for (const k of Object.keys(row)) {
    if (/name|title|label|content|body|message/i.test(k) && typeof row[k] === 'string') row[k] = BAYBAYIN; } });
  await rerun();
  {
    const s = read();
    const rendered = /[ᜀ-ᜟ]/.test(s.t);
    out.script_name = { ok: rendered && s.doc <= 0, inconclusive: !rendered,
                        baybayinRendered: rendered, docOverflow: s.doc };
  }

  // DEGRADED — the network drops out from under the page
  set(async () => { throw new TypeError('Failed to fetch'); });
  window.dispatchEvent(new Event('offline'));
  await new Promise(r => setTimeout(r, 1500));
  out.degraded = {
    ok: [...document.body.querySelectorAll('div')].some(el =>
      /you are offline|no connection|reconnect/i.test(el.innerText || '') &&
      getComputedStyle(el).display !== 'none' && (el.offsetParent || el.getClientRects().length)),
  };

  window.fetch = orig;
  window.dispatchEvent(new Event('online'));
  out._allOk = Object.keys(out).filter(k => !k.startsWith('_')).every(k => out[k].ok === true);
  return out;
}

// ── F3 · BH-ui-visual (the two the battery cannot do) ────────────────────────────────────────
// ufai_battery.js already runs axe-core WCAG 2.2 AA (contrast, names, target size) and the
// focus-visible tab-walk, across every enumerated state via sweepAll(). REUSE that; this adds only
// the two it does not measure:
//
//   APCA — axe grades WCAG 2.x contrast RATIO, which is a different model from APCA's perceptual
//   lightness contrast. They disagree often enough that this platform has already recorded a page
//   scoring WCAG 100% and APCA 25%. Passing one says nothing about the other.
//
//   REDUCED MOTION — the battery reports "OS-off" because the browser is not emulating
//   prefers-reduced-motion, so it cannot observe the honoured state. Whether the page HONOURS it is
//   still answerable: does anything animate, and is there a rule that turns it off.
//
// Backgrounds are composited through ancestors. A tinted pill over a dark card over a gradient page
// is the exact shape that made naive checks read a transparent background as white and pass.
const APCA = {
  normBG: 0.56, normTXT: 0.57, revTXT: 0.62, revBG: 0.65,
  blkThrs: 0.022, blkClmp: 1.414, scale: 1.14, loOffset: 0.027, deltaYmin: 0.0005,
};

function _parseRGBA(s) {
  const m = String(s).match(/rgba?\(([^)]+)\)/);
  if (!m) return null;
  const p = m[1].split(',').map(x => parseFloat(x.trim()));
  return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
}

function _overlay(fg, bg) {            // source-over compositing
  const a = fg.a + bg.a * (1 - fg.a);
  if (a === 0) return { r: 0, g: 0, b: 0, a: 0 };
  return {
    r: (fg.r * fg.a + bg.r * bg.a * (1 - fg.a)) / a,
    g: (fg.g * fg.a + bg.g * bg.a * (1 - fg.a)) / a,
    b: (fg.b * fg.a + bg.b * bg.a * (1 - fg.a)) / a,
    a,
  };
}

// A GRADIENT IS A BACKGROUND. Reading backgroundColor alone reports rgba(0,0,0,0) for anything
// painted by background-image, so the walk fell through to the page canvas and produced nonsense:
// the seller's Save button is dark navy on a BRIGHT ORANGE gradient -- high contrast -- and scored
// Lc 0, "invisible". 41 of 49 text nodes on that surface sit over a gradient, so almost every
// reading was wrong. Averaging the gradient's colour stops is an approximation, and it is enormously
// closer than pretending the element is transparent. A url() image cannot be averaged from CSS at
// all, so those are reported INCONCLUSIVE rather than scored.
function _gradientAvg(bgImage) {
  if (!bgImage || bgImage === 'none') return null;
  if (/url\(/i.test(bgImage)) return { unknown: true };
  const stops = bgImage.match(/rgba?\([^)]+\)/g);
  if (!stops || !stops.length) return null;
  const cs = stops.map(_parseRGBA).filter(Boolean);
  if (!cs.length) return null;
  const n = cs.length;
  return { r: cs.reduce((s, c) => s + c.r, 0) / n,
           g: cs.reduce((s, c) => s + c.g, 0) / n,
           b: cs.reduce((s, c) => s + c.b, 0) / n,
           a: cs.reduce((s, c) => s + c.a, 0) / n };
}

function _effectiveBg(el) {
  // walk up compositing each ancestor's background until opaque; the page canvas is the floor
  let acc = { r: 0, g: 0, b: 0, a: 0 };
  let inconclusive = false;
  for (let n = el; n && n !== document.documentElement.parentNode; n = n.parentElement) {
    const st = getComputedStyle(n);
    const g = _gradientAvg(st.backgroundImage);
    if (g && g.unknown) { inconclusive = true; break; }
    if (g) { acc = _overlay(acc, g); if (acc.a >= 0.999) break; }
    const c = _parseRGBA(st.backgroundColor);
    if (c && c.a > 0) { acc = _overlay(acc, c); if (acc.a >= 0.999) break; }
  }
  if (!inconclusive && acc.a < 0.999) {
    const bodySt = getComputedStyle(document.body);
    const bodyG = _gradientAvg(bodySt.backgroundImage);
    const body = (bodyG && !bodyG.unknown) ? bodyG
               : (_parseRGBA(bodySt.backgroundColor) || { r: 255, g: 255, b: 255, a: 1 });
    acc = _overlay(acc, { ...body, a: 1 });
  }
  acc.inconclusive = inconclusive;
  return acc;
}

function _Y(c) {
  const f = v => Math.pow(Math.max(0, Math.min(255, v)) / 255, 2.4);
  return 0.2126729 * f(c.r) + 0.7151522 * f(c.g) + 0.0721750 * f(c.b);
}

function _apcaLc(txt, bg) {
  let Yt = _Y(txt), Yb = _Y(bg);
  Yt = Yt > APCA.blkThrs ? Yt : Yt + Math.pow(APCA.blkThrs - Yt, APCA.blkClmp);
  Yb = Yb > APCA.blkThrs ? Yb : Yb + Math.pow(APCA.blkThrs - Yb, APCA.blkClmp);
  if (Math.abs(Yb - Yt) < APCA.deltaYmin) return 0;
  let S;
  if (Yb > Yt) {                                   // dark text on light
    S = (Math.pow(Yb, APCA.normBG) - Math.pow(Yt, APCA.normTXT)) * APCA.scale;
    return (S < APCA.loOffset ? 0 : S - APCA.loOffset) * 100;
  }
  S = (Math.pow(Yb, APCA.revBG) - Math.pow(Yt, APCA.revTXT)) * APCA.scale;   // light text on dark
  return (S > -APCA.loOffset ? 0 : S + APCA.loOffset) * 100;
}

export function visual() {
  const m = document.querySelector('main') || document.body;
  const vis = el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
  const texts = [...m.querySelectorAll('*')].filter(el =>
    el.childElementCount === 0 && vis(el) && (el.textContent || '').trim().length > 1);

  const rows = texts.slice(0, 400).map(el => {
    const cs = getComputedStyle(el);
    const fg = _parseRGBA(cs.color) || { r: 0, g: 0, b: 0, a: 1 };
    const bg = _effectiveBg(el);
    const composited = fg.a < 1 ? _overlay(fg, bg) : fg;   // translucent TEXT composites too
    const px = parseFloat(cs.fontSize) || 16;
    const w = parseInt(cs.fontWeight, 10) || 400;
    const Lc = Math.abs(_apcaLc(composited, bg));
    // APCA bronze-ish floors: large/bold text may sit lower than body copy
    const floor = (px >= 24 || (px >= 18.66 && w >= 700)) ? 45 : (px < 14 ? 75 : 60);
    return { txt: (el.textContent || '').trim().slice(0, 32), px: Math.round(px), w,
             Lc: Math.round(Lc * 10) / 10, floor,
             ok: bg.inconclusive ? null : Lc >= floor,
             inconclusive: !!bg.inconclusive,
             fg: cs.color, bg: 'rgb(' + [bg.r, bg.g, bg.b].map(Math.round).join(',') + ')' };
  });
  const fails = rows.filter(r => r.ok === false).sort((a, b) => a.Lc - b.Lc);
  const unknown = rows.filter(r => r.inconclusive);

  // REDUCED MOTION: does anything actually animate, and is the opt-out expressed?
  const animated = [...document.querySelectorAll('*')].filter(el => {
    const cs = getComputedStyle(el);
    return vis(el) && ((cs.animationName && cs.animationName !== 'none') ||
                       (cs.transitionDuration && parseFloat(cs.transitionDuration) > 0));
  });
  let declaresGuard = false;
  for (const sheet of document.styleSheets) {
    let rules; try { rules = sheet.cssRules; } catch (e) { continue; }  // empty-catch-allow: cross-origin sheet
    for (const r of rules || []) {
      if (r.media && /prefers-reduced-motion/.test(r.conditionText || r.media.mediaText || '')) { declaresGuard = true; break; }
    }
    if (declaresGuard) break;
  }
  return {
    apca: {
      measured: rows.length,
      failing: fails.length,
      inconclusive: unknown.length,
      ok: unknown.length ? null : fails.length === 0,
      worst: fails.slice(0, 10),
      unmeasurable: unknown.slice(0, 4).map(u => u.txt),
    },
    reduced_motion: {
      animatedElements: animated.length,
      declaresGuard,
      ok: animated.length === 0 ? null : declaresGuard,
      note: animated.length === 0 ? 'nothing animates on this surface - nothing to honour'
                                  : (declaresGuard ? null : 'elements animate and no @media (prefers-reduced-motion) rule exists'),
      matchesNow: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    },
  };
}

// ── F3 · BG-ui-state ─────────────────────────────────────────────────────────────────────────
// The six states per COMPONENT, not per page. Four of them cannot be seen on a settled page at all
// -- loading, skeleton and busy only exist while something is in flight, and a disabled control only
// proves itself when you try to use it -- so they are INDUCED here rather than looked for.
//
// The disabled check is deliberately NOT a forced click. Playwright's force:true dispatches the event
// past the very guard under test, which is how a disabled control once "passed" a probe it does not
// actually survive. A real click on a real disabled button is a no-op, and that is the assertion.
export async function states(opts) {
  const wait = (opts && opts.settle) || 1500;
  const orig = window.__lsrFetch || window.fetch;
  window.__lsrFetch = orig;
  const out = {};
  const m = () => document.querySelector('main') || document.body;
  const vis = el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';

  // POPULATED — every field it promises, and none of the four strings that mean a bug reached the eye
  {
    const t = (m().innerText || '');
    const junk = t.match(/\bundefined\b|\bNaN\b|\[object Object\]/g) || [];
    out.component_populated = { ok: junk.length === 0 && t.length > 120, junk, len: t.length };
  }

  // LOADING + SKELETON — hold every read open, then look at what the page shows while it waits. The
  // response is DELAYED, not failed: a rejected promise leaves a stuck skeleton and proves something
  // else entirely (the same rule the failure states inherit).
  let heightsBefore = null;
  {
    // A BOUNDED DELAY, NOT AN OPEN HOLD. The first version parked every REST response in a promise
    // that only resolved after the sample -- and then awaited the page's loaders, which await those
    // same responses. That deadlocks: the release code sits after the await that can never finish,
    // and the probe hung for half an hour before the harness killed it. A delay gives the same
    // in-flight window to look at and always drains itself. The loaders are also fired WITHOUT being
    // awaited here, for the same reason: this state is about what the page shows WHILE it waits.
    const HOLD = 1100;
    window.fetch = (i, x) => {
      const u = typeof i === 'string' ? i : (i && i.url) || '';
      const method = ((x && x.method) || (i && i.method) || 'GET');
      if (!REST.test(u)) return orig(i, x);
      // same rule as the busy check: a mutating verb is answered, never forwarded. The loaders this
      // re-runs are reads, but "should only be reads" is an assumption and the cost of being wrong
      // is a write to the shared database.
      if (/^(POST|PATCH|PUT|DELETE)$/i.test(method)) {
        return new Promise(res => setTimeout(() => res(
          new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } })), HOLD));
      }
      return new Promise(res => setTimeout(() => res(orig(i, x)), HOLD));
    };
    document.dispatchEvent(new Event('DOMContentLoaded'));
    for (const k of LOADERS) {
      // deliberately NOT awaited: we sample mid-flight, and a throw must not stop the others
      if (typeof window[k] === 'function') { try { window[k](); } catch (e) { /* empty-catch-allow: see above */ } }
    }
    await new Promise(r => setTimeout(r, Math.floor(HOLD / 2)));   // sample INSIDE the flight
    const s = m();
    const skel = [...s.querySelectorAll('[class*="skeleton"],[id*="skeleton"],.shimmer,[aria-busy="true"]')].filter(vis);
    const txt = (s.innerText || '');
    heightsBefore = skel.map(e => Math.round(e.getBoundingClientRect().height));
    // "loading" must be distinguishable from "empty": an invite to act is what an EMPTY surface says,
    // and a surface that is merely waiting must not say it
    out.component_loading = {
      ok: skel.length > 0 || /loading|loadingâ€¦|…/i.test(txt) || /\bloading\b/i.test(txt),
      skeletonNodes: skel.length,
      saysLoading: /\bloading\b/i.test(txt),
      looksEmptyInstead: INVITE.test(txt),
      distinguishableFromEmpty: !(INVITE.test(txt) && skel.length === 0),
    };
    out.component_skeleton = {
      ok: skel.length === 0 ? null : heightsBefore.every(h => h > 0),
      reservedHeights: heightsBefore,
      note: skel.length === 0 ? 'no skeleton component on this surface - nothing to reserve space, recorded rather than passed' : null,
    };
    await new Promise(r => setTimeout(r, HOLD + wait));   // let the delayed reads land and settle
  }

  // DISABLED — looks disabled AND refuses activation. Both, not either.
  {
    const dis = [...document.querySelectorAll('button[disabled],[aria-disabled="true"],input[disabled],select[disabled]')].filter(vis);
    const checked = dis.slice(0, 6).map(el => {
      const cs = getComputedStyle(el);
      const looks = Number(cs.opacity) < 0.9 || /not-allowed/.test(cs.cursor) || cs.pointerEvents === 'none';
      let fired = false;
      const mark = () => { fired = true; };
      el.addEventListener('click', mark, { once: true });
      el.click();                       // a REAL click, never force:true
      el.removeEventListener('click', mark);
      return { el: (el.tagName + (el.id ? '#' + el.id : '')).slice(0, 36),
               looksDisabled: looks, refusedActivation: !fired, opacity: cs.opacity, cursor: cs.cursor };
    });
    out.component_disabled = {
      ok: checked.length === 0 ? null : checked.every(c => c.looksDisabled && c.refusedActivation),
      found: dis.length, checked,
      note: dis.length === 0 ? 'no disabled control in this state - recorded rather than passed' : null,
    };
  }

  // BUSY — an in-flight control must be busy and must not re-fire. Held open so the flight is real.
  {
    // A SUBMIT, not anything whose label happens to contain a verb. The first version matched
    // /search/i and picked the "Searches" TAB -- a nav control that fires no write, cannot go busy,
    // and therefore failed the check by construction. Require a real submit or a form-owned button,
    // and exclude the tab/nav families explicitly.
    const btn = [...document.querySelectorAll('button')].filter(vis).find(b =>
      !b.disabled &&
      !b.closest('[role="tablist"], nav, .section-tabs, .wh-hub-panel') &&
      !/tab-btn|wh-hub|section-tab/.test(b.className || '') &&
      // `button.type` reflects "submit" by DEFAULT on almost every button, form or not, so testing
      // it alone matched everything and picked whichever button happened to come first (the
      // Watchlist trust-bar control). The button has to actually belong to a form, or say plainly
      // that it commits something.
      ((b.type === 'submit' && b.closest('form')) ||
       // decision controls count too: the admin queues commit money with "Verify: mint credits" /
       // "Approve" / "Reject", which no submit-shaped test would ever find. Safe to press only
       // because the mutating verbs above are answered and never forwarded -- this list must not
       // grow beyond what that guard covers.
       /^(save|file|submit|post|send|hail|confirm|top.?up|verify|approve|reject|decide)\b/i
         .test((b.textContent || '').trim())));
    if (!btn) {
      out.component_busy = { ok: null, note: 'no in-flight-capable control on this surface' };
    } else {
      // THE WRITE MUST NEVER LAND. This check CLICKS a real commit control, and the first version
      // only DELAYED the request before forwarding it -- so on marketplace-seller.html it pressed
      // Save and the profile row's updated_at actually moved. A probe that mutates the shared
      // database is the one thing this bank is not allowed to do, and "it was only a timestamp" is
      // not the standard. Mutating verbs are now answered synthetically and NEVER forwarded; reads
      // are merely delayed, which is all the in-flight window needs.
      const HOLD = 1100;
      const MUTATING = /^(POST|PATCH|PUT|DELETE)$/i;
      const blocked = [];
      window.fetch = (i, x) => {
        const u = typeof i === 'string' ? i : (i && i.url) || '';
        const method = ((x && x.method) || (i && i.method) || 'GET');
        if (!REST.test(u)) return orig(i, x);
        if (MUTATING.test(method)) {
          blocked.push(method + ' ' + u.split('/rest/v1/')[1]);
          return new Promise(res => setTimeout(() => res(
            new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } })), HOLD));
        }
        return new Promise(res => setTimeout(() => res(orig(i, x)), HOLD));
      };
      out._writesBlocked = blocked;
      btn.click();
      await new Promise(r => setTimeout(r, 450));          // sample INSIDE the flight
      const cs = getComputedStyle(btn);
      out.component_busy = {
        ok: btn.disabled || btn.getAttribute('aria-busy') === 'true' || cs.pointerEvents === 'none',
        control: (btn.textContent || '').trim().slice(0, 28),
        disabledInFlight: btn.disabled,
        ariaBusy: btn.getAttribute('aria-busy'),
        pointerEvents: cs.pointerEvents,
      };
      await new Promise(r => setTimeout(r, HOLD + wait));
    }
  }

  window.fetch = orig;
  return out;
}

// ── F4 · BI-ux-comprehension ─────────────────────────────────────────────────────────────────
// "Can a person say what this number means, what happens next, and what it costs?"
//
// This lens cannot be fully mechanised and is not pretended to be: the probe COLLECTS the evidence
// (every number with whatever text is within reach of it, the cost language before a commit, the
// refusal sentences) and a human judgement is made on what it returns. What the probe does decide
// is the one thing it can: whether a number has ANY explanation reachable at all. A number with no
// label, no heading, no aria-label and no title is unreadable by construction, and that is the
// class the vanished credits chip belonged to -- the value was right and the meaning was missing.
export function comprehension() {
  const m = document.querySelector('main') || document.body;
  const vis = el => (el.offsetParent || el.getClientRects().length);
  const NUM = /^[₱$]?\s*-?[\d,]+(\.\d+)?\s*(%|x|hrs?|days?|km)?$/i;

  // A number is EXPLAINED if something within reach names it: its own aria-label/title, a sibling
  // label, its container's label element, or a heading above it. "Within reach" is deliberately
  // generous -- the aim is to find numbers nothing explains, not to grade prose.
  const numbers = [...m.querySelectorAll('*')].filter(el =>
    el.childElementCount === 0 && vis(el) && NUM.test((el.textContent || '').trim()) &&
    (el.textContent || '').trim().length > 0
  ).slice(0, 40).map(el => {
    const own = (el.getAttribute('aria-label') || '') + ' ' + (el.getAttribute('title') || '');
    const par = el.parentElement;
    const near = par ? (par.innerText || '').replace(/\s+/g, ' ').trim() : '';
    const labelEl = par ? par.querySelector('.sc-label, .ac-label, label, .mod-sub, .sc-sub, dt') : null;
    const grandNear = par && par.parentElement ? (par.parentElement.innerText || '').replace(/\s+/g, ' ').trim() : '';
    const value = (el.textContent || '').trim();
    // the explanation is whatever text sits with it, minus the number itself
    const context = (own + ' ' + (labelEl ? labelEl.innerText : '') + ' ' +
                     near.replace(value, '') + ' ' + grandNear.replace(value, '')).replace(/\s+/g, ' ').trim();
    return { value, explainedBy: context.slice(0, 90), explained: context.length > 2 };
  });

  const body = (m.innerText || '').replace(/\s+/g, ' ');
  const commit = [...m.querySelectorAll('button, [type=submit]')].filter(vis)
    .map(b => (b.textContent || '').trim())
    .filter(t => /buy|book|hire|hail|post|file|submit|confirm|pay|send|save|top.?up/i.test(t));

  return {
    numbersFound: numbers.length,
    unexplained: numbers.filter(n => !n.explained),
    unexplainedCount: numbers.filter(n => !n.explained).length,
    // what does it cost -- stated BEFORE the commitment, not after
    cost: {
      commitControls: commit.slice(0, 8),
      statesFee:    /\b(fee|commission|charge|cost)\b/i.test(body),
      statesFree:   /\bno fees?\b|\bfree\b/i.test(body),
      statesReward: /credits back|credits? when|reward/i.test(body),
      statesHold:   /\bhold\b|\breserved?\b|\bescrow\b/i.test(body),
    },
    // what happens next -- after an action, the surface says what and when
    next: {
      saysWhatNext: /(what to do next|next step|we.ll|you.ll (get|receive|hear)|within \d|once (you|the)|after)/i.test(body),
      hasActionCard: !!m.querySelector('.action-card, #mk-action-text, .ac-text'),
      actionText: (m.querySelector('#mk-action-text, .ac-text') || {}).innerText || null,
    },
    // why refused -- a refusal must name the rule AND a way out that can actually work
    refusals: [...m.querySelectorAll('[role=alert], .error, .refusal, .wh-error, .form-error')]
      .filter(vis).map(e => (e.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean).slice(0, 6),
  };
}

// ── F3 · BF-ui-layout ────────────────────────────────────────────────────────────────────────
// The width is set by the MCP (JS cannot resize the window) and then DISBELIEVED: browser_resize
// reports the width it was asked for, and a request for 390 has landed as 585 here before now
// (device pixel ratio). So every verdict carries the width it was actually measured at, and a walk
// whose `verifiedWidth` is not within tolerance of the target is not evidence for that target.
//
// Three offender lists rather than three counts. A count says a page is wrong; a list says which
// element, which is the difference between a banked row and a fix.
export function layout(target) {
  const m = document.querySelector('main') || document.body;
  const vis = el => (el.offsetParent || el.getClientRects().length) &&
                    getComputedStyle(el).visibility !== 'hidden';
  const name = el => (el.tagName.toLowerCase() +
    (el.id ? '#' + el.id : '') +
    (el.className && typeof el.className === 'string'
      ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '')).slice(0, 60);

  // OVERFLOW. An element that scrolls ON PURPOSE (overflow-x auto/scroll) is not an offender — the
  // marketplace tab strip is deliberately swipeable. A collapsed <details> reports its expanded
  // scrollWidth and is excluded for the same reason it was excluded upstream: it is not on screen.
  const offenders = [...m.querySelectorAll('*')].filter(el =>
    el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0 &&
    getComputedStyle(el).overflowX === 'visible' &&
    !el.closest('details:not([open])') && vis(el)
  ).map(el => ({ el: name(el), content: el.scrollWidth, box: el.clientWidth,
                 by: el.scrollWidth - el.clientWidth }))
   .sort((a, b) => b.by - a.by).slice(0, 8);

  // SIDEWAYS SCROLL. documentElement.clientWidth already excludes the vertical scrollbar gutter, so
  // this difference is real horizontal overflow — but a fractional device pixel ratio rounds, and a
  // 1px reading is that rounding rather than a defect. Tolerate 1, report the number either way.
  const docBy = document.documentElement.scrollWidth - document.documentElement.clientWidth;

  // TAP TARGETS, measured by RECT and not by stylesheet intent: a 44px min-height loses to a flex
  // parent that squeezes it. Links sitting inside a sentence are excluded — an inline citation is
  // not a thumb target, and counting it buries the controls that are.
  const inProse = el => !!el.closest('p, li, .wh-prose, .prose') &&
                        getComputedStyle(el).display.includes('inline');
  const small = [...m.querySelectorAll('button, a[href], input:not([type=hidden]), select, textarea, [role="button"], [onclick]')]
    .filter(el => vis(el) && !inProse(el))
    .map(el => { const r = el.getBoundingClientRect();
                 return { el: name(el), w: Math.round(r.width), h: Math.round(r.height),
                          txt: (el.textContent || '').trim().slice(0, 24) }; })
    .filter(r => (r.w > 0 && r.h > 0) && (r.w < 44 || r.h < 44))
    .sort((a, b) => (a.w * a.h) - (b.w * b.h)).slice(0, 12);

  // SAFE AREA. Fixed bottom chrome on a notched phone must clear the home indicator. The honest
  // check is whether the rule is EXPRESSED — env(safe-area-inset-bottom) resolves to 0 on this
  // desktop browser, so a measured gap of 0 here proves nothing either way.
  const bottomFixed = [...document.querySelectorAll('*')].filter(el => {
    const cs = getComputedStyle(el);
    if (cs.position !== 'fixed' || !vis(el)) return false;
    const r = el.getBoundingClientRect();
    return r.bottom >= window.innerHeight - 4 && r.height > 0 && r.height < window.innerHeight / 2;
  }).map(el => {
    const cs = getComputedStyle(el);
    // getComputedStyle RESOLVES env(), and on a desktop browser it resolves to 0 — so a sheet that
    // clears the home indicator and one that does not both compute to the same 32px. The only place
    // the difference survives is the UNRESOLVED declaration, so read the stylesheet rules that match
    // this element. Checking inline style alone reported marketplace.html's .sheet and its seller
    // twin as identical when one had env() and the other did not; the buyer's sheet was in fact
    // putting "Save Search" under the indicator. Ask the CSSOM, not the computed value.
    let declaresSafeArea = /safe-area-inset-bottom/.test(el.style.cssText || '');
    if (!declaresSafeArea) {
      for (const sheet of document.styleSheets) {
        let rules;
        // empty-catch-allow: a cross-origin stylesheet throws on .cssRules. Skipping it is correct —
        // the platform's own rules are same-origin, and a font CDN has no bottom chrome.
        try { rules = sheet.cssRules; } catch (e) { continue; }
        for (const r of rules || []) {
          if (!r.selectorText || !r.cssText.includes('safe-area-inset-bottom')) continue;
          // empty-catch-allow: an exotic selector can throw in matches(); it is not our rule.
          try { if (el.matches(r.selectorText)) { declaresSafeArea = true; } } catch (e) { continue; }
          if (declaresSafeArea) break;
        }
        if (declaresSafeArea) break;
      }
    }
    return { el: name(el), padBottom: cs.paddingBottom, declaresSafeArea };
  });

  const verifiedWidth = window.innerWidth;
  const onTarget = target == null ? true : Math.abs(verifiedWidth - target) <= 12;
  return {
    requested: target ?? null,
    verifiedWidth, dpr: window.devicePixelRatio, onTarget,
    docScrollsSideways: docBy > 1, docBy,
    overflowCount: offenders.length, offenders,
    tapTargetsUnder44: small.length, small,
    bottomFixed,
    ok: onTarget && docBy <= 1 && offenders.length === 0,
  };
}
