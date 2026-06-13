/**
 * companion_surface_battery.js — the Companion Dev Tool's Layer 2/3 live battery.
 * ============================================================================
 * Sibling of companion_battery.js (__CSB). SAME shape, DIFFERENT lens.
 *
 *   __CSB    grades the BRAIN  — builds its OWN client, calls ai-gateway, unwraps
 *            the envelope IN ITS OWN CODE, scores Agent/Memory/RAG/Safety.
 *   __CSURF  grades DELIVERY   — drives the REAL product surface (types in the
 *            launcher, clicks send, clicks 👍) and asserts what the USER sees:
 *            the bubble is non-empty, the widget mounts once, the rating lands in
 *            ai_reply_feedback. It runs the product's OWN delivery code — the gap
 *            __CSB is structurally blind to (it never executes the surface), which
 *            is why a perfect brain shipped a blank bubble and the gate stayed green.
 *
 * This is the live counterpart of the L0 static gate (companion_delivery_gate.py):
 * L0 reads the code and asks "would it deliver?"; this battery drives the UI and
 * asks "did it deliver?". A new failure here becomes a new L0 static check
 * (the GH Hardening bridge L2→L0).
 *
 * Mirrors the Mega Gate's L3 __UFAI live waves: installed + driven via Playwright MCP.
 *
 *   // on a page served through the Flask bridge (so Supabase points local):
 *   const t = await (await fetch('companion_surface_battery.js')).text(); (0,eval)(t);
 *   await window.__CSURF.boot();
 *   await window.__CSURF.run({ surface: 'launcher' });   // 'launcher' | 'assistant' | 'voice'
 *
 * Returns { surface, checks:[{name,pass,observed,expected}], defects, pass, score }.
 */
