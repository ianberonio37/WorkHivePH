// prove_component_states_scoped.mjs — CK ui-state, measured PER COMPONENT instead of per page.
//
// WHY THIS EXISTS. `prove_component_states.mjs` answers "did THIS PAGE show a loading state and did it
// resolve?" — one reading per page. But CK asks its five questions of THREE named components (C1/C2/C3),
// so banking that single reading against all three subjects records one measurement as three, which is
// the exact error that put V1's failure-injection verdicts onto 14 V2 rows earlier in this arc
// ([[feedback_one_measurement_swept_two_views]]). A subject that was never separately observed has not
// been proven, however green the page looks.
//
// THE BLOCKER WAS SELECTION, NOT MEASUREMENT. A component cannot be measured until it can be selected,
// and the bank's own subject.seen refs carry a real CSS selector for only 39 of 66 — the rest are prose
// ("hive_members read", "grid render"). `page_component_selectors.json` is the missing structure: every
// component's live-resolved selector, discovered by loading all 22 pages signed-in, then verified to
// resolve (66/66) before being trusted.
//
// ★THE HARD PART IS NOT "IS THERE A SKELETON", IT IS "SHOULD THERE BE ONE".
// A component with no skeleton is a DEFECT if a person waits on it, and NOTHING AT ALL if it is static
// furniture — and treating the second as the first fabricates defects on every page with a static header.
// Guessing from the selector name would be exactly the desk-written assumption this arc keeps catching.
// So the distinction is MEASURED: each component's text is sampled at first paint and again at settle.
//   grew   -> it is fed by an async read, a person waited on it, and a wait state is owed.
//   same   -> it was complete at first paint; there is no wait to describe, and the row is declared-na
//             WITH that reason rather than passed (vacuity) or failed (a fabricated defect).
// That is the same "an absence is only a defect where a subject exists" rule the fail_slow triage used
// when three dialogs turned out to issue no read on open.
//
// ARMED AT document_start, ON documentElement. The recorder installs via addInitScript before any page
// script runs, because arming at 'interactive' loses the first ~650ms and banks "no loading state" for a
// component whose skeleton came and went before the observer existed
// ([[feedback_arming_on_documentelement_lost_the_first_650ms]]).
//
// CONTROL PROBE. A detector that silently stops detecting reports a clean sweep, so a synthetic skeleton
// is planted inside a known container and must be caught; if it is not, the run refuses to report.
//
// Usage:
//   node tools/prove_component_states_scoped.mjs                 # all pages
//   node tools/prove_component_states_scoped.mjs --page hive     # one page
//   node tools/prove_component_states_scoped.mjs --selftest      # teeth, both directions
import { chromium } from 'playwright';
import { readFileSync, writeFileSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
const _MAPFILE = JSON.parse(readFileSync('page_component_selectors.json', 'utf8'));
const MAP = _MAPFILE.pages;
// A PARAMLESS WALK IS A DIFFERENT PAGE. project-report returns early with no ?project_id, so a walk
// without it grades an empty shell and every component reads as absent.
const URLS = _MAPFILE._urls || {};

// The recorder. Attributes every transient state to the component that CONTAINS it, so a skeleton in the
// feed is never credited to the header sitting beside it.
const RECORDER = (comps) => {
  window.__whCK = { comps: {}, armedAt: Math.round(performance.now()), domReadyAt: null };
  document.addEventListener('DOMContentLoaded',
    () => { window.__whCK.domReadyAt = performance.now(); }, { once: true });
  for (const k of Object.keys(comps)) {
    window.__whCK.comps[k] = { skel: 0, busy: 0, disabled: 0, skelIds: [], firstText: null, lastAt: 0,
                               sawLoadingWord: false, loadingQuote: null,
                               heightAtSkel: null, heightLast: 0,
                               ticks: 0, firstSeenTick: null, firstSeenAt: null, seenAfterDom: null };
  }
  const EXPLICIT = /skeleton|shimmer|placeholder-glow|wh-skel/i;
  const PULSE = /animate-pulse/i;
  const isSkel = (e) => {
    const c = String(e.className || '');
    if (EXPLICIT.test(c)) return true;
    if (!PULSE.test(c)) return false;
    const b = e.getBoundingClientRect ? e.getBoundingClientRect() : { width: 0, height: 0 };
    return b.width >= 24 && b.height >= 24;   // a pulsing dot is a status light, not a placeholder
  };
  // Which component owns this node? Containment, not proximity.
  const owner = (e) => {
    for (const [k, v] of Object.entries(comps)) {
      try {
        if (e.closest && e.closest(v.sel)) return k;
        for (const host of document.querySelectorAll(v.sel)) if (host.contains(e)) return k;
      } catch (_) { /* a bad selector must not kill the observer */ }
    }
    return null;
  };
  // ★REGIONAL ATTRIBUTION, RESOLVED AFTER THE FACT. Containment alone cannot see the wait state that
  // matters most: a component whose selector matches the CONTENT (.oh-tile-num, a table row) does not exist
  // until it is populated, so its placeholder necessarily lives in an ANCESTOR and is attributed to nobody.
  // Scoped that way, three KPI tiles that appear late read as "no loading state" on a page that plainly has
  // four skeletons — the same shape as a lens that measured 3% of the page and a stuck skeleton no gate
  // could see. So every transient state is ALSO recorded with its ancestor id-chain, and after the run each
  // component asks: did any of them happen in a region that CONTAINS me? A person waits on the card, not on
  // the <span> inside it.
  const WAIT_WORD = /\b(loading|loading…|working|fetching|generating|calculating|rolling up|crunching|please wait)\b/i;
  const chainIds = (e) => {
    const out = []; let n = e;
    for (let i = 0; i < 10 && n && n !== document.documentElement; i++) {
      if (n.id) out.push(n.id);
      n = n.parentElement;
    }
    return out;
  };
  window.__whCK.regional = [];
  const regional = (e, kind, note) => {
    if (window.__whCK.regional.length >= 400) return;
    const ids = chainIds(e);
    if (!ids.length) return;                       // nothing to anchor the region to
    window.__whCK.regional.push({ ids, kind, note: String(note || '').slice(0, 40),
                                  at: Math.round(performance.now()) });
  };
  const one = (e) => {
    if (!e || e.nodeType !== 1) return;
    const skel = isSkel(e);
    const busy = e.getAttribute && e.getAttribute('aria-busy') === 'true';
    // A wait SENTENCE counts as a wait state — checked on short text only, so a paragraph that merely
    // contains the word "loading" is not mistaken for a spinner.
    const own = (e.textContent || '').trim();
    const word = own.length > 0 && own.length <= 80 && WAIT_WORD.test(own);
    if (skel) regional(e, 'skeleton', e.id || String(e.className).slice(0, 28));
    if (busy) regional(e, 'aria-busy', e.id || String(e.className).slice(0, 28));
    if (word) regional(e, 'wait-word', own.slice(0, 40));
    const k = owner(e);
    if (!k) return;
    const S = window.__whCK.comps[k];
    if (skel) {
      S.skel++; S.lastAt = Math.round(performance.now());
      if (S.skelIds.length < 6) S.skelIds.push(e.id || String(e.className).slice(0, 28));
    }
    if (busy) S.busy++;
    if (e.disabled === true) S.disabled++;
  };
  const scan = (root) => { one(root); if (root.querySelectorAll) for (const e of root.querySelectorAll('*')) one(e); };
  const mo = new MutationObserver((muts) => {
    for (const m of muts) { for (const n of m.addedNodes) scan(n); if (m.type === 'attributes') one(m.target); }
  });
  const start = () => {
    mo.observe(document.documentElement, {
      childList: true, subtree: true, attributes: true,
      attributeFilter: ['class', 'aria-busy', 'disabled'],
    });
    // FIRST-PAINT SAMPLE. Taken as early as the element exists, because "did it grow?" is the whole
    // basis for deciding whether a wait state was owed.
    // ★A WAIT STATE IS OFTEN JUST A SENTENCE, AND A DETECTOR THAT ONLY KNOWS SKELETONS FABRICATES
    // DEFECTS. Counting only .skeleton/aria-busy reported 18 read-fed components as having no
    // distinguishable loading state — and they are the verdict hero cards, which say "Rolling up alert
    // state…" in words. That is the same shape as pm-scheduler's <div id="dash-loading">Loading
    // assets...</div>, where the signal was in the ID and the copy rather than a class. So the sampler
    // also watches for the platform's own in-flight WORDING, harvested from its rendered copy rather
    // than invented here. Anchored to short text so a paragraph merely containing "loading" cannot pass.
    const LOADING_RE = /loading|rolling up|checking|fetching|working on it|please wait|calculating|reading|analys|generating|thinking|…$|\.\.\.$/i;
    const sample = () => {
      for (const [k, v] of Object.entries(comps)) {
        const S = window.__whCK.comps[k];
        try {
          S.ticks++;
          const hosts = document.querySelectorAll(v.sel);
          // ★A ROW CREATED BY THE READ NEVER "GROWS" — IT ARRIVES. The growth test compares a component's
          // text at first paint against settle, which silently mis-reads every component that does not
          // EXIST until its data lands: the first sample that can see it already contains its final text,
          // so a read-created part row or post card reports as static furniture. Appearance is therefore
          // tracked separately, and appearing late is the STRONGEST evidence of being read-fed.
          // LATE IS MEASURED FROM DOMContentLoaded, NOT FROM document_start. Sampling arms before <body>
          // exists, so "was it absent at tick 1" is true of EVERY element on the page including static
          // markup mid-parse — a boundary that would have called all 66 components read-fed. The honest
          // line is the parsed document: anything in the static HTML is present by DOMContentLoaded, so a
          // component first seen AFTER it was created by something that ran later, i.e. a read.
          if (hosts.length && S.firstSeenTick === null) {
            S.firstSeenTick = S.ticks;
            S.firstSeenAt = performance.now();
            // A GRACE WINDOW, because a bare readyState check is too coarse at a 60ms cadence. Sampling
            // arms at document_start, and a large page can finish parsing between two ticks — so a div
            // that genuinely ships in the markup (index.html:987 #scroll-progress) is first SEEN once
            // readyState already says 'interactive', and a bare check calls static furniture read-fed.
            // Read-created content arrives after a network round-trip, hundreds of ms later, so 150ms
            // past DOMContentLoaded separates the two cleanly without needing the HTML source.
            const dr = window.__whCK.domReadyAt;
            S.seenAfterDom = (dr !== null) && (S.firstSeenAt > dr + 150);
          }
          if (!hosts.length) continue;
          let t = 0, txt = '';
          for (const h of hosts) { const s = (h.textContent || '').trim(); t += s.length; txt += ' ' + s; }
          txt = txt.replace(/\s+/g, ' ').trim();
          if (S.firstText === null) S.firstText = t;
          // ── component_skeleton: "the skeleton reserves the space the content will take, so nothing
          // jumps." That is a GEOMETRY claim, not a "does a skeleton exist" claim, so it is measured as
          // geometry: the component's height WHILE a placeholder is showing, against its height once the
          // content has landed. A skeleton that reserves nothing is not a skeleton doing its job — it is
          // a shimmer that still lets the page jump under someone's thumb.
          let h = 0;
          for (const hh of hosts) { const r = hh.getBoundingClientRect(); h += r.height; }
          if (S.skel > 0 && S.heightAtSkel === null) S.heightAtSkel = Math.round(h);
          S.heightLast = Math.round(h);
          // Sampled on EVERY tick, not only the first: the loading sentence is transient by definition,
          // and a first-paint-only sample misses one that appears at 200ms and clears at 900ms.
          if (!S.sawLoadingWord && txt.length < 400 && LOADING_RE.test(txt)) {
            S.sawLoadingWord = true;
            S.loadingQuote = txt.slice(0, 90);
          }
        } catch (_) { /* ignore */ }
      }
    };
    // ★SWEEP WHAT IS ALREADY THERE. The observer only reports FUTURE mutations, so every node inserted
    // before arming is invisible forever — and arming is not always at document_start: when
    // document.documentElement is not yet present the fallback below waits for readystatechange, which
    // first fires at 'interactive', i.e. DOMContentLoaded. project-report paints its wait state at ~258ms
    // and had it gone by settle; a poller saw 4 such elements, this recorder saw none, and the component
    // read "no loading state" — a FALSE DEFECT on a page that behaves correctly. An observer with no
    // initial sweep cannot distinguish "nothing happened" from "it happened before I looked", which is the
    // same shape as arming at 'interactive' and losing the first 650ms.
    scan(document.documentElement);
    sample();
    const iv = setInterval(sample, 60);
    setTimeout(() => clearInterval(iv), 3000);
  };
  if (document.documentElement) start();
  else document.addEventListener('readystatechange', start, { once: true });
};

const READ = (comps) => {
  const vis = (el) => {
    const s = getComputedStyle(el); const b = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0.01 && b.width > 0 && b.height > 0;
  };
  const EXPLICIT = /skeleton|shimmer|placeholder-glow|wh-skel/i;
  const out = {};
  for (const [k, v] of Object.entries(comps)) {
    const S = (window.__whCK && window.__whCK.comps[k])
      || { skel: 0, busy: 0, disabled: 0, skelIds: [], firstText: null, sawLoadingWord: false,
           loadingQuote: null, heightAtSkel: null, heightLast: 0, ticks: 0, firstSeenTick: null,
           firstSeenAt: null, seenAfterDom: null };
    let hosts = [];
    try { hosts = [...document.querySelectorAll(v.sel)]; } catch (_) { hosts = []; }
    let finalText = 0;
    for (const h of hosts) finalText += ((h.textContent || '').trim()).length;
    const stuck = hosts.some((h) => [...h.querySelectorAll('*')]
      .some((e) => EXPLICIT.test(String(e.className || '')) && vis(e)));
    // ── component_populated: "renders every field it promises, with no undefined/NaN" ──────────────
    // Read the oracle's actual words, not the family name. This is a CONTENT claim, so it is checked by
    // reading the component's rendered text for the tokens a broken template leaks. Word-bounded and
    // case-exact for NaN: a naive /null/i matches "nullify" and the page's own copy, and a substring
    // hunt for "undefined" matches the word used legitimately in prose ("undefined risk"). Only a token
    // standing ALONE is evidence of a template hole.
    const holeRe = /(^|[\s>:,(\[])(undefined|NaN|\[object Object\])($|[\s<:,)\].])/;
    const nullRe = /(^|[\s>:,(\[])null($|[\s<:,)\].])/;
    let holes = [];
    for (const h of hosts) {
      const clone = h.cloneNode(true);
      clone.querySelectorAll('style,script,noscript,template').forEach((n) => n.remove());
      const t = (clone.textContent || '').replace(/\s+/g, ' ').trim();
      if (holeRe.test(t) || nullRe.test(t)) {
        const m = t.match(holeRe) || t.match(nullRe);
        const at = t.indexOf(m[2]);
        holes.push(t.slice(Math.max(0, at - 40), at + 40));
      }
    }
    // ── component_populated, the OTHER half: "renders EVERY FIELD IT PROMISES" ──────────────────────
    // The hole scan below only covers "no undefined/NaN". Banking green on that alone would be the
    // half-measured-oracle error - a label's own claim is that a value follows it, so a component that
    // prints "Due:" with nothing after it has failed the promise without ever leaking the word undefined.
    // A promise is detected structurally: a label element (class says label, or its text ends in a colon)
    // must be followed by a non-empty value in its own row - the next element sibling, or the remaining
    // text of its parent once the label's own text is removed. An em-dash or "n/a" COUNTS as a value: the
    // platform uses them deliberately to say "known to be absent", which is an answer, not a gap.
    const promises = [];
    for (const h of hosts) {
      const labels = [h, ...h.querySelectorAll('*')].filter((e) => {
        if (e.children.length) return false;
        const t = (e.textContent || '').trim();
        if (!t || t.length > 40) return false;
        return /label|-key|field-name/i.test(String(e.className || '')) || /:$/.test(t);
      });
      for (const L of labels.slice(0, 6)) {
        const own = (L.textContent || '').trim();
        // ★A FORM LABEL IS A PROMPT, NOT A PROMISE. "Quantity Used:" above an empty input is the form
        // working exactly as intended - the value is the PERSON'S to supply, and demanding the app fill
        // it would flag every blank form on the platform as a defect. Measured, not guessed: a label is
        // treated as a prompt when it is a <label>, when it points at a control via `for`, or when the
        // value position holds a form control. Only DISPLAY labels - where the app owes a rendered value -
        // carry a promise this oracle can judge.
        const forId = L.getAttribute && L.getAttribute('for');
        const isPrompt = L.tagName === 'LABEL' || !!forId
          || (L.parentElement && L.parentElement.querySelector('input,textarea,select,[contenteditable]'));
        // ★A LABEL INSIDE A CONTROL IS ITS NAME, NOT A PROMISE OF A VALUE. report-sender renders report
        // types as tappable chips built from {id:'pm_overdue', label:'PM Overdue'}, and .chip-label matched
        // the class rule - so the chip's own NAME was read as a field owing a value, and four perfectly
        // correct chips reported as unfilled. A control's text labels the control; nothing follows it.
        const inControl = L.closest && L.closest('button,a,[role="button"],[role="tab"],[role="option"],'
          + '[class*="chip"],[class*="btn"],[class*="pill"],[tabindex]');
        if (isPrompt || inControl) continue;
        let val = '';
        let sib = L.nextElementSibling;
        while (sib && !val) { val = (sib.textContent || '').trim(); sib = sib.nextElementSibling; }
        if (!val && L.parentElement) {
          val = ((L.parentElement.textContent || '').replace(own, '')).trim();
        }
        promises.push({ label: own.slice(0, 28), filled: val.length > 0 });
      }
    }

    // ── component_disabled: "a disabled control looks disabled AND refuses activation - both" ───────
    // BOTH HALVES, because either alone is a real bug shipped on real products: a control that refuses
    // but looks live gets tapped repeatedly in frustration, and one that looks dead but still fires is
    // the double-submit that bills someone twice.
    //
    // ★NON-ACTIVATING BY CONSTRUCTION. A probe that clicks live controls can PERFORM the thing it meant
    // to observe — that is exactly how a previous sweep hunting a refusal activated a SUCCESS and wrote
    // real rows. So: only elements ALREADY marked disabled are touched (a disabled control's whole claim
    // is that it does nothing), a capture-phase guard on document stops the event before it can reach any
    // application handler, and the click is dispatched as a non-trusted synthetic event. Nothing here can
    // submit, save, pay or delete.
    const dis = [];
    for (const h of hosts) {
      const cands = [h, ...h.querySelectorAll('*')].filter((e) =>
        (e.disabled === true) || e.getAttribute?.('aria-disabled') === 'true');
      for (const e of cands.slice(0, 4)) {
        const cs = getComputedStyle(e);
        // Looks disabled: the platform signals it by dimming, a not-allowed cursor, or muted colour.
        const looks = (+cs.opacity < 0.85) || /not-allowed|default/.test(cs.cursor)
          || cs.pointerEvents === 'none' || /disabled/i.test(String(e.className || ''));
        let fired = false;
        const guard = (ev) => { ev.stopPropagation(); ev.preventDefault(); };
        const spy = () => { fired = true; };
        document.addEventListener('click', guard, true);
        e.addEventListener('click', spy);
        try { e.click(); } catch (_) { /* a control that throws on click has certainly not activated */ }
        e.removeEventListener('click', spy);
        document.removeEventListener('click', guard, true);
        dis.push({ tag: e.tagName, looksDisabled: !!looks, activated: fired,
                   label: (e.textContent || '').trim().slice(0, 30) });
      }
    }

    // ── component_loading: "the loading state is distinguishable from its empty state" ──────────────
    // Distinguishable means a person can TELL THEM APART. A component that showed a placeholder or an
    // aria-busy while in flight is distinguishable; one that sat visually identical to empty is not.
    // Only meaningful where the component is actually read-fed, which `grew` establishes by measurement.
    // Read-fed = its text grew after paint, OR it did not exist at the first sample and does now.
    // firstSeenTick > 1 means the component was absent when sampling began and appeared afterwards.
    // Appeared late == first seen once the document had finished parsing.
    const appearedLate = S.seenAfterDom === true;
    // ★GROWTH MUST BE MATERIAL, NOT MERELY POSITIVE. A flat +8 char floor calls a server-rendered block
    // "read-fed" when a single detail inside it updates: #wh-logbook-grid holds 11,057 characters at +34ms
    // and ends at 11,136 — a 0.7% change — and on that basis the grid was told it owed a loading state and
    // failed for not having one. The two pulsing dots it does have are 8x8px STATUS LIGHTS, which this
    // recorder correctly refuses to count as placeholders. Nobody waits on a component that was already
    // there and complete. So the threshold stays absolute for a near-empty component, where +8 genuinely IS
    // the content arriving, and becomes proportional once there is substantial text to compare against.
    const growthFloor = Math.max(8, Math.round((S.firstText || 0) * 0.15));
    const grew = (S.firstText !== null && finalText > S.firstText + growthFloor) || appearedLate;
    out[k] = {
      sel: v.sel, on_load: v.on_load !== false, present: hosts.length,
      skel: S.skel, busy: S.busy, disabled: S.disabled, skelIds: S.skelIds,
      firstText: S.firstText, finalText, grew, stuck,
      appearedLate, firstSeenTick: S.firstSeenTick, seenAfterDom: S.seenAfterDom,
      sawLoadingWord: !!S.sawLoadingWord, loadingQuote: S.loadingQuote || null,
      heightAtSkel: S.heightAtSkel, heightFinal: (() => {
        let h = 0; for (const hh of hosts) h += hh.getBoundingClientRect().height; return Math.round(h);
      })(),
      // Reserved = the box the placeholder held is within 8px of the box the content ended up in.
      // 8px absorbs sub-pixel and one line-height rounding without excusing a real jump.
      reserved: S.heightAtSkel === null ? null
        : Math.abs(S.heightAtSkel - (() => { let h = 0; for (const hh of hosts) h += hh.getBoundingClientRect().height; return h; })()) <= 8,
      // REGIONAL FALLBACK, resolved here rather than at record time. A component's own subtree may hold no
      // wait state and the page may still have said "wait" where the person was looking — in the card that
      // CONTAINS this component. So if nothing was found inside, ask whether any recorded wait state
      // happened in a region enclosing this component's host, and say which one it was so the row can be
      // audited rather than trusted.
      regional: (() => {
        if (!hosts.length) return null;
        // depth 0 = the host itself, 1 = its nearest id-bearing ancestor, and so on. A wait state in the
        // component's own card is strong evidence; one anchored only at the page container is weak, and the
        // row must be able to tell them apart instead of both reading as "a skeleton exists".
        const depth = new Map();
        for (const h of hosts) {
          let n = h, d = 0;
          for (let i = 0; i < 10 && n && n !== document.documentElement; i++) {
            if (n.id && !depth.has(n.id)) depth.set(n.id, d);
            n = n.parentElement; d++;
          }
        }
        if (!depth.size) return null;
        let best = null;
        for (const r of (window.__whCK.regional || [])) {
          for (const id of r.ids) {
            if (!depth.has(id)) continue;
            const d = depth.get(id);
            if (!best || d < best.depth) best = { kind: r.kind, note: r.note, at: r.at, region: id, depth: d };
          }
        }
        return best;
      })(),
      distinguishable: grew ? (S.skel > 0 || S.busy > 0 || !!S.sawLoadingWord
        || !!(() => {
          if (!hosts.length) return false;
          const hostIds = new Set();
          for (const h of hosts) {
            let n = h;
            for (let i = 0; i < 10 && n && n !== document.documentElement; i++) { if (n.id) hostIds.add(n.id); n = n.parentElement; }
          }
          return (window.__whCK.regional || []).some((r) => r.ids.some((id) => hostIds.has(id)));
        })()) : null,
      disabledControls: dis,
      disabled_ok: dis.length ? dis.every((d) => d.looksDisabled && !d.activated) : null,
      holes: holes.slice(0, 3),
      promises, unfilledPromises: promises.filter((x) => !x.filled).map((x) => x.label).slice(0, 4),
      // BOTH halves of the oracle: no template holes AND every label's promised value present.
      // null (not false) when there is nothing to judge: no host, or no rendered text at all. A component
      // with zero text has not FAILED to populate its fields, it has no fields on screen to populate, and
      // reporting that as a violation manufactured three findings in the first run.
      populated_ok: (!hosts.length || finalText === 0) ? null
        : (holes.length === 0 && promises.every((x) => x.filled)),
    };
  }
  return out;
};

async function measure(ctx, page, comps) {
  await page.goto(`${ORIGIN}/${page.__name}.html${URLS[page.__name] || ''}`,
                  { waitUntil: 'domcontentloaded', timeout: 25000 });
  await page.waitForTimeout(5200);
  return page.evaluate(READ, comps);
}

if (args.includes('--selftest')) {
  // TEETH. A planted skeleton inside a known component must be ATTRIBUTED TO THAT COMPONENT and not to
  // its neighbour — attribution is the whole claim of this prover, so a run that cannot separate two
  // sibling components proves nothing about either.
  const b = await chromium.launch();
  const c = await b.newContext({ viewport: { width: 390, height: 844 } });
  const comps = { C1: { sel: '#wh-ck-a', on_load: true }, C2: { sel: '#scroll-progress', on_load: true } };
  await c.addInitScript(RECORDER, comps);
  // THE FIXTURE MUST EXIST BEFORE SAMPLING BEGINS, or the test is not testing what it claims. Planting
  // both divs with page.evaluate() AFTER goto made BOTH of them appear late, so the "static component is
  // not read-fed" assertion failed against a component that was static in every way except the one the
  // fixture controlled. Creating them at document_start makes the only difference between A and B the
  // difference under test: A gets a skeleton and late content, B gets neither.
  // THE STATIC COMPONENT IS A REAL ONE FROM THE PAGE, NOT A PLANTED DIV. "Appeared late" means first
  // seen after parsing finished, so any fixture I inject is late by construction — planting at
  // DOMContentLoaded fails the static assertion, and appending to <html> at document_start does not
  // survive the parser building <body>. #scroll-progress (index.html:987) genuinely ships in the parsed
  // markup and never changes, which is exactly the shape the static case is meant to represent. Only the
  // DYNAMIC half needs planting.
  await c.addInitScript(() => {
    const plant = () => {
      if (document.getElementById('wh-ck-a')) return;
      const d = document.createElement('div'); d.id = 'wh-ck-a';
      d.style.cssText = 'width:200px;height:60px;position:relative;z-index:99999';
      const s = document.createElement('div'); s.className = 'skeleton';
      s.style.cssText = 'width:120px;height:40px'; d.appendChild(s);
      document.body.appendChild(d);
      setTimeout(() => { d.textContent = 'now populated with real content here'; }, 300);
    };
    if (document.body) plant();
    else document.addEventListener('DOMContentLoaded', plant, { once: true });
  });
  const pg = await c.newPage();
  await pg.goto(`${ORIGIN}/index.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
  await pg.waitForTimeout(1500);
  const r = await pg.evaluate(READ, comps);
  let fail = 0;
  if (!(r.C1.skel > 0)) { console.log('  FAIL — planted skeleton not seen in its own component'); fail++; }
  else console.log(`  ok — skeleton attributed to C1 (${r.C1.skel})`);
  if (r.C2.skel > 0) { console.log('  FAIL — C1\'s skeleton leaked onto the sibling C2'); fail++; }
  else console.log('  ok — sibling C2 did NOT inherit C1\'s skeleton (attribution holds)');
  if (!r.C1.grew) { console.log('  FAIL — content that arrived after paint was not seen as growth'); fail++; }
  else console.log('  ok — late content detected as growth (so a wait state was genuinely owed)');
  if (r.C2.grew) { console.log('  FAIL — a static component was reported as read-fed'); fail++; }
  else console.log('  ok — static component NOT reported as read-fed (no fabricated obligation)');
  // component_populated teeth, both ways — a leak detector that never fires reports a clean sweep.
  await pg.evaluate(() => { document.getElementById('scroll-progress').textContent = 'Qty: undefined units'; });
  const r2 = await pg.evaluate(READ, comps);
  if (r2.C2.populated_ok || !r2.C2.holes.length) { console.log('  FAIL — a leaked "undefined" was not caught'); fail++; }
  else console.log(`  ok — template hole caught: "${r2.C2.holes[0].trim().slice(0, 40)}"`);
  await pg.evaluate(() => { document.getElementById('scroll-progress').textContent = 'Risk is undefined-ish nullify 5 NaNo'; });
  const r3 = await pg.evaluate(READ, comps);
  if (r3.C2.holes.length) { console.log(`  FAIL — prose false-positive: "${r3.C2.holes[0]}"`); fail++; }
  else console.log('  ok — "undefined-ish", "nullify", "NaNo" in prose do NOT count as holes');

  // ── component_skeleton teeth: a placeholder that RESERVES vs one that COLLAPSES ────────────────
  // Both directions, because "reserved" is the claim: a detector that always says yes would bless the
  // very jump this oracle exists to catch.
  const cs2 = { R: { sel: '#wh-ck-r', on_load: true }, J: { sel: '#wh-ck-j', on_load: true } };
  const c3 = await b.newContext({ viewport: { width: 390, height: 844 } });
  await c3.addInitScript(RECORDER, cs2);
  const pg2 = await c3.newPage();
  await pg2.goto(`${ORIGIN}/index.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
  await pg2.evaluate(() => {
    const mk = (id) => { const d = document.createElement('div'); d.id = id; document.body.appendChild(d); return d; };
    // R reserves: its skeleton is 100px and the content that replaces it is also ~100px.
    const R = mk('wh-ck-r');
    R.innerHTML = '<div class="skeleton" style="width:200px;height:100px"></div>';
    setTimeout(() => { R.innerHTML = '<div style="width:200px;height:100px">real content arrived here</div>'; }, 400);
    // J jumps: a 10px shimmer standing in for 140px of content.
    const J = mk('wh-ck-j');
    J.innerHTML = '<div class="skeleton" style="width:200px;height:10px"></div>';
    setTimeout(() => { J.innerHTML = '<div style="width:200px;height:140px">much taller real content</div>'; }, 400);
  });
  await pg2.waitForTimeout(1600);
  const rr = await pg2.evaluate(READ, cs2);
  if (rr.R.reserved !== true) { console.log(`  FAIL — a correctly-reserving skeleton was called a jump (${rr.R.heightAtSkel}->${rr.R.heightFinal})`); fail++; }
  else console.log(`  ok — reserving skeleton accepted (${rr.R.heightAtSkel}px -> ${rr.R.heightFinal}px)`);
  if (rr.J.reserved !== false) { console.log(`  FAIL — a 10px shimmer under 140px of content was called reserved (${rr.J.heightAtSkel}->${rr.J.heightFinal})`); fail++; }
  else console.log(`  ok — collapsing skeleton CAUGHT as a jump (${rr.J.heightAtSkel}px -> ${rr.J.heightFinal}px)`);
  await c3.close();

  // ── component_disabled teeth, both directions ─────────────────────────────────────────────────
  // A control that is genuinely disabled AND dimmed must pass; one that is aria-disabled, looks fully
  // live, and still runs its handler must be CAUGHT. Without the second plant the check would bless the
  // exact "looks dead but still fires" double-submit it exists to find.
  const cs3 = { OK: { sel: '#wh-ck-ok', on_load: true }, BAD: { sel: '#wh-ck-bad', on_load: true } };
  const c4 = await b.newContext({ viewport: { width: 390, height: 844 } });
  await c4.addInitScript(RECORDER, cs3);
  const pg3 = await c4.newPage();
  await pg3.goto(`${ORIGIN}/index.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
  await pg3.evaluate(() => {
    const wrap = (id) => { const d = document.createElement('div'); d.id = id; document.body.appendChild(d); return d; };
    const a = wrap('wh-ck-ok');
    const okBtn = document.createElement('button');
    okBtn.disabled = true; okBtn.textContent = 'Save';
    okBtn.style.cssText = 'opacity:0.4;cursor:not-allowed'; a.appendChild(okBtn);
    const z = wrap('wh-ck-bad');
    const badBtn = document.createElement('button');
    badBtn.setAttribute('aria-disabled', 'true');       // claims disabled...
    badBtn.textContent = 'Send'; badBtn.style.cssText = 'opacity:1;cursor:pointer';
    badBtn.addEventListener('click', () => { window.__whBadFired = true; });   // ...but still fires
    z.appendChild(badBtn);
  });
  await pg3.waitForTimeout(400);
  const rd = await pg3.evaluate(READ, cs3);
  if (rd.OK.disabled_ok !== true) { console.log(`  FAIL — a properly disabled+dimmed control was flagged (${JSON.stringify(rd.OK.disabledControls)})`); fail++; }
  else console.log('  ok — genuinely disabled control accepted (looks disabled, did not activate)');
  if (rd.BAD.disabled_ok !== false) { console.log(`  FAIL — a live control claiming aria-disabled was NOT caught (${JSON.stringify(rd.BAD.disabledControls)})`); fail++; }
  else console.log('  ok — "looks live and still fires" CAUGHT despite aria-disabled=true');
  await c4.close();

  // ── component_populated teeth: the PROMISED-FIELD half, both directions ────────────────────────
  // "No undefined leaked" and "every promised field is filled" are different claims, and a component can
  // pass the first while failing the second. A label with an empty value must be CAUGHT; a label whose
  // value is a deliberate em-dash must NOT be, because "—" is the platform saying "known to be absent",
  // which answers the promise rather than breaking it.
  const cs4 = { FILL: { sel: '#wh-ck-fill', on_load: true }, GAP: { sel: '#wh-ck-gap', on_load: true } };
  const c5 = await b.newContext({ viewport: { width: 390, height: 844 } });
  await c5.addInitScript(RECORDER, cs4);
  const pg4 = await c5.newPage();
  await pg4.goto(`${ORIGIN}/index.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
  await pg4.evaluate(() => {
    const mk = (id, html) => { const d = document.createElement('div'); d.id = id; d.innerHTML = html;
      document.body.appendChild(d); };
    mk('wh-ck-fill', '<div><span class="label">Due:</span><span>12 Aug</span></div>'
                   + '<div><span class="label">Owner:</span><span>&mdash;</span></div>');
    mk('wh-ck-gap',  '<div><span class="label">Due:</span><span></span></div>');
  });
  await pg4.waitForTimeout(400);
  const rp = await pg4.evaluate(READ, cs4);
  if (rp.FILL.populated_ok !== true) { console.log(`  FAIL — a fully-filled component was flagged (unfilled: ${JSON.stringify(rp.FILL.unfilledPromises)})`); fail++; }
  else console.log('  ok — filled component accepted, and a deliberate em-dash counts as an answer');
  if (rp.GAP.populated_ok !== false) { console.log('  FAIL — a label with an EMPTY value was not caught'); fail++; }
  else console.log(`  ok — unfilled promise CAUGHT: ${JSON.stringify(rp.GAP.unfilledPromises)}`);
  await c5.close();
  await b.close();
  console.log(fail ? `\n  SELFTEST FAILED (${fail})`
    : '\n  SELFTEST PASSED — states attribute to the right component, and read-fed is distinguished from static');
  process.exit(fail ? 1 : 0);
}

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
await assertSignedIn(signIn(ctx, 'supervisor'));
const pages = ONE ? [ONE] : Object.keys(MAP);
const report = { ran: new Date().toISOString(), origin: ORIGIN, pages: {} };
for (const p of pages) {
  const comps = MAP[p];
  if (!comps) { console.log(`  ${p.padEnd(19)} no component map entry`); continue; }
  const c2 = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await assertSignedIn(signIn(c2, 'supervisor'));
  await c2.addInitScript(RECORDER, comps);
  const pg = await c2.newPage();
  pg.__name = p;
  try {
    report.pages[p] = await measure(c2, pg, comps);
    const line = Object.entries(report.pages[p]).map(([k, v]) =>
      `${k}:${v.present}el${v.grew ? ' fed' : ' static'}${v.skel ? ' skel' + v.skel : ''}${v.busy ? ' busy' + v.busy : ''}${v.stuck ? ' STUCK' : ''}`).join('  ');
    console.log(`  ${p.padEnd(19)} ${line}`);
  } catch (e) {
    report.pages[p] = { error: String(e).slice(0, 120) };
    console.log(`  ${p.padEnd(19)} ERROR ${String(e).slice(0, 60)}`);
  }
  await c2.close();
}
// A NARROWED RUN MUST NOT CLOBBER THE FULL ONE: this file is read downstream (gates and
// bank_prover_reports), so a --page/--case spot-check overwriting a whole sweep's verdicts
// corrupts the BANK, not just a log. Measured on prove_retry_path 2026-08-27.
writeFileSync((ONE ? 'component_states_scoped_report.partial.json' : 'component_states_scoped_report.json'), JSON.stringify(report, null, 1));
console.log(`\n  wrote component_states_scoped_report.json (${Object.keys(report.pages).length} page(s))`);
await browser.close();
