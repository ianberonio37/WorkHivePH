/**
 * WorkHive Voice Handler
 * ────────────────────────────────────────────────────────────────────────────
 * Cross-page voice command UI. Lazy-loaded by nav-hub.js (same pattern as
 * search-overlay.js). Records audio via MediaRecorder, transcribes via the
 * voice-transcribe edge function, classifies intent via voice-action-router
 * (which reads canonical v_asset_truth for asset resolution), then dispatches
 * to per-page handlers registered via WHVoice.register(kind, handler).
 *
 * Public API:
 *   WHVoice.register(kind, handler)  — page tells WHVoice it can handle this intent
 *   WHVoice.open()                   — show the voice overlay (start recording)
 *   WHVoice.close()                  — hide the overlay
 *   WHVoice.dispatch(intent, ctx)    — programmatic dispatch (for tests)
 *
 * Per-page integration pattern:
 *   document.addEventListener('DOMContentLoaded', () => {
 *     if (window.WHVoice) {
 *       WHVoice.register('logbook.create', async (intent) => {
 *         const p = intent.params;
 *         document.getElementById('machine').value = p.machine || '';
 *         // ... fill form fields, scroll into view
 *         return { ok: true, message: 'Form pre-filled. Review and tap Save.' };
 *       });
 *     }
 *   });
 *
 * Skills consulted: ai-engineer (callAI rate limit + transcript cap already
 * enforced in voice-action-router), security (confirmation BEFORE any
 * write, escape user-controlled strings on render, audio size cap 10 MB),
 * mobile-maestro (44px+ targets, viewport-fit safe areas, 16px input,
 * MediaRecorder works on iOS 14+), architect (DB write must confirm first;
 * unknown intents fall through to floating-ai chat, never assume).
 */