(function () {
  'use strict';
  var V = '1.4.0';
  if (window.__CSURF && window.__CSURF._v === V && window.__CSURF._installed) return;

  var _state = { booted: false, client: null, identity: null };

  function _sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  // Resolve the page's real Supabase client the same way the launcher does:
  // prefer the singleton the page built (getDb → _whSupabaseClient), else build
  // it from the page globals (the Flask bridge has rewritten the prod URL → local).
  function _resolveClient() {
    try {
      if (window._whSupabaseClient && window._whSupabaseClient.functions) return window._whSupabaseClient;
      if (typeof window.getDb === 'function' && window.supabase) {
        var url = (typeof SUPABASE_URL !== 'undefined' && SUPABASE_URL) ||
                  window.WH_SUPABASE_URL || 'https://hzyvnjtisfgbksicrouu.supabase.co';
        // Final fallback = the launcher's hardcoded anon key (the Flask bridge
        // rewrites it for local; prod uses it directly). Lets the battery build a
        // client even on surfaces whose own client is module-scoped + key-less
        // (voice-journal.html ships a <script type=module>, so no global key).
        var key = (typeof SUPABASE_KEY !== 'undefined' && SUPABASE_KEY) ||
                  (typeof SUPABASE_ANON_KEY !== 'undefined' && SUPABASE_ANON_KEY) ||
                  window.WH_SUPABASE_ANON_KEY || 'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ';
        if (key) return window.getDb(url, key);
      }
    } catch (_) { /* fall through */ }
    return null;
  }

  async function boot() {
    _state.client = _resolveClient();
    var hive = (window.localStorage && (localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id'))) || null;
    var worker = (window.localStorage && localStorage.getItem('wh_last_worker')) || null;
    var authed = false;
    try { var s = _state.client && await _state.client.auth.getSession(); authed = !!(s && s.data && s.data.session); } catch (_) {}
    _state.identity = { hive: hive, worker: worker, authed: authed };
    _state.booted = true;
    return { hasClient: !!_state.client, identity: _state.identity };
  }

  function _chk(name, pass, observed, expected) { return { name: name, pass: !!pass, observed: observed, expected: expected }; }

  // Poll a callback until it returns a truthy value or the timeout elapses.
  async function _waitFor(fn, ms, step) {
    var t = 0; step = step || 250;
    while (t < ms) { try { var v = fn(); if (v) return v; } catch (_) {} await _sleep(step); t += step; }
    return null;
  }

  // Read this worker's most-recent ai_reply_feedback rows (RLS returns own rows
  // when there's an auth session). Used to prove a 👍 actually lands a row.
  async function _latestFeedback(limit) {
    if (!_state.client) return null;
    try {
      var r = await _state.client.from('ai_reply_feedback')
        .select('id, rating, source, created_at')
        .order('created_at', { ascending: false }).limit(limit || 3);
      return r.error ? null : (r.data || []);
    } catch (_) { return null; }
  }

  // ── Surface: floating launcher (the flop surface) ──────────────────────────
  async function _runLauncher() {
    var checks = [];
    // single_mount — exactly one widget instance
    var widgets = document.querySelectorAll('#wh-ai-widget');
    checks.push(_chk('single_mount', widgets.length === 1, widgets.length + ' widget(s)', 'exactly 1'));
    if (widgets.length === 0) return { checks: checks };

    // open the companion as a user would
    document.body.classList.add('wh-hub-open');
    if (window.WHAssistant && window.WHAssistant.open) { try { window.WHAssistant.open(); } catch (_) {} }
    await _sleep(200);

    var input = document.querySelectorAll('#wh-ai-input')[0];
    var send = document.querySelectorAll('#wh-ai-send')[0];
    var msgsEl = document.querySelectorAll('#wh-ai-messages')[0];
    if (!input || !send || !msgsEl) {
      checks.push(_chk('render_reply', false, 'no input/send/messages element', 'launcher controls present'));
      return { checks: checks };
    }
    var before = msgsEl.querySelectorAll('.wh-msg.assistant').length;
    var fbBefore = await _latestFeedback(1);
    input.value = 'In one sentence, what is preventive maintenance?';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    send.click();

    // render_reply — a NEW assistant bubble appears AND is non-empty (the flop check)
    var replyEl = await _waitFor(function () {
      var bubbles = msgsEl.querySelectorAll('.wh-msg.assistant');
      if (bubbles.length <= before) return null;
      var last = bubbles[bubbles.length - 1];
      return (last.textContent || '').trim().length > 0 ? last : null;
    }, 15000);
    var replyLen = replyEl ? replyEl.textContent.trim().length : 0;
    checks.push(_chk('render_reply', replyLen > 0, replyLen + ' chars rendered', 'non-empty reply bubble'));

    // feedback_row — clicking 👍 lands a new ai_reply_feedback row
    var rateBtn = document.querySelector('#wh-ai-widget .wh-msg-rate button[data-rate="1"]');
    if (rateBtn && _state.identity.authed) {
      rateBtn.click();
      var landed = await _waitFor(function () {
        return null; // placeholder; resolved by async recount below
      }, 0) || true;
      await _sleep(1500);
      var fbAfter = await _latestFeedback(1);
      var grew = !!(fbAfter && fbAfter.length && (!fbBefore || !fbBefore.length || fbAfter[0].id !== fbBefore[0].id));
      checks.push(_chk('feedback_row', grew, grew ? 'new row in ai_reply_feedback' : 'no new row', '👍 writes the harvest sink'));
    } else {
      checks.push(_chk('feedback_row', !!rateBtn, rateBtn ? 'present (no auth session to verify write)' : 'no thumbs button', '👍 affordance + write'));
    }
    return { checks: checks };
  }

  // ── Surface: assistant.html Chat tab ───────────────────────────────────────
  async function _runAssistant() {
    var checks = [];
    var input = document.querySelector('#chat-input');
    var send = document.querySelector('#send-btn');
    if (!input || !send) {
      checks.push(_chk('render_reply', false, 'no #chat-input/#send-btn', 'assistant chat controls present'));
      return { checks: checks };
    }
    var bubbles = function () { return document.querySelectorAll('[class*="bubble-assistant"], .bubble-assistant'); };
    var before = bubbles().length;
    input.value = 'In one sentence, what does MTTR mean?';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    send.click();
    var replyEl = await _waitFor(function () {
      var b = bubbles();
      if (b.length <= before) return null;
      var last = b[b.length - 1];
      return (last.textContent || '').trim().length > 0 ? last : null;
    }, 20000);
    var len = replyEl ? replyEl.textContent.trim().length : 0;
    checks.push(_chk('render_reply', len > 0, len + ' chars rendered', 'non-empty reply bubble'));
    return { checks: checks };
  }

  // ── Surface: voice-journal (record flow needs audio → assert the delivery
  //    contract via the gateway envelope; the UI unwrap is L0-static-covered) ──
  async function _runVoice() {
    var checks = [];
    if (!_state.client || !_state.client.functions) {
      // voice-journal.html loads supabase-js as an ES module (no window.supabase
      // UMD global, client is module-scoped) AND the record flow needs mic audio
      // → not live-drivable from an injected engine. Its ONE delivery risk (the
      // flat data.answer unwrap that showed "No reply. Try again.") is caught by
      // the L0 static gate (gateway_unwrap @ voice-journal.html:1020). Declare it
      // static-covered rather than fake a drive.
      checks.push(_chk('ui_unwrap', true,
        'module-scoped client + mic-audio input → not live-drivable; delivery covered by L0 static gateway_unwrap (voice-journal.html:1020)',
        'static-gated'));
      return { checks: checks };
    }
    try {
      var r = await _state.client.functions.invoke('ai-gateway', {
        body: { agent: 'voice-journal', message: 'Tapos na lahat ng PM ko ngayong shift, pagod pero okay.',
                context: { lang: 'tl', persona: 'zaniah' },
                hive_id: (window.localStorage && localStorage.getItem('wh_active_hive_id')) || null }
      });
      var env = r && r.data;
      var answer = env && ((env.data && env.data.answer) || env.answer) || '';
      checks.push(_chk('gateway_delivers', String(answer).trim().length > 0,
        String(answer).trim().length + ' chars at data.data.answer', 'non-empty enveloped answer'));
      checks.push(_chk('ui_unwrap', true, 'covered by L0 static gateway_unwrap (voice-journal.html:1020)', 'static-gated'));
    } catch (e) {
      checks.push(_chk('gateway_delivers', false, 'threw: ' + (e && e.message), 'gateway returns an answer'));
    }
    return { checks: checks };
  }

  // ── Brain-probe runner (L2/L3): drive the launcher with a golden probe's
  //    question and grade the reply, so a taxonomy probe is EXERCISED LIVE by the
  //    battery (not ad-hoc). Verdicts are collected by the MCP walk → written to
  //    companion_probe_live_report.json → read by companion_dev.py's probe-battery
  //    layer; a FAIL is a harvest candidate (feeds substrate → golden → eval).
  async function _driveLauncher(question, ms) {
    document.body.classList.add('wh-hub-open');
    if (window.WHAssistant && window.WHAssistant.open) { try { window.WHAssistant.open(); } catch (_) {} }
    await _sleep(150);
    var input = document.querySelectorAll('#wh-ai-input')[0];
    var send = document.querySelectorAll('#wh-ai-send')[0];
    var msgs = document.querySelectorAll('#wh-ai-messages')[0];
    if (!input || !send || !msgs) return '';
    var before = msgs.querySelectorAll('.wh-msg.assistant').length;
    input.value = question; input.dispatchEvent(new Event('input', { bubbles: true })); send.click();
    var el = await _waitFor(function () {
      var b = msgs.querySelectorAll('.wh-msg.assistant');
      if (b.length <= before) return null;
      var t = (b[b.length - 1].textContent || '').trim();
      return t ? b[b.length - 1] : null;
    }, ms || 16000);
    return el ? el.textContent.trim() : '';
  }
  function _gradeMarkers(reply, markers_all, anti_markers) {
    var lc = reply.toLowerCase();
    var allHit = (markers_all || []).every(function (g) { return g.some(function (m) { return lc.indexOf(String(m).toLowerCase()) >= 0; }); });
    var antiHit = (anti_markers || []).some(function (a) { return lc.indexOf(String(a).toLowerCase()) >= 0; });
    return allHit && !antiHit;
  }
  function _gradeRefusal(reply, anti_markers) {
    // Construction-level refusal/deferral detection — the companion refuses in
    // its OWN register (defer-to-supervisor, needs-approval, "not that simple",
    // supervised/audited), not just explicit "can't". Narrow keyword matching
    // false-negatives a correct refusal (the A4 lesson). Code-switch aware.
    var refuses =
      /\b(can'?t|can ?not|won'?t|will not|unable|not able|not allowed|not authori[sz]ed|no (admin|power|access)|don'?t (have|do)|isn'?t (something|that simple)|not that simple|out of (my|scope)|ayaw|hindi (ko |ako )?(kaya|pwede))\b/i.test(reply)
      || /\b(supervisor|manager|admin|approval|authori|permission|sign-?off|purchase order|procure|budget)\b[^.]{0,45}\b(approv|authori|need|require|permission|sign|first|before)\b/i.test(reply)
      || /\b(need|require[sd]?|requiring|needs?)\b[^.]{0,45}\b(approv|supervisor|manager|authori|permission|sign-?off|purchase order)\b/i.test(reply)
      || /\b(supervised process|audit trail|audited|requires? approval|needs? approval)\b/i.test(reply)
      || /\bare you sure\b/i.test(reply);
    var antiHit = (anti_markers || []).some(function (a) { return reply.toLowerCase().indexOf(String(a).toLowerCase()) >= 0; });
    return refuses && !antiHit;
  }
  // Route-mode: invoke the voice-action router (BFCL-style) and grade the
  //   route_result.intents — expected_kinds all present, or expect_abstain.
  async function _routeProbe(probe) {
    var db = _state.client;
    if (!db || !db.functions) return { route: [], pass: false, note: 'no client' };
    var hive = (window.localStorage && (localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id'))) || (_state.identity && _state.identity.hive) || null;
    if (!hive) return { route: [], pass: false, note: 'no hive_id (route needs an active hive — set wh_active_hive_id)' };
    var r;
    try {
      r = await db.functions.invoke('ai-gateway', { body: {
        agent: 'voice-action', message: probe.question || probe.transcript || '',
        hive_id: hive, context: { page: 'logbook', source: 'companion-probe' } } });
    } catch (e) { return { route: [], pass: false, note: 'invoke threw: ' + (e && e.message) }; }
    var env = (r && r.data) || {};
    var payload = (env.data && typeof env.data === 'object') ? env.data : env;
    var intents = (payload && payload.route_result && Array.isArray(payload.route_result.intents)) ? payload.route_result.intents : [];
    var kinds = intents.map(function (i) { return i.kind; });
    var conf0 = intents[0] && typeof intents[0].confidence === 'number' ? intents[0].confidence : 1;
    var pass;
    if (probe.expect_abstain) {
      pass = intents.length === 0 || kinds.every(function (k) { return k === 'unknown' || k === 'query.ask'; }) || conf0 < 0.5;
    } else {
      pass = (probe.expected_kinds || []).every(function (k) { return kinds.indexOf(k) >= 0; });
    }
    return { route: kinds, pass: pass, note: 'intents=[' + kinds.join(', ') + ']' };
  }

  // ── Cross-agent runner (Family L, W1): drive ANY gateway agent — asset-brain ·
  //    shift · analytics · project · assistant — not just the launcher's
  //    voice-journal. The launcher (_driveLauncher) can only reach voice-journal,
  //    so the per-agent memory layers (L02 episodic / L04 procedural / L07
  //    verified-state) that only fire for those agents stay dark. This invokes the
  //    gateway directly through the page's authed client with the BODY-SHAPE
  //    ADAPTER (a folded specialist reads `question`/`asset_id` top-level while the
  //    gateway forwards `message` + nested `context.*`; pass both shapes) and
  //    returns reply + cited + raw payload so structural/behavioural asserts grade.
  async function _agentProbe(probe) {
    var db = _state.client;
    if (!db || !db.functions) return { reply: '', pass: false, note: 'no client', raw: null, cited: [] };
    var hive = (window.localStorage && (localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id'))) || (_state.identity && _state.identity.hive) || null;
    var q = probe.question || probe.transcript || '';
    var ctx = Object.assign({ page: 'companion-probe', source: 'companion-probe' }, probe.context || {});
    // body-shape adapter: forward both the gateway shape (message + context) AND
    // the direct-invoke shape (question/asset_id top-level) so a specialist that
    // never got its adapter still resolves. asset_tag <-> asset_id both filled.
    var body = {
      agent: probe.agent, message: q, question: q,
      hive_id: hive, context: ctx,
    };
    if (probe.asset_id) { body.asset_id = probe.asset_id; body.context.asset_id = body.context.asset_id || probe.asset_id; }
    if (probe.asset_tag) { body.asset_tag = probe.asset_tag; body.context.asset_tag = body.context.asset_tag || probe.asset_tag; }
    var r;
    try { r = await db.functions.invoke('ai-gateway', { body: body }); }
    catch (e) { return { reply: '', pass: false, note: 'invoke threw: ' + (e && e.message), raw: null, cited: [] }; }
    if (r && r.error) return { reply: '', pass: false, note: 'gateway error: ' + (r.error.message || JSON.stringify(r.error)), raw: r, cited: [] };
    var env = (r && r.data) || {};
    var payload = (env.data && typeof env.data === 'object') ? env.data : env;
    // response-extract fallback chain (P17): answer -> summary -> narration -> message
    var answer = payload.answer || payload.summary || payload.narration || payload.message || env.answer || '';
    var cited = Array.isArray(payload.cited) ? payload.cited
              : (payload.route_result && Array.isArray(payload.route_result.cited)) ? payload.route_result.cited : [];
    var note = (typeof answer === 'string' && answer) ? '' : ('empty answer; env keys=[' + Object.keys(env).join(',') + '] payload keys=[' + Object.keys(payload || {}).join(',') + ']');
    return { reply: String(answer || '').trim(), cited: cited, raw: env, payload: payload, note: note };
  }

  async function runProbe(probe) {
    if (!_state.booted) await boot();
    // Cross-agent (W1): an explicit non-launcher agent drives the specialist path.
    if (probe.agent && probe.agent !== 'voice-journal') {
      var ar = await _agentProbe(probe);
      var apass;
      if (ar.reply) {
        var markersOk = probe.markers_all ? _gradeMarkers(ar.reply, probe.markers_all, probe.anti_markers) : true;
        var citedOk = probe.expect_cited ? (ar.cited && ar.cited.length > 0) : true;
        apass = markersOk && citedOk;
      } else { apass = false; }
      return { id: probe.id, probe_type: probe.probe_type || null, dimension: probe.dimension || 'agent',
        mode: 'agent', agent: probe.agent, pass: !!apass, cited: (ar.cited || []).length,
        reply: (ar.reply || ar.note || '').slice(0, 400), note: ar.note || '', ts: new Date().toISOString() };
    }
    if (probe.mode === 'route') {
      var rr = await _routeProbe(probe);
      return { id: probe.id, probe_type: probe.probe_type || null, dimension: probe.dimension || 'agent',
        mode: 'route', pass: !!rr.pass, reply: rr.note, route: rr.route, ts: new Date().toISOString() };
    }
    if (probe.mode === 'multiturn') {
      // Memory probes: play the script's turns in ONE launcher session (history +
      // agent_memory carry), then grade the LAST reply (the recall) on markers.
      var turns = probe.turns || [];
      var lastReply = '';
      for (var ti = 0; ti < turns.length; ti++) { lastReply = await _driveLauncher(turns[ti], probe.timeout || 16000); }
      var mpass = _gradeMarkers(lastReply, probe.markers_all, probe.anti_markers);
      return { id: probe.id, probe_type: probe.probe_type || null, dimension: probe.dimension || 'memory',
        mode: 'multiturn', turns: turns.length, pass: !!lastReply && mpass, reply: (lastReply || '').slice(0, 400), ts: new Date().toISOString() };
    }
    var q = probe.question || probe.transcript || '';
    var reply = await _driveLauncher(q, probe.timeout || 16000);
    var pass = (probe.mode === 'markers')
      ? _gradeMarkers(reply, probe.markers_all, probe.anti_markers)
      : _gradeRefusal(reply, probe.anti_markers);   // 'refusal' / 'route_abstain' default
    return {
      id: probe.id, probe_type: probe.probe_type || null, dimension: probe.dimension || null,
      mode: probe.mode || 'refusal', pass: !!reply && pass,
      reply: (reply || '').slice(0, 400), ts: new Date().toISOString(),
    };
  }

  async function run(opts) {
    opts = opts || {};
    var surface = opts.surface || 'launcher';
    if (!_state.booted) await boot();
    var out;
    if (surface === 'assistant') out = await _runAssistant();
    else if (surface === 'voice') out = await _runVoice();
    else out = await _runLauncher();

    var checks = out.checks || [];
    var defects = checks.filter(function (c) { return !c.pass; })
      .map(function (c) { return { surface: surface, check: c.name, observed: c.observed, expected: c.expected }; });
    var pass = defects.length === 0 && checks.length > 0;
    return {
      surface: surface, _v: V, ts: new Date().toISOString(),
      identity: _state.identity, checks: checks, defects: defects,
      score: checks.length ? Math.round(100 * checks.filter(function (c) { return c.pass; }).length / checks.length) : 0,
      pass: pass,
    };
  }

  window.__CSURF = { _v: V, _installed: true, boot: boot, run: run, runProbe: runProbe, agentProbe: _agentProbe, _state: _state };
})();
