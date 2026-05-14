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
      return (raw === 'rosa' || raw === 'james') ? raw : 'james';
    } catch (_) { return 'james'; }
  }

  function isTtsOn() {
    try {
      return localStorage.getItem(TTS_STORAGE_KEY) !== 'off';
    } catch (_) { return true; }
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
    if (_audio) { try { _audio.pause(); } catch (_) {} }
    if (window.speechSynthesis) {
      try { window.speechSynthesis.cancel(); } catch (_) {}
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
      if (_audio) { try { _audio.pause(); } catch (_) {} }
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
      if (_audio) { try { _audio.pause(); } catch (_) {} }
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

  // Persona-gender map for the browser-TTS fallback path. James (male)
  // and Rosa (female) sound identical via the system default voice
  // unless we bias the choice. We pick the first installed voice whose
  // name OR locale tag matches the gender heuristic.
  const PERSONA_GENDER = { james: 'male', rosa: 'female' };
  const MALE_HINTS   = /(male|man|guy|david|mark|alex|james|angelo|paolo|daniel)/i;
  const FEMALE_HINTS = /(female|woman|girl|samantha|victoria|sara|rosa|maria|isabella|tessa)/i;

  function pickBrowserVoice(persona) {
    if (!window.speechSynthesis) return null;
    const voices = window.speechSynthesis.getVoices() || [];
    if (!voices.length) return null;
    const wantMale = PERSONA_GENDER[persona] === 'male';
    const matchGender = (v) => wantMale
      ? (MALE_HINTS.test(v.name)   && !FEMALE_HINTS.test(v.name))
      : (FEMALE_HINTS.test(v.name) && !MALE_HINTS.test(v.name));
    // Prefer en-PH voices first, then en-* voices, then any.
    const phMatches = voices.filter(v => /en-PH/i.test(v.lang));
    const enMatches = voices.filter(v => /^en[-_]/i.test(v.lang));
    return phMatches.find(matchGender) ||
           enMatches.find(matchGender) ||
           voices.find(matchGender) ||
           phMatches[0] || enMatches[0] || voices[0];
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
      u.rate  = 1.0;
      u.pitch = 1.0;
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

    // Local dev mode: if WH_TTS_EDGE_URL is set, try Edge-TTS first (better quality).
    if (window.WH_TTS_EDGE_URL && await speakEdge(text, persona)) {
      return true;
    }

    // Production mode: browser SpeechSynthesis with gender bias.
    // Always available, free, no external keys required.
    speakBrowser(text, persona);
    return false;
  }

  // Expose globally so any inline script can use it.
  window.speakPersona     = speakPersona;
  window.stopPersonaSpeak = stop;
  window.getPersona       = getPersona;
})();