(function () {
  'use strict';

  if (window.WHVoice) return; // singleton guard

  // ─── Config ─────────────────────────────────────────────────────────────
  const SUPABASE_URL = 'https://hzyvnjtisfgbksicrouu.supabase.co';
  const SUPABASE_KEY = 'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ';
  const MAX_RECORD_MS = 30 * 1000;
  const MAX_TRANSCRIPT_CHARS = 500;

  let _db = null;
  function _getDb() {
    if (!_db && window.supabase) {
      _db = window.supabase.createClient(SUPABASE_URL, SUPABASE_KEY);
    }
    return _db;
  }

  // Read identity / hive context from localStorage (canonical pattern)
  function _ctx() {
    return {
      worker_name:
        localStorage.getItem('wh_last_worker') ||
        localStorage.getItem('wh_worker_name') ||
        localStorage.getItem('workerName') || '',
      hive_id:
        localStorage.getItem('wh_active_hive_id') ||
        localStorage.getItem('wh_hive_id') || '',
      hive_role: localStorage.getItem('wh_hive_role') || '',
    };
  }

  function _currentPage() {
    const path = (location.pathname || '').toLowerCase();
    const m = path.match(/\/?([a-z0-9-]+)\.html/);
    return m ? m[1] : 'home';
  }

  function _currentAssetId() {
    try {
      const u = new URL(location.href);
      return u.searchParams.get('asset_id') || u.searchParams.get('node_id') || null;
    } catch (_) { return null; }
  }

  // Minimal HTML escape (mirrors utils.js escHtml; in case utils.js isn't on this page)
  function escHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  // ─── State ───────────────────────────────────────────────────────────────
  const handlers = {};            // kind -> async fn(intent, asset_resolution)
  let _stream = null;
  let _recorder = null;
  let _chunks = [];
  let _stopTimer = null;
  let _sessionId = null;          // Phase 2: session-scoped memory tracking
  let _turnNum = 0;               // Phase 2: turn counter per session

  // Phase 2: Initialize session ID (per-tab or per-conversation window)
  function _getSessionId() {
    if (!_sessionId) {
      _sessionId = 'voice_session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
      if (typeof sessionStorage !== 'undefined') {
        sessionStorage.setItem('wh_voice_session_id', _sessionId);
      }
    }
    return _sessionId;
  }

  // ─── Styles + DOM ────────────────────────────────────────────────────────
  const STYLE = `
    .wh-voice-btn {
      position: fixed; right: 16px; bottom: calc(86px + env(safe-area-inset-bottom));
      width: 52px; height: 52px; border-radius: 50%; border: none;
      background: linear-gradient(135deg, #29B6D9, #1f8aab); color: #fff;
      box-shadow: 0 6px 18px rgba(31,138,171,0.45);
      display: flex; align-items: center; justify-content: center;
      cursor: pointer; z-index: 9990; font-family: 'Poppins', sans-serif;
      transition: transform 0.12s, box-shadow 0.12s;
    }
    .wh-voice-btn:hover  { transform: translateY(-1px); box-shadow: 0 8px 22px rgba(31,138,171,0.55); }
    .wh-voice-btn:active { transform: scale(0.95); }
    .wh-voice-btn[disabled] { opacity: 0.5; cursor: not-allowed; }
    .wh-voice-btn.recording { background: linear-gradient(135deg, #EF5757, #c33b3b); animation: wh-voice-pulse 1.2s ease-in-out infinite; }
    @keyframes wh-voice-pulse {
      0%, 100% { box-shadow: 0 6px 18px rgba(195,59,59,0.45); }
      50%      { box-shadow: 0 8px 30px rgba(195,59,59,0.85); }
    }

    .wh-voice-overlay {
      position: fixed; inset: 0; z-index: 9995; display: none;
      align-items: center; justify-content: center;
      background: rgba(10,18,28,0.82); backdrop-filter: blur(6px);
      padding: 1rem; padding-bottom: calc(1rem + env(safe-area-inset-bottom));
      font-family: 'Poppins', sans-serif;
    }
    .wh-voice-overlay.open { display: flex; }
    .wh-voice-card {
      width: 100%; max-width: 460px;
      background: linear-gradient(145deg, rgba(42,61,88,0.97), rgba(22,32,50,0.99));
      border: 1px solid rgba(255,255,255,0.10);
      border-radius: 1.25rem; padding: 1.25rem 1.1rem;
      color: #F4F6FA;
      box-shadow: 0 30px 70px rgba(0,0,0,0.55);
      max-height: 90vh; overflow-y: auto;
    }
    .wh-voice-title {
      font-size: 0.66rem; letter-spacing: 0.10em; text-transform: uppercase;
      color: rgba(255,255,255,0.6); margin-bottom: 0.4rem;
    }
    .wh-voice-status {
      font-size: 1.1rem; font-weight: 700; margin-bottom: 0.85rem;
    }
    .wh-voice-rec-row {
      display: flex; align-items: center; gap: 0.65rem; margin: 0.6rem 0 0.85rem;
    }
    .wh-voice-dot {
      width: 10px; height: 10px; border-radius: 50%; background: #EF5757;
      box-shadow: 0 0 10px #EF5757;
      animation: wh-voice-dot-pulse 1s ease-in-out infinite;
    }
    @keyframes wh-voice-dot-pulse {
      0%, 100% { opacity: 0.4; transform: scale(1); }
      50%      { opacity: 1;   transform: scale(1.25); }
    }
    .wh-voice-elapsed { font-size: 0.85rem; color: rgba(255,255,255,0.7); }

    .wh-voice-transcript {
      background: rgba(255,255,255,0.05);
      border: 1px dashed rgba(255,255,255,0.12);
      border-radius: 0.6rem; padding: 0.65rem 0.85rem;
      font-size: 0.85rem; line-height: 1.45; color: #F4F6FA;
      margin-bottom: 0.85rem; min-height: 2.6rem;
    }

    .wh-voice-intent-card {
      background: rgba(255,255,255,0.04);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 0.85rem; padding: 0.75rem 0.9rem;
      margin-bottom: 0.55rem;
    }
    .wh-voice-kind {
      font-size: 0.62rem; letter-spacing: 0.08em; text-transform: uppercase;
      color: #F7A21B; font-weight: 700;
    }
    .wh-voice-conf {
      font-size: 0.62rem; color: rgba(255,255,255,0.5); float: right;
    }
    .wh-voice-summary {
      font-size: 0.92rem; line-height: 1.45; margin: 0.4rem 0 0.4rem;
      color: #F4F6FA; word-break: break-word;
    }
    .wh-voice-asset-pill {
      display: inline-block; padding: 2px 9px; border-radius: 999px;
      background: rgba(247,162,27,0.18); color: #ffc566;
      font-size: 0.66rem; font-weight: 700; letter-spacing: 0.04em;
      margin-right: 0.35rem;
    }
    .wh-voice-asset-pill.ambiguous { background: rgba(239,87,87,0.18); color: #ff8a8a; }

    .wh-voice-actions {
      display: flex; gap: 0.45rem; margin-top: 0.85rem;
    }
    .wh-voice-btn-action {
      flex: 1; min-height: 44px; border-radius: 0.65rem;
      font-size: 0.88rem; font-weight: 700; cursor: pointer;
      font-family: inherit; border: 1px solid transparent;
    }
    .wh-voice-confirm {
      background: linear-gradient(135deg, #4ADE80, #22a155); color: #0b1a10; border-color: transparent;
    }
    .wh-voice-confirm:disabled { opacity: 0.5; cursor: not-allowed; }
    .wh-voice-cancel {
      background: rgba(255,255,255,0.06); color: #F4F6FA;
      border-color: rgba(255,255,255,0.14);
    }
    .wh-voice-stop {
      background: linear-gradient(135deg, #F7A21B, #FDB94A); color: #162032; border-color: transparent;
      font-weight: 700;
    }
    .wh-voice-stop:hover { box-shadow: 0 4px 14px rgba(247,162,27,0.45); }

    /* Conversational bubble — when voice-router classifies as query.ask
       we drop the intent card and render the journal-agent reply here. */
    .wh-voice-bubble {
      display: flex; align-items: flex-start; gap: 0.6rem;
      background: rgba(247,162,27,0.06);
      border: 1px solid rgba(247,162,27,0.22);
      border-radius: 0.95rem;
      padding: 0.7rem 0.85rem 0.75rem;
      margin: 0.4rem 0 0.55rem;
      animation: wh-bubble-in 0.22s ease forwards;
    }
    @keyframes wh-bubble-in {
      from { opacity: 0; transform: translateY(4px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    .wh-voice-bubble-text {
      flex: 1;
      font-size: 0.94rem;
      line-height: 1.5;
      color: #F4F6FA;
      word-break: break-word;
      white-space: pre-wrap;
    }
    /* Thinking dots while we wait for the model. */
    .wh-voice-dots { display: inline-flex; gap: 4px; }
    .wh-voice-dots i {
      width: 6px; height: 6px; border-radius: 50%;
      background: #F7A21B; opacity: 0.4;
      animation: wh-dot 1.2s ease-in-out infinite;
    }
    .wh-voice-dots i:nth-child(2) { animation-delay: 0.15s; }
    .wh-voice-dots i:nth-child(3) { animation-delay: 0.30s; }
    @keyframes wh-dot {
      0%, 80%, 100% { opacity: 0.2; transform: scale(0.85); }
      40%           { opacity: 1;   transform: scale(1.10); }
    }
    .wh-voice-result {
      margin-top: 0.65rem; font-size: 0.82rem; line-height: 1.45;
      color: rgba(255,255,255,0.85);
      padding: 0.55rem 0.75rem; border-radius: 0.55rem;
      background: rgba(74,222,128,0.10);
      border: 1px solid rgba(74,222,128,0.25);
    }
    .wh-voice-result.error {
      background: rgba(239,87,87,0.10);
      border-color: rgba(239,87,87,0.25);
      color: #ffaeae;
    }
  `;

  const VOICE_BTN_HTML = `
    <button id="wh-voice-btn" class="wh-voice-btn" aria-label="Voice command" title="Voice command">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"/>
        <path d="M19 10v2a7 7 0 01-14 0v-2"/>
        <line x1="12" y1="19" x2="12" y2="23"/>
        <line x1="8" y1="23" x2="16" y2="23"/>
      </svg>
    </button>`;

  const OVERLAY_HTML = `
    <div id="wh-voice-overlay" class="wh-voice-overlay" role="dialog" aria-modal="true" aria-labelledby="wh-voice-status">
      <div class="wh-voice-card">
        <div class="wh-voice-title">Voice command</div>
        <div id="wh-voice-status" class="wh-voice-status">Listening...</div>
        <div id="wh-voice-rec-row" class="wh-voice-rec-row">
          <span class="wh-voice-dot"></span>
          <span class="wh-voice-elapsed" id="wh-voice-elapsed">0:00</span>
          <span style="margin-left:auto;font-size:0.7rem;color:rgba(255,255,255,0.4);">Tap Stop when done</span>
        </div>
        <div id="wh-voice-transcript" class="wh-voice-transcript" style="display:none;"></div>
        <div id="wh-voice-intents"></div>
        <div id="wh-voice-result" style="display:none;"></div>
        <div class="wh-voice-actions">
          <button id="wh-voice-cancel" class="wh-voice-btn-action wh-voice-cancel" type="button">Cancel</button>
          <button id="wh-voice-stop" class="wh-voice-btn-action wh-voice-stop" type="button">Stop</button>
          <button id="wh-voice-confirm" class="wh-voice-btn-action wh-voice-confirm" type="button" style="display:none;">Confirm</button>
        </div>
      </div>
    </div>`;

  // ─── Mount ────────────────────────────────────────────────────────────────
  // Companion Streamline Step A: the standalone blue button is no
  // longer mounted. The single voice entry point is the mic icon inside
  // floating-ai's panel, which delegates here via WHVoice.open(). Only
  // the overlay (recording UI + intent confirmation) is mounted.
  function _mount() {
    if (document.getElementById('wh-voice-overlay')) return;
    const style = document.createElement('style');
    style.id = 'wh-voice-styles';
    style.textContent = STYLE;
    document.head.appendChild(style);

    const ovDiv = document.createElement('div');
    ovDiv.innerHTML = OVERLAY_HTML.trim();
    document.body.appendChild(ovDiv.firstElementChild);

    const cancel  = document.getElementById('wh-voice-cancel');
    const stop    = document.getElementById('wh-voice-stop');
    if (cancel) cancel.addEventListener('click', () => close());
    if (stop)   stop.addEventListener('click', () => _stopRecording());

    document.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape' && _isOpen()) close();
    });
  }

  function _isOpen() {
    const ov = document.getElementById('wh-voice-overlay');
    return !!(ov && ov.classList.contains('open'));
  }

  function _setStatus(msg) {
    const el = document.getElementById('wh-voice-status');
    if (el) el.textContent = msg;
  }

  function _setTranscript(text) {
    const el = document.getElementById('wh-voice-transcript');
    if (!el) return;
    if (!text) { el.style.display = 'none'; el.textContent = ''; return; }
    el.style.display = 'block';
    el.textContent = text;
  }

  function _setResult(text, isError) {
    const el = document.getElementById('wh-voice-result');
    if (!el) return;
    if (!text) { el.style.display = 'none'; el.innerHTML = ''; el.classList.remove('error'); return; }
    el.style.display = 'block';
    el.classList.toggle('error', !!isError);
    el.textContent = text;
  }

  function _setRecRowVisible(v) {
    const row = document.getElementById('wh-voice-rec-row');
    if (row) row.style.display = v ? 'flex' : 'none';
  }

  function _summariseIntent(intent) {
    const p = intent.params || {};
    if (intent.kind === 'logbook.create') {
      const parts = [];
      if (p.machine) parts.push(`on ${p.machine}`);
      if (p.action)  parts.push(`(${p.action})`);
      if (p.maintenance_type) parts.push(`[${p.maintenance_type}]`);
      if (p.downtime_hours != null) parts.push(`${p.downtime_hours}h downtime`);
      const head = parts.join(' ').trim() || 'New entry';
      const partsList = Array.isArray(p.parts_used) && p.parts_used.length
        ? `Parts: ${p.parts_used.map(x => `${x.qty || 1} x ${x.part_name}`).join(', ')}`
        : '';
      return [head, partsList].filter(Boolean).join('. ');
    }
    if (intent.kind === 'inventory.deduct') {
      const list = Array.isArray(p.parts) ? p.parts : [];
      return `Deduct ${list.map(x => `${x.qty || 1} x ${x.part_name}`).join(', ') || '(no parts parsed)'}.`;
    }
    if (intent.kind === 'pm.complete') {
      const head = p.machine ? `PM on ${p.machine}` : 'PM completion';
      return [head, p.task_summary].filter(Boolean).join(': ');
    }
    if (intent.kind === 'asset.lookup') {
      return `Look up: ${p.question || p.machine || '(no detail)'}.`;
    }
    if (intent.kind === 'query.ask') {
      return `Ask assistant: ${p.question || '(no question)'}.`;
    }
    return 'Unrecognised command. Falls through to assistant chat.';
  }

  function _renderIntents(intents, assetResolution) {
    const root = document.getElementById('wh-voice-intents');
    if (!root) return;
    if (!intents || !intents.length) {
      root.innerHTML = `<div class="wh-voice-intent-card">
        <div class="wh-voice-kind">unknown</div>
        <div class="wh-voice-summary">No actionable command detected. Say something like:
          "I just replaced the V-belt on Pump P-5, took 20 minutes"
          or "Show me Pump 5".</div>
      </div>`;
      return;
    }
    const ar = assetResolution || {};
    const candidates = Array.isArray(ar.candidates) ? ar.candidates : [];
    const ambiguous = !!ar.ambiguous;
    const primary  = ar.primary;

    let assetHtml = '';
    if (primary) {
      assetHtml = `<span class="wh-voice-asset-pill${ambiguous ? ' ambiguous' : ''}">${
        escHtml(primary.tag || primary.name || 'asset')
      }${ambiguous ? ' (multiple matches)' : ''}</span>`;
    } else if (candidates.length === 0 && (ar.mentioned_assets || []).length) {
      assetHtml = `<span class="wh-voice-asset-pill ambiguous">no match</span>`;
    }

    root.innerHTML = intents.map((it, idx) => `
      <div class="wh-voice-intent-card" data-idx="${idx}">
        <div>
          <span class="wh-voice-kind">${escHtml(it.kind)}</span>
          <span class="wh-voice-conf">${Math.round((it.confidence || 0) * 100)}%</span>
        </div>
        <div class="wh-voice-summary">${idx === 0 ? assetHtml : ''}${escHtml(_summariseIntent(it))}</div>
      </div>
    `).join('');
  }

  // ─── Recording ────────────────────────────────────────────────────────────
  async function _toggle() {
    if (_recorder && _recorder.state === 'recording') {
      _stopRecording();
      return;
    }
    open();
  }

  async function _startRecording() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      _setStatus('Voice not supported on this browser.');
      _setRecRowVisible(false);
      return;
    }
    try {
      _stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      _setStatus('Microphone permission denied.');
      _setRecRowVisible(false);
      return;
    }
    _chunks = [];
    const mime = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/mp4';
    _recorder = new MediaRecorder(_stream, { mimeType: mime });
    _recorder.ondataavailable = (ev) => { if (ev.data && ev.data.size) _chunks.push(ev.data); };
    _recorder.onstop = _onStopRecording;
    _recorder.start();
    document.getElementById('wh-voice-btn')?.classList.add('recording');
    _setStatus('Listening...');
    _setRecRowVisible(true);
    // Show the in-overlay Stop button so the worker has a tap-to-stop
    // affordance now that the standalone blue mic is gone.
    const stopBtn = document.getElementById('wh-voice-stop');
    if (stopBtn) stopBtn.style.display = '';

    const startedAt = Date.now();
    const elTimer = document.getElementById('wh-voice-elapsed');
    if (elTimer) {
      const tick = () => {
        if (!_recorder || _recorder.state !== 'recording') return;
        const s = Math.floor((Date.now() - startedAt) / 1000);
        elTimer.textContent = `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`;
        requestAnimationFrame(tick);
      };
      tick();
    }

    _stopTimer = setTimeout(_stopRecording, MAX_RECORD_MS);
  }

  function _stopRecording() {
    if (_stopTimer) { clearTimeout(_stopTimer); _stopTimer = null; }
    if (_recorder && _recorder.state === 'recording') _recorder.stop();
    document.getElementById('wh-voice-btn')?.classList.remove('recording');
    // Hide the Stop button — the recording loop is finished. Confirm
    // appears after transcription + intent classification land.
    const stopBtn = document.getElementById('wh-voice-stop');
    if (stopBtn) stopBtn.style.display = 'none';
  }

  async function _onStopRecording() {
    _setRecRowVisible(false);
    _setStatus('Transcribing...');
    if (_stream) { _stream.getTracks().forEach(t => t.stop()); _stream = null; }
    if (!_chunks.length) {
      _setStatus('No audio captured.');
      return;
    }
    const blob = new Blob(_chunks, { type: _recorder?.mimeType || 'audio/webm' });
    const ctx = _ctx();
    if (!ctx.hive_id) {
      _setStatus('Voice needs a hive. Join or create one first.');
      return;
    }
    try {
      // Step 1: voice-transcribe (multipart/form-data)
      // Force English transcription. Whisper's auto-detect was hallucinating
      // Russian / Indonesian on short PH-English clips because the audio
      // budget per frame is too small to disambiguate. WorkHive workers
      // speak English, Tagalog, or Cebuano — for command intent
      // (voice-router) we want English text we can parse, so we lock the
      // hint to "en" and let Whisper do best-effort translation for the
      // few Filipino words.
      const fd = new FormData();
      fd.append('audio', blob, 'voice.webm');
      fd.append('language', 'en');
      const tResp = await fetch(SUPABASE_URL + '/functions/v1/voice-transcribe', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + SUPABASE_KEY, 'apikey': SUPABASE_KEY },
        body: fd,
      });
      const tData = await tResp.json();
      if (!tResp.ok) throw new Error(tData.error || 'Transcribe failed');
      const transcript = String(tData.text || '').trim().slice(0, MAX_TRANSCRIPT_CHARS);
      if (!transcript) {
        _setStatus('I did not catch that. Try again.');
        return;
      }
      _setTranscript(transcript);

      // Step 2: voice-action-router
      _setStatus('Parsing intent...');
      const db = _getDb();
      if (!db) throw new Error('Supabase client not loaded');
      const { data: routerData, error: routerErr } = await db.functions.invoke('voice-action-router', {
        body: {
          transcript,
          hive_id: ctx.hive_id,
          context_page: _currentPage(),
          context_asset_id: _currentAssetId(),
          // Persona Contract: ctx.persona drives the narration field's
          // voice. Gateway-hydrated default is used if absent.
          persona: (typeof window.getPersona === 'function') ? window.getPersona() : undefined,
        },
      });
      if (routerErr) throw new Error(routerErr.message || 'Router failed');
      if (!routerData) throw new Error('Empty router response');
      if (routerData.error) throw new Error(routerData.error);

      // hasActionable = there's a structured intent we COULD dispatch
      // (logbook.create, inventory.use, etc.) — but only useful if the
      // current page has a handler registered for it. A page without
      // handlers (e.g. index.html, voice-journal in iframe) would just
      // tell the worker "no handler registered" which is useless.
      const structured = (routerData.intents || []).filter(
        it => it.kind !== 'unknown' && it.kind !== 'query.ask',
      );
      const handlableHere = structured.some(it => handlers[it.kind]);
      const hasActionable = structured.length > 0 && handlableHere;

      const confirmBtn = document.getElementById('wh-voice-confirm');

      if (hasActionable) {
        // STRUCTURED INTENT PATH — logbook.create, inventory.use, etc.
        // Render intent cards, play router narration, wait for Confirm.
        _renderIntents(routerData.intents || [], routerData.asset_resolution);
        if (routerData.narration && typeof window.speakPersona === 'function') {
          window.speakPersona(routerData.narration);
        }
        if (confirmBtn) {
          confirmBtn.style.display = 'block';
          confirmBtn.disabled = false;
          confirmBtn.onclick = () => _confirm(routerData);
        }
        _setStatus('Review and confirm.');
      } else {
        // CONVERSATIONAL PATH — query.ask / unknown / unhandled-structured.
        // Pass full router output so _converseInline can use router's intent
        // classification instead of re-parsing with duplicate regex classifier.
        document.getElementById('wh-voice-intents').innerHTML = '';
        if (confirmBtn) confirmBtn.style.display = 'none';
        const unhandledKind = structured.length && !handlableHere
          ? structured[0].kind : null;
        await _converseInline(transcript, {
          routerIntents: routerData.intents,
          routerNarration: routerData.narration,
          assetResolution: routerData.asset_resolution,
          unhandledKind,
        });
      }
    } catch (err) {
      console.error('[WHVoice]', err);
      _setStatus('Could not process voice command.');
      _setResult((err && err.message) || String(err), true);
    }
  }

  // ─── Confirm + dispatch ──────────────────────────────────────────────────
  async function _confirm(routerData) {
    const intents = (routerData && routerData.intents) || [];
    const ar = routerData && routerData.asset_resolution;
    const confirmBtn = document.getElementById('wh-voice-confirm');
    if (confirmBtn) { confirmBtn.disabled = true; confirmBtn.textContent = 'Working...'; }

    const messages = [];
    let anyError = false;
    for (const intent of intents) {
      if (intent.kind === 'unknown' || intent.kind === 'query.ask') continue;
      try {
        const result = await dispatch(intent, ar);
        if (result && result.message) messages.push(result.message);
        if (result && result.ok === false) { anyError = true; messages.push(result.message || 'Failed.'); }
      } catch (err) {
        anyError = true;
        messages.push('Error: ' + ((err && err.message) || err));
      }
    }
    _setResult(messages.join('\n') || 'Done.', anyError);
    if (confirmBtn) {
      confirmBtn.textContent = 'Done';
      confirmBtn.disabled = false;
      confirmBtn.onclick = () => close();
    }
  }

  // Programmatic dispatch (also used by _confirm).
  async function dispatch(intent, assetResolution) {
    const handler = handlers[intent.kind];
    if (!handler) {
      return {
        ok: false,
        message: `No handler registered for "${intent.kind}" on this page. Open the right page (e.g. Logbook for logbook.create) and try again.`,
      };
    }
    return await handler(intent, assetResolution || {});
  }

  // ─── Conversational path ─────────────────────────────────────────────────
  // Calls the same Cloudflare Worker assistant.html / floating-ai uses, with
  // a focused work+empathy system prompt. The journal agent was the wrong
  // target here — its conversational mode is for emotional reflection only
  // ("I'm tired" / "stress na ako") and explicitly tells the model NOT to
  // diagnose, plan, or answer work questions. Sending "what is the priority
  // PM?" to it produced a feelings-check answer instead of guidance.
  //
  // After the reply, we still save the turn to voice_journal_entries so
  // every conversation lands in the worker's journal as expected.
  const WH_ASSISTANT_WORKER_URL = 'https://workhive-assistant.ian-beronio37.workers.dev';

  // Session-only fallback memory. voice_journal_entries requires auth
  // (RLS: auth.uid() = auth_uid for both read and insert), so anon
  // workers in the Tester walkthrough have no persistent memory. We
  // keep the last few turns in a module-local array so within one page
  // session James / Rosa still has continuity. Lost on page reload —
  // signed-in workers get durable history from the table.
  const _sessionTurns = [];   // [{ user, assistant, ts }]
  const _SESSION_TURN_LIMIT = 5;

  function _appendSessionTurn(transcript, reply) {
    _sessionTurns.push({
      user:      String(transcript || '').slice(0, 240),
      assistant: String(reply || '').slice(0, 240),
      ts:        Date.now(),
    });
    if (_sessionTurns.length > _SESSION_TURN_LIMIT) {
      _sessionTurns.splice(0, _sessionTurns.length - _SESSION_TURN_LIMIT);
    }
  }

  // Canonical-data intent classifier. Detects when the worker is asking
  // for a number that lives in v_*_truth so we can fetch it BEFORE the
  // LLM call and inject it as DATA. Without this, the model knows the
  // hard rule "never invent numbers" and falls back to the vaguest legal
  // answer ("check Analytics") on every turn — even when the worker is
  // clearly asking for the actual figure.
  //
  // Conservative on purpose: ONLY matches obvious canonical-data asks.
  // Free-form chat ("how do I check bearings?", "ang init dito") falls
  // through to the persona-only path unchanged.
  function _classifyDataIntent(transcriptRaw) {
    const t = String(transcriptRaw || '').toLowerCase();
    if (!t.trim()) return null;
    // MTBF — direct keyword + common Tagalog framings ("gaano katagal
    // bago masira", "average time between failures").
    if (/\bmtbf\b|mean time between fail|gaano katagal.*sira|average.*between.*fail/.test(t)) {
      return { kind: 'mtbf', window_days: _extractWindow(t, 30) };
    }
    // MTTR
    if (/\bmttr\b|mean time to repair|gaano katagal.*ayos|average.*repair time/.test(t)) {
      return { kind: 'mttr', window_days: _extractWindow(t, 30) };
    }
    // Downtime / breakdown count
    if (/\bdowntime\b|total downtime|how much downtime|gaano katagal.*off|ilang oras.*sira/.test(t)) {
      return { kind: 'downtime', window_days: _extractWindow(t, 30) };
    }
    // Risk ranking — "what are the highest risk", "top risk assets",
    // "anong pinaka-risky", "alin ang madaling masira".
    if (/(top|highest|biggest|pinaka).{0,15}(risk|risky)|(risk|risky).{0,20}(asset|machine|equipment)|alin.*madaling.*sira/.test(t)) {
      return { kind: 'risk_top', limit: 3 };
    }
    // Failures count — "how many breakdowns", "ilang beses nasira"
    if (/how many.*(failure|breakdown|fail)|ilang beses.*sira|number of breakdowns/.test(t)) {
      return { kind: 'failures_count', window_days: _extractWindow(t, 30) };
    }
    return null;
  }

  // Extract a window from natural language: "this month" / "30 days" /
  // "last quarter". Returns a window in days, defaulting to fallback.
  function _extractWindow(t, fallback) {
    if (/\bthis month\b|\bngayong buwan\b|\bngayon this month\b|\blast 30\b|\b30 days\b/.test(t)) return 30;
    if (/\blast 90\b|\b90 days\b|\bquarter\b|\bquarterly\b/.test(t)) return 90;
    if (/\bthis year\b|\bngayong taon\b|\blast year\b|\b365 days\b|\bannual\b/.test(t)) return 365;
    return fallback;
  }

  // Fetch canonical data for the classified intent. Returns a small
  // string block to inject into the system prompt, or '' if anything
  // fails. Reads v_kpi_truth (MTBF/MTTR/downtime/failures) and
  // v_risk_truth (risk_top). Hive-scoped via the worker's active hive.
  // Sub-second latency; no AI cost; uses the canonical source the rest
  // of the platform reads from.
  async function _fetchCanonicalData(db, hiveId, intent) {
    if (!db || !intent || !hiveId) return '';
    try {
      if (intent.kind === 'risk_top') {
        const { data, error } = await db.from('v_risk_truth')
          .select('asset_name, risk_score, risk_level')
          .eq('hive_id', hiveId)
          .order('risk_score', { ascending: false })
          .limit(intent.limit || 3);
        if (error || !data || !data.length) return '';
        const lines = data.map(r => '  - ' + r.asset_name + ': ' + r.risk_level + ' (score ' + Number(r.risk_score).toFixed(2) + ')');
        return 'CANONICAL DATA from v_risk_truth — your hive\'s top at-risk assets right now:\n' + lines.join('\n');
      }
      // All MTBF / MTTR / downtime / failures live in v_kpi_truth.
      const win = intent.window_days || 30;
      const col = _kpiColumn(intent.kind, win);
      if (!col) return '';
      const { data, error } = await db.from('v_kpi_truth')
        .select('machine, ' + col + ', generated_at')
        .eq('hive_id', hiveId)
        .not(col, 'is', null);
      if (error || !data || !data.length) return '';
      // Aggregate to a hive-level rollup the worker would actually expect.
      // MTBF / MTTR average across machines; downtime / failures sum.
      let value, unit, agg;
      if (intent.kind === 'mtbf') {
        const nums = data.map(r => Number(r[col])).filter(n => !isNaN(n) && n > 0);
        if (!nums.length) return '';
        value = (nums.reduce((a, b) => a + b, 0) / nums.length).toFixed(1);
        unit = 'days'; agg = 'average across ' + nums.length + ' machines';
      } else if (intent.kind === 'mttr') {
        const nums = data.map(r => Number(r[col])).filter(n => !isNaN(n) && n > 0);
        if (!nums.length) return '';
        value = (nums.reduce((a, b) => a + b, 0) / nums.length).toFixed(1);
        unit = 'hours'; agg = 'average across ' + nums.length + ' machines';
      } else if (intent.kind === 'downtime') {
        const nums = data.map(r => Number(r[col])).filter(n => !isNaN(n));
        value = nums.reduce((a, b) => a + b, 0).toFixed(1);
        unit = 'hours'; agg = 'sum across ' + nums.length + ' machines';
      } else if (intent.kind === 'failures_count') {
        const nums = data.map(r => Number(r[col])).filter(n => !isNaN(n));
        value = nums.reduce((a, b) => a + b, 0);
        unit = 'breakdowns'; agg = 'sum across ' + nums.length + ' machines';
      } else {
        return '';
      }
      const label = _kpiLabel(intent.kind);
      const generated = data[0] && data[0].generated_at ? new Date(data[0].generated_at).toISOString().slice(0, 16).replace('T', ' ') : 'recent';
      return 'CANONICAL DATA from v_kpi_truth — your hive\'s actual ' + label + ':\n' +
             '  - ' + label + ' over the last ' + win + ' days: ' + value + ' ' + unit + ' (' + agg + ')\n' +
             '  - Source snapshot: ' + generated + ' UTC, refreshed hourly';
    } catch (err) {
      console.warn('[WHVoice] canonical fetch failed (non-fatal):', err && err.message);
      return '';
    }
  }

  function _kpiColumn(kind, win) {
    const w = (win === 90 || win === 365) ? win : 30;
    if (kind === 'mtbf')           return 'mtbf_' + w + 'd';
    if (kind === 'mttr')           return 'mttr_' + w + 'd';
    if (kind === 'downtime')       return 'total_downtime_' + w + 'd';
    if (kind === 'failures_count') return 'failures_' + w + 'd';
    return null;
  }

  function _kpiLabel(kind) {
    if (kind === 'mtbf')           return 'MTBF';
    if (kind === 'mttr')           return 'MTTR';
    if (kind === 'downtime')       return 'total downtime';
    if (kind === 'failures_count') return 'breakdown count';
    return kind;
  }

  // Pull the worker's recent journal turns so the model has actual
  // conversation continuity ("the downtime you started", "yung pump
  // kanina") instead of asking generic clarifiers. Tries the DB first
  // (signed-in workers), then falls back to the session-only array
  // (anon workers in the Tester). Cheap on both paths, best-effort.
  async function _fetchRecentMemory(db, workerName) {
    let agentMemoryTurns = [];
    let voiceJournalTurns = [];

    // Phase 2: Try agent_memory table first (current session + recent history)
    if (db && workerName) {
      const sessionId = _getSessionId();
      try {
        // Fetch current session memory (most recent, highest fidelity)
        const { data: sessionData, error: sessionErr } = await db.from('agent_memory')
          .select('turn_num, user_input, assistant_response')
          .eq('session_id', sessionId)
          .order('turn_num', { ascending: true })
          .limit(10);

        if (!sessionErr && sessionData && sessionData.length) {
          agentMemoryTurns = sessionData.map(row => ({
            user: String(row.user_input || ''),
            assistant: String(row.assistant_response || ''),
            turn_num: row.turn_num,
          }));
        }
      } catch (err) {
        console.warn('[WHVoice] agent_memory fetch failed (Phase 2):', err && err.message);
      }
    }

    // Fallback: voice_journal_entries (older history, broader context)
    if (db && workerName && agentMemoryTurns.length < 5) {
      try {
        const since = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
        const { data, error } = await db.from('voice_journal_entries')
          .select('transcript, reply, created_at')
          .eq('worker_name', workerName)
          .gte('created_at', since)
          .order('created_at', { ascending: false })
          .limit(5);
        if (!error && data && data.length) {
          voiceJournalTurns = data.slice().reverse().map(row => ({
            user:      String(row.transcript || ''),
            assistant: String(row.reply || ''),
          }));
        }
      } catch (_) { /* RLS denial / network — fall through */ }
    }

    // Merge: session turns (fresh), then journal turns (older). Dedupe by user message.
    const sessionTurns = _sessionTurns.map(t => ({ user: t.user, assistant: t.assistant }));
    const allTurns = agentMemoryTurns.concat(voiceJournalTurns).concat(sessionTurns);

    const seen = new Set();
    const merged = [];
    for (const turn of allTurns) {
      const key = turn.user.slice(0, 80);
      if (seen.has(key)) continue;
      seen.add(key);
      merged.push(turn);
    }

    if (!merged.length) return '';

    // Format memory block with turn numbers for clarity
    return 'RECENT SESSION MEMORY:\n' + merged.map((t, idx) => {
      const u = t.user.slice(0, 240).trim();
      const a = t.assistant.slice(0, 240).trim();
      return `Turn ${idx + 1}:\nWorker asked: ${u}\nYou replied: ${a}`;
    }).filter(Boolean).join('\n\n---\n\n');
  }

  // Phase 2: Store turn in agent_memory table (session-scoped, durable memory)
  async function _storeTurn(db, hiveId, workerName, transcript, response, intentKind, confidence, responseTimeMs) {
    if (!db || !hiveId || !workerName) return; // silent no-op for anon
    const sessionId = _getSessionId();
    _turnNum++;

    try {
      const result = await db.rpc('store_memory_turn', {
        p_hive_id: hiveId,
        p_session_id: sessionId,
        p_turn_num: _turnNum,
        p_user_input: String(transcript || '').slice(0, 2000),
        p_assistant_response: String(response || '').slice(0, 2000),
        p_intent: intentKind || 'unknown',
        p_confidence: Number(confidence || 0),
        p_response_time_ms: Number(responseTimeMs || 0),
      });

      if (result.error) {
        console.warn('[WHVoice] store_memory_turn RPC failed:', result.error);
      } else {
        console.log('[WHVoice] Turn ' + _turnNum + ' stored to agent_memory');
      }
    } catch (err) {
      console.warn('[WHVoice] Memory store exception:', err && err.message);
    }
  }

  // Phase 4: Fetch dialog state for multi-turn intent refinement
  async function _fetchDialogState(db, sessionId) {
    if (!db || !sessionId) return null;
    try {
      const { data, error } = await db.rpc('fetch_dialog_state', { p_session_id: sessionId });
      if (error || !data || data.length === 0) return null;
      return data[0];
    } catch (err) {
      console.warn('[WHVoice] Dialog state fetch failed:', err && err.message);
      return null;
    }
  }

  // Phase 5: Fetch active proactive alerts (KPI spikes, risk escalation, overdue PM)
  async function _fetchProactiveAlerts(db, hiveId) {
    if (!db || !hiveId) return [];
    try {
      const { data, error } = await db.rpc('fetch_active_alerts', { p_hive_id: hiveId });
      if (error || !data) return [];
      return data.slice(0, 5); // Top 5 critical alerts only
    } catch (err) {
      console.warn('[WHVoice] Proactive alerts fetch failed:', err && err.message);
      return [];
    }
  }

  // Phase 4: Update dialog state (intent + slots) after each turn
  async function _updateDialogState(db, hiveId, sessionId, intentKind, confidence, contextSlots, clarificationPending, clarificationPrompt) {
    if (!db || !hiveId || !sessionId) return;
    try {
      const result = await db.rpc('update_dialog_state', {
        p_hive_id: hiveId,
        p_session_id: sessionId,
        p_turn_num: _turnNum,
        p_intent: intentKind || 'unknown',
        p_confidence: Number(confidence || 0),
        p_context_slots: contextSlots || {},
        p_clarification_pending: clarificationPending || false,
        p_clarification_prompt: clarificationPrompt || null,
      });
      if (result.error) {
        console.warn('[WHVoice] Dialog state update failed:', result.error);
      }
    } catch (err) {
      console.warn('[WHVoice] Dialog state update exception:', err && err.message);
    }
  }

  // Phase 4: Clarification logic — if confidence too low, ask instead of guessing
  function _shouldClarify(confidence, priorIntent, newIntent) {
    // If confidence < 0.65 and intent flipped, ask for clarification
    if (confidence < 0.65 && priorIntent && newIntent && priorIntent !== newIntent) {
      return true;
    }
    return false;
  }

  // Phase 4: Generate clarification question
  function _generateClarification(transcript, newIntent, priorIntent) {
    const intentNames = {
      'mtbf': 'equipment reliability',
      'mttr': 'repair time',
      'oee': 'overall efficiency',
      'risk_assessment': 'risk analysis',
      'pm_scheduling': 'preventive maintenance',
      'inventory_check': 'parts availability',
      'troubleshooting': 'troubleshooting',
    };

    const newName = intentNames[newIntent] || newIntent;
    const priorName = priorIntent ? (intentNames[priorIntent] || priorIntent) : '';

    if (priorName) {
      return `I think you\'re asking about ${newName}, but we were just discussing ${priorName}. Did you mean to keep talking about ${priorName}, or switch to ${newName}?`;
    }
    return `I think you\'re asking about ${newName}. Is that right?`;
  }

  // Phase 1: Semantic Router — classify whether question needs platform data, semantic depth, or simple reply
  async function _classifySemanticRoute(transcript, routerIntents) {
    // Short-circuit: if voice-action-router already classified as a data intent,
    // skip the LLM call and route straight to platform (saves ~500ms + cost).
    const firstIntent = routerIntents && routerIntents[0];
    if (firstIntent && ['mtbf', 'mttr', 'downtime', 'risk_top', 'failures_count', 'oee', 'availability'].includes(firstIntent.kind)) {
      return { route: 'platform', confidence: 0.95, reasoning: 'Router pre-classified as data intent: ' + firstIntent.kind };
    }

    // Pre-check: heuristic catches KPI keywords before the LLM call (faster + cheaper)
    const tLower = String(transcript || '').toLowerCase();
    if (/\b(mtbf|mttr|oee|availability|reliability|uptime|downtime|how many|overdue|risk|low stock|out of stock)\b/.test(tLower)) {
      return { route: 'platform', confidence: 0.9, reasoning: 'KPI keywords detected: ' + tLower };
    }

    try {
      const fetcher = (typeof window.fetchWithTimeout === 'function')
        ? window.fetchWithTimeout
        : (u, o) => fetch(u, o);

      const systemMsg = 'You are a lightweight intent router for an industrial maintenance voice assistant. Output ONLY a JSON object with fields: "route" ("platform"|"semantic"|"simple"), "confidence" (0.0-1.0), "reasoning" (string).\n\nROUTE RULES:\n- "platform" = real-time KPI/metric queries. ALWAYS use this for: MTBF, MTTR, OEE, availability, reliability, uptime, downtime, equipment counts, PM status, inventory levels, risk scores. Examples: "MTBF today", "what is our OEE", "how many overdue PMs", "compressor MTTR this week".\n- "semantic" = pattern/analysis/why questions. Use for: "why does X fail", "what changed", "is this trend normal".\n- "simple" = greetings, thanks, no-data-needed. Use for: "thanks", "hi", "what time is it".\n\nWhen in doubt between platform vs semantic, prefer platform — we have real-time data to answer with.';
      const resp = await fetcher(WH_ASSISTANT_WORKER_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'meta-llama/llama-4-scout-17b-16e-instruct',
          max_tokens: 80,
          messages: [
            { role: 'system', content: systemMsg },
            { role: 'user', content: transcript },
          ],
        }),
      }, 5000);

      if (resp && resp.ok) {
        const data = await resp.json();
        const answer = (data && data.choices && data.choices[0] && data.choices[0].message && data.choices[0].message.content) || '';
        try {
          const parsed = JSON.parse(answer);
          if (parsed.route && (parsed.route === 'platform' || parsed.route === 'semantic' || parsed.route === 'simple')) {
            return parsed;
          }
        } catch (_) {}
      }
    } catch (_) {}
    // Fallback heuristic if LLM call fails
    return _heuristicRoute(transcript);
  }

  // Heuristic fallback for semantic router (keywords-based)
  function _heuristicRoute(transcript) {
    const t = String(transcript || '').toLowerCase();
    if (/(mtbf|mttr|oee|availability|reliability|uptime|downtime|how many|count|overdue|down|running|risk|alert|stock|status|equipment|today|this week|this month)/.test(t)) {
      return { route: 'platform', confidence: 0.8, reasoning: 'Platform/KPI keywords detected' };
    } else if (/(why|how can|prevent|improve|trend|pattern|analysis|cause)/.test(t)) {
      return { route: 'semantic', confidence: 0.7, reasoning: 'Analysis keywords detected' };
    } else if (/(thanks|thank|hi|hello|bye)/.test(t)) {
      return { route: 'simple', confidence: 0.8, reasoning: 'Greeting or closing' };
    } else {
      return { route: 'platform', confidence: 0.5, reasoning: 'Ambiguous; defaulting to platform (data first)' };
    }
  }

  // Phase 1: Platform Scraper Agent — fetch real-time KPI data for status queries
  async function _invokePlatformScraper(db, hiveId, workerName) {
    if (!hiveId) return '';
    try {
      // Call platform-scraper edge function for KPI aggregation
      const fetcher = (typeof window.fetchWithTimeout === 'function')
        ? window.fetchWithTimeout
        : (u, o) => fetch(u, o);

      const resp = await fetcher(SUPABASE_URL + '/functions/v1/platform-scraper', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer ' + SUPABASE_KEY,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          hive_id: hiveId,
          worker_name: workerName,
        }),
      }, 5000);

      if (resp && resp.ok) {
        const data = await resp.json();
        return data.summary || '';
      }
    } catch (err) {
      console.warn('[WHVoice] platform scraper edge function failed (non-fatal):', err && err.message);
    }

    // Fallback: direct DB queries if edge function unavailable
    try {
      if (!db) return '';
      const [eqStatus, riskAssets, pmStatus, invAlerts, adoptionMetrics] = await Promise.all([
        _fetchEquipmentStatus(db, hiveId),
        _fetchRiskAssets(db, hiveId, 2),
        _fetchPMStatus(db, hiveId),
        _fetchInventoryAlerts(db, hiveId),
        _fetchAdoptionMetrics(db, hiveId),
      ]);

      const parts = [];
      if (eqStatus) parts.push(eqStatus);
      if (riskAssets) parts.push('At-risk assets: ' + riskAssets);
      if (pmStatus) parts.push(pmStatus);
      if (invAlerts) parts.push('Inventory: ' + invAlerts);
      if (adoptionMetrics) parts.push(adoptionMetrics);

      return parts.length ? parts.join(' ') : '';
    } catch (err2) {
      console.warn('[WHVoice] platform scraper fallback failed:', err2 && err2.message);
      return '';
    }
  }

  // Full platform snapshot — scans every canonical truth view + worker-scoped tables in parallel.
  // Returns one comprehensive block that gives the LLM complete platform awareness.
  // The LLM picks what's relevant to the user's question from this snapshot.
  async function _fetchFullPlatformSnapshot(db, hiveId, workerName) {
    if (!db) {
      console.warn('[WHVoice] Snapshot: missing db');
      return '';
    }
    if (!hiveId) {
      console.warn('[WHVoice] Snapshot: hiveId not set in context, checking localStorage fallback');
      // Fallback: if hive_id not in context, try all common localStorage keys
      hiveId = localStorage.getItem('wh_active_hive_id') ||
               localStorage.getItem('wh_hive_id') ||
               localStorage.getItem('hive_id') || '';
      if (!hiveId) {
        console.warn('[WHVoice] Snapshot: no hiveId found in localStorage either');
        return '';
      }
      console.log('[WHVoice] Snapshot: recovered hiveId from localStorage:', hiveId);
    }
    const today = new Date().toISOString().slice(0, 10);

    const fetches = await Promise.allSettled([
      db.from('v_kpi_truth').select('machine,mtbf_30d,mttr_30d,total_downtime_30d,failures_30d').eq('hive_id', hiveId).limit(50),
      db.from('v_risk_truth').select('asset_name,risk_score,risk_level,mtbf_days,days_until_failure').eq('hive_id', hiveId).order('risk_score', { ascending: false }).limit(5),
      db.from('v_pm_compliance_truth').select('asset_name,category,criticality,last_anchor_date,days_since_last_completion,completions_30d').eq('hive_id', hiveId).limit(20),
      // Open logbook items (the "open work" backlog — what Day Planner shows in its sidebar)
      db.from('v_logbook_truth').select('machine,category,problem,action,status,date,created_at,worker_name').eq('hive_id', hiveId).eq('status', 'Open').order('created_at', { ascending: false }).limit(30),
      db.from('v_inventory_items_truth').select('part_name,part_number,qty_on_hand,min_qty,reorder_point').eq('hive_id', hiveId).limit(50),
      db.from('v_asset_truth').select('name,tag,iso_class,criticality,last_failure_at,lifetime_logbook_entries').eq('hive_id', hiveId).limit(100),
      db.from('v_adoption_truth').select('risk_tier,risk_score,active_ratio_risk,momentum_risk,snapshot_date').eq('hive_id', hiveId).order('snapshot_date', { ascending: false }).limit(1),
      db.from('v_knowledge_truth').select('source,content,created_at').eq('hive_id', hiveId).order('created_at', { ascending: false }).limit(5),
      // Schedule items for the worker — broaden to recent + upcoming so we never say "nothing" when items exist
      workerName ? db.from('schedule_items').select('title,start_time,end_time,category,item_status,date,worker_name').eq('worker_name', workerName).order('date', { ascending: false }).limit(30) : Promise.resolve({ data: [] }),
      workerName ? db.from('v_worker_skill_truth').select('discipline,primary_skill,role').eq('worker_name', workerName).limit(10) : Promise.resolve({ data: [] }),
      db.from('v_anomaly_truth').select('machine,composite_score,logbook_cluster_score,snapshot_date').eq('hive_id', hiveId).order('snapshot_date', { ascending: false }).limit(5),
      db.from('v_project_truth').select('name,project_code,project_type,status,priority').eq('hive_id', hiveId).limit(10),
      // Recent CLOSED logbook (so Rosa can answer "what did we fix recently?")
      db.from('v_logbook_truth').select('machine,category,problem,action,date,created_at,worker_name').eq('hive_id', hiveId).eq('status', 'Closed').order('created_at', { ascending: false }).limit(10),
    ]);

    const data = fetches.map((r, i) => {
      const result = r.status === 'fulfilled' && r.value && r.value.data ? r.value.data : [];
      if (r.status === 'rejected') {
        console.warn('[WHVoice] Query', i, 'rejected:', r.reason);
      }
      return result;
    });
    const [kpi, risk, pm, openLogbook, inventory, assets, adoption, knowledge, schedule, skills, anomalies, projects, recentClosed] = data;
    const logbook = openLogbook; // alias for backward compat with formatting below

    console.log('[WHVoice] Snapshot context:', { hiveId, workerName });
    console.log('[WHVoice] Snapshot data counts:', {
      kpi: kpi.length, risk: risk.length, pm: pm.length, openLogbook: openLogbook.length,
      inventory: inventory.length, assets: assets.length, adoption: adoption.length,
      knowledge: knowledge.length, schedule: schedule.length, skills: skills.length,
      anomalies: anomalies.length, projects: projects.length, recentClosed: recentClosed.length
    });

    const parts = ['═══ FULL PLATFORM SNAPSHOT (live, scanned just now) ═══'];

    // KPI summary (MTBF/MTTR averages, downtime totals)
    if (kpi.length) {
      const mtbfs = kpi.map(r => Number(r.mtbf_30d)).filter(n => n > 0);
      const mttrs = kpi.map(r => Number(r.mttr_30d)).filter(n => n > 0);
      const dts = kpi.map(r => Number(r.total_downtime_30d)).filter(n => !isNaN(n));
      const fails = kpi.map(r => Number(r.failures_30d)).filter(n => !isNaN(n));
      const avg = (arr) => arr.length ? (arr.reduce((a,b)=>a+b,0)/arr.length).toFixed(1) : 'n/a';
      const sum = (arr) => arr.length ? arr.reduce((a,b)=>a+b,0).toFixed(1) : 'n/a';
      parts.push(`KPIs (last 30d, ${kpi.length} machines):\n  MTBF avg=${avg(mtbfs)} days | MTTR avg=${avg(mttrs)} hours | Total downtime=${sum(dts)} hours | Failures=${sum(fails)}`);
    }

    // Equipment breakdown by criticality
    if (assets.length) {
      const byCrit = {};
      assets.forEach(a => { byCrit[a.criticality || 'unknown'] = (byCrit[a.criticality || 'unknown'] || 0) + 1; });
      const recentFails = assets.filter(a => a.last_failure_at).length;
      parts.push(`Equipment (${assets.length} assets): ${Object.entries(byCrit).map(([s,c])=>`${c} ${s}`).join(', ')}. ${recentFails} have failure history.`);
    }

    // Top risk assets
    if (risk.length) {
      parts.push(`Top risk assets:\n  ` + risk.map(r => `${r.asset_name} (${r.risk_level}, score ${Number(r.risk_score).toFixed(2)}, MTBF ${r.mtbf_days || 'n/a'}d, days until failure ${r.days_until_failure || 'n/a'})`).join('\n  '));
    }

    // PM compliance — recently completed vs stale
    if (pm.length) {
      const stale = pm.filter(p => p.days_since_last_completion && p.days_since_last_completion > 30).length;
      const recent = pm.filter(p => p.completions_30d && p.completions_30d > 0).length;
      parts.push(`PM compliance: ${recent} completed in last 30d, ${stale} stale (no PM in 30+ days) of ${pm.length} tracked assets`);
      if (stale > 0) {
        parts.push(`  Stale PMs:\n    ` + pm.filter(p => p.days_since_last_completion && p.days_since_last_completion > 30).slice(0, 5).map(p => `${p.asset_name} (${p.criticality}): ${p.days_since_last_completion} days since last PM`).join('\n    '));
      }
    }

    // OPEN logbook items — these are what Day Planner shows as "open work"
    if (openLogbook.length) {
      parts.push(`OPEN WORK ITEMS from logbook (${openLogbook.length} unresolved, what Day Planner shows in sidebar):\n  ` + openLogbook.slice(0, 15).map(l => `${(l.created_at || l.date || '').slice(0,10)} ${l.machine || ''} [${l.category || ''}]: ${(l.problem || l.action || '').slice(0, 80)} (by ${l.worker_name || '?'})`).join('\n  '));
    }

    // Recently CLOSED logbook
    if (recentClosed && recentClosed.length) {
      parts.push(`Recently CLOSED logbook (last ${recentClosed.length}):\n  ` + recentClosed.slice(0, 5).map(l => `${(l.created_at || l.date || '').slice(0,10)} ${l.machine || ''} [${l.category || ''}]: ${(l.problem || l.action || '').slice(0, 80)}`).join('\n  '));
    }

    // Inventory — low stock
    if (inventory.length) {
      const lowStock = inventory.filter(i => i.reorder_point && Number(i.qty_on_hand) < Number(i.reorder_point));
      const outOfStock = inventory.filter(i => Number(i.qty_on_hand) === 0);
      parts.push(`Inventory (${inventory.length} items): ${outOfStock.length} out of stock, ${lowStock.length} low stock${lowStock.length ? '\n  Low: ' + lowStock.slice(0,5).map(i => `${i.part_name} (${i.qty_on_hand}/${i.reorder_point})`).join(', ') : ''}`);
    }

    // Anomalies
    if (anomalies.length) {
      parts.push(`Active anomalies (${anomalies.length}):\n  ` + anomalies.map(a => `${a.machine}: composite score ${a.composite_score}, logbook cluster ${a.logbook_cluster_score}`).join('\n  '));
    }

    // Projects
    if (projects.length) {
      parts.push(`Active projects:\n  ` + projects.map(p => `${p.name} (${p.project_type || 'n/a'}) — ${p.status} [${p.priority || 'normal'}]`).join('\n  '));
    }

    // Day Planner breakdown — match the UI's TODAY / THIS WEEK / OVERDUE counters
    const weekStart = new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10);
    const weekEnd = new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10);
    const todayItems = schedule.filter(s => s.date === today);
    const thisWeekItems = schedule.filter(s => s.date >= weekStart && s.date <= weekEnd);
    const overdueItems = schedule.filter(s => s.date && s.date < today && s.item_status !== 'closed' && s.item_status !== 'done');
    const totalOpenWork = openLogbook.length;

    if (schedule.length || totalOpenWork) {
      const dpLines = [`Your Day Planner status:`];
      dpLines.push(`  TODAY (${today}): ${todayItems.length} scheduled items`);
      dpLines.push(`  THIS WEEK (${weekStart} to ${weekEnd}): ${thisWeekItems.length} scheduled items`);
      dpLines.push(`  OVERDUE scheduled: ${overdueItems.length} past their date and not yet closed`);
      dpLines.push(`  OPEN WORK from logbook (sidebar): ${totalOpenWork} unresolved items`);
      if (todayItems.length) {
        dpLines.push(`  Today's items:\n    ` + todayItems.map(s => `${s.start_time || ''}-${s.end_time || ''} ${s.title || ''} [${s.category || 'task'}] (${s.item_status || 'pending'})`).join('\n    '));
      }
      if (overdueItems.length) {
        dpLines.push(`  Overdue items:\n    ` + overdueItems.slice(0, 5).map(s => `${s.date}: ${s.title || ''} [${s.category || 'task'}]`).join('\n    '));
      }
      parts.push(dpLines.join('\n'));
    } else if (workerName) {
      parts.push(`Your Day Planner: no schedule items found for "${workerName}". (Open Work items above may still be relevant — they're what shows in the planner sidebar.)`);
    }

    // Worker skills / role
    if (skills.length) {
      parts.push(`Your skills: ` + skills.map(s => `${s.discipline}${s.primary_skill ? ' (' + s.primary_skill + ')' : ''}${s.role ? ' role=' + s.role : ''}`).join(', '));
    }

    // Adoption / activity risk
    if (adoption.length && adoption[0]) {
      const a = adoption[0];
      parts.push(`Hive adoption health: tier=${a.risk_tier || 'n/a'}, risk_score=${a.risk_score}, active_ratio_risk=${a.active_ratio_risk}, momentum_risk=${a.momentum_risk} (snapshot ${a.snapshot_date})`);
    }

    // Knowledge base
    if (knowledge.length) {
      parts.push(`Recent knowledge entries (${knowledge.length}):\n  ` + knowledge.map(k => `[${k.source}] "${(k.content || '').slice(0, 100)}..."`).join('\n  '));
    }

    return parts.length > 1 ? parts.join('\n\n') : '';
  }

  // Helper: fetch equipment status from v_asset_truth (running / idle / maintenance / down)
  async function _fetchEquipmentStatus(db, hiveId) {
    try {
      const { data, error } = await db.from('v_asset_truth')
        .select('state, COUNT(*)')
        .eq('hive_id', hiveId)
        .not('state', 'is', null)
        .group_by('state')
        .execute();
      if (error || !data) return '';
      const parts = data.map(r => r.count + ' ' + (r.state || 'unknown')).filter(Boolean);
      return parts.length ? 'Equipment: ' + parts.join(', ') + '.' : '';
    } catch (_) { return ''; }
  }

  // Helper: fetch top N assets by risk score
  async function _fetchRiskAssets(db, hiveId, limit) {
    try {
      const { data, error } = await db.from('v_risk_truth')
        .select('asset_name, risk_level')
        .eq('hive_id', hiveId)
        .order('risk_score', { ascending: false })
        .limit(limit);
      if (error || !data || !data.length) return '';
      return data.map(r => r.asset_name + ' (' + r.risk_level + ')').join(', ');
    } catch (_) { return ''; }
  }

  // Helper: fetch PM status (due this week / overdue)
  async function _fetchPMStatus(db, hiveId) {
    try {
      const today = new Date().toISOString().slice(0, 10);
      const weekEnd = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
      const dueSoon = await db.from('v_pm_truth').select('COUNT').eq('hive_id', hiveId).eq('status', 'due').gte('next_due_date', today).lt('next_due_date', weekEnd).execute();
      const overdue = await db.from('v_pm_truth').select('COUNT').eq('hive_id', hiveId).eq('status', 'overdue').execute();
      const due = (dueSoon.data && dueSoon.data[0] && dueSoon.data[0].count) || 0;
      const overdueCount = (overdue.data && overdue.data[0] && overdue.data[0].count) || 0;
      if (due + overdueCount === 0) return '';
      return 'PMs: ' + due + ' due this week' + (overdueCount ? ', ' + overdueCount + ' overdue' : '') + '.';
    } catch (_) { return ''; }
  }

  // Helper: fetch inventory alerts (low stock / out of stock)
  async function _fetchInventoryAlerts(db, hiveId) {
    try {
      const low = await db.from('v_inventory_truth').select('COUNT').eq('hive_id', hiveId).eq('stock_level', 'low').execute();
      const out = await db.from('v_inventory_truth').select('COUNT').eq('hive_id', hiveId).eq('stock_level', 'out').execute();
      const lowCount = (low.data && low.data[0] && low.data[0].count) || 0;
      const outCount = (out.data && out.data[0] && out.data[0].count) || 0;
      if (lowCount + outCount === 0) return '';
      return (lowCount ? lowCount + ' low' : '') + (outCount ? (lowCount ? ' + ' : '') + outCount + ' out of stock' : '');
    } catch (_) { return ''; }
  }

  // Helper: fetch adoption metrics (active workers, adoption score)
  async function _fetchAdoptionMetrics(db, hiveId) {
    try {
      const { data, error } = await db.from('v_adoption_truth').select('active_workers_week, adoption_score').eq('hive_id', hiveId).single().execute();
      if (error || !data) return '';
      const workers = data.active_workers_week || 0;
      if (workers === 0) return '';
      return 'Active workers: ' + workers + '.';
    } catch (_) { return ''; }
  }

  // Phase 1: RAG Agent — fetch semantic context from voice journal (Phase 1.5: optional semantic search)
  async function _invokeRAGAgent(db, workerName, firstIntent, transcript) {
    if (!db || !workerName) return '';
    try {
      const ctx = _ctx();
      const auth_uid = ctx && ctx.user && ctx.user.id;
      if (!auth_uid) return ''; // Anon users have no voice journal

      // Phase 1.5: Try semantic search via edge function (falls back to recency)
      const fetcher = (typeof window.fetchWithTimeout === 'function')
        ? window.fetchWithTimeout
        : (u, o) => fetch(u, o);

      const ragResp = await fetcher(SUPABASE_URL + '/functions/v1/voice-semantic-rag', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer ' + SUPABASE_KEY,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          auth_uid,
          query_text: transcript,
          limit: 5,
        }),
      }, 5000);

      if (ragResp && ragResp.ok) {
        const ragData = await ragResp.json();
        const results = ragData.results || [];
        const method = ragData.method || 'fallback';

        if (!results.length) return '';

        // Format turns for semantic context: older turns first
        const turns = results.map((row, idx) => {
          const ts = new Date(row.created_at).toLocaleTimeString();
          const sim = row.similarity ? ' (match: ' + Math.round(row.similarity * 100) + '%)' : '';
          return 'At ' + ts + sim + ':\nYou: ' + String(row.transcript || '').slice(0, 100) + '\nAssistant: ' + String(row.reply || '').slice(0, 100);
        });

        const methodLabel = method === 'semantic' ? ' (semantic match)' : ' (recent entries)';
        return turns.length ? 'Your voice history' + methodLabel + ':\n' + turns.join('\n---\n') : '';
      }
    } catch (err) {
      console.warn('[WHVoice] RAG agent failed (non-fatal):', err && err.message);
    }

    // Fallback: fetch recent turns directly from DB (Phase 1 style)
    try {
      const since = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();
      const { data, error } = await db.from('voice_journal_entries')
        .select('transcript, reply, created_at')
        .eq('worker_name', workerName)
        .gt('created_at', since)
        .order('created_at', { ascending: false })
        .limit(5)
        .execute();

      if (error || !data || !data.length) return '';

      const turns = data.reverse().map(row => {
        const ts = new Date(row.created_at).toLocaleTimeString();
        return 'At ' + ts + ':\nYou: ' + String(row.transcript || '').slice(0, 100) + '\nAssistant: ' + String(row.reply || '').slice(0, 100);
      });

      return turns.length ? 'Recent context from your voice history:\n' + turns.join('\n---\n') : '';
    } catch (_) {
      return '';
    }
  }

  // Phase 3: Error Recovery — generate intelligent fallback reply when AI is offline
  function _generateFallbackReply(transcript, routerIntents, persona) {
    const intent = routerIntents && routerIntents[0];
    const kind = intent && intent.kind;
    const personaName = persona === 'rosa' ? 'Rosa' : 'James';

    // Match against known intent patterns for better fallback text
    if (kind === 'mtbf' || kind === 'mttr' || kind === 'downtime' || kind === 'risk_top' || kind === 'failures_count') {
      return 'I\'m offline right now, but check Analytics for the exact ' + (kind === 'mtbf' ? 'MTBF' : kind === 'mttr' ? 'MTTR' : 'numbers') + ' you need. Your voice transcript is saved.';
    } else if (kind === 'logbook.create' || kind === 'inventory.use' || kind === 'pm.complete') {
      return 'I can\'t connect right now, but your question is saved. Open ' + (kind === 'logbook.create' ? 'Logbook' : kind === 'inventory.use' ? 'Inventory' : 'PM Scheduler') + ' to continue.';
    } else if (kind === 'asset.lookup') {
      return 'I\'m offline right now. Open Asset Hub to find the details you need. Your transcript is saved.';
    } else {
      return 'Sorry, I\'m offline. Your question is saved and I\'ll be back soon.';
    }
  }

  function _buildVoiceSystemPrompt(persona, workerName, hiveName, pageLabel, routingHint, memoryBlock, canonicalData, routerContext, platformData, ragContext, dialogState, proactiveAlerts) {
    const personaBlock = (typeof window.getCompanionBlock === 'function')
      ? window.getCompanionBlock() : '';
    // Internal-only grounding. These facts help the model pick the right
    // tool to point to ("you're on the logbook page, just scroll down to
    // the entry form") — but NEVER mention the page name verbatim in
    // your reply. Workers don't think in page names; they think in tasks.
    const ident = [];
    if (workerName) ident.push("Worker speaking: " + workerName + ".");
    if (hiveName)   ident.push("Their hive: " + hiveName + ".");
    if (pageLabel)  ident.push("Internal context (DO NOT mention by name in your reply): the worker is on the " + pageLabel + " page.");
    const identBlock = ident.length ? ('\n' + ident.join(' ') + '\n') : '';
    // Router pre-classification. The voice-action-router already ran intent
    // classification (Groq LLM, high confidence). This context tells the model
    // what was already classified so it doesn't re-parse from scratch.
    const routerBlock = routerContext
      ? '\nROUTER PRE-CLASSIFIED: ' + routerContext + ' — use this context in your reply. If the worker is asking about a data point, that classification tells you they want numbers, not emotional support.\n'
      : '';
    // When the worker spoke a command we can't dispatch from this page,
    // inject the canonical routing tip so the model gives accurate
    // guidance instead of inventing UI ("click the asset card's Log
    // Downtime button" — no such thing).
    const routingBlock = routingHint
      ? '\nIMPORTANT — the worker tried to speak a command this page can\'t execute: ' + routingHint + ' Keep the reply to ONE short sentence. Do NOT describe specific buttons / cards / menus you haven\'t been told about.\n'
      : '';
    // Phase 5: Proactive alerts (KPI spikes, risk, overdue PM)
    const alertsSection = (proactiveAlerts && proactiveAlerts.length)
      ? '\nACTIVE ALERTS — Surface these FIRST before answering the worker\'s question:\n' +
        proactiveAlerts.map((a, idx) => {
          const severity = (a.severity || 'info').toUpperCase();
          const desc = (a.description || '').slice(0, 200);
          const action = (a.action_suggested || 'Investigate.').slice(0, 150);
          return `[${severity}] ${a.alert_type}: ${desc}\nAction: ${action}`;
        }).join('\n') +
        '\n\nOPENING RULE FOR ALERTS: If there are critical/high alerts above, your reply should start with "Before you ask, I need to flag something:" followed by the alert summary. Then answer the worker\'s question if appropriate. NEVER skip mentioning critical alerts.\n'
      : '';

    // Phase 4: Dialog state (intent + slots + clarification status)
    const dialogSection = dialogState
      ? '\nDIALOG STATE:\n' +
        'Current intent: ' + (dialogState.current_intent || 'unknown') + '\n' +
        'Confidence: ' + Math.round((dialogState.intent_confidence || 0) * 100) + '%\n' +
        (dialogState.context_slots && Object.keys(dialogState.context_slots).length
          ? 'Context: ' + JSON.stringify(dialogState.context_slots) + '\n'
          : '') +
        (dialogState.clarification_pending ? 'Awaiting clarification from worker\n' : '') +
        '\n'
      : '';

    // Recent conversation context. Without this, "Help me find it" /
    // "yung pump kanina" / "tapos?" have nothing to anchor to and the
    // model has to ask generic clarifiers. With it, the model can say
    // "the downtime you were logging earlier?" naturally.
    const memorySection = memoryBlock
      ? '\nPRIOR TURNS WITH THIS WORKER (most recent at the bottom — use these for continuity, but never quote them verbatim):\n' + memoryBlock + '\n'
      : '';
    // Canonical data — when the worker asks for a number that lives in a
    // v_*_truth view, we fetch it BEFORE the LLM call and inject it here.
    // Without this block, Hard Rule #2 (no inventing numbers) + Rule #9 (no
    // inventing UI) leaves the model only one legal answer ("check
    // Analytics"). With it, Rosa/James paraphrase the real figure.
    const canonicalSection = canonicalData
      ? '\n═══════════════════════════════════════════════════════════════════\n' +
        'CANONICAL DATA — anchor verbatim on the figures below.\n' +
        '═══════════════════════════════════════════════════════════════════\n' +
        canonicalData + '\n' +
        'You MUST anchor your reply on these figures. Paraphrase naturally (it is being heard, not read) but never change the digits, the unit, or the window. If the worker asked something the data above does NOT cover, say so plainly and point to Analytics for the full breakdown.\n' +
        '═══════════════════════════════════════════════════════════════════\n'
      : '';

    // Phase 1: Platform data (real-time KPI snapshots for status queries)
    const platformSection = platformData
      ? '\nPLATFORM DATA — Real-time status snapshot:\n' + platformData + '\n'
      : '';

    // Phase 1: RAG context (semantic depth for analysis questions)
    const ragSection = ragContext
      ? '\nSEMANTIC CONTEXT — Historical patterns & analysis:\n' + ragContext + '\n'
      : '';

    const hasData = platformData || canonicalData || ragContext;
    const directAnswerInstruction = hasData
      ? '- ANSWER FROM THE PLATFORM SNAPSHOT above. The ENTIRE platform has been scanned: KPIs (MTBF, MTTR, downtime, failures), equipment status, risk assets, PM compliance, inventory levels, recent logbook entries, anomalies, projects, your Day Planner today, your skill levels, hive activity, knowledge entries — all of it is in your context. SCAN the snapshot for the relevant section before answering. NEVER say "check [tool]" or "open Day Planner" or "your dashboard should have that" when the answer is sitting in the snapshot above. ONLY say "I don\'t have that data right now" if you scanned the snapshot and the specific thing is genuinely absent.\n'
      : '- If they asked a maintenance / work question, ANSWER IT directly with practical maintenance knowledge. If you don\'t have the data they\'re asking about, say so plainly.\n';

    return personaBlock + '\n\n' +
      'You are answering a worker over voice. They will HEAR your reply, so:\n' +
      '- Keep it 2-3 short sentences. Long answers are tiring spoken aloud.\n' +
      directAnswerInstruction +
      '- If they shared a feeling or vented ("stressed", "tired", "ayoko na"), react first ("naks, mahirap yan" / "hala ka"). For pure data questions ("how many", "what is", "where"), skip the warmth opener and just answer directly.\n' +
      identBlock +
      routerBlock +
      routingBlock +
      alertsSection +
      dialogSection +
      memorySection +
      canonicalSection +
      platformSection +
      ragSection +
      '\nIf the worker mixes Filipino / Cebuano / Tagalog in, that\'s fine — understand it, reply in English.\n\n' +
      '═══════════════════════════════════════════════════════════════════\n' +
      'HARD RULES — read these last; they override everything above.\n' +
      '═══════════════════════════════════════════════════════════════════\n' +
      '0. PRONOUN ANCHORING. If the worker uses a pronoun ("it", "that", "this", "yan", "iyon", "ito", "yun") and PRIOR TURNS WITH THIS WORKER exists above, the pronoun refers to the most recent topic in those turns. Do NOT infer a different referent (lost physical object, missing tool, broken machine) when memory has a clear antecedent. "How can I find it?" after a data question is "how do I find the data?", not "I lost something."\n' +
      '1. NEVER ask "what changed?" or "what\'s changed today?" or "why are you asking again?" — these are clinical/therapy follow-ups and the worker hates them.\n' +
      '2. NEVER say "I see you\'ve been asking about X a lot lately" — you do NOT have conversation history in this turn; pretending you do is hallucination.\n' +
      '3. NEVER echo the worker\'s question back as the answer. "Priority checking ka na naman" is NOT an answer to "what\'s the priority PM today?"\n' +
      '4. NEVER treat a direct work question ("what is X", "how do I Y", "where can I find Z") as emotional. Just answer it or say honestly you can\'t see the data and point to the right tool.\n' +
      '4a. NEVER say "check Analytics" or "open Day Planner" or "your dashboard should have that" or "you can find that in [tool]" UNLESS you have first scanned the FULL PLATFORM SNAPSHOT above for the answer. The snapshot contains: KPIs, equipment, risk, PM, inventory, logbook, anomalies, projects, schedule, skills, knowledge, adoption — all current values. The phrases "check X" / "open X" / "find that in X" are BANNED when X\'s data is in the snapshot. If the worker asks about Day Planner and your schedule appears in the snapshot, READ IT and tell them. Same for inventory, PMs, MTBF, projects — read first, punt only if truly absent.\n' +
      '4b. WARMTH OPENER RULE: Only open with "hala ka" / "naks" / "ay grabe" if the worker explicitly shared a feeling or emotional state ("tired", "stressed", "frustrated", "ayoko na", "mahirap", etc.). For pure data questions ("how many", "what is", "check who", "list"), start with the answer directly. Warmth words are fine MID-response for clarification or context, but not automatic openers on factual queries.\n' +
      '5. If you find yourself starting with "Naiintindihan kita" or "I understand" on a factual question, STOP and rewrite — that opener is for emotional venting only.\n' +
      '6. NEVER mention the page name (e.g. "index", "logbook", "hive", "asset-hub") in your reply. Workers don\'t think in page names. Say "this page" or "your dashboard" or just answer naturally without referencing where they are.\n' +
      '7. NEVER invent details the worker did not mention. If they say "what is the problem?" — you do NOT know what problem. Do NOT make up "the production line" or "the pump" or "your machine". Ask back: "which one, pre?" — or if it\'s totally vague, say "tell me a bit more, what\'s going on?"\n' +
      '8. If the worker\'s message is short or ambiguous ("what now?", "tapos?", "ok?", "what is the problem?"), do NOT assume emotion. Ask a SPECIFIC clarifier in one short sentence. No "draining your energy" / "tough one" framing.\n' +
      '9. NEVER invent specific UI elements ("the asset card", "the Log Downtime button", "the Save icon"). The only WorkHive nouns you may use verbatim are: Logbook, Inventory, PM Scheduler, Asset Hub, Alert Hub, Analytics, Day Planner, Shift Brain, Hive Board, Voice Journal, Work Assistant. To act on something, tell the worker which TOOL to open — never describe a specific button you weren\'t explicitly told about.\n' +
      '10. REPLY IN ENGLISH, ALWAYS. The worker can speak Tagalog / Cebuano / Filipino at you — UNDERSTAND it, but reply in PH-English. You may keep ONE short Tagalog warmth word per reply (naks / hala / pre / ate / ka), no more. If you find yourself writing a full Tagalog sentence ("Ano ba talaga hinahanap mo?", "Naiintindihan kita..."), STOP and rewrite in English. Pure-Tagalog replies are a hard fail.\n' +
      '11. NO REPEAT REPLIES. If your prior reply in memory said exactly the same thing you are about to say, the worker is asking for MORE detail, not the same answer. Add a different facet: which tab inside the tool, when the data refreshes, what the number actually means, what to compare it against. If the only honest answer is still the same tool, name a fresh angle — never repeat the same sentence twice.\n' +
      'If unsure whether the question is factual or emotional: treat it as factual and answer it.';
  }

  async function _saveJournalTurn(db, ctx, transcript, reply, persona) {
    if (!db) return;
    try {
      const { data: { user } = { user: null } } = await db.auth.getUser();
      const auth_uid = user ? user.id : null;
      await db.from('voice_journal_entries').insert({
        auth_uid,
        worker_name: ctx.worker_name || null,
        hive_id:     ctx.hive_id || null,
        transcript:  String(transcript || ''),
        reply:       String(reply || ''),
        lang:        'en',
        meta:        { source: 'voice-handler', persona },
      });
    } catch (err) {
      console.warn('[WHVoice] journal save failed (non-fatal):', err && err.message);
    }
  }

  // Map of "the worker said a command we can't dispatch here" to the
  // canonical guidance for that command. Keeps routing hints accurate
  // and stops the model from inventing UI elements.
  const UNHANDLED_INTENT_GUIDANCE = {
    'logbook.create':  "they want to log a maintenance entry — tell them to open the Logbook from the menu and tap +Add (or use Speak-to-Fill there). Don't describe specific buttons.",
    'inventory.use':   "they want to record a parts pull — tell them to open Inventory and select the part.",
    'inventory.restock': "they want to restock a part — tell them to open Inventory and use the Restock action on that item.",
    'asset.lookup':    "they want details on an asset — tell them to open Asset Hub and tap the asset card.",
    'pm.complete':     "they want to close a PM — tell them to open PM Scheduler and tap the asset's PM card.",
  };

  async function _converseInline(transcript, opts) {
    const db = _getDb();
    const ctx = _ctx();
    const persona = (typeof window.getPersona === 'function')
      ? window.getPersona() : 'james';
    const personaName = persona === 'rosa' ? 'Rosa' : 'James';
    const hiveName = (function () {
      try { return localStorage.getItem('wh_hive_name') || ''; } catch (_) { return ''; }
    })();
    const pageLabel = _currentPage();
    const unhandledKind = opts && opts.unhandledKind;
    const routerIntents = opts && opts.routerIntents;
    const routerNarration = opts && opts.routerNarration;
    const routingHint = unhandledKind ? UNHANDLED_INTENT_GUIDANCE[unhandledKind] : null;
    const routerContext = routerIntents && routerIntents.length
      ? `Router classified: ${routerIntents[0].kind} (${Math.round((routerIntents[0].confidence || 0) * 100)}%)`
      : '';

    _setStatus(personaName + ' is thinking…');
    _setRecRowVisible(false);
    _renderReplyBubble(null, persona);

    // Phase 4: Fetch dialog state (intent evolution + context slots)
    const sessionId = _getSessionId();
    const priorDialogState = await _fetchDialogState(db, sessionId).catch(() => null);
    const priorIntent = priorDialogState && priorDialogState.current_intent;
    const priorSlots = priorDialogState && priorDialogState.context_slots;

    // Phase 5: Fetch proactive alerts (KPI spikes, risk escalation, overdue PM)
    const proactiveAlerts = await _fetchProactiveAlerts(db, ctx.hive_id).catch(() => []);

    // FULL PLATFORM SCAN: pull everything from every truth view in parallel, hand to LLM.
    // No routing decisions, no intent classification — the LLM gets the complete platform
    // snapshot every turn and picks what's relevant. This eliminates "I don't have that info"
    // for any data that exists on the platform (KPIs, PM, inventory, logbook, schedule,
    // skills, projects, anomalies, knowledge, adoption — all in one shot).
    const firstIntent = routerIntents && routerIntents[0];
    const [platformSnapshot, platformData, memoryBlock, ragContext] = await Promise.all([
      _fetchFullPlatformSnapshot(db, ctx.hive_id, ctx.worker_name).catch((err) => {
        console.warn('[WHVoice] Platform snapshot failed:', err);
        return '';
      }),
      _invokePlatformScraper(db, ctx.hive_id, ctx.worker_name).catch(() => ''),
      _fetchRecentMemory(db, ctx.worker_name),
      _invokeRAGAgent(db, ctx.worker_name, firstIntent, transcript).catch(() => ''),
    ]);

    // canonicalData carries the full snapshot — every truth view in one block.
    // platformData (legacy scraper) and ragContext stay separate for now.
    const canonicalData = platformSnapshot || '';
    if (!canonicalData && db && ctx.hive_id && ctx.worker_name) {
      console.warn('[WHVoice] No platform snapshot returned; check DB connection or query errors');
    }

    const system = _buildVoiceSystemPrompt(persona, ctx.worker_name, hiveName, pageLabel, routingHint, memoryBlock, canonicalData, routerContext, platformData, ragContext, priorDialogState, proactiveAlerts);
    const messages = [
      { role: 'system', content: system },
      { role: 'user',   content: transcript },
    ];

    try {
      const fetcher = (typeof window.fetchWithTimeout === 'function')
        ? window.fetchWithTimeout
        : (u, o) => fetch(u, o);
      const resp = await fetcher(WH_ASSISTANT_WORKER_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model:      'meta-llama/llama-4-scout-17b-16e-instruct',
          max_tokens: 280,
          messages,
        }),
      }, 25000);
      if (!resp)        throw new Error('Network timeout');
      if (!resp.ok)     throw new Error('Worker error ' + resp.status);
      const data = await resp.json();
      const answer = String(
        (data && data.choices && data.choices[0] && data.choices[0].message && data.choices[0].message.content) || ''
      ).trim();
      if (!answer) {
        _setStatus('No reply came back. Tap to try again.');
        _renderReplyBubble('(no reply)', persona);
        _showTalkAgainButton();
        return;
      }
      // Phase 4: Intent refinement + clarification logic
      const newIntentKind = (firstIntent && firstIntent.kind) || 'unknown';
      const newConfidence = (firstIntent && firstIntent.confidence) || 0;

      // If intent flipped and confidence low, ask clarification instead
      if (_shouldClarify(newConfidence, priorIntent, newIntentKind)) {
        const clarifyAnswer = _generateClarification(transcript, newIntentKind, priorIntent);
        _setStatus(personaName + ' is clarifying:');
        _renderReplyBubble(clarifyAnswer, persona);
        if (typeof window.speakPersona === 'function') {
          window.speakPersona(clarifyAnswer, { persona });
        }
        _appendSessionTurn(transcript, clarifyAnswer);
        _saveJournalTurn(db, ctx, transcript, clarifyAnswer, persona);
        _storeTurn(db, ctx.hive_id, ctx.worker_name, transcript, clarifyAnswer, newIntentKind, newConfidence, 0);
        _updateDialogState(db, ctx.hive_id, sessionId, priorIntent, (priorDialogState && priorDialogState.intent_confidence) || newConfidence, priorSlots || {}, true, clarifyAnswer);
        _showTalkAgainButton();
        return;
      }

      _setStatus(personaName + ' says:');
      _renderReplyBubble(answer, persona);
      if (typeof window.speakPersona === 'function') {
        window.speakPersona(answer, { persona });
      }
      // Session-memory turn (always — works for anon walkthrough).
      _appendSessionTurn(transcript, answer);
      // Durable save — silently no-ops if RLS denies (anon workers).
      _saveJournalTurn(db, ctx, transcript, answer, persona);
      // Phase 2: Store in agent_memory table (session-scoped, enable recall + dedup)
      _storeTurn(db, ctx.hive_id, ctx.worker_name, transcript, answer, newIntentKind, newConfidence, 0);
      // Phase 4: Update dialog state with new intent + context (enable multi-turn slot carryover)
      _updateDialogState(db, ctx.hive_id, sessionId, newIntentKind, newConfidence, {}, false, null);
      _showTalkAgainButton();
    } catch (err) {
      console.warn('[WHVoice] conversational call failed:', err);

      // Phase 3: Error recovery with graceful fallback
      const fallbackReply = _generateFallbackReply(transcript, routerIntents, persona);
      _setStatus(personaName + ' (offline):');
      _renderReplyBubble(fallbackReply, persona);
      if (typeof window.speakPersona === 'function') {
        window.speakPersona(fallbackReply, { persona });
      }
      // Session-memory turn (capture both success and fallback responses).
      _appendSessionTurn(transcript, fallbackReply);
      // Best-effort save even on failure — capture the transcript so it
      // doesn't get lost.
      _saveJournalTurn(db, ctx, transcript, fallbackReply, persona);
      _showTalkAgainButton();
    }
  }

  function _renderReplyBubble(text, persona) {
    const slot = document.getElementById('wh-voice-intents');
    if (!slot) return;
    const avatarHTML = (typeof window.personaAvatarHTML === 'function')
      ? window.personaAvatarHTML(persona, 28)
      : '<span style="display:inline-block;width:28px;height:28px;border-radius:50%;background:linear-gradient(135deg,#F7A21B,#FDB94A);"></span>';
    const safe = String(text == null ? '' : text)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    if (text === null) {
      // Thinking dots — a known visual cue while the model warms up.
      slot.innerHTML =
        '<div class="wh-voice-bubble wh-voice-bubble-assistant">' +
          avatarHTML +
          '<span class="wh-voice-bubble-text"><span class="wh-voice-dots"><i></i><i></i><i></i></span></span>' +
        '</div>';
    } else {
      slot.innerHTML =
        '<div class="wh-voice-bubble wh-voice-bubble-assistant">' +
          avatarHTML +
          '<span class="wh-voice-bubble-text">' + safe + '</span>' +
        '</div>';
    }
  }

  function _showTalkAgainButton() {
    const actions = document.querySelector('.wh-voice-actions');
    if (!actions) return;
    // Reuse / repurpose the Confirm slot — relabel as "Tap to talk again".
    let again = document.getElementById('wh-voice-again');
    if (!again) {
      again = document.createElement('button');
      again.id = 'wh-voice-again';
      again.type = 'button';
      again.className = 'wh-voice-btn-action wh-voice-confirm';
      again.textContent = '🎙  Tap to talk again';
      again.addEventListener('click', () => {
        // Reset the overlay to a fresh recording state in place.
        _setResult('');
        _setTranscript('');
        document.getElementById('wh-voice-intents').innerHTML = '';
        again.style.display = 'none';
        _startRecording();
      });
      actions.appendChild(again);
    }
    again.style.display = 'block';
    const stopBtn = document.getElementById('wh-voice-stop');
    if (stopBtn) stopBtn.style.display = 'none';

    // Show TTS toggle button
    _showTtsToggle();
  }

  function _showTtsToggle() {
    const actions = document.querySelector('.wh-voice-actions');
    if (!actions) return;
    let ttsBtn = document.getElementById('wh-voice-tts-toggle');
    if (!ttsBtn) {
      ttsBtn = document.createElement('button');
      ttsBtn.id = 'wh-voice-tts-toggle';
      ttsBtn.type = 'button';
      ttsBtn.className = 'wh-voice-btn-action wh-voice-secondary';
      ttsBtn.style.cssText = 'background-color:#666;font-size:0.9em;';
      ttsBtn.addEventListener('click', () => {
        const isOn = typeof window.toggleTts === 'function' ? window.toggleTts() : false;
        ttsBtn.textContent = isOn ? '🔊 Voice on' : '🔇 Voice off';
        ttsBtn.style.backgroundColor = isOn ? '#4CAF50' : '#666';
      });
      actions.appendChild(ttsBtn);
    }
    ttsBtn.style.display = 'block';
    const isOn = typeof window.isTtsOn === 'function' ? window.isTtsOn() : false;
    ttsBtn.textContent = isOn ? '🔊 Voice on' : '🔇 Voice off';
    ttsBtn.style.backgroundColor = isOn ? '#4CAF50' : '#666';
  }

  function _fallthroughToChat(q) {
    // Best-effort: open floating-ai chat with the question prefilled.
    try {
      if (window.WHAssistant && typeof window.WHAssistant.sendMessage === 'function') {
        window.WHAssistant.sendMessage(q);
      } else {
        // Floating-ai exposes openPanel via direct DOM if API missing
        const input = document.getElementById('wh-ai-input');
        if (input) {
          input.value = q;
          input.focus();
          document.getElementById('wh-ai-panel')?.classList.add('open');
        }
      }
    } catch (_) {}
  }

  // ─── Public API ──────────────────────────────────────────────────────────
  function open() {
    _mount();
    const ov = document.getElementById('wh-voice-overlay');
    if (!ov) return;
    ov.classList.add('open');
    _setTranscript('');
    _setResult('');
    document.getElementById('wh-voice-intents').innerHTML = '';
    const confirmBtn = document.getElementById('wh-voice-confirm');
    if (confirmBtn) { confirmBtn.style.display = 'none'; confirmBtn.disabled = false; confirmBtn.textContent = 'Confirm'; }
    const again = document.getElementById('wh-voice-again');
    if (again) again.style.display = 'none';
    _startRecording();
  }

  function close() {
    _stopRecording();
    if (_stream) { _stream.getTracks().forEach(t => t.stop()); _stream = null; }
    const ov = document.getElementById('wh-voice-overlay');
    if (ov) ov.classList.remove('open');
  }

  function register(kind, handler) {
    if (typeof handler !== 'function') return;
    handlers[kind] = handler;
  }

  // Debug helper: log current context for troubleshooting voice issues
  window._debugVoiceContext = function() {
    const ctx = _ctx();
    const db = _getDb();
    const lsKeys = Object.keys(localStorage).filter(k => k.includes('wh_') || k.includes('hive') || k.includes('worker') || k.includes('auth'));
    console.log('[WHVoice Debug] Current Context:', {
      db_available: !!db,
      worker_name: ctx.worker_name || '(empty)',
      hive_id: ctx.hive_id || '(empty)',
      hive_role: ctx.hive_role || '(empty)',
      all_relevant_localStorage_keys: lsKeys.map(k => k + '=' + (localStorage.getItem(k) ? '✓' : '✗')).join(' | '),
    });
    return { ctx, db_available: !!db };
  };

  window.WHVoice = { open, close, register, dispatch, _handlers: handlers, _debugContext: window._debugVoiceContext };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _mount);
  } else {
    _mount();
  }
})();
