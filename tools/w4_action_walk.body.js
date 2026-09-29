// w4_action_walk.body.js - LIVE a wave-4 ACTION group through the Playwright MCP (2026-09-23).
//
// WHY THIS EXISTS. tools/prove_w4_actions.mjs already knows how to live these rows, but it drives the Playwright
// LIBRARY, and Ian retracted every row banked on a library prover on 2026-09-15: "I thought we are using relevant
// live MCPs?". The rule is that the instrument is part of the definition of done, so a prover may WALK to find
// defects but may not BANK a row reserved for an MCP walk. This file is that walk - the prover's semantics, moved
// into the MCP's own browser, so the receipt's instrument is honestly `playwright-mcp + postgres-mcp`.
//   (the postgres half is the DRIVER's: it resolves the cast and any persisted-effect receipt through the postgres
//    MCP and hands them in via .tmp/w4_args.json - nothing here shells out to psql.)
//
// Rows that share a path and a cast are walked ONCE, with every PostgREST / RPC / edge response the person's own
// session receives recorded; each row in the group is then answered from that one record. That is the prover's
// design and the reason 506 rows cost ~152 walks instead of 506.
//
//   rpc   - a 2xx to /rest/v1/rpc/<subject> received by the person's session on the path. A page calls some of its
//           RPCs only on a tap, so a row with no observed call is answered by the person's OWN SESSION calling it
//           (same PostgREST route, same JWT). A function needing arguments the story does not give answers 4xx and
//           the row stays open, honestly.
//   edge  - a 2xx to /functions/v1/<subject> (never the OPTIONS preflight) AND the page it landed on shows its
//           provenance (.wh-source-chip) - "the answer landed with provenance" is the whole story, not just a 200.
//
// ★A MUTATING RPC IS NEVER CALLED BY THE WALK. The deny-list below is carried over verbatim from the prover, which
// earned it the hard way: its first build called deactivate_my_account as the cast and deactivated two local
// accounts. A walk reads; only the page's own control may write. (CLAUDE.md: "A walk must NEVER call a mutating
// RPC"; memory feedback_a_generic_caller_must_classify_before_it_calls.)
//
// Parameters: .tmp/w4_args.json { id, pages[], actions[{id,kind,subject}], user, pass, castName, lang, width,
// height, origin, api, anonKey, sigs{name:[signature]}, hiveId, anon }.
// Receipt: POST /api/w4/steps -> .tmp/w4_steps/<id>.json + <id>.records.json.
async (page) => {
  try {
    return await walkOn(page);
  } finally {
    try { await page.close(); } catch (e) { void e; }
  }

  async function walkOn(page) {
    let P = globalThis.__W4 || {};
    try {
      const ar = await page.request.get('http://localhost:5000/workhive/.tmp/w4_args.json', { timeout: 5000 });
      if (ar.ok()) P = Object.assign({}, await ar.json(), P);
    } catch (e) { void e; }
    const origin = P.origin || 'http://localhost:5000/workhive';
    const API = P.api || 'http://127.0.0.1:54321';
    const LANG = P.lang || 'en';
    const VP = { w: P.width || 390, h: P.height || 844 };
    const pages = (P.pages || []).filter(Boolean);
    const acts = P.actions || [];
    const anon = !!P.anon;
    const out = { id: P.id, axis: P.axis, pages, cast: anon ? 'anonymous reader' : (P.castName || null),
                  steps: [], records: [], answers: {}, problems: [] };
    if (!pages.length) { out.problems.push('no pages in .tmp/w4_args.json'); return out; }
    if (!acts.length) { out.problems.push('no actions in .tmp/w4_args.json'); return out; }

    // ── the allow-list Postgres itself declares (safe[] from .tmp/rpc_volatility.json), then the
    //    prover's name deny-list as a second fence ───────────────────────────────────────────────
    const SAFE = P.safeRpcs || {};
    const MUTATING =/^(deactivate_|claim_|notify_|set_|report_|ensure_|insert|update|delete|create|mark_|accept_|reject_|grant_|revoke_|publish_|submit_|send_|bind_|record_|log_|dismiss_|award_|redeem_|spend_|charge_|cancel_|archive_|reset_|register_|join_|leave_|invite_|approve_|assign_|complete_|close_|open_|start_|stop_|toggle_)/i;
    const atPath = (h) => new RegExp('/' + String(h).split('.').join('[.]') + '(?:[?#]|$)');
    const fillArg = (name, ctx) => {
      const n = String(name).toLowerCase();
      if (/^(p_)?hive(_id)?$/.test(n)) return ctx.hiveId;
      if (/^(p_)?worker_name$/.test(n)) return ctx.worker;
      if (/^(p_)?(period_|since_|window_|lookback_)?days$/.test(n)) return 30;
      if (/^(p_)?(limit|max|page_size)$/.test(n)) return 20;
      if (/^(p_)?offset$/.test(n)) return 0;
      if (/^(p_)?lang(uage)?$/.test(n)) return LANG;
      // ...then the REAL values the story gives, read from the database through the postgres MCP: an invite
      // code a person joining a hive would type, the category and condition a buyer comparing prices picks,
      // a listing/request/project id that actually exists. Without these the row answers "needs argument(s)
      // the story does not give" when the story plainly does give them - it was the VALUE that was missing.
      const CTX = P.context || {};
      if (Object.prototype.hasOwnProperty.call(CTX, n)) return CTX[n];
      if (Object.prototype.hasOwnProperty.call(CTX, 'p_' + n)) return CTX['p_' + n];
      return undefined;
    };

    // ── the overlap/occlusion audit, re-armed from the served file when its sha moves ───────────
    try {
      const ar = await page.request.get(`${origin}/tools/phone_fit_audit.browser.js`, { timeout: 5000 });
      if (ar.ok()) {
        const body = await ar.text();
        const sha = (body.match(/\(sha ([0-9a-f]{6,})\)/) || [])[1] || String(body.length);
        if (page.__w4AuditSha !== sha) { await page.addInitScript({ content: body }); page.__w4AuditSha = sha; }
      }
    } catch (e) { void e; }
    try { if (typeof page.unrouteAll === 'function') await page.unrouteAll({ behavior: 'ignoreErrors' }); } catch (e) { void e; }

    const read = () => page.evaluate(() => ({
      url: location.pathname.split('/').pop(),
      worker: localStorage.getItem('wh_last_worker'),
      lang: document.documentElement.lang,
      chars: (document.body.innerText || '').replace(/\s+/g, ' ').trim().length,
    }));
    const A = async (step) => page.evaluate((s) => {
      if (!window.__W4_AUDIT) return { step: s, error: 'audit not installed', findings: 0 };
      const r = window.__W4_AUDIT(null, { step: s });
      return Object.assign({ step: s }, r);
    }, step);
    const compact = (f) => f ? { findings: f.findings || 0, occlusion: (f.occlusion || []).slice(0, 4),
      overflowEl: (f.overflowEl || []).slice(0, 2), wrapped: (f.wrapped || []).slice(0, 2),
      outside: (f.outside || []).slice(0, 2), error: f.error } : { findings: 0 };
    const chip = () => page.evaluate(() => {
      const c = document.querySelector('.wh-source-chip');
      return c ? (c.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 120) : '';
    }).catch(() => '');

    // ── a print row needs window.print RECORDED, not suppressed ────────────────────────────────
    // Stubbed before the first navigation so the page's own Print / Export-PDF control can be pressed and
    // the call observed. A print can also land as a download or a popup window, so both are counted too -
    // "the row lives when the call landed OR a download started" is the prover's rule, kept.
    const actResult = {};
    let downloads = 0, popups = 0;
    try {
      await page.addInitScript(() => {
        window.__w4Printed = false;
        const orig = window.print;
        window.print = function () { window.__w4Printed = true; try { return orig && orig.call(window); } catch (e) { void e; } };
      });
      page.on('download', () => { downloads++; });
      page.on('popup', async (pp) => { popups++; try { await pp.close(); } catch (e) { void e; } });
    } catch (e) { void e; }

    // ── record every response the PERSON'S session receives, before anything navigates ─────────
    // The OPTIONS preflight is excluded on purpose: an edge row's story is that the answer landed, and a
    // preflight is the browser asking permission, not an answer.
    let current = pages[0];
    const hits = [];
    const onResp = (r) => {
      try {
        const u = r.url();
        if (!/\/rest\/v1\/|\/functions\/v1\//.test(u)) return;
        const req = r.request();
        if ((req.method() || '').toUpperCase() === 'OPTIONS') return;
        hits.push({ url: u.replace(API, ''), full: u, status: r.status(), method: req.method(), page: current });
      } catch (e) { void e; }
    };
    page.on('response', onResp);

    // ── the CONTROL-PRESS half: a print / cta row is lived by pressing the page's OWN control ──
    // Ported from the prover's actOn(). The `rpc`/`edge` half of this walker answers off the responses a
    // page makes on its own; these two kinds cannot be answered that way, because the whole story is that
    // a PERSON pressed something. Restores the page afterwards (back out of a navigation, Escape a dialog)
    // so the next row in the group meets the page it expects.
    const normL = (x) => String(x || '').replace(/[^\p{L}\p{N} ]/gu, ' ').replace(/\s+/g, ' ').trim().toLowerCase();
    const snap = () => page.evaluate(() => ({
      url: location.href,
      len: (document.body.innerText || '').length,
      dialogs: [...document.querySelectorAll('[role="dialog"], .modal, .sheet')]
        .filter((e) => e.getBoundingClientRect().height > 0 && getComputedStyle(e).visibility !== 'hidden').length,
    })).catch(() => ({ url: '', len: 0, dialogs: 0 }));

    // ★SOME CONTROLS DO NOT EXIST UNTIL THE PAGE IS IN THE STATE THAT NEEDS THEM (2026-09-23).
    // engineering-design.html is a FOUR-STEP WIZARD and arrives at "Step 2 of 4: Select Calculation Type".
    // Its Generate / 💾 Save / Generate Documents controls are not hidden by a bug - they do not exist yet,
    // because nothing has been calculated. A cta row that reports "no visible control labelled X" on a page
    // in step 2 is measuring the walk's own laziness, not the product. (I nearly filed this as a defect:
    // the page rendered 781-1824 chars with no inputs and "Run Calculation" present, which reads like a
    // broken form until you read the page's own words - it says which step it is on. Read the page, not the
    // absence. feedback_the_instrument_was_wrong_more_often_than_the_code.)
    // An opener is per-page and NAMED, never a generic "click things until something appears".
    const OPENERS = {
      'engineering-design.html': async () => {
        // ...and the card is a bare `div.calc-card[data-id]` - no role, no tabindex, no inner control - so
        // it is selected HERE by its class, not by any control selector. That is not a convenience: the
        // control-finder below deliberately queries only what assistive tech can reach, and these cards are
        // not in that set. The walker not seeing them is the walker being right; see the a11y finding for
        // W4163 in .tmp/w4_skill_proposals.md (the tab order never lands on one).
        const grid = page.locator('#calc-type-grid .calc-card');
        const n = await grid.count().catch(() => 0);
        for (let i = 0; i < Math.min(n, 12); i++) {
          const el = grid.nth(i);
          if (!(await el.isVisible().catch(() => false))) continue;
          await el.click({ timeout: 8000 }).catch(() => {});
          await page.waitForTimeout(2500);
          break;
        }
        // Step 3: give the form values so "Run Calculation" has something to compute. The numbers only need
        // to be VALID, not meaningful - this row's story is that the control works, and the calc's own
        // correctness is the maintenance-expert lens's job, not this walk's.
        const filled = await page.evaluate(() => {
          let k = 0;
          document.querySelectorAll('input[type=number], input[type=text]').forEach((i) => {
            const r = i.getBoundingClientRect();
            if (!(r.width > 0 && r.height > 0) || i.value || i.id === 'calc-search' || i.type === 'search') return;
            const min = parseFloat(i.min);
            i.value = String(Number.isFinite(min) && min > 0 ? min : 10);
            i.dispatchEvent(new Event('input', { bubbles: true }));
            i.dispatchEvent(new Event('change', { bubbles: true }));
            k++;
          });
          return k;
        }).catch(() => 0);
        out.opener = { page: 'engineering-design.html', inputsFilled: filled };
        await page.waitForTimeout(600);
      },
    };
    const opened = {};
    const reveal = async (p) => {
      // after the opener, Generate/Save still need a RUN to exist - press the calc button once
      if (p !== 'engineering-design.html') return;
      const run = page.locator('#calc-btn');
      if (await run.count().catch(() => 0) && await run.isVisible().catch(() => false)) {
        await run.click({ timeout: 8000 }).catch(() => {});
        await page.waitForTimeout(4000);
      }
    };

    const actOn = async (p) => {
      const pending = acts.filter((x) => (x.kind === 'print' || x.kind === 'cta')
                                      && (x.subjectPage || pages[pages.length - 1]) === p && !actResult[x.id]);
      if (pending.length && OPENERS[p] && !opened[p]) {
        opened[p] = true;
        try { await OPENERS[p](); } catch (e) { out.problems.push(`opener for ${p} threw: ${String(e.message || e).slice(0, 70)}`); }
      }
      for (const t of acts.filter((x) => (x.kind === 'print' || x.kind === 'cta')
                                      && (x.subjectPage || pages[pages.length - 1]) === p && !actResult[x.id])) {
        try {
          if (t.kind === 'print') {
            const ctl = page.locator('button, a, [role="button"]')
              .filter({ hasText: /print|download pdf|export pdf|save as pdf|i-print|pdf/i }).first();
            if (!(await ctl.count()) || !(await ctl.isVisible().catch(() => false))) {
              actResult[t.id] = { ok: false, detail: `no visible print / export-PDF control on ${p}` };
              continue;
            }
            const label = ((await ctl.textContent().catch(() => '')) || '').replace(/\s+/g, ' ').trim().slice(0, 40);
            const d0 = downloads, p0 = popups;
            await page.evaluate(() => { window.__w4Printed = false; }).catch(() => {});
            await ctl.click({ timeout: 8000 }).catch(() => {});
            await page.waitForTimeout(8000);
            const printed = await page.evaluate(() => !!window.__w4Printed).catch(() => false);
            actResult[t.id] = { ok: printed || downloads > d0 || popups > p0,
              detail: `"${label}" on ${p}: ${printed ? 'window.print was called' : downloads > d0 ? 'a file download started' : popups > p0 ? 'a print/PDF window opened' : 'neither window.print, a download nor a window followed in 8s'}` };
          } else {
            const subj = String(t.subject || '');
            const generic = /the page's primary link/i.test(subj);
            const want = normL(subj);
            const find = async () => {
              const all = page.locator('button, a[href], [role="button"], input[type="submit"]');
              const cnt = await all.count();
              for (let i = 0; i < Math.min(cnt, 400); i++) {
                const el = all.nth(i);
                if (!(await el.isVisible().catch(() => false))) continue;
                const txt = normL((await el.textContent().catch(() => ''))
                  || (await el.getAttribute('value').catch(() => ''))
                  || (await el.getAttribute('aria-label').catch(() => '')) || '');
                const cls = ((await el.getAttribute('class').catch(() => '')) || '').toLowerCase();
                const primary = /btn-primary|primary|cta|submit/.test(cls);
                if (generic ? primary : (want && txt && (txt === want || txt.startsWith(want) || (txt.length > 3 && want.startsWith(txt))))) return { el, label: txt.slice(0, 40) };
              }
              return null;
            };
            let found = await find();
            // a control that only EXISTS after the page has done something (Generate / Save on the calc
            // workbench) gets one reveal attempt before the row is called open - and the receipt says so
            if (!found) { await reveal(p); found = await find(); if (found) out.revealed = (out.revealed || 0) + 1; }
            const ctl = found && found.el;
            const label = found ? found.label : '';
            if (!ctl) {
              actResult[t.id] = { ok: false, detail: generic ? `no visible primary-styled control on ${p}` : `no visible control labelled "${subj}" on ${p}` };
              continue;
            }
            const h0 = hits.length;
            const before = await snap();
            await ctl.click({ timeout: 8000 }).catch(() => {});
            await page.waitForTimeout(3500);
            const after = await snap();
            // a Refresh re-renders the same words: the change a person cannot see is the READ it triggered
            const what = after.url !== before.url ? 'navigated to ' + after.url.replace(/^https?:\/\/[^/]+/, '')
              : after.dialogs > before.dialogs ? 'a dialog opened'
              : Math.abs(after.len - before.len) >= 40 ? `the page changed (${after.len - before.len >= 0 ? '+' : ''}${after.len - before.len} chars)`
              : (hits.length > h0 ? `the page re-read its data (${hits.length - h0} request${hits.length - h0 === 1 ? '' : 's'} answered)` : '');
            actResult[t.id] = { ok: !!what, detail: `"${label}" on ${p}: ${what || 'nothing visible changed in 3.5s'}` };
            if (after.url !== before.url) { await page.goBack({ waitUntil: 'load', timeout: 30000 }).catch(() => {}); await page.waitForTimeout(1500); }
            else if (after.dialogs > before.dialogs) { await page.keyboard.press('Escape').catch(() => {}); await page.waitForTimeout(400); }
          }
        } catch (err) {
          actResult[t.id] = { ok: false, detail: 'the action threw: ' + String(err.message || err).split('\n')[0].slice(0, 100) };
        }
      }
    };

    try {
      // ── measure the SHIPPED shell, not the one this browser installed last time ──────────────
      try {
        const cdp0 = await page.context().newCDPSession(page);
        await cdp0.send('Storage.clearDataForOrigin', { origin: origin.replace(/\/workhive\/?$/, ''), storageTypes: 'service_workers,cache_storage' });
        out.cdpReset = 'ok';
      } catch (e) { out.cdpReset = String(e.message || e).slice(0, 60); }
      await page.goto(`${origin}/index.html`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
      try {
        out.shellReset = await page.evaluate(async () => {
          const rs = navigator.serviceWorker ? await navigator.serviceWorker.getRegistrations() : [];
          await Promise.all(rs.map((r) => r.unregister()));
          const ks = (typeof caches !== 'undefined') ? await caches.keys() : [];
          await Promise.all(ks.map((k) => caches.delete(k)));
          return { workers: rs.length, caches: ks.length };
        });
      } catch (e) { out.problems.push('could not reset the service worker: ' + String(e.message || e).slice(0, 80)); }
      try { const cdp = await page.context().newCDPSession(page); await cdp.send('Network.setCacheDisabled', { cacheDisabled: true }); out.httpCache = 'disabled'; }
      catch (e) { out.httpCache = 'could not disable: ' + String(e.message || e).slice(0, 60); }

      await page.setViewportSize({ width: VP.w, height: VP.h });
      // the axis's language is SET, never assumed - a previous fil walk leaves wh_lang=fil in this persistent browser
      await page.addInitScript((l) => { try { if (sessionStorage.getItem('w4_lang_lock') !== '1') localStorage.setItem('wh_lang', l); } catch (e) { void e; } }, LANG);
      await page.evaluate((l) => { try { sessionStorage.removeItem('w4_lang_lock'); localStorage.setItem('wh_lang', l); } catch (e) { void e; } }, LANG).catch(() => {});

      // ── arrive as the person: the wall first, then the path ──────────────────────────────────
      const first = pages[0];
      current = first;
      if (!anon) {
        await page.goto(`${origin}/index.html?signin=1&return=${first}`, { waitUntil: 'load', timeout: 30000 });
        await page.waitForSelector('#si-username', { state: 'visible', timeout: 45000 }).catch(() => {});
        if (await page.locator('#si-username').isVisible().catch(() => false)) {
          const wr = await read();
          out.steps.push({ page: 'index.html', chars: wr.chars, identityKept: true, lang: wr.lang,
                           fit: compact(await A('index.html wall at ' + VP.w)) });
          await page.fill('#si-username', P.user || '', { timeout: 8000 });
          await page.fill('#si-password', P.pass || 'test1234', { timeout: 8000 });
          await page.click('#si-btn', { timeout: 10000 }).catch(async () => {
            out.problems.push('the sign-in submit did not become clickable in 10s; pressed Enter instead');
            await page.press('#si-password', 'Enter', { timeout: 4000 }).catch(() => {});
          });
          try { await page.waitForURL(atPath(first), { timeout: 30000 }); }
          catch (e) {
            const err = await page.evaluate(() => ((document.getElementById('si-error') || {}).textContent || '').trim().slice(0, 120)).catch(() => '?');
            out.problems.push('sign-in did not reach ' + first + ' in 30s: ' + err);
          }
        }
      }

      // ── walk the path, one page at a time, the overlap record after each ─────────────────────
      for (const p of pages) {
        current = p;
        const here = await page.evaluate(() => location.pathname.split('/').pop()).catch(() => '');
        if (here !== p) {
          await page.goto(`${origin}/${p}`, { waitUntil: 'load', timeout: 60000 })
            .catch((err) => out.problems.push(`${p}: ${String(err.message).split('\n')[0].slice(0, 80)}`));
        }
        await page.waitForTimeout(3500);
        let r = await read(); let looks = 0;
        while (r.chars < 300 && looks < 2) { await page.waitForTimeout(2500); r = await read(); looks++; }
        // press this page's own controls BEFORE the overlap record, so the record describes the page a
        // person is left holding - and so a cta that navigates is walked from here, not from a later page
        await actOn(p);
        r = await read();
        out.steps.push({ page: p, viewport: P.device || (VP.w + 'px'), chars: r.chars, lang: r.lang,
                         identityKept: anon ? true : (r.worker === (P.castName || r.worker)),
                         fit: compact(await A(`${p} at ${P.device || VP.w}`)) });
      }
    } catch (err) {
      out.problems.push('the walk threw: ' + String(err.message || err).split('\n')[0].slice(0, 120));
    }

    const provenance = await chip();
    const pageHits = hits.length;   // everything after this index is the walk's own call, not the page's

    // ── "call rpc X and read what it returns" is the PERSON'S call, not only the page's ────────
    const direct = {};
    if (!anon) {
      const ctxVals = await page.evaluate(() => ({
        hiveId: localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id') || null,
        worker: localStorage.getItem('wh_last_worker') || null,
        keys: Object.keys(localStorage).filter((k) => /auth|sb-/.test(k)).slice(0, 6),
      })).catch(() => ({ hiveId: P.hiveId || null, worker: null, keys: [] }));
      if (!ctxVals.hiveId && P.hiveId) ctxVals.hiveId = P.hiveId;
      const want = acts.filter((x) => x.kind === 'rpc'
        && !hits.slice(0, pageHits).some((h) => h.url.includes('/rest/v1/rpc/' + String(x.subject || ''))));
      for (const t of want) {
        const subj = String(t.subject || '');
        if (direct[subj]) continue;
        // ★THE DATABASE CLASSIFIES, NOT THE NAME (2026-09-23). The prover's prefix regex is kept as a second
        // fence, but the FIRST fence is Postgres' own `provolatile`: a STABLE or IMMUTABLE function provably
        // cannot write, and the planner enforces that. Measured through the postgres MCP, the regex alone was
        // unsafe in the dangerous direction - `get_hive_readiness_current` and `get_pm_compliance_smrp` read
        // like getters and are VOLATILE, `apply_credits_to_request` and `increment_listing_view` match no
        // denied prefix, and `compute_anomaly_signals` (volatile) is one the prover's own comment records
        // calling. A name is not an identity; an allow-list of what the DB declares read-only is.
        if (!SAFE[subj]) {
          direct[subj] = { status: 0, note: 'not declared STABLE/IMMUTABLE by Postgres, so the walk does not call it; the page\'s own control must trigger it' };
          continue;
        }
        if (MUTATING.test(subj)) {
          direct[subj] = { status: 0, note: "a mutating rpc is not called by the walk; the page's own control must trigger it" };
          continue;
        }
        const sig = ((P.sigs || {})[subj] || [''])[0] || '';
        const body = {}; const missing = [];
        for (const a of sig.split(',').map((x) => x.trim()).filter(Boolean)) {
          const nm = a.split(/\s+/)[0];
          const v = fillArg(nm, ctxVals);
          if (v === undefined || v === null) missing.push(nm); else body[nm] = v;
        }
        if (missing.length) {
          direct[subj] = { status: 0, note: 'needs argument(s) the story does not give: ' + missing.join(', ') + ' (signature ' + sig + ')' };
          continue;
        }
        direct[subj] = await page.evaluate(async ({ subj, apikey, api, body, keys }) => {
          try {
            const k = Object.keys(localStorage).find((x) => /^sb-.*-auth-token$/.test(x));
            if (!k) return { status: 0, note: 'no session token in localStorage (keys: ' + keys.join(',') + ')' };
            const tok = (JSON.parse(localStorage.getItem(k)) || {}).access_token;
            if (!tok) return { status: 0, note: 'session token has no access_token' };
            const r = await fetch(`${api}/rest/v1/rpc/${subj}`, {
              method: 'POST',
              headers: { apikey, Authorization: 'Bearer ' + tok, 'Content-Type': 'application/json', Prefer: 'return=representation' },
              body: JSON.stringify(body),
            });
            // `txt`, not `body`: a const named body here once shadowed the request body for the whole try
            // block and every call died in the TDZ (prover, 2026-09-15 02:02).
            const txt = await r.text();
            let rows = null;
            try { const j = JSON.parse(txt); rows = Array.isArray(j) ? j.length : (j && typeof j === 'object' ? 1 : null); } catch (e) { void e; }
            return { status: r.status, bytes: txt.length, rows, note: r.ok ? '' : txt.slice(0, 120) };
          } catch (e) { return { status: 0, note: String(e.message).slice(0, 100) }; }
        }, { subj, apikey: P.anonKey || '', api: API, body, keys: ctxVals.keys || [] })
          .catch((e) => ({ status: 0, note: String(e.message).slice(0, 80) }));
        direct[subj].via = "called directly by the person's own session";
      }
    }

    // ── answer each row in the group from the one record ──────────────────────────────────────
    const distinct = new Set(out.steps.map((s) => s.page)).size;
    const idKept = anon ? true : out.steps.every((s) => s.identityKept !== false);
    for (const t of acts) {
      const subj = String(t.subject || '');
      let pred; let observed = null; let effect = null;
      if (t.kind === 'rpc') {
        const h = hits.slice(0, pageHits).find((x) => x.url.includes('/rest/v1/rpc/' + subj));
        const dc = direct[subj];
        observed = h || (dc ? Object.assign({}, dc) : null);
        const okHit = !!h && h.status >= 200 && h.status < 300;
        const okDirect = !!dc && dc.status >= 200 && dc.status < 300;
        pred = { ok: okHit || okDirect,
          detail: h ? `rpc ${subj} answered ${h.status} on ${h.page}`
            : dc ? `rpc ${subj} called by the person's own session answered ${dc.status}${dc.rows != null ? ' with ' + dc.rows + ' row(s)' : ''}${dc.note ? ' - ' + dc.note : ''}`
            : `the person's session never called rpc ${subj} along ${pages.join(' -> ')}` };
      } else if (t.kind === 'edge') {
        const h = hits.find((x) => x.url.includes('/functions/v1/' + subj));
        observed = h || null;
        if (h) effect = { fn: subj, status: h.status, bytes: h.bytes, page: h.page, provenance };
        pred = { ok: !!h && h.status >= 200 && h.status < 300 && !!provenance,
          detail: h ? `${subj} answered ${h.status} on ${h.page}; provenance ${provenance ? '"' + provenance.slice(0, 60) + '"' : 'ABSENT (no source chip)'}`
            : `the person's session never invoked ${subj} along the path` };
      } else if (t.kind === 'print' || t.kind === 'cta') {
        pred = actResult[t.id] || { ok: false,
          detail: `the subject page ${t.subjectPage || '(unknown)'} was not reached on this path` };
        observed = actResult[t.id] || null;
      } else {
        pred = { ok: false, detail: `no walker yet for action kind ${t.kind} - this walk records the path and the responses, so adding it costs no re-walk` };
      }
      const rowProblems = out.problems.slice();
      if (!pred.ok) rowProblems.push(`${t.kind} ${subj} not lived clean: ${pred.detail}`);
      if (!idKept) rowProblems.push('identity did not survive the arrival');
      if (distinct < 4) rowProblems.push(`only ${distinct} distinct pages walked`);
      out.answers[t.id] = { id: t.id, ok: rowProblems.length === 0, kind: t.kind, subject: subj,
                            note: `${t.kind} ${subj} ${pred.ok ? 'LIVED CLEAN' : 'STILL OPEN'}: ${pred.detail}`,
                            observed, effect, problems: rowProblems };
    }

    out.records = hits.slice(0, 400);
    out.provenance = provenance;
    out.direct = direct;
    try { page.off('response', onResp); } catch (e) { void e; }

    // ── hand the record to the seeder (the MCP vm cannot write a file; its request context can POST) ──
    try {
      const res = await page.request.post('http://localhost:5000/api/w4/steps', {
        data: { id: P.id, steps: out.steps, records: { records: out.records, answers: out.answers, direct: out.direct, provenance, pages, axis: P.axis, cast: out.cast } },
        timeout: 10000,
      });
      out.wrote = res.ok() ? (await res.json()).path : `POST /api/w4/steps -> ${res.status()}`;
    } catch (e) { out.problems.push('could not POST the record: ' + String(e.message || e).slice(0, 80)); }

    return { id: out.id, wrote: out.wrote, cast: out.cast, pages, axis: P.axis, problems: out.problems,
             distinctPages: distinct, identityKept: idKept, hits: hits.length, provenance,
             steps: out.steps.map((s) => ({ page: s.page, chars: s.chars, lang: s.lang, identityKept: s.identityKept,
                                            findings: s.fit && s.fit.findings, occlusion: s.fit && s.fit.occlusion })),
             answers: Object.values(out.answers).map((a) => ({ id: a.id, ok: a.ok, note: a.note })) };
  }
}
