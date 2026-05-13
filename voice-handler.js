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
        // CONVERSATIONAL PATH — query.ask / unknown.
        // Auto-call voice-journal-agent through ai-gateway. The gateway
        // both replies in James/Rosa's voice AND saves the turn to
        // voice_journal_entries + agent_memory (durable + recallable).
        // Hide the intent cards and the standard Confirm button.
        document.getElementById('wh-voice-intents').innerHTML = '';
        if (confirmBtn) confirmBtn.style.display = 'none';
        await _converseInline(transcript);
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

  function _buildVoiceSystemPrompt(persona, workerName, hiveName, pageLabel) {
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

    return personaBlock + '\n\n' +
      'You are answering a worker over voice. They will HEAR your reply, so:\n' +
      '- Keep it 2-3 short sentences. Long answers are tiring spoken aloud.\n' +
      '- If they asked a maintenance / work question, ANSWER IT directly with practical maintenance knowledge. If you don\'t have the data they\'re asking about (e.g. their specific PM schedule, their hive\'s OEE), say so plainly and point them to the right WorkHive tool: PM Scheduler for due tasks, Alert Hub for risk + low stock, Asset Hub for asset history, Analytics for MTBF/OEE.\n' +
      '- If they shared a feeling or vented, react first ("naks, mahirap yan" / "hala ka"), THEN one practical line.\n' +
      identBlock +
      '\nIf the worker mixes Filipino / Cebuano / Tagalog in, that\'s fine — understand it, reply in English.\n\n' +
      '═══════════════════════════════════════════════════════════════════\n' +
      'HARD RULES — read these last; they override everything above.\n' +
      '═══════════════════════════════════════════════════════════════════\n' +
      '1. NEVER ask "what changed?" or "what\'s changed today?" or "why are you asking again?" — these are clinical/therapy follow-ups and the worker hates them.\n' +
      '2. NEVER say "I see you\'ve been asking about X a lot lately" — you do NOT have conversation history in this turn; pretending you do is hallucination.\n' +
      '3. NEVER echo the worker\'s question back as the answer. "Priority checking ka na naman" is NOT an answer to "what\'s the priority PM today?"\n' +
      '4. NEVER treat a direct work question ("what is X", "how do I Y", "where can I find Z") as emotional. Just answer it or say honestly you can\'t see the data and point to the right tool.\n' +
      '5. If you find yourself starting with "Naiintindihan kita" or "I understand" on a factual question, STOP and rewrite — that opener is for emotional venting only.\n' +
      '6. NEVER mention the page name (e.g. "index", "logbook", "hive", "asset-hub") in your reply. Workers don\'t think in page names. Say "this page" or "your dashboard" or just answer naturally without referencing where they are.\n' +
      '7. NEVER invent details the worker did not mention. If they say "what is the problem?" — you do NOT know what problem. Do NOT make up "the production line" or "the pump" or "your machine". Ask back: "which one, pre?" — or if it\'s totally vague, say "tell me a bit more, what\'s going on?"\n' +
      '8. If the worker\'s message is short or ambiguous ("what now?", "tapos?", "ok?", "what is the problem?"), do NOT assume emotion. Ask a SPECIFIC clarifier in one short sentence. No "draining your energy" / "tough one" framing.\n' +
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

  async function _converseInline(transcript) {
    const db = _getDb();
    const ctx = _ctx();
    const persona = (typeof window.getPersona === 'function')
      ? window.getPersona() : 'james';
    const personaName = persona === 'rosa' ? 'Rosa' : 'James';
    const hiveName = (function () {
      try { return localStorage.getItem('wh_hive_name') || ''; } catch (_) { return ''; }
    })();
    const pageLabel = _currentPage();

    _setStatus(personaName + ' is thinking…');
    _setRecRowVisible(false);
    _renderReplyBubble(null, persona);

    const system = _buildVoiceSystemPrompt(persona, ctx.worker_name, hiveName, pageLabel);
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
      _setStatus(personaName + ' says:');
      _renderReplyBubble(answer, persona);
      if (typeof window.speakPersona === 'function') {
        window.speakPersona(answer, { persona });
      }
      // Background save — never blocks the UI.
      _saveJournalTurn(db, ctx, transcript, answer, persona);
      _showTalkAgainButton();
    } catch (err) {
      console.warn('[WHVoice] conversational call failed:', err);
      _setStatus('Could not reach ' + personaName + '. Tap to try again.');
      _renderReplyBubble('Sorry, the chat is offline right now. Your transcript above is still saved as a journal entry.', persona);
      // Best-effort save even on failure — capture the transcript so it
      // doesn't get lost.
      _saveJournalTurn(db, ctx, transcript, '', persona);
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

  window.WHVoice = { open, close, register, dispatch, _handlers: handlers };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _mount);
  } else {
    _mount();
  }
})();
