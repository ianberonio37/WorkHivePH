// lm_walk_leo_block.js - the LM-L (Latency & waiting), LM-E (Evals & quality gates) and LM-O (Observability)
// instruments, written to be SPLICED into tools/lm_walk.body.js. NOT runnable on its own. Read
// tools/lm_leo_instrument.md first: it holds the lens, the per-surface specifics, the E coverage map, what O can and
// cannot prove locally, and the banker gates/witness wording.
//
// THREE PARTS, each between a BEGIN and an END marker. Anchor on the exact TEXT - the walker is edited while rows are
// walked, so its line numbers move:
//
//   PART 1  top-level constants        insert AFTER   `  VARIANTS.proposal = Object.assign({ ok: true, data: PROPOSAL }, PROPOSAL);`
//   PART 2  per-viewport route + state insert BEFORE  `    ctx.on('request', (r) => { try { const h = r.headers(); if (!apikey`
//           (= right after the closing `});` of the existing `await ctx.route('**/functions/v1/**', ...)` handler)
//   PART 3  helpers + the L / E / O    insert BEFORE  `      if (P.sublayer === 'S') {`
//           reading blocks             (= right after the closing `}` of `if (P.sublayer === 'R') {...}`, inside the
//                                      per-viewport `try`, where page / ctx / step / captured are in scope)
//
// HOW PART 2's ROUTE FITS THE EXISTING ONE. Playwright runs a context's routes in REVERSE registration order, so the
// route PART 2 registers runs BEFORE the existing '**/functions/v1/**' handler. While `leo.mode === 'off'` (the whole
// time, except inside a PART 3 pass) it calls route.fallback() for every request, so the existing handler behaves
// exactly as today: the walker's own first ask on an L/E/O row is still answered 503 by it (`variant` is null for
// L/E/O). Side-effect functions (send/push/...) and the helper functions (semantic-search, embed-entry) always fall
// back too - the existing handler keeps blocking/answering them. Inside a pass it answers the MODEL functions itself
// (and records them in `captured` with the same shape the existing handler uses, so the end-of-walk hive checks still
// read them): 'answer' = 200 with VARIANTS.leo at once; 'delay' = the same answer after L_DELAY_MS; 'hang' = held until
// PART 3 releases it; 'fail504' = 504 at once. For E it also registers '**/rest/v1/ai_reply_feedback**', which HOLDS
// every write to the feedback table (201, recorded with its body) whatever blockWrites says - the existing
// '**/rest/v1/**' handler records only "METHOD table" for a held write unless the row is LM-A.
//
// Variables of the walker this uses: mcpPage, P, PROPOSAL, fill, VARIANTS, OWN_STEPS_ALL, MODEL_FNS, hiveOf, askSurface,
// apikey (outer), problems, notes; per viewport: ctx, vp, captured, blockWrites, heldWrites, page, step.

  // ===== LEO PART 1 BEGIN (top-level constants) =====
  // LM-L / LM-E / LM-O (2026-10-07). ONE realistic answer every model function gets while these sub-layers walk: the
  // text keys a chat reads (fill), the structured keys a generator reads (PROPOSAL: project_type, template_id, dates;
  // actions for hive's coach; bullets for resume polish; action_plan for alert-hub's brief) - each carrying a per-run
  // mark, so "the answer was shown" and "the feedback carried the answer" are read as THIS run's answer, never an old one.
  const LEO_MARK = 'LMW' + Math.random().toString(36).slice(2, 7).toUpperCase();
  const LEO_TXT = LEO_MARK + ' Inspect the drive belt this week and replace it if worn.';
  const LEO_ACTIONS = [{ priority: 1, urgency: 'THIS WEEK', machine: 'the asked machine', action: LEO_TXT, why: 'Stubbed answer for the walk' }];
  const LEO_BODY = Object.assign({}, PROPOSAL, fill(LEO_TXT), { lessons_text: LEO_TXT, bullets: [LEO_TXT], actions: LEO_ACTIONS,
    action_plan: { summary: LEO_TXT, narration: LEO_TXT, today: LEO_ACTIONS, this_week: LEO_ACTIONS, watch_list: [] }, cited: [] });
  VARIANTS.leo = Object.assign({ ok: true, data: LEO_BODY }, LEO_BODY);
  // what an answer that never comes finally ends as, once the walk stops holding it: the gateway's own sentence for a
  // forward that could not finish (ai-gateway/index.ts, the catch around the 70 s forward), on a 504
  const LEO_504 = { error: 'That assistant could not finish. Try again in a moment.' };
  // LM-L numbers
  const L_DELAY_MS = 12000;      // the slow answer arrives 12 s after the request - past the 10 s "keep attention" limit
  const L_PROGRESS_MS = 1500;    // "within ~1 s of the ask": the in-page observer stamps it, +0.5 s for the request hop
  const L_AFTER_MS = 8000;       // after the answer arrives the page has this long to show it and drop its working state
  const L_HANG_MAX_MS = 165000;  // the longest the walk waits for a page to give up on an answer that never comes
  // each surface's OWN deadline for one ask whose answer never comes, read from source (see the md): a supabase-js
  // function call aborts at 75 s (utils.js getDb, WH_DB_TIMEOUT for /functions/v1/); a page that falls back to a
  // second function after the first times out waits twice. The walk waits deadline + 12 s (capped) before it calls a
  // wait endless.
  const L_DEADLINE_MS = { companion: 75000, 'assistant.html': 92000, 'asset-hub.html': 150000, 'hive.html': 150000,
    'resume.html': 45000, 'analytics.html': 120000, 'analytics-report.html': 90000 };
  // how each surface's OWN AI is reached: 'own' (the default) = the page's own control with the companion taken off the
  // page (OWN_STEPS_ALL, then the ask helper, then the page's own AI button - the S pass's order); { load } = the AI
  // runs as the page opens, so the stub is armed before the navigation and only that function is judged; 'companion' =
  // the page's own AI functions are not a typed or pressed wait (an embedding on save, voice, a photo), so the AI a
  // person can ask there is the floating companion. A surface whose own AI is not reached falls back to the companion
  // on that page, and the note says so.
  const LEO_ENTRY = { 'alert-hub.html': { load: 'analytics-orchestrator', background: true },
    'shift-brain.html': { load: 'shift-planner-orchestrator' },
    'logbook.html': 'companion', 'pm-scheduler.html': 'companion', 'skillmatrix.html': 'companion', 'report-sender.html': 'companion' };
  // functions a page calls BESIDE its answer (retrieval, embeddings): left to the existing 503 stub, never delayed
  const LEO_HELPER_FNS = new Set(['semantic-search', 'embed-entry']);
  // what tools/ai_ask.mjs PREP types before it asks (resume.html: an experience line) - the person's own words to keep
  const LEO_PREP_NEEDLE = { 'resume.html': 'Repaired Pump P-204B' };
  // the page's own AI control, when no ask box reached a model (the S pass's two vocabularies)
  const LEO_OWN_RX = /generate|polish|summar|recompute|refresh|re-?run|suggest|analy[sz]e|improve|rewrite|explain|draft|insight|report/i;
  const LEO_BAD_RX = /send|export|delete|remove|share|publish|sign out|log ?out|email|download|print/i;
  // the in-page readings (their sources are passed into the page, which compiles them)
  const LEO_PROG_RX = /\b(thinking|working|generating|analy[sz]ing|loading|asking|parsing|drafting|polishing|composing|compiling|computing|calculating|processing|preparing|refreshing|searching|tailoring|building|scoring|one moment|please wait)\b|nag-iisip|sinusuri|ginagawa|nire-refresh|kinakalkula|sandali|…\s*$|\.\.\.\s*$/i;
  const LEO_SPIN_RX = /typing|spinner|\bspin\b|loader|loading|skeleton|shimmer|is-busy|ar-status|refreshing/i;
  const LEO_STOP_RX = /^\s*(stop|cancel|abort|itigil|ihinto|kanselahin)\b/i;
  const LEO_FAIL_RX = /try again|could ?n.?t|could not|unavailable|did ?n.?t|took too long|too long|not available|busy|went wrong|failed|no answer|timed? ?out|not sent|pakisubukan|subukan|natagalan|hindi natuloy/i;
  const LEO_WRONG_RX = /\b(wrong|unhelpful|not helpful|incorrect|inaccurate|thumbs? ?down)\b|\bmali\b|hindi nakatulong|👎/i;
  const LEO_ACK_RX = /recorded|thank|salamat|naitala|feedback (sent|saved)/i;
  // the gateway agent each body names -> the function it forwards to (ai-gateway/index.ts AGENT_ROUTES)
  const LEO_GW_FN = { 'asset-brain': 'asset-brain-query', assistant: 'ai-orchestrator', coach: 'ai-orchestrator',
    'voice-journal': 'voice-journal-agent', analytics: 'analytics-orchestrator', project: 'project-orchestrator',
    shift: 'shift-planner-orchestrator', 'logbook-voice': 'voice-logbook-entry', 'report-voice': 'voice-report-intent',
    'voice-action': 'voice-action-router', 'temporal-rag': 'temporal-rag-orchestrator', 'service-triage': 'marketplace-listing-assist' };
  // LM-O: what ONE successful call of each function leaves behind, read from source. `call` = a per-call record an
  // operator can read (who/when/which model/latency); `output` = provenance on the row the AI's output was saved to.
  // A function missing here writes neither on success: it imports logAICost and never calls it (or never imports it),
  // serveObserved writes wh_traces only on an UNHANDLED throw, and the only trace left is the edge runtime's stdout line
  // "[ai-chain] served by <provider> / <model> (tokens N)" (_shared/ai-chain.ts), which nothing in the product reads.
  const O_TRACE = 'wh_traces row, route ai-gateway (status, hive_id, latency_ms, model_chain; user_id is never set) - read only by the founder Grafana SLO board';
  const O_SINK = {
    'ai-gateway:voice-journal': { call: ['ai_cost_log fn voice-journal-agent (written by voice-journal-agent itself)', O_TRACE],
      output: ['voice_journal_entries: the question, written before the quota gates; the reply added on success (the person\'s Journal)'],
      src: 'ai-gateway/index.ts persist-first journal (~L1021), per-turn cost log skipped for voice-journal (~L1897); voice-journal-agent/index.ts logAICost (~L710); _shared/envelope.ts recordTrace' },
    'ai-gateway': { call: ['ai_cost_log fn <forwarded function>, model gateway:<fn>, tokens ESTIMATED from text length (hive members via ai-quality.html; founder Grafana)', O_TRACE],
      output: [], src: 'ai-gateway/index.ts per-turn logAICost (~L1897) and ok() -> _shared/envelope.ts recordTrace' },
    'marketplace-listing-assist': { call: ['ai_cost_log fn marketplace-listing-assist (served model, estimated tokens, schema_compliance)'],
      output: ['marketplace_listings.ai_assisted_fields once the listing is posted (LM332)'], src: 'marketplace-listing-assist/index.ts logAICost (~L243)' },
    'visual-defect-capture': { call: ['ai_cost_log fn visual-defect-capture'], output: [], src: 'visual-defect-capture/index.ts logAICost (~L342/366/386)' },
    'intelligence-report': { call: ['automation_log job row (one per report, not per model call)'], output: ['ph_intelligence_reports.generated_at'], src: 'intelligence-report/index.ts (~L293)' },
    'scheduled-agents': { call: ['automation_log job row per agent run'], output: [], src: 'scheduled-agents/index.ts logResult (~L41)' },
    'batch-risk-scoring': { call: ['automation_log job row (no model call: deterministic scoring)'], output: [], src: 'batch-risk-scoring/index.ts (~L116)' },
    'shift-planner-orchestrator': { call: [], output: ['shift_plans.generated_by / generated_at'], src: 'shift-planner-orchestrator/index.ts imports logAICost, never calls it' },
    'fmea-populator': { call: [], output: ['rcm_fmea_modes.source = ai_logbook, ai_confidence'], src: 'fmea-populator/index.ts imports logAICost, never calls it' },
    'project-orchestrator': { call: [], output: ['projects.meta _ai_intent / _ai_prefilled_fields / _ai_generated_lessons once the person saves (LM335, PJ14)'], src: 'project-orchestrator/index.ts imports logAICost, never calls it' },
  };
  const O_NO_SINK = { call: [], output: [], src: 'imports logAICost and never calls it (or never imports it); serveObserved writes wh_traces only on an unhandled throw; only the edge stdout line "[ai-chain] served by ..." remains' };
  // an echo replay of a voice-journal body WRITES a journal note: ai-gateway persists the question to
  // voice_journal_entries BEFORE its quota gates and before the debug echo returns (ai-gateway/index.ts ~L1021). Off
  // by default - flip only with Ian's yes (the md says what it costs).
  const O_REPLAY_JOURNAL_AGENTS = false;
  // a reached function that leaves no per-call record is an LM-O finding (false = a note only)
  const O_STATIC_GAP_IS_PROBLEM = true;
  // LM-E: the evaluation that covers each surface's AI, read from source (file + what it grades). The banker's
  // postgres witness adds what the runs actually measured (ai_quality_log) - see the md.
  const E_RUN = (agent, what) => ({ by: 'ai-eval-runner (nightly pg_cron ai-eval-daily) on evals/canonical_questions.json agent "' + agent + '"',
    grades: what + '; LLM-as-judge score >= 70 AND every expected keyword present; writes ai_quality_log' });
  const E_COVERAGE = {
    companion: [{ by: 'tools/companion_{agent,rag,memory,persona,domain,robustness,safety_gaps}_eval.py + tools/companion_rigorous_grader.py (companion_eval_scorecard.json)',
      grades: '8 dimensions - tool routing, RAG citations, memory recall + abstention, persona markers, maintenance-domain facts, Taglish/noise robustness, injection/leak refusal, latency; gates companion-dim-gate / ai-eval-regression / companion-diverse-gate degrade to SKIP without fresh results' },
      { by: 'evals/canonical_questions.json agent "voice-journal"', grades: 'NONE - 0 fixtures (validate_ai_eval_coverage WARN)' }],
    'alert-hub.html': [E_RUN('analytics', 'OEE / MTBF-trend questions - the page calls the prescriptive phase, which no fixture asks')],
    'analytics-report.html': [E_RUN('analytics', 'OEE / MTBF-trend questions')],
    'analytics.html': [E_RUN('analytics', 'OEE / MTBF-trend questions'), { by: 'batch-risk-scoring', grades: 'n/a - no model call (deterministic scoring)' }],
    'asset-hub.html': [E_RUN('asset-brain', 'failure history / PM due / similar-pump root cause'),
      { by: 'tools/companion_rag_eval.py (companion_rag_golden.json, asset HPU-001)', grades: 'Asset Brain cites the right evidence kinds; 2 abstention controls; deterministic context recall/precision + judged faithfulness' },
      { by: 'fmea-populator', grades: 'none (tools/validate_ai_draft_shows_its_basis.py checks the draft names its basis, not its quality)' }],
    'assistant.html': [{ by: 'evals/canonical_questions.json agent "assistant"', grades: 'NONE - 0 fixtures (validate_ai_eval_coverage WARN)' },
      { by: 'tools/companion_memory_eval.py (agent "assistant" -> ai-orchestrator)', grades: 'memory recall across sessions + abstention' }],
    'hive.html': [{ by: 'evals/canonical_questions.json agent "coach"', grades: 'NONE - 0 fixtures (validate_ai_eval_coverage WARN)' },
      { by: 'tools/fb4_grounding_eval.py (gate fb4-grounding-eval)', grades: 'the coach via ai-gateway and ai-orchestrator direct: every asset tag it names must be a real hive tag; an injection must not leak' }],
    'logbook.html': [E_RUN('logbook-voice', 'voice entries parsed into logbook fields (voice-logbook-entry)'), { by: 'visual-defect-capture', grades: 'none' }],
    'marketplace.html': [E_RUN('service-triage', 'service triage suggestions'),
      { by: 'tools/validate_service_triage_eval.py (gate service-triage-eval)', grades: 'triage category / urgency / mode are in the product vocabulary read from the DB - the triage MODE only; the parts listing assist (description draft) has no eval' }],
    'ph-intelligence.html': [{ by: 'intelligence-report', grades: 'none' }],
    'pm-scheduler.html': [{ by: 'embed-entry', grades: 'n/a - an embedding, no answer to grade; the AI a person asks here is the companion' }],
    'project-manager.html': [E_RUN('project', 'status / blockers / change-order cost - not the intent-parse or lessons-draft phases this page calls')],
    'project-report.html': [E_RUN('project', 'status / blockers / change-order cost - not the narrative phase this page calls')],
    'report-sender.html': [E_RUN('report-voice', 'voice report intents (voice-report-intent)'), { by: 'scheduled-agents, voice-transcribe', grades: 'none' }],
    'resume.html': [{ by: 'resume-polish, resume-extract', grades: 'none (tools/validate_new_claims_are_opt_in.py is a static contract on the review sheet, not a grade)' }],
    'shift-brain.html': [E_RUN('shift', 'handover / coverage (shift-planner-orchestrator)'), E_RUN('analytics', 'OEE / MTBF-trend questions')],
    'skillmatrix.html': [{ by: 'embed-entry', grades: 'n/a - an embedding; the AI a person asks here is the companion' }],
  };
  // ===== LEO PART 1 END =====

    // ===== LEO PART 2 BEGIN (per viewport: the L/E/O route and its state) =====
    const leo = { mode: 'off', only: null, reqs: [], gw: [], held: [], fb: [], apikey: null };
    // a timer that works whether or not this vm exposes setTimeout
    const leoSleep = (ms) => (typeof setTimeout === 'function' ? new Promise((res) => setTimeout(res, ms)) : mcpPage.waitForTimeout(ms));
    const leoRelease = (how) => { const hs = leo.held.splice(0); hs.forEach((res) => { try { res(how); } catch (e) { void e; } }); return hs.length; };
    if (P.sublayer === 'L' || P.sublayer === 'E' || P.sublayer === 'O') {
      await ctx.route('**/functions/v1/**', async (route) => {
        const req = route.request();
        const fn = (req.url().split('/functions/v1/')[1] || '').split(/[?/#]/)[0];
        if (leo.mode === 'off' || !MODEL_FNS.has(fn) || LEO_HELPER_FNS.has(fn)
          || /send|push|notify|email|export|reset|invite|payment|webhook/i.test(fn)) return route.fallback();
        const h = req.headers();
        if (h.apikey && !leo.apikey) leo.apikey = h.apikey;
        let body = null;
        const raw = req.postData() || '';
        try { body = raw ? JSON.parse(raw) : null; } catch (e) { body = null; }
        const hv = body ? hiveOf(body) : (/name="hive_id"\r?\n\r?\n([^\r\n]*)/.exec(raw) || [])[1];
        // a load-time pass judges ONE function; every other model call meanwhile is answered at once
        const mode = (leo.only && fn !== leo.only) ? 'answer' : leo.mode;
        captured.push({ fn, method: req.method(), hive: hv === undefined ? '(not named)' : hv, injectionIn: [], leo: mode });
        const rec = { fn, t: Date.now(), mode, agent: body && typeof body.agent === 'string' ? body.agent : null,
          traceHeader: h['x-wh-trace'] || null, answeredAt: null, status: null };
        leo.reqs.push(rec);
        if (fn === 'ai-gateway' && body && typeof body === 'object') leo.gw.push(body);
        const done = (status, b) => { rec.answeredAt = Date.now(); rec.status = status;
          return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(b) }).catch(() => {}); };
        if (mode === 'delay') {
          await leoSleep(L_DELAY_MS);
          return leo.mode === 'fail504' ? done(504, LEO_504) : done(200, VARIANTS.leo);
        }
        if (mode === 'hang') {
          const how = await new Promise((res) => leo.held.push(res));
          if (how === 'abort') { rec.answeredAt = Date.now(); rec.status = 'released'; return route.abort().catch(() => {}); }
          return done(504, LEO_504);
        }
        if (mode === 'fail504') return done(504, LEO_504);
        return done(200, VARIANTS.leo);
      });
      if (P.sublayer === 'E') {
        await ctx.route('**/rest/v1/ai_reply_feedback**', async (route) => {
          const r = route.request();
          if (r.method() === 'GET' || r.method() === 'HEAD') return route.fallback();
          leo.fb.push({ t: Date.now(), method: r.method(), body: r.postData() || '' });
          return route.fulfill({ status: 201, contentType: 'application/json', body: '[]' });
        });
      }
    }
    // ===== LEO PART 2 END =====

      // ===== LEO PART 3 BEGIN (helpers + the L / E / O reading blocks) =====
      // Shared by the three blocks below; inert unless one of them runs. Every pass starts from a fresh load of the
      // page (as the R and S re-asks do), writes are HELD for its whole length (blockWrites), and the person's question
      // is the walk's grounded one, set AFTER each load (a reload clears window.__lmQ, and the ask helper would then
      // type the injection instead).
      const leoQ = `What maintenance has been done on ${P.groundSubject || 'the pump'} recently?`;
      // L's second pass asks something else: the companion restores its chat history after a reload, so pass A's
      // question would still be on screen and "the person's words were kept" would read pass A's bubble
      const leoQ2 = `Is ${P.groundSubject || 'the pump'} due for any work this week?`;
      const LEO_ON = P.sublayer === 'L' || P.sublayer === 'E' || P.sublayer === 'O';
      if (LEO_ON) {
        // the in-page stopwatch: from document start on every load, a MutationObserver stamps (Date.now(), the same
        // clock the route stamps requests with) each visible working / failure / acknowledgement / stop sign, and
        // whether it sits in a live region. It records only while ARMED (set before an ask, or from sessionStorage
        // for a load-time pass), so a page's own load is not timed.
        await page.addInitScript((args) => {
          if (window.__lmL) return;
          const PROG = new RegExp(args[0], 'i'), SPIN = new RegExp(args[1], 'i'), STOP = new RegExp(args[2], 'i');
          const FAIL = new RegExp(args[3], 'i'), ACK = new RegExp(args[4], 'i');
          let armed = false;
          try { armed = sessionStorage.getItem('__lmLArm') === '1'; } catch (e) { armed = false; }
          const L = window.__lmL = { armed, ev: [] };
          const LIVE = '[aria-live]:not([aria-live="off"]),[role="status"],[role="alert"],[role="log"],[role="progressbar"]';
          const look = (el, why) => {
            if (!L.armed || !el || el.nodeType !== 1 || L.ev.length > 600) return;
            const big = el.childElementCount > 25;
            const t = big ? '' : String(el.textContent || '').replace(/\s+/g, ' ').trim();
            const cls = (typeof el.className === 'string' ? el.className : '') + ' ' + (el.id || '');
            const busy = el.getAttribute('aria-busy') === 'true';
            const prog = busy || el.getAttribute('role') === 'progressbar' || SPIN.test(cls) || (!!t && t.length < 120 && PROG.test(t));
            const fail = !!t && t.length < 400 && FAIL.test(t);
            const ack = !!t && t.length < 200 && ACK.test(t);
            const stop = !big && [el, ...el.querySelectorAll('button,[role="button"]')].some((b) => b.matches && b.matches('button,[role="button"]')
              && !b.dataset.lmPreStop && STOP.test(String(b.textContent || '').trim() + ' ' + String(b.getAttribute('aria-label') || '')));
            if (!(prog || fail || ack || stop)) return;
            const anc = el.closest('[id]');
            L.ev.push({ t: Date.now(), why, prog, fail, ack, stop, busy, vis: !!(el.checkVisibility && el.checkVisibility()),
              live: !!el.closest(LIVE), text: t.slice(0, 160), where: anc ? '#' + anc.id : el.tagName.toLowerCase() });
          };
          new MutationObserver((ms) => {
            for (const m of ms) {
              if (m.type === 'childList') m.addedNodes.forEach((n) => look(n.nodeType === 1 ? n : n.parentElement, 'added'));
              else if (m.type === 'characterData') look(m.target.parentElement, 'text');
              else look(m.target, 'attr:' + m.attributeName);
            }
          }).observe(document, { childList: true, subtree: true, characterData: true, attributes: true,
            attributeFilter: ['aria-busy', 'class', 'style', 'hidden', 'disabled'] });
        }, [LEO_PROG_RX.source, LEO_SPIN_RX.source, LEO_STOP_RX.source, LEO_FAIL_RX.source, LEO_ACK_RX.source]).catch(() => {});
      }
      // the working signs showing NOW (aria-busy, a progressbar, a spinner/typing/skeleton class, or a short text that
      // says it is working) - each pass subtracts what was already there before its ask
      const leoProgNow = () => page.evaluate((args) => {
        const PROG = new RegExp(args[0], 'i'), SPIN = new RegExp(args[1], 'i');
        const vis = (e) => !!(e && e.checkVisibility && e.checkVisibility());
        const out = new Set();
        for (const el of document.querySelectorAll('[aria-busy="true"],[role="progressbar"]')) if (vis(el)) out.add('busy:' + (el.id || el.getAttribute('role') || el.tagName));
        for (const el of document.querySelectorAll('[class],[id]')) {
          const c = ((typeof el.className === 'string' ? el.className : '') + ' ' + (el.id || '')).trim();
          if (SPIN.test(c) && vis(el)) out.add('el:' + c.slice(0, 50));
        }
        const w = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT);
        let n;
        while ((n = w.nextNode())) {
          const s = n.textContent.replace(/\s+/g, ' ').trim();
          if (s && s.length < 120 && PROG.test(s) && vis(n.parentElement)) out.add('tx:' + s.slice(0, 60));
        }
        return [...out];
      }, [LEO_PROG_RX.source, LEO_SPIN_RX.source]).catch(() => []);
      const leoEvents = () => page.evaluate(() => (window.__lmL && window.__lmL.ev) || []).catch(() => []);
      // are the person's words (and this run's answer mark) on the page - its text or any field's value?
      const leoRead = (needles) => page.evaluate((args) => {
        const all = (document.body ? document.body.innerText : '') + ' ' + [...document.querySelectorAll('textarea, input')].map((e) => e.value || '').join(' ');
        return { has: args[0].map((x) => all.includes(x)), mark: all.includes(args[1]) };
      }, [needles.map((x) => String(x).slice(0, 40)), LEO_MARK]).catch(() => ({ has: needles.map(() => false), mark: false }));
      // a Stop / Cancel the WAIT offers (one that was on the page before the ask - a modal's Cancel - does not count)
      const leoStopNow = () => page.evaluate((stopS) => {
        const rx = new RegExp(stopS, 'i');
        const b = [...document.querySelectorAll('button,[role="button"]')].find((e) => !e.dataset.lmPreStop && e.checkVisibility && e.checkVisibility()
          && rx.test(String(e.innerText || e.textContent || '').trim() + ' ' + String(e.getAttribute('aria-label') || '')));
        return b ? String(b.innerText || b.getAttribute('aria-label') || '').trim().slice(0, 40) : null;
      }, LEO_STOP_RX.source).catch(() => null);
      const leoTok = () => page.evaluate(() => {
        try { for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); if (/^sb-.*-auth-token$/.test(k)) { const v = JSON.parse(localStorage.getItem(k) || '{}'); return v.access_token || (v.currentSession && v.currentSession.access_token) || null; } } } catch (e) { void e; }
        return null;
      }).catch(() => null);
      const leoPrep = async (keepCompanion) => {
        await page.goto(`${P.origin}/${P.page}`, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
        await page.waitForTimeout(4500);
        await page.keyboard.press('Escape').catch(() => {});
        await page.evaluate((keep) => {
          if (!keep) { ['wh-ai-trigger', 'wh-ai-panel'].forEach((id) => { const el = document.getElementById(id); if (el) el.remove(); }); return; }
          // the ask helper TOGGLES the trigger (LM200): an open panel is closed first, so its click opens it
          const box = document.getElementById('wh-ai-input'), trig = document.getElementById('wh-ai-trigger');
          if (box && trig && box.checkVisibility && box.checkVisibility({ opacityProperty: true, visibilityProperty: true })) trig.click();
        }, !!keepCompanion).catch(() => {});
        await page.waitForTimeout(600);
      };
      // before an ask: the question, and a mark on every feedback and stop control already on the page
      const leoArm = (resetEvents, q) => page.evaluate((args) => {
        const stop = new RegExp(args[1], 'i'), wrong = new RegExp(args[2], 'i');
        window.__lmQ = args[0];
        const lab = (b) => String(b.innerText || b.textContent || '').trim() + ' ' + String(b.getAttribute('aria-label') || '') + ' ' + String(b.title || '');
        document.querySelectorAll('button,[role="button"],[data-rate]').forEach((b) => {
          if (b.hasAttribute('data-rate') || wrong.test(lab(b))) b.dataset.lmPre = '1';
          if (stop.test(lab(b))) b.dataset.lmPreStop = '1';
        });
        if (window.__lmL) { window.__lmL.armed = true; if (args[3]) window.__lmL.ev = []; }
      }, [q || leoQ, LEO_STOP_RX.source, LEO_WRONG_RX.source, !!resetEvents]).catch(() => {});
      const leoRemoveCompanion = () => page.evaluate(() => { ['wh-ai-trigger', 'wh-ai-panel'].forEach((id) => { const el = document.getElementById(id); if (el) el.remove(); }); }).catch(() => {});
      // ONE ask of the surface's AI with the stub in `mode`. Returns where it went and what the person typed, or null
      // when no AI was reached (own AI first; the companion on this page as the fallback).
      const leoAsk = async (mode, question) => {
        const q = question || leoQ;
        const e0 = P.surface === 'companion' ? 'companion' : (LEO_ENTRY[P.page] || 'own');
        const tries = e0 === 'companion' ? ['companion'] : [e0, 'companion'];
        for (const e of tries) {
          const kind = (e && typeof e === 'object' && e.load) ? 'load' : e;
          leo.mode = 'off'; leo.only = null; leoRelease('abort');
          const n0 = leo.reqs.length, g0 = leo.gw.length;
          const typed = [];
          let how = null, base = [], tAsk = Date.now();
          if (kind === 'load') {
            // armed BEFORE the navigation: the page's AI runs as it opens
            await page.evaluate(() => { try { sessionStorage.setItem('__lmLArm', '1'); } catch (x) { void x; } }).catch(() => {});
            leo.only = e.load; leo.mode = mode; tAsk = Date.now();
            await page.goto(`${P.origin}/${P.page}`, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
            base = await leoProgNow();
            await page.evaluate(() => { try { sessionStorage.removeItem('__lmLArm'); } catch (x) { void x; } }).catch(() => {});
            await leoArm(false, q);   // marks the controls already there; keeps the events recorded since document start
            for (let i = 0; i < 24 && !leo.reqs.slice(n0).some((r) => r.fn === e.load); i++) await page.waitForTimeout(500);
            how = 'page load (' + e.load + ')';
          } else {
            await leoPrep(kind === 'companion');
            base = await leoProgNow();
            await leoArm(true, q);
            leo.mode = mode; tAsk = Date.now();
            if (kind === 'own') {
              const steps0 = OWN_STEPS_ALL[P.page] || [];
              let doneSteps = 0;
              for (const stp of steps0) {
                const did = await page.evaluate((s) => {
                  const el = document.querySelector(s.click || s.fill);
                  if (!el) return 'absent';
                  if (!(el.checkVisibility && el.checkVisibility({ opacityProperty: true, visibilityProperty: true }))) return 'hidden';
                  if (s.click) { if (!(s.unlessExpanded && el.getAttribute('aria-expanded') === 'true')) el.click(); return 'ok'; }
                  el.focus(); el.value = s.value; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true }));
                  return 'ok';
                }, stp).catch(() => 'threw');
                if (did !== 'ok') { notes.push(`${vp.name}: LM-${P.sublayer}: ${stp.click || stp.fill} is ${did} for ${P.castName}`); break; }
                doneSteps++;
                if (stp.fill) typed.push(stp.value);
                if (stp.nav) {
                  await page.waitForLoadState('domcontentloaded').catch(() => {});
                  await page.waitForTimeout(4000);
                  await leoRemoveCompanion();
                  base = await leoProgNow();
                  await leoArm(true, q);
                } else await page.waitForTimeout(1200);
              }
              const last = steps0.slice(-1)[0];
              // scripted only when EVERY step ran and the last one is the press that calls the model
              if (steps0.length && doneSteps === steps0.length && last.calls) how = 'scripted: ' + steps0.map((x) => x.click || x.fill).join(' > ');
              else {
                const asked = askSurface ? await askSurface(page, P.page, false).catch(() => false) : false;
                for (let i = 0; i < 8 && leo.reqs.length === n0; i++) await page.waitForTimeout(400);
                if (leo.reqs.length > n0) {
                  how = asked;
                  if (typeof asked === 'string') typed.push(q);
                  if (LEO_PREP_NEEDLE[P.page]) typed.push(LEO_PREP_NEEDLE[P.page]);
                } else {
                  how = await page.evaluate((args) => {
                    const ok = new RegExp(args[0], 'i'), bad = new RegExp(args[1], 'i');
                    const vis = (x) => x.checkVisibility && x.checkVisibility({ opacityProperty: true, visibilityProperty: true });
                    const b = [...document.querySelectorAll('button, [role="button"]')].find((x) => {
                      const t = (x.innerText || x.getAttribute('aria-label') || '').trim();
                      return vis(x) && !x.disabled && t && ok.test(t) && !bad.test(t);
                    });
                    if (!b) return false;
                    b.click();
                    return 'button: ' + (b.innerText || b.getAttribute('aria-label') || '').trim().slice(0, 40);
                  }, [LEO_OWN_RX.source, LEO_BAD_RX.source]).catch(() => false);
                }
              }
            } else {
              how = askSurface ? await askSurface(page, P.page, true).catch(() => false) : false;
              if (typeof how === 'string') typed.push(q);
            }
            for (let i = 0; i < 10 && leo.reqs.length === n0; i++) await page.waitForTimeout(400);
          }
          const reached = leo.reqs.slice(n0).filter((r) => kind !== 'load' || r.fn === e.load);
          if (reached.length) {
            return { entry: kind, target: kind === 'companion' ? 'companion' : P.page, how, typed, n0: leo.reqs.indexOf(reached[0]), g0,
              tAsk: kind === 'load' ? reached[0].t : tAsk, base, background: !!(kind === 'load' && e.background),
              fns: [...new Set(leo.reqs.slice(n0).map((r) => r.fn + (r.agent ? '(' + r.agent + ')' : '')))] };
          }
          leo.mode = 'off'; leo.only = null; leoRelease('abort');
          const what = kind === 'own' ? "the page's own AI" : (kind === 'load' ? 'the AI ' + P.page + ' runs as it opens (' + e.load + ')' : 'the companion');
          notes.push(`${vp.name}: LM-${P.sublayer}: ${what} was not reached for ${P.castName} (${how || 'nothing to ask or press'})` +
            (kind !== 'companion' ? ' - walked the companion this page carries instead' : ''));
        }
        return null;
      };
      const leoReqsFrom = (n0) => leo.reqs.slice(n0);

      if (P.sublayer === 'L') {
        // ★LATENCY & WAITING (LM-L): "I knew it was working; a slow answer was saved, not lost." Pass A answers 12 s
        // late with a valid answer: a visible working sign within ~1 s, announced, held for the whole wait, the
        // person's words kept, the answer shown when it lands. Pass B never answers: the page's own deadline must end
        // the wait with a sentence the person can act on, their words intact. A Stop control is RECORDED, never judged.
        blockWrites = true;
        step.lat = { delayMs: L_DELAY_MS, mark: LEO_MARK };
        try {
          const a = await leoAsk('delay');
          if (!a) problems.push(`${vp.name}: LM-L: no AI on ${P.page} was reached for ${P.castName} - the slow-answer pass is unproven`);
          else {
            const tReq = leo.reqs[a.n0].t;
            const samples = [];
            let stopSeen = null;
            const tEnd = tReq + L_DELAY_MS * 2 + L_AFTER_MS + 4000;
            while (Date.now() < tEnd) {
              await page.waitForTimeout(500);
              const at = Date.now() - tReq;
              const prog = (await leoProgNow()).filter((x) => !a.base.includes(x));
              const rd = await leoRead(a.typed);
              samples.push({ at, prog: prog.length, p0: prog[0] || null, typed: rd.has.every(Boolean), mark: rd.mark });
              if (!stopSeen && at > 1000 && at < L_DELAY_MS) stopSeen = await leoStopNow();
              const mine = leoReqsFrom(a.n0);
              const pending = mine.filter((r) => !r.answeredAt).length;
              const lastAns = Math.max(0, ...mine.map((r) => r.answeredAt || 0));
              if (!pending && lastAns && Date.now() - lastAns > L_AFTER_MS) break;
            }
            const ev = await leoEvents();
            const progEv = ev.filter((x) => x.prog && x.vis && x.t >= a.tAsk - 300);
            const firstEv = progEv.length ? Math.min(...progEv.map((x) => x.t)) - tReq : null;
            const firstPoll = (samples.find((s) => s.prog) || {}).at;
            const firsts = [firstEv, firstPoll].filter((x) => typeof x === 'number');
            const progressAtMs = firsts.length ? Math.min(...firsts) : null;
            const mine = leoReqsFrom(a.n0);
            const lastAnsAbs = Math.max(0, ...mine.map((r) => (typeof r.status === 'number' ? r.answeredAt || 0 : 0)));
            // null = the page abandoned the request before the slow answer came (its own deadline is under 12 s)
            const arrivedAt = lastAnsAbs ? lastAnsAbs - tReq : null;
            const waitEnd = arrivedAt === null ? L_DELAY_MS : arrivedAt;
            const announced = ev.filter((x) => x.prog && x.live && x.text && x.t >= a.tAsk - 300 && x.t <= tReq + waitEnd).map((x) => x.text);
            const waiting = samples.filter((s) => s.at >= 2000 && s.at <= waitEnd - 1000);
            const gap = waiting.find((s) => !s.prog);
            const lost = a.typed.length ? waiting.find((s) => !s.typed) : null;
            const after = arrivedAt === null ? [] : samples.filter((s) => s.at >= arrivedAt);
            const shown = after.find((s) => s.mark);
            const lastAfter = after.slice(-1)[0];
            step.lat.slow = { target: a.target, entry: a.entry, how: a.how, fns: a.fns, progressAtMs,
              firstSign: (progEv[0] && (progEv[0].text || progEv[0].where)) || (samples.find((s) => s.prog) || {}).p0 || null,
              announced: announced.slice(0, 3), stopControl: stopSeen, signGoneAtMs: gap ? gap.at : null,
              typedKept: a.typed.length ? !lost : null, answerArrivedAtMs: arrivedAt, answerShownAtMs: shown ? shown.at : null,
              stillWorkingAfterAnswer: !!(lastAfter && lastAfter.prog && lastAfter.at - arrivedAt >= L_AFTER_MS - 1000) };
            const S = step.lat.slow, on = a.target === 'companion' ? 'the companion' : P.page;
            if (progressAtMs === null || progressAtMs > L_PROGRESS_MS) problems.push(`${vp.name}: LM-L: no visible sign that ${on}'s AI was working within ${L_PROGRESS_MS / 1000} s of the ask (${progressAtMs === null ? 'none at all' : 'first at ' + (progressAtMs / 1000).toFixed(1) + ' s'})`);
            else if (!announced.length) problems.push(`${vp.name}: LM-L: ${on}'s waiting state ("${S.firstSign}") was not announced to a screen reader (no live region carried it)`);
            if (S.signGoneAtMs !== null) problems.push(`${vp.name}: LM-L: the sign that ${on}'s AI was working was gone ${(S.signGoneAtMs / 1000).toFixed(1)} s after the ask, while the answer was still ${((waitEnd - S.signGoneAtMs) / 1000).toFixed(0)} s away`);
            if (lost) problems.push(`${vp.name}: LM-L: the person's words were gone from ${on} ${(lost.at / 1000).toFixed(1)} s into the wait`);
            if (arrivedAt === null) problems.push(`${vp.name}: LM-L: ${on} abandoned the request before its ${L_DELAY_MS / 1000} s answer arrived - a slow answer is lost, not kept`);
            else if (!shown && a.typed.length && a.entry !== 'load') problems.push(`${vp.name}: LM-L: the slow answer arrived ${(arrivedAt / 1000).toFixed(0)} s after the ask and ${on} did not show it (lost)`);
            else if (!shown) notes.push(`${vp.name}: LM-L: the slow answer (${a.how}) arrived and its words were not found on the page - a structured generator renders its own fields, so this is recorded, not judged`);
            if (S.stillWorkingAfterAnswer) problems.push(`${vp.name}: LM-L: ${on} still said it was working ${(L_AFTER_MS / 1000)} s after the answer arrived ("${lastAfter.p0}")`);
            notes.push(`${vp.name}: LM-L: a way to stop the wait - ${stopSeen ? '"' + stopSeen + '"' : 'NONE offered'} (recorded, not judged)`);
          }
          // pass B: the answer never comes
          leo.mode = 'off'; leoRelease('abort');
          const b = await leoAsk('hang', leoQ2);
          if (!b) problems.push(`${vp.name}: LM-L: no AI on ${P.page} was reached for ${P.castName} - the never-answered pass is unproven`);
          else {
            const tReq = leo.reqs[b.n0].t;
            const deadline = L_DEADLINE_MS[b.target] || 75000;
            const cap = Math.min(deadline + 12000, L_HANG_MAX_MS);
            let endedBy = null, saidAt = null, goneAt = null;
            while (Date.now() - tReq < cap) {
              await page.waitForTimeout(1000);
              const at = Date.now() - tReq;
              const fails = (await leoEvents()).filter((x) => x.fail && x.t >= tReq + 500);
              const prog = (await leoProgNow()).filter((x) => !b.base.includes(x));
              if (prog.length) goneAt = null; else if (goneAt === null) goneAt = at;
              if (fails.length) { saidAt = Math.min(...fails.map((x) => x.t)) - tReq; endedBy = 'page'; await page.waitForTimeout(3000); break; }
              if (goneAt !== null && at - goneAt > 15000) { endedBy = 'silence'; break; }
            }
            const evB = await leoEvents();
            const failEv = evB.filter((x) => x.fail && x.t >= tReq + 500);
            const progEnd = (await leoProgNow()).filter((x) => !b.base.includes(x));
            const rdB = await leoRead(b.typed);
            const notice = await page.evaluate(() => {
              const n = document.getElementById('wh-connection-notice');
              return n && n.checkVisibility && n.checkVisibility() ? (n.innerText || '').trim().slice(0, 160) : '';
            }).catch(() => '');
            const stillHeld = leo.held.length;
            let afterRelease = null;
            if (endedBy !== 'page') {
              // the walk stops holding: what the person reads once the answer finally fails
              leo.mode = 'fail504';
              leoRelease('504');
              await page.waitForTimeout(8000);
              afterRelease = (await leoEvents()).filter((x) => x.fail && x.t >= tReq + 500).map((x) => x.text).slice(0, 2);
            }
            step.lat.never = { target: b.target, entry: b.entry, how: b.how, fns: b.fns, deadlineMs: deadline, capMs: cap,
              endedBy: endedBy || 'not by ' + Math.round(cap / 1000) + ' s', saidAtMs: saidAt, said: failEv.map((x) => x.text).filter(Boolean).slice(0, 3),
              saidInLiveRegion: failEv.some((x) => x.live), stillWorking: progEnd.slice(0, 2),
              typedKept: b.typed.length ? rdB.has.every(Boolean) : null, outageNotice: notice || null, requestsStillHeld: stillHeld, afterRelease };
            const on = b.target === 'companion' ? 'the companion' : P.page;
            if (!endedBy) problems.push(`${vp.name}: LM-L: when the answer never came, ${on} was still waiting ${Math.round(cap / 1000)} s after the ask ("${progEnd[0] || 'no working sign, no sentence'}") - its own limit is ~${Math.round(deadline / 1000)} s`);
            else if (endedBy === 'silence') (b.background ? notes : problems).push(`${vp.name}: LM-L: when the answer never came, ${on}'s working sign went away ${(goneAt / 1000).toFixed(0)} s after the ask and nothing said the answer was not coming${b.background ? ' (a background upgrade: what was already on screen stayed)' : ''}`);
            else if (progEnd.length) problems.push(`${vp.name}: LM-L: ${on} said "${failEv[0].text}" but still showed it was working (${progEnd[0]})`);
            if (b.typed.length && !rdB.has.every(Boolean)) problems.push(`${vp.name}: LM-L: after the answer never came, the person's words were gone from ${on}`);
            if (notice) problems.push(`${vp.name}: LM-L: an AI answer that never came was announced as a page outage: "${notice}"`);
            if (endedBy === 'page') notes.push(`${vp.name}: LM-L: ${on} gave up after ${(saidAt / 1000).toFixed(0)} s and said "${failEv[0].text}"${failEv.some((x) => x.live) ? '' : ' (not in a live region)'}`);
          }
        } finally { leo.mode = 'off'; leo.only = null; leoRelease('abort'); blockWrites = false; }
      }

      if (P.sublayer === 'E') {
        // ★EVALS & QUALITY GATES (LM-E): "quality is measured, not claimed." Static: E_COVERAGE names the evaluation
        // that covers this surface's AI (the banker's postgres witness adds what its runs measured). Walked: after a
        // stubbed answer, the "was this right?" control is there, and pressing "wrong" is a HELD write to
        // ai_reply_feedback that carries the answer it was about.
        blockWrites = true;
        step.eval = { mark: LEO_MARK, pageCoverage: E_COVERAGE[P.page] || [] };
        try {
          const a = await leoAsk('answer');
          if (!a) problems.push(`${vp.name}: LM-E: no AI on ${P.page} was reached for ${P.castName} - the feedback walk is unproven`);
          else {
            let ctl = null;
            for (let i = 0; i < 24 && !ctl; i++) {
              await page.waitForTimeout(500);
              ctl = await page.evaluate((wrongS) => {
                const rx = new RegExp(wrongS, 'i');
                const vis = (x) => !!(x.checkVisibility && x.checkVisibility());
                const lab = (x) => (String(x.getAttribute('aria-label') || '') + ' ' + String(x.title || '') + ' ' + String(x.innerText || x.textContent || '')).trim();
                const c = [...document.querySelectorAll('button,[role="button"]')].filter((x) => !x.dataset.lmPre && vis(x) && !x.disabled
                  && (x.getAttribute('data-rate') === '-1' || rx.test(lab(x))));
                if (!c.length) return null;
                const b = c[c.length - 1];
                document.querySelectorAll('[data-lm-pick]').forEach((x) => x.removeAttribute('data-lm-pick'));
                b.setAttribute('data-lm-pick', '1');
                const row = b.closest('[data-ai-trust]'), anc = b.closest('[id]');
                return { n: c.length, label: lab(b).slice(0, 60),
                  via: row ? 'whAiTrustRow (' + row.getAttribute('data-ai-trust') + ')' : (b.closest('.wh-msg-rate') ? 'companion thumbs (.wh-msg-rate)' : (anc ? '#' + anc.id : b.tagName.toLowerCase())) };
              }, LEO_WRONG_RX.source).catch(() => null);
            }
            const shown = (await leoRead([])).mark;
            const f0 = leo.fb.length, h0 = heldWrites.length, tPress = Date.now();
            let pressed = false;
            if (ctl) {
              pressed = await page.evaluate(() => { const b = document.querySelector('[data-lm-pick="1"]'); if (!b) return false; b.click(); return true; }).catch(() => false);
              await page.waitForTimeout(2500);
            }
            const fb = leo.fb.slice(f0).map((x) => { let o = null; try { o = JSON.parse(x.body); } catch (err) { o = null; } return Array.isArray(o) ? o[0] : o; }).filter(Boolean);
            const w = fb[0] || null;
            const ack = (await leoEvents()).filter((x) => x.ack && x.t >= tPress).map((x) => x.text).filter(Boolean).slice(0, 2);
            Object.assign(step.eval, { target: a.target, entry: a.entry, how: a.how, fns: a.fns, coverage: E_COVERAGE[a.target] || [],
              answerShown: shown, control: ctl, pressed,
              write: w ? { table: 'ai_reply_feedback', rating: w.rating, agent: w.agent || null, source: w.source || null, page: w.page || null,
                hive: w.hive_id || null, carriesAnswer: String(w.answer || '').includes(LEO_MARK),
                carriesQuestion: a.typed.length ? a.typed.some((q) => String(w.question || '').includes(String(q).slice(0, 30))) : null,
                answerChars: String(w.answer || '').length } : null,
              ack, otherWritesHeld: [...new Set(heldWrites.slice(h0))] });
            const on = a.target === 'companion' ? 'the companion' : P.page;
            if (!ctl && shown) problems.push(`${vp.name}: LM-E: ${on}'s AI answer offered no way to say it was wrong (no "was this right?" control appeared under it)`);
            else if (!ctl) problems.push(`${vp.name}: LM-E: the stubbed answer did not render on ${on} (${a.how}), so its "was this right?" control could not be judged - unproven`);
            else if (!w) problems.push(`${vp.name}: LM-E: pressing "${ctl.label}" on ${on} wrote nothing - the disagreement went nowhere`);
            else {
              if (!step.eval.write.carriesAnswer) problems.push(`${vp.name}: LM-E: the "wrong" record from ${on} does not carry the answer it was about (answer field: ${step.eval.write.answerChars} chars, no mark of this answer)`);
              if (Number(w.rating) !== -1) problems.push(`${vp.name}: LM-E: pressing "${ctl.label}" recorded rating ${w.rating}, not -1`);
              if (step.eval.write.carriesQuestion === false) notes.push(`${vp.name}: LM-E: the "wrong" record does not carry the question the person typed`);
              notes.push(`${vp.name}: LM-E: after the press the person was told ${ack.length ? '"' + ack[0] + '"' : 'nothing in words (only the control changed)'}`);
            }
          }
          notes.push(`${vp.name}: LM-E: ai_reply_feedback has no call or trace id column - a "wrong" can be matched to the call it judged only by its question/answer text`);
        } finally { leo.mode = 'off'; leo.only = null; blockWrites = false; }
      }

      if (P.sublayer === 'O') {
        // ★OBSERVABILITY (LM-O): "someone can see afterwards what the AI did." The page's ask is stubbed IN THE
        // BROWSER, so it never reaches the gateway and nothing is logged for it. So: (1) which functions the ask
        // reached, and what each leaves for an operator when it really answers (O_SINK, from source); (2) every
        // gateway body the page sent is REPLAYED as the person to the gateway's LOCAL debug echo with a minted
        // x-wh-trace id - the echo calls no LLM but answers through ok(), which writes the wh_traces row the banker
        // then reads back by that id (traceIds); (3) the hive's AI cost ledger, read as the person (RLS: members).
        blockWrites = true;
        step.obs = { replays: [], traceIds: [] };
        try {
          const a = await leoAsk('answer');
          if (!a) problems.push(`${vp.name}: LM-O: no AI on ${P.page} was reached for ${P.castName} - the observability walk is unproven`);
          else {
            await page.waitForTimeout(4000);
            const reached = leoReqsFrom(a.n0);
            const keys = [...new Set(reached.map((r) => (r.fn === 'ai-gateway' && O_SINK['ai-gateway:' + r.agent]) ? 'ai-gateway:' + r.agent : r.fn))];
            Object.assign(step.obs, { target: a.target, entry: a.entry, how: a.how, fns: a.fns,
              pageSentTraceId: reached.some((r) => r.traceHeader),
              sinks: keys.map((k) => Object.assign({ fn: k }, O_SINK[k] || O_NO_SINK)) });
            const on = a.target === 'companion' ? 'the companion' : P.page;
            for (const s of step.obs.sinks) {
              if (!s.call.length) (O_STATIC_GAP_IS_PROBLEM ? problems : notes).push(`${vp.name}: LM-O: ${on}'s ask reached ${s.fn}, which leaves no record of the call an operator can read when it answers` +
                (s.output.length ? ' (only provenance on its output: ' + s.output.join('; ') + ')' : '') + ` [source: ${s.src}]`);
            }
            if (!step.obs.pageSentTraceId) notes.push(`${vp.name}: LM-O: ${on}'s request carried no x-wh-trace id, so nothing the person sees can be matched to the gateway's trace of it`);
            const tok = await leoTok();
            const seen = new Set();
            for (const body of leo.gw.slice(a.g0)) {
              const agent = String(body.agent || '?');
              if (seen.has(agent)) continue;
              seen.add(agent);
              if (agent === 'voice-journal' && !O_REPLAY_JOURNAL_AGENTS) {
                step.obs.replays.push({ agent, replayed: false, why: 'the gateway writes a journal note before its debug echo returns - not replayed (O_REPLAY_JOURNAL_AGENTS)' });
                continue;
              }
              if (!tok) { step.obs.replays.push({ agent, replayed: false, why: 'no session token' }); continue; }
              const minted = Array.from({ length: 16 }, () => Math.floor(Math.random() * 16).toString(16)).join('');
              const echoBody = Object.assign({}, body, { context: Object.assign({}, body.context || {}, { debug_echo_memory_block: true }) });
              let status = 0, hdr = null, inBody = null, echoed = false;
              try {
                const r = await ctx.request.post(`${P.api}/functions/v1/ai-gateway`, { headers: { Authorization: 'Bearer ' + tok,
                  apikey: leo.apikey || apikey || '', 'Content-Type': 'application/json', 'x-wh-trace': minted }, data: echoBody, timeout: 60000 });
                status = r.status();
                hdr = r.headers()['x-wh-trace'] || null;
                const j = await r.json().catch(() => null);
                inBody = (j && j.trace_id) || null;
                echoed = !!(j && j.data && j.data.debug_echo);
              } catch (err) { void err; }
              step.obs.replays.push({ agent, replayed: true, status, minted, traceHeader: hdr, traceInBody: inBody, echoed });
              if (status === 200 && echoed) step.obs.traceIds.push(minted);
              if (status !== 200 || !echoed) problems.push(`${vp.name}: LM-O: the ${agent} request ${on} sent, replayed to the gateway's local debug echo, came back ${status}${echoed ? '' : ' with no echo'} - the gateway's trace path is unproven for it`);
              else if (hdr !== minted && inBody !== minted) problems.push(`${vp.name}: LM-O: the gateway answered the ${agent} request under another trace id (${hdr || inBody || 'none'}) than the one it was sent - a report could not be matched to its trace`);
            }
            const hive = await page.evaluate(() => localStorage.getItem('wh_active_hive_id')).catch(() => null);
            const fns = [...new Set(reached.map((r) => (r.fn === 'ai-gateway' ? LEO_GW_FN[r.agent] : r.fn)).filter(Boolean))];
            if (hive && tok && fns.length) {
              try {
                const r = await ctx.request.get(`${P.api}/rest/v1/ai_cost_log?select=fn,model,status,created_at&hive_id=eq.${encodeURIComponent(hive)}&fn=in.(${fns.join(',')})&order=created_at.desc&limit=50`,
                  { headers: { Authorization: 'Bearer ' + tok, apikey: leo.apikey || apikey || '' }, timeout: 15000 });
                const rows = r.ok() ? await r.json().catch(() => []) : [];
                const by = {};
                for (const x of (Array.isArray(rows) ? rows : [])) { if (!by[x.fn]) by[x.fn] = { n: 0, newest: x.created_at, model: x.model }; by[x.fn].n++; }
                step.obs.ledger = { readableByPerson: r.ok(), status: r.status(), hive, asked: fns, byFn: by };
              } catch (err) { step.obs.ledger = { error: String(err.message || err).slice(0, 100) }; }
            } else step.obs.ledger = { skipped: !hive ? 'the person has no active hive - ai_cost_log rows are readable only for a hive (RLS: hive_id is not null)' : (!tok ? 'no session token' : 'no function to look up') };
          }
        } finally { leo.mode = 'off'; leo.only = null; blockWrites = false; }
      }
      // ===== LEO PART 3 END =====
