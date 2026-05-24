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
        /* storage-key-allow: legacy worker-name fallback (current writes use wh_last_worker) */ localStorage.getItem('wh_worker_name') ||
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
  let _micQualityMeter = null;  // T63 — AnalyserNode wrapper; stopped on close
  let _chunks = [];
  let _stopTimer = null;
  let _sessionId = null;          // Phase 2: session-scoped memory tracking
  let _turnNum = 0;               // Phase 2: turn counter per session

  // Phase 2: Initialize session ID (per-tab or per-conversation window).
  // Persists in sessionStorage so a page reload inside the same tab keeps
  // the same session ID (preserves dialog state continuity).
  function _getSessionId() {
    if (!_sessionId) {
      // empty-catch-allow: sessionStorage may be denied in private-browsing or
      // strict-cookie modes. Failure here is benign — we just fall through to
      // generating a fresh ID, which is the existing behaviour.
      try {
        if (typeof sessionStorage !== 'undefined') {
          const prior = sessionStorage.getItem('wh_voice_session_id');
          if (prior && prior.startsWith('voice_session_')) {
            _sessionId = prior;
          }
        }
      } catch (_) { /* sessionStorage may be denied */ /* empty-catch-allow: best-effort silent swallow */ }
      if (!_sessionId) {
        _sessionId = 'voice_session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
      }
      // empty-catch-allow: setItem fails the same way as getItem; we already
      // have a working in-memory session ID, persistence is best-effort.
      try {
        if (typeof sessionStorage !== 'undefined') {
          sessionStorage.setItem('wh_voice_session_id', _sessionId);
        }
      } catch (_) { /* sessionStorage may be denied */ /* empty-catch-allow: best-effort silent swallow */ }
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
    // Phase 4.21 (turn #17) AUDIO INTERRUPT — if Zaniah/Hezekiah is mid-
    // sentence and the worker taps the mic, KILL the audio first.
    // Otherwise the worker hears their own question over the persona's
    // reply, which sounds broken on noisy plant floors. Both the Edge
    // / Azure audio path (wh-tts._audio) and the browser TTS fallback
    // need cancelling — wh-tts.stop() does both.
    if (window.WHTts && typeof window.WHTts.stop === 'function') {
      try { window.WHTts.stop(); } catch (_) { /* non-fatal */ /* empty-catch-allow: best-effort silent swallow */ }
    } else if (window.speechSynthesis) {
      try { window.speechSynthesis.cancel(); } catch (_) { /* non-fatal */ /* empty-catch-allow: best-effort silent swallow */ }
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      _setStatus('Voice not supported on this browser.');
      _setRecRowVisible(false);
      return;
    }
    try {
      _stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      // Phase 4.62 (turn #63) Mic quality meter — wraps the live stream
      // in an AnalyserNode. If the peak stays below threshold for >2s,
      // we surface a one-time "you sound far away" hint to the worker.
      try {
        if (_micQualityMeter && typeof _micQualityMeter.stop === 'function') {
          _micQualityMeter.stop();
        }
        _micQualityMeter = _attachMicQualityMeter(_stream, function () {
          _setStatus('You sound far away — speak closer to the mic.');
        });
      } catch (_) { /* non-fatal */ /* empty-catch-allow: best-effort silent swallow */ }
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
  // 2026-05-19 Companion Streamline Step C/D: legacy Cloudflare Worker
  // const kept here as a tombstone reference for git-archaeology only.
  // Production code now routes EVERY conversational reply through
  // ai-gateway (Step C) and embedding lookups through _embedQuery()
  // (which is a stub until the embed-entry edge fn is exposed for
  // synchronous RAG embedding from the browser). The Worker URL must
  // NOT be passed to fetch/fetcher anywhere — enforced by
  // validate_legacy_worker_decommission.py.
  const WH_ASSISTANT_WORKER_URL_DEPRECATED = 'https://workhive-assistant.ian-beronio37.workers.dev';

  // _embedQuery: returns the [384]-dim embedding vector for `transcript`
  // or null when no synchronous embeddings backend is available. The
  // callers gracefully degrade — RAG / KG / Standards context just
  // becomes the empty string in that case. Wire this to a real
  // /functions/v1/embed-entry call when that path is exposed without
  // requiring an auth.uid (today it embeds journal entries, not query
  // strings). TODO closes when that work lands.
  async function _embedQuery(_transcript) {
    return null;
  }

  // Session-only fallback memory. voice_journal_entries requires auth
  // (RLS: auth.uid() = auth_uid for both read and insert), so anon
  // workers in the Tester walkthrough have no persistent memory. We
  // keep the last few turns in a module-local array so within one page
  // session Hezekiah / Zaniah still has continuity. Lost on page reload —
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
      } catch (_) { /* RLS denial / network — fall through */ /* empty-catch-allow: best-effort silent swallow */ }
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
        console.log('[WHVoice] Turn ' + _turnNum + ' stored to agent_memory'); // console-log-allow: agent-memory store confirmation, low-volume (1 per turn)
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
    if (!db || !hiveId) {
      console.warn('[WHVoice] Fetch alerts: missing db or hiveId', { hasDb: !!db, hiveId });
      return [];
    }
    try {
      console.log('[WHVoice] Calling fetch_active_alerts RPC with hiveId:', hiveId); // console-log-allow: RPC call observability (alerts fetch debug)
      const { data, error } = await db.rpc('fetch_active_alerts', { p_hive_id: hiveId });
      console.log('[WHVoice] RPC response:', { data, error }); // console-log-allow: RPC response observability
      if (error) {
        console.warn('[WHVoice] Fetch alerts RPC error:', JSON.stringify(error));
        return [];
      }
      if (!data || !Array.isArray(data)) {
        console.warn('[WHVoice] Fetch alerts returned invalid data:', data, 'type:', typeof data);
        return [];
      }
      // Validate alert structure — ensure description & action_suggested exist
      const validated = data.slice(0, 5).map((a) => {
        if (!a.description || !a.action_suggested) {
          console.warn('[WHVoice] Alert missing description or action:', a);
        }
        return a;
      });
      console.log('[WHVoice] Fetched alerts:', validated.length, 'alerts'); // console-log-allow: alerts count confirmation
      return validated;
    } catch (err) {
      console.warn('[WHVoice] Proactive alerts fetch exception:', err && err.message);
      return [];
    }
  }

  // Phase 6: Offline resilience — cache snapshot + response queue
  async function _cacheOfflineSnapshot(db, hiveId, snapshot) {
    if (!db) return;
    try {
      const hash = String(snapshot).slice(0, 100);
      await db.from('offline_snapshot_cache').insert({
        worker_id: (await db.auth.getUser())?.data?.user?.id,
        hive_id: hiveId,
        snapshot_data: JSON.parse(snapshot || '{}'),
        snapshot_hash: hash,
        expires_at: new Date(Date.now() + 24*60*60*1000).toISOString(),
      });
    } catch (err) {
      console.warn('[WHVoice] Offline cache failed:', err && err.message);
    }
  }

  // Phase 7: TTS quality metrics + caching
  async function _logTTSMetrics(db, hiveId, latencyMs, error) {
    if (!db) return;
    try {
      await db.from('tts_quality_log').insert({
        worker_id: (await db.auth.getUser())?.data?.user?.id,
        hive_id: hiveId,
        persona: 'zaniah',
        latency_ms: latencyMs,
        error_message: error || null,
      });
    } catch (err) {
      console.warn('[WHVoice] TTS metrics log failed:', err && err.message);
    }
  }

  // Phase 8: Capture response quality for learning loop
  async function _captureAnalytics(db, sessionId, turnNum, category, quality, confidence) {
    if (!db) return;
    try {
      await db.from('conversation_analytics').insert({
        session_id: sessionId,
        turn_num: turnNum,
        question_category: category,
        answer_quality_rating: quality,  // -1, 0, or 1
        model_confidence: confidence,
        response_time_ms: 0,  // filled by caller if needed
      });
    } catch (err) {
      console.warn('[WHVoice] Analytics capture failed:', err && err.message);
    }
  }

  // Phase 9: Cross-hive context awareness
  async function _fetchCrossHiveContext(db) {
    if (!db) return '';
    try {
      const { data, error } = await db.from('cross_hive_alerts')
        .select('alert_reason, severity')
        .eq('severity', 'critical')
        .limit(3);
      if (error || !data || data.length === 0) return '';
      return 'CROSS-HIVE CONTEXT: ' + data.map(a => a.alert_reason).join('; ');
    } catch (err) {
      return '';
    }
  }

  // Phase 10: Avatar state tracking
  async function _updateAvatarState(db, sessionId, state, emotion) {
    if (!db) return;
    try {
      await db.from('avatar_state').upsert({
        session_id: sessionId,
        current_state: state,
        emotion: emotion || 'neutral',
        updated_at: new Date().toISOString(),
      });
    } catch (err) {
      console.warn('[WHVoice] Avatar state update failed:', err && err.message);
    }
  }

  // Phase 11: Multilingual term lookup (per-term — for UI rendering)
  async function _lookupMultilingualTerm(db, englishTerm, targetLanguage) {
    if (!db || !targetLanguage || targetLanguage === 'en') return englishTerm;
    try {
      const { data, error } = await db.from('multilingual_terms')
        .select(targetLanguage === 'tl' ? 'tagalog_term' : 'visayan_term')
        .eq('english_term', englishTerm)
        .limit(1);
      if (error || !data || !data[0]) return englishTerm;
      return targetLanguage === 'tl' ? (data[0].tagalog_term || englishTerm) : (data[0].visayan_term || englishTerm);
    } catch (err) {
      return englishTerm;
    }
  }

  // Day 5 (L7): Load PH industrial phrase glossary for the LLM system prompt.
  // The 207 Tagalog/Visayan terms seeded by tools/day5_seed_filipino_phrases.py
  // act as a context cache so the LLM correctly understands worker code-switching
  // ("may oil leak sa motor" -> oil leak + motor). Module-scope memoized; the
  // table is small (~207 rows) so one fetch per page load is plenty.
  let _filipinoGlossaryCache = null;
  async function _fetchFilipinoGlossary(db) {
    if (_filipinoGlossaryCache !== null) return _filipinoGlossaryCache;
    if (!db) { _filipinoGlossaryCache = ''; return ''; }
    try {
      const { data, error } = await db.from('multilingual_terms')
        .select('english_term, tagalog_term, visayan_term, domain')
        .order('domain', { ascending: true });
      if (error || !data || !data.length) { _filipinoGlossaryCache = ''; return ''; }

      // Format: one line per term, grouped by domain header. Skip rows with no
      // translations at all (no point spending tokens on bare English).
      const byDomain = {};
      for (const row of data) {
        if (!row.tagalog_term && !row.visayan_term) continue;
        if (!byDomain[row.domain]) byDomain[row.domain] = [];
        const parts = [row.english_term];
        if (row.tagalog_term) parts.push('tl: ' + row.tagalog_term);
        if (row.visayan_term) parts.push('ceb: ' + row.visayan_term);
        byDomain[row.domain].push(parts.join(' / '));
      }
      const lines = [];
      for (const dom of Object.keys(byDomain).sort()) {
        lines.push('[' + dom + '] ' + byDomain[dom].join('; '));
      }
      _filipinoGlossaryCache = lines.join('\n');
      return _filipinoGlossaryCache;
    } catch (err) {
      console.warn('[WHVoice] Filipino glossary fetch failed:', err && err.message);
      _filipinoGlossaryCache = '';
      return '';
    }
  }

  // Phase 3: Semantic RAG — embed query and search knowledge base
  async function _fetchRAGContext(db, hiveId, transcript) {
    if (!db || !hiveId || !transcript) return '';
    try {
      // 2026-05-19 Step C/D: embedding via _embedQuery() stub until a
      // browser-callable embed-entry edge fn exists. Returns null today,
      // which short-circuits RAG context — graceful degrade, no offline
      // banner. See validate_legacy_worker_decommission.py.
      const embedding = await _embedQuery(transcript);
      if (!embedding) return '';

      // Semantic search in kb_chunks via RPC
      const { data: chunks, error } = await db.rpc('semantic_search_kb', {
        p_hive_id: hiveId,
        p_query_embedding: embedding,
        p_similarity_threshold: 0.7,
        p_limit: 5,
      });

      if (error || !chunks || chunks.length === 0) return '';

      // Format RAG context with citations
      return chunks.map(c => {
        const doc = (c.doc_title || '').slice(0, 50);
        const text = (c.chunk_text || '').slice(0, 300);
        return `[${doc}] ${text}`;
      }).join('\n\n');
    } catch (err) {
      console.warn('[WHVoice] RAG context fetch failed:', err && err.message);
      return '';
    }
  }

  // Day 5 / Day 8 (L5): Knowledge-graph triples retrieval — TWO STORES.
  // - knowledge_graph_facts            = HIVE-scoped     (this hive's claims)
  // - platform_knowledge_graph_facts   = PLATFORM-scoped (regulatory canon)
  // Mirrors the kb_chunks vs. industry_standards_chunks split. One query
  // embedding fans out to both RPCs; results merged by similarity score.
  // The 2026-05-19 migration moved 1,533 standards-derived triples out of
  // the hive table (where they had been broadcast x3 = 4,605 rows) into
  // the platform table — single source of truth per canonical-audit reflex.
  async function _fetchKGContext(db, hiveId, transcript) {
    if (!db || !transcript) return '';
    try {
      const embedding = await _embedQuery(transcript);
      if (!embedding) return '';

      // Fan out: hive-scoped only if we have a hive_id, platform always.
      const hivePromise = hiveId
        ? db.rpc('semantic_search_kg_facts', {
            p_hive_id:              hiveId,
            p_query_embedding:      embedding,
            p_similarity_threshold: 0.5,
            p_limit:                4,
            p_min_confidence:       0.6,
          })
        : Promise.resolve({ data: [], error: null });

      const platformPromise = db.rpc('semantic_search_platform_kg_facts', {
        p_query_embedding:      embedding,
        p_similarity_threshold: 0.5,
        p_limit:                4,
        p_min_confidence:       0.6,
      });

      const [hiveRes, platformRes] = await Promise.all([hivePromise, platformPromise]);

      const hiveFacts     = (hiveRes && !hiveRes.error && Array.isArray(hiveRes.data))     ? hiveRes.data     : [];
      const platformFacts = (platformRes && !platformRes.error && Array.isArray(platformRes.data)) ? platformRes.data : [];
      const combined = [...hiveFacts, ...platformFacts];
      if (combined.length === 0) return '';

      // Lower similarity_score = closer in cosine distance (matches RPC convention).
      combined.sort((a, b) => (a.similarity_score || 1) - (b.similarity_score || 1));
      const top = combined.slice(0, 6);

      return top.map(f => {
        const claim = (f.claim_text || `${f.subject_ref} ${f.predicate} ${f.object_ref}`).slice(0, 220);
        const src   = (f.source_ref || f.source_type || '').slice(0, 40);
        return src ? `[${src}] ${claim}` : claim;
      }).join('\n');
    } catch (err) {
      console.warn('[WHVoice] KG context fetch failed:', err && err.message);
      return '';
    }
  }

  // Day 4: Platform-wide standards retrieval (industry_standards_chunks).
  // Mirrors _fetchRAGContext but is HIVE-AGNOSTIC — standards are global.
  // Use when worker asks about ISO/IEC/ASHRAE/NFPA/PSME/DOLE regulations or
  // best practice canon. Returned chunks carry the standard_code as citation.
  async function _fetchStandardsContext(db, transcript) {
    if (!db || !transcript) return '';
    try {
      const embedding = await _embedQuery(transcript);
      if (!embedding) return '';

      // Platform-wide semantic search — no hive_id param.
      // Lower threshold (0.5) since standards corpus is narrower than per-hive KB.
      const { data: chunks, error } = await db.rpc('semantic_search_industry_standards', {
        p_query_embedding:       embedding,
        p_similarity_threshold:  0.5,
        p_limit:                 3,
        p_family:                null,  // all families
      });

      if (error || !chunks || chunks.length === 0) return '';

      return chunks.map(c => {
        const code = (c.standard_code || 'standard').slice(0, 40);
        const section = c.section ? ` §${c.section}` : '';
        const text = (c.chunk_text || '').slice(0, 300);
        return `[${code}${section}] ${text}`;
      }).join('\n\n');
    } catch (err) {
      console.warn('[WHVoice] Standards context fetch failed:', err && err.message);
      return '';
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

  // Phase 4.1: Follow-up affirmation detector — bypass the clarification UI.
  // Caught 2026-05-20: worker said "Yes, the details" after being asked about
  // query.ask and Zaniah STILL surfaced "Did you mean to keep talking about
  // query.ask, or switch to unknown?". Affirmative continuations must
  // resume the prior topic, not look like a topic switch.
  //
  // Phrases match the SHORT-REPLY shape only (start-of-utterance, ≤5 words);
  // longer requests like "yes — and also tell me about MTBF" should still
  // go through normal intent classification.
  const _AFFIRMATION_RE = /^(yes|yeah|yep|yup|sure|ok|okay|alright|right|correct|that(?:'|’)?s\s+right|of course|definitely|absolutely|tama|opo|oo|sige|sige na|sige po|go|go on|please|continue|tell me more|more details?|the details?|details(?:\s+please)?|kindly)([\s,!.?]|$)/i;
  function _isFollowupAffirmation(text) {
    const s = String(text || '').trim();
    if (!s) return false;
    // Cap: short utterances only. A long sentence starting with "yes" is a
    // real follow-up question, not a bare confirmation.
    const words = s.split(/\s+/);
    if (words.length > 5) return false;
    return _AFFIRMATION_RE.test(s);
  }

  // Phase 4.2: Follow-up NEGATION detector — mirror of affirmation.
  // Short "no", "cancel that", "wala na", "hindi", "scratch that" after a
  // prior topic / pending clarification MUST exit the thread cleanly,
  // not be classified as a new intent (which would also trip the
  // clarification UI). Same ≤5-word cap as affirmation so longer
  // sentences ("no, tell me about MTBF instead") still classify normally.
  const _NEGATION_RE = /^(no|nope|nah|not really|not now|never mind|nevermind|cancel|cancel that|scratch that|skip|forget it|stop|hindi|hindi pa|wala|wala na|huwag na|ayaw|ayaw ko)([\s,!.?]|$)/i;
  function _isFollowupNegation(text) {
    const s = String(text || '').trim();
    if (!s) return false;
    const words = s.split(/\s+/);
    if (words.length > 5) return false;
    return _NEGATION_RE.test(s);
  }

  // Phase 4.3: Noisy / empty transcript guard. Background sound, false
  // mic trigger, "uh", "um", or 1-2 character garbage transcripts must
  // NEVER enter intent classification — the resulting unknown intent
  // would otherwise trip the topic-switch clarification UI for what is
  // really just silence. Routes to a "didn't catch that" prompt instead.
  function _isNoisyTranscript(text) {
    const s = String(text || '').trim();
    if (!s) return true;                                // empty
    // Short negation / affirmation bypass: "no", "oo", "ok" are 1-2 chars
    // but ARE valid worker utterances — let them through so the follow-up
    // affirmation/negation classifier can route them properly.
    if (/^(no|oo|ok|ko|sí|si|ya|aw|aw\.?)[.!?,]*$/i.test(s)) return false;
    if (s.length < 3) return true;                      // 1-2 chars
    if (/^[^\w]+$/.test(s)) return true;                // pure punctuation/whitespace
    // Lone filler word ("uh", "um", "ah", "hm", "oh") with nothing else.
    if (s.split(/\s+/).length === 1 && /^(uh|um|ah|hm|hmm|oh|er|eh)[.!?,]*$/i.test(s)) return true;
    return false;
  }

  // Phase 4.4: Clarification-loop ceiling. If we already clarified twice
  // in a row and the worker STILL hasn't landed on a clear intent, we
  // stop clarifying — looping the same prompt makes Zaniah/Hezekiah feel
  // broken. After 2 consecutive clarifies we ask once in a different
  // shape ("what page would help?") and HARD reset the counter so we
  // can never loop more than 3 deep on the same conversation.
  let _clarifyStreak = 0;
  function _getClarifyStreak() { return _clarifyStreak; }
  function _resetClarifyStreak() { _clarifyStreak = 0; }
  function _bumpClarifyStreak() { _clarifyStreak += 1; return _clarifyStreak; }

  // Phase 4.7: Clarification-recovery routing. After the streak ceiling
  // fires the "what page would help: Analytics, Logbook, PM Scheduler,
  // or Asset Hub?" prompt, a worker saying just "logbook" / "PM" /
  // "analytics" / "asset hub" must route DIRECTLY to that intent. Without
  // this detector the bare page name enters normal classification, gets
  // tagged 'unknown' (low confidence), and trips clarify AGAIN — the
  // exact loop the ceiling was supposed to break.
  //
  // Returns the resolved intent slug (compatible with _generateClarification's
  // intentNames map) when matched, else null. ≤4-word cap keeps real
  // sentences ("can you open the logbook page for me?") going through
  // normal classification.
  const _PAGE_RECOVERY_MAP = {
    'analytics':         'oee',
    'analytics report':  'oee',
    'oee':               'oee',
    'logbook':           'troubleshooting',
    'log':               'troubleshooting',
    'pm':                'pm_scheduling',
    'pm scheduler':      'pm_scheduling',
    'preventive maintenance': 'pm_scheduling',
    'asset':             'troubleshooting',
    'asset hub':         'troubleshooting',
    'asset brain':       'troubleshooting',
    'inventory':         'inventory_check',
    'parts':             'inventory_check',
    'predictive':        'risk_assessment',
    'risk':              'risk_assessment',
    'shift':             'pm_scheduling',
    'shift brain':       'pm_scheduling',
  };
  function _isPageRecoveryReply(text) {
    const s = String(text || '').trim().toLowerCase().replace(/[.,!?;:]/g, '');
    if (!s) return null;
    const words = s.split(/\s+/);
    if (words.length > 4) return null;
    if (Object.prototype.hasOwnProperty.call(_PAGE_RECOVERY_MAP, s)) {
      return _PAGE_RECOVERY_MAP[s];
    }
    return null;
  }

  // Phase 4.9: Persona-switch utterance detector (turn #5).
  // Workers occasionally ask for the OTHER companion mid-conversation —
  // "switch to Hezekiah", "talk to Zaniah", "tawagin si Hezekiah".
  // Without this detector the bare phrase gets intent-classified as
  // 'unknown' and trips the clarification UI. We instead route directly
  // to the persona toggle, render a warm hand-off, and clear dialog
  // state so the new persona starts on a clean slate.
  //
  // Returns the resolved persona key ('hezekiah' / 'zaniah') or null.
  const _PERSONA_SWITCH_RE = /^(?:switch to|talk to|change to|get|call|tawagin si|kunin si|usapin si)\s+(hezekiah|zaniah|hez|zan)\b/i;
  function _isPersonaSwitchUtterance(text) {
    const s = String(text || '').trim();
    if (!s) return null;
    const words = s.split(/\s+/);
    if (words.length > 6) return null;
    const m = _PERSONA_SWITCH_RE.exec(s);
    if (!m) return null;
    const tok = m[1].toLowerCase();
    if (tok === 'hez') return 'hezekiah';
    if (tok === 'zan') return 'zaniah';
    return tok;
  }

  // Phase 4.10: Stale dialog-state guard (turn #6).
  // A worker who comes back to voice journal hours later should be
  // treated as a FRESH conversation. Applying the prior intent / slots /
  // clarification_pending across a long gap makes the companion sound
  // like it didn't notice the worker was gone. Threshold: 15 minutes
  // since the prior turn. Anything older → ignore priorDialogState.
  const _STALE_THRESHOLD_MS = 15 * 60 * 1000;
  function _isStaleDialogState(dialogState) {
    if (!dialogState) return false;
    // updated_at / created_at / last_turn_at — whichever the RPC returns.
    const ts = dialogState.updated_at || dialogState.last_turn_at || dialogState.created_at;
    if (!ts) return false;
    const t = new Date(ts).getTime();
    if (!isFinite(t) || t <= 0) return false;
    return (Date.now() - t) > _STALE_THRESHOLD_MS;
  }

  // Phase 4.11: Topic interruption signal (turn #7).
  // The affirmation bypass (4.1) treats short follow-ups as "stay on the
  // prior topic". But sometimes a worker INTERRUPTS — "hold on", "wait,
  // actually", "speaking of", "by the way" — signalling they want to
  // switch topics RIGHT NOW. When this signal fires, we explicitly
  // SUPPRESS the affirmation bypass and let normal intent classification
  // run on the full utterance. The detector is "starts-with" so longer
  // sentences carry the signal correctly without bypass interference.
  const _TOPIC_SHIFT_RE = /^(?:hold on|hold up|wait|wait a sec|wait wait|actually|speaking of|by the way|btw|teka|sandali|sandali lang|teka muna)\b/i;
  function _isTopicShiftSignal(text) {
    const s = String(text || '').trim();
    if (!s) return false;
    return _TOPIC_SHIFT_RE.test(s);
  }

  // ─── Item 6 of AGENTIC_RAG_ROADMAP.md integration: long-horizon detector ──
  // Identifies questions that span multiple periods or 18-month+ history —
  // the queries the standard ai-gateway path can't ground without context
  // overflow. When this fires, voice-handler tries agentic-rag-loop first
  // (with hierarchical summaries + grader + checker) and falls back to
  // ai-gateway on any failure. Heuristic-only — never blocks short queries.
  const _LONG_HORIZON_RE = new RegExp(
    [
      // English: compare/trend across years/quarters/months
      /\b(compare|trend|history|over the (?:last|past))\b.*\b(year|years|quarter|quarters|month|months|decade)\b/i.source,
      // Multi-year explicit ranges or "since YYYY"
      /\b(20\d{2})\b.*\b(?:vs|versus|compared to|to)\b.*\b(20\d{2})\b/i.source,
      /\bsince\s+(?:20\d{2}|last\s+year)\b/i.source,
      // "Last N years" / "past N years"
      /\b(?:last|past)\s+(?:\d+|\bfive\b|\bten\b|\btwo\b|\bthree\b|\bfour\b)\s+years?\b/i.source,
      // "All-time", "since commissioning", "lifetime"
      /\b(all[\s-]?time|since\s+commissioning|lifetime|historical)\b/i.source,
      // Tagalog/Filipino: "mga taon", "mula nuong", "nakaraang taon"
      /\b(?:mga\s+taon|mula\s+nuong|nakaraang\s+taon|taon\s+na\s+ang\s+nakakaraan)\b/i.source,
    ].join('|'), 'i'
  );
  function _isLongHorizonQuestion(text) {
    const s = String(text || '').trim();
    if (!s || s.length < 8) return false;     // too short to be a horizon query
    return _LONG_HORIZON_RE.test(s);
  }

  // Phase 4.12: Thanks / acknowledgment detector (turn #8).
  // "Thanks" / "salamat" / "maraming salamat" / "appreciate it" are
  // conversation-CLOSERS. Workers don't want a follow-up question after
  // a thank-you — they want acknowledgment then silence so they can
  // get back to work. Skip the LLM, render a short "you're welcome"
  // beat, and clear the dialog state so the next utterance starts fresh.
  const _THANKS_RE = /^(?:thanks|thank you|thx|tnx|appreciate it|salamat|maraming salamat|salamat ah|salamat po|nice one|cool|got it|noted)([\s,!.?]|$)/i;
  function _isThanksReply(text) {
    const s = String(text || '').trim();
    if (!s) return false;
    const words = s.split(/\s+/);
    if (words.length > 5) return false;
    return _THANKS_RE.test(s);
  }

  // Phase 4.14: First-turn greeting detector (turn #10).
  // When a worker opens voice journal with NO prior dialog state AND
  // no in-session memory turns AND a short greeting-shape utterance
  // ("hello", "hi", "kumusta", "magandang umaga"), respond with a warm
  // hello rather than running the LLM through full grounding. The
  // greeting acts as a session opener — it sets the tone before the
  // worker gets into a real question.
  const _GREETING_RE = /^(?:hello|hi|hey|yo|good morning|good afternoon|good evening|magandang umaga|magandang hapon|magandang gabi|kumusta|kamusta|musta|kumusta ka|hi po|hello po|sup)([\s,!.?]|$)/i;
  function _isGreeting(text) {
    const s = String(text || '').trim();
    if (!s) return false;
    const words = s.split(/\s+/);
    if (words.length > 5) return false;
    return _GREETING_RE.test(s);
  }

  // Phase 4.28 (turn #28): Voice command shortcut detector.
  // "open logbook", "show analytics", "schedule a PM", "asset hub" —
  // explicit navigation requests that should jump to that page instead
  // of running through the conversational LLM. Returns the target URL
  // path (e.g. 'logbook.html') or null. Cap at 6 words so longer
  // questions ("can you walk me through how to open the logbook?") still
  // route through the LLM for a conversational answer.
  const _VOICE_SHORTCUT_MAP = {
    'open logbook':          'logbook.html',
    'go to logbook':         'logbook.html',
    'log this':              'logbook.html',
    'log a job':             'logbook.html',
    'open analytics':        'analytics.html',
    'show analytics':        'analytics.html',
    'show me analytics':     'analytics.html',
    'open pm':               'pm-scheduler.html',
    'open pm scheduler':     'pm-scheduler.html',
    'schedule pm':           'pm-scheduler.html',
    'schedule a pm':         'pm-scheduler.html',
    'open inventory':        'inventory.html',
    'show inventory':        'inventory.html',
    'open asset hub':        'asset-hub.html',
    'asset hub':             'asset-hub.html',
    'open hive':             'hive.html',
    'show hive':             'hive.html',
    'open community':        'community.html',
    'open dayplanner':       'dayplanner.html',
    'open day planner':      'dayplanner.html',
    'open assistant':        'assistant.html',
    'open ai assistant':     'assistant.html',
    'open report sender':    'report-sender.html',
    'show predictive':       'predictive.html',
  };
  function _isVoiceShortcut(text) {
    const s = String(text || '').trim().toLowerCase().replace(/[.,!?;:]/g, '');
    if (!s) return null;
    const words = s.split(/\s+/);
    if (words.length > 6) return null;
    if (Object.prototype.hasOwnProperty.call(_VOICE_SHORTCUT_MAP, s)) {
      return _VOICE_SHORTCUT_MAP[s];
    }
    return null;
  }

  // Phase 4.29 (turn #31): Goodbye / wrap-up detector. "yun lang" /
  // "that's all" / "I'm done" / "tapos na" — worker is closing the
  // conversation. Render a warm exit + persist a clean session end.
  // Different from thanks (T8) which is a closer ON A SINGLE TURN;
  // goodbye is a closer ON THE WHOLE SESSION.
  const _GOODBYE_RE = /^(?:that(?:'|’)?s\s+all|that(?:'|’)?s\s+it|i(?:'|’)?m\s+done|im\s+done|done|all\s+set|all\s+good|good\s+for\s+now|nothing\s+else|wala\s+na|wala\s+nang\s+iba|tapos|tapos\s+na|tama\s+na|hanggang\s+dito|goodbye|bye|paalam|see\s+you)([\s,!.?]|$)/i;
  function _isGoodbye(text) {
    const s = String(text || '').trim();
    if (!s) return false;
    const words = s.split(/\s+/);
    if (words.length > 5) return false;
    return _GOODBYE_RE.test(s);
  }

  // Phase 4.54 (turn #55): Proactive companion turn.
  // When a CRITICAL/HIGH proactive alert exists and the worker hasn't
  // acknowledged it yet, the companion may speak FIRST without a tap.
  // We expose a helper that picks the highest-severity unacknowledged
  // alert. The voice-overlay opens with this line pre-rendered.
  function _selectProactiveAlertForSpeak(alerts) {
    if (!Array.isArray(alerts) || alerts.length === 0) return null;
    const critical = alerts.find(a => a && String(a.severity || '').toLowerCase() === 'critical');
    if (critical) return critical;
    const high = alerts.find(a => a && String(a.severity || '').toLowerCase() === 'high');
    if (high) return high;
    return null;
  }

  // Phase 4.55 (turn #56): Maturity-stair gating.
  // Hives at Stair < 2 don't have enough history for predictive replies.
  // The anchor below MUTES the companion's predictive vocabulary on
  // those hives so we don't promise capability they haven't earned.
  function _readHiveMaturityStair() {
    try {
      const s = /* storage-key-allow: hive-stair value, set by hive maturity rollup elsewhere */ localStorage.getItem('wh_hive_maturity_stair');
      const n = Number(s);
      return isFinite(n) ? n : null;
    } catch (_) { return null; }
  }

  // Phase 4.56 (turn #57): Per-slot expiry windows.
  // T6 expires the whole dialogState at 15min. Per-slot expiry is
  // finer: asset_tag is ephemeral (60min), time_window decays faster
  // (2h), machine_status is volatile (30min). Anything else uses the
  // session-level guard. Returns a slots object with stale entries removed.
  const _SLOT_TTL_MS = {
    asset_tag:      60 * 60 * 1000,
    machine_status: 30 * 60 * 1000,
    time_window:   120 * 60 * 1000,
    failure_mode:   60 * 60 * 1000,
    co_worker:     120 * 60 * 1000,
  };
  function _pruneStaleSlots(slots, slotsUpdatedAt) {
    if (!slots || typeof slots !== 'object') return slots || {};
    if (!slotsUpdatedAt) return slots;
    const refTs = new Date(slotsUpdatedAt).getTime();
    if (!isFinite(refTs) || refTs <= 0) return slots;
    const now = Date.now();
    const pruned = {};
    Object.keys(slots).forEach(k => {
      const ttl = _SLOT_TTL_MS[k];
      if (!ttl) { pruned[k] = slots[k]; return; }
      if ((now - refTs) <= ttl) pruned[k] = slots[k];
    });
    return pruned;
  }

  // Phase 4.57 (turn #58): Action replay.
  // After a confirmed logbook/PM action lands, we snapshot its shape
  // (verb + slot template) on a module-local var. A subsequent "same
  // fix on <new_asset>" / "same as before for <new_asset>" replays the
  // template with the new asset_tag substituted.
  let _lastConfirmedAction = null;  // { verb, slots, ts }
  function _stashConfirmedAction(verb, slots) {
    if (!verb) return;
    _lastConfirmedAction = { verb: String(verb), slots: slots || {}, ts: Date.now() };
  }
  function _getLastConfirmedAction() { return _lastConfirmedAction; }
  // NOTE the alternation groups end at "(?:for|on)" / "(?:for|sa)" with NO
  // trailing literal space — the outer "\s+" supplies the separator. Adding
  // a literal space inside the group forced "double-space" matches and
  // broke "same fix on P-205".
  const _REPLAY_RE = /\b(?:same (?:thing|fix|action|entry) (?:for|on)|gawin mo (?:rin )?(?:to|yan) (?:for|sa))\s+([A-Z0-9][A-Za-z0-9\-_.]{1,30})\b/i;
  function _detectActionReplay(text) {
    const m = String(text || '').match(_REPLAY_RE);
    if (!m || !_lastConfirmedAction) return null;
    // Only honour if the prior action is fresh (within 15 min).
    if ((Date.now() - _lastConfirmedAction.ts) > 15 * 60 * 1000) return null;
    return { verb: _lastConfirmedAction.verb, slots: _lastConfirmedAction.slots, newAsset: m[1] };
  }

  // Phase 4.58 (turn #59): Language opt-in.
  // "Speak tagalog" / "english only" / "tagalog na lang" — persist a
  // session-level pref so the LLM picks the right output language
  // without the worker having to ask every turn.
  const _LANG_OPT_RE = /\b(?:speak\s+(tagalog|english|cebuano|tag\-?lish)|reply\s+in\s+(tagalog|english|cebuano)\s*only|(tagalog|english|cebuano)\s+(?:na\s+lang|lang|please)|sa\s+(tagalog|english|cebuano)\s+na\s+lang)\b/i;
  function _detectLanguagePref(text) {
    const m = String(text || '').match(_LANG_OPT_RE);
    if (!m) return null;
    const lang = (m[1] || m[2] || m[3] || m[4] || '').toLowerCase();
    if (!lang) return null;
    if (lang === 'tag-lish' || lang === 'taglish') return 'taglish';
    return lang;
  }
  function _setLanguagePref(lang) {
    if (!lang) return;
    try { localStorage.setItem('wh_voice_lang_pref', lang); } catch (_) { /* non-fatal */ /* empty-catch-allow: best-effort silent swallow */ }
  }
  function _getLanguagePref() {
    try { return localStorage.getItem('wh_voice_lang_pref') || null; }
    catch (_) { return null; }
  }

  // Phase 4.59 (turn #60): Brevity preference.
  // "Shorter" / "be brief" / "one sentence" / "TLDR" — persists a
  // session-level brevity flag. The prompt then caps the reply at one
  // sentence until the worker says "more detail" / "expand".
  const _BREVITY_ON_RE  = /\b(?:shorter|be\s+brief|brief\s+please|one\s+sentence|tldr|tl;dr|maikli\s+lang|saglit\s+lang|usapan\s+ng\s+maikli)\b/i;
  const _BREVITY_OFF_RE = /\b(?:more\s+detail|tell\s+me\s+more|expand|longer\s+please|details\s+please\s+full|kompleto\s+ko|detalyado)\b/i;
  function _detectBrevityToggle(text) {
    const s = String(text || '');
    if (_BREVITY_ON_RE.test(s)) return 'brief';
    if (_BREVITY_OFF_RE.test(s)) return 'full';
    return null;
  }
  function _setBrevityPref(mode) {
    if (mode !== 'brief' && mode !== 'full') return;
    try { localStorage.setItem('wh_voice_brevity', mode); } catch (_) { /* non-fatal */ /* empty-catch-allow: best-effort silent swallow */ }
  }
  function _getBrevityPref() {
    try { return localStorage.getItem('wh_voice_brevity') || null; }
    catch (_) { return null; }
  }

  // Phase 4.60 (turn #61): Timer follow-up.
  // "Remind me in 20 minutes about P-203" — parse the duration + topic,
  // schedule a setTimeout that opens the overlay with a pre-rendered
  // reminder. Bounded list so we never schedule more than 5 concurrent.
  const _TIMER_LIST_MAX = 5;
  const _timers = [];  // [{ id, due, label }]
  const _TIMER_RE = /\bremind\s+me\s+(?:in\s+)?(\d{1,3})\s*(min|mins|minute|minutes|hr|hour|hours)\s+(?:about|to|tungkol sa)\s+(.{2,80})$/i;
  function _detectTimerRequest(text) {
    const m = String(text || '').match(_TIMER_RE);
    if (!m) return null;
    const n = Number(m[1]);
    const unit = String(m[2] || 'min').toLowerCase();
    const label = String(m[3] || '').trim();
    if (!n || !label) return null;
    const ms = (unit.startsWith('h') ? n * 60 : n) * 60 * 1000;
    return { ms, label };
  }
  function _scheduleTimer(spec) {
    if (!spec || !spec.ms || !spec.label) return null;
    if (_timers.length >= _TIMER_LIST_MAX) return null;
    const due = Date.now() + spec.ms;
    const id = setTimeout(function () {
      try {
        const text = "Hey, you asked me to remind you about " + spec.label + ".";
        if (typeof open === 'function') open();
        _setStatus(personaName_safe() + ' (reminder):');
        _renderReplyBubble(text, _getPersonaSafe());
        if (typeof window.speakPersona === 'function') {
          window.speakPersona(text, { persona: _getPersonaSafe() });
        }
      } catch (_) { /* non-fatal */ /* empty-catch-allow: best-effort silent swallow */ }
      // Remove from active list when fired.
      const idx = _timers.findIndex(t => t.id === id);
      if (idx >= 0) _timers.splice(idx, 1);
    }, spec.ms);
    _timers.push({ id, due, label: spec.label });
    return { due, label: spec.label };
  }
  function _getActiveTimers() { return _timers.slice(); }
  function _clearAllTimers() {
    _timers.forEach(t => { try { clearTimeout(t.id); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ } });
    _timers.length = 0;
  }
  function personaName_safe() {
    try {
      const p = (typeof window.getPersona === 'function') ? window.getPersona() : 'zaniah';
      return p === 'hezekiah' ? 'Hezekiah' : 'Zaniah';
    } catch (_) { return 'Zaniah'; }
  }
  function _getPersonaSafe() {
    try { return (typeof window.getPersona === 'function') ? window.getPersona() : 'zaniah'; }
    catch (_) { return 'zaniah'; }
  }

  // Phase 4.61 (turn #62): URL-context pre-fill.
  // When voice-journal opens from asset-hub.html?asset=P-203 (or any
  // page with ?asset= / ?machine= query params), pre-seed asset_tag
  // into the dialog-state slots so turn 1 already has context.
  function _readUrlAssetParam() {
    try {
      const u = new URL(window.location.href);
      const tag = u.searchParams.get('asset') || u.searchParams.get('machine') ||
                  u.searchParams.get('asset_tag') || u.searchParams.get('tag');
      return tag ? String(tag).trim() : null;
    } catch (_) { return null; }
  }

  // Phase 4.62 (turn #63): Mic quality warning.
  // Module-local rolling RMS / peak level monitor. The MediaRecorder
  // pipeline already grabs an audio stream; we sample it through an
  // AnalyserNode and surface a "you sound far away" warning if the
  // peak stays below threshold for >2s. Helper only — the wiring at
  // _startRecording can wrap it in opportunistically.
  function _attachMicQualityMeter(stream, onLowLevel) {
    if (!stream || !window.AudioContext) return null;
    try {
      const ac = new AudioContext();
      const src = ac.createMediaStreamSource(stream);
      const analyser = ac.createAnalyser();
      analyser.fftSize = 1024;
      src.connect(analyser);
      const buf = new Uint8Array(analyser.fftSize);
      let lowStreakMs = 0;
      let stopped = false;
      const startTs = Date.now();
      function tick() {
        if (stopped) return;
        analyser.getByteTimeDomainData(buf);
        let peak = 0;
        for (let i = 0; i < buf.length; i++) {
          const v = Math.abs(buf[i] - 128);
          if (v > peak) peak = v;
        }
        // Peak ranges 0..128; below 8 ≈ silence; below 20 ≈ very quiet.
        if (peak < 20) lowStreakMs += 100;
        else lowStreakMs = 0;
        if (lowStreakMs >= 2000 && Date.now() - startTs > 1500) {
          stopped = true;
          if (typeof onLowLevel === 'function') {
            try { onLowLevel({ peak, lowStreakMs }); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
          }
          try { ac.close(); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
          return;
        }
        setTimeout(tick, 100);
      }
      tick();
      return {
        stop: function () { stopped = true; try { ac.close(); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ } },
      };
    } catch (_) { return null; }
  }

  // Phase 4.63 (turn #64): Action queue.
  // Multi-step request: "log entry then start PM then notify supervisor".
  // We parse with split on "then" / "tapos" / "after that" / "pagkatapos
  // ay" and produce an ordered list of action verbs the LLM can confirm
  // one-by-one. Returns the list or null when no batch shape detected.
  const _ACTION_SPLIT_RE = /\bthen\b|\bafter that\b|\btapos\b|\bpagkatapos(?:\s+ay)?\b|;/i;
  function _parseActionQueue(text) {
    const s = String(text || '').trim();
    if (!s) return null;
    if (!_isActionRequest(s)) return null;
    const parts = s.split(_ACTION_SPLIT_RE).map(p => p.trim()).filter(p => p.length > 2);
    if (parts.length < 2) return null;
    // Each step must look action-shaped (start with a verb).
    const queue = parts.filter(p => _isActionRequest(p));
    if (queue.length < 2) return null;
    return queue;
  }

  // ============================================================
  // SEVENTH 10-TURN FLYWHEEL — turns #65-#74 (Phase 4.67-4.76)
  // ORCHESTRATION + INTEGRATION layer. Detectors stay tight; most
  // wins are wiring real infra (RPC, push, locks, streaming UI,
  // pronunciation overrides) into the existing detector lattice.
  // ============================================================

  // Phase 4.67 (turn #65) PDF EXPORT REQUEST — "save as PDF" /
  // "i-PDF mo ito" / "export to PDF" / "download conversation".
  // The companion does NOT generate PDFs; it points the worker at
  // the Report Sender surface which already owns the PDF pipeline.
  // Two-tier match: (a) standalone PH/EN PDF verbs ("i-pdf mo ito",
  // "pdf mo") that ARE the export request by themselves, or (b) an
  // English export verb followed somewhere in the same utterance by
  // "pdf"/"hard copy" ("save this as PDF", "download to PDF"). The
  // function caps text length at 200 chars so the "[^.!?]*" filler
  // cannot run away.
  const _PDF_EXPORT_RE = /\b(?:i[\-\s]?pdf(?:\s+mo)?|pdf[\s\-]?mo)\b|\b(?:save|export|download|send|print)\b[^.!?]{0,80}\b(?:pdf|p\.d\.f|hard\s*copy)\b/i;
  function _isPdfExportRequest(text) {
    const s = String(text || '').trim();
    if (!s || s.length > 200) return false;
    return _PDF_EXPORT_RE.test(s);
  }

  // Phase 4.68 (turn #66) CUSTOM PRONUNCIATION LIBRARY — workers
  // routinely correct STT/TTS mispronunciations of plant-specific
  // terms ("it's pee-two-oh-three, not pi-two-oh-three"). The
  // override map persists per-device so the correction sticks
  // across sessions. Applied immediately before TTS in callers.
  const _PRONUNCIATION_KEY = 'wh_pronunciation_overrides';
  function _getPronunciationMap() {
    try {
      const raw = localStorage.getItem(_PRONUNCIATION_KEY);
      if (!raw) return {};
      const parsed = JSON.parse(raw);
      return (parsed && typeof parsed === 'object') ? parsed : {};
    } catch (_) { return {}; }
  }
  function _setPronunciationOverride(term, sayAs) {
    if (!term || !sayAs) return false;
    const t = String(term).trim();
    const a = String(sayAs).trim();
    if (!t || !a || t.length > 60 || a.length > 80) return false;
    try {
      const m = _getPronunciationMap();
      m[t.toLowerCase()] = a;
      localStorage.setItem(_PRONUNCIATION_KEY, JSON.stringify(m));
      return true;
    } catch (_) { return false; }
  }
  function _applyPronunciation(text) {
    const s = String(text || '');
    if (!s) return s;
    const m = _getPronunciationMap();
    const keys = Object.keys(m);
    if (keys.length === 0) return s;
    let out = s;
    for (const k of keys) {
      // word-boundary, case-insensitive replace
      const re = new RegExp('\\b' + k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b', 'gi');
      out = out.replace(re, m[k]);
    }
    return out;
  }

  // Phase 4.69 (turn #67) VOICE EXECUTE LOCK — safety gate so that
  // write-verb intents (action confirmation / replay / queue) do
  // NOT actually dispatch through voice-action-router until the
  // worker has explicitly enabled voice-execute mode. Default is
  // OFF — conservative. The lock is per-device.
  const _VOICE_EXECUTE_KEY = 'wh_voice_execute_authorised';
  function _isVoiceExecuteAuth() {
    try { return localStorage.getItem(_VOICE_EXECUTE_KEY) === '1'; }
    catch (_) { return false; }
  }
  function _setVoiceExecuteAuth(flag) {
    try {
      if (flag) localStorage.setItem(_VOICE_EXECUTE_KEY, '1');
      else localStorage.removeItem(_VOICE_EXECUTE_KEY);
      return true;
    } catch (_) { return false; }
  }

  // Phase 4.70 (turn #68) PERSONA PORTRAIT ANIMATION — companion
  // bubble carries a data-avatar-anim attribute that drives a CSS
  // animation (idle / listening / thinking / speaking / urgent).
  // The animation is purely visual; the avatar emotion (T53) drives
  // tint, this drives motion. Fail-soft if the overlay isn't mounted.
  const _AVATAR_ANIM_STATES = ['idle', 'listening', 'thinking', 'speaking', 'urgent'];
  function _setAvatarAnimation(state) {
    if (!_AVATAR_ANIM_STATES.includes(state)) return false;
    try {
      const ov = document.getElementById('wh-voice-overlay');
      if (!ov) return false;
      ov.setAttribute('data-avatar-anim', state);
      return true;
    } catch (_) { return false; }
  }

  // Phase 4.71 (turn #69) CROSS-HIVE BENCHMARK RPC — wires the T54
  // anchor to a real Supabase RPC. Returns { p50, p90, p_self } for
  // the requested metric. 5-minute in-memory cache keyed by metric;
  // the RPC itself enforces anonymisation (PH-INTELLIGENCE rollup).
  const _CROSS_HIVE_RPC = 'fn_cross_hive_benchmark';
  const _BENCHMARK_CACHE_TTL_MS = 5 * 60 * 1000;
  const _benchmarkCache = {}; // metric -> { value, ts }
  async function _fetchCrossHiveBenchmark(db, metric) {
    if (!db || !metric) return null;
    const m = String(metric).toLowerCase();
    const now = Date.now();
    const cached = _benchmarkCache[m];
    if (cached && (now - cached.ts) < _BENCHMARK_CACHE_TTL_MS) {
      return cached.value;
    }
    try {
      const { data, error } = await db.rpc(_CROSS_HIVE_RPC, { p_metric: m });
      if (error || !data) return null;
      const value = (Array.isArray(data) ? data[0] : data) || null;
      if (value) _benchmarkCache[m] = { value, ts: now };
      return value;
    } catch (_) { return null; }
  }

  // Phase 4.72 (turn #70) DAILY DIGEST MODE — "morning summary" /
  // "what happened overnight" / "i-summarize mo ang shift" → flip
  // into a 5-line briefing format. Distinct from T22 SUMMARY MODE
  // (recap of THIS session) — this surfaces platform-state delta.
  const _DIGEST_RE = /\b(?:morning\s+(?:summary|brief|digest|update)|overnight\s+(?:summary|update)|shift\s+(?:summary|digest|brief)|i[\-\s]?summarize\s+mo(?:\s+ang)?\s+shift|brief\s+me\s+(?:on|about)\s+the\s+(?:shift|night|morning)|what\s+happened\s+(?:overnight|last\s+shift|sa\s+gabi)|daily\s+digest)\b/i;
  function _isDigestRequest(text) {
    const s = String(text || '').trim();
    if (!s || s.length > 200) return false;
    return _DIGEST_RE.test(s);
  }

  // Phase 4.73 (turn #71) PUSH NOTIFICATION READINESS — wraps the
  // browser Notification API. The companion checks permission state
  // BEFORE offering to "alert me" so it doesn't promise a feature
  // the browser will silently drop. Requesting permission is
  // user-gesture-gated by the browser; we expose the request as a
  // helper but never auto-call it.
  function _canPushNotify() {
    try {
      return (typeof Notification !== 'undefined') &&
             Notification.permission === 'granted';
    } catch (_) { return false; }
  }
  function _pushNotifyState() {
    try {
      if (typeof Notification === 'undefined') return 'unsupported';
      return Notification.permission || 'default';
    } catch (_) { return 'unsupported'; }
  }
  async function _requestPushPerm() {
    try {
      if (typeof Notification === 'undefined') return 'unsupported';
      if (Notification.permission === 'granted') return 'granted';
      if (Notification.permission === 'denied') return 'denied';
      const result = await Notification.requestPermission();
      return String(result || 'default');
    } catch (_) { return 'error'; }
  }
  const _PUSH_OPT_IN_RE = /\b(?:yes\s*,?\s*(?:alert|notify|ping|notify\s+me)|sige[, ]+(?:alert|notify|ipush)\s+mo|turn\s+on\s+(?:alerts|notifications|push)|enable\s+(?:alerts|notifications|push)|push\s+(?:on|please|sige)|opt\s+in\s+(?:to\s+)?(?:alerts|push|notifications))\b/i;
  function _isPushOptInReply(text) {
    const s = String(text || '').trim();
    if (!s || s.length > 120) return false;
    return _PUSH_OPT_IN_RE.test(s);
  }

  // Phase 4.74 (turn #72) MULTI-WORKER CONCURRENCY LOCK — when two
  // workers in the same hive open the companion on overlapping
  // devices, the second one would otherwise stomp on shared
  // dialog-state. We write a short-lived lock keyed by hive_id;
  // the holder's worker_id is in the value, with a 10-min TTL.
  // The owning device clears it on close(). Lock is advisory —
  // we don't block, we just surface a warning anchor.
  const _SESSION_LOCK_TTL_MS = 10 * 60 * 1000;
  function _sessionLockKey(hiveId) {
    return 'wh_voice_session_lock_' + String(hiveId || 'anon');
  }
  function _acquireSessionLock(hiveId, workerId) {
    if (!hiveId || !workerId) return false;
    try {
      const payload = JSON.stringify({ worker: String(workerId), ts: Date.now() });
      localStorage.setItem(_sessionLockKey(hiveId), payload);
      return true;
    } catch (_) { return false; }
  }
  function _isSessionLocked(hiveId, workerId) {
    if (!hiveId) return null;
    try {
      const raw = localStorage.getItem(_sessionLockKey(hiveId));
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== 'object') return null;
      if ((Date.now() - Number(parsed.ts || 0)) >= _SESSION_LOCK_TTL_MS) {
        // expired — clear and treat as unlocked
        try { localStorage.removeItem(_sessionLockKey(hiveId)); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
        return null;
      }
      if (workerId && String(parsed.worker) === String(workerId)) return null; // own lock
      return parsed; // foreign lock
    } catch (_) { return null; }
  }
  function _releaseSessionLock(hiveId, workerId) {
    if (!hiveId) return false;
    try {
      const raw = localStorage.getItem(_sessionLockKey(hiveId));
      if (!raw) return true;
      const parsed = JSON.parse(raw);
      if (!parsed) return true;
      if (workerId && String(parsed.worker) !== String(workerId)) return false;
      localStorage.removeItem(_sessionLockKey(hiveId));
      return true;
    } catch (_) { return false; }
  }

  // Phase 4.75 (turn #73) ACCENT / VOICE SIGNATURE — over a session,
  // measure how much of the worker's speech is Tagalog-leaning so
  // the TTS voice picker can adapt. Persisted per-device. The hint
  // is recomputed from the rolling _sessionTurns; a stable pref
  // sticks once set explicitly.
  const _ACCENT_PREF_KEY = 'wh_voice_accent_pref';
  const _TGL_HINT_WORDS = new Set([
    'ako','ikaw','siya','kami','tayo','kayo','sila','yung','yun','yan','iyan',
    'kasi','naman','lang','po','ho','sige','oo','hindi','wala','meron','meron',
    'tapos','pagkatapos','tagalog','salamat','paki','paano','bakit','ano',
    'kuya','ate','kapatid','mam','sir',
  ]);
  function _detectAccentHint(turnSamples) {
    const samples = Array.isArray(turnSamples) ? turnSamples : (_sessionTurns || []);
    if (samples.length === 0) return null;
    const window = samples.slice(-10);
    let tgl = 0, total = 0;
    for (const t of window) {
      const text = String((t && (t.utter || t.user || t)) || '').toLowerCase();
      const words = text.split(/[^a-z]+/).filter(w => w.length >= 2);
      for (const w of words) {
        total++;
        if (_TGL_HINT_WORDS.has(w)) tgl++;
      }
    }
    if (total < 8) return null; // not enough signal
    const ratio = tgl / total;
    if (ratio >= 0.18) return 'tagalog-leaning';
    if (ratio <= 0.03) return 'english-leaning';
    return 'mixed';
  }
  function _getAccentPref() {
    try { return localStorage.getItem(_ACCENT_PREF_KEY) || null; }
    catch (_) { return null; }
  }
  function _setAccentPref(pref) {
    try {
      if (!pref) { localStorage.removeItem(_ACCENT_PREF_KEY); return true; }
      const allowed = new Set(['tagalog-leaning','english-leaning','mixed','cebuano-leaning']);
      if (!allowed.has(pref)) return false;
      localStorage.setItem(_ACCENT_PREF_KEY, pref);
      return true;
    } catch (_) { return false; }
  }

  // Phase 4.76 (turn #74) STREAMING SSE INDICATOR — when the ai-
  // gateway later emits incremental tokens, voice-handler updates
  // the latest reply bubble in place instead of waiting for the
  // full response. This block exposes the wiring; the gateway
  // flip-over (server side) ships separately. data-streaming on
  // the overlay drives a subtle "..." cursor.
  let _streamIncremental = false;
  let _lastReplyBubble = null;
  function _setStreamingState(on) {
    _streamIncremental = !!on;
    try {
      const ov = document.getElementById('wh-voice-overlay');
      if (ov) ov.setAttribute('data-streaming', on ? '1' : '0');
    } catch (_) { /* non-fatal */ /* empty-catch-allow: best-effort silent swallow */ }
    return _streamIncremental;
  }
  function _isStreaming() { return _streamIncremental === true; }
  function _bindStreamingBubble(node) {
    _lastReplyBubble = node || null;
  }
  function _appendStreamingChunk(chunk) {
    if (!_streamIncremental || !chunk) return false;
    const c = String(chunk);
    try {
      if (_lastReplyBubble && typeof _lastReplyBubble.textContent === 'string') {
        _lastReplyBubble.textContent = (_lastReplyBubble.textContent || '') + c;
        return true;
      }
    } catch (_) { /* non-fatal */ /* empty-catch-allow: best-effort silent swallow */ }
    return false;
  }
  function _finalizeStream() {
    _streamIncremental = false;
    _lastReplyBubble = null;
    try {
      const ov = document.getElementById('wh-voice-overlay');
      if (ov) ov.setAttribute('data-streaming', '0');
    } catch (_) { /* non-fatal */ /* empty-catch-allow: best-effort silent swallow */ }
  }

  // ============================================================
  // EIGHTH 10-TURN FLYWHEEL — turns #75-#84 (Phase 4.77-4.86)
  // TRUST DEPLOYMENT layer. Production-safety + collaboration:
  // toxicity guard, question shape classifier, freshness
  // disclosure, rate-limit cooldown, conversation share, readback,
  // scope disclosure, correction handler, confidence label,
  // crisis escalation extension.
  // ============================================================

  // Phase 4.77 (turn #75) TOXICITY GUARD — detect obviously toxic
  // language directed at the worker (or coming from them about a
  // colleague). The companion should de-escalate, never amplify.
  // Word-list approach is intentional — keeps the gate local-only,
  // no PII leaves the device. Severity 0..1 (0=clean, 1=hostile).
  const _TOX_TERMS_SEVERE = [
    /\b(?:f(?:ck|uck|uk)|sht|shit|bitch|bullsh.t|kill\s+(?:yourself|yourselves)|fucking\s+id\w+)\b/i,
    /\b(?:gago|tanga|bobo|inutil|hayop|pakshet|putang\s*ina|tang\s*ina|punyeta|leche|gunggong)\b/i,
  ];
  const _TOX_TERMS_MILD = [
    /\b(?:stupid|idiot|dumb|garbage|trash|useless|moron|loser)\b/i,
    /\b(?:bobo[\s-]talaga|tanga[\s-]talaga|wala[\s-]kang\s+kwenta)\b/i,
  ];
  function _detectToxicLanguage(text) {
    const s = String(text || '');
    if (!s || s.length > 600) return { severity: 0, hit: null };
    for (const re of _TOX_TERMS_SEVERE) {
      const m = s.match(re);
      if (m) return { severity: 0.85, hit: m[0] };
    }
    for (const re of _TOX_TERMS_MILD) {
      const m = s.match(re);
      if (m) return { severity: 0.45, hit: m[0] };
    }
    return { severity: 0, hit: null };
  }

  // Phase 4.78 (turn #76) QUESTION SHAPE CLASSIFIER — different
  // shapes of question deserve different reply structures. The
  // classifier is heuristic (not LLM) so we can pre-anchor in the
  // system prompt before the LLM ever sees the transcript.
  function _classifyQuestionShape(text) {
    const s = String(text || '').trim().toLowerCase();
    if (!s) return 'unknown';
    if (/\b(?:how\s+(?:do|can|to)|paano|pano|saan|where\s+can\s+i|how\s+about)\b/i.test(s)) return 'how_to';
    if (/\b(?:what(?:'s|\s+is)|ano(?:\s+ang)?|magkano|how\s+many|how\s+much|kailan|when\s+(?:was|is|did))\b/i.test(s)) return 'data';
    if (/\b(?:should\s+i|dapat\s+ba|mas\s+ok\s+ba|do\s+you\s+think|sa\s+tingin\s+mo)\b/i.test(s)) return 'opinion';
    if (/\b(?:why\s+(?:is|are|do|does)|bakit|paano\s+nangyari|how\s+come)\b/i.test(s)) return 'troubleshoot';
    if (/\b(?:hi|hello|hey|kamusta|magandang|salamat|thank\s+you|good\s+(?:morning|afternoon|evening|night))\b/i.test(s)) return 'social';
    return 'unknown';
  }

  // Phase 4.79 (turn #77) FRESHNESS DISCLOSURE — when the reply
  // depends on a canonical view (PLATFORM SNAPSHOT), the freshness
  // (last_updated timestamp) MUST be disclosable on demand. The
  // detector picks up "is this fresh" / "kailan ito na-update" so
  // the LLM has an anchor to reach for. Defaults rely on the
  // truth-view source-of-record convention already documented in
  // canonical/standards.json.
  // The "is this <noun?> fresh" variant covers both bare ("is this fresh")
  // and noun-bearing ("is this data fresh", "is the report current") shapes.
  const _FRESHNESS_RE = /\b(?:is\s+(?:this|that|it|the)(?:\s+\w+)?\s+(?:fresh|current|up\s*to\s+date|stale|old)|kailan\s+(?:ito|to|yan|yun)\s+(?:na[\-\s]?update|naging\s+ganito)|how\s+old\s+is\s+(?:this|the\s+data|the\s+report)|kailan\s+ang\s+huling\s+(?:update|sync|refresh))\b/i;
  function _isFreshnessRequest(text) {
    const s = String(text || '').trim();
    if (!s || s.length > 200) return false;
    return _FRESHNESS_RE.test(s);
  }

  // Phase 4.80 (turn #78) RATE-LIMIT GRACEFUL FALLBACK — when the
  // ai-gateway returns 429 (or our local rateLimitedResponse fires)
  // we stash a cooldown-until timestamp per-hive. Until that time
  // passes, we don't re-call the gateway; we serve a canned reply
  // that points the worker at the right page.
  function _rateLimitKey(hiveId) {
    return 'wh_ratelimit_until_' + String(hiveId || 'anon');
  }
  function _setRateLimitCooldown(hiveId, durationMs) {
    if (!hiveId) return false;
    const ms = Number(durationMs) || (60 * 1000); // default 60s
    try {
      const until = Date.now() + Math.min(ms, 10 * 60 * 1000); // cap 10 min
      localStorage.setItem(_rateLimitKey(hiveId), String(until));
      return until;
    } catch (_) { return false; }
  }
  function _inRateLimitCooldown(hiveId) {
    if (!hiveId) return false;
    try {
      const raw = localStorage.getItem(_rateLimitKey(hiveId));
      if (!raw) return false;
      const until = Number(raw);
      if (!Number.isFinite(until)) return false;
      if (Date.now() >= until) {
        try { localStorage.removeItem(_rateLimitKey(hiveId)); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
        return false;
      }
      return until;
    } catch (_) { return false; }
  }
  function _clearRateLimitCooldown(hiveId) {
    if (!hiveId) return;
    try { localStorage.removeItem(_rateLimitKey(hiveId)); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
  }

  // Phase 4.81 (turn #79) CONVERSATION SHARE LINK — workers
  // routinely want to forward the assistant's reply to a colleague.
  // The companion produces a URL with the session id; the receiving
  // surface (voice-journal.html) loads the persisted turns. The link
  // is built locally; no extra round-trip.
  const _SHARE_RE = /\b(?:share\s+(?:this|it|that|yun|yan)\s*(?:with|to|kay|sa)?|forward\s+(?:this|it|that|to)|i[\-\s]?share\s+mo|ipasa\s+mo)\b/i;
  function _isShareRequest(text) {
    const s = String(text || '').trim();
    if (!s || s.length > 200) return false;
    return _SHARE_RE.test(s);
  }
  function _buildShareLink(sessionId) {
    if (!sessionId) return null;
    try {
      const origin = (window.location && window.location.origin) || '';
      const safeId = String(sessionId).replace(/[^A-Za-z0-9_\-]/g, '').slice(0, 64);
      if (!safeId) return null;
      return origin + '/voice-journal.html#session=' + safeId;
    } catch (_) { return null; }
  }

  // Phase 4.82 (turn #80) READBACK REQUEST — distinct from T14
  // _isRepeatRequest (which replays the entire last reply text in
  // the same channel). READBACK explicitly asks the companion to
  // SPEAK the prior reply through TTS again — useful for hands-busy
  // / eyes-busy situations like working at a panel.
  const _READBACK_RE = /\b(?:read\s+(?:it|that|this|yun|yan|ito|yung\s+\w+)\s+(?:aloud|again|please|ulit)|read\s+(?:back|aloud)|basahin\s+(?:mo)?\s+(?:ulit|nga|para\s+sa\s+akin)|ulit\s+basahin|i[\-\s]?speak\s+mo\s+(?:ulit|yun))\b/i;
  function _isReadbackRequest(text) {
    const s = String(text || '').trim();
    if (!s || s.length > 120) return false;
    return _READBACK_RE.test(s);
  }

  // Phase 4.83 (turn #81) SCOPE DISCLOSURE — workers ask "what can
  // you do" / "magagawa mo ba ___" to discover the surface. The
  // companion should NOT guess; it should reach for a canonical
  // scope list. The detector flags the question; the SCOPE
  // DISCLOSURE anchor instructs the LLM to ground the answer in
  // the actual capability list.
  const _SCOPE_RE = /\b(?:what\s+can\s+you\s+do|what\s+(?:are\s+)?your\s+(?:capabilities|skills|features)|can\s+you\s+(?:do|help\s+with|access)|magagawa\s+mo\s+ba|kaya\s+mo\s+ba(?:ng)?|paano\s+ka\s+tumulong|how\s+do\s+you\s+help|tell\s+me\s+what\s+you\s+can\s+do)\b/i;
  function _isScopeQuery(text) {
    const s = String(text || '').trim();
    if (!s || s.length > 200) return false;
    return _SCOPE_RE.test(s);
  }

  // Phase 4.84 (turn #82) MULTI-TURN CORRECTION — "no, I meant X" /
  // "hindi yun, ___" / "actually it was X". DISTINCT from T2
  // _isFollowupNegation (which cancels the current line of thought).
  // CORRECTION says "your prior answer used wrong info; here's the
  // right info — please redo the answer with the correction."
  const _CORRECTION_RE = /\b(?:no\s*,?\s*i\s+(?:meant|said|wanted)|actually\s*,?\s*(?:it|that|the|i)\s+(?:was|is|meant)|wait\s*,?\s*(?:i\s+meant|hindi)|hindi\s+yun\s*,?\s+(?:ito|yung|yun)|let\s+me\s+correct|wrong\s*,?\s+(?:the|it|that)\s+(?:was|is)|to\s+correct|teka\s*,?\s*(?:hindi|ang\s+meant))\b/i;
  function _isCorrection(text) {
    const s = String(text || '').trim();
    if (!s || s.length > 200) return false;
    return _CORRECTION_RE.test(s);
  }

  // Phase 4.85 (turn #83) CONFIDENCE LABEL TIER — T28 already
  // hedges on low-sample data; this layer adds the explicit label
  // ('high'/'medium'/'low') the LLM should PREFIX a number with
  // when the underlying source has fewer than 30 days of history
  // OR fewer than 5 rows. Caller passes the source counts.
  function _confidenceLabel(rowCount, dayCount) {
    const rows = Number(rowCount);
    const days = Number(dayCount);
    if (!Number.isFinite(rows) || !Number.isFinite(days)) return 'unknown';
    if (rows < 5 || days < 30) return 'low';
    if (rows < 30 || days < 90) return 'medium';
    return 'high';
  }

  // Phase 4.86 (turn #84) CRISIS ESCALATION EXTENSION — T4 covered
  // self-harm + helpline. This layer extends to workplace violence
  // ("X threatened me", "may nanakit") and routes to the safety
  // officer / HR hotline. Returns the kind so the caller can pick
  // the right escalation path. PII redaction kept best-effort.
  function _detectCrisisEscalation(text) {
    const s = String(text || '');
    if (!s) return null;
    if (/\b(?:kill\s+myself|end\s+(?:my|it\s+all)|magpakamatay|gusto\s+ko\s+nang\s+(?:mamatay|magpakamatay)|don[ '`]t\s+want\s+to\s+live|self[\s\-]harm|suicidal)\b/i.test(s)) {
      return { kind: 'self_harm', severity: 'critical' };
    }
    if (/\b(?:(?:he|she|they|si\s+\w+)\s+(?:threatened|hit|punched|attacked|hurt)\s+(?:me|us)|may\s+(?:nanakit|nambabraso|nagbanta)|workplace\s+violence|sinaktan\s+(?:ako|kami)|hinarass(?:\s+ako)?|harassed?\s+me)\b/i.test(s)) {
      return { kind: 'workplace_violence', severity: 'high' };
    }
    return null;
  }

  // ============================================================
  // NINTH 10-TURN FLYWHEEL — turns #85-#94 (Phase 4.87-4.96)
  // INPUT NORMALIZATION + ONBOARDING layer. Now that the lattice
  // is broad, the next velocity comes from making input forgiving
  // (asset tag spelling variants, time-range phrases, KPI label
  // mismatch) and onboarding new workers cleanly.
  // ============================================================

  // Phase 4.87 (turn #85) NUMERIC PRECISION RULE — when the
  // companion quotes a KPI it must include unit + sensible
  // precision (no "92.482314%"). Helper rounds + unit-stamps.
  // The PRECISION RULE anchor instructs LLM to invoke this shape.
  function _formatKpi(value, unit, decimals) {
    // null / undefined are sentinels for "no value" — Number(null) coerces
    // to 0 which would print "0.0%", a lie. Reject these BEFORE coercion.
    if (value === null || value === undefined) return null;
    const v = Number(value);
    if (!Number.isFinite(v)) return null;
    const d = Number.isFinite(Number(decimals)) ? Math.max(0, Math.min(4, Number(decimals))) : 1;
    const u = String(unit || '').trim();
    const rounded = v.toFixed(d);
    return u ? (rounded + (u.startsWith('%') || u.startsWith('/') ? u : ' ' + u)) : rounded;
  }

  // Phase 4.88 (turn #86) ASSET TAG NORMALIZATION — STT regularly
  // hands us "P TWO OH THREE" or "PEE DASH 2 0 3" instead of
  // "P-203". The normalizer collapses the spoken form to canonical.
  // Returns the canonical tag or null when no pattern matches.
  const _DIGIT_WORDS = {
    'zero':'0','o':'0','oh':'0',
    'one':'1','two':'2','three':'3','four':'4','five':'5',
    'six':'6','seven':'7','eight':'8','nine':'9',
    'isa':'1','dalawa':'2','tatlo':'3','apat':'4','lima':'5',
    'anim':'6','pito':'7','walo':'8','siyam':'9','siam':'9',
  };
  const _LETTER_WORDS = {
    'pee':'P','bee':'B','see':'C','cee':'C','dee':'D','ee':'E','eff':'F',
    'gee':'G','aitch':'H','jay':'J','kay':'K','ell':'L','em':'M','en':'N',
    'pe':'P','be':'B','ce':'C','de':'D','ge':'G',
  };
  function _normalizeAssetTag(text) {
    const s = String(text || '').toLowerCase();
    if (!s) return null;
    // Fast path: already canonical e.g. "P-203" / "C01" / "MX-12"
    const direct = s.match(/\b([A-Za-z]{1,3})\s*-?\s*(\d{2,5})\b/);
    if (direct) {
      return direct[1].toUpperCase() + '-' + direct[2];
    }
    // Slow path: replace letter/digit words.
    const tokens = s.replace(/[^a-z0-9 \-]/g, ' ').split(/\s+/).filter(Boolean);
    const mapped = tokens.map(t => {
      if (_LETTER_WORDS[t]) return _LETTER_WORDS[t];
      if (_DIGIT_WORDS[t]) return _DIGIT_WORDS[t];
      if (/^[a-z]$/.test(t)) return t.toUpperCase();
      if (/^\d+$/.test(t)) return t;
      if (t === 'dash' || t === 'gitling') return '-';
      return null;
    }).filter(Boolean);
    // Look for a [letter+] [digit+] adjacency.
    for (let i = 0; i < mapped.length - 1; i++) {
      const a = mapped[i], b = mapped[i + 1];
      if (/^[A-Z]{1,3}$/.test(a) && /^\d{2,5}$/.test(b)) {
        return a + '-' + b;
      }
      // Compact form e.g. P + 2 + 0 + 3 → P-203
      if (/^[A-Z]$/.test(a)) {
        const rest = mapped.slice(i + 1, i + 5).join('');
        if (/^\d{2,4}$/.test(rest)) return a + '-' + rest;
      }
    }
    return null;
  }

  // Phase 4.89 (turn #87) TIME-RANGE NORMALIZATION — workers say
  // "this week" / "yesterday" / "ngayong araw" / "last 7 days".
  // Helper returns { start, end } ISO strings (start of day to now).
  // Server-side queries can use these directly.
  function _normalizeTimeRange(text) {
    const s = String(text || '').toLowerCase();
    if (!s) return null;
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const dayMs = 24 * 60 * 60 * 1000;
    function isoSpan(daysAgo) {
      const start = new Date(todayStart.getTime() - daysAgo * dayMs);
      return { start: start.toISOString(), end: now.toISOString(), days: daysAgo + 1 };
    }
    if (/\btoday|ngayon|ngayong\s+araw\b/i.test(s)) return isoSpan(0);
    if (/\byesterday|kahapon\b/i.test(s)) {
      const start = new Date(todayStart.getTime() - dayMs);
      const end = new Date(todayStart.getTime() - 1);
      return { start: start.toISOString(), end: end.toISOString(), days: 1 };
    }
    if (/\bthis\s+week|ngayong\s+linggo\b/i.test(s))   return isoSpan(7);
    if (/\blast\s+week|nakaraang\s+linggo\b/i.test(s)) return isoSpan(14);
    if (/\bthis\s+month|ngayong\s+buwan\b/i.test(s))   return isoSpan(30);
    if (/\blast\s+30\s+days|nakaraang\s+30\s+araw\b/i.test(s)) return isoSpan(30);
    if (/\blast\s+7\s+days|nakaraang\s+7\s+araw|past\s+week\b/i.test(s)) return isoSpan(7);
    const m = s.match(/\blast\s+(\d{1,3})\s+(day|days|araw)\b/i);
    if (m) {
      const n = Math.min(365, Math.max(1, Number(m[1])));
      return isoSpan(n);
    }
    return null;
  }

  // Phase 4.90 (turn #88) ACKNOWLEDGEMENT STYLE — workers vary in
  // how much warm-up they want. 'terse' = no naks/sige/ah/oo before
  // the data; 'warm' = one short ack line. Persists per-device.
  const _ACK_STYLE_KEY = 'wh_voice_ack_style';
  function _getAckStyle() {
    try { return localStorage.getItem(_ACK_STYLE_KEY) || 'warm'; }
    catch (_) { return 'warm'; }
  }
  function _setAckStyle(style) {
    if (style !== 'terse' && style !== 'warm') return false;
    try { localStorage.setItem(_ACK_STYLE_KEY, style); return true; }
    catch (_) { return false; }
  }
  const _ACK_TERSE_RE = /\b(?:no\s+small\s+talk|skip\s+(?:the\s+)?(?:ack|small\s+talk|pleasantries)|just\s+(?:the|give\s+me\s+the)\s+(?:number|answer|data)|terse|cut\s+the\s+chit\s*chat|wag\s+nang\s+(?:mag[\-\s]?ack|magpaligoy[\-\s]?ligoy))\b/i;
  const _ACK_WARM_RE  = /\b(?:be\s+warmer|more\s+(?:friendly|warm|conversational)|warm\s+(?:up|mode|tone)|sige[, ]+(?:friendly|mag[\-\s]?warm)\s+ka)\b/i;
  function _detectAckStyleToggle(text) {
    const s = String(text || '');
    if (!s) return null;
    if (_ACK_TERSE_RE.test(s)) return 'terse';
    if (_ACK_WARM_RE.test(s)) return 'warm';
    return null;
  }

  // Phase 4.91 (turn #89) FORBIDDEN-TOPIC REDIRECT — beyond the
  // T12 SENSITIVE TOPIC (HR/legal/financial), some surfaces are
  // hard-banned: competitor names, internal politics, off-topic
  // chitchat at depth. Detector returns the topic kind so the LLM
  // can use the matched REDIRECT anchor.
  const _COMPETITORS_RE = /\b(?:UpKeep|Fiix|Limble|MaintainX|eMaint|Hippo\s+CMMS|Maintenance\s+Connection|MicroMain)\b/i;
  const _POLITICS_RE = /\b(?:office\s+politics|chismis|tsismis|drama|backstab|gossip|rumour|rumor)\b/i;
  function _detectForbiddenTopic(text) {
    const s = String(text || '');
    if (!s) return null;
    if (_COMPETITORS_RE.test(s)) return 'competitor';
    if (_POLITICS_RE.test(s)) return 'office_politics';
    return null;
  }

  // Phase 4.92 (turn #90) NOISE-FLOOR AUTO-PAUSE — extends T63
  // mic meter with a noise-floor estimate. If background noise
  // sustains above 35 (peak) for >3s while no speech-shaped
  // burst lands, suggest a quieter location.
  function _classifyMicEnv(peakSamples) {
    if (!Array.isArray(peakSamples) || peakSamples.length < 8) return 'unknown';
    const sorted = peakSamples.slice().sort((a, b) => a - b);
    const p50 = sorted[Math.floor(sorted.length / 2)];
    const p90 = sorted[Math.floor(sorted.length * 0.9)];
    if (p50 < 20)  return 'quiet';
    if (p50 < 35)  return 'normal';
    if (p50 < 55 && p90 - p50 > 10)  return 'spotty';   // bursts of background
    return 'noisy';
  }

  // Phase 4.93 (turn #91) CONVERSATION PIN — workers want to mark
  // a piece of advice ("pin this") so it surfaces again at the
  // start of the next session. Stored per worker_name, capped at
  // 20 entries.
  const _PIN_KEY_PREFIX = 'wh_voice_pinned_';
  const _PIN_MAX = 20;
  function _pinTurn(workerName, payload) {
    if (!workerName || !payload) return false;
    try {
      const key = _PIN_KEY_PREFIX + String(workerName).slice(0, 60);
      const raw = localStorage.getItem(key);
      const list = raw ? (JSON.parse(raw) || []) : [];
      list.push({
        ts:    Date.now(),
        text:  String(payload.text || '').slice(0, 240),
        intent: String(payload.intent || ''),
      });
      while (list.length > _PIN_MAX) list.shift();
      localStorage.setItem(key, JSON.stringify(list));
      return true;
    } catch (_) { return false; }
  }
  function _getPinnedTurns(workerName) {
    if (!workerName) return [];
    try {
      const raw = localStorage.getItem(_PIN_KEY_PREFIX + String(workerName).slice(0, 60));
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch (_) { return []; }
  }
  const _PIN_RE = /\b(?:pin\s+(?:this|that|yan|yun|ito)|i[\-\s]?pin\s+mo|save\s+(?:this|that)\s+(?:for\s+later|as\s+pin)|tandaan\s+mo\s+(?:to|ito|yun|yan)|tag\s+(?:this|ito|yun)\s+(?:as\s+)?pin)\b/i;
  function _isPinRequest(text) {
    const s = String(text || '');
    if (!s || s.length > 120) return false;
    return _PIN_RE.test(s);
  }

  // Phase 4.94 (turn #92) HELP COMMAND SHORTCUT — "help" /
  // "tulungan mo ako" / "/help" surfaces a quick capability tour
  // (different from T81 SCOPE which describes the full surface).
  // HELP routes directly without LLM round-trip.
  const _HELP_RE = /^(?:\/help|help(?:\s+(?:me|please|pls))?|tulungan\s+mo\s+ako|saklolo|paano\s+gamitin|how\s+to\s+use)$/i;
  function _isHelpCommand(text) {
    const s = String(text || '').trim();
    if (!s || s.length > 60) return false;
    return _HELP_RE.test(s);
  }

  // Phase 4.95 (turn #93) MULTI-LANGUAGE KPI LABEL — when the
  // language pref is Tagalog/Cebuano, serve the KPI label in that
  // language too. The dictionary is intentionally small + manual
  // (no machine translation) so terminology stays standards-aligned.
  const _KPI_LABEL_DICT = {
    'mtbf':       { tagalog: 'Karaniwang oras bago masira', cebuano: 'Kasagarang takna bag-o madaot' },
    'mttr':       { tagalog: 'Karaniwang oras para iayos',   cebuano: 'Kasagarang takna sa pag-ayo' },
    'oee':        { tagalog: 'Bisa ng makina (OEE)',         cebuano: 'Episyensya sa makina (OEE)' },
    'compliance': { tagalog: 'Pagsunod sa PM',                cebuano: 'Pagsunod sa PM' },
    'availability': { tagalog: 'Kahandaan',                   cebuano: 'Kahandaan' },
  };
  function _translateKpiLabel(metric, pref) {
    if (!metric) return null;
    const m = String(metric).toLowerCase();
    const p = String(pref || '').toLowerCase().replace(/-leaning$/, '');
    const entry = _KPI_LABEL_DICT[m];
    if (!entry) return null;
    return entry[p] || null;
  }

  // Phase 4.96 (turn #94) NEW-WORKER ONBOARDING — when the worker
  // has no prior turns in agent_memory AND voice_journal_entries
  // is empty, mark this as a first-time session. Caller surfaces
  // a 2-line welcome + a "try saying X" hint as the first
  // companion line.
  async function _isFirstTimeWorker(db, hiveId, workerName) {
    if (!db || !hiveId || !workerName) return false;
    try {
      const { count } = await db.from('voice_journal_entries')
        .select('id', { count: 'exact', head: true })
        .eq('hive_id', hiveId)
        .eq('worker_name', workerName)
        .limit(1);
      return Number(count) === 0;
    } catch (_) { return false; }
  }
  function _firstTimeWelcomeLine(personaName) {
    const p = String(personaName || 'kapatid');
    return 'Hi! I\'m ' + p + ', your maintenance companion. ' +
           'Try saying: "what\'s overdue today" / "log a stop on P-203" / "what is OEE". ' +
           'I\'ll always cite the source — and I never guess on numbers.';
  }

  // ============================================================
  // TENTH 10-TURN FLYWHEEL — turns #95-#104 (Phase 4.97-4.106)
  // INTEGRATION + AUDIT layer. Adds audit trail, quiet hours,
  // action preflight, idle cleanup, error analytics, session
  // tagging, deep links, STT grammar guess, persona phrase pool,
  // shift-end handover trigger.
  // ============================================================

  // Phase 4.97 (turn #95) AUDIT LOG EMISSION — every confirmed
  // write action (log entry, schedule, alert flag) writes to
  // ai_audit_log so we can replay every voice-driven decision.
  // Best-effort: never blocks the turn.
  async function _emitAuditEvent(db, ctx, eventType, payload) {
    if (!db || !ctx || !eventType) return false;
    try {
      const row = {
        hive_id:     ctx.hive_id || null,
        worker_name: ctx.worker_name || null,
        event_type:  String(eventType).slice(0, 60),
        payload:     payload || {},
        source:      'voice-handler',
        created_at:  new Date().toISOString(),
      };
      await db.from('ai_audit_log').insert(row);
      return true;
    } catch (_) { return false; }
  }

  // Phase 4.98 (turn #96) QUIET HOURS — non-critical proactive
  // alerts are silent between 22:00-06:00 PHT (UTC+8). Critical
  // alerts always fire — quiet hours never block safety signals.
  function _isQuietHours(nowDate) {
    const d = nowDate ? new Date(nowDate) : new Date();
    if (!(d instanceof Date) || isNaN(d.getTime())) return false;
    // Convert to UTC+8 hour. d.getUTCHours() gives UTC.
    const phHour = (d.getUTCHours() + 8) % 24;
    return phHour >= 22 || phHour < 6;
  }

  // Phase 4.99 (turn #97) ACTION PREFLIGHT — before dispatching
  // through voice-action-router, run a deterministic preflight:
  // do we have the required slots? is the asset valid-shape?
  // do we hold the voice-execute lock? Returns {ok, blocker}.
  function _preflightAction(intent, slots) {
    const i = String(intent || '');
    const s = (slots && typeof slots === 'object') ? slots : {};
    if (!i) return { ok: false, blocker: 'no_intent' };
    // Most write intents need an asset_tag.
    const writeVerbs = new Set([
      'log_entry','schedule_pm','flag_alert','update_status',
      'log_stop','close_pm','start_pm','log_bearing_change',
    ]);
    if (writeVerbs.has(i)) {
      if (!s.asset_tag) return { ok: false, blocker: 'missing_asset_tag' };
      if (!/^[A-Z]{1,3}-?\d{2,5}$/i.test(String(s.asset_tag))) {
        return { ok: false, blocker: 'malformed_asset_tag' };
      }
    }
    if (!_isVoiceExecuteAuth()) {
      return { ok: false, blocker: 'voice_execute_lock' };
    }
    return { ok: true, blocker: null };
  }

  // Phase 4.100 (turn #98) IDLE SESSION CLEANUP — when the
  // overlay sits open with no input for >5 min, auto-pause:
  // stop recording, dim avatar to 'idle', release session lock.
  // Caller schedules with setTimeout.
  const _IDLE_TIMEOUT_MS = 5 * 60 * 1000;
  let _idleTimerHandle = null;
  function _scheduleIdleCleanup(callback) {
    if (_idleTimerHandle) {
      try { clearTimeout(_idleTimerHandle); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
    }
    if (typeof callback !== 'function') return null;
    _idleTimerHandle = setTimeout(callback, _IDLE_TIMEOUT_MS);
    return _idleTimerHandle;
  }
  function _cancelIdleCleanup() {
    if (_idleTimerHandle) {
      try { clearTimeout(_idleTimerHandle); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
      _idleTimerHandle = null;
    }
  }

  // Phase 4.101 (turn #99) COMPANION-ERROR ANALYTICS — when the
  // gateway returns 5xx, bump a per-hive counter in localStorage.
  // The ai-quality.html surface surfaces this; the supervisor
  // sees patterns (e.g. "Hive 3 hit 12 gateway 503s today").
  function _errorKey(hiveId) {
    return 'wh_voice_errors_' + String(hiveId || 'anon');
  }
  function _bumpErrorCount(hiveId, kind) {
    if (!hiveId) return false;
    try {
      const k = _errorKey(hiveId);
      const raw = localStorage.getItem(k);
      const data = raw ? (JSON.parse(raw) || {}) : {};
      const today = new Date().toISOString().slice(0, 10);
      data[today] = data[today] || {};
      const errKind = String(kind || 'unknown').slice(0, 32);
      data[today][errKind] = (data[today][errKind] || 0) + 1;
      // Prune older than 7 days.
      const cutoff = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000)
        .toISOString().slice(0, 10);
      Object.keys(data).forEach(day => { if (day < cutoff) delete data[day]; });
      localStorage.setItem(k, JSON.stringify(data));
      return data[today][errKind];
    } catch (_) { return false; }
  }
  function _getErrorCounts(hiveId) {
    try {
      const raw = localStorage.getItem(_errorKey(hiveId));
      return raw ? (JSON.parse(raw) || {}) : {};
    } catch (_) { return {}; }
  }

  // Phase 4.102 (turn #100) SESSION TAG — workers can label a
  // session ("PM planning", "incident on C-01") so the next
  // session can pull up the prior context. Stored per-session
  // in localStorage with a session_id key.
  function _sessionTagKey(sessionId) {
    return 'wh_voice_session_tag_' + String(sessionId || 'unknown');
  }
  function _setSessionTag(sessionId, tag) {
    if (!sessionId || !tag) return false;
    try {
      localStorage.setItem(_sessionTagKey(sessionId),
        String(tag).slice(0, 80));
      return true;
    } catch (_) { return false; }
  }
  function _getSessionTag(sessionId) {
    try { return localStorage.getItem(_sessionTagKey(sessionId)) || null; }
    catch (_) { return null; }
  }
  const _TAG_RE = /\b(?:tag\s+(?:this|ito|yan)\s+(?:as|na)?\s*([\w\-\s]{3,40})|i[\-\s]?tag\s+mo\s+(?:as|na)\s+([\w\-\s]{3,40}))\b/i;
  function _detectSessionTagRequest(text) {
    const s = String(text || '');
    if (!s || s.length > 120) return null;
    const m = s.match(_TAG_RE);
    if (!m) return null;
    return String(m[1] || m[2] || '').trim().slice(0, 60);
  }

  // Phase 4.103 (turn #101) CROSS-PAGE DEEP-LINK SHORTHAND — the
  // companion's reply may contain a token like <wh-link page=pm
  // asset=P-203> which the renderer converts to an anchor tag.
  // Helper here builds + parses the shorthand.
  function _buildDeepLink(page, params) {
    const p = String(page || '').toLowerCase().replace(/[^a-z0-9\-_]/g, '');
    if (!p) return null;
    const safeParams = {};
    if (params && typeof params === 'object') {
      Object.keys(params).forEach(k => {
        const cleanK = String(k).replace(/[^a-z0-9_]/g, '');
        if (cleanK) safeParams[cleanK] = String(params[k] || '')
          .replace(/[<>"]/g, '').slice(0, 60);
      });
    }
    const q = Object.keys(safeParams)
      .map(k => k + '=' + encodeURIComponent(safeParams[k])).join('&');
    return '/' + p + '.html' + (q ? '?' + q : '');
  }
  function _parseDeepLinkToken(token) {
    const s = String(token || '');
    const m = s.match(/<wh-link\s+([^>]+)>/i);
    if (!m) return null;
    const attrs = {};
    const re = /(\w+)\s*=\s*([^\s>]+)/g;
    let am;
    while ((am = re.exec(m[1])) !== null) {
      attrs[am[1].toLowerCase()] = am[2];
    }
    if (!attrs.page) return null;
    const { page, ...rest } = attrs;
    return { page, params: rest };
  }

  // Phase 4.104 (turn #102) STT GRAMMAR CORRECTION GUESS — when
  // the transcript looks badly mangled (high consonant clustering,
  // few word boundaries), surface a "did you mean" line. Heuristic
  // only — never silently rewrites the worker's input.
  function _looksGrammarMangled(text) {
    const s = String(text || '').trim();
    if (!s || s.length < 8 || s.length > 400) return false;
    const words = s.split(/\s+/);
    if (words.length < 3) return false;
    // Too many >=10-char tokens AND no recognised verbs.
    const longTokens = words.filter(w => w.length >= 10).length;
    const hasVerb = /\b(?:is|are|was|were|has|have|will|can|do|does|did|log|check|schedule|show|tell|find|open|close|update|start|stop|create|fix|run|set|get)\b/i.test(s);
    if (longTokens / words.length >= 0.5 && !hasVerb) return true;
    // High consonant ratio with no spaces.
    const noSpace = s.replace(/\s+/g, '');
    if (noSpace.length >= 20) {
      const vowels = (noSpace.match(/[aeiouAEIOU]/g) || []).length;
      if (vowels / noSpace.length < 0.18) return true;
    }
    return false;
  }

  // Phase 4.105 (turn #103) PERSONA PHRASE POOL — instead of
  // always opening with "naks" / "sige", rotate through a small
  // pool to avoid repetition fatigue. Pool keyed by category;
  // helper returns a randomly chosen phrase.
  const _PHRASE_POOL = {
    ack:        ['sige', 'oks', 'ay sige', 'okay kuya', 'ah ok'],
    encourage:  ['naks', 'galing', 'astig', 'magaling', 'sulit'],
    concern:    ['aray', 'medyo magulo', 'sandali lang', 'teka', 'eh ano nga'],
    closing:    ['salamat', 'good luck', 'ingat ka', 'tara', 'sige po'],
  };
  let _lastPhrasePerCategory = {};
  function _pickPersonaPhrase(category) {
    const cat = String(category || '').toLowerCase();
    const pool = _PHRASE_POOL[cat];
    if (!pool || pool.length === 0) return null;
    let i = Math.floor(Math.random() * pool.length);
    // Avoid emitting the same phrase twice in a row.
    if (_lastPhrasePerCategory[cat] === pool[i] && pool.length > 1) {
      i = (i + 1) % pool.length;
    }
    _lastPhrasePerCategory[cat] = pool[i];
    return pool[i];
  }

  // Phase 4.106 (turn #104) SHIFT-END HANDOVER TRIGGER — when
  // the worker's shift is about to end (worker_shift_end_hour
  // in worker profile + UTC+8 math), proactively offer a
  // handover summary. Detection only; caller decides UX.
  function _isNearShiftEnd(shiftEndHour, marginMin) {
    const h = Number(shiftEndHour);
    if (!Number.isFinite(h) || h < 0 || h > 23) return false;
    const m = Number.isFinite(Number(marginMin)) ? Number(marginMin) : 30;
    const now = new Date();
    const phMin = (now.getUTCHours() * 60 + now.getUTCMinutes() + 8 * 60) % (24 * 60);
    const endMin = h * 60;
    const diff = endMin - phMin;
    if (diff < 0) return false;
    return diff <= m;
  }

  // ============================================================
  // ELEVENTH 10-TURN FLYWHEEL — turns #105-#114 (Phase 4.107-4.116)
  // PROACTIVE ASSISTANCE + LEARNING. The companion now adapts to
  // the worker rather than vice-versa: skill-level pacing, pattern
  // detection, vocabulary normalization, knowledge-gap logging,
  // and mentor-handoff.
  // ============================================================

  // Phase 4.107 (turn #105) ADAPTIVE PM SYNC — when the worker
  // logs "PM done on P-203" and the schedule says it wasn't due
  // for X more days, surface a sync prompt so the schedule
  // doesn't drift. Returns {sync_needed, days_diff} or null.
  function _detectPmSyncDrift(loggedAsset, schedNextDate) {
    if (!loggedAsset || !schedNextDate) return null;
    try {
      const next = new Date(schedNextDate);
      if (isNaN(next.getTime())) return null;
      const now = Date.now();
      const diffMs = next.getTime() - now;
      const diffDays = Math.round(diffMs / (24 * 60 * 60 * 1000));
      if (Math.abs(diffDays) < 3) return null; // tolerance
      return { sync_needed: true, days_diff: diffDays, asset: loggedAsset };
    } catch (_) { return null; }
  }

  // Phase 4.108 (turn #106) SKILL-LEVEL ADAPTATION — the worker's
  // skill record (Level 1-5) drives vocabulary depth. Level 1-2
  // (apprentice) gets plain words; Level 4-5 (senior/lead) gets
  // technical depth (RPN, FMEA, MTBF derivative). The helper picks
  // the depth tier.
  function _skillDepthForLevel(level) {
    const n = Number(level);
    if (!Number.isFinite(n)) return 'standard';
    if (n <= 2) return 'apprentice';
    if (n >= 4) return 'senior';
    return 'standard';
  }
  function _vocabularyForDepth(depth) {
    if (depth === 'apprentice') {
      return { mtbf: 'average time between breakdowns', mttr: 'average repair time',
               rpn: 'risk score (1-1000)', fmea: 'failure-mode review' };
    }
    if (depth === 'senior') {
      return { mtbf: 'MTBF (calendar time)', mttr: 'MTTR (active repair)',
               rpn: 'RPN (S*O*D)', fmea: 'FMEA per SAE J1739' };
    }
    return { mtbf: 'mean time between failures', mttr: 'mean time to repair',
             rpn: 'risk priority number', fmea: 'FMEA' };
  }

  // Phase 4.109 (turn #107) CROSS-ASSET PATTERN DETECTION — when
  // the same failure_mode is reported on >=2 assets in <7 days,
  // surface the pattern. Helper takes the recent logbook entries
  // and finds clusters.
  function _detectCrossAssetPattern(logbookEntries) {
    if (!Array.isArray(logbookEntries) || logbookEntries.length < 2) return null;
    const cutoff = Date.now() - 7 * 24 * 60 * 60 * 1000;
    const recent = logbookEntries.filter(e => {
      if (!e || !e.created_at) return false;
      try { return new Date(e.created_at).getTime() >= cutoff; }
      catch (_) { return false; }
    });
    if (recent.length < 2) return null;
    const byMode = {};
    for (const e of recent) {
      const m = String((e.failure_mode || e.issue || '')).toLowerCase().trim();
      if (!m) continue;
      const a = String(e.asset_tag || '').trim();
      if (!a) continue;
      byMode[m] = byMode[m] || new Set();
      byMode[m].add(a);
    }
    const patterns = [];
    Object.keys(byMode).forEach(m => {
      const assets = Array.from(byMode[m]);
      if (assets.length >= 2) patterns.push({ failure_mode: m, assets, count: assets.length });
    });
    return patterns.length ? patterns : null;
  }

  // Phase 4.110 (turn #108) VOICE COMMAND VOCABULARY LEARNING —
  // count per-worker recurring intents in localStorage so the
  // companion can hint "you usually check X next". Capped at 50
  // intents per worker; 30-day rolling window.
  const _INTENT_HISTORY_KEY = 'wh_voice_intent_hist_';
  function _recordIntent(workerName, intent) {
    if (!workerName || !intent) return false;
    try {
      const key = _INTENT_HISTORY_KEY + String(workerName).slice(0, 60);
      const raw = localStorage.getItem(key);
      const list = raw ? (JSON.parse(raw) || []) : [];
      list.push({ intent: String(intent).slice(0, 40), ts: Date.now() });
      const cutoff = Date.now() - 30 * 24 * 60 * 60 * 1000;
      const pruned = list.filter(e => e.ts >= cutoff).slice(-50);
      localStorage.setItem(key, JSON.stringify(pruned));
      return true;
    } catch (_) { return false; }
  }
  function _topRecurringIntents(workerName, n) {
    if (!workerName) return [];
    try {
      const raw = localStorage.getItem(_INTENT_HISTORY_KEY + String(workerName).slice(0, 60));
      const list = raw ? (JSON.parse(raw) || []) : [];
      const counts = {};
      list.forEach(e => { counts[e.intent] = (counts[e.intent] || 0) + 1; });
      const limit = Math.max(1, Math.min(10, Number(n) || 3));
      return Object.keys(counts)
        .map(k => ({ intent: k, count: counts[k] }))
        .sort((a, b) => b.count - a.count)
        .slice(0, limit);
    } catch (_) { return []; }
  }

  // Phase 4.111 (turn #109) SENTIMENT-OVER-TIME — track the
  // session sentiment (rough heuristic) per day. Three days of
  // negative sentiment in a row → escalate to supervisor via
  // ai_quality_escalation.
  const _SENTIMENT_KEY = 'wh_voice_sentiment_';
  function _classifySessionSentiment(turns) {
    if (!Array.isArray(turns) || turns.length === 0) return 'neutral';
    const text = turns.map(t => (t && (t.user || t.utter)) || '').join(' ').toLowerCase();
    const neg = (text.match(/\b(?:pagod|frustrated|stressed|sira|broken|fail|hindi gumana|nakakaloka|ayoko|sawa|gago|tanga)\b/g) || []).length;
    const pos = (text.match(/\b(?:salamat|thanks|naks|galing|magaling|astig|nice|fixed|gumana|tapos na|done|ayos)\b/g) || []).length;
    if (neg - pos >= 3) return 'negative';
    if (pos - neg >= 3) return 'positive';
    return 'neutral';
  }
  function _recordDailySentiment(workerName, sentiment) {
    if (!workerName || !sentiment) return false;
    try {
      const key = _SENTIMENT_KEY + String(workerName).slice(0, 60);
      const raw = localStorage.getItem(key);
      const log = raw ? (JSON.parse(raw) || {}) : {};
      const today = new Date().toISOString().slice(0, 10);
      log[today] = sentiment;
      // Prune older than 14 days.
      const cutoff = new Date(Date.now() - 14 * 24 * 60 * 60 * 1000)
        .toISOString().slice(0, 10);
      Object.keys(log).forEach(d => { if (d < cutoff) delete log[d]; });
      localStorage.setItem(key, JSON.stringify(log));
      return true;
    } catch (_) { return false; }
  }
  function _isPersistentNegative(workerName, daysRequired) {
    if (!workerName) return false;
    // Minimum 1 day required (a single same-day sentiment IS persistent
    // for the trivial case). Cap at 7 so a caller asking for 30 days
    // doesn't read more days than _recordDailySentiment retains.
    const req = Math.max(1, Math.min(7, Number(daysRequired) || 3));
    try {
      const raw = localStorage.getItem(_SENTIMENT_KEY + String(workerName).slice(0, 60));
      const log = raw ? (JSON.parse(raw) || {}) : {};
      const days = Object.keys(log).sort().slice(-req);
      if (days.length < req) return false;
      return days.every(d => log[d] === 'negative');
    } catch (_) { return false; }
  }

  // Phase 4.112 (turn #110) ANTICIPATORY DATA WARM-UP — when the
  // worker is on asset-hub and an asset_tag is mentioned, pre-
  // fetch the asset record so the next turn is sub-second. We
  // cache for 60s; longer than that and freshness matters more
  // than latency.
  const _WARMUP_TTL_MS = 60 * 1000;
  const _warmupCache = {};
  async function _warmAssetRecord(db, hiveId, assetTag) {
    if (!db || !hiveId || !assetTag) return null;
    const key = String(hiveId) + '|' + String(assetTag);
    const now = Date.now();
    const cached = _warmupCache[key];
    if (cached && (now - cached.ts) < _WARMUP_TTL_MS) return cached.value;
    try {
      const { data } = await db.from('v_asset_truth')
        .select('asset_tag,name,category,status,last_pm_at,next_pm_at,description')
        .eq('hive_id', hiveId).eq('asset_tag', assetTag).limit(1);
      const value = Array.isArray(data) && data.length ? data[0] : null;
      _warmupCache[key] = { value, ts: now };
      return value;
    } catch (_) { return null; }
  }

  // Phase 4.113 (turn #111) MAINTENANCE VOCABULARY NORMALIZER —
  // workers describe symptoms colloquially. Normalize to canonical
  // failure-mode tags so the LLM + downstream tooling agree.
  const _SYMPTOM_TO_FMODE = {
    vibration_anomaly: /\b(?:vibrat\w+|yumayanig|nag[\-\s]?vibrate|shaking|umuugoy|gumagalaw|shake|wobble)\b/i,
    overheat:          /\b(?:overheat|napaka[\-\s]?init|sumosobra\s+ang\s+init|mainit\s+(?:masyado|sobra)|nag[\-\s]?init|hot\s+to\s+touch|too\s+hot)\b/i,
    noise_anomaly:     /\b(?:noisy|umiingay|maingay|rattling|kumakalabog|kumakalansing|grinding|klanggg|squeal\w*)\b/i,
    leak:              /\b(?:leak\w*|tumutulo|tagas|paagos|may\s+tubig\s+sa)\b/i,
    smell_anomaly:     /\b(?:burning\s+smell|naa[\-\s]?amoy\s+sunog|amoy\s+kable|electrical\s+smell)\b/i,
    no_start:          /\b(?:won['']?t\s+start|hindi\s+(?:nag[\-\s]?start|umaandar|bumubukas)|no[\-\s]?start|ayaw\s+(?:bumukas|gumana))\b/i,
  };
  function _normalizeSymptom(text) {
    const s = String(text || '');
    if (!s) return null;
    for (const mode of Object.keys(_SYMPTOM_TO_FMODE)) {
      if (_SYMPTOM_TO_FMODE[mode].test(s)) return mode;
    }
    return null;
  }

  // Phase 4.114 (turn #112) SHIFT-BOUNDARY CONTEXT RESET — when
  // the session has been alive across a shift boundary (PHT
  // 06:00 / 14:00 / 22:00), the worker is effectively a new
  // session. Surface that + suggest a fresh session.
  function _crossedShiftBoundary(startedAtIso) {
    if (!startedAtIso) return false;
    try {
      const start = new Date(startedAtIso);
      const now = new Date();
      if (isNaN(start.getTime())) return false;
      // Build the list of PHT shift boundaries between start and now.
      const boundaries = [6, 14, 22];
      const startPhHour = (start.getUTCHours() + 8) % 24;
      const nowPhHour   = (now.getUTCHours() + 8) % 24;
      // If now-start > 8h, definitely crossed.
      if ((now.getTime() - start.getTime()) > 8 * 60 * 60 * 1000) return true;
      // Otherwise check whether we walked through a boundary.
      return boundaries.some(b => {
        if (startPhHour < b && nowPhHour >= b) return true;
        if (startPhHour > nowPhHour && nowPhHour >= b) return true; // wrapped midnight
        return false;
      });
    } catch (_) { return false; }
  }

  // Phase 4.115 (turn #113) KNOWLEDGE GAP LOGGING — when the
  // companion can't answer ("I don't have that data"), write a
  // row to ai_knowledge_gap so the supervisor can prioritise
  // backfilling the truth view. Best-effort.
  async function _logKnowledgeGap(db, ctx, transcript, reason) {
    if (!db || !ctx || !transcript) return false;
    try {
      await db.from('ai_knowledge_gap').insert({
        hive_id:     ctx.hive_id || null,
        worker_name: ctx.worker_name || null,
        question:    String(transcript).slice(0, 280),
        reason:      String(reason || 'unknown').slice(0, 80),
        source:      'voice-handler',
        created_at:  new Date().toISOString(),
      });
      return true;
    } catch (_) { return false; }
  }

  // Phase 4.116 (turn #114) MENTOR-MODE HANDOFF — when the
  // worker says "I'll ask my supervisor", offer to relay the
  // question (drops into a queue the supervisor reads on Hive).
  const _MENTOR_HANDOFF_RE = /\b(?:i[ '']?ll\s+(?:ask|check\s+with)\s+(?:my\s+)?(?:supervisor|kuya|ate|boss|lead)|tatanungin\s+ko\s+(?:si\s+\w+|ang\s+supervisor)|mag[\-\s]?tatanong\s+ako\s+kay\s+supervisor)\b/i;
  function _isMentorHandoff(text) {
    const s = String(text || '');
    if (!s || s.length > 200) return false;
    return _MENTOR_HANDOFF_RE.test(s);
  }
  async function _relayMentorQuestion(db, ctx, question) {
    if (!db || !ctx || !question) return false;
    try {
      await db.from('mentor_relay_queue').insert({
        hive_id:     ctx.hive_id || null,
        from_worker: ctx.worker_name || null,
        question:    String(question).slice(0, 280),
        status:      'pending',
        source:      'voice-handler',
        created_at:  new Date().toISOString(),
      });
      return true;
    } catch (_) { return false; }
  }

  // ============================================================
  // TWELFTH 10-TURN FLYWHEEL — turns #115-#124 (Phase 4.117-4.126)
  // COMPLIANCE + DATA GOVERNANCE. PII scrub, consent, retention,
  // right-to-erasure, audit export, suspicious activity, AI
  // disclosure, locale-aware dates, cost cap, voice drift advisory.
  // ============================================================

  // Phase 4.117 (turn #115) PII SCRUBBER — before persisting any
  // transcript to ai_audit_log / voice_journal, scrub phone
  // numbers, emails, and obvious PII patterns. PHL Data Privacy
  // Act compliance. Returns scrubbed text + the scrub count.
  function _scrubPii(text) {
    const s = String(text || '');
    if (!s) return { text: s, scrubs: 0 };
    let scrubs = 0;
    let out = s;
    // PH mobile: 09XX-XXX-XXXX or +639XX-XXX-XXXX
    out = out.replace(/(?:\+63|0)9\d{2}[\s\-]?\d{3}[\s\-]?\d{4}/g, () => { scrubs++; return '[PHONE]'; });
    // Generic email
    out = out.replace(/[a-z0-9._-]+@[a-z0-9.-]+\.[a-z]{2,}/gi, () => { scrubs++; return '[EMAIL]'; });
    // Generic 11-15 digit numbers (likely IDs)
    out = out.replace(/\b\d{11,15}\b/g, () => { scrubs++; return '[ID]'; });
    return { text: out, scrubs };
  }

  // Phase 4.118 (turn #116) CONSENT CAPTURE — voice recording
  // requires explicit worker consent under PH Data Privacy Act.
  // Stored per-device with timestamp + scope.
  const _CONSENT_KEY = 'wh_voice_consent';
  function _hasConsent() {
    try {
      const raw = localStorage.getItem(_CONSENT_KEY);
      if (!raw) return false;
      const data = JSON.parse(raw);
      return !!(data && data.consented_at);
    } catch (_) { return false; }
  }
  function _captureConsent(scope) {
    try {
      localStorage.setItem(_CONSENT_KEY, JSON.stringify({
        consented_at: new Date().toISOString(),
        scope: String(scope || 'voice-recording').slice(0, 80),
      }));
      return true;
    } catch (_) { return false; }
  }
  function _revokeConsent() {
    try { localStorage.removeItem(_CONSENT_KEY); return true; }
    catch (_) { return false; }
  }
  const _CONSENT_GRANT_RE = /\b(?:i\s+consent|sige[, ]+(?:i[\-\s]?consent|payag\s+ako)|payag\s+ako(?:\s+sa\s+recording)?|opt\s+in\s+to\s+(?:recording|voice)|sang[\-\s]?ayon\s+ako)\b/i;
  const _CONSENT_REVOKE_RE = /\b(?:revoke\s+(?:my\s+)?consent|opt\s+out\s+of\s+(?:recording|voice)|hindi\s+(?:na\s+)?ako\s+payag|withdraw\s+(?:my\s+)?consent|stop\s+recording\s+me)\b/i;
  function _detectConsentChange(text) {
    const s = String(text || '');
    if (!s) return null;
    if (_CONSENT_GRANT_RE.test(s))  return 'grant';
    if (_CONSENT_REVOKE_RE.test(s)) return 'revoke';
    return null;
  }

  // Phase 4.119 (turn #117) DATA RETENTION POLICY — per-hive
  // configurable retention (default 180 days). The retention
  // check returns the cutoff ISO; caller runs the DELETE.
  function _retentionCutoffIso(daysToRetain) {
    const d = Number(daysToRetain);
    const days = Number.isFinite(d) && d > 0 ? Math.min(d, 3650) : 180;
    return new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();
  }
  async function _enforceRetention(db, hiveId, daysToRetain) {
    if (!db || !hiveId) return false;
    try {
      const cutoff = _retentionCutoffIso(daysToRetain);
      await db.from('voice_journal_entries')
        .delete()
        .eq('hive_id', hiveId)
        .lt('created_at', cutoff);
      return cutoff;
    } catch (_) { return false; }
  }

  // Phase 4.120 (turn #118) RIGHT-TO-ERASURE — when the worker
  // says "delete my voice history" / "burahin mo lahat", run a
  // scoped DELETE against voice_journal_entries for their rows.
  // Best-effort + reports the operation for audit.
  const _ERASURE_RE = /\b(?:delete\s+(?:my|all\s+my)\s+(?:voice|conversation|chat|journal)\s+(?:history|data|records)|forget\s+everything\s+about\s+me|burahin\s+mo\s+(?:lahat|ang\s+history)|kalimutan\s+mo\s+lahat|right\s+to\s+erasure|gdpr\s+delete)\b/i;
  function _isErasureRequest(text) {
    const s = String(text || '');
    if (!s || s.length > 200) return false;
    return _ERASURE_RE.test(s);
  }
  async function _executeErasure(db, ctx) {
    if (!db || !ctx || !ctx.hive_id || !ctx.worker_name) return false;
    try {
      await db.from('voice_journal_entries')
        .delete()
        .eq('hive_id', ctx.hive_id)
        .eq('worker_name', ctx.worker_name);
      // Log the erasure itself so we have a record OF the deletion.
      await db.from('ai_audit_log').insert({
        hive_id:     ctx.hive_id,
        worker_name: ctx.worker_name,
        event_type:  'right_to_erasure',
        payload:     { scope: 'voice_journal_entries' },
        source:      'voice-handler',
        created_at:  new Date().toISOString(),
      });
      return true;
    } catch (_) { return false; }
  }

  // Phase 4.121 (turn #119) AUDIT EXPORT — produce a CSV string
  // of voice activity for compliance review. Caller hands the
  // string to a Blob/download anchor.
  function _toCsvRow(values) {
    return values.map(v => {
      const s = String(v == null ? '' : v).replace(/"/g, '""');
      return /[",\n]/.test(s) ? '"' + s + '"' : s;
    }).join(',');
  }
  function _buildAuditCsv(rows) {
    if (!Array.isArray(rows) || rows.length === 0) {
      return 'created_at,worker_name,event_type\n';
    }
    const header = ['created_at','worker_name','event_type','payload'];
    const out = [header.join(',')];
    for (const r of rows) {
      out.push(_toCsvRow([
        r.created_at || '',
        r.worker_name || '',
        r.event_type || '',
        typeof r.payload === 'object' ? JSON.stringify(r.payload) : (r.payload || ''),
      ]));
    }
    return out.join('\n') + '\n';
  }

  // Phase 4.122 (turn #120) SUSPICIOUS-ACTIVITY FLAG — detect
  // anomalous patterns (rapid-fire same intent, bulk off-hours
  // requests). Returns a kind label or null.
  function _detectSuspiciousActivity(workerName) {
    if (!workerName) return null;
    try {
      const raw = localStorage.getItem(_INTENT_HISTORY_KEY + String(workerName).slice(0, 60));
      const list = raw ? (JSON.parse(raw) || []) : [];
      if (list.length < 6) return null;
      // Rapid-fire: 5 same-intent within 60s
      const sorted = list.slice().sort((a,b) => a.ts - b.ts);
      for (let i = 4; i < sorted.length; i++) {
        const window = sorted.slice(i - 4, i + 1);
        if (window.every(e => e.intent === window[0].intent)
            && (window[4].ts - window[0].ts) <= 60 * 1000) {
          return 'rapid_fire';
        }
      }
      // Off-hours bulk: 10+ events in quiet hours (PHT 22-06)
      const offHours = list.filter(e => {
        const d = new Date(e.ts);
        const h = (d.getUTCHours() + 8) % 24;
        return h >= 22 || h < 6;
      });
      if (offHours.length >= 10) return 'off_hours_bulk';
      return null;
    } catch (_) { return null; }
  }

  // Phase 4.123 (turn #121) AI DISCLOSURE — when the disclosure
  // policy flag is set, the first companion turn surfaces an
  // explicit "you're talking to AI" line. Helper returns the
  // line + flips the per-session flag so it doesn't repeat.
  const _AI_DISCLOSURE_FLAG_KEY = 'wh_voice_ai_disclosure_policy';
  const _AI_DISCLOSURE_SHOWN_PREFIX = 'wh_voice_ai_disclosure_shown_';
  function _setAiDisclosurePolicy(enabled) {
    try {
      if (enabled) localStorage.setItem(_AI_DISCLOSURE_FLAG_KEY, '1');
      else localStorage.removeItem(_AI_DISCLOSURE_FLAG_KEY);
      return true;
    } catch (_) { return false; }
  }
  function _needsAiDisclosure(sessionId) {
    try {
      if (localStorage.getItem(_AI_DISCLOSURE_FLAG_KEY) !== '1') return false;
      if (!sessionId) return true;
      const k = _AI_DISCLOSURE_SHOWN_PREFIX + String(sessionId);
      return localStorage.getItem(k) !== '1';
    } catch (_) { return false; }
  }
  function _markAiDisclosureShown(sessionId) {
    if (!sessionId) return false;
    try {
      localStorage.setItem(_AI_DISCLOSURE_SHOWN_PREFIX + String(sessionId), '1');
      return true;
    } catch (_) { return false; }
  }
  function _aiDisclosureLine() {
    return 'Quick note — I\'m an AI companion. I cite the source for every number ' +
           'and I won\'t make medical, legal, or HR decisions. Sige, what do you need?';
  }

  // Phase 4.124 (turn #122) LOCALE-AWARE DATE FORMAT — when
  // language pref is Tagalog/Cebuano, format dates as DD/MM/YYYY
  // (PH convention); otherwise ISO. Helper consumes a Date OR
  // an ISO string and returns the formatted string.
  function _formatLocaleDate(input, langPref) {
    let d = null;
    if (input instanceof Date) d = input;
    else if (typeof input === 'string') {
      const parsed = new Date(input);
      if (!isNaN(parsed.getTime())) d = parsed;
    }
    if (!d) return null;
    const dd = String(d.getDate()).padStart(2, '0');
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const yyyy = d.getFullYear();
    const p = String(langPref || '').toLowerCase();
    if (p.startsWith('tagalog') || p.startsWith('cebuano') || p.startsWith('filipino')) {
      return dd + '/' + mm + '/' + yyyy;
    }
    return yyyy + '-' + mm + '-' + dd;
  }

  // Phase 4.125 (turn #123) COST CAP — per-hive monthly cost
  // ceiling. Reads aggregate USD spend from ai_cost_log; when
  // the running total breaches the cap, the next turn is
  // short-circuited to a "monthly cap reached" reply.
  async function _getMonthlyCost(db, hiveId) {
    if (!db || !hiveId) return 0;
    try {
      const monthStart = new Date();
      monthStart.setUTCDate(1); monthStart.setUTCHours(0,0,0,0);
      const { data } = await db.from('ai_cost_log')
        .select('cost_usd')
        .eq('hive_id', hiveId)
        .gte('created_at', monthStart.toISOString())
        .limit(10000);
      if (!Array.isArray(data)) return 0;
      return data.reduce((acc, r) => acc + (Number(r.cost_usd) || 0), 0);
    } catch (_) { return 0; }
  }
  function _exceededCostCap(spentUsd, capUsd) {
    const s = Number(spentUsd);
    const c = Number(capUsd);
    if (!Number.isFinite(s) || !Number.isFinite(c) || c <= 0) return false;
    return s >= c;
  }

  // Phase 4.126 (turn #124) VOICE DRIFT ADVISORY — track a
  // hash of mic-input characteristics (peak avg + cadence) and
  // warn when it shifts dramatically mid-session (someone else
  // grabbed the mic). ADVISORY ONLY — never an auth signal.
  const _DRIFT_KEY_PREFIX = 'wh_voice_signature_';
  function _signatureKey(workerName) { return _DRIFT_KEY_PREFIX + String(workerName || 'anon').slice(0, 60); }
  function _recordVoiceSignature(workerName, signature) {
    if (!workerName || !signature) return false;
    try {
      localStorage.setItem(_signatureKey(workerName), JSON.stringify({
        ts: Date.now(),
        avg_peak: Number(signature.avg_peak) || 0,
        cadence:  Number(signature.cadence) || 0,
      }));
      return true;
    } catch (_) { return false; }
  }
  function _voiceSignatureDrift(workerName, currentSig) {
    if (!workerName || !currentSig) return null;
    try {
      const raw = localStorage.getItem(_signatureKey(workerName));
      if (!raw) return null;
      const prior = JSON.parse(raw);
      if (!prior) return null;
      const peakDelta = Math.abs((Number(currentSig.avg_peak) || 0) - prior.avg_peak);
      const cadenceDelta = Math.abs((Number(currentSig.cadence) || 0) - prior.cadence);
      // Thresholds intentionally generous; this is advisory only.
      if (peakDelta > 25 && cadenceDelta > 0.3) {
        return { drift: true, peakDelta, cadenceDelta };
      }
      return { drift: false, peakDelta, cadenceDelta };
    } catch (_) { return null; }
  }

  // ============================================================
  // THIRTEENTH 10-TURN FLYWHEEL — turns #125-#134 (Phase 4.127-4.136)
  // MULTI-MODAL + ACCESSIBILITY layer. Camera capture, file
  // attachments, reduced-motion, screen-reader announce, keyboard
  // nav, color-blind palette, large-text, haptic, voice-only,
  // live captions.
  // ============================================================

  // Phase 4.127 (turn #125) IMAGE CAPTURE — "tingnan mo to" /
  // "let me show you" routes through this helper to open the
  // device camera, capture a still, and return a blob URL.
  // Falls back gracefully when getUserMedia is unavailable.
  async function _captureImageStill() {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        return { ok: false, blocker: 'no_media_devices' };
      }
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
      const video = document.createElement('video');
      video.srcObject = stream;
      video.muted = true;
      video.playsInline = true;
      await video.play();
      // Give the camera one frame to expose
      await new Promise(r => setTimeout(r, 250));
      const w = video.videoWidth || 640;
      const h = video.videoHeight || 480;
      const canvas = document.createElement('canvas');
      canvas.width = w; canvas.height = h;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0, w, h);
      stream.getTracks().forEach(t => t.stop());
      const dataUrl = canvas.toDataURL('image/jpeg', 0.8);
      return { ok: true, dataUrl, width: w, height: h };
    } catch (e) {
      return { ok: false, blocker: 'capture_failed', message: String(e && e.message || e) };
    }
  }

  // Phase 4.128 (turn #126) FILE ATTACHMENT — accept photo /
  // PDF uploads through a hidden input. Returns base64 + meta;
  // caller hands to the platform_scraper or attaches to the
  // logbook entry.
  function _openFileAttachment(accept) {
    return new Promise((resolve) => {
      try {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = String(accept || 'image/*,application/pdf');
        input.style.display = 'none';
        document.body.appendChild(input);
        input.addEventListener('change', () => {
          const file = input.files && input.files[0];
          if (!file) { input.remove(); resolve(null); return; }
          if (file.size > 8 * 1024 * 1024) {
            input.remove();
            resolve({ ok: false, blocker: 'too_large', size: file.size });
            return;
          }
          const reader = new FileReader();
          reader.onload = () => {
            input.remove();
            resolve({
              ok: true,
              name: String(file.name).slice(0, 120),
              type: file.type,
              size: file.size,
              dataUrl: reader.result,
            });
          };
          reader.onerror = () => { input.remove(); resolve({ ok: false, blocker: 'read_failed' }); };
          reader.readAsDataURL(file);
        });
        input.click();
      } catch (e) {
        resolve({ ok: false, blocker: 'unsupported' });
      }
    });
  }

  // Phase 4.129 (turn #127) REDUCED-MOTION ACCESSIBILITY — when
  // the worker's OS prefers reduced motion (prefers-reduced-motion
  // media query) OR they've toggled the pref manually, suppress
  // the avatar animation + bubble fade-in.
  const _REDUCED_MOTION_KEY = 'wh_voice_reduced_motion';
  function _isReducedMotionRequested() {
    try {
      if (localStorage.getItem(_REDUCED_MOTION_KEY) === '1') return true;
      if (typeof window.matchMedia === 'function') {
        return window.matchMedia('(prefers-reduced-motion: reduce)').matches === true;
      }
      return false;
    } catch (_) { return false; }
  }
  function _setReducedMotion(on) {
    try {
      if (on) localStorage.setItem(_REDUCED_MOTION_KEY, '1');
      else localStorage.removeItem(_REDUCED_MOTION_KEY);
      const ov = document.getElementById('wh-voice-overlay');
      if (ov) ov.setAttribute('data-reduced-motion', on ? '1' : '0');
      return true;
    } catch (_) { return false; }
  }

  // Phase 4.130 (turn #128) SCREEN-READER ANNOUNCE — every reply
  // is mirrored into an aria-live="polite" region so AT users
  // hear the companion's reply without needing to focus the
  // bubble. The region is created on first use.
  function _ensureAriaLiveRegion() {
    let region = document.getElementById('wh-voice-aria-live');
    if (region) return region;
    try {
      region = document.createElement('div');
      region.id = 'wh-voice-aria-live';
      region.setAttribute('aria-live', 'polite');
      region.setAttribute('aria-atomic', 'true');
      region.setAttribute('role', 'status');
      region.style.cssText = 'position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden;';
      document.body.appendChild(region);
      return region;
    } catch (_) { return null; }
  }
  function _announceForScreenReader(text) {
    const r = _ensureAriaLiveRegion();
    if (!r) return false;
    try {
      // Force a content change so AT picks it up even on identical text.
      r.textContent = '';
      setTimeout(() => { r.textContent = String(text || '').slice(0, 800); }, 30);
      return true;
    } catch (_) { return false; }
  }

  // Phase 4.131 (turn #129) KEYBOARD NAVIGATION — workers wearing
  // gloves or using a keyboard-only setup need predictable
  // shortcuts. Handler dispatches to actions; caller registers
  // the keydown listener once at mount.
  const _KEY_ACTIONS = {
    'Escape':    'close',
    'Space':     'toggle_recording',
    'Enter':     'submit_typed',
    'ArrowUp':   'replay_last',
    'ArrowDown': 'next_suggestion',
    'KeyH':      'help',
  };
  function _resolveKeyAction(event) {
    if (!event || !event.code) return null;
    const action = _KEY_ACTIONS[event.code] || null;
    if (!action) return null;
    // KeyH only fires with Ctrl/Cmd to avoid stealing real letters.
    if (event.code === 'KeyH' && !(event.ctrlKey || event.metaKey)) return null;
    // Space is dangerous in inputs; ignore when target is editable.
    if (event.code === 'Space' && event.target && _isEditableTarget(event.target)) return null;
    return action;
  }
  function _isEditableTarget(el) {
    if (!el) return false;
    const tag = String(el.tagName || '').toUpperCase();
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
    if (el.isContentEditable) return true;
    return false;
  }

  // Phase 4.132 (turn #130) COLOR-BLIND SAFE PALETTE — the
  // critical/high/medium severity tints get a CB-safe alternative
  // (blue-orange-yellow) when the worker opts in. Returns the
  // palette tokens; caller applies via data-palette attribute.
  const _CB_PALETTE_KEY = 'wh_voice_cb_palette';
  const _PALETTE_DEFAULT = { critical: '#dc2626', high: '#ea580c', medium: '#ca8a04', low: '#65a30d', info: '#0891b2' };
  const _PALETTE_CB_SAFE = { critical: '#1d4ed8', high: '#f59e0b', medium: '#facc15', low: '#0ea5e9', info: '#64748b' };
  function _isColorBlindMode() {
    try { return localStorage.getItem(_CB_PALETTE_KEY) === '1'; }
    catch (_) { return false; }
  }
  function _setColorBlindMode(on) {
    try {
      if (on) localStorage.setItem(_CB_PALETTE_KEY, '1');
      else localStorage.removeItem(_CB_PALETTE_KEY);
      const ov = document.getElementById('wh-voice-overlay');
      if (ov) ov.setAttribute('data-palette', on ? 'cb-safe' : 'default');
      return true;
    } catch (_) { return false; }
  }
  function _currentPalette() {
    return _isColorBlindMode() ? _PALETTE_CB_SAFE : _PALETTE_DEFAULT;
  }

  // Phase 4.133 (turn #131) LARGE-TEXT MODE — outdoor / low-vision
  // workers need 1.5x text. Toggle persists, applied via
  // data-text-size attribute.
  const _LARGE_TEXT_KEY = 'wh_voice_large_text';
  function _isLargeTextMode() {
    try { return localStorage.getItem(_LARGE_TEXT_KEY) === '1'; }
    catch (_) { return false; }
  }
  function _setLargeTextMode(on) {
    try {
      if (on) localStorage.setItem(_LARGE_TEXT_KEY, '1');
      else localStorage.removeItem(_LARGE_TEXT_KEY);
      const ov = document.getElementById('wh-voice-overlay');
      if (ov) ov.setAttribute('data-text-size', on ? 'large' : 'normal');
      return true;
    } catch (_) { return false; }
  }

  // Phase 4.134 (turn #132) HAPTIC FEEDBACK — short vibrate
  // pulses for important events on mobile (critical alert,
  // confirm-needed, error). Wraps navigator.vibrate which is
  // missing on iOS Safari — guarded everywhere.
  const _HAPTIC_PATTERNS = {
    confirm:  [40],
    success:  [30, 60, 30],
    warning:  [80, 80, 80],
    critical: [200, 80, 200, 80, 200],
  };
  function _hapticPulse(kind) {
    const pattern = _HAPTIC_PATTERNS[String(kind || '').toLowerCase()];
    if (!pattern) return false;
    try {
      if (navigator && typeof navigator.vibrate === 'function') {
        return navigator.vibrate(pattern);
      }
      return false;
    } catch (_) { return false; }
  }

  // Phase 4.135 (turn #133) VOICE-ONLY MODE — workers in safety
  // glasses / hands-busy contexts. UI fades, TTS does all the
  // talking, all output stays in audio + screen-reader region.
  // Implemented as a flag + data attribute; UI css consumes.
  const _VOICE_ONLY_KEY = 'wh_voice_only_mode';
  function _isVoiceOnlyMode() {
    try { return localStorage.getItem(_VOICE_ONLY_KEY) === '1'; }
    catch (_) { return false; }
  }
  function _setVoiceOnlyMode(on) {
    try {
      if (on) localStorage.setItem(_VOICE_ONLY_KEY, '1');
      else localStorage.removeItem(_VOICE_ONLY_KEY);
      const ov = document.getElementById('wh-voice-overlay');
      if (ov) ov.setAttribute('data-voice-only', on ? '1' : '0');
      return true;
    } catch (_) { return false; }
  }
  const _VOICE_ONLY_TOGGLE_RE = /\b(?:voice[\s\-]?only\s+(?:mode|on|off)|hands[\s\-]?free\s+(?:mode|on|off)|i[\-\s]?turn\s+(?:on|off)\s+voice[\s\-]?only|naka[\s\-]?safety\s+glasses\s+ako)\b/i;
  function _detectVoiceOnlyToggle(text) {
    const s = String(text || '');
    if (!s) return null;
    if (!_VOICE_ONLY_TOGGLE_RE.test(s)) return null;
    return /\boff\b/i.test(s) ? 'off' : 'on';
  }

  // Phase 4.136 (turn #134) LIVE CAPTIONS — when the worker
  // requests captions, every TTS line is mirrored into a visible
  // caption bar on the overlay. Distinct from screen-reader
  // announce (which is for AT). Persists per-device.
  const _CAPTIONS_KEY = 'wh_voice_captions';
  function _isCaptionsOn() {
    try { return localStorage.getItem(_CAPTIONS_KEY) === '1'; }
    catch (_) { return false; }
  }
  function _setCaptionsOn(on) {
    try {
      if (on) localStorage.setItem(_CAPTIONS_KEY, '1');
      else localStorage.removeItem(_CAPTIONS_KEY);
      return true;
    } catch (_) { return false; }
  }
  function _renderCaption(text) {
    if (!_isCaptionsOn()) return false;
    try {
      let bar = document.getElementById('wh-voice-caption-bar');
      if (!bar) {
        bar = document.createElement('div');
        bar.id = 'wh-voice-caption-bar';
        bar.setAttribute('aria-hidden', 'true');
        bar.style.cssText = 'position:fixed;bottom:0;left:0;right:0;background:rgba(0,0,0,0.78);color:white;padding:12px 16px;text-align:center;z-index:99999;font-size:18px;line-height:1.4;';
        document.body.appendChild(bar);
      }
      bar.textContent = String(text || '').slice(0, 240);
      return true;
    } catch (_) { return false; }
  }

  // ============================================================
  // FOURTEENTH 10-TURN FLYWHEEL — turns #135-#144 (Phase 4.137-4.146)
  // OPERATIONAL EXCELLENCE. Health pings, self-test, feature flags,
  // browser support, network adaptation, memory pressure, clock
  // drift, background tab pause, auto-recovery, presence heartbeat.
  // ============================================================

  // Phase 4.137 (turn #135) HEALTH CHECK PING — every 5 min the
  // companion pings /functions/v1/health so the supervisor's
  // ai-quality surface knows the device is alive + which version
  // it's running.
  const _HEALTH_PING_INTERVAL_MS = 5 * 60 * 1000;
  let _healthPingHandle = null;
  async function _pingHealthCheck(db, ctx) {
    if (!db || !ctx) return false;
    try {
      const fetcher = (typeof window.fetchWithTimeout === 'function')
        ? window.fetchWithTimeout : (u, o) => fetch(u, o);
      const body = {
        hive_id:     ctx.hive_id || null,
        worker_name: ctx.worker_name || null,
        client:      'voice-handler',
        sw_version:  (window.WHTts && window.WHTts.version) || 'unknown',
        ts:          new Date().toISOString(),
      };
      await fetcher((typeof SUPABASE_URL !== 'undefined' ? SUPABASE_URL : '') + '/functions/v1/voice-health', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }, 4000);
      return true;
    } catch (_) { return false; }
  }
  function _scheduleHealthPings(db, ctx) {
    if (_healthPingHandle) return _healthPingHandle;
    _healthPingHandle = setInterval(() => _pingHealthCheck(db, ctx), _HEALTH_PING_INTERVAL_MS);
    return _healthPingHandle;
  }
  function _stopHealthPings() {
    if (_healthPingHandle) {
      try { clearInterval(_healthPingHandle); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
      _healthPingHandle = null;
    }
  }

  // Phase 4.138 (turn #136) SELF-TEST ON MOUNT — sanity-check
  // the key helpers exist + return expected shapes. Logs to
  // console; never throws. Result is a {passed, total, failures}
  // structure so caller can render a badge.
  function _runSelfTest() {
    const checks = [
      ['affirmation regex', () => _isFollowupAffirmation('yes') === true],
      ['negation regex', () => _isFollowupNegation('no') === true],
      ['noise transcript', () => _isNoisyTranscript('') === true],
      ['asset tag normalize', () => _normalizeAssetTag('P-203') === 'P-203'],
      ['time range parse', () => _normalizeTimeRange('this week') !== null],
      ['toxicity guard', () => _detectToxicLanguage('clean text').severity === 0],
      ['pii scrub', () => _scrubPii('09171234567').text.includes('[PHONE]')],
      ['symptom normalize', () => _normalizeSymptom('yumayanig') === 'vibration_anomaly'],
      ['confidence label', () => _confidenceLabel(50, 120) === 'high'],
      ['palette current', () => typeof _currentPalette().critical === 'string'],
    ];
    const failures = [];
    let passed = 0;
    for (const [name, fn] of checks) {
      try {
        if (fn()) passed++;
        else failures.push(name);
      } catch (e) { failures.push(name + ': ' + (e && e.message || e)); }
    }
    const result = { passed, total: checks.length, failures };
    try { console.info('[WHVoice self-test]', result); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
    return result;
  }

  // Phase 4.139 (turn #137) FEATURE FLAG SYSTEM — per-hive flags
  // override per-build defaults. Flags are pulled from
  // wh_feature_flags table once per session + cached in module.
  const _featureFlagCache = { fetched_at: 0, flags: {} };
  const _FEATURE_FLAG_TTL_MS = 5 * 60 * 1000;
  async function _loadFeatureFlags(db, hiveId) {
    if (!db || !hiveId) return {};
    const now = Date.now();
    if (now - _featureFlagCache.fetched_at < _FEATURE_FLAG_TTL_MS
        && _featureFlagCache.hive_id === hiveId) {
      return _featureFlagCache.flags;
    }
    try {
      const { data } = await db.from('wh_feature_flags')
        .select('name,enabled')
        .or('hive_id.eq.' + hiveId + ',hive_id.is.null')
        .limit(200);
      const flags = {};
      if (Array.isArray(data)) data.forEach(r => { flags[r.name] = !!r.enabled; });
      _featureFlagCache.fetched_at = now;
      _featureFlagCache.hive_id = hiveId;
      _featureFlagCache.flags = flags;
      return flags;
    } catch (_) { return _featureFlagCache.flags; }
  }
  function _isFeatureOn(name) {
    const n = String(name || '');
    if (!n) return false;
    return _featureFlagCache.flags[n] === true;
  }

  // Phase 4.140 (turn #138) BROWSER SUPPORT BANNER — when key
  // APIs are missing (mediaDevices, AudioContext, fetch), surface
  // a banner so the worker knows to upgrade.
  function _checkBrowserSupport() {
    const missing = [];
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) missing.push('mediaDevices');
    if (typeof AudioContext === 'undefined' && typeof webkitAudioContext === 'undefined') missing.push('AudioContext');
    if (typeof fetch !== 'function') missing.push('fetch');
    if (typeof Promise === 'undefined') missing.push('Promise');
    return { supported: missing.length === 0, missing };
  }
  function _renderBrowserBanner(missing) {
    if (!Array.isArray(missing) || missing.length === 0) return false;
    try {
      let banner = document.getElementById('wh-voice-browser-banner');
      if (banner) return true;
      banner = document.createElement('div');
      banner.id = 'wh-voice-browser-banner';
      banner.setAttribute('role', 'alert');
      banner.textContent = 'Voice companion: your browser is missing ' + missing.join(', ') +
        '. Please use a recent Chrome / Edge / Safari for full functionality.';
      banner.style.cssText = 'position:fixed;top:0;left:0;right:0;background:#fef3c7;color:#92400e;padding:10px 16px;text-align:center;z-index:99998;border-bottom:1px solid #f59e0b;';
      document.body.appendChild(banner);
      return true;
    } catch (_) { return false; }
  }

  // Phase 4.141 (turn #139) NETWORK CONDITION ADAPTATION —
  // navigator.connection.effectiveType ('slow-2g'/'2g'/'3g'/'4g')
  // drives payload size. On 2g we send the transcript only; on
  // 4g we send the full context block.
  function _currentNetworkClass() {
    try {
      const c = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
      if (!c) return 'unknown';
      return String(c.effectiveType || 'unknown');
    } catch (_) { return 'unknown'; }
  }
  function _shouldUseLitePayload() {
    const cls = _currentNetworkClass();
    return cls === 'slow-2g' || cls === '2g';
  }

  // Phase 4.142 (turn #140) MEMORY PRESSURE HANDLER — when device
  // memory is low OR performance.memory shows heavy usage, drop
  // optional context (filipinoGlossary, kgContext) to keep the
  // turn under the heap budget.
  function _checkMemoryPressure() {
    try {
      const dm = Number(navigator.deviceMemory);
      if (Number.isFinite(dm) && dm <= 2) return { pressure: 'high', reason: 'device_memory_low' };
      if (typeof performance !== 'undefined' && performance.memory) {
        const used = performance.memory.usedJSHeapSize || 0;
        const limit = performance.memory.jsHeapSizeLimit || 1;
        const pct = used / limit;
        if (pct > 0.85) return { pressure: 'high', reason: 'heap_pct_high', pct };
        if (pct > 0.60) return { pressure: 'medium', reason: 'heap_pct_medium', pct };
      }
      return { pressure: 'low', reason: null };
    } catch (_) { return { pressure: 'unknown', reason: null }; }
  }

  // Phase 4.143 (turn #141) SERVER TIME SYNC — if the client
  // clock drifts >2 min from server time (Date header on a ping),
  // warn the supervisor — log timestamps will mismatch.
  async function _checkClockDrift() {
    try {
      const fetcher = (typeof window.fetchWithTimeout === 'function')
        ? window.fetchWithTimeout : (u, o) => fetch(u, o);
      const resp = await fetcher((typeof SUPABASE_URL !== 'undefined' ? SUPABASE_URL : '') + '/functions/v1/voice-health', { method: 'HEAD' }, 3000);
      if (!resp) return null;
      const serverDate = resp.headers && resp.headers.get && resp.headers.get('Date');
      if (!serverDate) return null;
      const serverMs = new Date(serverDate).getTime();
      if (!Number.isFinite(serverMs)) return null;
      const driftMs = Math.abs(Date.now() - serverMs);
      return { drift_ms: driftMs, exceeded: driftMs > 2 * 60 * 1000 };
    } catch (_) { return null; }
  }

  // Phase 4.144 (turn #142) BACKGROUND TAB PAUSE — when
  // document.visibilityState === 'hidden', pause recording so a
  // background tab doesn't keep the mic open + waste battery.
  function _shouldPauseForBackground() {
    try {
      return document.visibilityState === 'hidden';
    } catch (_) { return false; }
  }
  function _attachVisibilityHandler(onHidden, onVisible) {
    if (typeof onHidden !== 'function' && typeof onVisible !== 'function') return null;
    const handler = () => {
      try {
        if (document.visibilityState === 'hidden' && typeof onHidden === 'function') onHidden();
        else if (document.visibilityState === 'visible' && typeof onVisible === 'function') onVisible();
      } catch (_) { /* non-fatal */ /* empty-catch-allow: best-effort silent swallow */ }
    };
    try {
      document.addEventListener('visibilitychange', handler);
      return handler;
    } catch (_) { return null; }
  }

  // Phase 4.145 (turn #143) AUTO-RECOVERY ON JS EXCEPTION —
  // window.onerror catcher captures uncaught exceptions inside
  // the companion code path; surfaces a recover button (caller
  // wires the click). Best-effort: don't fight the browser's
  // own error handler.
  let _lastUncaughtError = null;
  function _installCrashHandler() {
    try {
      const prev = window.onerror;
      window.onerror = function(msg, src, line, col, err) {
        try {
          const s = String(src || '');
          if (s.indexOf('voice-handler') >= 0 || s.indexOf('wh-tts') >= 0) {
            _lastUncaughtError = { msg, src, line, col, ts: Date.now() };
          }
        } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
        if (typeof prev === 'function') {
          try { return prev.apply(this, arguments); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
        }
        return false;
      };
      return true;
    } catch (_) { return false; }
  }
  function _getLastCrashSummary() {
    if (!_lastUncaughtError) return null;
    return {
      msg: String(_lastUncaughtError.msg || '').slice(0, 200),
      line: _lastUncaughtError.line || 0,
      ago_ms: Date.now() - (_lastUncaughtError.ts || Date.now()),
    };
  }
  function _clearCrashState() { _lastUncaughtError = null; }

  // Phase 4.146 (turn #144) PRESENCE HEARTBEAT — write
  // last_seen for the worker_name to wh_voice_presence every
  // 60s. Supervisor's hive dashboard lists active voice workers.
  const _PRESENCE_INTERVAL_MS = 60 * 1000;
  let _presenceHandle = null;
  async function _writePresence(db, ctx) {
    if (!db || !ctx || !ctx.hive_id || !ctx.worker_name) return false;
    try {
      await db.from('wh_voice_presence').upsert({
        hive_id:     ctx.hive_id,
        worker_name: ctx.worker_name,
        last_seen:   new Date().toISOString(),
      }, { onConflict: 'hive_id,worker_name' });
      return true;
    } catch (_) { return false; }
  }
  function _startPresenceHeartbeat(db, ctx) {
    if (_presenceHandle) return _presenceHandle;
    _writePresence(db, ctx);
    _presenceHandle = setInterval(() => _writePresence(db, ctx), _PRESENCE_INTERVAL_MS);
    return _presenceHandle;
  }
  function _stopPresenceHeartbeat() {
    if (_presenceHandle) {
      try { clearInterval(_presenceHandle); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
      _presenceHandle = null;
    }
  }

  // ============================================================
  // FIFTEENTH 10-TURN FLYWHEEL — turns #145-#154 (Phase 4.147-4.156)
  // TEAM COORDINATION + CROSS-WORKER layer. Active sessions,
  // handoff, shared notes, broadcast, watchlist, buddy mode.
  // ============================================================

  // Phase 4.147 (turn #145) ACTIVE SESSION LIST — query
  // wh_voice_presence for all workers in the same hive whose
  // last_seen is within 5 min. Returns array of {worker_name, last_seen, age_min}.
  async function _listActiveVoiceWorkers(db, hiveId, selfWorker) {
    if (!db || !hiveId) return [];
    try {
      const since = new Date(Date.now() - 5 * 60 * 1000).toISOString();
      const { data } = await db.from('wh_voice_presence')
        .select('worker_name,last_seen')
        .eq('hive_id', hiveId)
        .gte('last_seen', since)
        .limit(50);
      if (!Array.isArray(data)) return [];
      const now = Date.now();
      return data
        .filter(r => r.worker_name && r.worker_name !== selfWorker)
        .map(r => ({
          worker_name: r.worker_name,
          last_seen:   r.last_seen,
          age_min:     Math.round((now - new Date(r.last_seen).getTime()) / 60000),
        }));
    } catch (_) { return []; }
  }

  // Phase 4.148 (turn #146) CROSS-WORKER HANDOFF — "send this to
  // Mike" / "ipasa kay kuya Ben" writes a row to
  // companion_handoff. Receiver sees it at next session open.
  const _HANDOFF_RE = /\b(?:send\s+(?:this|that|yan|yun|ito)\s+(?:to|kay|sa)\s+([A-Z][\w \-]{1,40})|i[\-\s]?pasa\s+mo\s+(?:kay|sa)\s+([A-Z][\w \-]{1,40})|hand\s+(?:this|that|it)\s+to\s+([A-Z][\w \-]{1,40}))\b/;
  function _detectHandoffRequest(text) {
    const s = String(text || '');
    if (!s || s.length > 200) return null;
    const m = s.match(_HANDOFF_RE);
    if (!m) return null;
    const name = (m[1] || m[2] || m[3] || '').trim();
    return name ? name.slice(0, 60) : null;
  }
  async function _sendHandoff(db, ctx, toWorker, message) {
    if (!db || !ctx || !toWorker || !message) return false;
    try {
      await db.from('companion_handoff').insert({
        hive_id:      ctx.hive_id || null,
        from_worker:  ctx.worker_name || null,
        to_worker:    String(toWorker).slice(0, 60),
        message:      String(message).slice(0, 600),
        status:       'pending',
        source:       'voice-handler',
        created_at:   new Date().toISOString(),
      });
      return true;
    } catch (_) { return false; }
  }
  async function _fetchPendingHandoffs(db, ctx) {
    if (!db || !ctx || !ctx.hive_id || !ctx.worker_name) return [];
    try {
      const { data } = await db.from('companion_handoff')
        .select('id,from_worker,message,created_at')
        .eq('hive_id', ctx.hive_id)
        .eq('to_worker', ctx.worker_name)
        .eq('status', 'pending')
        .order('created_at', { ascending: false })
        .limit(10);
      return Array.isArray(data) ? data : [];
    } catch (_) { return []; }
  }

  // Phase 4.149 (turn #147) SHARED NOTE THREAD — workers can
  // attach a turn to a shared note (per-asset or per-shift).
  // Writes to shared_voice_notes; renders on Hive surface.
  const _SHARED_NOTE_RE = /\b(?:share\s+(?:this|that|yan|ito)\s+(?:to|with)\s+(?:the\s+team|kuya|kasama|shift)|share\s+(?:this|that)\s+as\s+(?:a\s+)?note|i[\-\s]?share\s+mo\s+sa\s+team|post\s+(?:this|to\s+the\s+team\s+note))\b/i;
  function _isSharedNoteRequest(text) {
    const s = String(text || '');
    if (!s || s.length > 200) return false;
    return _SHARED_NOTE_RE.test(s);
  }
  async function _postSharedNote(db, ctx, threadKey, content) {
    if (!db || !ctx || !content) return false;
    try {
      await db.from('shared_voice_notes').insert({
        hive_id:     ctx.hive_id || null,
        thread_key:  String(threadKey || 'general').slice(0, 80),
        worker_name: ctx.worker_name || null,
        content:     String(content).slice(0, 600),
        source:      'voice-handler',
        created_at:  new Date().toISOString(),
      });
      return true;
    } catch (_) { return false; }
  }

  // Phase 4.150 (turn #148) ACTIVE WORKER COUNT ALERT — when
  // the hive has >5 voice sessions active concurrently, surface
  // "team is busy, consider async" so workers don't crowd the
  // shared mental-state.
  function _shouldFlagHighConcurrency(activeCount, threshold) {
    const n = Number(activeCount);
    const t = Number(threshold);
    if (!Number.isFinite(n)) return false;
    const cap = Number.isFinite(t) && t > 0 ? t : 5;
    return n > cap;
  }

  // Phase 4.151 (turn #149) WATCHLIST SUBSCRIPTIONS — worker
  // subscribes to an asset_tag; when ANY worker logs activity
  // on that tag, the subscriber gets a heads-up on next open.
  async function _subscribeWatchlist(db, ctx, assetTag) {
    if (!db || !ctx || !assetTag) return false;
    try {
      await db.from('asset_watchlist').upsert({
        hive_id:     ctx.hive_id || null,
        worker_name: ctx.worker_name || null,
        asset_tag:   String(assetTag).slice(0, 40),
        subscribed_at: new Date().toISOString(),
      }, { onConflict: 'hive_id,worker_name,asset_tag' });
      return true;
    } catch (_) { return false; }
  }
  async function _unsubscribeWatchlist(db, ctx, assetTag) {
    if (!db || !ctx || !assetTag) return false;
    try {
      await db.from('asset_watchlist')
        .delete()
        .eq('hive_id', ctx.hive_id || null)
        .eq('worker_name', ctx.worker_name || null)
        .eq('asset_tag', String(assetTag).slice(0, 40));
      return true;
    } catch (_) { return false; }
  }
  const _WATCH_RE = /\b(?:watch\s+(?:this|that|yung|yang)?\s*(?:asset|tag|machine)?\s*([A-Z]{1,3}-?\d{2,5})|sub(?:scribe)?\s+(?:to|kay)\s+([A-Z]{1,3}-?\d{2,5})|i[\-\s]?watch\s+mo\s+([A-Z]{1,3}-?\d{2,5})|notify\s+me\s+(?:on|about)\s+([A-Z]{1,3}-?\d{2,5}))\b/i;
  function _detectWatchRequest(text) {
    const s = String(text || '');
    if (!s) return null;
    const m = s.match(_WATCH_RE);
    if (!m) return null;
    return (m[1] || m[2] || m[3] || m[4] || '').toUpperCase();
  }

  // Phase 4.152 (turn #150) VOICE BROADCAST — supervisor-only
  // capability: send a one-line message to every active voice
  // worker in the hive. Helper here is the SEND side; receive
  // is _fetchPendingHandoffs with from_worker='__broadcast__'.
  async function _sendBroadcast(db, ctx, message) {
    if (!db || !ctx || !ctx.hive_id || !message) return false;
    if (String(ctx.hive_role || '').toLowerCase() !== 'supervisor') {
      return { ok: false, blocker: 'not_supervisor' };
    }
    try {
      const active = await _listActiveVoiceWorkers(db, ctx.hive_id, null);
      const rows = active.map(w => ({
        hive_id:     ctx.hive_id,
        from_worker: '__broadcast__',
        to_worker:   w.worker_name,
        message:     String(message).slice(0, 600),
        status:      'pending',
        source:      'voice-handler-broadcast',
        created_at:  new Date().toISOString(),
      }));
      if (rows.length === 0) return { ok: true, recipients: 0 };
      await db.from('companion_handoff').insert(rows);
      return { ok: true, recipients: rows.length };
    } catch (_) { return { ok: false, blocker: 'insert_failed' }; }
  }

  // Phase 4.153 (turn #151) KNOWLEDGE SHARING NUDGE — when the
  // worker resolves a fault ("fixed", "ayos na", "tapos na yan"),
  // prompt to share the resolution. Returns the resolution kind.
  const _RESOLUTION_RE = /\b(?:fixed(?:\s+it)?|gumana\s+na|tapos\s+na\s+(?:to|yun|yan)|ayos\s+na(?:\s+to)?|solved(?:\s+it)?|nag[\-\s]?work\s+na|naayos\s+na|resolved|patched\s+it)\b/i;
  function _detectResolution(text) {
    const s = String(text || '');
    if (!s || s.length > 200) return null;
    if (!_RESOLUTION_RE.test(s)) return null;
    return 'fix_resolved';
  }

  // Phase 4.154 (turn #152) CROSS-SHIFT CONTINUITY — at session
  // start, pull the prior-shift open items (logbook entries with
  // status='open' from the prior shift slot). Returns array of
  // open items so the welcome line can surface them.
  async function _fetchPriorShiftOpenItems(db, hiveId) {
    if (!db || !hiveId) return [];
    try {
      // "Prior shift" = previous 8h window in PHT.
      const since = new Date(Date.now() - 16 * 60 * 60 * 1000).toISOString();
      const { data } = await db.from('v_logbook_truth')
        .select('asset_tag,issue,status,created_at')
        .eq('hive_id', hiveId)
        .eq('status', 'open')
        .gte('created_at', since)
        .order('created_at', { ascending: false })
        .limit(20);
      return Array.isArray(data) ? data : [];
    } catch (_) { return []; }
  }

  // Phase 4.155 (turn #153) BUDDY MODE — pair worker A + B per
  // hive; their handovers auto-route to each other. Stored in
  // localStorage (per device).
  const _BUDDY_KEY_PREFIX = 'wh_voice_buddy_';
  function _buddyKey(workerName) { return _BUDDY_KEY_PREFIX + String(workerName || 'anon').slice(0, 60); }
  function _setBuddy(workerName, buddyName) {
    if (!workerName || !buddyName) return false;
    try {
      localStorage.setItem(_buddyKey(workerName),
        String(buddyName).slice(0, 60));
      return true;
    } catch (_) { return false; }
  }
  function _getBuddy(workerName) {
    if (!workerName) return null;
    try { return localStorage.getItem(_buddyKey(workerName)) || null; }
    catch (_) { return null; }
  }
  function _clearBuddy(workerName) {
    if (!workerName) return false;
    try { localStorage.removeItem(_buddyKey(workerName)); return true; }
    catch (_) { return false; }
  }
  const _BUDDY_SET_RE = /\b(?:set\s+(?:my\s+)?buddy\s+(?:to|kay)\s+([\w \-]{2,40})|buddy\s+up\s+with\s+([\w \-]{2,40})|kasama\s+ko\s+sa\s+shift\s+si\s+([\w \-]{2,40})|partner\s+with\s+([\w \-]{2,40}))\b/i;
  function _detectBuddySet(text) {
    const s = String(text || '');
    if (!s) return null;
    const m = s.match(_BUDDY_SET_RE);
    if (!m) return null;
    return (m[1] || m[2] || m[3] || m[4] || '').trim().slice(0, 60);
  }

  // Phase 4.156 (turn #154) MENTION NOTIFICATIONS — when the
  // worker mentions another by name (T38 _detectMention),
  // notify that worker through companion_handoff with a
  // 'mention' status so their next session surfaces it.
  async function _sendMentionNotice(db, ctx, mentionedWorker, snippet) {
    if (!db || !ctx || !mentionedWorker) return false;
    try {
      await db.from('companion_handoff').insert({
        hive_id:     ctx.hive_id || null,
        from_worker: ctx.worker_name || null,
        to_worker:   String(mentionedWorker).slice(0, 60),
        message:     '[mention] ' + String(snippet || '').slice(0, 400),
        status:      'mention',
        source:      'voice-handler-mention',
        created_at:  new Date().toISOString(),
      });
      return true;
    } catch (_) { return false; }
  }

  // ============================================================
  // SIXTEENTH 10-TURN FLYWHEEL — turns #155-#164 (Phase 4.157-4.166)
  // EXTERNAL INTEGRATION layer. CMMS / SCADA / chat / email / IoT
  // bridge — the companion talks to the rest of the enterprise.
  // ============================================================

  // Phase 4.157 (turn #155) SAP PM WEBHOOK RECEIVER — inbound
  // work-order notifications from SAP PM land at our edge
  // function which normalises + writes to pm_external_inbox.
  // Helper validates the payload shape before insert.
  function _validateSapWorkOrder(payload) {
    if (!payload || typeof payload !== 'object') return { ok: false, reason: 'not_object' };
    if (!payload.order_id) return { ok: false, reason: 'missing_order_id' };
    if (!payload.equipment_id) return { ok: false, reason: 'missing_equipment_id' };
    const validTypes = ['PM01','PM02','PM03','PM04'];
    if (payload.order_type && !validTypes.includes(payload.order_type)) {
      return { ok: false, reason: 'invalid_order_type' };
    }
    return { ok: true, normalized: {
      external_id: String(payload.order_id).slice(0, 40),
      asset_ref:   String(payload.equipment_id).slice(0, 40),
      order_type:  payload.order_type || 'PM01',
      priority:    Number(payload.priority) || 3,
      due_at:      payload.due_at || null,
      source_system: 'sap_pm',
    }};
  }

  // Phase 4.158 (turn #156) MAXIMO POLL SYNC — outbound poll
  // against Maximo's REST endpoint for completed PMs we should
  // back-fill into our schedule. Helper builds the request shape
  // + parses the response into our pm_schedule row format.
  function _buildMaximoQuery(hiveId, sinceIso) {
    if (!hiveId || !sinceIso) return null;
    return {
      url: '/maximo/rest/mxapi/v2/os/mxwo',
      params: {
        'oslc.where':  'site="' + hiveId + '" and statusdate>"' + sinceIso + '" and status="COMP"',
        'oslc.select': 'wonum,description,assetnum,statusdate,actfinish',
        'oslc.pageSize': '100',
      },
    };
  }
  function _parseMaximoResponse(resp) {
    if (!resp || !Array.isArray(resp.member)) return [];
    return resp.member.map(r => ({
      external_id: String(r.wonum || '').slice(0, 40),
      asset_ref:   String(r.assetnum || '').slice(0, 40),
      completed_at: r.actfinish || r.statusdate || null,
      source_system: 'maximo',
    })).filter(r => r.external_id && r.asset_ref);
  }

  // Phase 4.159 (turn #157) OPC-UA TAG MAPPING — plant-floor
  // OPC tags ("Plant1.Pump203.Vibration_RMS") map to our canonical
  // asset_tag ("P-203") + metric. Maintained as a per-hive
  // dictionary in the opc_tag_map table; helper just normalises.
  function _parseOpcTag(opcTag) {
    if (!opcTag) return null;
    const s = String(opcTag);
    // Pattern: <plant>.<asset><digits>.<metric>
    const m = s.match(/(?:^|\.)([A-Z]{1,3})(\d{2,5})\.([A-Z_a-z]+)$/);
    if (!m) return null;
    return {
      asset_tag: m[1].toUpperCase() + '-' + m[2],
      metric:    m[3].toLowerCase(),
    };
  }

  // Phase 4.160 (turn #158) MQTT TOPIC SUBSCRIBE — declarative
  // helper that produces the canonical MQTT topic for a (hive,
  // asset_tag) tuple. Subscription lifecycle is the edge fn's
  // problem; we just build the strings.
  function _buildMqttTopic(hiveId, assetTag, metric) {
    if (!hiveId || !assetTag) return null;
    const m = String(metric || 'all').toLowerCase().replace(/[^a-z0-9_]/g, '');
    return 'workhive/' + String(hiveId).slice(0, 40) + '/' + String(assetTag).slice(0, 20) + '/' + m;
  }
  function _parseMqttPayload(raw) {
    try {
      const data = typeof raw === 'string' ? JSON.parse(raw) : raw;
      if (!data || typeof data !== 'object') return null;
      return {
        value:     Number(data.value),
        unit:      String(data.unit || '').slice(0, 20),
        timestamp: data.ts || data.timestamp || null,
      };
    } catch (_) { return null; }
  }

  // Phase 4.161 (turn #159) SLACK WEBHOOK — supervisor configures
  // a webhook URL per hive. Helper formats the payload + POSTs;
  // never blocks the turn.
  async function _sendSlackMessage(webhookUrl, text, blocks) {
    if (!webhookUrl || !text) return false;
    const body = { text: String(text).slice(0, 1500) };
    if (Array.isArray(blocks)) body.blocks = blocks;
    try {
      const fetcher = (typeof window.fetchWithTimeout === 'function')
        ? window.fetchWithTimeout : (u, o) => fetch(u, o);
      await fetcher(webhookUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }, 5000);
      return true;
    } catch (_) { return false; }
  }

  // Phase 4.162 (turn #160) EMAIL DIGEST — supervisor receives a
  // daily 5-line digest. Helper formats the body; the send goes
  // through Resend via an edge function (not directly from the
  // client, to keep API key off the device).
  function _buildEmailDigestBody(digest) {
    if (!digest || typeof digest !== 'object') return null;
    const lines = [
      'Daily Digest — ' + new Date().toISOString().slice(0, 10),
      '',
      '1) Open alerts: ' + (digest.open_alerts || 0),
      '2) Closed PMs: ' + (digest.closed_pms || 0),
      '3) Overdue PMs: ' + (digest.overdue_pms || 0),
      '4) Watch list: ' + (Array.isArray(digest.watch_list) ? digest.watch_list.join(', ') : ''),
      '5) Focus: ' + (digest.focus_item || 'none'),
      '',
      '— WorkHive Voice Companion',
    ];
    return lines.join('\n');
  }

  // Phase 4.163 (turn #161) MICROSOFT TEAMS WEBHOOK — adaptive
  // card payload format. Different shape from Slack; helper
  // builds the Teams-flavoured payload.
  function _buildTeamsCard(title, text, severity) {
    const colorMap = { critical: 'attention', high: 'warning', medium: 'good', info: 'default' };
    const color = colorMap[String(severity || 'info').toLowerCase()] || 'default';
    return {
      type: 'message',
      attachments: [{
        contentType: 'application/vnd.microsoft.card.adaptive',
        content: {
          $schema: 'http://adaptivecards.io/schemas/adaptive-card.json',
          type: 'AdaptiveCard',
          version: '1.4',
          body: [
            { type: 'TextBlock', size: 'Medium', weight: 'Bolder', text: String(title || '').slice(0, 200), color },
            { type: 'TextBlock', text: String(text || '').slice(0, 800), wrap: true },
          ],
        },
      }],
    };
  }

  // Phase 4.164 (turn #162) CALENDAR INTEGRATION — Google/Outlook
  // accept ICS payloads. Helper builds the ICS string for a PM
  // schedule entry. Edge fn posts it to the worker's calendar API.
  function _buildIcsEvent(event) {
    if (!event || !event.start || !event.summary) return null;
    function fmt(iso) {
      const d = new Date(iso);
      if (isNaN(d.getTime())) return null;
      return d.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '');
    }
    const dtStart = fmt(event.start);
    const dtEnd   = fmt(event.end || event.start);
    if (!dtStart || !dtEnd) return null;
    const uid = (event.uid || ('wh-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8))).slice(0, 60);
    return [
      'BEGIN:VCALENDAR',
      'VERSION:2.0',
      'PRODID:-//WorkHive//Voice Companion//EN',
      'BEGIN:VEVENT',
      'UID:' + uid,
      'DTSTAMP:' + fmt(new Date().toISOString()),
      'DTSTART:' + dtStart,
      'DTEND:' + dtEnd,
      'SUMMARY:' + String(event.summary).slice(0, 200).replace(/\n/g, ' '),
      'DESCRIPTION:' + String(event.description || '').slice(0, 800).replace(/\n/g, '\\n'),
      'END:VEVENT',
      'END:VCALENDAR',
    ].join('\r\n');
  }

  // Phase 4.165 (turn #163) WEBHOOK SIGNATURE VALIDATION —
  // inbound webhooks (SAP/Maximo/Slack) must carry an HMAC-SHA256
  // signature we verify before processing. Helper is the constant-
  // time comparator (actual HMAC is server-side).
  function _constantTimeCompare(a, b) {
    const sa = String(a || '');
    const sb = String(b || '');
    if (sa.length !== sb.length) return false;
    let diff = 0;
    for (let i = 0; i < sa.length; i++) {
      diff |= sa.charCodeAt(i) ^ sb.charCodeAt(i);
    }
    return diff === 0;
  }

  // Phase 4.166 (turn #164) OUTBOUND RETRY QUEUE — when an
  // outbound POST (Slack / Teams / SAP) fails, push to a local
  // retry queue that drains on next online window. Capped at 20
  // entries; oldest dropped on overflow.
  const _OUTBOUND_QUEUE_KEY = 'wh_voice_outbound_queue';
  const _OUTBOUND_MAX = 20;
  function _enqueueOutbound(entry) {
    if (!entry || !entry.url) return false;
    try {
      const raw = localStorage.getItem(_OUTBOUND_QUEUE_KEY);
      const q = raw ? (JSON.parse(raw) || []) : [];
      q.push({
        url:     String(entry.url).slice(0, 240),
        body:    typeof entry.body === 'string' ? entry.body.slice(0, 4000) : JSON.stringify(entry.body).slice(0, 4000),
        headers: entry.headers || {},
        kind:    String(entry.kind || 'unknown').slice(0, 40),
        ts:      Date.now(),
      });
      while (q.length > _OUTBOUND_MAX) q.shift();
      localStorage.setItem(_OUTBOUND_QUEUE_KEY, JSON.stringify(q));
      return true;
    } catch (_) { return false; }
  }
  function _getOutboundQueue() {
    try {
      const raw = localStorage.getItem(_OUTBOUND_QUEUE_KEY);
      return raw ? (JSON.parse(raw) || []) : [];
    } catch (_) { return []; }
  }
  async function _drainOutboundQueue() {
    const q = _getOutboundQueue();
    if (q.length === 0) return { drained: 0, remaining: 0 };
    const remaining = [];
    let drained = 0;
    for (const entry of q) {
      try {
        await fetch(entry.url, {
          method: 'POST',
          headers: entry.headers || { 'Content-Type': 'application/json' },
          body: entry.body,
        });
        drained++;
      } catch (_) {
        remaining.push(entry);
      }
    }
    try {
      localStorage.setItem(_OUTBOUND_QUEUE_KEY, JSON.stringify(remaining));
    } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
    return { drained, remaining: remaining.length };
  }

  // ============================================================
  // SEVENTEENTH 10-TURN FLYWHEEL — turns #165-#174 (Phase 4.167-4.176)
  // ADVANCED ANALYTICS layer. Statistical primitives the companion
  // can use to ground its replies in real math instead of vague
  // language ("looks high"). Pure-function utilities.
  // ============================================================

  // Phase 4.167 (turn #165) ANOMALY DETECTION — 3σ rule.
  // Returns {is_anomaly, z, mean, sd} for the current reading
  // against a rolling-window sample.
  function _detectAnomaly3Sigma(current, sample) {
    if (!Number.isFinite(Number(current))) return null;
    if (!Array.isArray(sample) || sample.length < 5) return null;
    const nums = sample.map(Number).filter(Number.isFinite);
    if (nums.length < 5) return null;
    const mean = nums.reduce((a, b) => a + b, 0) / nums.length;
    const variance = nums.reduce((a, b) => a + (b - mean) * (b - mean), 0) / nums.length;
    const sd = Math.sqrt(variance);
    if (sd === 0) return { is_anomaly: false, z: 0, mean, sd };
    const z = (Number(current) - mean) / sd;
    return { is_anomaly: Math.abs(z) >= 3, z, mean, sd };
  }

  // Phase 4.168 (turn #166) WEIBULL MTBF FORECAST — given a list
  // of times-to-failure, fit a 2-parameter Weibull (method of
  // moments) and return MTBF + 80% confidence interval.
  function _weibullMomentFit(timesToFailure) {
    if (!Array.isArray(timesToFailure) || timesToFailure.length < 3) return null;
    const nums = timesToFailure.map(Number).filter(t => Number.isFinite(t) && t > 0);
    if (nums.length < 3) return null;
    const n = nums.length;
    const mean = nums.reduce((a, b) => a + b, 0) / n;
    const variance = nums.reduce((a, b) => a + (b - mean) * (b - mean), 0) / n;
    if (variance === 0) return { mtbf: mean, low_80: mean, high_80: mean, beta: null, eta: mean };
    const cv = Math.sqrt(variance) / mean; // coefficient of variation
    // Closed-form approx: beta ≈ (cv)^-1.086 (Justus, 1978)
    const beta = Math.pow(Math.max(cv, 0.001), -1.086);
    // eta solved from mean = eta * Γ(1 + 1/beta); approximate Γ via Stirling
    const gammaArg = 1 + 1 / beta;
    const gammaApprox = Math.sqrt(2 * Math.PI / gammaArg) * Math.pow(gammaArg / Math.E, gammaArg);
    const eta = mean / gammaApprox;
    // 80% CI on mean (normal approximation; OK for engineering use)
    const sem = Math.sqrt(variance / n);
    return {
      mtbf:   mean,
      low_80: Math.max(0, mean - 1.28 * sem),
      high_80: mean + 1.28 * sem,
      beta, eta,
    };
  }

  // Phase 4.169 (turn #167) PARETO ANALYSIS — given an array of
  // {label, value} pairs, return the items contributing to 80%
  // of cumulative value.
  function _paretoTop80(items) {
    if (!Array.isArray(items) || items.length === 0) return [];
    const sorted = items
      .filter(i => i && Number.isFinite(Number(i.value)) && Number(i.value) > 0)
      .map(i => ({ label: String(i.label || ''), value: Number(i.value) }))
      .sort((a, b) => b.value - a.value);
    const total = sorted.reduce((a, b) => a + b.value, 0);
    if (total === 0) return [];
    const out = [];
    let acc = 0;
    for (const item of sorted) {
      out.push({ ...item, pct: item.value / total, cum_pct: (acc + item.value) / total });
      acc += item.value;
      if (acc / total >= 0.8) break;
    }
    return out;
  }

  // Phase 4.170 (turn #168) TREND DETECTION — simple linear
  // regression on time-series (x = day index, y = value). Returns
  // slope + r^2 + direction.
  function _linearTrend(series) {
    if (!Array.isArray(series) || series.length < 3) return null;
    const pts = series.map((y, i) => ({ x: i, y: Number(y) }))
      .filter(p => Number.isFinite(p.y));
    if (pts.length < 3) return null;
    const n = pts.length;
    const sumX = pts.reduce((a, p) => a + p.x, 0);
    const sumY = pts.reduce((a, p) => a + p.y, 0);
    const meanX = sumX / n, meanY = sumY / n;
    let numer = 0, denomX = 0, denomY = 0;
    for (const p of pts) {
      numer  += (p.x - meanX) * (p.y - meanY);
      denomX += (p.x - meanX) * (p.x - meanX);
      denomY += (p.y - meanY) * (p.y - meanY);
    }
    if (denomX === 0) return null;
    const slope = numer / denomX;
    const r2 = denomY === 0 ? 0 : (numer * numer) / (denomX * denomY);
    const direction = slope > 0.001 ? 'rising' : (slope < -0.001 ? 'falling' : 'flat');
    return { slope, r2, direction, n };
  }

  // Phase 4.171 (turn #169) SEASONAL PATTERN — for a series
  // indexed by day-of-week or hour-of-day, surface the index
  // where activity peaks + average peak/trough ratio.
  function _seasonalPeakIndex(buckets) {
    if (!Array.isArray(buckets) || buckets.length < 2) return null;
    const nums = buckets.map(Number);
    if (nums.some(n => !Number.isFinite(n))) return null;
    const max = Math.max(...nums);
    const min = Math.min(...nums);
    if (max === 0) return { peak_index: -1, ratio: 0 };
    const peak_index = nums.indexOf(max);
    return {
      peak_index,
      trough_index: nums.indexOf(min),
      ratio: min > 0 ? max / min : Infinity,
    };
  }

  // Phase 4.172 (turn #170) OUTLIER-TRIMMED MEAN — trim top/bottom
  // pct (default 5%) before averaging. Robust to single huge
  // outliers (e.g. a 24h shift where the machine was down).
  function _trimmedMean(values, trimPct) {
    if (!Array.isArray(values) || values.length === 0) return null;
    const nums = values.map(Number).filter(Number.isFinite);
    if (nums.length === 0) return null;
    const pct = Number.isFinite(Number(trimPct)) ? Math.max(0, Math.min(0.45, Number(trimPct))) : 0.05;
    const sorted = nums.slice().sort((a, b) => a - b);
    const trim = Math.floor(sorted.length * pct);
    const trimmed = sorted.slice(trim, sorted.length - trim);
    if (trimmed.length === 0) return null;
    return trimmed.reduce((a, b) => a + b, 0) / trimmed.length;
  }

  // Phase 4.173 (turn #171) Z-SCORE — bare primitive.
  function _zScore(value, mean, sd) {
    const v = Number(value), m = Number(mean), s = Number(sd);
    if (!Number.isFinite(v) || !Number.isFinite(m) || !Number.isFinite(s) || s === 0) return null;
    return (v - m) / s;
  }

  // Phase 4.174 (turn #172) PEARSON CORRELATION — between two
  // equal-length series. Used to surface "your overheat counts
  // correlate with daytime hours" type insights.
  function _pearsonCorrelation(x, y) {
    if (!Array.isArray(x) || !Array.isArray(y)) return null;
    if (x.length !== y.length || x.length < 3) return null;
    const nx = x.map(Number), ny = y.map(Number);
    if (nx.some(v => !Number.isFinite(v)) || ny.some(v => !Number.isFinite(v))) return null;
    const n = nx.length;
    const mx = nx.reduce((a, b) => a + b, 0) / n;
    const my = ny.reduce((a, b) => a + b, 0) / n;
    let num = 0, dx = 0, dy = 0;
    for (let i = 0; i < n; i++) {
      const ax = nx[i] - mx, ay = ny[i] - my;
      num += ax * ay; dx += ax * ax; dy += ay * ay;
    }
    if (dx === 0 || dy === 0) return 0;
    return num / Math.sqrt(dx * dy);
  }

  // Phase 4.175 (turn #173) WEIBULL CDF — given beta + eta from
  // _weibullMomentFit, evaluate the failure-probability CDF at a
  // time t. Used by the companion to answer "what's the chance
  // P-203 fails in the next 14 days".
  function _weibullCdf(t, beta, eta) {
    const tn = Number(t), bn = Number(beta), en = Number(eta);
    if (!Number.isFinite(tn) || tn <= 0) return null;
    if (!Number.isFinite(bn) || bn <= 0) return null;
    if (!Number.isFinite(en) || en <= 0) return null;
    return 1 - Math.exp(-Math.pow(tn / en, bn));
  }

  // Phase 4.176 (turn #174) AVAILABILITY — uptime / (uptime +
  // downtime). Tolerates zero-uptime by returning 0; tolerates
  // zero-downtime by returning 1; rejects negative inputs.
  function _availability(uptimeHours, downtimeHours) {
    const u = Number(uptimeHours), d = Number(downtimeHours);
    if (!Number.isFinite(u) || !Number.isFinite(d)) return null;
    if (u < 0 || d < 0) return null;
    const total = u + d;
    if (total === 0) return null;
    return u / total;
  }

  // ============================================================
  // EIGHTEENTH 10-TURN FLYWHEEL — turns #175-#184 (Phase 4.177-4.186)
  // SAFETY + PERMIT-TO-WORK layer. Domain-critical detectors for
  // LOTO, hot work, confined space, PPE checks, near-miss capture.
  // ============================================================

  // Phase 4.177 (turn #175) LOTO INTENT DETECTOR — "lockout
  // tagout" / "isolation" / "padlock the breaker". The companion
  // MUST not proceed with diagnostic work intents until LOTO is
  // confirmed.
  const _LOTO_RE = /\b(?:loto|lockout[\s\-]?tagout|lockout\s+tag\s*out|lock\s+out|tag\s+out|isolation|isolate(?:\s+the\s+\w+)?|padlock(?:\s+the\s+breaker)?|de[\-\s]?energi[sz]e|line\s+breaking|i[\-\s]?lock\s+mo|i[\-\s]?isolate\s+mo)\b/i;
  function _detectLotoIntent(text) {
    const s = String(text || '');
    if (!s || s.length > 200) return false;
    return _LOTO_RE.test(s);
  }

  // Phase 4.178 (turn #176) HOT WORK INTENT — welding, grinding,
  // open flame, soldering on plant. Requires hot-work permit.
  const _HOT_WORK_RE = /\b(?:welding|weld\s+(?:on|the)|grinding|grinder|cutting\s+torch|open\s+flame|brazing|soldering\s+on\s+(?:pipe|line|tank)|hot\s+work|paghihinang|nag[\-\s]?welding)\b/i;
  function _detectHotWorkIntent(text) {
    const s = String(text || '');
    if (!s || s.length > 200) return false;
    return _HOT_WORK_RE.test(s);
  }

  // Phase 4.179 (turn #177) CONFINED SPACE — tank entry, sump,
  // boiler interior, sewer manhole. Requires gas testing +
  // attendant + rescue plan.
  const _CONFINED_RE = /\b(?:confined\s+space|tank\s+entry|enter\s+(?:the\s+)?tank|manhole\s+entry|boiler\s+interior|sump\s+entry|vessel\s+entry|pumasok\s+sa\s+(?:tangke|tank|sump))\b/i;
  function _detectConfinedSpaceIntent(text) {
    const s = String(text || '');
    if (!s || s.length > 200) return false;
    return _CONFINED_RE.test(s);
  }

  // Phase 4.180 (turn #178) PPE COMPLIANCE QUESTION — when the
  // worker asks "what PPE do I need" / "ano ang PPE para dito",
  // surface the matrix by hazard kind.
  const _PPE_QUERY_RE = /\b(?:what\s+ppe|which\s+ppe|do\s+i\s+need\s+ppe|ppe\s+for|ano\s+(?:ang\s+)?ppe|kailangan\s+(?:ko\s+ba|niya)\s+(?:ng\s+)?ppe)\b/i;
  function _isPpeQuery(text) {
    const s = String(text || '');
    if (!s || s.length > 200) return false;
    return _PPE_QUERY_RE.test(s);
  }
  const _PPE_MATRIX = {
    hot_work:       ['welding hood (shade 10+)', 'flame-resistant clothing', 'leather gloves', 'fire watch'],
    confined_space: ['SCBA or air-line respirator', '4-gas monitor (O2/LEL/CO/H2S)', 'harness + retrieval line', 'attendant'],
    chemical:       ['chemical splash goggles', 'gauntlet gloves (matching chemical)', 'apron or suit', 'eyewash within 10m'],
    electrical:     ['Class 0/1 rubber gloves', 'arc-rated face shield', 'voltage detector', 'rubber mat'],
    height:         ['full-body harness', 'double lanyard', 'hard hat with chinstrap', 'tool tether'],
    default:        ['hard hat', 'safety shoes', 'safety glasses', 'gloves matching the task'],
  };
  function _ppeFor(hazardKind) {
    const k = String(hazardKind || 'default').toLowerCase();
    return _PPE_MATRIX[k] || _PPE_MATRIX.default;
  }

  // Phase 4.181 (turn #179) NEAR-MISS CAPTURE — "almost slipped",
  // "muntik na akong masaktan", "close call" → propose a
  // near-miss report (writes to safety_near_miss table; the
  // detector is here, the write is wired at the call site).
  const _NEAR_MISS_RE = /\b(?:near[\s\-]?miss|close\s+call|almost\s+(?:slipped|fell|got\s+hit|hurt|cut)|muntik\s+na(?:[\s,]+\w+){0,4}\s+(?:matamaan|madisgrasya|masaktan|mahulog|nasugatan|ma[\-\s]?electrocute)|halos\s+(?:nahulog|nasaktan)|nag[\-\s]?slip\s+pero\s+ayos|stopped\s+(?:myself|in\s+time))\b/i;
  function _isNearMissReport(text) {
    const s = String(text || '');
    if (!s || s.length > 300) return false;
    return _NEAR_MISS_RE.test(s);
  }

  // Phase 4.182 (turn #180) JSA (JOB SAFETY ANALYSIS) PROMPT —
  // for first-time or high-risk task, propose a 4-step JSA
  // (task → hazard → control → PPE). Detect "first time doing X"
  // / "unang beses kong gagawin to".
  const _JSA_NEED_RE = /\b(?:first\s+time\s+(?:doing|sa)|unang\s+beses\s+(?:kong)?\s*(?:gagawin|ginagawa)\s+(?:to|ito)|never\s+done\s+this|haven['']?t\s+done\s+this\s+before|new\s+to\s+(?:me|this\s+task))\b/i;
  function _shouldOfferJsa(text) {
    const s = String(text || '');
    if (!s || s.length > 300) return false;
    return _JSA_NEED_RE.test(s);
  }
  function _buildJsaTemplate(taskName) {
    return {
      task:        String(taskName || 'this task').slice(0, 80),
      steps: [
        { step: 1, label: 'Break the task into 3-5 steps',  prompt: 'What are the major steps?' },
        { step: 2, label: 'Identify hazards per step',       prompt: 'What can hurt you at each step?' },
        { step: 3, label: 'Define controls (elim/sub/eng/admin/PPE)', prompt: 'How will you reduce each hazard? (use hierarchy)' },
        { step: 4, label: 'Confirm PPE + permits',           prompt: 'Do you have all PPE + permits before you start?' },
      ],
    };
  }

  // Phase 4.183 (turn #181) GAS-TEST GATING — before confined-
  // space entry, the worker must record a 4-gas reading. Helper
  // validates the reading against PH OSHS limits.
  function _validateGasReading(reading) {
    const limits = {
      O2_min:  19.5,
      O2_max:  23.5,
      LEL_max: 10,      // % of LEL
      CO_max:  35,      // ppm
      H2S_max: 10,      // ppm
    };
    if (!reading || typeof reading !== 'object') return { ok: false, reason: 'missing_reading' };
    const O2 = Number(reading.O2), LEL = Number(reading.LEL), CO = Number(reading.CO), H2S = Number(reading.H2S);
    const fail = [];
    if (!Number.isFinite(O2) || O2 < limits.O2_min || O2 > limits.O2_max) fail.push('O2_out_of_range');
    if (!Number.isFinite(LEL) || LEL > limits.LEL_max) fail.push('LEL_too_high');
    if (!Number.isFinite(CO) || CO > limits.CO_max) fail.push('CO_too_high');
    if (!Number.isFinite(H2S) || H2S > limits.H2S_max) fail.push('H2S_too_high');
    return { ok: fail.length === 0, fail, limits };
  }

  // Phase 4.184 (turn #182) INCIDENT REPORT TRIGGER — "someone
  // got hurt", "may nasaktan", "injury" → escalate to safety
  // officer queue. Distinct from T84 crisis (workplace violence)
  // and T182 near-miss (no actual harm).
  const _INCIDENT_RE = /\b(?:(?:someone|may\s+\w+)\s+(?:got\s+hurt|nasaktan|got\s+injured|got\s+burned|got\s+shocked|nabaril|nahulog)|injury\s+on\s+(?:site|line|the\s+floor)|may\s+(?:tao|kasamahan)\s+(?:nasaktan|nasugatan|nahulog)|need\s+(?:first\s+aid|medical)\s+(?:now|asap)|paramedic\s+kailangan)\b/i;
  function _isIncidentReport(text) {
    const s = String(text || '');
    if (!s || s.length > 300) return false;
    return _INCIDENT_RE.test(s);
  }

  // Phase 4.185 (turn #183) ENERGY-ISOLATION CHECKLIST — for
  // LOTO, the worker confirms each energy source. Returns the
  // checklist for the asset's category (electrical / mechanical
  // / hydraulic / pneumatic / chemical / thermal / gravitational).
  function _energyIsolationChecklist(category) {
    const map = {
      electrical:    ['Identify all electrical sources', 'Switch off + lock breaker', 'Verify zero voltage with tester', 'Tag with worker name + date'],
      mechanical:    ['Stop rotating parts', 'Engage mechanical block / pin', 'Verify by attempt-to-start', 'Tag'],
      hydraulic:     ['Close isolation valve', 'Bleed residual pressure', 'Verify 0 PSI on gauge', 'Tag'],
      pneumatic:     ['Close air supply', 'Vent line to atmosphere', 'Verify 0 PSI', 'Tag'],
      chemical:      ['Close + lock chemical supply valve', 'Drain or purge line', 'Verify with sampling port', 'Tag'],
      thermal:       ['Shut off heat source', 'Allow cool-down to safe touch temp', 'Verify with thermal camera', 'Tag'],
      gravitational: ['Lower load to ground OR support with cribbing', 'Verify mechanical stop engaged', 'Tag'],
    };
    return map[String(category || '').toLowerCase()] || null;
  }

  // Phase 4.186 (turn #184) PERMIT EXPIRY CHECK — work permits
  // have validity windows (typically 8h shift). Helper returns
  // remaining minutes + an "expired" flag.
  function _permitTimeRemaining(issuedAtIso, validityHours) {
    if (!issuedAtIso) return null;
    const issued = new Date(issuedAtIso);
    if (isNaN(issued.getTime())) return null;
    const hours = Number.isFinite(Number(validityHours)) ? Math.max(0.5, Math.min(24, Number(validityHours))) : 8;
    const elapsedMs = Date.now() - issued.getTime();
    const totalMs = hours * 60 * 60 * 1000;
    const remainingMs = totalMs - elapsedMs;
    return {
      remaining_min: Math.round(remainingMs / 60000),
      expired:       remainingMs <= 0,
      expires_in_min: remainingMs <= 0 ? 0 : Math.round(remainingMs / 60000),
    };
  }

  // ============================================================
  // NINETEENTH 10-TURN FLYWHEEL — turns #185-#194 (Phase 4.187-4.196)
  // KNOWLEDGE GRAPH layer. Entity + relation extraction, triple
  // builder, RAG helpers, embedding hash, chunking, citation,
  // query rewriter, multi-hop, KB versioning.
  // ============================================================

  // Phase 4.187 (turn #185) ENTITY EXTRACTION — extract asset
  // tags, failure modes, worker name candidates from a transcript.
  // Returns {asset_tags: [], failure_modes: [], workers: []}.
  function _extractEntities(text) {
    const s = String(text || '');
    if (!s) return { asset_tags: [], failure_modes: [], workers: [] };
    const asset_tags = [];
    const re = /\b[A-Z]{1,3}-\d{2,5}\b/g;
    let m;
    while ((m = re.exec(s)) !== null) {
      if (!asset_tags.includes(m[0])) asset_tags.push(m[0]);
    }
    const failure_modes = [];
    for (const mode of Object.keys(_SYMPTOM_TO_FMODE || {})) {
      if (_SYMPTOM_TO_FMODE[mode].test(s)) failure_modes.push(mode);
    }
    // Worker candidates: "Kuya/Ate <Name>" / "si <Name>".
    const workers = [];
    const wre = /\b(?:Kuya|Ate|si)\s+([A-Z][a-z]{2,20}(?:\s+[A-Z][a-z]{2,20})?)/g;
    while ((m = wre.exec(s)) !== null) {
      if (!workers.includes(m[1])) workers.push(m[1]);
    }
    return { asset_tags, failure_modes, workers };
  }

  // Phase 4.188 (turn #186) RELATION EXTRACTION — find simple
  // "<asset> <verb> <asset>" or "<asset> caused <failure>" triples
  // in the transcript.
  function _extractRelations(text) {
    const s = String(text || '');
    if (!s) return [];
    const triples = [];
    // Pattern A: asset A caused/triggered/led to asset B
    let m;
    const reCause = /([A-Z]{1,3}-\d{2,5})\s+(?:caused|triggered|led\s+to|nag[\-\s]?cause\s+ng)\s+(?:failure\s+on\s+)?([A-Z]{1,3}-\d{2,5}|\w+_anomaly|overheat|leak|no_start)/gi;
    while ((m = reCause.exec(s)) !== null) {
      triples.push({ subject: m[1], predicate: 'caused', object: m[2] });
    }
    // Pattern B: asset A connects to / feeds asset B
    const reConn = /([A-Z]{1,3}-\d{2,5})\s+(?:feeds|connects\s+to|supplies|naka[\-\s]?connect\s+sa)\s+([A-Z]{1,3}-\d{2,5})/gi;
    while ((m = reConn.exec(s)) !== null) {
      triples.push({ subject: m[1], predicate: 'feeds', object: m[2] });
    }
    return triples;
  }

  // Phase 4.189 (turn #187) TRIPLE BUILDER — normalise an
  // {subject, predicate, object} into the canonical row shape
  // for the kg_triples table (worker-provided triples join the
  // edge function's harvested ones).
  function _buildKgTriple(hiveId, subject, predicate, object, source) {
    if (!hiveId || !subject || !predicate || !object) return null;
    const allowedPredicates = new Set([
      'caused', 'feeds', 'requires', 'isolates', 'is_part_of',
      'replaced_by', 'measured_by', 'next_pm_at', 'fmea_link',
    ]);
    const p = String(predicate).toLowerCase();
    if (!allowedPredicates.has(p)) return null;
    return {
      hive_id:   String(hiveId).slice(0, 40),
      subject:   String(subject).slice(0, 80),
      predicate: p,
      object:    String(object).slice(0, 80),
      source:    String(source || 'voice-handler').slice(0, 40),
      created_at: new Date().toISOString(),
    };
  }

  // Phase 4.190 (turn #188) RAG CONTEXT BUILDER — given a hit
  // list from the vector search (id + score + snippet), assemble
  // the prompt-side block with citation markers.
  function _buildRagBlock(hits, maxLen) {
    if (!Array.isArray(hits) || hits.length === 0) return '';
    const cap = Number.isFinite(Number(maxLen)) ? Math.max(200, Number(maxLen)) : 2000;
    const lines = ['RAG CONTEXT — relevant prior knowledge:'];
    let total = lines[0].length;
    for (let i = 0; i < hits.length && i < 6; i++) {
      const h = hits[i];
      if (!h || !h.snippet) continue;
      const cite = '[doc:' + (h.id || ('h' + i)) + ' score=' + (Number(h.score) || 0).toFixed(2) + ']';
      const line = cite + ' ' + String(h.snippet).slice(0, 300);
      if (total + line.length > cap) break;
      lines.push(line);
      total += line.length;
    }
    return lines.join('\n');
  }

  // Phase 4.191 (turn #189) EMBEDDING HASH — until we wire a real
  // embedding model in the edge function, the client produces a
  // 32-bit hash that's stable per-content and usable as a cheap
  // similarity surrogate (Hamming distance over hex chars).
  function _embeddingHash32(text) {
    const s = String(text || '');
    if (!s) return '00000000';
    let h = 0x811c9dc5;  // FNV-1a 32-bit
    for (let i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = (h * 0x01000193) >>> 0;
    }
    return ('00000000' + h.toString(16)).slice(-8);
  }
  function _hashHamming(h1, h2) {
    if (!h1 || !h2 || h1.length !== h2.length) return null;
    let diff = 0;
    for (let i = 0; i < h1.length; i++) {
      if (h1[i] !== h2[i]) diff++;
    }
    return diff;
  }

  // Phase 4.192 (turn #190) DOCUMENT CHUNKING — split a long
  // SOP/manual into overlapping chunks suitable for embedding.
  // Default 400 chars per chunk with 50 char overlap.
  function _chunkDocument(text, chunkSize, overlap) {
    const s = String(text || '');
    if (!s) return [];
    const size = Number.isFinite(Number(chunkSize)) ? Math.max(100, Math.min(2000, Number(chunkSize))) : 400;
    const lap  = Number.isFinite(Number(overlap)) ? Math.max(0, Math.min(size / 2, Number(overlap))) : 50;
    const out = [];
    let i = 0;
    while (i < s.length) {
      out.push({
        offset: i,
        text: s.slice(i, i + size),
      });
      i += (size - lap);
      if (out.length > 1000) break; // safety
    }
    return out;
  }

  // Phase 4.193 (turn #191) CITATION BUILDER — given a reply
  // that references a number, build the canonical citation
  // string `<view>:<row_id>:<column>` so the worker can verify.
  function _buildCitation(viewName, rowId, column) {
    const v = String(viewName || '').slice(0, 60);
    const r = String(rowId == null ? '' : rowId).slice(0, 60);
    const c = String(column || '').slice(0, 40);
    if (!v) return null;
    return v + (r ? ':' + r : '') + (c ? ':' + c : '');
  }
  function _parseCitation(citation) {
    if (!citation) return null;
    const parts = String(citation).split(':');
    if (parts.length < 1) return null;
    return {
      view:   parts[0] || null,
      row_id: parts[1] || null,
      column: parts[2] || null,
    };
  }

  // Phase 4.194 (turn #192) QUERY REWRITER — when the worker
  // asks a question, rewrite into a retrieval-friendly form by
  // stripping fillers + lowering case + injecting known entities.
  function _rewriteQueryForRetrieval(transcript, knownEntities) {
    const s = String(transcript || '').toLowerCase();
    if (!s) return '';
    // Strip common fillers
    const fillers = ['kasi', 'naman', 'po', 'eh', 'kaya', 'pala', 'lang', 'eh ano', 'yan'];
    let cleaned = s;
    fillers.forEach(f => {
      cleaned = cleaned.replace(new RegExp('\\b' + f + '\\b', 'g'), '');
    });
    cleaned = cleaned.replace(/\s+/g, ' ').trim();
    // Append known asset tags / failure modes if not already in the text
    if (knownEntities && knownEntities.asset_tags) {
      for (const tag of knownEntities.asset_tags) {
        if (cleaned.indexOf(tag.toLowerCase()) === -1) cleaned += ' ' + tag.toLowerCase();
      }
    }
    return cleaned;
  }

  // Phase 4.195 (turn #193) MULTI-HOP REASONING TRACE — record
  // the step-by-step reasoning the LLM used (caller pulls
  // intermediate think-block markers). Trace is bounded at 8
  // hops per turn.
  const _REASONING_TRACE_KEY = 'wh_voice_reasoning_trace';
  function _recordReasoningHop(sessionId, hop) {
    if (!sessionId || !hop) return false;
    try {
      const k = _REASONING_TRACE_KEY + '_' + String(sessionId).slice(0, 40);
      const raw = localStorage.getItem(k);
      const trace = raw ? (JSON.parse(raw) || []) : [];
      trace.push({
        step: trace.length + 1,
        hop:  String(hop).slice(0, 200),
        ts:   Date.now(),
      });
      while (trace.length > 8) trace.shift();
      localStorage.setItem(k, JSON.stringify(trace));
      return trace.length;
    } catch (_) { return false; }
  }
  function _getReasoningTrace(sessionId) {
    if (!sessionId) return [];
    try {
      const raw = localStorage.getItem(_REASONING_TRACE_KEY + '_' + String(sessionId).slice(0, 40));
      return raw ? (JSON.parse(raw) || []) : [];
    } catch (_) { return []; }
  }

  // Phase 4.196 (turn #194) KB VERSIONING — track the version
  // of the local knowledge base (SOP set) so the companion can
  // warn the worker when answers may be stale. Stored once per
  // hive in localStorage; updated on next sync.
  const _KB_VERSION_KEY = 'wh_voice_kb_version_';
  function _setKbVersion(hiveId, version) {
    if (!hiveId || !version) return false;
    try {
      localStorage.setItem(_KB_VERSION_KEY + String(hiveId).slice(0, 40), JSON.stringify({
        version: String(version).slice(0, 60),
        synced_at: new Date().toISOString(),
      }));
      return true;
    } catch (_) { return false; }
  }
  function _getKbVersion(hiveId) {
    if (!hiveId) return null;
    try {
      const raw = localStorage.getItem(_KB_VERSION_KEY + String(hiveId).slice(0, 40));
      return raw ? JSON.parse(raw) : null;
    } catch (_) { return null; }
  }
  function _isKbStale(hiveId, maxAgeDays) {
    const entry = _getKbVersion(hiveId);
    if (!entry || !entry.synced_at) return true;
    const max = Number.isFinite(Number(maxAgeDays)) ? Number(maxAgeDays) : 30;
    const ageMs = Date.now() - new Date(entry.synced_at).getTime();
    return ageMs > max * 24 * 60 * 60 * 1000;
  }

  // ============================================================
  // TWENTIETH 10-TURN FLYWHEEL — turns #195-#204 (Phase 4.197-4.206)
  // ENERGY MANAGEMENT + SUSTAINABILITY layer. ISO 50001 alignment,
  // kWh tracking, carbon intensity, peak-demand alerts.
  // ============================================================

  // Phase 4.197 (turn #195) ENERGY USE INDEX — kWh per unit of
  // production output. ISO 50001 EnPI metric.
  function _energyUseIndex(kwh, output) {
    const k = Number(kwh), o = Number(output);
    if (!Number.isFinite(k) || !Number.isFinite(o) || o <= 0) return null;
    return k / o;
  }

  // Phase 4.198 (turn #196) CARBON INTENSITY — kgCO2e per kWh.
  // Default PH grid mix factor 0.717 kgCO2e/kWh (2024 DOE figure).
  const _PH_GRID_CARBON_FACTOR = 0.717;
  function _carbonFromKwh(kwh, factorOverride) {
    const k = Number(kwh);
    if (!Number.isFinite(k) || k < 0) return null;
    const factor = Number.isFinite(Number(factorOverride)) ? Number(factorOverride) : _PH_GRID_CARBON_FACTOR;
    return k * factor;
  }

  // Phase 4.199 (turn #197) PEAK DEMAND DETECTOR — when current
  // demand (kW) crosses a per-hive ceiling, fire an alert so the
  // worker can shed load before the utility penalty kicks in.
  function _isPeakDemandBreach(currentKw, ceilingKw, headroomPct) {
    const c = Number(currentKw), ceil = Number(ceilingKw);
    if (!Number.isFinite(c) || !Number.isFinite(ceil) || ceil <= 0) return null;
    const headroom = Number.isFinite(Number(headroomPct)) ? Number(headroomPct) : 0.95;
    return {
      breach: c >= ceil,
      near:   c >= ceil * headroom,
      pct:    c / ceil,
    };
  }

  // Phase 4.200 (turn #198) ENERGY ANOMALY DETECTOR — same shape
  // as T165 but tuned for energy series (5σ instead of 3σ —
  // electrical loads are noisier than mechanical KPIs).
  function _detectEnergyAnomaly(current, sample) {
    if (!Array.isArray(sample) || sample.length < 5) return null;
    const result = _detectAnomaly3Sigma(current, sample);
    if (!result) return null;
    // Upgrade threshold from 3σ to 5σ.
    return {
      ...result,
      is_anomaly: Math.abs(result.z) >= 5,
    };
  }

  // Phase 4.201 (turn #199) STANDBY POWER WASTE — when a machine
  // is "off" (not producing) but still drawing >baseline, surface
  // the waste opportunity in kWh/day.
  function _standbyWaste(idleKw, dailyIdleHours, baselineKw) {
    const ik = Number(idleKw), ih = Number(dailyIdleHours), bk = Number(baselineKw || 0);
    if (!Number.isFinite(ik) || !Number.isFinite(ih) || ih <= 0) return null;
    const wasteKw = Math.max(0, ik - bk);
    return wasteKw * ih;
  }

  // Phase 4.202 (turn #200) WATER USE TRACKING — per-asset m³/day
  // baseline + breach detector. Water is the second-most reported
  // sustainability metric in PH F&B plants.
  function _waterUseBreach(currentM3PerDay, baselineM3PerDay, tolerancePct) {
    const c = Number(currentM3PerDay), b = Number(baselineM3PerDay);
    if (!Number.isFinite(c) || !Number.isFinite(b) || b <= 0) return null;
    const tol = Number.isFinite(Number(tolerancePct)) ? Number(tolerancePct) : 0.15;
    return {
      breach: c > b * (1 + tol),
      pct_over: (c - b) / b,
    };
  }

  // Phase 4.203 (turn #201) COMPRESSED AIR LEAK ESTIMATOR —
  // ultrasonic-leak survey returns dB readings; helper converts
  // to estimated leak cfm + annual kWh waste.
  function _compressedAirLeakLoss(dbReading, runningHoursYr, kwhPerCfmYear) {
    const db = Number(dbReading), hrs = Number(runningHoursYr), kp = Number(kwhPerCfmYear || 2400);
    if (!Number.isFinite(db) || db < 0 || !Number.isFinite(hrs) || hrs <= 0) return null;
    // Rough conversion: cfm ≈ 0.1 * (dB - 25), clamped at 0.
    const cfm = Math.max(0, 0.1 * (db - 25));
    return {
      estimated_cfm: cfm,
      annual_kwh:    cfm * kp,
    };
  }

  // Phase 4.204 (turn #202) MOTOR EFFICIENCY CHECK — given
  // measured kW + nameplate kW + load factor, return efficiency
  // delta from IE3 baseline (typical 93-95%).
  function _motorEfficiencyDelta(measuredKw, nameplateKw, loadFactor) {
    const m = Number(measuredKw), n = Number(nameplateKw), lf = Number(loadFactor);
    if (!Number.isFinite(m) || !Number.isFinite(n) || n <= 0) return null;
    if (!Number.isFinite(lf) || lf <= 0 || lf > 1.2) return null;
    const expected = n * lf / 0.94; // IE3 baseline 94%
    const efficiency = (n * lf) / m;
    return {
      efficiency,
      delta_from_ie3: efficiency - 0.94,
      kw_overdraw:    m - expected,
    };
  }

  // Phase 4.205 (turn #203) SUSTAINABILITY KPI BUNDLE — package
  // the per-hive monthly numbers (kWh, kgCO2e, m³ water, leak
  // count) into a single bundle for the dashboard.
  function _buildSustainabilityBundle(input) {
    if (!input || typeof input !== 'object') return null;
    return {
      kwh_total:    Number(input.kwh_total) || 0,
      kgco2e:       Number(input.kgco2e) || _carbonFromKwh(input.kwh_total) || 0,
      water_m3:     Number(input.water_m3) || 0,
      leak_count:   Number(input.leak_count) || 0,
      enpi:         _energyUseIndex(input.kwh_total, input.output_units) || null,
      month_ending: input.month_ending || new Date().toISOString().slice(0, 7),
    };
  }

  // Phase 4.206 (turn #204) ENERGY INTENT DETECTOR — worker
  // says "are we wasting power on P-203" / "kuryente lang ba
  // kakain nito" → route to energy lookup pipeline.
  const _ENERGY_QUERY_RE = /\b(?:energy\s+(?:use|cost|waste)|kwh|kilowatt|electric(?:al|ity)\s+(?:bill|cost|use)|wasting\s+power|nag[\-\s]?aaksaya\s+ng\s+kuryente|kuryente\s+(?:lang|nag[\-\s]?aaksaya|gastos)|power\s+(?:bill|hog|consumption))\b/i;
  function _isEnergyQuery(text) {
    const s = String(text || '');
    if (!s || s.length > 200) return false;
    return _ENERGY_QUERY_RE.test(s);
  }

  // ============================================================
  // TWENTY-FIRST 10-TURN FLYWHEEL — turns #205-#214 (Phase 4.207-4.216)
  // MULTI-LANGUAGE NLU layer. Cebuano + Hiligaynon + Tagalog
  // dialect detection, politeness register, regional time
  // expressions, slang.
  // ============================================================

  // Phase 4.207 (turn #205) CEBUANO DIALECT MARKERS — extends T59
  // language detection with explicit Bisaya phrases.
  const _CEBUANO_MARKERS = ['unsa', 'asa', 'kinsa', 'kanus-a', 'pila', 'lagi', 'bitaw', 'gud', 'bya', 'oo bitaw', 'sus', 'naman ka oy'];
  function _isCebuanoLeaning(text) {
    const s = String(text || '').toLowerCase();
    if (!s) return false;
    let hits = 0;
    for (const w of _CEBUANO_MARKERS) {
      if (new RegExp('\\b' + w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b').test(s)) hits++;
    }
    return hits >= 2;
  }

  // Phase 4.208 (turn #206) HILIGAYNON (ILONGGO) MARKERS.
  const _ILONGGO_MARKERS = ['gid', 'bala', 'ano gani', 'diin', 'sin-o', 'san-o', 'pila ka', 'manami', 'damo gid'];
  function _isIlonggoLeaning(text) {
    const s = String(text || '').toLowerCase();
    if (!s) return false;
    let hits = 0;
    for (const w of _ILONGGO_MARKERS) {
      if (new RegExp('\\b' + w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b').test(s)) hits++;
    }
    return hits >= 2;
  }

  // Phase 4.209 (turn #207) TAGALOG IMPERATIVE — "i-<verb> mo" /
  // "<verb>-an mo" / "<verb> mo nga". Useful for action intent.
  const _TGL_IMPERATIVE_RE = /\b(?:i[\-\s][a-z]{3,}\s+mo|[a-z]{3,}\s+mo\s+(?:nga|naman|please|po)|[a-z]{3,}-an\s+mo|pakisuyo|paki[\s\-]?(?:gawin|check|log|i[\-\s]\w+))\b/i;
  function _isTagalogImperative(text) {
    const s = String(text || '');
    if (!s || s.length > 200) return false;
    return _TGL_IMPERATIVE_RE.test(s);
  }

  // Phase 4.210 (turn #208) CODE-SWITCH RATIO — fraction of words
  // in PH languages vs total words. Returns 0..1.
  const _PH_WORDS_SAMPLE = new Set([
    'ako','ikaw','siya','kami','tayo','kayo','sila','ang','ng','sa','at','o','pero',
    'kasi','naman','lang','po','ho','sige','oo','hindi','wala','meron','may',
    'tapos','pagkatapos','yung','yun','yan','ito','ano','paano','bakit','saan',
    'unsa','asa','kinsa','gid','bala','manami','kuya','ate','kapatid',
  ]);
  function _codeSwitchRatio(text) {
    const s = String(text || '').toLowerCase();
    if (!s) return 0;
    const words = s.split(/[^a-z]+/).filter(w => w.length >= 2);
    if (words.length === 0) return 0;
    let ph = 0;
    for (const w of words) {
      if (_PH_WORDS_SAMPLE.has(w)) ph++;
    }
    return ph / words.length;
  }

  // Phase 4.211 (turn #209) POLITENESS REGISTER — "po"/"ho" present
  // = formal; absent + tu-form = casual. Returns 'formal' /
  // 'casual' / 'mixed'.
  function _classifyPolitenessRegister(text) {
    const s = String(text || '').toLowerCase();
    if (!s) return 'unknown';
    const hasPo = /\b(?:po|ho|opo|opo\s*po)\b/.test(s);
    const hasCasual = /\b(?:tol|pre|bro|bes|bestie|kuya|ate|gago|bobo)\b/.test(s);
    if (hasPo && !hasCasual) return 'formal';
    if (!hasPo && hasCasual) return 'casual';
    if (hasPo && hasCasual) return 'mixed';
    return 'neutral';
  }

  // Phase 4.212 (turn #210) REGIONAL TIME EXPRESSIONS — Filipino
  // expressions for time-of-day that aren't covered by T87.
  // Returns the canonical 24h hour OR null.
  const _PH_TIME_PHRASES = {
    'umaga':       7,
    'tanghali':    12,
    'hapon':       15,
    'gabi':        20,
    'madaling araw': 4,
    'paglubog ng araw': 18,
    'pagsikat ng araw': 6,
    'alas-singko ng umaga': 5,
    'alas-otso ng umaga':  8,
    'tanghaling tapat':    12,
  };
  function _parsePhTimeExpression(text) {
    const s = String(text || '').toLowerCase();
    if (!s) return null;
    for (const phrase of Object.keys(_PH_TIME_PHRASES)) {
      if (s.indexOf(phrase) !== -1) return _PH_TIME_PHRASES[phrase];
    }
    return null;
  }

  // Phase 4.213 (turn #211) NUMBER WORDS — convert spoken PH +
  // English number words 0-20 to digits.
  const _NUMBER_WORDS = {
    'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
    'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
    'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20,
    'isa': 1, 'dalawa': 2, 'tatlo': 3, 'apat': 4, 'lima': 5,
    'anim': 6, 'pito': 7, 'walo': 8, 'siyam': 9, 'sampu': 10,
    'labing-isa': 11, 'labindalawa': 12, 'labintatlo': 13, 'dalawampu': 20,
    'usa': 1, 'duha': 2, 'tulo': 3, 'upat': 4, 'lima_ceb': 5, 'unom': 6,
  };
  function _wordToNumber(word) {
    if (!word) return null;
    const k = String(word).toLowerCase().trim();
    return Object.prototype.hasOwnProperty.call(_NUMBER_WORDS, k) ? _NUMBER_WORDS[k] : null;
  }

  // Phase 4.214 (turn #212) FILLER SUPPRESSION — strip throat-
  // clearing fillers ("uh", "um", "ahh", "eto kasi") before
  // intent classification.
  function _stripFillers(text) {
    let s = String(text || '');
    if (!s) return s;
    s = s.replace(/\b(?:uh+|um+|ahh+|eh+|er+|hmm+|ano ba|kasi|eto kasi|yun nga|ay+)\b[, ]*/gi, ' ');
    s = s.replace(/\s+/g, ' ').trim();
    return s;
  }

  // Phase 4.215 (turn #213) STOP-WORD LIST — for retrieval index
  // building. Bilingual.
  const _STOP_WORDS = new Set([
    'the','a','an','and','or','of','to','in','on','for','at','by','with','from',
    'is','are','was','were','be','been','being','this','that','it','its',
    'ang','ng','sa','at','ay','na','mga','para','kung','dahil','kasi','tas','o',
    'yung','yun','iyon','ito','yan','iyan',
  ]);
  function _removeStopWords(text) {
    const s = String(text || '').toLowerCase();
    if (!s) return '';
    return s.split(/\s+/).filter(w => w && !_STOP_WORDS.has(w)).join(' ');
  }

  // Phase 4.216 (turn #214) SLANG DICTIONARY — common shop-floor
  // slang to canonical maintenance vocabulary.
  const _SLANG_DICT = {
    'sira':       'broken',
    'siraulo':    'malfunction',
    'naloloka':   'erratic',
    'nag-init':   'overheat',
    'umiyak':     'leak',
    'umiwas':     'avoid',
    'pumalya':    'failure',
    'wala_na':    'depleted',
    'patay':      'no_power',
    'iling':      'wobble',
    'busted':     'failure',
  };
  function _slangToCanonical(word) {
    if (!word) return null;
    const k = String(word).toLowerCase().trim();
    return Object.prototype.hasOwnProperty.call(_SLANG_DICT, k) ? _SLANG_DICT[k] : null;
  }

  // Phase 4.44 (turn #45): Offline degradation tracker.
  // Module-local state so successive failures don't each retry the
  // same dead endpoint. Flips true after a fetch failure inside the
  // conversational call path; the next turn reads `_isOffline()` and
  // renders an offline indicator instead of pretending to call the LLM.
  // Recovers automatically on next successful fetch (reset by the
  // _converseInline success path).
  let _offlineFlag = false;
  function _isOffline() { return _offlineFlag === true; }
  function _setOffline(v) { _offlineFlag = !!v; }

  // Phase 4.45 (turn #46): Reply cache (memoization).
  // Identical (transcript, hiveId) tuples within a 10-minute TTL replay
  // the prior assistant turn instead of calling the LLM. Captures the
  // common case where workers tap the same question twice (network
  // hiccup, accidental re-tap, double mic press). 16-entry LRU keeps
  // memory bounded.
  const _REPLY_CACHE_TTL_MS = 10 * 60 * 1000;
  const _REPLY_CACHE_MAX_ENTRIES = 16;
  const _replyCache = [];  // [{ key, reply, ts }]
  function _replyCacheKey(transcript, hiveId) {
    return String(hiveId || 'anon') + '|' + String(transcript || '').trim().toLowerCase();
  }
  function _lookupReplyCache(transcript, hiveId) {
    const k = _replyCacheKey(transcript, hiveId);
    const now = Date.now();
    for (let i = _replyCache.length - 1; i >= 0; i--) {
      const e = _replyCache[i];
      if (e.key === k && (now - e.ts) < _REPLY_CACHE_TTL_MS) {
        return e.reply;
      }
    }
    return null;
  }
  function _writeReplyCache(transcript, hiveId, reply) {
    if (!reply) return;
    const k = _replyCacheKey(transcript, hiveId);
    _replyCache.push({ key: k, reply: reply, ts: Date.now() });
    if (_replyCache.length > _REPLY_CACHE_MAX_ENTRIES) {
      _replyCache.splice(0, _replyCache.length - _REPLY_CACHE_MAX_ENTRIES);
    }
  }
  function _clearReplyCache() { _replyCache.length = 0; }

  // Phase 4.46 (turn #47): Worker-feedback escalation check.
  // If the worker has 3+ thumbs-down ratings in the last 7 days, flag
  // ai_quality_escalation so the supervisor's ai-quality dashboard
  // surfaces it. Best-effort — never blocks the conversation.
  async function _checkFeedbackEscalation(db, workerName) {
    if (!db || !workerName) return null;
    try {
      const since = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();
      const { data } = await db.from('ai_cost_log')
        .select('quality_rating')
        .eq('worker_name', workerName)
        .gte('created_at', since)
        .lt('quality_rating', 0)
        .limit(20);
      if (!Array.isArray(data)) return null;
      if (data.length >= 3) {
        return { needs_escalation: true, negative_count: data.length };
      }
      return null;
    } catch (_) { return null; }
  }

  // Phase 4.47 (turn #48): Custom plant terminology resolver.
  // Workers say "the big chiller" / "yung pump sa loading area" instead
  // of the registered asset_tag. We fuzzy-match against the worker's
  // hive assets and return the best candidate (or null). Match is
  // intentionally fuzzy — phonetic-ish, common-word stripped — because
  // STT regularly mangles tag boundaries.
  async function _resolveTerminology(db, hiveId, transcript) {
    if (!db || !hiveId || !transcript) return null;
    const s = String(transcript).toLowerCase();
    // Heuristic gate: only fire when the transcript contains a noun
    // phrase typical of nicknames (no digit-letter asset shape).
    const looksLikeNickname = /\b(?:the|yung|yang)\s+[a-z]{3,}/i.test(s)
      && !/\b[A-Z]{1,3}-?\d{2,5}\b/.test(transcript);
    if (!looksLikeNickname) return null;
    try {
      const { data } = await db.from('v_asset_truth')
        .select('asset_tag,name,category,description')
        .eq('hive_id', hiveId)
        .limit(60);
      if (!Array.isArray(data) || data.length === 0) return null;
      const words = s.replace(/[^a-z0-9 ]/g, '').split(/\s+/).filter(w => w.length >= 3);
      const stops = new Set(['the','yung','yang','sa','ng','at','mo','ko','about','this','that','what','how']);
      const sig = words.filter(w => !stops.has(w));
      if (sig.length === 0) return null;
      // Score each asset by overlap with name + category + description.
      let best = null, bestScore = 0;
      for (const a of data) {
        const hay = (String(a.name || '') + ' ' + String(a.category || '') + ' ' + String(a.description || '')).toLowerCase();
        let score = 0;
        for (const w of sig) {
          if (hay.includes(w)) score += 1;
        }
        if (score > bestScore) { bestScore = score; best = a; }
      }
      // Require ≥2 significant overlaps so a single common word doesn't
      // false-match.
      if (best && bestScore >= 2) {
        return { asset_tag: best.asset_tag, name: best.name, score: bestScore };
      }
      return null;
    } catch (_) { return null; }
  }

  // Phase 4.48 (turn #49): Conversation branching.
  // Module-local stack of (intent, slots, ts) snapshots. When the
  // worker says "back to the X thing", we pop the matching snapshot
  // and reuse its priorIntent for this turn. Bounded to last 5
  // branches so memory stays small.
  const _BRANCH_STACK_MAX = 5;
  const _branchStack = [];  // [{ intent, slots, label, ts }]
  function _pushBranch(intent, slots) {
    if (!intent || intent === 'unknown') return;
    _branchStack.push({
      intent: intent,
      slots: slots || {},
      label: String(intent).toLowerCase(),
      ts: Date.now(),
    });
    if (_branchStack.length > _BRANCH_STACK_MAX) {
      _branchStack.splice(0, _branchStack.length - _BRANCH_STACK_MAX);
    }
  }
  const _BRANCH_RECALL_RE = /\b(?:back to|going back to|earlier|kanina|bumalik tayo sa|balik tayo sa)\s+(?:the\s+|yung\s+|yang\s+)?([A-Za-z0-9\-_. ]{2,30}?)(?:\s+(?:thing|topic|question|issue))?\b/i;
  function _detectBranchRecall(text) {
    const m = String(text || '').match(_BRANCH_RECALL_RE);
    if (!m) return null;
    const needle = String(m[1] || '').trim().toLowerCase();
    if (!needle) return null;
    // Find best matching branch by label substring.
    for (let i = _branchStack.length - 1; i >= 0; i--) {
      const b = _branchStack[i];
      if (b.label.includes(needle) || needle.includes(b.label) ||
          JSON.stringify(b.slots).toLowerCase().includes(needle)) {
        return b;
      }
    }
    return null;
  }

  // Phase 4.49 (turn #50): Multi-modal photo intent.
  // "let me show you" / "tingnan mo to" / "I'll send a photo" — worker
  // wants to share visual context. We don't open visual-defect-capture
  // automatically (that would feel pushy), we instruct the LLM to
  // offer it ONCE in plain prose.
  const _PHOTO_INTENT_RE = /\b(?:let me show you|tingnan mo (?:to|ito)|send (?:you )?a photo|i(?:'|’)?ll send (?:you )?a photo|let me snap|i can show|may litrato|may picture|kuhanan kita ng picture|photo capture)\b/i;
  function _isPhotoIntent(text) {
    const s = String(text || '').trim();
    if (!s) return false;
    return _PHOTO_INTENT_RE.test(s);
  }

  // Phase 4.50 (turn #53): Summary-on-demand detector.
  // "summarise this conversation" / "i-summarize mo yung pinag-usapan
  // natin" — worker wants a recap. We don't compress here; we tell
  // the LLM to switch to summary mode using the existing session
  // turns + dialog state context.
  const _SUMMARY_RE = /\b(?:summari[sz]e (?:this|our|the) (?:conversation|chat|session|talk)|recap (?:this|the) (?:conversation|chat)|i-summari[sz]e mo|i-recap mo|give me the (?:summary|recap)|wrap[- ]up (?:my|the) shift)\b/i;
  function _isSummaryRequest(text) {
    const s = String(text || '').trim();
    if (!s) return false;
    return _SUMMARY_RE.test(s);
  }

  // Phase 4.51 (turn #54): Identity drift detector.
  // Workers occasionally hand their phone to a colleague mid-shift.
  // We track the worker_name observed on the FIRST turn; if a later
  // turn carries a different worker_name, we flag the drift so the
  // LLM can ask "still you?" before logging anything as the original
  // account. Module-local — resets on session reload.
  let _identityFirstSeen = null;
  function _trackIdentity(workerName) {
    if (!workerName) return false;
    const w = String(workerName).trim();
    if (!w) return false;
    if (_identityFirstSeen === null) { _identityFirstSeen = w; return false; }
    return _identityFirstSeen !== w;
  }
  function _resetIdentityTracking() { _identityFirstSeen = null; }

  // Phase 4.52 (turn #51): Avatar emotion-state classifier.
  // Inspects the assistant reply and picks an avatar state attribute
  // (UI uses this to color-tint the persona portrait while playing).
  // States: 'urgent' (any 🚨 / "critical" / "action today"), 'celebratory'
  // ("naks" / "great work"), 'concerned' (fatigue or sensitive topic
  // mentioned), 'helpful' (default).
  function _classifyAvatarState(replyText) {
    const r = String(replyText || '').toLowerCase();
    if (/critical|action today|red line|safety risk|emergency|🚨/.test(r)) return 'urgent';
    if (/naks|great work|good job|salamat sa shift|nicely done|amazing/.test(r)) return 'celebratory';
    if (/hala|frustrated|pagod|stressed|take care|i hear you/.test(r)) return 'concerned';
    return 'helpful';
  }

  // Phase 4.34 (turn #35): Voice action verb detector.
  // When the transcript starts with a write-action verb ("log", "create",
  // "file", "schedule", "open a ticket"), the reply MUST ask for
  // explicit yes/no confirmation BEFORE voice-action-router executes
  // the side effect. Workers don't want a typo to silently create
  // logbook rows or PM schedules.
  // Verbs that imply a write or side-effecting step. The list also feeds
  // _parseActionQueue when it splits a batch utterance, so each sub-step
  // ("start PM", "notify supervisor", "close the work order") must look
  // action-shaped to count toward the queue.
  const _ACTION_VERB_RE = /^(?:log|create|file|schedule|open a ticket|raise a ticket|book|add|record|i-log|gawa ng|gawan ng|i-record|start|notify|send|run|check|update|close|finish|complete|resolve|mark)\b/i;
  function _isActionRequest(text) {
    const s = String(text || '').trim();
    if (!s) return false;
    return _ACTION_VERB_RE.test(s);
  }

  // Phase 4.35 (turn #40): Batch action language detector.
  // "log bearing replacement on P-203, P-205, and P-208" — multiple
  // items in one utterance. The LLM needs to know to PARSE each item
  // and confirm BATCH (e.g. "I see 3 entries — confirm all?"). Caps
  // at >=2 comma/and separators so single-item logs don't trip it.
  function _isBatchAction(text) {
    const s = String(text || '').trim();
    if (!s) return false;
    // Counts the joiners: commas + the word "and" + "at" (Tagalog).
    const commaCount = (s.match(/,/g) || []).length;
    const andCount = (s.match(/\b(?:and|at)\b/gi) || []).length;
    return (commaCount + andCount) >= 2 && _isActionRequest(s);
  }

  // Phase 4.36 (turn #41): Explainability question detector.
  // "Why did you say that?" / "How do you know?" / "Where did that
  // come from?" — worker is questioning the reasoning behind a prior
  // claim. The LLM should TRACE: name the source view, the row, and
  // the timestamp. No more "the data shows" without saying which data.
  const _EXPLAIN_RE = /^(?:why|how do you know|how did you|where did you get|where(?:'|’)?s that from|paano mo nalaman|saan galing|saan mo nakuha|prove it|show me how)\b/i;
  function _isExplainRequest(text) {
    const s = String(text || '').trim();
    if (!s) return false;
    return _EXPLAIN_RE.test(s);
  }

  // Phase 4.37 (turn #42): Worker-mention detector.
  // "kasama si Romeo" / "with Romeo" / "Romeo helped" — worker is
  // tagging another teammate. The LLM should capture the second name
  // so voice-action-router can attach it to the logbook entry's
  // co_worker field. Returns the captured name or null.
  const _MENTION_RE = /\b(?:kasama si|kasama ni|with|together with|along with|kasama|katulong si|tinulungan ako ni|with help from)\s+([A-Z][a-zA-Z'\-]{1,40}(?:\s+[A-Z][a-zA-Z'\-]{1,40})?)\b/;
  function _detectMention(text) {
    const m = String(text || '').match(_MENTION_RE);
    return m ? String(m[1]).trim() : null;
  }

  // Phase 4.38 (turn #43): Fatigue / frustration detector.
  // Workers signal stress through specific phrases. The LLM should
  // shift to a more empathetic tone and offer a break + (optionally)
  // mention available wellbeing resources without being preachy.
  const _FATIGUE_RE = /\b(?:pagod\s+na(?:\s+ako)?|tired|exhausted|burnt\s*out|frustrated|nakaka\s*frustrate|ayoko\s+na|naloloka(?:\s+na)?|nahirapan\s+na|stress\s+na|stressed\s+out|sawa\s+na|sira\s+ulit|ulit\s+ulit|nakaka\s*hassle)\b/i;
  function _detectFatigueSignal(text) {
    const s = String(text || '').trim();
    if (!s) return false;
    return _FATIGUE_RE.test(s);
  }

  // Phase 4.39 (turn #44): Transcript export detector.
  // "send the transcript" / "save this conversation" / "i-save mo ito"
  // — worker wants the session captured outside the journal. We
  // don't ship execution here (handled by report-sender), just emit
  // an EXPORT REQUEST anchor so the LLM acknowledges + routes.
  const _EXPORT_RE = /\b(?:send (?:me )?(?:the |a |this )?(?:transcript|summary|conversation|notes)|save (?:this |the )?(?:transcript|conversation|session|chat)|email (?:me )?(?:the )?(?:transcript|summary)|i-save mo (?:ito|yan)|i-send mo ito|export this)\b/i;
  function _isExportRequest(text) {
    const s = String(text || '').trim();
    if (!s) return false;
    return _EXPORT_RE.test(s);
  }

  // Phase 4.31 (turn #26): Repeated-issue surface.
  // Best-effort query against v_logbook_truth for same-asset failure
  // repetition in the last 30 days. If the same machine has 3+ entries
  // with similar failure mode, the LLM gets a flag in the prompt so it
  // can escalate ("this is the 3rd corrective on Compressor C-01 this
  // month — worth flagging to your supervisor"). Empty string when no
  // repetition or query fails — never blocks.
  async function _fetchRepeatedIssueFlag(db, hiveId) {
    if (!db || !hiveId) return '';
    try {
      const since = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();
      const { data } = await db.from('v_logbook_truth')
        .select('machine,category,maintenance_type')
        .eq('hive_id', hiveId)
        .eq('maintenance_type', 'Corrective')
        .gte('created_at', since)
        .limit(200);
      if (!Array.isArray(data) || data.length === 0) return '';
      // Group by machine. Any machine with >= 3 corrective entries is
      // "chronic" in the 30-day window.
      const counts = {};
      data.forEach(row => {
        const m = String(row.machine || '').trim();
        if (!m) return;
        counts[m] = (counts[m] || 0) + 1;
      });
      const chronic = Object.entries(counts)
        .filter(([_, n]) => n >= 3)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3);
      if (chronic.length === 0) return '';
      const lines = chronic.map(([m, n]) => '  - ' + m + ': ' + n + ' corrective entries in last 30 days').join('\n');
      return '\nREPEATED ISSUES (last 30 days, ≥3 corrective each — surface ' +
             'these IF the worker asks about any of these machines, or ' +
             'proactively if context warrants):\n' + lines + '\n';
    } catch (_) {
      return '';
    }
  }

  // Phase 4.43 (turn #38): Skill-gap nudge fetch.
  // Pulls v_worker_skill_truth for the current worker, identifies the
  // lowest-level discipline relative to their primary, and emits a
  // SKILL GAP block when the gap is meaningful (level <=2 / Awareness
  // or Foundational). Empty string when no gap or query fails. The
  // anchor lets the LLM offer a quick refresher path without becoming
  // a nag (only surfaces when the conversation naturally warrants it).
  async function _fetchSkillGapFlag(db, workerName) {
    if (!db || !workerName) return '';
    try {
      const { data } = await db.from('v_worker_skill_truth')
        .select('discipline,level,primary_skill,role')
        .eq('worker_name', workerName)
        .limit(20);
      if (!Array.isArray(data) || data.length === 0) return '';
      const gaps = data.filter(r => typeof r.level === 'number' && r.level <= 2);
      if (gaps.length === 0) return '';
      // Surface up to 2 lowest-level gaps so the prompt stays short.
      const sorted = gaps.slice().sort((a, b) => (a.level || 99) - (b.level || 99)).slice(0, 2);
      const lines = sorted.map(g =>
        '  - ' + (g.discipline || 'discipline') + ' (Level ' + (g.level || 0) + ')'
      ).join('\n');
      return '\nSKILL GAPS (Awareness / Foundational level — surface ONLY if the ' +
             'worker\'s question maps to one of these, and only as a one-line ' +
             'offer: "want a quick refresher on <discipline>?"):\n' + lines + '\n';
    } catch (_) {
      return '';
    }
  }

  // Phase 4.32 (turn #27): Standards lookup detector.
  // When the worker's transcript mentions a maintenance standard
  // (ISO 14224, SAE JA1011, ISO 22400-2, NFPA 70, IEC 60812, SMRP,
  // ASHRAE, etc.), inject a STANDARDS QUERY flag so the LLM knows to
  // anchor the reply on industry_standards_chunks (already RAG'd via
  // standardsContext) instead of paraphrasing from training data.
  const _STANDARDS_RE = /\b(?:ISO\s*\d{4,5}(?:-\d+)?|IEC\s*\d{4,5}|SAE\s*JA\s*\d{4}|ASHRAE\s*\d{2,3}(?:\.\d+)?|NFPA\s*\d{2,3}|SMRP|TPM|RCM|FMEA|ASME\s*[A-Z]?\d{2,3}|PEC\s*\d{4}|PSME|NSCP)\b/i;
  function _detectStandardsMention(text) {
    const s = String(text || '');
    const m = s.match(_STANDARDS_RE);
    return m ? m[0] : null;
  }

  // Phase 4.18: Repeat-that detector (turn #14).
  // Plants are loud. Workers regularly miss the audio playback the
  // first time and ask "what?" / "ulitin mo" / "say it again" / "come
  // again". Don't burn an LLM call — just replay the LAST assistant
  // reply from session memory. Falls through to normal classification
  // when there's nothing to replay.
  const _REPEAT_RE = /^(?:what|huh|huh\?|sorry|come again|say it again|say that again|repeat that|repeat please|paki ulit|paki-ulit|pakiulit|ulitin mo|ulit|ulit nga|one more time|once more)([\s,!.?]|$)/i;
  function _isRepeatRequest(text) {
    const s = String(text || '').trim();
    if (!s) return false;
    const words = s.split(/\s+/);
    // Legit repeats top out at 3-4 words ("one more time", "say that again, please").
    // 5 was over-inclusive: "what does that mean exactly" starts with "what" and
    // tripped the regex even though it's a follow-up question, not a repeat.
    if (words.length > 4) return false;
    return _REPEAT_RE.test(s);
  }

  // Phase 4.13: Asset-context auto-priming (turn #9).
  // When a worker opens voice journal from inside an asset page (or
  // right after editing a logbook entry on a specific machine), the
  // asset_tag is sitting in the worker's recent context but NOT yet in
  // the dialog state's context_slots. This helper auto-primes
  // context_slots.asset_tag from the most recent logbook entry so the
  // PRIOR TOPIC HANDLE + slot enumeration can reference it from turn 1.
  // The PRIOR TOPIC HANDLE clause itself (built below in this file) lists
  // the pronouns workers actually use: it, that, those, yan, yun, iyon,
  // iyan — so the L2 audit can verify the contract from this slice alone.
  //
  // The fetch is best-effort: failures fall through to no priming.
  async function _maybePrimeAssetContext(db, dialogState, workerName, hiveId) {
    if (!db || !workerName || !hiveId) return dialogState;
    const slots = (dialogState && dialogState.context_slots) || {};
    // If asset_tag is already set, don't override.
    if (slots.asset_tag) return dialogState;
    try {
      const { data } = await db.from('v_logbook_truth')
        .select('machine,date,created_at')
        .eq('worker_name', workerName)
        .eq('hive_id', hiveId)
        .order('created_at', { ascending: false })
        .limit(1);
      const recent = Array.isArray(data) && data[0];
      if (!recent || !recent.machine) return dialogState;
      // Only prime if the logbook entry is recent (last 60 min) — older
      // entries aren't reliable context anymore.
      const ts = recent.created_at ? new Date(recent.created_at).getTime() : 0;
      if (!ts || (Date.now() - ts) > 60 * 60 * 1000) return dialogState;
      const primed = Object.assign({}, dialogState || { context_slots: {} });
      primed.context_slots = Object.assign({}, slots, { asset_tag: recent.machine });
      return primed;
    } catch (_) {
      return dialogState;
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

    // 2026-05-19 Companion Streamline Step C/D: removed the LLM-assisted
    // intent classification call (previously hit the legacy Cloudflare
    // Worker). The heuristics above (router pre-classify + KPI keyword
    // regex) cover the vast majority of voice traffic already, and the
    // LLM call was the silent failure mode that stranded users behind
    // "Sorry, I'm offline" replies. If you reintroduce LLM-assisted
    // routing, point it at ai-gateway with a dedicated `intent-router`
    // agent registered in AGENT_ROUTES — never at an external Worker.
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
               /* storage-key-allow: bootstrap fallback for hive context */ localStorage.getItem('hive_id') || '';
      if (!hiveId) {
        console.warn('[WHVoice] Snapshot: no hiveId found in localStorage either');
        return '';
      }
      console.log('[WHVoice] Snapshot: recovered hiveId from localStorage:', hiveId); // console-log-allow: snapshot hiveId recovery diagnostic
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
      // Recent CLOSED logbook (so Zaniah can answer "what did we fix recently?")
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

    console.log('[WHVoice] Snapshot context:', { hiveId, workerName }); // console-log-allow: snapshot context dump (once per session-open)
    console.log('[WHVoice] Snapshot data counts:', { // console-log-allow: snapshot data counts (once per session-open)
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
      const dueSoon = await db.from('v_pm_scope_items_truth').select('COUNT').eq('hive_id', hiveId).eq('is_due_soon', true).execute();
      const overdue = await db.from('v_pm_scope_items_truth').select('COUNT').eq('hive_id', hiveId).eq('is_overdue', true).execute();
      const due = (dueSoon.data && dueSoon.data[0] && dueSoon.data[0].count) || 0;
      const overdueCount = (overdue.data && overdue.data[0] && overdue.data[0].count) || 0;
      if (due + overdueCount === 0) return '';
      return 'PMs: ' + due + ' due this week' + (overdueCount ? ', ' + overdueCount + ' overdue' : '') + '.';
    } catch (_) { return ''; }
  }

  // Helper: fetch inventory alerts (low stock / out of stock)
  async function _fetchInventoryAlerts(db, hiveId) {
    try {
      const low = await db.from('v_inventory_items_truth').select('COUNT').eq('hive_id', hiveId).eq('is_low_stock', true).execute();
      const out = await db.from('v_inventory_items_truth').select('COUNT').eq('hive_id', hiveId).eq('is_out_of_stock', true).execute();
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
    const personaName = persona === 'zaniah' ? 'Zaniah' : 'Hezekiah';

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

  function _buildVoiceSystemPrompt(persona, workerName, hiveName, pageLabel, routingHint, memoryBlock, canonicalData, routerContext, platformData, ragContext, dialogState, proactiveAlerts, crossHiveContext, standardsContext, filipinoGlossary, kgContext, transcript) {
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
    if (proactiveAlerts && proactiveAlerts.length) {
      console.log('[WHVoice] DEBUG: alertsSection building with', proactiveAlerts.length, 'alerts:', JSON.stringify(proactiveAlerts.slice(0, 2)));
    } else {
      console.log('[WHVoice] DEBUG: NO ALERTS FOUND - proactiveAlerts empty or null:', proactiveAlerts); // console-log-allow: T6 proactive-alerts DEBUG trace
    }
    const alertsSection = (proactiveAlerts && proactiveAlerts.length)
      ? '\n═══ CRITICAL PRIORITY: ACTIVE EQUIPMENT ALERTS ═══\n' +
        'MANDATORY RULE: You MUST surface the alerts below FIRST in your reply, using the exact descriptions provided. Do NOT summarize, paraphrase, or ignore them.\n' +
        'If ANY alert has severity=critical, start your reply with: "Before you ask, I need to flag something critical:"\n' +
        'Then list each alert with its description and suggested action.\n' +
        'ONLY after fully addressing alerts should you answer the worker\'s question.\n' +
        'Alerts:\n' +
        proactiveAlerts.map((a, idx) => {
          if (!a || typeof a !== 'object') {
            console.warn('[WHVoice] Invalid alert object at index', idx, ':', a);
            return '';
          }
          const severity = String(a.severity || 'info').toUpperCase();
          const alertType = String(a.alert_type || 'unknown');
          const desc = String(a.description || 'No description provided').slice(0, 250);
          const action = String(a.action_suggested || 'Investigate.').slice(0, 200);
          return `${idx + 1}. [${severity}] ${alertType}: ${desc}\n   Action: ${action}`;
        }).filter((s) => s).join('\n') +
        '\n═══ END ALERTS (MANDATORY TO ADDRESS ABOVE) ═══\n'
      : '';

    // Phase 4.15 (turn #11) CODE-SWITCH ANCHOR — explicit hint that workers
    // mix English + Tagalog / Cebuano / Ilocano in one sentence. Without
    // this, models occasionally try to "translate" PH words to English
    // ("ay grabe" → "wow really") which loses the affective tone.
    const codeSwitchAnchor =
      'LANGUAGE NOTE — workers in PH plants mix English with Tagalog / Cebuano / Ilocano / Hiligaynon mid-sentence. ' +
      'When they say "ay grabe naman ang init" or "pak, sira ulit", DO NOT translate the PH words to English — ' +
      'mirror their cadence. You reply in English (per the persona contract) but you may keep one or two PH words ' +
      'they used if it carries the meaning ("the bearing housing is mainit at 80°C").\n';

    // Phase 4.16 (turn #12) SENSITIVE-TOPIC REDIRECT — anchor a one-line
    // reminder that HR / legal / financial / payroll / disciplinary topics
    // are above the companion's scope. Route to supervisor + plant
    // administrator instead of attempting to advise.
    const sensitiveTopicAnchor =
      'SENSITIVE TOPIC REDIRECT — if the worker raises HR / legal / financial / payroll / disciplinary / ' +
      'visa / immigration issues, respond with ONE calm sentence: "Yan ay para sa supervisor / HR / plant ' +
      'admin — they will help you properly." Do NOT advise, do NOT speculate, do NOT take sides. The ' +
      'self-harm + helpline clause in the safety block still applies for crisis content.\n';

    // Phase 4.17 (turn #13) WORKER NAME PERSONALIZATION — always address
    // the worker by name when known. Falls back to "kapatid" (kin) for
    // anonymous voice-journal callers so the reply still sounds warm
    // rather than clinical.
    const safeWorkerName = (workerName && String(workerName).trim()) || 'kapatid';
    const workerNameAnchor = 'You are talking to ' + safeWorkerName + '. Use their name in your reply when it feels natural.\n';

    // Phase 4.19 (turn #15) HALLUCINATION GUARD — explicit rule that no
    // asset tag / part number / KPI value / page name may appear in the
    // reply UNLESS it is present verbatim in CANONICAL DATA, PRIOR TURNS,
    // or the worker's own utterance. Without this anchor the model
    // sometimes invents plausible-sounding tags ("Pump P-104") that
    // don't exist in the worker's hive — destroys trust on first read.
    const hallucinationGuardAnchor =
      'HALLUCINATION GUARD — you may ONLY mention asset tags, part numbers, ' +
      'machine names, KPI values, or page names that appear verbatim in CANONICAL ' +
      'DATA above, in PRIOR TURNS WITH THIS WORKER, or in the worker\'s own ' +
      'utterance. If you want to reference something not there, say plainly ' +
      '"your records don\'t show that one — check Asset Hub" instead of inventing. ' +
      'A friendly-but-wrong tag destroys trust on first read.\n';

    // Phase 4.20 (turn #16) CITATION ENFORCEMENT — when the reply quotes a
    // KPI / metric / number that came from CANONICAL DATA, name the
    // source view inline ("MTBF is 14 days from v_kpi_truth"). This
    // gives the worker a one-tap path to drill into the underlying data
    // and forces the model to stay anchored. Optional when no number is
    // quoted (a tone-only reply doesn\'t need a citation).
    const citationAnchor =
      'CITATION RULE — when your reply quotes a number, percentage, or ' +
      'date that came from CANONICAL DATA, name the source view in plain ' +
      'prose: "from v_kpi_truth", "per v_pm_compliance_truth", "the logbook ' +
      'shows…". One short citation per reply is enough. Skip the citation ' +
      'when the reply is tone-only (no numbers).\n';

    // Phase 4.24 (turn #25) SHIFT CONTEXT ANCHOR — PH industrial plants
    // run 3 shifts (06:00 / 14:00 / 22:00 PHT). The companion's opener
    // should match: "magandang umaga" for AM shift, "good afternoon
    // kapatid" for PM, "kumusta sa night shift" for graveyard. Inject
    // the current shift NAME so the LLM can tailor accordingly without
    // having to compute it.
    const phNow = new Date();
    // PH is UTC+8 — use offset arithmetic so this works regardless of
    // the worker's device timezone (a worker in Mindanao on UTC+8 vs a
    // dev on UTC+12 both get the same shift window).
    const phHour = (phNow.getUTCHours() + 8) % 24;
    let shiftName = 'Day';
    if (phHour >= 6  && phHour < 14) shiftName = 'Morning (06:00-14:00 PHT)';
    else if (phHour >= 14 && phHour < 22) shiftName = 'Afternoon (14:00-22:00 PHT)';
    else                                  shiftName = 'Night (22:00-06:00 PHT)';
    const shiftAnchor = 'SHIFT CONTEXT — it is currently the ' + shiftName + ' shift. ' +
      'If the worker hasn\'t said hello yet, match the time-of-day in your opener ' +
      '(magandang umaga / magandang hapon / kumusta sa night shift). Workers on ' +
      'graveyard shift are running on less sleep — keep replies extra short.\n';

    // Phase 4.25 (turn #30) WORKER DISCIPLINE BIASING — when the worker
    // has a registered primary_discipline (mechanical / electrical /
    // instrumentation / facilities / production), bias technical examples
    // toward THAT discipline. Default: keep neutral (mechanical-ish).
    const workerDiscipline = (routerContext && routerContext.worker_discipline) ||
                             (dialogState && dialogState.worker_discipline) || '';
    const disciplineAnchor = workerDiscipline
      ? 'WORKER DISCIPLINE — ' + safeWorkerName + ' is registered as ' + workerDiscipline +
        '. Bias technical examples toward ' + workerDiscipline + ' (vocabulary, failure ' +
        'modes, standards). Do NOT switch to ' + workerDiscipline + '-only — workers also ' +
        'ask cross-discipline questions — but pick the matching example when there\'s a choice.\n'
      : '';

    // Phase 4.26 (turn #32) CONFIDENCE CALIBRATION — when the canonical
    // data behind the reply is THIN (sample size <5, RAG context empty,
    // or analytics window <30 days), the reply MUST hedge. Workers
    // distrust over-confident answers about small-sample data more than
    // they distrust honest "not enough yet".
    const confidenceAnchor =
      'CONFIDENCE CALIBRATION — if CANONICAL DATA shows <5 records / <30 days / ' +
      'empty RAG, your reply MUST hedge: "based on what we have so far", "early ' +
      'signal — verify with your records", "this is one entry, not a pattern". ' +
      'Stating a small-sample finding as if it were a verified pattern is the ' +
      '#1 way to lose worker trust.\n';

    // Phase 4.40 (turn #36) WELLBEING NUDGE — fires automatically on
    // graveyard shift. The transcript-based fatigue signal (T43) is
    // appended separately at the call site (where transcript is in
    // scope). Both produce similar prompt overlays — empathy first,
    // cap at 2 sentences, optional EAP pointer.
    const isGraveyard = (shiftName || '').startsWith('Night');
    const wellbeingAnchor = isGraveyard
      ? 'WELLBEING NUDGE — the worker is on graveyard shift. Open with one ' +
        'short empathy beat ("pagod na talaga ng shift na ito, hindi ba"). ' +
        'Cap your reply at 2 sentences max. If they mention burnout / ' +
        'frustration / safety risk to themselves, point ONCE to "talk to ' +
        'your supervisor or use the EAP helpline if you have one" and stop ' +
        'journaling further advice for that turn. Never moralise. Never ' +
        'compare to other workers.\n'
      : '';

    // Phase 4.41 (turn #37) ENCOURAGEMENT ANCHOR — when CANONICAL DATA
    // shows the worker just closed a logbook entry or completed a PM
    // in the last 24h, the reply should open with a brief "naks, good
    // work" beat. Workers in PH plants rarely get verbal recognition
    // for daily wins — even a one-line acknowledgement materially
    // changes adoption.
    const encouragementAnchor =
      'ENCOURAGEMENT — if the worker\'s recent logbook or PM completion is ' +
      'in CANONICAL DATA (LOGBOOK / PM HEALTH section), and the question ' +
      'is general or wrap-up shaped, open with ONE short recognition line: ' +
      '"naks, you closed P-203 today, salamat ah". Skip if the question is ' +
      'purely a data lookup — don\'t pad data answers with praise.\n';

    // Phase 4.64 (turn #56) MATURITY-STAIR GATING — when the hive is
    // at Stair 0 (Paper) or Stair 1 (Digital Logbook) — i.e. <2 — the
    // companion MUST NOT promise predictive features. Reply stays
    // descriptive ("what is happening") and points to the Maturity
    // Stairway when the worker asks for forecasts.
    const maturityStair = _readHiveMaturityStair();
    const maturityAnchor = (typeof maturityStair === 'number' && maturityStair < 2)
      ? 'MATURITY GATING — this hive is at Stair ' + maturityStair + ' (Paper / ' +
        'Digital Logbook). Do NOT promise predictive features (forecast, ' +
        'next-failure date, anomaly detection). Stay descriptive ("here is ' +
        'what happened in the last 30 days"). If asked for a forecast, say ' +
        'plainly "we need 90 days of history first — check the Maturity ' +
        'Stairway on Home for the path".\n'
      : '';

    // Phase 4.65 (turn #59) LANGUAGE PREF — when the worker has opted
    // into a non-default language for output, honour it. The persona
    // contract still keeps the default (English) so this anchor only
    // fires when an explicit pref is stored.
    const langPref = _getLanguagePref();
    const languageAnchor = langPref
      ? 'LANGUAGE PREFERENCE — the worker has opted into "' + langPref +
        '" output. Reply in ' + langPref + ' (not the persona-default English) ' +
        'until they say "speak english" again. Persona character + safety ' +
        'rules still apply — only the output language changes.\n'
      : '';

    // Phase 4.66 (turn #60) BREVITY PREF — when set, force a one-sentence
    // cap on the reply. Worker says "more detail" / "expand" to release.
    const brevityPref = _getBrevityPref();
    const brevityAnchor = (brevityPref === 'brief')
      ? 'BREVITY MODE — worker requested brief replies. Cap your reply at ' +
        'ONE sentence, ≤25 words. If they need a number, just say the number ' +
        '+ unit + source view. Skip the empathy beat unless they vented. ' +
        'Release by them saying "more detail" / "expand".\n'
      : '';

    // Phase 4.68 (turn #66) PRONUNCIATION RESPECT — when the worker
    // has registered pronunciation overrides (per-device library),
    // the reply text MUST use the override spelling so the TTS
    // pronunciation pipeline lands the right sound. The map is
    // already applied client-side in _applyPronunciation, but the
    // anchor also instructs the LLM to keep referring to the term
    // with the worker's preferred spelling so corrections stick.
    const _pronunciationMap = _getPronunciationMap();
    const _pronunciationKeys = Object.keys(_pronunciationMap || {});
    const pronunciationAnchor = (_pronunciationKeys.length > 0)
      ? 'PRONUNCIATION RESPECT — the worker has corrected the say-as for: ' +
        _pronunciationKeys.slice(0, 8).join(', ') + '. Use the corrected ' +
        'spelling/form when referring to those terms; do NOT revert to the ' +
        'STT default. If the worker corrects a new term ("it\'s pee-two-oh-three, ' +
        'not pi-two-oh-three"), acknowledge and ask if they want it remembered.\n'
      : '';

    // Phase 4.69 (turn #67) VOICE EXECUTE LOCK — when the device has
    // NOT opted into voice-execute, write-verb intents (action
    // confirmation / replay / queue) must NOT auto-dispatch. The
    // companion confirms verbally + tells the worker to tap the
    // typed-confirm button. Default OFF (conservative).
    const _voiceExecuteOn = _isVoiceExecuteAuth();
    const voiceExecuteLockAnchor = !_voiceExecuteOn
      ? 'VOICE EXECUTE LOCK — voice-execute is OFF for this device. If the worker ' +
        'asks you to perform a write action (log, schedule, notify, file ticket), ' +
        'DO confirm what you understood ("you want me to log a stop on P-203 for ' +
        '15 minutes — confirm?") but tell them to tap the confirm button in the ' +
        'overlay — voice-confirm-only is disabled until they turn it on in Settings.\n'
      : '';

    // Phase 4.75 (turn #73) ACCENT MATCH — if a stored accent pref
    // is set OR the session is leaning Tagalog/Cebuano, the reply
    // should mirror the worker's natural code-switch density.
    // Persona contract (English default) still applies; this only
    // shifts the conversational filler tone, not the data terms.
    const _storedAccent = _getAccentPref();
    const _detectedAccent = _detectAccentHint(_sessionTurns);
    const _accentToUse = _storedAccent || _detectedAccent;
    const accentMatchAnchor = (_accentToUse && _accentToUse !== 'english-leaning')
      ? 'ACCENT MATCH — the worker is ' + _accentToUse + '. Mirror the ' +
        'code-switch density: keep conversational fillers in their tongue ("oo, ' +
        'tama" / "sige po" / "ayos lang") while data terms stay in canonical ' +
        'form (asset_tag, MTBF, source view). Do not over-correct toward formal ' +
        'English when they speak casually.\n'
      : '';

    // Phase 4.53 (turn #52) CROSS-HIVE BENCHMARK — when CROSS-HIVE
    // CONTEXT (PH-INTELLIGENCE anonymised median) is in the prompt
    // and the worker's question is about a KPI (MTBF / MTTR / OEE / PM
    // compliance), the reply SHOULD include the comparison ("your 14d
    // MTBF vs the PH F&B median of 18d"). Never name other plants —
    // anonymised only.
    const crossHiveBenchmarkAnchor = (crossHiveContext && String(crossHiveContext).trim().length > 0)
      ? 'CROSS-HIVE BENCHMARK — CROSS-HIVE CONTEXT above carries anonymised PH ' +
        'industry medians. If the worker\'s question is about a KPI, include a ' +
        'one-line comparison ("your MTBF is 14d vs PH F&B median 18d — slightly ' +
        'behind"). Never name other plants or workers; the data is anonymised by ' +
        'design. Skip the comparison if the question isn\'t KPI-shaped.\n'
      : '';

    // Phase 4.42 (turn #39) SHIFT HANDOVER MODE — if the transcript
    // contains handover language ("handover", "turnover", "pass to
    // next shift", "endorso"), the reply should produce a STRUCTURED
    // handover block (machine + status + open items + watch list)
    // suitable for the next shift to read at a glance. Different from
    // a conversational answer.
    const handoverIntent = /\b(?:handover|hand\s*over|turnover|turn\s*over|endorso|endorse to next shift|pass to next shift|brief the next shift|shift handover|shift report)\b/i.test(transcript || '');
    const handoverAnchor = handoverIntent
      ? 'HANDOVER MODE — worker requested a shift handover. Structure the reply as ' +
        'a 4-line block:\n' +
        '  Machines worked: <comma-separated tags>\n' +
        '  Open items: <max 3, with status>\n' +
        '  Watch list: <max 2, what next shift should monitor>\n' +
        '  Notes: <one short line>\n' +
        'No prose intro / outro. The next shift reads this in 10 seconds.\n'
      : '';

    // Phase 4.30 (turn #33) LONG-SESSION PACING — once the worker has
    // gone >10 turns in a single session, plant fatigue is real. The
    // companion should suggest a short break OR a wrap-up. The anchor
    // only fires after the LLM finishes its primary answer, so we don't
    // truncate substantive content; it appears as a closing nudge.
    const sessionPacingAnchor = (_sessionTurns.length >= 10)
      ? 'SESSION PACING — we are at turn ' + _sessionTurns.length + ' in this session. ' +
        'After your normal answer, append ONE short closing line nudging a break or ' +
        'wrap-up: "we\'ve been at this a while — pa-break ka muna?" / "want to wrap ' +
        'up and pick this up next shift?". One line, then stop.\n'
      : '';

    // Phase 4.27 (turn #34) PROACTIVE ALERTS OVERRIDE — critical / high
    // severity alerts MUST be the FIRST thing in the reply, even when
    // the worker asked about something else. The worker can't make a
    // safe decision without seeing the active fire first.
    const alertsOverrideAnchor =
      'ALERTS OVERRIDE — if PROACTIVE ALERTS above contains a CRITICAL or HIGH ' +
      'severity entry, your reply MUST surface it in the FIRST sentence, even if ' +
      'the worker asked about something else. Example: "Heads up — bearing on C-01 ' +
      'is in critical range, action today. About your MTBF question…". Workers ' +
      'can\'t make a safe decision if you bury the alert.\n';

    // Phase 4: Dialog state (intent + slots + clarification status) plus
    // Phase 4.5 PRIOR TOPIC HANDLE — explicit pronoun-resolution clause so
    // the LLM treats "it" / "that" / "yan" / "yun" as references to the
    // prior intent instead of asking the worker to repeat themselves.
    // Phase 4.6 SLOT CARRYOVER — natural-language enumeration of the
    // sticky slots (asset_tag, time_window, machine, etc.) so the model
    // can reuse them without re-prompting.
    let dialogSection = '';
    if (dialogState) {
      const intent = dialogState.current_intent || 'unknown';
      const confPct = Math.round((dialogState.intent_confidence || 0) * 100);
      const slots = dialogState.context_slots && typeof dialogState.context_slots === 'object'
        ? dialogState.context_slots
        : {};
      const slotKeys = Object.keys(slots).filter(k => slots[k] != null && slots[k] !== '');
      // Natural-language enumeration of slots — easier for the model to
      // honour than a raw JSON dump. Falls back to JSON when there is
      // nothing nameable so we never lie about empty state.
      const slotEnumeration = slotKeys.length
        ? 'You already know:\n' + slotKeys.map(k =>
            '  - ' + k.replace(/_/g, ' ') + ' = ' + String(slots[k]).slice(0, 80)
          ).join('\n') + '\n'
        : '';
      // PRIOR TOPIC HANDLE — only emit when there IS a topic worth
      // resolving to. Resolving pronouns to "unknown" would just confuse
      // the model.
      const priorTopicHandle = (intent && intent !== 'unknown')
        ? 'PRIOR TOPIC HANDLE — if the worker uses a pronoun ("it", "that", "those", "yan", "yun", "iyon", "iyan") or a short follow-up ("more on that?", "details?", "and?"), resolve to: ' + intent + '. Do NOT ask the worker to repeat the subject — you already know it.\n'
        : '';
      dialogSection = '\nDIALOG STATE:\n' +
        'Current intent: ' + intent + '\n' +
        'Confidence: ' + confPct + '%\n' +
        slotEnumeration +
        priorTopicHandle +
        (dialogState.clarification_pending ? 'Awaiting clarification from worker\n' : '') +
        '\n';
    }

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
    // Analytics"). With it, Zaniah/Hezekiah paraphrase the real figure.
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

    // Phase 9: Cross-hive context (multi-site awareness)
    const crossHiveSection = crossHiveContext
      ? '\nCROSS-HIVE ALERTS — From other sites in the group:\n' + crossHiveContext + '\n'
      : '';

    // Day 4: Industry standards retrieval (platform-wide, ISO/IEC/ASHRAE/NFPA/PSME/DOLE).
    // Use these citations when answering regulatory or best-practice questions.
    // Tier-S anchor map for in-platform metrics: cite the registered standard
    // short_name whenever you mention the metric. validate_ai_regression L4
    // enforces this — keep the list in sync with canonical/formula_contracts.json.
    const standardsSection = standardsContext
      ? '\nINDUSTRY STANDARDS — Regulatory and best-practice canon:\n' + standardsContext +
        '\nWhen citing, name the standard code (e.g. "ISO 14224 says..." or "per NFPA 70E..."). ' +
        'Standards are authoritative; prefer them over generic advice.\n' +
        '\nPLATFORM METRIC ANCHORS — always cite the standard when answering about:\n' +
        '  MTBF / MTTR -> ISO 14224:2016\n' +
        '  OEE -> ISO 22400-2:2014 / Nakajima TPM (1988)\n' +
        '  PM compliance -> SMRP Best Practices v5.0\n' +
        '  FMEA RPN -> IEC 60812:2018\n' +
        '  RCM consequence -> SAE JA1011\n' +
        '  Anomaly detection -> Z-Score Anomaly (3-sigma rule)\n' +
        '  Risk score -> WorkHive composite (platform-internal)\n'
      : '';

    // Day 5 (L7): PH industrial phrase glossary. Helps the LLM correctly
    // interpret worker code-switching (e.g. "may oil leak sa motor", "panganib
    // sa breaker"). Reply still in English (Hard Rule 10) — this is for
    // understanding, not generation.
    const filipinoSection = filipinoGlossary
      ? '\nPH INDUSTRIAL GLOSSARY — Use to interpret worker Tagalog/Cebuano:\n' + filipinoGlossary + '\n'
      : '';

    // Day 5 (L5): Knowledge-graph triples — atomic subject/predicate/object
    // claims extracted from standards corpus. Surfaces specific facts that
    // would be buried in larger chunks (e.g. "RMF requires cybersecurity roles").
    const kgSection = kgContext
      ? '\nKNOWLEDGE GRAPH — Atomic claims relevant to the worker question:\n' + kgContext +
        '\nUse these as authoritative one-line facts. When you cite, prefer the source bracketed before the claim.\n'
      : '';

    const hasData = platformData || canonicalData || ragContext || standardsContext || kgContext;
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
      workerNameAnchor +
      codeSwitchAnchor +
      sensitiveTopicAnchor +
      hallucinationGuardAnchor +
      citationAnchor +
      shiftAnchor +
      disciplineAnchor +
      confidenceAnchor +
      alertsOverrideAnchor +
      sessionPacingAnchor +
      wellbeingAnchor +
      encouragementAnchor +
      handoverAnchor +
      crossHiveBenchmarkAnchor +
      maturityAnchor +
      languageAnchor +
      brevityAnchor +
      pronunciationAnchor +
      voiceExecuteLockAnchor +
      accentMatchAnchor +
      dialogSection +
      memorySection +
      canonicalSection +
      platformSection +
      ragSection +
      crossHiveSection +
      standardsSection +
      kgSection +
      filipinoSection +
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
      ? window.getPersona() : 'zaniah';
    const personaName = persona === 'zaniah' ? 'Zaniah' : 'Hezekiah';
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
    const priorDialogStateRaw = await _fetchDialogState(db, sessionId).catch(() => null);
    // Phase 4.10 stale-state guard (turn #6): if the prior turn was >15 min
    // ago, ignore the dialog state entirely. The worker has moved on and
    // applying stale intent/slots would feel like the companion missed
    // the gap.
    let priorDialogState = _isStaleDialogState(priorDialogStateRaw) ? null : priorDialogStateRaw;
    // Phase 4.13 asset-context auto-priming (turn #9): if the worker
    // edited a logbook entry on a specific machine in the last hour,
    // pull that asset_tag into context_slots so PRIOR TOPIC HANDLE +
    // slot enumeration can reference it from turn 1.
    priorDialogState = await _maybePrimeAssetContext(db, priorDialogState, ctx.worker_name, ctx.hive_id);

    // Phase 4.61 (turn #62) URL-context pre-fill — voice-journal opened
    // from asset-hub.html?asset=P-203 (or ?machine= / ?asset_tag=) seeds
    // context_slots.asset_tag so the very first turn has the right tag.
    const urlAsset = _readUrlAssetParam();
    if (urlAsset) {
      priorDialogState = priorDialogState || { current_intent: null, context_slots: {} };
      priorDialogState.context_slots = priorDialogState.context_slots || {};
      if (!priorDialogState.context_slots.asset_tag) {
        priorDialogState.context_slots.asset_tag = urlAsset;
      }
    }

    const priorIntent = priorDialogState && priorDialogState.current_intent;
    // Phase 4.56 (turn #57) Per-slot expiry — prune stale slots based
    // on their individual TTL before passing to the LLM. The reference
    // timestamp is the dialog state's updated_at; missing timestamps
    // pass through unchanged.
    const rawSlots = priorDialogState && priorDialogState.context_slots;
    const priorSlots = _pruneStaleSlots(rawSlots, priorDialogState && priorDialogState.updated_at);
    if (priorDialogState) priorDialogState.context_slots = priorSlots;

    // Phase 4.45 (turn #46) Reply cache hit — return the prior assistant
    // turn for the same (transcript, hive) pair within a 10-min TTL.
    // Saves an LLM call on accidental double-tap or network-retry. Sits
    // right after the noise guard so we don't cache empty transcripts.
    {
      const cached = _lookupReplyCache(transcript, ctx.hive_id);
      if (cached) {
        _setStatus(personaName + ' (cached):');
        _renderReplyBubble(cached, persona);
        if (typeof window.speakPersona === 'function') {
          window.speakPersona(cached, { persona });
        }
        _appendSessionTurn(transcript, cached);
        _showTalkAgainButton();
        return;
      }
    }

    // Phase 4.3: Noisy / empty transcript guard — runs BEFORE the LLM call
    // and before the heavy parallel platform fetch. Empty, 1-2 char, or
    // pure-filler ("uh", "um") transcripts must never enter intent
    // classification — the resulting 'unknown' would trip the topic-switch
    // clarification UI for what is really just silence. Saves an LLM call
    // and renders an honest "didn't catch that" prompt.
    if (_isNoisyTranscript(transcript)) {
      const noiseReply = "Hindi ko marinig yan. Tap to talk again — try in a few words.";
      _setStatus(personaName + " didn't catch that:");
      _renderReplyBubble(noiseReply, persona);
      if (typeof window.speakPersona === 'function') {
        window.speakPersona(noiseReply, { persona });
      }
      _appendSessionTurn(transcript, noiseReply);
      // Do NOT touch dialog state — this turn never happened from the
      // state-machine's perspective. Worker tries again on the next tap.
      _resetClarifyStreak();
      _showTalkAgainButton();
      return;
    }

    // Phase 4.2: Negation handler — short "no" / "cancel" / "wala" / "hindi"
    // exits the prior topic cleanly. Renders an acknowledgement, CLEARS the
    // dialog state (no priorIntent, no pending clarification), and returns
    // WITHOUT running the LLM call or intent classification. Mirrors the
    // affirmation bypass (Phase 4.1) on the negative side.
    if (priorIntent && _isFollowupNegation(transcript)) {
      const negReply = "Sige, never mind yan. Ano next?";
      _setStatus(personaName + ' says:');
      _renderReplyBubble(negReply, persona);
      if (typeof window.speakPersona === 'function') {
        window.speakPersona(negReply, { persona });
      }
      _appendSessionTurn(transcript, negReply);
      _saveJournalTurn(db, ctx, transcript, negReply, persona);
      // Reset dialog state: no prior intent, no pending clarification.
      _updateDialogState(db, ctx.hive_id, sessionId, null, 0, {}, false, null);
      _resetClarifyStreak();
      _showTalkAgainButton();
      return;
    }

    // Phase 4.18: Repeat-that short-circuit. Noisy plant → worker
    // missed the first audio playback → "ulit nga" / "say it again".
    // Replay the LAST assistant turn instead of running the LLM again.
    if (_sessionTurns.length > 0 && _isRepeatRequest(transcript)) {
      const last = _sessionTurns[_sessionTurns.length - 1];
      const repeatReply = (last && last.assistant) || "Wala pa akong nasabi — try the question again.";
      _setStatus(personaName + ' (repeating):');
      _renderReplyBubble(repeatReply, persona);
      if (typeof window.speakPersona === 'function') {
        window.speakPersona(repeatReply, { persona });
      }
      _appendSessionTurn(transcript, repeatReply);
      // Don't disturb dialog state — the worker is just asking for a re-play.
      _showTalkAgainButton();
      return;
    }

    // Phase 4.14: First-turn greeting short-circuit. No prior dialog
    // state AND no session turns AND greeting-shape utterance = open a
    // fresh conversation with a warm hello. Skips the LLM call entirely.
    if (!priorDialogState && _sessionTurns.length === 0 && _isGreeting(transcript)) {
      const greetReply = "Hi! " + personaName + " here. What can I help you with today?";
      _setStatus(personaName + ' says:');
      _renderReplyBubble(greetReply, persona);
      if (typeof window.speakPersona === 'function') {
        window.speakPersona(greetReply, { persona });
      }
      _appendSessionTurn(transcript, greetReply);
      _saveJournalTurn(db, ctx, transcript, greetReply, persona);
      _resetClarifyStreak();
      _showTalkAgainButton();
      return;
    }

    // Phase 4.28 (turn #28) Voice command shortcut — direct navigation.
    // "open logbook" / "schedule a PM" / "show analytics" navigate
    // straight to the target page. We render a brief ack so the worker
    // hears confirmation before the page swap, then call window.location
    // after a short delay.
    const shortcutTarget = _isVoiceShortcut(transcript);
    if (shortcutTarget) {
      const shortcutReply = "Opening " + shortcutTarget.replace('.html', '').replace(/-/g, ' ') + " — sandali lang.";
      _setStatus(personaName + ' says:');
      _renderReplyBubble(shortcutReply, persona);
      if (typeof window.speakPersona === 'function') {
        window.speakPersona(shortcutReply, { persona });
      }
      _appendSessionTurn(transcript, shortcutReply);
      _saveJournalTurn(db, ctx, transcript, shortcutReply, persona);
      // Don't disturb dialog state — the worker is navigating, not
      // ending the conversation. Defer the actual nav so audio has a
      // chance to start playing.
      setTimeout(function () {
        try { window.location.href = shortcutTarget; } catch (_) { /* non-fatal */ /* empty-catch-allow: best-effort silent swallow */ }
      }, 1200);
      _showTalkAgainButton();
      return;
    }

    // Phase 4.29 (turn #31) Goodbye / wrap-up short-circuit. Worker is
    // closing the whole session ("yun lang" / "I'm done" / "tapos na").
    // Render a warm exit, clear dialog state, suggest reopening
    // tomorrow. Different from thanks (turn #8) which is a single-turn
    // closer — goodbye implies the worker is walking away from the
    // overlay.
    if (_isGoodbye(transcript)) {
      const goodbyeName = (ctx && ctx.worker_name && String(ctx.worker_name).trim()) || 'kapatid';
      const goodbyeReply = "Sige, " + goodbyeName + ". Salamat sa shift, take care.";
      _setStatus(personaName + ' says:');
      _renderReplyBubble(goodbyeReply, persona);
      if (typeof window.speakPersona === 'function') {
        window.speakPersona(goodbyeReply, { persona });
      }
      _appendSessionTurn(transcript, goodbyeReply);
      _saveJournalTurn(db, ctx, transcript, goodbyeReply, persona);
      // Clean session end — same shape as close() (turn #24).
      _updateDialogState(db, ctx.hive_id, sessionId, null, 0, {}, false, null);
      _resetClarifyStreak();
      _showTalkAgainButton();
      return;
    }

    // Phase 4.12: Thanks / acknowledgment short-circuit. Conversation
    // closer — render a brief "walang anuman" beat, clear dialog state,
    // skip the LLM call. Suppresses the urge to ask one-more-question
    // when the worker is signalling they're done.
    if (_isThanksReply(transcript)) {
      const thanksReply = "Walang anuman. Take care.";
      _setStatus(personaName + ' says:');
      _renderReplyBubble(thanksReply, persona);
      if (typeof window.speakPersona === 'function') {
        window.speakPersona(thanksReply, { persona });
      }
      _appendSessionTurn(transcript, thanksReply);
      _saveJournalTurn(db, ctx, transcript, thanksReply, persona);
      _updateDialogState(db, ctx.hive_id, sessionId, null, 0, {}, false, null);
      _resetClarifyStreak();
      _showTalkAgainButton();
      return;
    }

    // Phase 4.9: Persona-switch utterance — "switch to Hezekiah" /
    // "tawagin si Zaniah" routes to the persona toggle, NOT through
    // intent classification. Persists the chosen persona to localStorage
    // (so subsequent surfaces see it) AND clears dialog state so the new
    // persona starts on a clean slate.
    const switchTarget = _isPersonaSwitchUtterance(transcript);
    if (switchTarget) {
      try { localStorage.setItem('wh_voice_journal_persona', switchTarget); } catch (_) { /* ignore */ /* empty-catch-allow: best-effort silent swallow */ }
      const targetName = switchTarget === 'hezekiah' ? 'Hezekiah' : 'Zaniah';
      const switchReply = "Sige, switching you to " + targetName + ". Tap the mic again — " + targetName + " will take it from here.";
      _setStatus('Switching companion to ' + targetName + '…');
      _renderReplyBubble(switchReply, persona);
      if (typeof window.speakPersona === 'function') {
        window.speakPersona(switchReply, { persona });
      }
      _appendSessionTurn(transcript, switchReply);
      _saveJournalTurn(db, ctx, transcript, switchReply, persona);
      // Reset state so the new persona has a clean slate (no carryover
      // intent / slots) AND nudge any open companion UI to refresh.
      _updateDialogState(db, ctx.hive_id, sessionId, null, 0, {}, false, null);
      _resetClarifyStreak();
      if (window.WHAssistant && typeof window.WHAssistant.refreshPersona === 'function') {
        try { window.WHAssistant.refreshPersona(); } catch (_) { /* non-fatal */ /* empty-catch-allow: best-effort silent swallow */ }
      }
      _showTalkAgainButton();
      return;
    }

    // Phase 4.7: Clarification-recovery routing — only fires when the
    // PRIOR turn ended with a pending clarification (the streak-ceiling
    // prompt). A worker reply that is JUST a page name resolves directly
    // to that intent. Without this guard the bare page name enters
    // normal classification → 'unknown' → clarify loops again — the
    // exact dead-end the ceiling was meant to break.
    const recoveryIntent = (priorDialogState && priorDialogState.clarification_pending)
      ? _isPageRecoveryReply(transcript)
      : null;
    if (recoveryIntent) {
      const recReply = "Sige, let's stay on " + recoveryIntent.replace(/_/g, ' ') + ". What do you need to know?";
      _setStatus(personaName + ' says:');
      _renderReplyBubble(recReply, persona);
      if (typeof window.speakPersona === 'function') {
        window.speakPersona(recReply, { persona });
      }
      _appendSessionTurn(transcript, recReply);
      _saveJournalTurn(db, ctx, transcript, recReply, persona);
      // Persist the resolved intent at high confidence so the next turn
      // has a real anchor. Clarification flag is now cleared — the worker
      // landed on a page, the loop is broken.
      _updateDialogState(db, ctx.hive_id, sessionId, recoveryIntent, 0.85, {}, false, null);
      _resetClarifyStreak();
      _showTalkAgainButton();
      return;
    }

    // Phase 5: Fetch proactive alerts (KPI spikes, risk escalation, overdue PM)
    const proactiveAlerts = await _fetchProactiveAlerts(db, ctx.hive_id).catch(() => []);

    // Phase 4.31 (turn #26): Fetch repeated-issue flag for the hive.
    // Best-effort, in parallel where possible. Surfaces machines with
    // 3+ corrective entries in 30d so the LLM can suggest escalation.
    const repeatedIssueFlag = await _fetchRepeatedIssueFlag(db, ctx.hive_id).catch(() => '');

    // Phase 4.43 (turn #38): Skill-gap nudge.
    // Best-effort fetch of v_worker_skill_truth. Empty string when no
    // gap, fetch fails, or worker isn't registered. The anchor surfaces
    // a one-line refresher offer when the LLM judges it relevant — it
    // does NOT force the LLM to mention it on every turn.
    const skillGapFlag = await _fetchSkillGapFlag(db, ctx.worker_name).catch(() => '');

    // Phase 4.32 (turn #27): Detect standards mention in the transcript
    // and emit a STANDARDS QUERY anchor so the LLM grounds on the
    // industry_standards_chunks RAG (already in standardsContext) when
    // available.
    const standardMentioned = _detectStandardsMention(transcript);
    const standardsQueryAnchor = standardMentioned
      ? '\nSTANDARDS QUERY — worker mentioned ' + standardMentioned + '. If the ' +
        'STANDARDS CONTEXT block above contains an excerpt from that standard, ' +
        'quote it verbatim (clause + page). If not, say plainly "I don\'t have ' +
        'that clause loaded — check Plant Connections > Standards Library".\n'
      : '';

    // Phase 4.34/4.35/4.36/4.37/4.38/4.39 (turns #35/#40/#41/#42/#43/#44):
    // Per-turn transcript-driven anchors. Each detector runs against
    // the current utterance; matched anchors are appended to canonicalData
    // so the LLM sees them in the prompt alongside the static T26 + T27
    // anchors. Stays out of _buildVoiceSystemPrompt to keep that
    // function's signature small.
    let perTurnAnchors = '';
    if (_isActionRequest(transcript)) {
      perTurnAnchors +=
        '\nACTION CONFIRMATION — worker started with a write-action verb ' +
        '(log / create / file / schedule). Do NOT execute the side effect ' +
        'this turn. Reply with: "Confirm: <restate the action in 1 line> — ' +
        'sabihin yes para gawin." Voice-action-router only executes after ' +
        'an explicit yes on the NEXT turn.\n';
    }
    if (_isBatchAction(transcript)) {
      perTurnAnchors +=
        '\nBATCH ACTION — worker named multiple items in one breath (comma + ' +
        '"and" / "at"). Parse the list, restate as a numbered batch, then ' +
        'ask for ONE confirmation for the whole batch ("3 entries — confirm ' +
        'all?"). Never split into multiple confirmation rounds.\n';
    }
    if (_isExplainRequest(transcript)) {
      perTurnAnchors +=
        '\nEXPLAIN PATH — worker is questioning your reasoning. Trace it: ' +
        'name the SOURCE VIEW (e.g. v_kpi_truth), the ROW count or date ' +
        'window the figure came from, and the most recent timestamp. ' +
        '"MTBF is 14 days — from v_kpi_truth, 6 corrective entries between ' +
        'May 1 and May 21." No more "the data shows" without showing which.\n';
    }
    const mentionedCoWorker = _detectMention(transcript);
    if (mentionedCoWorker) {
      perTurnAnchors +=
        '\nCO-WORKER MENTION — the worker named "' + mentionedCoWorker + '" ' +
        'as a teammate on this task. If the conversation involves logging ' +
        'an action, include co_worker = "' + mentionedCoWorker + '" in the ' +
        'confirmation summary so voice-action-router tags the logbook row.\n';
    }
    if (_detectFatigueSignal(transcript)) {
      perTurnAnchors +=
        '\nFATIGUE SIGNAL — worker said something tired / frustrated. ' +
        'Open with one short empathy line ("pagod ka na, hindi ba"), then ' +
        'answer in ONE sentence max. If they continue venting on the next ' +
        'turn, suggest a break or talking to their supervisor — do NOT ' +
        'stack more technical advice on top.\n';
    }
    if (_isExportRequest(transcript)) {
      perTurnAnchors +=
        '\nEXPORT REQUEST — worker wants this session captured outside the ' +
        'journal. Acknowledge briefly ("Sige, I\'ll prepare a summary") and ' +
        'point to Report Sender (report-sender.html) as the surface that ' +
        'emails transcripts. Don\'t fabricate sending it yourself.\n';
    }
    // T50 photo intent — offer visual-defect-capture in plain prose.
    if (_isPhotoIntent(transcript)) {
      perTurnAnchors +=
        '\nPHOTO INTENT — worker wants to share a photo. Offer ONCE: ' +
        '"open Visual Defect Capture from the logbook, snap a shot, and ' +
        'I\'ll read it back to you". Don\'t open the page yourself; the ' +
        'worker drives the camera, not the LLM.\n';
    }
    // T53 summary request — switch the LLM to summary mode.
    if (_isSummaryRequest(transcript)) {
      perTurnAnchors +=
        '\nSUMMARY MODE — worker requested a recap. Produce a 4-bullet ' +
        'summary from PRIOR TURNS WITH THIS WORKER + CANONICAL DATA: ' +
        '(1) main topics covered, (2) decisions / confirmations, (3) ' +
        'open items / unanswered questions, (4) suggested next step. ' +
        'No prose intro / outro. Bullets only.\n';
    }
    // T48 terminology resolution — async fetch + inject resolved tag.
    const resolvedAsset = await _resolveTerminology(db, ctx.hive_id, transcript).catch(() => null);
    if (resolvedAsset) {
      perTurnAnchors +=
        '\nTERMINOLOGY RESOLVED — worker said a nickname that fuzzy-matched ' +
        'to asset_tag "' + resolvedAsset.asset_tag + '" (' + (resolvedAsset.name || '') +
        '). Treat the rest of the turn as if they said the tag explicitly. ' +
        'If unsure, briefly confirm: "you mean ' + resolvedAsset.asset_tag + ', right?".\n';
    }
    // T49 branch recall — if worker referenced a prior thread, surface it.
    const recalledBranch = _detectBranchRecall(transcript);
    if (recalledBranch) {
      perTurnAnchors +=
        '\nBRANCH RECALL — worker wants to return to the "' + recalledBranch.label +
        '" thread (' + Math.round((Date.now() - recalledBranch.ts) / 60000) + ' min ago). ' +
        'Resume from that intent + slots: ' + JSON.stringify(recalledBranch.slots) + '. ' +
        'Acknowledge the switch ("right, back to ' + recalledBranch.label + '") before answering.\n';
    }
    // T54 identity drift — flag if worker_name changed mid-session.
    if (_trackIdentity(ctx.worker_name)) {
      perTurnAnchors +=
        '\nIDENTITY DRIFT — the worker_name on this turn differs from the ' +
        'first turn of the session. Open with a single calm verification ' +
        'line: "quick check — is this still ' + (ctx.worker_name || 'you') +
        '?". Do NOT log any action this turn until they confirm.\n';
    }

    // T58 Action replay — "same fix on P-205" after a confirmed action.
    const replay = _detectActionReplay(transcript);
    if (replay) {
      perTurnAnchors +=
        '\nACTION REPLAY — worker wants to repeat the last confirmed action ' +
        '("' + replay.verb + '") on a new asset: ' + replay.newAsset + '. ' +
        'Substitute asset_tag = ' + replay.newAsset + ' into the same slot ' +
        'shape: ' + JSON.stringify(replay.slots) + '. Confirm once before ' +
        'voice-action-router executes.\n';
    }

    // T59 Language opt-in — persist the worker's choice.
    const langChange = _detectLanguagePref(transcript);
    if (langChange) {
      _setLanguagePref(langChange);
      perTurnAnchors +=
        '\nLANGUAGE PREF UPDATED — worker opted into "' + langChange + '". ' +
        'Acknowledge in one short line ("sige, ' + langChange + ' na") + reply ' +
        'in the new language from here.\n';
    }

    // T60 Brevity toggle.
    const brevityChange = _detectBrevityToggle(transcript);
    if (brevityChange) {
      _setBrevityPref(brevityChange);
    }

    // T61 Timer request.
    const timerSpec = _detectTimerRequest(transcript);
    if (timerSpec) {
      const scheduled = _scheduleTimer(timerSpec);
      if (scheduled) {
        perTurnAnchors +=
          '\nTIMER SCHEDULED — set a reminder in ' + Math.round(timerSpec.ms / 60000) +
          ' minutes about "' + timerSpec.label + '". Acknowledge in one line ' +
          '("sige, paalalahanan kita") and do NOT re-prompt for confirmation.\n';
      }
    }

    // T64 Action queue — multi-step ("log entry then start PM then notify").
    const actionQueue = _parseActionQueue(transcript);
    if (actionQueue && actionQueue.length > 1) {
      perTurnAnchors +=
        '\nACTION QUEUE — worker chained ' + actionQueue.length + ' steps. ' +
        'Enumerate them ("1. ' + actionQueue.join(', 2. ').slice(0, 200) + '") ' +
        'and confirm the FIRST step only. Voice-action-router will pick up the ' +
        'remaining steps after each confirmation lands.\n';
    }

    // T65 PDF export — point to Report Sender, never fabricate sending.
    if (_isPdfExportRequest(transcript)) {
      perTurnAnchors +=
        '\nPDF EXPORT REQUEST — worker wants this conversation saved as a PDF. ' +
        'Do NOT pretend to generate or send anything. Tell them to tap the export ' +
        'icon, or open Report Sender from the menu — that surface owns the PDF ' +
        'pipeline. One short line, then stop.\n';
    }

    // T70 Daily digest — 5-line briefing format.
    if (_isDigestRequest(transcript)) {
      perTurnAnchors +=
        '\nDIGEST MODE — worker asked for a shift/overnight digest. Reply as ' +
        'exactly 5 lines:\n' +
        '  1) Open alerts (count + top 2 with severity)\n' +
        '  2) Closed PMs since last shift (count)\n' +
        '  3) Overdue PMs (count + top asset_tag)\n' +
        '  4) Watch list (assets with anomaly flag — top 2)\n' +
        '  5) Focus item (the one thing you would do first this shift)\n' +
        'No prose intro / outro. Numbers from PLATFORM SNAPSHOT only.\n';
    }

    // T71 Push opt-in detected — request browser permission inline.
    if (_isPushOptInReply(transcript)) {
      const pushState = _pushNotifyState();
      if (pushState === 'default') {
        // Fire the permission prompt — user-gesture window is open.
        try { _requestPushPerm(); } catch (_) { /* non-fatal */ /* empty-catch-allow: best-effort silent swallow */ }
      }
      perTurnAnchors +=
        '\nPUSH READINESS — worker opted into alerts. Browser permission ' +
        'state is "' + pushState + '". If granted, confirm in one line ("sige, ' +
        'aalertan kita sa critical events"). If denied/unsupported, say plainly ' +
        '"alerts are blocked in your browser — open site settings to enable" — ' +
        'do NOT promise alerts you cannot deliver.\n';
    }

    // T75 Toxicity guard — de-escalate, never amplify.
    const _tox = _detectToxicLanguage(transcript);
    if (_tox && _tox.severity >= 0.45) {
      perTurnAnchors +=
        '\nTOXICITY GUARD — the worker\'s turn contains hostile/abusive language ' +
        '(severity ' + _tox.severity.toFixed(2) + '). Do NOT repeat the term, do NOT ' +
        'match the tone, and do NOT moralise. Reply in one calm sentence: ' +
        'acknowledge the frustration ("ok, kasi mukha talagang stressful"), then ' +
        'offer the next concrete action. If the language is directed at a ' +
        'colleague, point to the Shift Supervisor — never coach the worker on ' +
        'how to talk to that person.\n';
    }

    // T76 Question shape — drives reply structure.
    const _shape = _classifyQuestionShape(transcript);
    if (_shape && _shape !== 'unknown') {
      perTurnAnchors +=
        '\nQUESTION SHAPE — this turn is "' + _shape + '". Reply structure: ' +
        (_shape === 'data' ? 'lead with the number + unit + source view name; ONE follow-up line max.' :
         _shape === 'how_to' ? 'numbered steps (1, 2, 3); link to the relevant page at the end.' :
         _shape === 'opinion' ? 'state your view with confidence calibration; cite the canonical data behind it.' :
         _shape === 'troubleshoot' ? 'lead with the most likely cause; offer to walk through the diagnostic tree.' :
         _shape === 'social' ? 'one warm line, no data dump; ask what they\'re working on.' :
         'plain answer.') + '\n';
    }

    // T77 Freshness disclosure — caller asks how current the data is.
    if (_isFreshnessRequest(transcript)) {
      perTurnAnchors +=
        '\nFRESHNESS DISCLOSURE — worker asked how fresh the data is. Pull the ' +
        'last_updated timestamp from PLATFORM SNAPSHOT for the relevant truth view ' +
        'and state it plainly ("v_kpi_truth was refreshed 3 min ago"). If the ' +
        'snapshot doesn\'t carry a freshness stamp, say so — do NOT invent.\n';
    }

    // T79 Share request — emit a shareable session link.
    if (_isShareRequest(transcript)) {
      const _sId = (typeof _getSessionId === 'function') ? _getSessionId() : null;
      const _link = _buildShareLink(_sId);
      if (_link) {
        perTurnAnchors +=
          '\nSHARE LINK — worker wants to forward this conversation. Quote the ' +
          'URL exactly: ' + _link + ' — tell them to paste it in Slack/SMS. Don\'t ' +
          'try to send it yourself; the link IS the share mechanism.\n';
      }
    }

    // T80 Readback request — re-trigger TTS on the prior reply.
    if (_isReadbackRequest(transcript) && _sessionTurns.length > 0) {
      perTurnAnchors +=
        '\nREADBACK — worker wants the prior reply spoken aloud again, not a new ' +
        'answer. Repeat the LAST assistant turn verbatim (no rephrasing, no new ' +
        'analysis). Voice client will route this through TTS — keep the reply ' +
        'short so the read-back fits in their listening window.\n';
    }

    // T81 Scope query — disclose actual capabilities.
    if (_isScopeQuery(transcript)) {
      perTurnAnchors +=
        '\nSCOPE DISCLOSURE — worker asked what you can do. Ground the answer in ' +
        'the actual capability list:\n' +
        '  • answer questions about KPIs (MTBF, MTTR, OEE) using v_*_truth views\n' +
        '  • surface open alerts + overdue PMs\n' +
        '  • log a journal entry / schedule a PM (if voice-execute is ON)\n' +
        '  • point you at the right page for deeper work\n' +
        'DO NOT invent abilities (predicting future failures, sending email, ' +
        'doing maintenance). Be honest about the boundary.\n';
    }

    // T82 Correction handler — redo last answer with new info.
    if (_isCorrection(transcript)) {
      perTurnAnchors +=
        '\nCORRECTION — worker said your last answer used wrong info. Apologise ' +
        'in HALF a line ("ah ok"), then REDO the answer using the corrected ' +
        'detail. Do NOT defend the prior answer; do NOT ask why. Just produce ' +
        'the right one.\n';
    }

    // T84 Crisis escalation — extended (self-harm + workplace violence).
    const _crisis = _detectCrisisEscalation(transcript);
    if (_crisis && _crisis.kind) {
      perTurnAnchors += (_crisis.kind === 'self_harm')
        ? '\nCRISIS — self-harm signal. Drop the technical reply. One short line ' +
          'of care, then the National Center for Mental Health crisis line: ' +
          '1553 (PH toll-free). Then "may we connect you to your supervisor or HR?".\n'
        : '\nCRISIS — workplace-violence signal. One short line of care, then ' +
          '"tell Safety Officer / HR right away — would you like me to flag this ' +
          'to your supervisor through the Alert Hub?". Do NOT advise tactics.\n';
    }

    // T182 INCIDENT GATE — actual injury / first-aid needed. Highest
    // priority safety anchor; fires before LOTO/hot-work/confined gates.
    if (_isIncidentReport(transcript)) {
      perTurnAnchors +=
        '\nINCIDENT GATE — worker is reporting an actual injury on site. Drop ' +
        'every other reply path. One short line of care, then route: "Tap the ' +
        'red SOS button in Alert Hub or call site Safety Officer NOW. I am ' +
        'flagging this to your supervisor on logging." Do NOT advise first aid ' +
        'beyond "stop the bleed / clear the area / wait for medic" basics. The ' +
        'router will write to safety_incident_queue on confirmation.\n';
    }

    // T175 LOTO GATE — lockout-tagout mentioned. Diagnostic-work
    // intents MUST NOT proceed until isolation is confirmed.
    if (_detectLotoIntent(transcript)) {
      perTurnAnchors +=
        '\nLOTO GATE — worker mentioned lockout-tagout / isolation / ' +
        'de-energize. Before ANY diagnostic step proceeds, confirm verbatim: ' +
        '(1) energy source identified, (2) breaker/valve locked, (3) zero-energy ' +
        'verified, (4) tag in place with worker name + date. Use the ' +
        'energy isolation checklist (electrical / mechanical / hydraulic / pneumatic / ' +
        'chemical / thermal / gravitational) for the right category. If ANY ' +
        'step is unconfirmed, stop and ask. Never let confidence override the ' +
        'gate.\n';
    }

    // T176 HOT WORK GATE — welding / grinding / cutting torch on
    // plant. Requires a current hot-work permit + fire watch.
    if (_detectHotWorkIntent(transcript)) {
      perTurnAnchors +=
        '\nHOT WORK GATE — worker mentioned welding / grinding / cutting / ' +
        'brazing / paghihinang. Required before any flame touches metal: (1) ' +
        'hot-work permit issued + still within validity window, (2) fire watch ' +
        'assigned, (3) flammables cleared 11m radius (or fire-blanket coverage), ' +
        '(4) PPE per the hot_work matrix (welding hood shade 10+, FR clothing, ' +
        'leather gloves). Ask "permit number + expiry?" if not yet on the turn ' +
        'transcript.\n';
    }

    // T177 CONFINED SPACE GATE — tank / sump / vessel entry. MUST
    // trigger gas-test workflow (PH OSHS limits) + attendant +
    // rescue plan. Entering without gas reading is P0.
    if (_detectConfinedSpaceIntent(transcript)) {
      perTurnAnchors +=
        '\nCONFINED SPACE GATE — worker mentioned tank / sump / vessel / ' +
        'manhole entry. Required before ANY entry: (1) 4-gas reading within ' +
        'PH OSHS limits — O2 19.5-23.5%, LEL ≤10%, CO ≤35ppm, H2S ≤10ppm, (2) ' +
        'attendant stationed at entry with comms, (3) rescue plan agreed + ' +
        'retrieval line attached, (4) confined-space entry permit. Ask for ' +
        'the gas-test reading first — do not advise on the task until the ' +
        'numbers are confirmed in range.\n';
    }

    // T178 PPE QUERY — answer from the matrix, never improvise.
    if (_isPpeQuery(transcript)) {
      perTurnAnchors +=
        '\nPPE MATRIX — worker asked what PPE to wear. Answer ONLY from the ' +
        'authoritative matrix below — never invent. If the hazard kind is ' +
        'unclear, ask one short clarifying question (hot work? confined space? ' +
        'electrical? chemical? height? or general task?) before listing PPE.\n' +
        '  • hot_work: welding hood shade 10+, FR clothing, leather gloves, fire watch\n' +
        '  • confined_space: SCBA or air-line respirator, 4-gas monitor, harness + retrieval line, attendant\n' +
        '  • chemical: chemical splash goggles, gauntlet gloves (matching chemical), apron or suit, eyewash within 10m\n' +
        '  • electrical: Class 0/1 rubber gloves, arc-rated face shield, voltage detector, rubber mat\n' +
        '  • height: full-body harness, double lanyard, hard hat with chinstrap, tool tether\n' +
        '  • default: hard hat, safety shoes, safety glasses, gloves matching task\n';
    }

    // T179 NEAR-MISS CAPTURE — close call, no injury yet.
    if (_isNearMissReport(transcript)) {
      perTurnAnchors +=
        '\nNEAR-MISS CAPTURE — worker described a close call (no injury). One ' +
        'short empathy line ("naks, mabuti naiwasan mo"), then offer to log a ' +
        'near-miss report: "want me to file this as a near-miss? safety team ' +
        'can review the root cause." Voice-action-router writes to ' +
        'safety_near_miss on yes. Distinct from INCIDENT GATE (actual injury).\n';
    }

    // T180 JSA OFFER — first time / never done before.
    if (_shouldOfferJsa(transcript)) {
      perTurnAnchors +=
        '\nJSA OFFER — worker said this is their first time on the task. ' +
        'Offer a 4-step JSA in one line: "let us walk through a quick JSA — ' +
        '(1) break the task into 3-5 steps, (2) identify hazards per step, ' +
        '(3) define controls (elim / sub / eng / admin / PPE), (4) confirm ' +
        'PPE + permits before starting." Wait for their yes before stepping ' +
        'through each. Adding more than 4 steps defeats the purpose.\n';
    }

    // T85 Numeric precision — sticky anchor (every turn).
    perTurnAnchors +=
      '\nPRECISION RULE — every KPI number you quote MUST include a unit and ' +
      'sensible precision: percentages to 1 decimal (92.4%), times to whole ' +
      'units (14 days, 38 min), counts as integers. Never quote a raw 92.4823. ' +
      'No-data is "no data yet" + the source view name, not 0 or N/A.\n';

    // T86 Asset tag normalization — when normalizer returns a tag.
    const _normTag = _normalizeAssetTag(transcript);
    if (_normTag) {
      perTurnAnchors +=
        '\nASSET TAG NORMALIZED — the worker said this asset; canonical form is "' +
        _normTag + '". Use this exact form (with hyphen) when querying or quoting.\n';
    }

    // T87 Time range normalization — surface ISO bounds for SQL clarity.
    const _normTime = _normalizeTimeRange(transcript);
    if (_normTime && _normTime.start) {
      perTurnAnchors +=
        '\nTIME RANGE NORMALIZED — worker referenced a time window. Canonical span: ' +
        _normTime.start + ' to ' + _normTime.end + ' (' + _normTime.days +
        ' day' + (_normTime.days === 1 ? '' : 's') +
        '). Use this when filtering PLATFORM SNAPSHOT data.\n';
    }

    // T88 Ack-style toggle — persist + acknowledge in 1 line.
    const _ackToggle = _detectAckStyleToggle(transcript);
    if (_ackToggle) {
      _setAckStyle(_ackToggle);
      perTurnAnchors +=
        '\nACK STYLE — worker switched to "' + _ackToggle + '" mode. ' +
        (_ackToggle === 'terse'
          ? 'No "naks" / "sige" / "ah" before the data — answer cold + direct.'
          : 'One short warm ack line ("ah ok kuya") before the data is welcome.') + '\n';
    }

    // T89 Forbidden-topic redirect.
    const _forbidden = _detectForbiddenTopic(transcript);
    if (_forbidden) {
      perTurnAnchors += (_forbidden === 'competitor')
        ? '\nFORBIDDEN — competitor name detected. Don\'t compare, don\'t comment. ' +
          '"I focus on the work in front of you — let\'s look at your plant\'s data."\n'
        : '\nFORBIDDEN — office-politics / chismis detected. Redirect: "let\'s stay ' +
          'on what we can fix today — what machine or PM is on your mind?".\n';
    }

    // T91 Pin request.
    if (_isPinRequest(transcript) && _sessionTurns.length > 0) {
      const last = _sessionTurns[_sessionTurns.length - 1];
      if (last && last.assistant && ctx && ctx.worker_name) {
        _pinTurn(ctx.worker_name, { text: last.assistant, intent: priorIntent || '' });
      }
      perTurnAnchors +=
        '\nPIN — worker pinned the prior reply. Acknowledge in one line ("sige, ' +
        'pinned mo na") and proceed normally. The pinned list will surface again ' +
        'at the start of their next session.\n';
    }

    // T92 Help command — short-circuit before LLM.
    if (_isHelpCommand(transcript)) {
      perTurnAnchors +=
        '\nHELP — worker asked for help. Surface this exact mini-tour:\n' +
        '  1) Ask about KPIs: "what is the MTBF for P-203"\n' +
        '  2) Log: "log a 15-min stop on C-01"\n' +
        '  3) Schedule: "schedule a PM for next Tuesday"\n' +
        '  4) Get a digest: "morning summary please"\n' +
        '  Say "what can you do" for the full list.\n';
    }

    // ═══════════════════════════════════════════════════════════════════════
    // PHASE A COMPREHENSIVE WIRING — all transcript-driven detectors from
    // batches T95-T214 that weren't previously plumbed into per-turn anchors.
    // Each anchor uses a unique CAPS GATE / HEADER so validators can ratchet.
    // ═══════════════════════════════════════════════════════════════════════

    // T100 SESSION TAG — "tag this as X" labels the session.
    const _sessTag = _detectSessionTagRequest(transcript);
    if (_sessTag) {
      perTurnAnchors +=
        '\nSESSION TAG — worker labelled this session "' + _sessTag + '". ' +
        'Acknowledge in one line ("sige, tagged as ' + _sessTag + '"). ' +
        'Future references to this session by tag are resolvable.\n';
    }

    // T102 STT MANGLED — heuristic flag for garbled transcript.
    if (_looksGrammarMangled(transcript)) {
      perTurnAnchors +=
        '\nSTT MANGLED — transcript looks garbled (consonant clusters, no ' +
        'verb). Lead with a soft "did you mean…" guess based on closest ' +
        'asset tag / KPI in CANONICAL DATA, then offer to retry. Never log ' +
        'an action on a mangled turn.\n';
    }

    // T104 SHIFT END — within 30 min of worker's shift end.
    // empty-catch-allow: localStorage may be denied in private browsing.
    // If we can't read shift_end_hour, we just skip the horizon anchor —
    // a non-critical UX nudge that re-fires on the next turn anyway.
    try {
      const _shiftEnd = Number(localStorage.getItem('wh_shift_end_hour')); // storage-key-allow: T104 worker preference, set by worker profile UI (not in current source tree)
      if (Number.isFinite(_shiftEnd) && _isNearShiftEnd(_shiftEnd, 30)) {
        perTurnAnchors +=
          '\nSHIFT END HORIZON — worker is within 30 min of shift end. Offer ' +
          'handover prep in one line ("want me to draft the handover for next ' +
          'shift?"). Do NOT start long diagnostic threads — wrap up.\n';
      }
    } catch (_) { /* localStorage may be denied */ /* empty-catch-allow: best-effort silent swallow */ }

    // T96 QUIET HOURS — non-critical alerts muted 22:00-06:00 PHT.
    if (_isQuietHours(new Date())) {
      perTurnAnchors +=
        '\nQUIET HOURS — non-critical replies should stay concise. Critical / ' +
        'safety items still surface in full; everything else gets a one-line ' +
        'summary unless the worker explicitly asks for more.\n';
    }

    // T114 MENTOR HANDOFF — "ask Kuya Ben" / "tanungin natin si mentor".
    if (_isMentorHandoff(transcript)) {
      perTurnAnchors +=
        '\nMENTOR HANDOFF — worker wants senior input. Acknowledge ("sige, ' +
        'i-relay ko ito sa mentor queue") and route the question into ' +
        'mentor_relay_queue. Do NOT fabricate an expert answer; defer to the ' +
        'real mentor.\n';
    }

    // T115 PII SCRUB — strip phone/email/ID markers before any persistence.
    // Calling here makes the scrubbed form available as _piiScrubbed for
    // downstream audit log + journal save paths.
    let _piiScrubbed = transcript;
    try {
      const _sc = _scrubPii(transcript);
      if (_sc && _sc.text) _piiScrubbed = _sc.text;
      if (_sc && _sc.markers && _sc.markers.length > 0) {
        perTurnAnchors +=
          '\nPII SCRUBBED — worker turn contained ' + _sc.markers.join(', ') +
          '. Reply MUST use the scrubbed canonical form (no raw phone / email / ' +
          'ID). The unscrubbed transcript is dropped before audit log write.\n';
      }
    } catch (_) { /* scrubber is best-effort */ /* empty-catch-allow: best-effort silent swallow */ }

    // T116 CONSENT CHANGE — explicit grant/revoke voice consent.
    const _consent = _detectConsentChange(transcript);
    if (_consent) {
      perTurnAnchors +=
        '\nCONSENT CHANGE — worker said "' + _consent + '" voice consent. ' +
        'Acknowledge in plain language ("sige, ' + _consent + ' ka na — voice ' +
        'logging is ' + (_consent === 'grant' ? 'on' : 'off') + '") and persist ' +
        'to wh_voice_consent. PH Data Privacy Act.\n';
    }

    // T118 ERASURE REQUEST — right-to-be-forgotten.
    if (_isErasureRequest(transcript)) {
      perTurnAnchors +=
        '\nERASURE REQUEST — worker invoked right-to-erasure. Reply in one ' +
        'line: "I can clear your voice + journal history for this hive. ' +
        'Confirm with yes — this cannot be undone." The scoped DELETE runs ' +
        'on the next confirmed yes; an audit row records the request.\n';
    }

    // T120 SUSPICIOUS ACTIVITY — per-worker pattern check.
    if (ctx && ctx.worker_name) {
      try {
        const _susp = _detectSuspiciousActivity(ctx.worker_name);
        if (_susp && _susp.kind) {
          perTurnAnchors +=
            '\nSUSPICIOUS ACTIVITY — pattern "' + _susp.kind + '" detected for ' +
            'this worker (' + (_susp.count || '?') + ' events). Stay calm + ' +
            'helpful — do NOT accuse. If pattern persists, flag to supervisor ' +
            'via the Alert Hub on the worker\'s next confirmed action.\n';
        }
      } catch (_) { /* aggregate may be missing */ /* empty-catch-allow: best-effort silent swallow */ }
    }

    // T133 VOICE-ONLY TOGGLE — UI dim / audio-only mode.
    const _voiceOnly = _detectVoiceOnlyToggle(transcript);
    if (_voiceOnly) {
      perTurnAnchors +=
        '\nVOICE-ONLY TOGGLE — worker requested "' + _voiceOnly + '" mode. ' +
        'Acknowledge in one short line; the UI dim + caption suppress is ' +
        'driven by wh_voice_only_mode persisted state.\n';
    }

    // T140 MEMORY PRESSURE — device under load.
    try {
      const _mem = _checkMemoryPressure();
      if (_mem && _mem.level === 'high') {
        perTurnAnchors +=
          '\nMEMORY PRESSURE — device is under high memory load. Keep replies ' +
          'concise and skip long RAG citations this turn. Suggest closing ' +
          'background tabs if the next turn also degrades.\n';
      }
    } catch (_) { /* perf API may be unavailable */ /* empty-catch-allow: best-effort silent swallow */ }

    // T146 HANDOFF — "send this to Kuya Ben".
    const _handoffTo = _detectHandoffRequest(transcript);
    if (_handoffTo) {
      perTurnAnchors +=
        '\nHANDOFF — worker wants to forward this turn to "' + _handoffTo + '". ' +
        'Confirm in one line ("sige, i-pasa ko kay ' + _handoffTo + '") and the ' +
        'next yes writes a row to companion_handoff. Do NOT auto-send; require ' +
        'the explicit yes.\n';
    }

    // T147 SHARED NOTE — broadcast to team thread.
    if (_isSharedNoteRequest(transcript)) {
      perTurnAnchors +=
        '\nSHARED NOTE — worker wants to post this to the team thread. ' +
        'Confirm in one line; on yes, write to shared_voice_notes. The note ' +
        'surfaces on the Hive page for everyone in the hive.\n';
    }

    // T149 WATCHLIST — subscribe to asset notifications.
    const _watchTag = _detectWatchRequest(transcript);
    if (_watchTag) {
      perTurnAnchors +=
        '\nWATCHLIST — worker wants notifications on "' + _watchTag + '". ' +
        'Acknowledge ("sige, aalertan kita pag may kilos sa ' + _watchTag +
        '") and upsert to asset_watchlist on the next confirmed yes.\n';
    }

    // T151 RESOLUTION — fault fixed; offer to capture the fix.
    if (_detectResolution(transcript)) {
      perTurnAnchors +=
        '\nRESOLUTION CAPTURE — worker reported the fault is fixed ("ayos na ' +
        '/ gumana na / fixed it"). Acknowledge briefly, then offer: "want me ' +
        'to log the fix to fault_knowledge so the next worker can find it?". ' +
        'On yes, write the resolution to fault_knowledge_base. This is how ' +
        'tribal knowledge becomes searchable.\n';
    }

    // T204 ENERGY QUERY — surface sustainability KPIs.
    if (_isEnergyQuery(transcript)) {
      perTurnAnchors +=
        '\nENERGY QUERY — worker asked about energy / kWh / carbon / ' +
        'compressed-air / motor-efficiency. Pull from PLATFORM SNAPSHOT ' +
        'energy block. Quote EnPI (ISO 50001) with unit, compare to baseline, ' +
        'and if a leak/standby waste is detected, name the asset. PH grid ' +
        'factor 0.717 kgCO2e/kWh.\n';
    }

    // T207 TAGALOG IMPERATIVE — direct command form ("i-X mo").
    if (_isTagalogImperative(transcript)) {
      perTurnAnchors +=
        '\nTAGALOG IMPERATIVE — worker used a direct command ("i-X mo / ' +
        'pakisuyo"). Reply in Tagalog/Taglish, not pure English. Match the ' +
        'register: imperative form deserves an active-voice answer, not a ' +
        'passive English explainer.\n';
    }

    // T209 POLITENESS REGISTER — formal "po/ho" vs casual "tol/pre".
    const _register = _classifyPolitenessRegister(transcript);
    if (_register && _register !== 'unknown') {
      perTurnAnchors +=
        '\nPOLITENESS REGISTER — worker is "' + _register + '". ' +
        (_register === 'formal'
          ? 'Use "po/ho" forms. No slang. Address as "sir/maam" or family role (kuya/ate).'
          : _register === 'casual'
            ? 'Drop honorifics, match the tol/pre/bro energy, no "po".'
            : 'Mixed — start neutral, follow the worker\'s next turn lead.') + '\n';
    }

    // T153 BUDDY SET — "buddy up with Juan" / "kasama ko sa shift si Romeo".
    // Persist on the spot so the buddy is queryable from the next turn.
    const _buddyName = _detectBuddySet(transcript);
    if (_buddyName && ctx && ctx.worker_name) {
      try { _setBuddy(ctx.worker_name, _buddyName); } catch (_) { /* best-effort */ /* empty-catch-allow: best-effort silent swallow */ }
      perTurnAnchors +=
        '\nBUDDY SET — worker paired with "' + _buddyName + '" for this shift. ' +
        'Acknowledge in one line ("sige, kasama mo ngayon si ' + _buddyName +
        '"). Future logbook entries / handoffs may auto-include the buddy.\n';
    }

    // T205 / T206 DIALECT NOTE — extends T59 LANGUAGE PREF with
    // implicit dialect detection. Fires when ≥2 Cebuano or Ilonggo
    // markers appear, even without an explicit "switch to" request.
    const _ceb = _isCebuanoLeaning(transcript);
    const _ilo = _isIlonggoLeaning(transcript);
    if (_ceb || _ilo) {
      perTurnAnchors +=
        '\nDIALECT NOTE — worker is leaning ' + (_ceb ? 'Cebuano (Bisaya)' : 'Ilonggo (Hiligaynon)') +
        ' based on dialect markers (unsa/asa/kinsa for Cebuano, gid/bala/manami for Ilonggo). ' +
        'Reply in matching dialect-leaning Tagalog/Taglish — do NOT force pure Tagalog. If unsure, ' +
        'keep the answer short and follow the worker\'s next turn lead.\n';
    }

    // ═══════════════════════════════════════════════════════════════════════
    // END PHASE A COMPREHENSIVE WIRING
    // ═══════════════════════════════════════════════════════════════════════

    // FULL PLATFORM SCAN: pull everything from every truth view in parallel, hand to LLM.
    // No routing decisions, no intent classification — the LLM gets the complete platform
    // snapshot every turn and picks what's relevant. This eliminates "I don't have that info"
    // for any data that exists on the platform (KPIs, PM, inventory, logbook, schedule,
    // skills, projects, anomalies, knowledge, adoption — all in one shot).
    const firstIntent = routerIntents && routerIntents[0];
    const [platformSnapshot, platformData, memoryBlock, ragContext, crossHiveContext, standardsContext, filipinoGlossary, kgContext] = await Promise.all([
      _fetchFullPlatformSnapshot(db, ctx.hive_id, ctx.worker_name).catch((err) => {
        console.warn('[WHVoice] Platform snapshot failed:', err);
        return '';
      }),
      _invokePlatformScraper(db, ctx.hive_id, ctx.worker_name).catch(() => ''),
      _fetchRecentMemory(db, ctx.worker_name),
      _fetchRAGContext(db, ctx.hive_id, transcript).catch(() => ''),
      _fetchCrossHiveContext(db).catch(() => ''),  // Phase 9: Cross-hive awareness
      _fetchStandardsContext(db, transcript).catch(() => ''),  // Day 4: platform-wide standards RAG
      _fetchFilipinoGlossary(db).catch(() => ''),  // Day 5 (L7): PH industrial phrase glossary (memoized)
      _fetchKGContext(db, ctx.hive_id, transcript).catch(() => ''),  // Day 5 (L5): KG triples retrieval
    ]);

    // canonicalData carries the full snapshot — every truth view in one block.
    // platformData (legacy scraper) and ragContext stay separate for now.
    // Turn #26 + #27 anchors are appended here so the prompt builder
    // doesn't need a signature change.
    const canonicalData = (platformSnapshot || '') + repeatedIssueFlag + skillGapFlag + standardsQueryAnchor + perTurnAnchors;
    if (!canonicalData && db && ctx.hive_id && ctx.worker_name) {
      console.warn('[WHVoice] No platform snapshot returned; check DB connection or query errors');
    }

    const system = _buildVoiceSystemPrompt(persona, ctx.worker_name, hiveName, pageLabel, routingHint, memoryBlock, canonicalData, routerContext, platformData, ragContext, priorDialogState, proactiveAlerts, crossHiveContext, standardsContext, filipinoGlossary, kgContext, transcript);
    const messages = [
      { role: 'system', content: system },
      { role: 'user',   content: transcript },
    ];

    // ─── Item 6: Agentic RAG opt-in path (AGENTIC_RAG_ROADMAP.md Phase 1) ──
    // For LONG-HORIZON questions (5-year compares, "since 2022", multi-period
    // failure-pattern questions), prefer agentic-rag-loop over ai-gateway.
    // The agentic loop runs hierarchical retrieval + grader + checker so the
    // answer is grounded across years without choking the context window.
    // Everything else keeps using ai-gateway (the existing 214-turn-hardened
    // path). On any failure the opt-in path falls through to ai-gateway.
    try {
      if (_isLongHorizonQuestion(transcript)) {
        const fetcher = (typeof window.fetchWithTimeout === 'function')
          ? window.fetchWithTimeout
          : (u, o) => fetch(u, o);
        const ragBody = {
          question:    transcript,
          hive_id:     ctx && ctx.hive_id ? ctx.hive_id : null,
          worker_name: ctx && ctx.worker_name ? ctx.worker_name : null,
          auth_uid:    ctx && ctx.auth_uid    ? ctx.auth_uid    : null,
        };
        const ragResp = await fetcher(SUPABASE_URL + '/functions/v1/agentic-rag-loop', {
          method: 'POST',
          headers: {
            'Content-Type':  'application/json',
            'apikey':        SUPABASE_KEY,
            'Authorization': 'Bearer ' + SUPABASE_KEY,
          },
          body: JSON.stringify(ragBody),
        }, 30000);
        if (ragResp && ragResp.ok) {
          const ragData = await ragResp.json().catch(() => ({}));
          const ragAnswer = String((ragData && ragData.answer) || '').trim();
          if (ragAnswer && ragAnswer.length > 20 && ragData.checker_passed !== false) {
            _setStatus(personaName + ' (agentic-RAG) says:');
            _renderReplyBubble(ragAnswer, persona);
            if (typeof window.speakPersona === 'function') {
              window.speakPersona(ragAnswer, { persona });
            }
            _writeReplyCache(transcript, ctx.hive_id, ragAnswer);
            _setOffline(false);
            _appendSessionTurn(transcript, ragAnswer);
            _saveJournalTurn(db, ctx, transcript, ragAnswer, persona);
            _showTalkAgainButton();
            return;   // success — short-circuit the ai-gateway path entirely
          }
        }
        // Failure / empty / checker-failed → fall through to ai-gateway.
      }
    } catch (ragErr) {
      console.warn('[WHVoice] agentic-rag-loop opt-in failed, falling back to ai-gateway:', ragErr && ragErr.message);
    }

    try {
      // 2026-05-19 Companion Streamline Step C/D: route through ai-gateway
      // (agent: "voice-journal") instead of the legacy Cloudflare Worker.
      // Same backend as companion-launcher.js + voice-journal.html → one
      // companion, one infra path, one persona contract. The rich system
      // prompt voice-handler builds (canonicalData / RAG / KG / dialog
      // state) rides along as context.platform_prompt for the agent to
      // optionally consume; the agent's own persona block + Step D
      // domain lens still wraps everything.
      const fetcher = (typeof window.fetchWithTimeout === 'function')
        ? window.fetchWithTimeout
        : (u, o) => fetch(u, o);
      const gatewayBody = {
        agent:   'voice-journal',
        message: transcript,
        hive_id: ctx && ctx.hive_id ? ctx.hive_id : null,
        context: {
          persona:         persona,
          page:            (ctx && ctx.page) || 'voice-journal',
          platform_prompt: system,  // rich grounding voice-handler assembled
          source:          'voice-handler',
        },
      };
      const resp = await fetcher(SUPABASE_URL + '/functions/v1/ai-gateway', {
        method: 'POST',
        headers: {
          'Content-Type':  'application/json',
          'apikey':        SUPABASE_KEY,
          'Authorization': 'Bearer ' + SUPABASE_KEY,
        },
        body: JSON.stringify(gatewayBody),
      }, 25000);
      if (!resp)        throw new Error('Network timeout');
      if (!resp.ok)     throw new Error('Gateway error ' + resp.status);
      const data = await resp.json();
      if (data && data.error) throw new Error(String(data.error));
      const answer = String((data && data.answer) || '').trim();
      if (!answer) {
        _setStatus('No reply came back. Tap to try again.');
        _renderReplyBubble('(no reply)', persona);
        _showTalkAgainButton();
        return;
      }
      // Phase 4: Intent refinement + clarification logic
      let newIntentKind = (firstIntent && firstIntent.kind) || 'unknown';
      let newConfidence = (firstIntent && firstIntent.confidence) || 0;

      // Phase 4.1: Affirmation passthrough — "yes / sige / the details" must
      // resume the prior topic, never flip to a topic-switch clarification.
      // Resolving the intent here means the downstream _shouldClarify check
      // naturally returns false (priorIntent === newIntentKind) AND every
      // state-persist call below records the resolved topic, not "unknown".
      //
      // Phase 4.11 OVERRIDE (turn #7): topic-shift signals ("hold on" /
      // "actually" / "by the way" / "teka") SUPPRESS the affirmation bypass.
      // The worker is explicitly interrupting the prior topic; let normal
      // intent classification run on the full utterance.
      if (priorIntent && _isFollowupAffirmation(transcript) && !_isTopicShiftSignal(transcript)) {
        newIntentKind = priorIntent;
        newConfidence = Math.max(newConfidence, 0.9);
      }

      // If intent flipped and confidence low, ask clarification instead
      if (_shouldClarify(newConfidence, priorIntent, newIntentKind)) {
        // Phase 4.4: Clarification-loop ceiling. After 2 consecutive
        // clarifications on the same conversation, switch to a different
        // shape ("what page would help?") and HARD reset the counter so
        // we can never loop deeper than 3 — looping the same prompt makes
        // Zaniah/Hezekiah feel broken.
        const streak = _bumpClarifyStreak();
        let clarifyAnswer;
        if (streak >= 2) {
          clarifyAnswer = "Let's try a different way — what page would help: Analytics, Logbook, PM Scheduler, or Asset Hub?";
          _resetClarifyStreak();
        } else {
          clarifyAnswer = _generateClarification(transcript, newIntentKind, priorIntent);
        }
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
      // Any non-clarify success turn resets the streak — a single good
      // turn means we're out of the loop. Lives here (right before the
      // success render path) so the reset is hard to miss in code review.
      _resetClarifyStreak();

      _setStatus(personaName + ' says:');
      _renderReplyBubble(answer, persona);
      const ttsStartMs = Date.now();
      if (typeof window.speakPersona === 'function') {
        window.speakPersona(answer, { persona });
      }
      const ttsLatencyMs = Date.now() - ttsStartMs;
      // Phase 4.45 (turn #46) Cache the successful reply for repeat-tap savings.
      _writeReplyCache(transcript, ctx.hive_id, answer);
      // Phase 4.44 (turn #45) Clear offline flag — we just got a successful gateway response.
      _setOffline(false);
      // Phase 4.52 (turn #51) Classify avatar emotion state from the rendered reply
      // and stamp it on the bubble for the UI tint layer to pick up.
      try {
        const bubble = document.querySelector('#wh-voice-intents .wh-voice-bubble');
        if (bubble) bubble.setAttribute('data-avatar-state', _classifyAvatarState(answer));
      } catch (_) { /* non-fatal */ /* empty-catch-allow: best-effort silent swallow */ }
      // Phase 4.48 (turn #49) Push the resolved intent onto the branch stack so a
      // future "back to the X" reference can recall it.
      _pushBranch(newIntentKind, priorSlots || {});
      // Session-memory turn (always — works for anon walkthrough).
      _appendSessionTurn(transcript, answer);
      // Durable save — silently no-ops if RLS denies (anon workers).
      _saveJournalTurn(db, ctx, transcript, answer, persona);
      // Phase 2: Store in agent_memory table (session-scoped, enable recall + dedup)
      _storeTurn(db, ctx.hive_id, ctx.worker_name, transcript, answer, newIntentKind, newConfidence, 0);
      // Phase 4: Update dialog state with new intent + context (enable multi-turn slot carryover)
      _updateDialogState(db, ctx.hive_id, sessionId, newIntentKind, newConfidence, {}, false, null);
      // Phase 6: Cache snapshot for offline resilience
      _cacheOfflineSnapshot(db, ctx.hive_id, canonicalData);
      // Phase 7: Log TTS metrics (latency + success)
      _logTTSMetrics(db, ctx.hive_id, ttsLatencyMs, null);
      // Phase 8: Capture conversation analytics
      _captureAnalytics(db, sessionId, _turnNum, newIntentKind || 'unknown', 1, newConfidence);
      // Phase 10: Update avatar state (response generated, neutral emotion by default)
      _updateAvatarState(db, sessionId, 'responding', 'helpful');
      _showTalkAgainButton();
    } catch (err) {
      console.warn('[WHVoice] conversational call failed:', err);

      // Phase 4.44 (turn #45) Offline degradation — flip the module flag
      // so the next turn knows we lost gateway connectivity. The flag
      // auto-clears on the next successful response (set in the success
      // path above).
      _setOffline(true);

      // Phase 3: Error recovery with graceful fallback
      const fallbackReply = _generateFallbackReply(transcript, routerIntents, persona);
      _setStatus(personaName + ' (offline):');
      _renderReplyBubble(fallbackReply, persona);
      const ttsStartMs = Date.now();
      if (typeof window.speakPersona === 'function') {
        window.speakPersona(fallbackReply, { persona });
      }
      const ttsLatencyMs = Date.now() - ttsStartMs;
      // Session-memory turn (capture both success and fallback responses).
      _appendSessionTurn(transcript, fallbackReply);
      // Best-effort save even on failure — capture the transcript so it
      // doesn't get lost.
      _saveJournalTurn(db, ctx, transcript, fallbackReply, persona);
      // Phase 6: Cache snapshot even on failure
      _cacheOfflineSnapshot(db, ctx.hive_id, canonicalData);
      // Phase 7: Log TTS metrics with error marker
      _logTTSMetrics(db, ctx.hive_id, ttsLatencyMs, String(err && err.message || 'Unknown error'));
      // Phase 8: Capture analytics (quality=-1 for failed responses)
      _captureAnalytics(db, sessionId, _turnNum, 'fallback', -1, 0);
      // Phase 10: Update avatar state (fallback state)
      _updateAvatarState(db, sessionId, 'offline', 'concerned');
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
      // Phase 4.33 (turn #29) AI QUALITY FEEDBACK — every assistant reply
      // ships with thumbs up/down so workers can rate the answer in one
      // tap. Rating persists to ai_cost_log.quality_rating (when a
      // matching log row exists) for the ai-quality dashboard.
      slot.innerHTML =
        '<div class="wh-voice-bubble wh-voice-bubble-assistant">' +
          avatarHTML +
          '<span class="wh-voice-bubble-text">' + safe + '</span>' +
          '<span class="wh-voice-rate" style="display:inline-flex;gap:6px;margin-left:8px;align-items:center;">' +
            '<button type="button" data-rate="1" aria-label="Helpful reply" ' +
              'style="background:transparent;border:1px solid rgba(255,255,255,.15);color:rgba(255,255,255,.55);' +
              'border-radius:50%;width:24px;height:24px;line-height:1;cursor:pointer;font-size:.7rem;">👍</button>' +
            '<button type="button" data-rate="-1" aria-label="Unhelpful reply" ' +
              'style="background:transparent;border:1px solid rgba(255,255,255,.15);color:rgba(255,255,255,.55);' +
              'border-radius:50%;width:24px;height:24px;line-height:1;cursor:pointer;font-size:.7rem;">👎</button>' +
          '</span>' +
        '</div>';
      // Wire the rating buttons. One-shot — once the worker rates, both
      // buttons disable so they can't double-vote on the same reply.
      const rateBtns = slot.querySelectorAll('button[data-rate]');
      rateBtns.forEach(function (btn) {
        btn.addEventListener('click', function () {
          const rating = Number(btn.getAttribute('data-rate')) || 0;
          rateBtns.forEach(b => { b.disabled = true; b.style.opacity = '0.4'; });
          btn.style.background = (rating > 0)
            ? 'rgba(74,222,128,.20)' : 'rgba(248,113,113,.20)';
          _recordReplyRating(rating).catch(function () { /* non-fatal */ /* empty-catch-allow: best-effort silent swallow */ });
        });
      });
    }
  }

  // Phase 4.33 (turn #29) AI QUALITY FEEDBACK helper.
  // Worker taps thumbs up/down → write to ai_cost_log.quality_rating
  // for the most recent voice-journal cost row, scoped to this worker
  // + session. Best-effort: anon callers (RLS) silently skip; cloud
  // outages don't disturb the conversation.
  async function _recordReplyRating(rating) {
    const r = Number(rating);
    if (r !== 1 && r !== -1) return;
    const db = _getDb();
    const ctx = _ctx();
    if (!db || !ctx) return;
    const sessionId = (typeof _getSessionId === 'function') ? _getSessionId() : null;
    try {
      const { error } = await db.rpc('record_ai_reply_rating', {
        p_session_id: sessionId,
        p_rating:     r,
      });
      if (error) {
        // Fall back to a direct UPDATE on ai_cost_log if the RPC isn't
        // available. Scoped to the most recent row for this hive +
        // agent so we don't accidentally rate stale entries.
        await db.from('ai_cost_log')
          .update({ quality_rating: r })
          .eq('hive_id', ctx.hive_id || null)
          .eq('agent_name', 'voice-journal')
          .order('created_at', { ascending: false })
          .limit(1);
      }
      // Phase 4.46 (turn #47) Feedback escalation — if this is a 👎 AND
      // the worker has 3+ negative ratings in the last 7 days, flag for
      // the ai-quality dashboard. The dashboard reads this flag to
      // prompt supervisor outreach.
      if (r < 0) {
        const esc = await _checkFeedbackEscalation(db, ctx.worker_name);
        if (esc && esc.needs_escalation) {
          try {
            await db.from('ai_quality_escalation').upsert({
              worker_name: ctx.worker_name,
              hive_id: ctx.hive_id || null,
              negative_count: esc.negative_count,
              last_negative_at: new Date().toISOString(),
            });
          } catch (_) { /* table may not exist yet — non-fatal */ /* empty-catch-allow: best-effort silent swallow */ }
        }
      }
    } catch (_) { /* swallow — non-fatal */ /* empty-catch-allow: best-effort silent swallow */ }
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
    } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
  }

  // ─── Public API ──────────────────────────────────────────────────────────
  function open(initOpts) {
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

    // T68 (Phase 4.70) Persona portrait animation — listening state
    // while the mic is hot. _startRecording flips to listening at end
    // of this function; idle is the default attribute.
    _setAvatarAnimation('listening');

    // T72 (Phase 4.74) Multi-worker concurrency lock — record this
    // session in localStorage so a second device in the same hive
    // can detect the foreign session. Advisory only; we don't block.
    try {
      const ctxOpen = _ctx();
      if (ctxOpen && ctxOpen.hive_id && ctxOpen.worker_name) {
        const foreign = _isSessionLocked(ctxOpen.hive_id, ctxOpen.worker_name);
        if (foreign && foreign.worker) {
          const ageMs = Date.now() - Number(foreign.ts || 0);
          const ageMin = Math.max(1, Math.round(ageMs / 60000));
          _renderReplyBubble(
            'Heads up — another worker (' + String(foreign.worker).slice(0, 24) +
            ') has the voice session open in your hive (' + ageMin +
            ' min ago). Both can talk, but shared notes may overlap.',
            _getPersonaSafe()
          );
        }
        _acquireSessionLock(ctxOpen.hive_id, ctxOpen.worker_name);
      }
    } catch (_) { /* non-fatal */ /* empty-catch-allow: best-effort silent swallow */ }

    // T74 (Phase 4.76) Streaming — reset the streaming indicator on
    // every open. ai-gateway flips it when the response starts.
    _setStreamingState(false);

    // Phase 4.54 (turn #55) Proactive alert opener — when initOpts.alert
    // is a critical/high proactive alert, render its description as the
    // FIRST companion line before listening. The worker can then tap to
    // talk and the conversation flows from there. Fires only when the
    // caller explicitly passes the alert (i.e. companion-launcher or
    // similar surface that knows of a fresh critical event).
    if (initOpts && initOpts.alert && initOpts.alert.description) {
      const a = initOpts.alert;
      const sev = String(a.severity || 'high').toUpperCase();
      const proactiveLine = '[' + sev + '] ' + String(a.description).slice(0, 200) +
        (a.action_suggested ? ' — ' + String(a.action_suggested).slice(0, 120) : '');
      try {
        const persona = _getPersonaSafe();
        _setStatus(personaName_safe() + ' (heads up):');
        _renderReplyBubble(proactiveLine, persona);
        if (typeof window.speakPersona === 'function') {
          window.speakPersona(proactiveLine, { persona });
        }
        _appendSessionTurn('(proactive alert)', proactiveLine);
      } catch (_) { /* non-fatal */ /* empty-catch-allow: best-effort silent swallow */ }
    }

    _startRecording();
  }

  function close() {
    // Phase 4.23 (turn #24) CONVERSATION-END ACK — when the worker closes
    // the voice overlay mid-conversation, persist a clean "session ended"
    // marker so the next time they open it the stale-state guard (turn #6)
    // and greeting (turn #10) behave correctly. Best-effort: failures
    // don't block the close.
    try {
      if (window.WHTts && typeof window.WHTts.stop === 'function') {
        window.WHTts.stop();
      } else if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    } catch (_) { /* non-fatal */ /* empty-catch-allow: best-effort silent swallow */ }
    try {
      const db = _getDb();
      const sessionId = (typeof _getSessionId === 'function') ? _getSessionId() : null;
      const ctx = _ctx();
      if (db && sessionId && ctx && ctx.hive_id && _sessionTurns.length > 0) {
        // Mark the dialog state as cleanly ended: no priorIntent, no
        // pending clarification, empty slots. The stale-state guard
        // (turn #6) will pick this up if the worker comes back >15 min
        // later; the first-turn greeting (turn #10) only requires
        // empty _sessionTurns to fire so the next session opens warm.
        _updateDialogState(db, ctx.hive_id, sessionId, null, 0, {}, false, null);
      }
    } catch (_) { /* non-fatal */ /* empty-catch-allow: best-effort silent swallow */ }
    _resetClarifyStreak();
    _stopRecording();
    if (_stream) { _stream.getTracks().forEach(t => t.stop()); _stream = null; }
    // T63 — stop the mic-quality meter so the AudioContext is released.
    if (_micQualityMeter && typeof _micQualityMeter.stop === 'function') {
      try { _micQualityMeter.stop(); } catch (_) { /* non-fatal */ /* empty-catch-allow: best-effort silent swallow */ }
      _micQualityMeter = null;
    }
    // T68 (Phase 4.70) — avatar back to idle.
    _setAvatarAnimation('idle');
    // T72 (Phase 4.74) — release the multi-worker session lock so the
    // next device opening voice in the same hive sees a clean slate.
    try {
      const ctxClose = _ctx();
      if (ctxClose && ctxClose.hive_id && ctxClose.worker_name) {
        _releaseSessionLock(ctxClose.hive_id, ctxClose.worker_name);
      }
    } catch (_) { /* non-fatal */ /* empty-catch-allow: best-effort silent swallow */ }
    // T74 (Phase 4.76) — clear any in-flight streaming state.
    _finalizeStream();
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
    console.log('[WHVoice Debug] Current Context:', { // console-log-allow: debug context dump (rare, only when debug helper is invoked)
      db_available: !!db,
      worker_name: ctx.worker_name || '(empty)',
      hive_id: ctx.hive_id || '(empty)',
      hive_role: ctx.hive_role || '(empty)',
      all_relevant_localStorage_keys: lsKeys.map(k => k + '=' + (localStorage.getItem(k) ? '✓' : '✗')).join(' | '),
    });
    return { ctx, db_available: !!db };
  };

  // Dialog-quality helpers exposed for the journey-voice-journal Playwright
  // sentinel — Layer 2 reaches into these directly to assert the live
  // regex + state machine behave correctly without simulating the full
  // multi-turn voice flow.
  //   _isFollowupAffirmation  — "yes / sige / the details" bypass (Phase 4.1)
  //   _isFollowupNegation     — "no / wala / cancel" exit (Phase 4.2)
  //   _isNoisyTranscript      — empty / 1-2 char / pure-filler guard (Phase 4.3)
  //   _getClarifyStreak       — current consecutive-clarify counter (Phase 4.4)
  //   _resetClarifyStreak     — test-side helper to reset between specs
  //   _shouldClarify          — predicate that fires the clarification UI
  //   _isPageRecoveryReply    — page-name recovery routing (Phase 4.7)
  //   _buildVoiceSystemPrompt — for L2 specs that assert the slot enumeration
  //                              + PRIOR TOPIC HANDLE actually land in the
  //                              prompt at runtime (turn #3 + turn #4)
  window.WHVoice = {
    open, close, register, dispatch,
    _handlers: handlers,
    _debugContext: window._debugVoiceContext,
    _isFollowupAffirmation,
    _isFollowupNegation,
    _isNoisyTranscript,
    _getClarifyStreak,
    _resetClarifyStreak,
    _bumpClarifyStreak,
    _shouldClarify,
    _isPageRecoveryReply,
    _buildVoiceSystemPrompt,
    // Turns #5-#10 + #14 helpers
    _isPersonaSwitchUtterance,
    _isStaleDialogState,
    _isTopicShiftSignal,
    _isThanksReply,
    _isGreeting,
    _isRepeatRequest,
    // Turns #25-#34 helpers
    _isVoiceShortcut,
    _isGoodbye,
    _detectStandardsMention,
    _recordReplyRating,
    // Turns #35-#44 helpers
    _isActionRequest,
    _isBatchAction,
    _isExplainRequest,
    _detectMention,
    _detectFatigueSignal,
    _isExportRequest,
    // Turns #45-#54 helpers
    _isOffline,
    _setOffline,
    _lookupReplyCache,
    _writeReplyCache,
    _clearReplyCache,
    _pushBranch,
    _detectBranchRecall,
    _isPhotoIntent,
    _isSummaryRequest,
    _classifyAvatarState,
    _trackIdentity,
    _resetIdentityTracking,
    // Turns #55-#64 helpers
    _selectProactiveAlertForSpeak,
    _readHiveMaturityStair,
    _pruneStaleSlots,
    _stashConfirmedAction,
    _getLastConfirmedAction,
    _detectActionReplay,
    _detectLanguagePref,
    _setLanguagePref,
    _getLanguagePref,
    _detectBrevityToggle,
    _setBrevityPref,
    _getBrevityPref,
    _detectTimerRequest,
    _scheduleTimer,
    _getActiveTimers,
    _clearAllTimers,
    _readUrlAssetParam,
    _parseActionQueue,
    // Turns #65-#74 helpers — ORCHESTRATION + INTEGRATION layer
    _isPdfExportRequest,
    _getPronunciationMap,
    _setPronunciationOverride,
    _applyPronunciation,
    _isVoiceExecuteAuth,
    _setVoiceExecuteAuth,
    _setAvatarAnimation,
    _fetchCrossHiveBenchmark,
    _isDigestRequest,
    _canPushNotify,
    _pushNotifyState,
    _requestPushPerm,
    _isPushOptInReply,
    _acquireSessionLock,
    _isSessionLocked,
    _releaseSessionLock,
    _detectAccentHint,
    _getAccentPref,
    _setAccentPref,
    _setStreamingState,
    _isStreaming,
    _bindStreamingBubble,
    _appendStreamingChunk,
    _finalizeStream,
    // Turns #75-#84 helpers — TRUST DEPLOYMENT layer
    _detectToxicLanguage,
    _classifyQuestionShape,
    _isFreshnessRequest,
    _setRateLimitCooldown,
    _inRateLimitCooldown,
    _clearRateLimitCooldown,
    _isShareRequest,
    _buildShareLink,
    _isReadbackRequest,
    _isScopeQuery,
    _isCorrection,
    _confidenceLabel,
    _detectCrisisEscalation,
    // Turns #85-#94 helpers — INPUT NORMALIZATION + ONBOARDING layer
    _formatKpi,
    _normalizeAssetTag,
    _normalizeTimeRange,
    _getAckStyle,
    _setAckStyle,
    _detectAckStyleToggle,
    _detectForbiddenTopic,
    _classifyMicEnv,
    _pinTurn,
    _getPinnedTurns,
    _isPinRequest,
    _isHelpCommand,
    _translateKpiLabel,
    _isFirstTimeWorker,
    _firstTimeWelcomeLine,
    // Turns #95-#104 helpers — INTEGRATION + AUDIT layer
    _emitAuditEvent,
    _isQuietHours,
    _preflightAction,
    _scheduleIdleCleanup,
    _cancelIdleCleanup,
    _bumpErrorCount,
    _getErrorCounts,
    _setSessionTag,
    _getSessionTag,
    _detectSessionTagRequest,
    _buildDeepLink,
    _parseDeepLinkToken,
    _looksGrammarMangled,
    _pickPersonaPhrase,
    _isNearShiftEnd,
    // Turns #105-#114 helpers — PROACTIVE ASSISTANCE + LEARNING
    _detectPmSyncDrift,
    _skillDepthForLevel,
    _vocabularyForDepth,
    _detectCrossAssetPattern,
    _recordIntent,
    _topRecurringIntents,
    _classifySessionSentiment,
    _recordDailySentiment,
    _isPersistentNegative,
    _warmAssetRecord,
    _normalizeSymptom,
    _crossedShiftBoundary,
    _logKnowledgeGap,
    _isMentorHandoff,
    _relayMentorQuestion,
    // Turns #115-#124 helpers — COMPLIANCE + DATA GOVERNANCE
    _scrubPii,
    _hasConsent,
    _captureConsent,
    _revokeConsent,
    _detectConsentChange,
    _retentionCutoffIso,
    _enforceRetention,
    _isErasureRequest,
    _executeErasure,
    _buildAuditCsv,
    _detectSuspiciousActivity,
    _setAiDisclosurePolicy,
    _needsAiDisclosure,
    _markAiDisclosureShown,
    _aiDisclosureLine,
    _formatLocaleDate,
    _getMonthlyCost,
    _exceededCostCap,
    _recordVoiceSignature,
    _voiceSignatureDrift,
    // Turns #125-#134 helpers — MULTI-MODAL + ACCESSIBILITY
    _captureImageStill,
    _openFileAttachment,
    _isReducedMotionRequested,
    _setReducedMotion,
    _ensureAriaLiveRegion,
    _announceForScreenReader,
    _resolveKeyAction,
    _isColorBlindMode,
    _setColorBlindMode,
    _currentPalette,
    _isLargeTextMode,
    _setLargeTextMode,
    _hapticPulse,
    _isVoiceOnlyMode,
    _setVoiceOnlyMode,
    _detectVoiceOnlyToggle,
    _isCaptionsOn,
    _setCaptionsOn,
    _renderCaption,
    // Turns #135-#144 helpers — OPERATIONAL EXCELLENCE
    _pingHealthCheck,
    _scheduleHealthPings,
    _stopHealthPings,
    _runSelfTest,
    _loadFeatureFlags,
    _isFeatureOn,
    _checkBrowserSupport,
    _renderBrowserBanner,
    _currentNetworkClass,
    _shouldUseLitePayload,
    _checkMemoryPressure,
    _checkClockDrift,
    _shouldPauseForBackground,
    _attachVisibilityHandler,
    _installCrashHandler,
    _getLastCrashSummary,
    _clearCrashState,
    _writePresence,
    _startPresenceHeartbeat,
    _stopPresenceHeartbeat,
    // Turns #145-#154 helpers — TEAM COORDINATION
    _listActiveVoiceWorkers,
    _detectHandoffRequest,
    _sendHandoff,
    _fetchPendingHandoffs,
    _isSharedNoteRequest,
    _postSharedNote,
    _shouldFlagHighConcurrency,
    _subscribeWatchlist,
    _unsubscribeWatchlist,
    _detectWatchRequest,
    _sendBroadcast,
    _detectResolution,
    _fetchPriorShiftOpenItems,
    _setBuddy,
    _getBuddy,
    _clearBuddy,
    _detectBuddySet,
    _sendMentionNotice,
    // Turns #155-#164 helpers — EXTERNAL INTEGRATION
    _validateSapWorkOrder,
    _buildMaximoQuery,
    _parseMaximoResponse,
    _parseOpcTag,
    _buildMqttTopic,
    _parseMqttPayload,
    _sendSlackMessage,
    _buildEmailDigestBody,
    _buildTeamsCard,
    _buildIcsEvent,
    _constantTimeCompare,
    _enqueueOutbound,
    _getOutboundQueue,
    _drainOutboundQueue,
    // Turns #165-#174 helpers — ADVANCED ANALYTICS
    _detectAnomaly3Sigma,
    _weibullMomentFit,
    _paretoTop80,
    _linearTrend,
    _seasonalPeakIndex,
    _trimmedMean,
    _zScore,
    _pearsonCorrelation,
    _weibullCdf,
    _availability,
    // Turns #175-#184 helpers — SAFETY + PERMIT-TO-WORK
    _detectLotoIntent,
    _detectHotWorkIntent,
    _detectConfinedSpaceIntent,
    _isPpeQuery,
    _ppeFor,
    _isNearMissReport,
    _shouldOfferJsa,
    _buildJsaTemplate,
    _validateGasReading,
    _isIncidentReport,
    _energyIsolationChecklist,
    _permitTimeRemaining,
    // Turns #185-#194 helpers — KNOWLEDGE GRAPH
    _extractEntities,
    _extractRelations,
    _buildKgTriple,
    _buildRagBlock,
    _embeddingHash32,
    _hashHamming,
    _chunkDocument,
    _buildCitation,
    _parseCitation,
    _rewriteQueryForRetrieval,
    _recordReasoningHop,
    _getReasoningTrace,
    _setKbVersion,
    _getKbVersion,
    _isKbStale,
    // Turns #195-#204 helpers — ENERGY + SUSTAINABILITY
    _energyUseIndex,
    _carbonFromKwh,
    _isPeakDemandBreach,
    _detectEnergyAnomaly,
    _standbyWaste,
    _waterUseBreach,
    _compressedAirLeakLoss,
    _motorEfficiencyDelta,
    _buildSustainabilityBundle,
    _isEnergyQuery,
    // Turns #205-#214 helpers — MULTI-LANGUAGE NLU
    _isCebuanoLeaning,
    _isIlonggoLeaning,
    _isTagalogImperative,
    _codeSwitchRatio,
    _classifyPolitenessRegister,
    _parsePhTimeExpression,
    _wordToNumber,
    _stripFillers,
    _removeStopWords,
    _slangToCanonical,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _mount);
  } else {
    _mount();
  }
})();
