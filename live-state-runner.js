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
