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
      note: 'structural half only — number-vs-source-of-truth is checked by the psql-backed rows',
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
    const u = typeof i === 'string' ? i : (i && i.url) || '';
    const r = await orig(i, x);
    if (!REST.test(u)) return r;
    let b; try { b = await r.clone().json(); } catch (e) { return r; }
    if (Array.isArray(b) && b.length) b.slice(0, 3).forEach(mapper);
    return new Response(JSON.stringify(b), { status: 200, headers: { 'Content-Type': 'application/json' } });
  });
  mutate(row => {
    for (const k of Object.keys(row)) {
      if (/name|title|label|scope|desc/i.test(k) && typeof row[k] === 'string') row[k] = LONG;
      if (/price|amount|budget|rate|fee|cost/i.test(k) && typeof row[k] === 'number') row[k] = 0;
    }
  });
  await rerun();
  {
    const s = read();
    out.edge = { ok: s.doc <= 0 && s.over === 0, docOverflow: s.doc, unclipped: s.over,
                 longNameRendered: /Southern Tagalog/.test(s.t), atWidth: s.innerWidth };
  }

  // SCRIPT_NAME — a real Philippine script, not lorem
  mutate(row => { for (const k of Object.keys(row)) {
    if (/name|title|label/i.test(k) && typeof row[k] === 'string') row[k] = BAYBAYIN; } });
  await rerun();
  {
    const s = read();
    const rendered = /[ᜀ-ᜟ]/.test(s.t);
    out.script_name = { ok: s.doc <= 0, baybayinRendered: rendered, docOverflow: s.doc };
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
