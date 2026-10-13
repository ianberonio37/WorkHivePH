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
    // ★A BATCH GROUP'S ARGS ARE WHOLE, AND THE FILE IS SOMEONE ELSE'S (2026-10-08). A batch loader hands each group its
    // complete args in globalThis.__W4; .tmp/w4_args.json is the single-walk file, which another driver (a write walk
    // running in parallel) may have just rewritten for a DIFFERENT group. Merging it underneath let any key a group did
    // not carry leak in from that other group - a castHive that moves an actor walk into a stranger's hive, a signup
    // flag that makes a cast walk try to create an account. The file is read only when no loader passed args in.
    let P = globalThis.__W4 || {};
    if (!globalThis.__W4) {
      try {
        const ar = await page.request.get('http://localhost:5000/workhive/.tmp/w4_args.json', { timeout: 5000 });
        if (ar.ok()) P = Object.assign({}, await ar.json(), P);
      } catch (e) { void e; }
    }
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
    const fillArg = (name, ctx, subj) => {
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
      // (2026-10-07) a value may be named for ONE function ('service_knob_pct:p_key'), because two functions can share
      // an argument name and want different values (service_knob reads an integer knob, service_knob_pct a percent);
      // and a context value may be an explicit null - the marketplace sends p_part_number: null when the field is
      // blank, so null is a value the story gives, unlike a hive id the session could not read.
      const own = (k) => (subj && Object.prototype.hasOwnProperty.call(CTX, subj + ':' + k)) ? [CTX[subj + ':' + k]]
        : (Object.prototype.hasOwnProperty.call(CTX, k) ? [CTX[k]] : null);
      const hit = own(n) || own('p_' + n);
      if (hit) return hit[0] === null ? NULL_ARG : hit[0];
      return undefined;
    };
    const NULL_ARG = { nullArg: true };

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
    // ★NO LIVE MODEL CALL BY ARRIVING (2026-10-07): shift-brain's first open of a shift calls shift-planner-orchestrator,
    // an LLM briefing. A CONTEXT route (survives the unrouteAll above), once per context; see w4_navhub_walk.body.js.
    // ★THE PLANNER STUB CAME OFF (2026-10-12, UFAI edge walk W4785): every walk sends x-wh-walk-no-model and the planner
    // honours it (the counts-only briefing, no model), so its fake 503 only kept the planner's own row from being walked.
    // A context an older walk body stubbed is cleared here.
    try { const _c = page.context(); if (_c.__whModelStub) { await _c.unroute('**/functions/v1/shift-planner-orchestrator**').catch(() => {}); _c.__whModelStub = null; } } catch (e) { void e; }
    // ★NO MODEL CALL FROM ANY WALK, ON ANY PAGE (2026-10-09). Signed-in paths end on analytics-report, project-report,
    // the assistant... pages whose own load can ask a model. Every edge call carries x-wh-walk-no-model: 1, which ONLY the
    // local runtime honours (_shared/observability.ts): the shared chain answers "{}" before any provider and the function's
    // deterministic path answers instead. fallback() hands the request on, so the stubs above still answer theirs. A walk
    // that is MEANT to reach a model (an LM G/R row) passes liveModel and the route comes off.
    try {
      const _c = page.context();
      if (P.liveModel && _c.__whNoModel) { await _c.unroute('**/functions/v1/**', _c.__whNoModel).catch(() => {}); _c.__whNoModel = null; }
      if (!P.liveModel && !_c.__whNoModel) {
        _c.__whNoModel = (r) => { const q = r.request(); return q.method() === 'OPTIONS' ? r.fallback() : r.fallback({ headers: Object.assign({}, q.headers(), { 'x-wh-walk-no-model': '1' }) }); };
        await _c.route('**/functions/v1/**', _c.__whNoModel);
      }
    } catch (e) { void e; }
    // ★A WRITE THAT NEEDS A MODEL'S ANSWER FIRST GETS A STUBBED ONE (2026-10-08). ai_reply_feedback is a thumbs-up on
    // an assistant reply, and the thumbs exist only under a reply - but a walk never spends a model call. The recipe
    // names the function (stub_model) and this walk answers it from a CONTEXT route, in the gateway's own envelope
    // ({ok, data:{answer, agent, usage}}); the route is removed when the walk ends, so no other walk ever meets it.
    // A recipe's `permissions` (push needs 'notifications') are granted the same way and cleared at the end.
    const ctxRoutes = [];
    for (const fn of [...new Set(acts.filter((x) => x.kind === 'write' && x.stubModel).map((x) => x.stubModel))]) {
      try {
        const pat = `**/functions/v1/${fn}**`;
        const h = (route) => {
          const rq = route.request();
          const cors = { 'access-control-allow-origin': '*', 'access-control-allow-methods': 'POST, OPTIONS',
                         'access-control-allow-headers': rq.headers()['access-control-request-headers'] || 'authorization, x-client-info, apikey, content-type' };
          if (rq.method() === 'OPTIONS') return route.fulfill({ status: 204, headers: cors });
          return route.fulfill({ status: 200, contentType: 'application/json', headers: cors,
            body: JSON.stringify({ ok: true, data: { answer: 'Two PM tasks are overdue this week. (A stubbed reply: this walk makes no model call.)',
                                                     agent: 'assistant', usage: { served_from: 'w4-walk-stub' } } }) });
        };
        await page.context().route(pat, h);
        ctxRoutes.push([pat, h]);
      } catch (e) { out.problems.push('could not stub ' + fn + ': ' + String(e.message || e).slice(0, 60)); }
    }
    const perms = [...new Set(acts.filter((x) => x.kind === 'write').flatMap((x) => x.permissions || []))];
    if (perms.length) {
      try { await page.context().grantPermissions(perms, { origin: origin.replace(/\/workhive\/?$/, '') }); out.granted = perms; }
      catch (e) { out.problems.push('could not grant ' + perms.join(',') + ': ' + String(e.message || e).slice(0, 60)); }
    }

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
    let downloads = 0, popups = 0, lastDownload = null;
    try {
      // ★RECORDED, NEVER OPENED (2026-10-08). Calling the real window.print() in the MCP's headed browser opens the
      // print preview, which holds the page's script until someone closes it; every later page.evaluate then waits with
      // no timeout of its own and the whole MCP call dies at its 30-minute ceiling. The PRESS is what the row proves -
      // the dialog is the browser's, not the platform's - so the stub records the call and opens nothing.
      await page.addInitScript(() => {
        window.__w4Printed = false;
        window.print = function () { window.__w4Printed = true; };
      });
      page.on('download', (d) => { downloads++; lastDownload = d; });
      page.on('popup', async (pp) => { popups++; try { await pp.close(); } catch (e) { void e; } });
    } catch (e) { void e; }

    // ── the confusions (2026-10-12): tools/prove_w4_confusions.mjs's predicates, lived in the MCP's own browser ──
    // The prover's PRED block and REACH helper are fetched from the local seeder and evaluated verbatim - one source,
    // so a predicate the prover corrects is the predicate this walk applies. ORIGIN is the walk's origin (C25, C27).
    const confActs = acts.filter((x) => x.kind === 'confusion');
    let CONF = {};
    if (confActs.length) {
      try {
        const src = await (await page.request.get(`${origin}/tools/prove_w4_confusions.mjs`, { timeout: 8000 })).text();
        const i0 = src.indexOf('const PRED = {'), i1 = src.indexOf('\nconst browser = await chromium.launch()');
        const r0 = src.indexOf('const REACH = '), r1 = src.indexOf('\n', r0);
        if (i0 < 0 || i1 < 0 || r0 < 0) throw new Error('the prover no longer carries const PRED / const REACH where expected');
        const ORIGIN = origin;   // eslint-disable-line no-unused-vars -- read by the evaluated predicates
        CONF = eval('(() => { ' + src.slice(i0, i1) + '\n return PRED; })()');
        const reachSrc = src.slice(r0 + 'const REACH = '.length, r1).trim().replace(/;$/, '');
        if (!page.__w4ConfReach) { await page.addInitScript({ content: 'window.__W4_REACH = ' + reachSrc + ';' }); page.__w4ConfReach = true; }
        await page.evaluate('window.__W4_REACH = ' + reachSrc).catch(() => {});
      } catch (e) { out.problems.push('the confusion predicates could not be loaded: ' + String(e.message || e).slice(0, 100)); }
      // the target: the predicate's own page on the path, else the ledger entry's page; appended when the path lacks it
      for (const t of confActs) {
        const pref = (CONF[t.subject] && CONF[t.subject].on) || [];
        const e = t.entry || {};
        t.target = pref.find((pp) => pages.includes(pp)) || pref[0] || e.host
          || (e.page && /\.html$/.test(e.page) ? e.page : (pages[pages.length - 1] !== 'index.html' ? pages[pages.length - 1] : 'achievements.html'));
        if (!pages.includes(t.target)) pages.push(t.target);
      }
    }
    const confCtx = {
      context: page.context(),
      openHub: async () => {
        const shown = await page.evaluate(() => { const p = document.querySelector('#wh-hub-panel'); return !!p && getComputedStyle(p).visibility !== 'hidden' && p.getBoundingClientRect().height > 0; }).catch(() => false);
        if (shown) return;
        const ok = await page.click('#wh-hub-fab', { timeout: 8000 }).then(() => true).catch(() => false);
        if (!ok) await page.keyboard.press('Control+k').catch(() => {});
        await page.waitForTimeout(700);
      },
      closeAll: async () => { await page.keyboard.press('Escape').catch(() => {}); await page.waitForTimeout(250); await page.keyboard.press('Escape').catch(() => {}); await page.waitForTimeout(250); },
    };
    const runConf = async (t) => {
      try { return await CONF[t.subject].run(page, confCtx); }
      catch (err) { return { ok: false, detail: 'predicate threw: ' + String(err.message || err).split('\n')[0].slice(0, 120) }; }
    };

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

    // ★A WRITE IS LIVED BY THE PERSON'S OWN CONTROL (2026-10-08). The W4 "write" rows (and the "rpc" rows whose
    // function mutates) were the group no walker could live: a walk never writes through PostgREST or calls a
    // mutating rpc itself. So each one carries a RECIPE (tools/w4_write_recipes.json, authored from the page's own
    // source and gated by validate_w4_write_recipes.py): the clicks and the typing a person does on the page that
    // owns the write. The walker presses them, waits for the request the press must produce (method + path), and
    // records it; the DRIVER then reads the persisted row through postgres (by this run's {MARK} or time window)
    // and reverses it, so the effect is proven and leaves nothing behind. Free text carries {MARK}, never a guess.
    // ★THE CAST'S OWN HIVE, CHOSEN THE WAY THE PERSON CHOOSES IT (2026-10-08). index.html seats a member of several
    // hives in the FIRST BY NAME (resolveActiveHiveContext orders v_hives_truth by name), so Christine Dizon -
    // supervisor of Baguio and Lucena, worker in Manila - always arrived in Baguio, and a Lucena write would have
    // landed in Baguio's data or been refused by its RLS. A person whose story is about another of their hives opens
    // the hive switcher and picks it; a write walk does the same, through hive.html's own switcher, before the path
    // and again after any write that moved the active hive. (P.castHive is set by tools/w4_write_drive.py for a cast
    // walk only; an actor or anonymous walk keeps the hive the product gives it.)
    const activeHive = () => page.evaluate(() => localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id') || '').catch(() => '');
    // ★A FAILED SWITCH TAINTS THE ROWS IT STRANDS, NOT THE WHOLE WALK (WGW446, 2026-10-08). The reason it failed is
    // kept here while the cast sits outside its hive; a write pressed in that state carries it as its own problem,
    // and a later switch that succeeds clears it. A walk that also lives non-write rows cannot say which of them ran
    // while stranded, so there it still lands on every row.
    let hiveAstray = '';
    const ensureHive = async (why) => {
      const want = P.castHive;
      if (!want || anon) return '';
      const was = await activeHive();
      if (was === want) { hiveAstray = ''; return ''; }
      const keep = current;
      current = 'hive.html';
      try {
        // a press is only true when the click LANDED: an overlay that intercepts it used to read as "menu true"
        const press = async (sel) => {
          const l = page.locator(sel).first();
          for (let i = 0; i < 16; i++) {
            if (await l.isVisible().catch(() => false)) {
              const ok = await l.click({ timeout: 8000 }).then(() => true).catch(() => false);
              await page.waitForTimeout(900);
              return ok;
            }
            await page.waitForTimeout(500);
          }
          return false;
        };
        // ★THE NEW HIVE ASKS ITS SUPERVISOR FOR A GOAL FIRST (WGW446, 2026-10-08). Creating a hive makes it active,
        // and on its board hive.html opens #intent-capture - a full-screen aria-modal "what should WorkHive focus
        // on?" - for a supervisor whose hive has no intent yet. It covered the More button, the click never landed,
        // and every row after the create ran in the wrong hive. A person who only wants to get back to their own
        // hive answers it with its own dismiss control ("Later", data-wh-close: a sessionStorage flag, no write) -
        // never its Save.
        const dismiss = async () => {
          let n = 0;
          for (let i = 0; i < 3; i++) {
            const later = page.locator('[role="dialog"][aria-modal="true"]:visible [data-wh-close]:visible').first();
            if (!(await later.isVisible().catch(() => false))) break;
            if (!(await later.click({ timeout: 5000 }).then(() => true).catch(() => false))) break;
            n++; await page.waitForTimeout(700);
          }
          return n;
        };
        let okMenu = false, okSw = false, okPick = false, dismissed = 0;
        for (let tries = 0; tries < 3 && !okSw; tries++) {
          // a retry reloads: the board reconciles wh_hives from the server on load, so a stale one-hive list heals
          await page.goto(`${origin}/hive.html`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
          await page.waitForTimeout(3000);
          dismissed += await dismiss();
          okMenu = await press('#btn-hive-menu');
          okSw = okMenu && await press('#btn-switch-hive');
          if (!okSw) { dismissed += await dismiss(); }
        }
        okPick = okSw && await press(`#hive-switch-list button[onclick*="${want}"]`);
        let now = '';
        for (let i = 0; i < 20; i++) { now = await activeHive(); if (now === want) break; await page.waitForTimeout(500); }
        const note = `${why}: the active hive ${was ? was.slice(0, 8) : '(none)'} -> ${now === want ? want.slice(0, 8) : 'NOT SWITCHED (' + (now || 'none').slice(0, 8) + ')'} through hive.html's switcher`
          + (dismissed ? ` (answered ${dismissed} first-run dialog${dismissed > 1 ? 's' : ''} with its own dismiss)` : '');
        (out.hiveSwitches = out.hiveSwitches || []).push(note);
        if (now !== want) {
          hiveAstray = `could not seat the cast in its hive ${want.slice(0, 8)} (${why}): menu ${okMenu}, switch ${okSw}, pick ${okPick}`;
          if (acts.some((x) => x.kind !== 'write')) out.problems.push(hiveAstray);
        } else hiveAstray = '';
        await page.waitForTimeout(3000);   // the switched board's own on-load reads land under hive.html
        return note;
      } finally { current = keep; }
    };

    const MARK = P.mark || 'W4M';
    const CA_CREW_MIN = 4;
    const CA_CREW = ['preventive maintenance', 'work order', 'breakdown', 'downtime', 'spare part', 'spares', 'lockout', 'loto', 'permit', 'ptw', 'shift', 'handover', 'checklist', 'mtbf', 'mttr', 'oee', 'supervisor', 'technician', 'crew', 'hive', 'logbook', 'asset', 'machine', 'inspection', 'repair', 'fault', 'plant', 'maintenance', 'pm schedule', 'pm task', 'root cause', 'failure', 'safety', 'calibration', 'equipment', 'job', 'task', 'team', 'worker', 'report', 'alert', 'log', 'entry', 'record', 'schedule', 'part', 'tool', 'inventory', 'stock', 'restock', 'fix', 'work', 'workshop', 'factory', 'operator', 'foreman', 'engineer', 'manual', 'sop', 'procedure', 'compliance', 'incident', 'hazard', 'mechanical', 'electrical', 'instrumentation', 'skill', 'discipline', 'switchgear', 'facilities', 'production line', 'pump', 'motor', 'bearing', 'compressor', 'conveyor', 'boiler', 'generator', 'lubrication', 'vibration', 'welding', 'electrician', 'mechanic', 'certification'];
    // ★EACH ROW ITS OWN MARK, IN ITS SELECTORS TOO (2026-10-08). One mark per group let two recipes seed the same row
    // and let ":has-text('W4M')" press a SIBLING row's seed. The driver now hands every action its own mark, and a
    // selector may name it as {MARK} - substituted here exactly as in typed values - so a press can only ever reach
    // the row this recipe seeded.
    const runRecipe = async (t, p) => {
      const R = t.recipe || {};
      const h0 = hits.length;
      const did = [];
      const MK = t.mark || MARK;
      const v = (x) => String(x == null ? '' : x).split('{MARK}').join(MK);
      let dialogs = 0;
      let uaCdp = null; let uaWas = '';   // a `device` step's user-agent override, put back when the recipe ends
      const onDialog = (d) => { dialogs++; d.accept().catch(() => {}); };
      page.on('dialog', onDialog);
      // ★"THE PERSON WAS TOLD" MEANS SOMETHING APPEARED BECAUSE OF THE PRESS (2026-10-12, WGW4112/WGW4118). The receipt
      // read the first visible role=status/alert/toast - and the page's provenance chip is role=status, on screen before
      // anything was pressed: a reaction toggle, a supervisor approval and a make-public all banked "the person was told
      // 'Live · updates automatically · as of 05:35 PHT …'", a sentence nobody said to them. The chip is excluded, and
      // only text that was not on screen before the steps (or since the last nav) counts as what the person was told.
      const STATUS_SEL = '[role="status"], [role="alert"], .toast, .wh-toast, #toast, #toast-msg';
      const statusTexts = () => page.evaluate((s) => [...document.querySelectorAll(s)]
        .filter((e) => !e.closest('.wh-source-chip'))
        .map((e) => (e.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean), STATUS_SEL).catch(() => []);
      let toldBefore = await statusTexts();
      try {
        for (const st of (R.steps || [])) {
          if (st.confirm) { did.push('confirm accepted when asked'); continue; }
          if (st.fake_mic) {
            // ★A MICROPHONE FOR A WALK THAT HAS NONE (2026-10-12): the MCP browser has no audio device, so voice capture
            // stopped at "No microphone found". The page gets a real MediaStream - a quiet generated tone - where a device
            // would supply one; its own record / stop / upload run unchanged. The receipt says the microphone was generated.
            // ★A REAL CLIP INTO THE MICROPHONE (2026-10-13): `fake_mic: true, fixture: "<kind>/<file>"` plays that fixture
            // once into the stream the page records (decoded from the local seeder's /_fixtures/, provenance in its kind's
            // manifest), so a transcriber hears what a person said; without a fixture the quiet tone below plays. A clip
            // the seeder cannot serve stops the walk here, never a silent tone in its place.
            const _clip = st.fixture ? 'http://localhost:5000/workhive/_fixtures/' + String(st.fixture) : null;
            if (_clip) {
              const cr = await page.request.get(_clip, { timeout: 30000 }).catch(() => null);
              if (!cr || !cr.ok()) return { ok: false, detail: `the real clip ${st.fixture} could not be read from the local seeder (after: ${did.join(' > ') || 'nothing'})`, did };
            }
            await page.evaluate((clipUrl) => {
              if (!navigator.mediaDevices) return;
              navigator.mediaDevices.getUserMedia = async () => {
                const Ctx = window.AudioContext || window.webkitAudioContext;
                const ctx = new Ctx();
                const dst = ctx.createMediaStreamDestination();
                if (clipUrl) {
                  const audio = await ctx.decodeAudioData(await (await fetch(clipUrl)).arrayBuffer());
                  const src = ctx.createBufferSource(); src.buffer = audio;
                  // 0.3 s in: the page starts its recorder once this stream is returned, so the first word lands inside it
                  src.connect(dst); src.start(ctx.currentTime + 0.3);
                } else {
                  // 0.2, not 0.05: a 0.05 sine is RMS ~4.5 on the 0-255 scale, one step from report-sender's "silence"
                  // (RMS < 4 for 2 s stops the recording), so the page could stop on its own and the stop tap would start
                  // a second recording. The stop belongs to the person's tap.
                  const osc = ctx.createOscillator(); const gain = ctx.createGain(); gain.gain.value = 0.2;
                  osc.connect(gain); gain.connect(dst); osc.start();
                }
                try { await ctx.resume(); } catch (_) { /* a suspended context still yields a stream */ }
                return dst.stream;
              };
            }, _clip).catch(() => {});
            did.push(_clip ? 'a microphone was attached, playing the real clip _fixtures/' + st.fixture : 'a microphone was attached (a generated tone)'); continue;
          }
          if (typeof st.fake_speech === 'string') {
            // ★A SPEECH RECOGNISER FOR A WALK THAT HAS NONE (2026-10-12, UFAI edge walk W4745): Chromium's Web Speech sends
            // the audio to a recognition service the MCP browser cannot reach, from a microphone it does not have, so a
            // spoken request never produced words. The recogniser the page already holds now "hears" the recipe's
            // sentence when the page starts it - a result event, then an end event, as the engine sends them - and the
            // page's own handler runs unchanged. The receipt quotes what it heard.
            const said = v(st.fake_speech);
            await page.evaluate((text) => {
              for (const C of [window.SpeechRecognition, window.webkitSpeechRecognition]) {
                if (!C || !C.prototype) continue;
                C.prototype.start = function () {
                  const rec = this;
                  setTimeout(() => {
                    const ev = new Event('result');
                    Object.defineProperty(ev, 'results', { value: [[{ transcript: text, confidence: 0.92 }]] });
                    Object.defineProperty(ev, 'resultIndex', { value: 0 });
                    rec.dispatchEvent(ev);
                    rec.dispatchEvent(new Event('end'));
                  }, 600);
                };
                C.prototype.stop = function () { this.dispatchEvent(new Event('end')); };
                C.prototype.abort = C.prototype.stop;
              }
            }, said).catch(() => {});
            did.push('a speech recogniser was attached (it heard "' + said + '")'); continue;
          }
          if (st.device) {
            // ★THE PATH AN IPHONE TAKES (2026-10-12, UFAI edge walk W4748): report-sender records with MediaRecorder and
            // uploads to voice-transcribe only where Web Speech is missing or broken - iPhone Safari, Firefox. The MCP
            // browser is Chromium, which always takes Web Speech, so that path was out of every walk's reach. The page is
            // told it runs on an iPhone (Safari's user agent, set before it loads, so its own capability check decides)
            // and reloaded; the agent is put back when the recipe ends. The receipt says so.
            const UA = { iphone: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1' }[st.device];
            if (!UA) { did.push('no user agent for device ' + st.device); continue; }
            if (!uaCdp) { uaWas = await page.evaluate(() => navigator.userAgent).catch(() => ''); uaCdp = await page.context().newCDPSession(page); }
            await uaCdp.send('Emulation.setUserAgentOverride', { userAgent: UA });
            await page.reload({ waitUntil: 'load', timeout: 30000 }).catch(() => {});
            await page.waitForTimeout(2500);
            did.push('the page was told it runs on an ' + st.device + ' (Safari\'s user agent) and reloaded'); toldBefore = await statusTexts(); continue;
          }
          if (st.hear) {
            // ★WHAT THE PAGE SAYS ALOUD IS SOMETHING THE PERSON WAS TOLD (2026-10-12, UFAI edge walk W4805). A voice reply
            // is heard, not read: the walker notes each sentence the page hands the device's voice and each audio reply
            // it plays, and a recipe that listens counts them as what the person was told. The page's own calls still run.
            await page.evaluate(() => {
              window.__whHeard = [];
              const ss = window.speechSynthesis;
              if (ss && !ss.__whHeard) {
                const orig = ss.speak.bind(ss);
                ss.speak = (u) => { try { window.__whHeard.push('the device voice read "' + String((u && u.text) || '').slice(0, 80) + '"'); } catch (_) { /* noting is best-effort */ } return orig(u); };
                ss.__whHeard = true;
              }
              const P = window.HTMLMediaElement && window.HTMLMediaElement.prototype;
              if (P && !P.__whHeard) {
                const op = P.play;
                P.play = function () { try { window.__whHeard.push('an audio reply played'); } catch (_) { /* best-effort */ } return op.apply(this, arguments); };
                P.__whHeard = true;
              }
            }).catch(() => {});
            did.push('listening for what the page says aloud'); continue;
          }
          if (typeof st.pause === 'number') {
            await page.waitForTimeout(Math.min(10000, Math.max(0, st.pause)));
            did.push('held for ' + st.pause + ' ms'); continue;
          }
          if (st.nav) {
            await page.goto(`${origin}/${v(st.nav)}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
            await page.waitForTimeout(2500); did.push('opened ' + st.nav); toldBefore = await statusTexts(); continue;
          }
          if (st.upload) {
            // a file the person picks (the CMMS import recipes): set on the input as an in-memory file
            const body = v(st.content || '');
            const name = v(st.filename || (st.fixture ? String(st.fixture).split('/').pop() : 'w4-upload.csv'));
            // a photo is bytes (content_b64, 2026-10-12: the nameplate scan and the defect photo); text stays text
            const mime = /\.png$/i.test(name) ? 'image/png' : (/\.jpe?g$/i.test(name) ? 'image/jpeg'
              : /\.pdf$/i.test(name) ? 'application/pdf' : /\.wav$/i.test(name) ? 'audio/wav' : /\.ogg$/i.test(name) ? 'audio/ogg'
              : (/\.csv$/i.test(name) ? 'text/csv' : (/\.json$/i.test(name) ? 'application/json' : 'application/octet-stream')));
            let bytes = st.content_b64 ? Buffer.from(String(st.content_b64), 'base64') : Buffer.from(body, 'utf-8');
            if (st.fixture) {
              // ★A REAL FILE (2026-10-12, UFAI upload walks): the fixture the row names, served by the local seeder exactly
              // as it was fetched from the internet (source, licence and sha256 in _fixtures/<kind>/manifest.json)
              const fr = await page.request.get('http://localhost:5000/workhive/_fixtures/' + String(st.fixture), { timeout: 30000 }).catch(() => null);
              if (!fr || !fr.ok()) return { ok: false, detail: `the real file ${st.fixture} could not be read from the local seeder (after: ${did.join(' > ') || 'nothing'})`, did };
              bytes = await fr.body();
            }
            const okUp = await page.setInputFiles(v(st.upload), { name, mimeType: mime, buffer: bytes }, { timeout: 8000 })
              .then(() => true).catch(() => false);
            if (!okUp) return { ok: false, detail: `the file could not be set on ${st.upload} on ${p} (after: ${did.join(' > ') || 'nothing'})`, did };
            did.push('chose ' + name + (st.fixture ? ' (a real file, ' + bytes.length + ' bytes, _fixtures/' + st.fixture + ')' : '') + ' in ' + st.upload);
            await page.waitForTimeout(2500); continue;
          }
          if (st.scroll) {
            // ★READ IT BEFORE THE EXAM (2026-10-12, W4791). skillmatrix enables "Take Exam" only once the lesson box is
            // scrolled to its end - the read-before-you-test design - and a click never scrolls an inner box. A person
            // scrolls the lesson; so does this step: the box to its end, in steps, so the page's own scroll handler runs.
            const box = page.locator(v(st.scroll)).first();
            const okScroll = await box.evaluate(async (el) => {
              for (let i = 0; i < 12 && el.scrollTop + el.clientHeight < el.scrollHeight - 2; i++) {
                el.scrollTop = Math.min(el.scrollHeight, el.scrollTop + el.clientHeight);
                el.dispatchEvent(new Event('scroll'));
                await new Promise((r) => setTimeout(r, 150));
              }
              return true;
            }).catch(() => false);
            if (!okScroll) return { ok: false, detail: `${st.scroll} could not be scrolled on ${p} (after: ${did.join(' > ') || 'nothing'})`, did };
            did.push('scrolled ' + st.scroll + ' to its end'); await page.waitForTimeout(400); continue;
          }
          const sel = v(st.click || st.fill || st.select || st.waitFor || st.check || '');
          if (!sel) continue;
          const loc = page.locator(sel).first();
          let vis = false;
          // ★A CONTROL THAT IS ONLY OFFERED SOMETIMES (2026-10-08). asset-hub's Reliability Workbench sits behind a
          // "Show Reliability Workbench" toggle whose state persists per device - the first FMEA recipe of a walk
          // opens it, the next finds it open, and pressing it again would CLOSE it. `if_shown` presses a control
          // only when the page offers it (the selector names the closed state), exactly as a person taps "Show"
          // only when it says Show; absent in 4s, the step is skipped and said so.
          // A waitFor names data the page fetches (a seeded row in a list), so it is given longer than a control.
          // `within` (seconds, a waitFor only): an import of thousands of rows takes longer than a list takes to load
          const tries = st.if_shown ? 8 : (st.waitFor ? (typeof st.within === 'number' ? Math.min(360, Math.max(2, Math.round(st.within * 2))) : 50) : 20);
          for (let i = 0; i < tries && !vis; i++) { vis = await loc.isVisible().catch(() => false); if (!vis) await page.waitForTimeout(500); }
          if (!vis && st.if_shown) { did.push('(not offered: ' + sel + ')'); continue; }
          if (!vis) {
            // say WHY it was not visible - absent, or present and hidden, and what its container held - so a
            // failed row names its cause instead of costing another walk to find it
            const n = await page.locator(sel).count().catch(() => -1);
            let why = n > 0 ? `${n} in the DOM, none visible` : 'not in the DOM';
            const root = (sel.match(/^#[\w-]+/) || [])[0];
            if (root) {
              why += '; ' + root + ': ' + await page.evaluate((id) => {
                const el = document.querySelector(id);
                if (!el) return 'absent';
                const cs = getComputedStyle(el); const b = el.getBoundingClientRect();
                return `${cs.display}/${cs.visibility} ${Math.round(b.width)}x${Math.round(b.height)}, ${el.children.length} children, "${(el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 90)}"`;
              }, root).catch(() => '?');
            }
            return { ok: false, detail: `${sel} never became visible on ${p} (${why}) (after: ${did.join(' > ') || 'nothing'})`, did };
          }
          if (st.waitFor) { did.push('saw ' + sel); continue; }
          if (st.click) {
            await loc.scrollIntoViewIfNeeded().catch(() => {});
            // what the person is told is what follows the LAST press: a hint shown mid-flow (the vehicle wizard's
            // "Ford Ranger 2026 XLT filled in…", WGW4271) is not the answer to the save
            toldBefore = await statusTexts();
            // a press that cannot land (covered, disabled, moving) names its selector and Playwright's reason - "the
            // recipe threw: Timeout 8000ms exceeded" said neither, and cost a walk to find out
            // force: a control that animates while active (a pulsing record button) never holds still for the
            // stability check; a person presses it anyway (2026-10-12, WGW4806)
            const err = await loc.click({ timeout: 8000, force: st.force === true }).then(() => null).catch((e) => String(e.message || e));
            if (err) {
              const why = (err.split('\n').find((l) => /intercepts pointer events|not enabled|not stable|outside of the viewport|detached/.test(l)) || err.split('\n')[0]).trim().slice(0, 180);
              return { ok: false, detail: `${sel} could not be pressed on ${p}: ${why} (after: ${did.join(' > ') || 'nothing'})`, did };
            }
            did.push('pressed ' + sel + (st.force === true ? ' (a moving control, pressed without waiting for it to settle)' : '')); await page.waitForTimeout(1500);
          }
          else if (st.fill) { await loc.fill(v(st.value), { timeout: 8000 }); did.push('typed into ' + sel); await page.waitForTimeout(300); }
          else if (st.select) { await loc.selectOption(v(st.value), { timeout: 8000 }).catch(async () => { await loc.selectOption({ index: 1 }, { timeout: 8000 }); }); did.push('chose in ' + sel); await page.waitForTimeout(500); }
          else if (st.check) { await loc.check({ timeout: 8000 }).catch(() => loc.click({ timeout: 8000 })); did.push('checked ' + sel); await page.waitForTimeout(300); }
        }
        const E = R.expect || {};
        const want = String(E.path || '');
        const match = (h) => (!E.method || String(h.method).toUpperCase() === String(E.method).toUpperCase())
          && (!want || String(h.url).split('?')[0].endsWith(want));
        let hit = null;
        // expect.on_load: the page makes this call while it loads (no control exists), so it is matched against every
        // request made since the walk ARRIVED on this page, not only those after the first step
        const pool = () => E.on_load ? hits.filter((h, i) => h.page === p || i >= h0) : hits.slice(h0);
        // expect.wait_ms (2026-10-12): an EDGE recipe waits for a function that composes (an orchestrator, a summary),
        // not a row insert - 15 s is the default, a recipe may ask for up to 90 s
        const tries = Math.max(30, Math.min(180, Math.round((Number(E.wait_ms) || 15000) / 500)));
        for (let i = 0; i < tries && !hit; i++) { hit = pool().find(match) || null; if (!hit) await page.waitForTimeout(500); }
        const readTold = () => page.evaluate(({ s, before }) => {
          const seen = new Set(before);
          const el = [...document.querySelectorAll(s)]
            .find((e) => !e.closest('.wh-source-chip') && e.checkVisibility && e.checkVisibility({ opacityProperty: true, visibilityProperty: true })
              && (e.innerText || '').trim() && !seen.has((e.innerText || '').replace(/\s+/g, ' ').trim()));
          return el ? el.innerText.replace(/\s+/g, ' ').trim().slice(0, 120) : '';
        }, { s: STATUS_SEL, before: toldBefore }).catch(() => '');
        // ★A WORKING SENTENCE IS NOT THE ANSWER (2026-10-12, WGW4227). The coach said "Analyzing your plant data..." when
        // the gateway answered, then fell back to its direct tool and only later said what came back. Text that still
        // ends in an ellipsis is the page saying it is busy: re-read until it settles (bounded), and record that.
        let told = await readTold();
        for (let i = 0; i < 20 && /(\.\.\.|…)\s*$/.test(told); i++) { await page.waitForTimeout(500); told = (await readTold()) || told; }
        if ((R.steps || []).some((s) => s && s.hear)) {
          // a recipe that listens: what the page said aloud is part of what the person was told
          const heard = await page.evaluate(() => (window.__whHeard || []).join('; ')).catch(() => '');
          if (heard) told = told ? `${told}; ${heard}` : heard;
        }
        const writes = hits.slice(h0).filter((h) => /^(POST|PATCH|PUT|DELETE)$/i.test(h.method)).map((h) => `${h.method} ${String(h.url).split('?')[0]} ${h.status}`);
        // ★AN HONEST REFUSAL A RECIPE NAMES IS A LIVED ANSWER (2026-10-12, WGW4803). Under the walk's no-model switch the
        // journal's reply cannot be written: the gateway saves the note FIRST and answers 502, and the page says the note
        // is saved and only the reply failed. A recipe may accept such a status (expect.accept_status, with the reason
        // the gate requires in expect.accept_why) - and only when the person WAS told something: a refusal the page
        // swallows is still a failure.
        const accepted = !!hit && (E.accept_status || []).includes(hit.status) && !!told;
        const ok = !!hit && ((hit.status >= 200 && hit.status < 300) || accepted);
        return { ok, hit, did, told, dialogs, writes: writes.slice(0, 8),
          detail: `${did.join(' > ')} on ${p}: ` + (hit ? `${hit.method} ${String(hit.url).split('?')[0]} answered ${hit.status}` + (accepted ? ` (accepted: ${String(E.accept_why || '').slice(0, 140)})` : '') : `no ${E.method || ''} ${want} request followed in 15s (writes seen: ${writes.join('; ') || 'none'})`)
            + (told ? `; the person was told "${told}"` : '') };
      } finally {
        try { page.off('dialog', onDialog); } catch (e) { void e; }
        if (uaCdp) {
          await uaCdp.send('Emulation.setUserAgentOverride', { userAgent: uaWas || '' }).catch(() => {});
          await uaCdp.detach().catch(() => {});
        }
      }
    };

    const actOn = async (p) => {
      const pending = acts.filter((x) => (x.kind === 'print' || x.kind === 'cta')
                                      && (x.subjectPage || pages[pages.length - 1]) === p && !actResult[x.id]);
      if (pending.length && OPENERS[p] && !opened[p]) {
        opened[p] = true;
        try { await OPENERS[p](); } catch (e) { out.problems.push(`opener for ${p} threw: ${String(e.message || e).slice(0, 70)}`); }
      }
      // ★"FOLLOW THE TOOL THIS GUIDE IS ABOUT" IN THE MCP'S OWN BROWSER (2026-10-08). The learn-cta rows were lived by
      // tools/prove_w4_actions.mjs (the Playwright LIBRARY) and retracted with every library-banked row on 2026-09-15;
      // this is the prover's semantics moved here so the receipt's instrument is honestly the MCP. The seeder's five
      // CTA shapes (seed_expansion_wave4.py learn_actions) each resolve to a link rule and an arrival rule; the link
      // must exist, be the element at its own first line box's centre (what a finger meets), and clicking it must
      // ARRIVE. The guide is reloaded before each next CTA.
      // ★THE CA LAYER IN THE MCP'S OWN BROWSER (2026-10-08): "The platform must speak, on this page, the words a
      // Philippine maintenance crew uses". tools/prove_w4_layer_ca.mjs (the Playwright LIBRARY) holds the bar and cannot
      // bank; its reading is moved here unchanged: on the row's subject page the copy carries the platform's language
      // stamps ([data-i]) and at least CA_CREW_MIN of the crew's own words. The overlap bar is applied in the answer.
      for (const t of acts.filter((x) => x.kind === 'layer-ca' && x.subjectPage === p && !actResult[x.id])) {
        const v = await page.evaluate(({ CREW }) => {
          const text = ' ' + (document.body.innerText || '').replace(/\s+/g, ' ').toLowerCase() + ' ';
          // a plural counts as its word; CA_CREW is tools/ca_crew_words.json (singulars), synced by tools/sync_ca_crew_words.py
          const has = (w) => new RegExp('(^|[^a-z\u00C0-\u024F])' + w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?:s|es)?([^a-z\u00C0-\u024F]|$)', 'i').test(text);
          const crew = CREW.filter(has);
          return { stamps: document.querySelectorAll('[data-i]').length, crew: crew.slice(0, 12), crewCount: crew.length,
                   htmlLang: document.documentElement.lang || '' };
        }, { CREW: CA_CREW }).catch(() => null);
        actResult[t.id] = !v ? { ok: false, detail: `the subject page ${p} could not be read` }
          : { ok: v.stamps >= 1 && v.crewCount >= CA_CREW_MIN, vocab: v,
              detail: `${p}: ${v.stamps} language stamps, ${v.crewCount} crew terms (${v.crew.slice(0, 6).join(', ')})` };
      }
      // ★"WORK THE EXAMPLE, COMPUTE, EXPORT OR PRINT, FOLLOW THE CTA" (2026-10-08). The W4 compute rows arrive on a
      // calculator's guide page (tools/<calc>/index.html: formula, a worked example, a "try it" link). The library prover
      // never lived them ("need a hand on the page"). The calculator is engineering-design.html?calc=<slug>, which
      // preselects the calculation - but the calculators need a free account, so a STRANGER following the link meets the
      // sign-in wall first (index.html?signin=1&return=engineering-design.html?calc=<slug>, engineering-design.js init).
      // ★THE PILOT READ THE WALL AS THE CALCULATOR: "arrived" (the URL matched for a moment before the redirect),
      // "calculator NOT preselected", "1 field filled" (the wall's own field), "Run never enabled". The page was right;
      // the walk was signed out. The stranger's honest path is the door the wall offers - Sign Up, through the page's
      // own form, under a throwaway name the DRIVER removes again with every row it wrote (tools/w4_kind_drive.py) -
      // and then the calculator the link named. So: read the worked example, follow the link, see the wall carry the
      // calculator, create the account, land on the calculator with it preselected, fill ITS form's empty fields with
      // valid values, press Run, read a result with no NaN / Infinity / undefined, press the report's own Download PDF
      // and wait for the file, then come back.
      for (const t of acts.filter((x) => x.kind === 'compute' && p === pages[0] && !actResult[x.id])) {
        try {
          const back = page.url();
          const notes = [];
          // ★#worked IS THE HEADING, NOT THE EXAMPLE (2026-10-09): every receipt read 32-38 chars - "Worked example (Fire
          // Protection)" - so a guide whose example had gone missing would still have passed. The example is the heading's
          // SECTION: its inputs and its result table, which must carry numbers to be an example at all.
          const worked = await page.evaluate(() => {
            const h = document.getElementById('worked');
            const s = document.querySelector('section[aria-labelledby="worked"]') || (h && h.closest('section'));
            const txt = s ? (s.innerText || '').replace(/\s+/g, ' ').trim() : '';
            return txt.length >= 80 && /\d/.test(txt) && s.querySelector('table') ? txt : '';
          }).catch(() => '');
          // ★TWO DESTINATIONS (2026-10-09). 56 guides hand off to engineering-design.html?calc=<slug>; the MTBF and OEE
          // guides hand off to analytics.html, which works those figures out from the person's OWN log (W41273/4,
          // W41279/80) - so the row's subject names which door the guide must open.
          const toAnalytics = /analytics\.html/.test(String(t.subject || ''));
          const link = page.locator(toAnalytics ? 'a[href$="analytics.html"]' : 'a[href*="engineering-design.html?calc="]').first();
          if (!(await link.count().catch(() => 0))) { actResult[t.id] = { ok: false, detail: `no link from ${p} to its ${toAnalytics ? 'Analytics page' : 'calculator'}` }; continue; }
          const href = (await link.getAttribute('href').catch(() => '')) || '';
          let slug = '';
          try { slug = toAnalytics ? 'analytics.html' : decodeURIComponent((href.match(/[?&]calc=([^&#]+)/) || [])[1] || ''); } catch (e) { void e; }
          const want = toAnalytics ? 'analytics.html' : 'calc=' + slug;
          await link.scrollIntoViewIfNeeded().catch(() => {});
          await link.click({ timeout: 8000 }).catch(() => {});
          // the wall: the calculator's own redirect settles on index.html, and the destination rides along in ?return=
          let wallUrl = '';
          for (let i = 0; i < 40 && !wallUrl; i++) {
            const u = page.url();
            if (/\/index\.html\?[^#]*signin=1/.test(u)) wallUrl = u; else await page.waitForTimeout(500);
          }
          // ★READ AFTER THE PAGE HAS RUN (2026-10-08): the URL turns to index.html when the navigation STARTS, before
          // index.html's script has stored ?return= - the first pilot read that slot empty and reported "the wall
          // carried NOT the calculator" on a walk that then landed on the calculator preselected. The URL's own return
          // parameter is the door's promise; the stored copy is what sign-up redeems - both are read, the copy polled.
          let urlRet = '';
          try { urlRet = new URL(wallUrl || 'http://x/').searchParams.get('return') || ''; } catch (e) { void e; }
          let carried = '';
          for (let i = 0; i < 10 && wallUrl && !carried; i++) {
            carried = await page.evaluate(() => { try { return sessionStorage.getItem('wh_return_to') || ''; } catch (e) { return ''; } }).catch(() => '');
            if (!carried) await page.waitForTimeout(500);
          }
          let carriedDec = carried;
          try { carriedDec = decodeURIComponent(carried); } catch (e) { void e; }
          const wallCarries = !!slug && urlRet.includes(want) && carriedDec.includes(want);
          const dest = toAnalytics ? 'Analytics' : 'the calculator';
          notes.push(!wallUrl ? 'no sign-in wall appeared'
            : `the wall carried ${wallCarries ? dest + ' ("' + urlRet.slice(0, 70) + '", stored for after sign-up)'
              : 'NOT ' + dest + ' (return=' + (urlRet || 'none') + '; stored ' + (carriedDec || 'nothing') + ')'}`);
          // the stranger takes the wall's Sign Up door
          let signedUp = false;
          const S = P.computeSignup || null;
          if (wallUrl && S && S.user) {
            const tab = page.locator('#tab-signup');
            for (let i = 0; i < 20 && !(await tab.isVisible().catch(() => false)); i++) await page.waitForTimeout(500);
            await tab.click({ timeout: 8000 }).catch(() => {});
            await page.waitForSelector('#su-username', { state: 'visible', timeout: 15000 }).catch(() => {});
            // ★A FIELD FILLED BEFORE THE FORM WAS READY IS AN EMPTY FIELD (2026-10-08, KCW41190): one walk submitted a
            // blank username and the page answered "Username must be 3-30 characters" - true of what it received. The
            // walk now reads each field back and refills it until it holds what was typed, and if the form still
            // refuses, fills and submits once more before calling the sign-up failed.
            const fillAll = async () => {
              const want = { '#su-username': S.user, '#su-displayname': S.name, '#su-password': S.pass || 'test1234', '#su-confirm': S.pass || 'test1234' };
              for (const [sel, val] of Object.entries(want)) {
                for (let k = 0; k < 3; k++) {
                  await page.fill(sel, val, { timeout: 8000 }).catch(() => {});
                  if ((await page.inputValue(sel).catch(() => '')) === val) break;
                  await page.waitForTimeout(600);
                }
              }
            };
            const hasSess = () => page.evaluate(() => Object.keys(localStorage).some((k) => /^sb-.*-auth-token$/.test(k) && /access_token/.test(localStorage.getItem(k) || ''))).catch(() => false);
            // ...but a SLOW sign-up is not a failed one (KCW41208/41211): on a loaded host the account was still being
            // created after 30 s, the retry pressed again, and the page rightly answered "Username already taken". So
            // the walk waits up to 60 s for the session and presses again ONLY when the page says the form did not get
            // its input (an empty or malformed field) - never while the first request may still be landing.
            const formRefused = () => page.evaluate(() => {
              const e = document.getElementById('su-error');
              const t = e && !e.classList.contains('hidden') ? (e.textContent || '').trim() : '';
              return /must be|required|do not match|at least/i.test(t) ? t : '';
            }).catch(() => '');
            for (let attempt = 0; attempt < 2 && !signedUp; attempt++) {
              await fillAll();
              await page.click('#su-btn', { timeout: 10000 }).catch(() => {});
              let refused = '';
              for (let i = 0; i < 60 && !signedUp && !refused; i++) {
                signedUp = await hasSess();
                if (!signedUp) { refused = await formRefused(); if (!refused) await page.waitForTimeout(1000); }
              }
              if (!signedUp && !refused) break;   // no session and no refusal: waiting longer, not pressing again
              if (!signedUp && attempt === 0) notes.push(`the form refused the first press ("${refused.slice(0, 60)}"); filled and pressed again`);
            }
            if (!signedUp) {
              const err = await page.evaluate(() => ((document.getElementById('su-error') || {}).textContent || '').trim().slice(0, 120)).catch(() => '?');
              notes.push('the sign-up produced no session (' + err + ')');
            } else notes.push(`signed up as "${S.name}" through the wall's own form`);
            out.computeAccount = { user: S.user, signedUp };
          } else if (wallUrl) notes.push('no throwaway account was handed to the walk, so the stranger stopped at the wall');
          const arrived = (signedUp || !wallUrl) && await page.waitForURL(toAnalytics ? /\/analytics\.html(\?|#|$)/ : /engineering-design\.html\?calc=/, { timeout: 30000 }).then(() => true).catch(() => false);
          if (toAnalytics) {
            // ★ANALYTICS COMPUTES FROM THE LOG, NOT FROM TYPED NUMBERS (2026-10-09). There is no form to fill: the figure
            // is worked out from the corrective failures (MTBF/MTTR) or the logged downtime and output (OEE) the crew
            // records. A newcomer has none, so the honest end of this journey is the page saying what it needs AND a way
            // to it - read here, and the way out pressed until it lands on the Logbook. A figure on the tile also passes.
            const kpi = /oee/i.test(p) ? 'oee' : 'mtbf';
            let view = null;
            for (let i = 0; i < 40 && arrived; i++) {
              view = await page.evaluate((k) => {
                const tx = (id) => { const e = document.getElementById(id); return e ? (e.innerText || '').replace(/\s+/g, ' ').trim() : ''; };
                const b = document.getElementById('an-action-btn');
                const bv = !!(b && !b.classList.contains('hidden') && b.checkVisibility && b.checkVisibility({ opacityProperty: true, visibilityProperty: true }));
                return { hero: tx('an-' + k + '-hero'), sub: tx('an-' + k + '-sub'), verdict: tx('an-verdict-label'), verdictSub: tx('an-verdict-sub'),
                         action: tx('an-action-text'), btn: bv ? (b.innerText || '').replace(/\s+/g, ' ').trim() : '', btnHref: bv ? (b.getAttribute('href') || '') : '' };
              }, kpi).catch(() => null);
              if (view && view.verdict && !/loading/i.test(view.verdict + ' ' + view.sub + ' ' + view.action)) break;
              await page.waitForTimeout(750);
            }
            const figure = !!(view && /\d/.test(view.hero));
            const empty = !!(view && /not enough data|no analytics yet/i.test(view.verdict + ' ' + view.action));
            let reached = '';
            if (!figure && empty && view.btn && /logbook\.html/.test(view.btnHref)) {
              await page.locator('#an-action-btn').click({ timeout: 8000 }).catch(() => {});
              reached = await page.waitForURL(/\/logbook\.html(\?|#|$)/, { timeout: 20000 }).then(() => 'logbook.html').catch(() => '');
            }
            const said = view ? `"${(view.verdict + (view.action ? ': ' + view.action : '')).slice(0, 150)}"` : 'nothing';
            actResult[t.id] = { ok: !!worked && !!wallUrl && wallCarries && signedUp && arrived && (figure || (empty && !!reached)),
              detail: `${p}: worked example ${worked ? 'present (' + worked.length + ' chars)' : 'MISSING'}; "${href}" -> ${notes.join('; ')}; `
                + `Analytics ${arrived ? 'reached' : 'NOT reached'}; ${kpi.toUpperCase()} tile "${view ? view.hero : '?'}"; `
                + (figure ? 'the figure is worked out from the log'
                  : empty ? `nothing logged yet - the page says ${said}${view.btn ? ', offers "' + view.btn + '"' + (reached ? ' and it lands on the Logbook' : ' but it did not land on the Logbook') : ' and offers no way to it'}`
                  : `the page said ${said}`) };
            await page.goto(back, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
            await page.waitForTimeout(1500);
            continue;
          }
          // ★THE MATH IS THE ROW'S STORY, THE NARRATIVE IS A MODEL'S (2026-10-08). Run posts to engineering-calc-agent,
          // which computes deterministically and then asks the model chain for the report's narrative - a live call a
          // walk never spends. The request carries x-wh-walk-no-model: 1, which the LOCAL runtime honours
          // (_shared/model-calls.ts no_model): the chain answers "{}" before any provider is asked and the function's
          // own deterministic narrative is used. The route is the walk's alone and is removed when the compute ends.
          const calcPat = '**/functions/v1/engineering-calc-agent**';
          const calcRoute = (route) => {
            const rq = route.request();
            if (rq.method() === 'OPTIONS') return route.continue();
            calcCalls++;
            return route.continue({ headers: Object.assign({}, rq.headers(), { 'x-wh-walk-no-model': '1' }) });
          };
          let calcCalls = 0;
          await page.context().route(calcPat, calcRoute).catch(() => {});
          let selected = '';
          for (let i = 0; i < 30 && arrived && !selected; i++) {
            selected = await page.evaluate(() => { const c = document.querySelector('.calc-card.selected'); return c ? (c.getAttribute('data-id') || 'selected') : ''; }).catch(() => '');
            if (!selected) await page.waitForTimeout(500);
          }
          await page.waitForTimeout(1500);
          // only the calculator's OWN form: the grid's search, the wall's fields and the nav are never "the inputs"
          const FILL = () => {
            const area = document.getElementById('input-form-area');
            if (!area) return 0;
            let k = 0;
            area.querySelectorAll('input[type=number], input[type=text], input:not([type]), select').forEach((i) => {
              const r = i.getBoundingClientRect();
              if (!(r.width > 0 && r.height > 0) || i.disabled || i.readOnly) return;
              if (i.tagName === 'SELECT') { if (!i.value && i.options.length > 1) { i.selectedIndex = 1; i.dispatchEvent(new Event('change', { bubbles: true })); k++; } return; }
              const min = parseFloat(i.min), max = parseFloat(i.max);
              if (i.value !== '') {
                // ★A PREFILLED VALUE THE FIELD'S OWN RANGE REFUSES IS NOT AN ENTRY (2026-10-08): AHU Sizing ships its
                // cooling load as "0" in a min-1 field, so a walk that filled only BLANK fields pressed Run on a form the
                // page itself refused ("must be at least 1 (you entered 0)"). A person types their load over the 0.
                const v = Number(i.value);
                if (i.type !== 'number' || !Number.isFinite(v)) return;
                if ((!Number.isFinite(min) || v >= min) && (!Number.isFinite(max) || v <= max)) return;
              }
              let val = Number.isFinite(min) && min > 0 ? min : 10;
              if (Number.isFinite(max) && val > max) val = max;
              i.value = String(val);
              i.dispatchEvent(new Event('input', { bubbles: true })); i.dispatchEvent(new Event('change', { bubbles: true })); k++;
            });
            return k;
          };
          const READ = () => {
            const o = document.getElementById('report-output');
            const vis = o && o.checkVisibility && o.checkVisibility({ opacityProperty: true, visibilityProperty: true });
            const txt = vis ? (o.innerText || '').replace(/\s+/g, ' ').trim() : '';
            const tst = document.getElementById('toast');
            const said = tst && tst.checkVisibility && tst.checkVisibility({ opacityProperty: true, visibilityProperty: true }) ? (tst.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 100) : '';
            return { chars: txt.length, bad: /\bNaN\b|\bInfinity\b|\bundefined\b/.test(txt), head: txt.slice(0, 120), said };
          };
          const filled = !selected ? 0 : await page.evaluate(FILL).catch(() => 0);
          const run = page.locator('#calc-btn');
          let enabled = false;
          for (let i = 0; i < 20 && selected && !enabled; i++) { enabled = await run.isEnabled().catch(() => false); if (!enabled) await page.waitForTimeout(500); }
          // press Run and read: a result, or what the page said instead. A refusal ("please / must be / at least")
          // is final - the page computes nothing after it - so the wait stops there rather than at 30 s.
          const REFUSAL = /please|must be|at least|enter |select |add /i;
          const runAndRead = async () => {
            await run.scrollIntoViewIfNeeded().catch(() => {});
            await run.click({ timeout: 8000 }).catch(() => {});
            let r = { chars: 0, bad: false, head: '', said: '' }, said1 = '';
            for (let i = 0; i < 40 && r.chars < 80; i++) {
              await page.waitForTimeout(750);
              r = await page.evaluate(READ).catch(() => ({ chars: 0, bad: false, head: '', said: '' }));
              if (r.said && !said1) said1 = r.said;
              if (!r.chars && said1 && REFUSAL.test(said1) && i >= 3) break;
            }
            return { res: r, said: said1 || r.said || '' };
          };
          let res = { chars: 0, bad: false, head: '', said: '' };
          let firstSaid = '';
          let addedRows = 0, bumpedCounts = 0, retriedAfter = '';
          if (enabled) {
            ({ res, said: firstSaid } = await runAndRead());
            // ★A FORM THAT STARTS WITH NO ROWS (2026-10-08, KCW41229 Fire Alarm Battery): "Please enter at least one
            // device or notification appliance." Many calculators take a LIST - devices, loads, fixtures, rooms, cable
            // runs, duct segments - and ship it empty, so a person adds a row before Run. The walk does the same, and only
            // when the page asked: the form's OWN Add control, the new row filled like the rest, Run again (twice at most).
            for (let attempt = 0; attempt < 2 && res.chars < 80 && /at least one|please add|add (a|an|one) /i.test(firstSaid); attempt++) {
              const added = await page.evaluate(() => {
                const area = document.getElementById('input-form-area');
                if (!area) return false;
                const btn = [...area.querySelectorAll('button')].find((x) => {
                  const r = x.getBoundingClientRect();
                  return r.width > 0 && r.height > 0 && !x.disabled && /^\s*(\+|\u2795)?\s*add\b/i.test((x.innerText || x.getAttribute('aria-label') || '').trim());
                });
                if (!btn) return false;
                btn.click();
                return true;
              }).catch(() => false);
              if (!added) {
                // ...or the list is a set of COUNT fields that ship at 0 (Fire Alarm Battery, KCW41229: seven device
                // counts, "Please enter at least one device"). A person told that types a count; the walk sets the
                // visible zero counts to 2 (within each field's own range) - once - and runs again.
                const bumped = attempt > 0 ? 0 : await page.evaluate(() => {
                  const area = document.getElementById('input-form-area');
                  if (!area) return 0;
                  let k = 0;
                  area.querySelectorAll('input[type=number]').forEach((i) => {
                    const r = i.getBoundingClientRect();
                    if (!(r.width > 0 && r.height > 0) || i.disabled || i.readOnly || Number(i.value) !== 0 || i.value === '') return;
                    const max = parseFloat(i.max);
                    i.value = String(Number.isFinite(max) && max < 2 ? max : 2);
                    i.dispatchEvent(new Event('input', { bubbles: true })); i.dispatchEvent(new Event('change', { bubbles: true })); k++;
                  });
                  return k;
                }).catch(() => 0);
                if (!bumped) break;
                bumpedCounts = bumped;
                ({ res, said: firstSaid } = await runAndRead());
                continue;
              }
              addedRows++;
              await page.waitForTimeout(800);
              await page.evaluate(FILL).catch(() => 0);
              ({ res, said: firstSaid } = await runAndRead());
            }
            // ★"PLEASE TRY AGAIN" IS AN INSTRUCTION A PERSON FOLLOWS (2026-10-09, KCW41271 Load Estimation). The local
            // runtime reuses a worker across requests, so its CPU budget ran out on whichever calculation was current: the
            // function answered 502 and the page said "Could not generate the report right now. Please try again." The
            // same group walked again passed with no CPU warning. A person presses Run again; so does the walk - once, after
            // the failure's toast has gone (a toast still showing would read as this run's refusal) - and the receipt says
            // so. A second failure stays open.
            if (res.chars < 80 && /try again/i.test(firstSaid)) {
              retriedAfter = firstSaid;
              for (let i = 0; i < 20; i++) {
                const shown = await page.evaluate(() => { const t = document.getElementById('toast'); return !!(t && t.checkVisibility && t.checkVisibility({ opacityProperty: true, visibilityProperty: true })); }).catch(() => false);
                if (!shown) break;
                await page.waitForTimeout(500);
              }
              ({ res, said: firstSaid } = await runAndRead());
            }
          }
          let printed = false, how = res.chars >= 80 ? 'no Download PDF control on the result' : 'nothing to export';
          const pr = page.locator('[onclick^="printReport("]').first();
          if (res.chars >= 80 && !res.bad && await pr.count().catch(() => 0)) {
            const d0 = downloads, p0 = popups;
            await page.evaluate(() => { window.__w4Printed = false; }).catch(() => {});
            await pr.scrollIntoViewIfNeeded().catch(() => {});
            const label = ((await pr.innerText().catch(() => '')) || '').replace(/\s+/g, ' ').trim().slice(0, 40) || 'Download PDF';
            await pr.click({ timeout: 8000 }).catch(() => {});
            // the export renders on the platform's PDF service (a cold container can take ~45s) and falls back to the
            // in-page exporter; either way the person is handed a FILE, so wait for one - or a print call - up to 60s
            for (let i = 0; i < 60 && !printed; i++) {
              await page.waitForTimeout(1000);
              const called = await page.evaluate(() => !!window.__w4Printed).catch(() => false);
              printed = called || downloads > d0 || popups > p0;
              if (printed) how = called ? `"${label}" called window.print` : downloads > d0 ? `"${label}" handed over a file (download)` : `"${label}" opened a print window`;
            }
            if (!printed) {
              const said = await page.evaluate(() => { const t = document.getElementById('toast'); return t ? (t.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 100) : ''; }).catch(() => '');
              how = `"${label}" pressed, no file and no print in 60s` + (said ? ` (the page said "${said}")` : '');
            }
          }
          actResult[t.id] = { ok: !!worked && !!wallUrl && wallCarries && signedUp && arrived && !!selected && res.chars >= 80 && !res.bad && printed,
            detail: `${p}: worked example ${worked ? 'present (' + worked.length + ' chars)' : 'MISSING'}; "${href}" -> ${notes.join('; ')}; `
              + `calculator ${arrived ? 'reached' : 'NOT reached'}${selected ? ', "' + selected + '" preselected' : ', nothing preselected'}; ${filled} empty field(s) filled; `
              + `${addedRows ? addedRows + ' row(s) added with the form\'s own Add; ' : ''}${bumpedCounts ? bumpedCounts + ' zero count field(s) set to 2; ' : ''}${retriedAfter ? 'Run pressed again on the page\'s own advice ("' + retriedAfter.slice(0, 70) + '"); ' : ''}Run${enabled ? 'pressed' : 'never enabled'} (${calcCalls} calculation request${calcCalls === 1 ? '' : 's'}, no model call); result ${res.chars} chars${res.bad ? ' with NaN/Infinity/undefined' : ''}${res.head ? ' ("' + res.head.slice(0, 60) + '")' : ''}${firstSaid ? ' (the page said "' + firstSaid + '")' : ''}; ${how}` };
          await page.context().unroute(calcPat, calcRoute).catch(() => {});
          await page.goto(back, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
          await page.waitForTimeout(1500);
        } catch (err) {
          actResult[t.id] = { ok: false, detail: 'the compute walk threw on ' + p + ': ' + String(err.message || err).split('\n')[0].slice(0, 100) };
          // the walk's no-model route lives on the CONTEXT, which outlives this page: never leave it for another walker
          await page.context().unroute('**/functions/v1/engineering-calc-agent**').catch(() => {});
        }
      }
      for (const t of acts.filter((x) => x.kind === 'learn-cta' && p === pages[0] && !actResult[x.id])) {
        try {
          const subject = String(t.subject || '');
          const spec = (() => {
            if (subject.startsWith('named-tool:')) { const target = subject.slice(11); return { mode: 'path', tpath: target.split('?')[0].split('#')[0], tquery: target.includes('?') ? target.slice(target.indexOf('?')).split('#')[0] : '', label: target }; }
            if (subject.startsWith('named-calculator:')) return { mode: 'path', tpath: '/tools/' + subject.slice(17) + '/', tquery: '', label: '/tools/' + subject.slice(17) + '/' };
            if (subject.startsWith('related-guide:')) return { mode: 'path', tpath: '/learn/' + subject.slice(14) + '/', tquery: '', label: '/learn/' + subject.slice(14) + '/' };
            if (subject === 'sign-up') return { mode: 'signup', tpath: '', tquery: '', label: 'the sign-up line (?signup=1)' };
            if (subject === 'open-workhive') return { mode: 'home', tpath: '', tquery: '', label: 'the landing page (.lh-cta)' };
            return { mode: 'path', tpath: subject, tquery: '', label: subject };
          })();
          const here = page.url();
          const found = await page.evaluate(({ mode, tpath, tquery }) => {
            // ★"/" IS THE ROOT, NOT "ANY PATH ENDING IN A SLASH" (CGW41133, 2026-10-08): the guide whose tool is the
            // platform itself named `named-tool:/`, and endsWith('/') matched every directory URL - the walker picked
            // the hidden "Skip to main content" link. A same-page anchor is never the tool; "/" means the root itself.
            const matches = (a) => { let u; try { u = new URL(a.href, location.href); } catch (e) { return false; }
              if ((a.getAttribute('href') || '').startsWith('#')) return false;
              const rootPath = u.pathname.replace(/^\/workhive/, '') || '/';
              if (mode === 'path' && tpath === '/') return /^\/(index\.html)?$/.test(rootPath) && (!tquery || u.search === tquery);
              if (mode === 'signup') return /[?&]signup=1/.test(u.search);
              if (mode === 'home') return (!!a.closest('.lh-cta, [class*="lh-cta"]') || /open workhive|start free|get started|simulan/i.test(a.textContent || '')) && /\/(index\.html)?$/.test(u.pathname);
              const pth = u.pathname; const ok = pth.endsWith(tpath) || (tpath.endsWith('/') && pth.endsWith(tpath + 'index.html')); return ok && (!tquery || u.search === tquery); };
            const cands = [...document.querySelectorAll('a[href]')].filter(matches);
            const vis = (a) => { const r = (a.getClientRects && a.getClientRects()[0]) || a.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(a).visibility !== 'hidden'; };
            const m = (mode === 'signup' ? cands.find((a) => a.closest('.cta-secondary') && vis(a)) : null) || cands.find(vis) || cands[0];
            if (!m) return { exists: false };
            m.scrollIntoView({ block: 'center' });
            const r = (m.getClientRects && m.getClientRects()[0]) || m.getBoundingClientRect();
            const hit = document.elementFromPoint(Math.min(innerWidth - 1, r.left + r.width / 2), Math.min(innerHeight - 1, r.top + r.height / 2));
            document.querySelectorAll('[data-w4-cta]').forEach((x) => x.removeAttribute('data-w4-cta'));
            m.setAttribute('data-w4-cta', '1');
            return { exists: true, href: m.getAttribute('href'), text: (m.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 60),
              reachable: !!hit && (hit === m || m.contains(hit)), hit: hit ? (hit.id ? '#' + hit.id : hit.tagName.toLowerCase() + (hit.className && typeof hit.className === 'string' ? '.' + hit.className.split(' ')[0] : '')) : null };
          }, spec).catch(() => ({ exists: false }));
          if (!found.exists) { actResult[t.id] = { ok: false, detail: `no link to ${spec.label} on ${p}` }; continue; }
          await page.click('a[data-w4-cta="1"]', { timeout: 8000 }).catch(() => {});
          const arrived = await page.waitForURL((u) => {
            if (spec.mode === 'signup') return /[?&]signup=1/.test(u.search) && /(^|\/)(index\.html)?$/.test(u.pathname.replace(/^\/workhive/, ''));
            if (spec.mode === 'home') return /\/(index\.html)?$/.test(u.pathname);
            if (spec.tpath === '/') return /^\/(index\.html)?$/.test(u.pathname.replace(/^\/workhive/, '') || '/') && (!spec.tquery || u.search === spec.tquery);
            const pth = u.pathname; return (pth.endsWith(spec.tpath) || (spec.tpath.endsWith('/') && pth.endsWith(spec.tpath + 'index.html'))) && (!spec.tquery || u.search === spec.tquery);
          }, { timeout: 20000 }).then(() => true).catch(() => false);
          // ★ARRIVING IS NOT ENOUGH IF THE ARRIVAL IS A DEAD END (CGW41004, 2026-10-08): PH Intelligence told a stranger
          // "Join or create a hive" and offered only Home and Back. A short arrival (a gate, an empty state) must carry
          // a FORWARD control - sign in, create, join, go to, open, start - or the person followed the guide into a wall.
          await page.waitForTimeout(2500);
          const landed = await page.evaluate(() => {
            const vis = (e) => e.checkVisibility && e.checkVisibility({ opacityProperty: true, visibilityProperty: true });
            const chrome = /^(skip|back|home|close|\u00d7|x|menu|read the guide|new to this page)/i;
            const fwd = /sign in|sign up|create|join|go to|open|start|get started|try|calculate|compute|continue|add |log |mag-sign|gumawa|sumali|buksan/i;
            const ctl = [...document.querySelectorAll('a[href], button')].filter(vis)
              .map((e) => (e.innerText || e.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim()).filter(Boolean);
            return { chars: (document.body.innerText || '').replace(/\s+/g, ' ').trim().length, title: document.title.slice(0, 60),
              forward: ctl.filter((x) => !chrome.test(x) && fwd.test(x)).slice(0, 4), controls: ctl.slice(0, 8) };
          }).catch(() => ({ chars: 0, title: '', forward: [], controls: [] }));
          const deadEnd = arrived && landed.chars < 1500 && !landed.forward.length;
          actResult[t.id] = { ok: found.reachable && arrived && landed.chars > 200 && !deadEnd,
            detail: `CTA "${found.text}" on ${p} ${found.reachable ? 'reachable at its centre' : 'COVERED by ' + found.hit}; ${arrived ? `arrived at ${spec.label} ("${landed.title}", ${landed.chars} chars)` : 'did not arrive at ' + spec.label + ' in 20s'}`
              + (deadEnd ? `; a DEAD END - no forward control (only: ${landed.controls.join(' | ') || 'none'})` : (landed.chars < 1500 && landed.forward.length ? `; the way forward: ${landed.forward.join(' | ')}` : '')) };
          await page.goto(here, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
          await page.waitForTimeout(1500);
        } catch (err) {
          actResult[t.id] = { ok: false, detail: 'the CTA step threw on ' + p + ': ' + String(err.message || err).split('\n')[0].slice(0, 100) };
        }
      }
      for (const t of acts.filter((x) => x.kind === 'write' && !x.last && x.recipe && (x.recipe.page || x.subjectPage) === p && !actResult[x.id])) {
        const astray0 = hiveAstray;   // pressed while the cast sat outside its hive: this row carries that
        try { actResult[t.id] = await runRecipe(t, p); }
        catch (err) { actResult[t.id] = { ok: false, detail: 'the recipe threw on ' + p + ': ' + String(err.message || err).split('\n')[0].slice(0, 100) }; }
        if (astray0 && actResult[t.id]) actResult[t.id].astray = astray0;
        // a write that moved the active hive (joining or creating one makes it active) is put back the way the person
        // puts it back - the switcher - before the next row meets a page reading the wrong hive
        if (P.castHive && (await activeHive()) !== P.castHive) await ensureHive('after ' + t.subject);
        // the page a person is left holding after the write is what the next row meets: reload it
        await page.goto(`${origin}/${p}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
        await page.waitForTimeout(2000);
      }
      for (const t of acts.filter((x) => (x.kind === 'print' || x.kind === 'cta')
                                      && (x.subjectPage || pages[pages.length - 1]) === p && !actResult[x.id])) {
        try {
          if (t.kind === 'print') {
            // ★PRINT OR EXPORT, AND READ WHAT CAME OUT (2026-10-09). The rows say "print or export this page and read the
            // artifact". audit-log, logbook and asset-hub export CSV; hive exports what it holds from its menu; analytics-
            // report prints only after Generate; resume's Download PDF lives in its preview. So the walk takes the step a
            // person takes first - Generate when the control is still disabled, Preview or the page's menu when it is
            // hidden - presses, and READS the file: a download that comes back empty is not an export.
            const PRINT_RE = /print|download pdf|export pdf|save as pdf|i-print|\bpdf\b|export|\bcsv\b/i;
            const labelOf = async (el) => [await el.textContent().catch(() => ''), await el.getAttribute('aria-label').catch(() => ''),
              await el.getAttribute('title').catch(() => '')].map((s) => String(s || '')).join(' ').replace(/\s+/g, ' ').trim();
            const findBy = async (re, skip) => {
              const all = page.locator('button, a, [role="button"], [role="menuitem"]');
              const n = Math.min(await all.count().catch(() => 0), 400);
              for (let i = 0; i < n; i++) {
                const el = all.nth(i);
                if (!(await el.isVisible().catch(() => false))) continue;
                const txt = await labelOf(el);
                if (re.test(txt) && !(skip && skip.test(txt))) return { el, txt };
              }
              return null;
            };
            // "Preview & Export" OPENS the export (resume) - it is an opener below, not the control itself
            const NOT_THIS_PAGE = /import|qr tag|choose a .*file|\bpreview\b/i;
            const steps = [];
            let found = await findBy(PRINT_RE, NOT_THIS_PAGE);
            if (!found) {   // hidden: a preview dialog, then the page's own menu
              for (const opener of [/\bpreview\b/i, /\bmore\b|\bmenu\b|more options|⋮|⋯/i]) {   // hive: "⋯ More"
                const o = await findBy(opener, /close|import/i);
                if (!o) continue;
                await o.el.click({ timeout: 8000 }).catch(() => {});
                await page.waitForTimeout(1500);
                steps.push(`opened "${o.txt.slice(0, 30)}"`);
                found = await findBy(PRINT_RE, NOT_THIS_PAGE);
                if (found) break;
              }
            }
            if (!found) {
              actResult[t.id] = { ok: false, detail: `no visible print or export control on ${p}${steps.length ? ' (after ' + steps.join(', ') + ')' : ''}` };
              continue;
            }
            if (!(await found.el.isEnabled().catch(() => true))) {   // a report that is not generated yet cannot be printed
              const g = await findBy(/^\s*(generate|build|create|run)\b/i, /close/i);
              if (g) {
                await g.el.click({ timeout: 8000 }).catch(() => {});
                steps.push(`pressed "${g.txt.slice(0, 30)}" first`);
                for (let i = 0; i < 60 && !(await found.el.isEnabled().catch(() => false)); i++) await page.waitForTimeout(1000);
              }
            }
            const label = found.txt.slice(0, 50);
            const d0 = downloads, p0 = popups;
            await page.evaluate(() => { window.__w4Printed = false; }).catch(() => {});
            await found.el.click({ timeout: 8000 }).catch(() => {});
            let printed = false;
            for (let i = 0; i < 30 && !printed && downloads === d0 && popups === p0; i++) {
              await page.waitForTimeout(1000);
              printed = await page.evaluate(() => !!window.__w4Printed).catch(() => false);
            }
            let artifact = '';
            if (downloads > d0 && lastDownload) {
              try {
                const stream = await lastDownload.createReadStream();
                const chunks = []; let size = 0;
                for await (const c of stream) { chunks.push(c); size += c.length; if (size > 65536) break; }
                const head = Buffer.concat(chunks).toString('utf8').replace(/\s+/g, ' ').trim();
                artifact = `${lastDownload.suggestedFilename()} (${size} bytes${size > 65536 ? '+' : ''}): "${head.slice(0, 90)}"`;
                if (!size) artifact = 'EMPTY ' + artifact;
              } catch (e) { artifact = 'the download could not be read: ' + String(e.message || e).slice(0, 60); }
            }
            const okFile = downloads > d0 && artifact && !/^EMPTY|could not be read/.test(artifact);
            actResult[t.id] = { ok: printed || okFile || popups > p0,
              detail: `${steps.length ? steps.join(', ') + '; ' : ''}"${label}" on ${p}: ${printed ? 'window.print was called'
                : downloads > d0 ? 'the file came down and was read - ' + artifact
                : popups > p0 ? 'a print/PDF window opened' : 'neither window.print, a download nor a window followed in 30s'}` };
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
            // ★"FIND A GUIDE" IS A SEARCH, NOT A BUTTON (2026-10-09). The seeder names this action when the learn hub has
            // its search box (lh-search) or "more guides" (lh-more); no control is labelled "find-a-guide". A person finds
            // a guide by typing a word of their trade - the walk types "pump" and reads whether the list answered.
            if (want === 'find a guide') {
              const box = page.locator('#lh-search');
              if (await box.isVisible().catch(() => false)) {
                const cards = () => page.evaluate(() => [...document.querySelectorAll('a[href*="/learn/"], a[href*="learn/"]')]
                  .filter((a) => a.checkVisibility({ opacityProperty: true, visibilityProperty: true })).length).catch(() => -1);
                const n0 = await cards();
                await box.fill('pump').catch(() => {});
                await box.dispatchEvent('input').catch(() => {});
                await page.waitForTimeout(2500);
                const n1 = await cards();
                actResult[t.id] = { ok: n1 > 0 && n1 !== n0,
                  detail: `typed "pump" into "Search guides" on ${p}: ${n0} guide link(s) shown before, ${n1} after` };
                continue;
              }
            }
            let found = await find();
            // a control that only EXISTS after the page has done something (Generate / Save on the calc
            // workbench) gets one reveal attempt before the row is called open - and the receipt says so
            if (!found) { await reveal(p); found = await find(); if (found) out.revealed = (out.revealed || 0) + 1; }
            // ★"THE PAGE'S PRIMARY LINK" WHEN NOTHING IS CLASSED PRIMARY (2026-10-09). The seeder wrote this subject for
            // pages with no CTA class. A first heuristic ("the first FILLED control") picked a header Back button on
            // ai-quality and public-feed and the SELECTED "24h" filter chip on audit-log - chrome and state, not an
            // action. The page's primary link is the first BUTTON-STYLED action in its MAIN content, in reading order:
            // never header/nav/the hub chrome, a tab or filter chip, a selected toggle, back/home/close, or anything
            // that signs out, deletes or resets. A page with none says so, and a stranger falls to the sign-up below.
            if (!found && generic) {
              const idx = await page.evaluate(() => {
                const SKIP = /sign ?out|log ?out|delete|remove|deactivate|reset|discard|leave|^back\b|back to|^home$|^close$|skip to|search|companion|feedback|menu|^more$/i;
                const scope = document.querySelector('main, [role="main"], #main, #main-content') || document.body;
                const els = [...document.querySelectorAll('button, a[href], [role="button"], input[type="submit"]')];
                for (let i = 0; i < els.length; i++) {
                  const e = els[i];
                  if (!scope.contains(e) || !e.checkVisibility({ opacityProperty: true, visibilityProperty: true })) continue;
                  if (e.closest('header, nav, [role="banner"], [role="navigation"], [role="tablist"], [class*="wh-hub"], [class*="chip"], [class*="filter"]')) continue;
                  if (e.getAttribute('role') === 'tab' || e.hasAttribute('aria-pressed') || e.getAttribute('aria-selected') === 'true' || e.getAttribute('aria-current')) continue;
                  const txt = (e.innerText || e.value || e.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim();
                  if (!txt || SKIP.test(txt)) continue;
                  const cs = getComputedStyle(e), r = e.getBoundingClientRect();
                  const filled = (String(cs.backgroundColor).match(/[\d.]+/g) || []).length >= 3 && !/rgba\(0, 0, 0, 0\)|transparent/.test(cs.backgroundColor);
                  const bordered = parseFloat(cs.borderTopWidth) > 0 && !/rgba\(0, 0, 0, 0\)/.test(cs.borderTopColor);
                  if ((filled || bordered || cs.backgroundImage !== 'none') && r.height >= 32 && parseFloat(cs.paddingLeft) >= 6) return i;
                }
                return -1;
              }).catch(() => -1);
              if (idx >= 0) {
                const el = page.locator('button, a[href], [role="button"], input[type="submit"]').nth(idx);
                found = { el, label: normL((await el.textContent().catch(() => '')) || '').slice(0, 40) + ' (the first button-styled action in the main content)' };
              }
            }
            // ...and a page with nothing emphasised at all (about, privacy, terms): a STRANGER's primary action on any
            // public page is the platform's own sign-up link, which every public header carries
            if (!found && generic && anon) {
              const su = page.locator('a[href*="signup=1"]:visible, a:visible:has-text("Sign Up"), button:visible:has-text("Sign Up")').first();
              if (await su.count().catch(() => 0)) found = { el: su, label: normL((await su.textContent().catch(() => '')) || '').slice(0, 40) + ' (a stranger\'s primary action: sign up)' };
            }
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
        // ★STOP THE LAST WALK'S SERVICE WORKER FIRST (2026-10-09). Clearing the origin deletes the worker's REGISTRATION, not
        // the worker already running: each walk left one orphaned service-worker process holding the shell it had
        // precached. 110 CA walks reached 115 processes and 13.4 GB committed - the host hit its commit limit (32.4 of
        // 32.6 GB) and a Python bank step died with MemoryError. Stopping every worker before the clear ends that.
        try { await cdp0.send('ServiceWorker.enable'); await cdp0.send('ServiceWorker.stopAllWorkers'); await cdp0.send('ServiceWorker.disable'); }
        catch (e) { void e; }
        // ★AN ANONYMOUS READER WHO WAS STILL SIGNED IN (CGW41001, 2026-10-08): the MCP's browser keeps localStorage across
        // walks, so a walk after a signed-in one read the landing page as Bryan Garcia (802 chars, not the 14,676 a
        // stranger sees). Every walk starts from a clean origin: its storage, cookies and session, not only the shell.
        // ★NOT 'all' (2026-10-09): Chrome's BROWSER process crashed 7 times (Crashpad ptype=browser), each on the first walk
        // after a fresh launch. 'all' also clears the GPU shader cache, interest groups, shared storage and storage
        // buckets - none of them app state - and the dumps carry the GPU's crash keys. The app's own state is the list below.
        await cdp0.send('Storage.clearDataForOrigin', { origin: origin.replace(/\/workhive\/?$/, ''),
          storageTypes: 'cookies,local_storage,indexeddb,cache_storage,service_workers,websql,file_systems' });
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
      if (!anon && P.signup) {
        // ★A NEWCOMER IS MADE THROUGH THE SIGN-UP FORM, NOT SEEDED (2026-10-08). set_worker_display_name refuses anyone
        // who already holds a hive membership (HIVE_NAME_HAS_HISTORY), and every cast member holds one - so its story is
        // a NEW person's: they create an account (index.html?signup=1, the page's own submitSignUp) and then join a hive
        // whose roster already answers to their name. The account is born here and removed by the driver's reversal.
        await page.goto(`${origin}/index.html?signup=1`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
        await page.waitForSelector('#su-username', { state: 'visible', timeout: 30000 }).catch(() => {});
        await page.fill('#su-username', P.user || '', { timeout: 8000 }).catch(() => {});
        await page.fill('#su-displayname', P.castName || '', { timeout: 8000 }).catch(() => {});
        await page.fill('#su-password', P.pass || 'test1234', { timeout: 8000 }).catch(() => {});
        await page.fill('#su-confirm', P.pass || 'test1234', { timeout: 8000 }).catch(() => {});
        await page.click('#su-btn', { timeout: 10000 }).catch(() => {});
        const hasSess = () => page.evaluate(() => Object.keys(localStorage).some((k) => /^sb-.*-auth-token$/.test(k) && /access_token/.test(localStorage.getItem(k) || ''))).catch(() => false);
        let sess = false;
        for (let i = 0; i < 30 && !sess; i++) { sess = await hasSess(); if (!sess) await page.waitForTimeout(1000); }
        out.signedUp = sess;
        if (!sess) {
          const err = await page.evaluate(() => ((document.getElementById('su-error') || {}).textContent || '').trim().slice(0, 120)).catch(() => '?');
          out.problems.push('no session after the wall (the sign-up did not produce one: ' + err + ')');
        } else await page.waitForTimeout(2500);
      } else if (!anon) {
        await page.goto(`${origin}/index.html?signin=1&return=${first}`, { waitUntil: 'load', timeout: 30000 });
        await page.waitForSelector('#si-username', { state: 'visible', timeout: 45000 }).catch(() => {});
        if (await page.locator('#si-username').isVisible().catch(() => false)) {
          // a confusion met AT the wall (C1 C13 C15 C24) is lived here, before the cast types anything
          for (const t of confActs.filter((x) => (CONF[x.subject] || {}).stage === 'wall' && CONF[x.subject].run)) {
            actResult[t.id] = await runConf(t);
          }
          const wr = await read();
          out.steps.push({ page: 'index.html', chars: wr.chars, identityKept: true, lang: wr.lang,
                           fit: compact(await A('index.html wall at ' + VP.w)) });
          // C2 (a slow login: the still-signing-in hint must show by 8 s) and C3 (one 503 "name resolution failed": the
          // plain outage sentence must show) are lived through the login POST itself - an in-page fetch wrapper, because the
          // service worker carries the request and a route never sees it. The page's next navigation drops the wrapper.
          const c2 = confActs.find((x) => x.subject === 'C2'), c3 = confActs.find((x) => x.subject === 'C3');
          if (c2 || c3) {
            await page.evaluate(({ slow, fail }) => {
              if (window.__whW4Fetch) return;
              const orig = window.fetch.bind(window); window.__whW4Fetch = orig; let failed = false;
              window.fetch = async (input, init) => {
                const url = typeof input === 'string' ? input : ((input && input.url) || '');
                const method = String((init && init.method) || (input && input.method) || 'GET').toUpperCase();
                if (/\/functions\/v1\/login(\?|$)/.test(url) && method === 'POST') {
                  if (fail && !failed) { failed = true; return new Response(JSON.stringify({ message: 'name resolution failed' }), { status: 503, headers: { 'Content-Type': 'application/json' } }); }
                  if (slow) await new Promise((r) => setTimeout(r, 10000));
                }
                return orig(input, init);
              };
            }, { slow: !!c2, fail: !!c3 }).catch(() => {});
          }
          await page.fill('#si-username', P.user || '', { timeout: 8000 });
          await page.fill('#si-password', P.pass || 'test1234', { timeout: 8000 });
          await page.click('#si-btn', { timeout: 10000 }).catch(async () => {
            out.problems.push('the sign-in submit did not become clickable in 10s; pressed Enter instead');
            await page.press('#si-password', 'Enter', { timeout: 4000 }).catch(() => {});
          });
          if (c2) {
            await page.waitForTimeout(9500);
            const hint = await page.evaluate(() => { const e = document.getElementById('si-error'); return e && !e.classList.contains('hidden') ? (e.textContent || '').trim() : ''; }).catch(() => '');
            actResult[c2.id] = { ok: /still signing in|nagsa-sign in pa/i.test(hint), detail: hint ? `at 9.5 s the wall said "${hint.slice(0, 80)}"` : 'at 9.5 s the wall said nothing' };
          }
          if (c3) {
            for (let i = 0; i < 30; i++) { const said = await page.evaluate(() => { const e = document.getElementById('si-error'); return e && !e.classList.contains('hidden') ? (e.textContent || '').trim() : ''; }).catch(() => ''); if (said) break; await page.waitForTimeout(500); }
            const said = await page.evaluate(() => { const e = document.getElementById('si-error'); return e ? (e.textContent || '').trim() : ''; }).catch(() => '');
            actResult[c3.id] = { ok: !/name resolution|upstream|gateway/i.test(said) && /temporarily unavailable|pansamantala|try again/i.test(said), detail: `after a 503 "name resolution failed" the wall said "${said.slice(0, 90)}"` };
            await page.evaluate(() => { if (window.__whW4Fetch) { window.fetch = window.__whW4Fetch; delete window.__whW4Fetch; } }).catch(() => {});
            await page.click('#si-btn', { timeout: 10000 }).catch(() => page.press('#si-password', 'Enter').catch(() => {}));
          }
          try { await page.waitForURL(atPath(first), { timeout: 30000 }); }
          catch (e) {
            const err = await page.evaluate(() => ((document.getElementById('si-error') || {}).textContent || '').trim().slice(0, 120)).catch(() => '?');
            out.problems.push('sign-in did not reach ' + first + ' in 30s: ' + err);
          }
          // ★A PATH THAT STARTS ON THE LANDING PAGE PROVES NOTHING BY ITS URL (WGW4118, 2026-10-08): the wall lives on
          // index.html, so "reached index.html" was true before the sign-in had done anything, and the whole walk ran
          // signed out - every page showed the landing's 14,680 chars. The proof is a SESSION: an auth token in
          // storage. Waited for, retried once through the wall, and a problem if it never comes.
          const hasSession = () => page.evaluate(() => Object.keys(localStorage).some((k) => /^sb-.*-auth-token$/.test(k) && /access_token/.test(localStorage.getItem(k) || ''))).catch(() => false);
          let sess = false;
          for (let i = 0; i < 30 && !sess; i++) { sess = await hasSession(); if (!sess) await page.waitForTimeout(1000); }
          if (!sess) {
            await page.goto(`${origin}/index.html?signin=1&return=${first}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
            await page.waitForSelector('#si-username', { state: 'visible', timeout: 30000 }).catch(() => {});
            await page.fill('#si-username', P.user || '', { timeout: 8000 }).catch(() => {});
            await page.fill('#si-password', P.pass || 'test1234', { timeout: 8000 }).catch(() => {});
            await page.click('#si-btn', { timeout: 10000 }).catch(() => page.press('#si-password', 'Enter').catch(() => {}));
            for (let i = 0; i < 40 && !sess; i++) { sess = await hasSession(); if (!sess) await page.waitForTimeout(1000); }
            out.signinRetried = true;
          }
          if (!sess) out.problems.push('no session after the wall (tried twice) - the walk would run signed out, so it stops here');
          else await page.waitForTimeout(1500);
        }
      }
      if (!anon && out.problems.some((x) => /^no session after the wall/.test(x))) throw new Error('signed out');
      if (!anon && acts.some((x) => x.kind === 'write')) await ensureHive('arrival');

      // ── walk the path, one page at a time, the overlap record after each ─────────────────────
      for (const p of pages) {
        current = p;
        // ★THE PATH, NOT ITS LAST PART (CGW41001, 2026-10-08): every guide is .../learn/<slug>/index.html, so the
        // basename of a guide page IS "index.html" - a path guide -> guide -> index.html never left the second guide,
        // and its receipt recorded the landing page with the guide's 7,908 chars. Compare the path under the origin.
        const here = await page.evaluate(() => location.pathname.replace(/^\/workhive\//, '').replace(/^\//, '')).catch(() => '');
        if (here !== p && here + 'index.html' !== p) {
          await page.goto(`${origin}/${p}`, { waitUntil: 'load', timeout: 60000 })
            .catch((err) => out.problems.push(`${p}: ${String(err.message).split('\n')[0].slice(0, 80)}`));
        }
        await page.waitForTimeout(3500);
        let r = await read(); let looks = 0;
        while (r.chars < 300 && looks < 2) { await page.waitForTimeout(2500); r = await read(); looks++; }
        // press this page's own controls BEFORE the overlap record, so the record describes the page a
        // person is left holding - and so a cta that navigates is walked from here, not from a later page
        await actOn(p);
        // ★EACH PREDICATE MEETS ITS OWN PAGE (2026-10-12). The prover gave every row a fresh context; here up to 27 share
        // one walk, and some predicates leave the page (C25 opens the landing page, C27 a calculator deep link) - so
        // each starts on its target, reloaded if a sibling moved it, and the page is put back before its overlap record.
        const atP = async () => {
          const here = await page.evaluate(() => location.pathname.replace(/^\/workhive\//, '').replace(/^\//, '')).catch(() => '');
          if (here !== p) { await page.goto(`${origin}/${p}`, { waitUntil: 'load', timeout: 60000 }).catch(() => {}); await page.waitForTimeout(3500); }
        };
        for (const t of confActs.filter((x) => x.target === p && !actResult[x.id] && (CONF[x.subject] || {}).stage === 'page' && CONF[x.subject].run)) {
          await atP();
          actResult[t.id] = await runConf(t);
          await confCtx.closeAll();
          await page.context().setOffline(false).catch(() => {});   // an offline predicate that threw must not strand the walk
          await atP();
          // AT REST MEANS AT REST (the prover, 2026-09-14): a predicate's reach probe scrolls; the overlap record must not
          await page.evaluate(() => window.scrollTo(0, 0)).catch(() => {});
          await page.waitForTimeout(300);
        }
        r = await read();
        out.steps.push({ page: p, viewport: P.device || (VP.w + 'px'), chars: r.chars, lang: r.lang,
                         // a person who RENAMED themselves on this walk (set_worker_display_name) is still the same
                         // person under the name they chose: P.castAliases, set by the write driver only
                         identityKept: anon ? true : (r.worker === (P.castName || r.worker) || (P.castAliases || []).includes(r.worker)),
                         fit: compact(await A(`${p} at ${P.device || VP.w}`)) });
      }
      // ★A WRITE THAT ENDS THE PERSON'S SESSION GOES LAST (2026-10-08). deactivate_my_account anonymises the account,
      // marks every membership deactivated and clears the page's storage - pressed mid-path it would sign out every
      // page after it and the walk would record a stranger. A recipe flagged `last` is pressed after the whole path
      // has been walked and recorded, on its own page (the driver restores the account when it banks).
      // ★AND SO DOES A WRITE THAT MOVES THE ACTIVE HIVE (WGW446, 2026-10-08). Leaving a hive, joining one by code and
      // creating one each leave the person in a DIFFERENT hive; pressed mid-path, every row after them ran outside
      // the cast's hive. They carry a numeric `last` (the order among them: leave 1, join 2, create 3, deactivate 9),
      // and each starts from the cast's own hive, put back through the switcher as after any write.
      // ★A RECIPE WHOSE PAGE IS NOT ON THE PATH IS PRESSED AFTER IT (2026-10-12, WGW4604). The driver prints "walked
      // anyway, the page is visited for it" for a recipe page off the row's path (a platform admin's triage on
      // platform-actions.html, for a feedback row whose journey never opens it) - but only `last` writes were ever
      // visited after the path, so these rows came back "the recipe's page was not reached". They are pressed on
      // their own page once the path is walked, from the cast's own hive, exactly like a `last` write.
      const offActs = acts.filter((x) => x.kind === 'write' && !x.last && x.recipe && !actResult[x.id]
        && !pages.includes(x.recipe.page || x.subjectPage));
      for (const t of offActs) {
        const lp = t.recipe.page || t.subjectPage;
        if (P.castHive && (await activeHive()) !== P.castHive) await ensureHive('before ' + t.subject);
        current = lp;
        await page.goto(`${origin}/${lp}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
        await page.waitForTimeout(3500);
        try { actResult[t.id] = await runRecipe(t, lp); }
        catch (err) { actResult[t.id] = { ok: false, detail: 'the recipe threw on ' + lp + ': ' + String(err.message || err).split('\n')[0].slice(0, 100) }; }
        if (actResult[t.id]) actResult[t.id].offPath = true;
      }
      const lastActs = acts.filter((x) => x.kind === 'write' && x.last && x.recipe && !actResult[x.id])
        .sort((a, b) => (Number(a.last) || 1) - (Number(b.last) || 1));
      for (const t of lastActs) {
        const lp = t.recipe.page || t.subjectPage;
        if (P.castHive && (await activeHive()) !== P.castHive) await ensureHive('before ' + t.subject);
        const astray0 = hiveAstray;
        current = lp;
        await page.goto(`${origin}/${lp}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
        await page.waitForTimeout(3500);
        try { actResult[t.id] = await runRecipe(t, lp); }
        catch (err) { actResult[t.id] = { ok: false, detail: 'the recipe threw on ' + lp + ': ' + String(err.message || err).split('\n')[0].slice(0, 100) }; }
        if (actResult[t.id]) { actResult[t.id].afterPath = true; if (astray0) actResult[t.id].astray = astray0; }
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
          const v = fillArg(nm, ctxVals, subj);
          if (v === NULL_ARG) body[nm] = null;
          else if (v === undefined || v === null) missing.push(nm); else body[nm] = v;
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
      } else if (t.kind === 'compute') {
        pred = actResult[t.id] || { ok: false, detail: `the guide ${pages[0]} was not reached` };
        observed = actResult[t.id] || null;
      } else if (t.kind === 'layer-ca') {
        const ar = actResult[t.id];
        pred = ar || { ok: false, detail: `the subject page ${t.subjectPage} was not reached on this path` };
        observed = ar || null;
        const occ = out.steps.find((s) => s.fit && (s.fit.occlusion || []).length);
        if (occ && pred.ok) pred = { ok: false, detail: pred.detail + `; overlap at "${occ.page}": ` + (occ.fit.occlusion || []).slice(0, 2).join(' | ') };
      } else if (t.kind === 'learn-cta') {
        pred = actResult[t.id] || { ok: false, detail: `the guide ${pages[0]} was not reached` };
        observed = actResult[t.id] || null;
      } else if (t.kind === 'write') {
        const ar = actResult[t.id];
        observed = ar || null;
        if (ar && ar.hit) effect = { request: `${ar.hit.method} ${String(ar.hit.url).split('?')[0]} ${ar.hit.status}`, page: ar.hit.page, mark: t.mark || MARK, told: ar.told || '' };
        pred = ar || { ok: false, detail: t.recipe ? `the recipe's page ${(t.recipe || {}).page} was not reached on this path` : 'no recipe for this write' };
      } else if (t.kind === 'confusion') {
        // the predicate's own answer; an overlap at any step keeps the row open (the prover's rule)
        pred = actResult[t.id] || (CONF[subj] && (CONF[subj].run || ['C2', 'C3'].includes(subj))
          ? { ok: false, detail: `${subj}: its page ${t.target} was never reached on this path` }
          : { ok: false, detail: `no predicate for ${subj} yet - the confusion was not lived` });
        observed = actResult[t.id] || null;
        const occ = out.steps.find((s) => s.fit && (s.fit.occlusion || []).length);
        if (occ && pred.ok) pred = { ok: false, detail: pred.detail + `; overlap at "${occ.page}": ` + (occ.fit.occlusion || []).slice(0, 2).join(' | ') };
      } else if (t.kind === 'print' || t.kind === 'cta') {
        pred = actResult[t.id] || { ok: false,
          detail: `the subject page ${t.subjectPage || '(unknown)'} was not reached on this path` };
        observed = actResult[t.id] || null;
      } else {
        pred = { ok: false, detail: `no walker yet for action kind ${t.kind} - this walk records the path and the responses, so adding it costs no re-walk` };
      }
      const rowProblems = out.problems.slice();
      // a write pressed while the cast sat outside its hive (ensureHive) - unless that already reached every row
      if (t.kind === 'write' && actResult[t.id] && actResult[t.id].astray && !rowProblems.includes(actResult[t.id].astray)) rowProblems.push(actResult[t.id].astray);
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
    for (const [pat, h] of ctxRoutes) { try { await page.context().unroute(pat, h); } catch (e) { void e; } }
    if (perms.length) { try { await page.context().clearPermissions(); } catch (e) { void e; } }

    // ── hand the record to the seeder (the MCP vm cannot write a file; its request context can POST) ──
    try {
      const res = await page.request.post('http://localhost:5000/api/w4/steps', {
        data: { id: P.id, steps: out.steps, records: { records: out.records, answers: out.answers, direct: out.direct, provenance, pages, axis: P.axis, cast: out.cast,
                                                         hiveSwitches: out.hiveSwitches || [], problems: out.problems } },
        timeout: 10000,
      });
      out.wrote = res.ok() ? (await res.json()).path : `POST /api/w4/steps -> ${res.status()}`;
    } catch (e) { out.problems.push('could not POST the record: ' + String(e.message || e).slice(0, 80)); }

    return { id: out.id, wrote: out.wrote, cast: out.cast, pages, axis: P.axis, problems: out.problems, hiveSwitches: out.hiveSwitches || [],
             distinctPages: distinct, identityKept: idKept, hits: hits.length, provenance,
             steps: out.steps.map((s) => ({ page: s.page, chars: s.chars, lang: s.lang, identityKept: s.identityKept,
                                            findings: s.fit && s.fit.findings, occlusion: s.fit && s.fit.occlusion })),
             answers: Object.values(out.answers).map((a) => ({ id: a.id, ok: a.ok, note: a.note })) };
  }
}
