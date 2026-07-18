// ─────────────────────────────────────────────
// wh-tts.js — Shared persona-aware TTS helper
// ─────────────────────────────────────────────
// One source of truth for "play this narration in the worker's persona
// voice." Every page that consumes a narrated-specialist response (visual
// defect draft, voice action route, analytics narration, etc.) calls
// window.speakPersona(text) to play the audio.
//
// Production path: Browser SpeechSynthesis (free, no keys).
// Local dev path (optional): Edge-TTS via python-api if WH_TTS_EDGE_URL is set
// (set it to http://localhost:8000 when running uvicorn locally for better
// quality TTS while iterating on companion behavior).
//
// See: WORKHIVE_PERSONA_CONTRACT.md, supabase/functions/tts-speak/
(function () {
  'use strict';

  const PERSONA_STORAGE_KEY = 'wh_voice_journal_persona';
  const TTS_STORAGE_KEY     = 'wh_voice_journal_tts';
  const TTS_URL_STORAGE_KEY = 'wh_tts_url';   // V7 Sovereignty toggle: a plant's local Piper server URL

  // V7 (NATIVE_AI_ROADMAP.md #6): restore a persisted SOVEREIGN-voice URL on load so the on-device
  // branded Piper voice (WH_TTS_URL -> speakPiper) stays enabled across page loads once a worker/plant
  // turns it on. Page config may also set window.WH_TTS_URL directly (deployment); this only fills it
  // from localStorage when it is not already set, so a deployment default always wins. Additive + safe.
  try {
    if (typeof window !== 'undefined' && !window.WH_TTS_URL) {
      const _saved = localStorage.getItem(TTS_URL_STORAGE_KEY);
      if (_saved) window.WH_TTS_URL = _saved;
    }
  } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }

  // Toggle the sovereign local voice: pass a Piper server URL to enable (persisted), or a falsy value
  // to fall back to the cloud/browser voice. Returns the new enabled state.
  function setSovereignVoice(url) {
    try {
      if (url) { localStorage.setItem(TTS_URL_STORAGE_KEY, String(url)); window.WH_TTS_URL = String(url); }
      else { localStorage.removeItem(TTS_URL_STORAGE_KEY); try { delete window.WH_TTS_URL; } catch (_) { window.WH_TTS_URL = undefined; } }
    } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
    return !!url;
  }
  function isSovereignVoiceOn() {
    try { return !!(window.WH_TTS_URL || localStorage.getItem(TTS_URL_STORAGE_KEY)); } catch (_) { return false; }
  }

  // Edge-TTS via python-api (optional, local dev only).
  // Set window.WH_TTS_EDGE_URL = 'http://localhost:8000' when running
  // uvicorn locally to get higher-quality TTS during iteration. If not set
  // or if Edge-TTS is offline, falls back to browser SpeechSynthesis.
  // Production uses browser TTS only (no external keys needed).
  function getEdgeTtsBase() {
    // Only use Edge-TTS if explicitly configured (local dev mode).
    // In production, WH_TTS_EDGE_URL is undefined and we skip to browser.
    const explicit = window.WH_TTS_EDGE_URL;
    if (!explicit) return null;
    return explicit.replace(/\/+$/, '');
  }

  // Reused audio element so a new play cancels the previous, mirroring
  // window.speechSynthesis.cancel() semantics. One file plays at a time.
  let _audio = null;

  function getPersona() {
    try {
      const raw = localStorage.getItem(PERSONA_STORAGE_KEY);
      // Legacy james/rosa values silently map to the new keys for
      // workers whose localStorage predates the 2026-05-20 rename.
      if (raw === 'hezekiah' || raw === 'zaniah') return raw;
      if (raw === 'james') return 'hezekiah';
      if (raw === 'rosa')  return 'zaniah';
      return 'zaniah';
    } catch (_) { return 'zaniah'; }
  }

  function isTtsOn() {
    try {
      return localStorage.getItem(TTS_STORAGE_KEY) === 'on';  // OFF by default
    } catch (_) { return false; }
  }

  function getEnv() {
    // Pages declare SUPABASE_URL and SUPABASE_KEY as inline consts. We
    // grab them off the global scope; failsafe to the production endpoint
    // if the page didn't declare them.
    const url = (typeof SUPABASE_URL !== 'undefined' && SUPABASE_URL)
      || (window.SUPABASE_URL)
      || 'https://hzyvnjtisfgbksicrouu.supabase.co';
    const key = (typeof SUPABASE_KEY !== 'undefined' && SUPABASE_KEY)
      || (window.SUPABASE_KEY)
      || '';
    return { url, key };
  }

  function stop() {
    if (_audio) { try { _audio.pause(); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ } }
    if (window.speechSynthesis) {
      try { window.speechSynthesis.cancel(); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ }
    }
  }

  // Optional local dev path: Edge-TTS via python-api (only if WH_TTS_EDGE_URL is set).
  // Returns true on success, false if not configured or on any failure.
  async function speakEdge(text, persona) {
    const base = getEdgeTtsBase();
    if (!base) return false;  // Not in dev mode, skip to browser
    try {
      const fetcher = (typeof window.fetchWithTimeout === 'function')
        ? window.fetchWithTimeout
        : (u, o) => fetch(u, o);
      const resp = await fetcher(base + '/tts/speak', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: String(text), persona }),
      }, 15000);
      if (!resp || !resp.ok) return false;
      const data = await resp.json();
      if (!data || !data.url) return false;
      const audioUrl = base + data.url;
      if (_audio) { try { _audio.pause(); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ } }
      _audio = new Audio(audioUrl);
      _audio.play().catch(err => {
        // AbortError is expected when a new narration interrupts an old
        // one mid-load (pause() rejects the pending play() promise).
        // Silently ignore — the new audio will play on its own promise.
        if (err && err.name === 'AbortError') return;
        console.warn('wh-tts edge play failed:', err);
      });
      return true;
    } catch (err) {
      console.warn('wh-tts edge fetch failed:', err);
      return false;
    }
  }

  // Sovereign local neural TTS (Piper) path (NATIVE_AI_ROADMAP.md #6, V-axis V2 / the "download the
  // voice" gap). When a plant sets WH_TTS_URL to its own Piper server, the companion speaks in ONE
  // branded, consistent, OFFLINE Hezekiah/Zaniah voice and the audio never leaves the plant, instead
  // of the device OS voice (speechSynthesis). Env-gated + additive exactly like WH_ASR_URL /
  // BGE_EMBED_URL: unset in production today, so this returns false and the existing chain runs
  // UNCHANGED. Returns true on success, false when unset or on any failure (then browser TTS runs).
  function getPiperTtsBase() {
    const u = (typeof window !== 'undefined') ? window.WH_TTS_URL : null;
    return u ? String(u).replace(/\/+$/, '') : null;
  }
  async function speakPiper(text, persona) {
    const base = getPiperTtsBase();
    if (!base) return false;   // sovereignty mode off -> skip to the existing chain (prod default)
    try {
      const fetcher = (typeof window.fetchWithTimeout === 'function')
        ? window.fetchWithTimeout
        : (u, o) => fetch(u, o);
      const resp = await fetcher(base + '/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: String(text), persona }),
      }, 15000);
      if (!resp || !resp.ok) return false;
      // Piper returns raw audio bytes (WAV/OGG). Play via a revocable blob URL.
      const buf = await resp.arrayBuffer();
      if (!buf || !buf.byteLength) return false;
      const type = (resp.headers && resp.headers.get && resp.headers.get('Content-Type')) || 'audio/wav';
      const blobUrl = URL.createObjectURL(new Blob([buf], { type }));
      if (_audio) { try { _audio.pause(); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ } }
      _audio = new Audio(blobUrl);
      _audio.onended = () => { try { URL.revokeObjectURL(blobUrl); } catch (_) { /* empty-catch-allow */ } };
      _audio.play().catch(err => {
        if (err && err.name === 'AbortError') return;
        console.warn('wh-tts piper play failed:', err);
      });
      return true;
    } catch (err) {
      console.warn('wh-tts piper fetch failed:', err);
      return false;
    }
  }

  async function speakAzure(text, persona) {
    const { url, key } = getEnv();
    if (!url || !key) return false;
    try {
      // 10s timeout — cache hit returns < 200ms, cold synth ~ 1-3s.
      // Wrap so a hung edge doesn't strand the worker waiting for audio.
      const fetcher = (typeof window.fetchWithTimeout === 'function')
        ? window.fetchWithTimeout
        : (u, o) => fetch(u, o);
      const resp = await fetcher(url + '/functions/v1/tts-speak', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer ' + key,
          'apikey':        key,
          'Content-Type':  'application/json',
        },
        body: JSON.stringify({ text: String(text), persona }),
      }, 10000);
      if (!resp || !resp.ok) return false;
      const data = await resp.json();
      if (!data || !data.url) return false;
      if (_audio) { try { _audio.pause(); } catch (_) { /* empty-catch-allow: best-effort silent swallow */ } }
      _audio = new Audio(data.url);
      _audio.play().catch(err => {
        if (err && err.name === 'AbortError') return;
        console.warn('wh-tts azure play failed:', err);
      });
      return true;
    } catch (err) {
      console.warn('wh-tts azure fetch failed:', err);
      return false;
    }
  }

  // Persona-gender map for the browser-TTS fallback path. Hezekiah (male)
  // and Zaniah (female) sound identical via the system default voice
  // unless we bias the choice. We pick the first installed voice whose
  // name OR locale tag matches the gender heuristic.
  //
  // MALE_HINTS / FEMALE_HINTS still include 'james' and 'rosa' because
  // those are SYSTEM voice names on Windows + macOS, not WorkHive persona
  // labels — keeping them ensures the browser's installed en-PH voices
  // still match the gender filter.
  const PERSONA_GENDER = { hezekiah: 'male', zaniah: 'female' };
  const MALE_HINTS   = /(male|man|guy|david|mark|alex|james|angelo|paolo|daniel|guy|ravi|brandon)/i;
  const FEMALE_HINTS = /(female|woman|girl|samantha|victoria|sara|rosa|maria|isabella|tessa|zira|hazel|eva|aria|jenny|nova|emma|libby|sonia|natasha|tracy|catherine)/i;

  // Phase 4.22 (turn #21) ACRONYM PRONUNCIATION. The TTS engines tend to
  // mangle maintenance acronyms — "MTBF" comes out as "mmm-tee-bff",
  // "OEE" as "ooo-ee-ee" run together. Pre-process the text to spell
  // out acronyms one letter at a time using spaces (which TTS engines
  // pronounce as letters). The same engines handle "P-203" correctly
  // because the dash + digit forces letter pronunciation, so we only
  // touch the pure-letter acronyms.
  const _ACRONYMS_TO_SPELL = [
    'MTBF', 'MTTR', 'MTBR', 'OEE', 'OEE%', 'KPI', 'KPIs',
    'PM', 'PMs', 'RPN', 'RCM', 'FMEA', 'PPE', 'SOP', 'SOPs',
    'LOTO', 'OPC-UA', 'MQTT', 'CMMS', 'ERP', 'SAP', 'HVAC',
    'RPM', 'TPM', 'SMRP', 'IR-gun', 'IR gun',
  ];
  function _spellOutAcronyms(text) {
    if (!text) return text;
    let out = String(text);
    _ACRONYMS_TO_SPELL.forEach(acr => {
      // Match the acronym only when surrounded by word boundaries to
      // avoid clobbering substrings (e.g. "PMS" inside "PMS-101").
      const re = new RegExp('\\b' + acr.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\$&') + '\\b', 'g');
      // Insert thin spaces between letters so TTS reads them as letters.
      // Keep hyphens and digits in place ("IR-gun" → "I R - gun").
      const spelled = acr.replace(/([A-Za-z])(?=[A-Za-z])/g, '$1 ');
      out = out.replace(re, spelled);
    });
    return out;
  }

  // Persona-name pronunciation fix (Ian-confirmed 2026-07-12): every TTS engine (Piper, edge-tts,
  // browser speechSynthesis) mis-says the uncommon proper nouns. Respell them phonetically so the
  // companion says its OWN name right. Applied to the SPOKEN text only; the on-screen text is
  // untouched. Hezekiah -> "Hezehkeeyah" (he-ze-kee-yah); Zaniah -> "Zah nah yah" (zah-nah-yah).
  function _respellPersonaNames(text) {
    if (!text) return text;
    return String(text)
      .replace(/\bHezekiah\b/gi, 'Hezehkeeyah')
      .replace(/\bZaniah\b/gi, 'Zah nah yah');
  }

  // Pre-load voices on page load (browsers populate this async)
  let _voicesCache = null;
  function _loadVoices() {
    if (!window.speechSynthesis) return [];
    const v = window.speechSynthesis.getVoices() || [];
    if (v.length) _voicesCache = v;
    return v;
  }
  if (window.speechSynthesis) {
    _loadVoices();
    if (window.speechSynthesis.onvoiceschanged !== undefined) {
      window.speechSynthesis.addEventListener('voiceschanged', _loadVoices);
    }
  }

  // Neural/Online voices sound DRAMATICALLY better than default voices.
  // Chrome's "Google" voices and Edge's "Natural"/"Online" voices use neural TTS.
  const NEURAL_HINTS = /(natural|online|google|neural|premium|enhanced)/i;

  function pickBrowserVoice(persona) {
    if (!window.speechSynthesis) return null;
    const voices = _loadVoices().length ? _loadVoices() : (_voicesCache || []);
    if (!voices.length) return null;
    const wantMale = PERSONA_GENDER[persona] === 'male';
    const matchGender = (v) => wantMale
      ? (MALE_HINTS.test(v.name)   && !FEMALE_HINTS.test(v.name))
      : (FEMALE_HINTS.test(v.name) && !MALE_HINTS.test(v.name));
    const isNeural = (v) => NEURAL_HINTS.test(v.name);
    // Strong NEGATIVE match — explicitly avoid wrong-gender voices
    const avoidWrongGender = (v) => wantMale
      ? !FEMALE_HINTS.test(v.name)
      : !MALE_HINTS.test(v.name);
    // Prefer en-PH voices first, then en-* voices, then any.
    const phMatches = voices.filter(v => /en-PH/i.test(v.lang));
    const enMatches = voices.filter(v => /^en[-_]/i.test(v.lang));
    // PRIORITY ORDER:
    // 1. Neural en-* voice matching gender (e.g., "Microsoft Aria Online (Natural)")
    // 2. Any en-PH voice matching gender (warmer accent for PH workers)
    // 3. Any en-* voice matching gender
    // 4. Any voice matching gender
    // 5. Any voice NOT matching wrong gender (better than wrong-gender default)
    const picked = enMatches.find(v => matchGender(v) && isNeural(v)) ||
           phMatches.find(matchGender) ||
           enMatches.find(matchGender) ||
           voices.find(matchGender) ||
           enMatches.find(avoidWrongGender) ||
           voices.find(avoidWrongGender) ||
           phMatches[0] || enMatches[0] || voices[0];
    if (picked) {
      console.log('[wh-tts] persona=' + persona + ' picked voice:', picked.name, picked.lang, isNeural(picked) ? '(NEURAL)' : '(default)'); // console-log-allow: TTS voice-pick diagnostic (one per persona switch)
    }
    return picked;
  }

  function speakBrowser(text, persona) {
    if (!window.speechSynthesis) return;
    try {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(String(text));
      u.lang  = 'en-PH';
      const v = pickBrowserVoice(persona);
      if (v) {
        u.voice = v;
        u.lang  = v.lang || u.lang;
      }
      u.rate  = 0.85;  // Slower = more natural (1.0 = robotic)
      u.pitch = 0.95;  // Slightly lower pitch = warmer tone
      window.speechSynthesis.speak(u);
    } catch (e) {
      console.warn('wh-tts browser speak failed:', e);
    }
  }

  /**
   * Play `text` in the worker's persona voice.
   * Production: browser SpeechSynthesis with gender-biased voice selection.
   * Local dev: optional Edge-TTS via python-api if WH_TTS_EDGE_URL is set.
   *
   * Respects the global TTS toggle (wh_voice_journal_tts). If TTS is
   * off, returns false immediately without playing anything.
   */
  async function speakPersona(text, opts) {
    if (!text || !isTtsOn()) return false;
    const persona = (opts && opts.persona) || getPersona();

    // Phase 4.22 (turn #21) ACRONYM PRONUNCIATION — spell out MTBF / OEE /
    // PM / RPN / etc. so TTS reads them as letters. Asset tags like
    // "P-203" already pronounce correctly because the digit+hyphen
    // pattern forces letter pronunciation in every TTS engine we use.
    const spoken = _respellPersonaNames(_spellOutAcronyms(text));

    // Sovereignty path (NATIVE_AI_ROADMAP.md #6, V2): a plant-local Piper server (WH_TTS_URL) FIRST
    // so the branded voice is offline and the audio never leaves the plant. Env-gated + additive:
    // unset in production today, so this no-ops straight to the existing chain below (prod unchanged).
    if (window.WH_TTS_URL && await speakPiper(spoken, persona)) {
      return true;
    }

    // Local dev mode: if WH_TTS_EDGE_URL is set, try Edge-TTS first (better quality).
    if (window.WH_TTS_EDGE_URL && await speakEdge(spoken, persona)) {
      return true;
    }

    // Production mode: browser SpeechSynthesis with gender bias.
    // Always available, free, no external keys required.
    speakBrowser(spoken, persona);
    return false;
  }

  function toggleTts() {
    try {
      const current = localStorage.getItem(TTS_STORAGE_KEY);
      const newValue = current === 'on' ? 'off' : 'on';
      localStorage.setItem(TTS_STORAGE_KEY, newValue);
      return newValue === 'on';
    } catch (_) {
      return false;
    }
  }

  // Expose globally so any inline script can use it.
  window.speakPersona     = speakPersona;
  window.stopPersonaSpeak = stop;
  window.getPersona       = getPersona;
  // Phase 4.21 (turn #17) AUDIO INTERRUPT — voice-handler's mic-tap needs
  // a single object handle (rather than relying on the legacy stopPersonaSpeak
  // global being present). Expose WHTts with stop() + getPersona() so
  // _startRecording can call window.WHTts.stop() before starting a fresh
  // recording, cancelling any in-flight audio.
  window.WHTts = Object.freeze({
    stop: stop,
    getPersona: getPersona,
    _spellOutAcronyms: _spellOutAcronyms,
  });
  window.toggleTts        = toggleTts;
  window.isTtsOn          = isTtsOn;
  window.setSovereignVoice   = setSovereignVoice;   // V7: enable/disable the on-device Piper voice
  window.isSovereignVoiceOn  = isSovereignVoiceOn;
})();
