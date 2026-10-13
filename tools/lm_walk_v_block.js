// lm_walk_v_block.js - the LM-V (Voice & vision) instrument, in three parts to SPLICE into tools/lm_walk.body.js.
// Not loadable on its own (part A awaits at the walker's top level, part B inside its per-viewport loop, part C inside
// that loop's try). Where each part goes - anchor lines are quoted from lm_walk.body.js as it stood on 2026-10-07:
//
//   PART A (top level)   insert AFTER the line that ends the BADRE map:
//                          "    scriptError: /\b(TypeError|ReferenceError|SyntaxError)\b|is not a function|Cannot read propert/g };"
//   PART B (per context) insert BEFORE the line:
//                          "    ctx.on('request', (r) => { try { const h = r.headers(); if (!apikey && h.apikey ..."
//                        i.e. after the walker's own ctx.route('**/functions/v1/**') - B's routes are registered later, so
//                        Playwright runs them FIRST; whatever they do not own goes on with route.fallback().
//   PART C (the reading) insert BEFORE the line:
//                          "      step.captured = captured.slice(0, 12);"
//                        i.e. after the closing brace of the `if (P.sublayer === 'S') { ... }` block.
//
// Walker variables used, nothing else: mcpPage, SEED, P, notes, problems (A); ctx, vp, captured, heldBodies,
// blockWrites (B); page, ctx, vp, st, step, problems, notes, captured, heldBodies (C). Every name this file adds starts
// with V_ or v (vState, vMk, vStub ...) and none collides with the walker's (it has `vp`; this file never declares it).
// The fixtures are tools/fixtures/lm_v/*.png (python tools/fixtures/lm_v/make_fixtures.py), fetched from the seeder.
// The per-page map, stub shapes, save controls, banker gates and receipt wording: tools/lm_v_instrument.md.

  // ==== LM-V PART A (top level) BEGIN ====
  // SUB-LAYER V - "I spoke and the entry landed; the photo became an entry." The person speaks into a page's own voice
  // control or photographs into its own photo input, at both viewports, with NO model call:
  //   - the microphone is a SYNTHETIC MediaStream (an AudioContext oscillator into a MediaStreamDestination) handed out
  //     by a replaced navigator.mediaDevices.getUserMedia, so MediaRecorder flows record in a headless browser with no
  //     permission prompt; the Web Speech API (logbook's Speak to Fill, report-sender's desktop path) is a scripted
  //     SpeechRecognition that "hears" the sentence the walk says;
  //   - every voice / vision function answers 200 with a stub shaped like what its index.ts really returns, so what the
  //     page shows is the page's own handling of a realistic answer;
  //   - every table write, mutating RPC and storage upload is HELD and recorded with the phase it happened in.
  // Then: did what was heard / seen reach the form or the preview; was the AI's draft written before the person saved;
  // after the page's own save, does the write that carries the draft also carry the platform's mark of machine
  // authorship; and on a FAILURE pass (the same functions answer 503) does the page say so and keep what the person had
  // already entered.
  const V_ON = P.sublayer === 'V';
  // the flows each page offers (read from the page sources, 2026-10-07). EVERY V page also carries the companion's mic
  // (#wh-ai-mic -> WHVoice.open() in voice-handler.js, which nav-hub.js lazy-loads on every page)
  const V_PAGE_FLOWS = { 'logbook.html': ['logbook-speak', 'logbook-photo', 'logbook-nameplate', 'companion'],
    'report-sender.html': ['report-voice', 'companion'], 'resume.html': ['resume-photo', 'companion'] };
  const vFlowsFor = (pg) => V_PAGE_FLOWS[pg] || ['companion'];
  // the intent each page registers a voice handler for (WHVoice.register in the page); every other page answers a
  // spoken QUESTION through the companion's conversational path
  const V_COMPANION_KIND = { 'logbook.html': 'logbook.create', 'asset-hub.html': 'asset.lookup', 'pm-scheduler.html': 'pm.complete' };
  // every payload, for the machine the person's own record is about (a solo owner's records say 'Own unit',
  // tools/seed_solo_personas.py). Shapes read from each function's index.ts, 2026-10-07.
  const vMk = (m) => {
    const say = {
      'logbook-speak': `Inspected the drive belt on ${m}, it is glazed and slipping under load. Re-tensioned it for now, it needs a new belt at the next PM.`,
      'report-voice': `Failure digest and shift handover for the last seven days, focus on ${m}.`,
      companion: { 'logbook.create': `Log an inspection on ${m}: drive belt glazed and slipping, re-tensioned, replace it at the next PM.`,
        'asset.lookup': `Show me ${m}.`, 'pm.complete': `PM done on ${m}, monthly greasing, all readings normal.`,
        'query.ask': `What was the last repair done on ${m}?` },
    };
    // voice-logbook-entry: { ok: true, entry } - the sanitised result object (index.ts, the `result` it returns)
    const entry = { machine: m, problem: `Drive belt on ${m} glazed and slipping under load`, root_cause: 'Wear',
      action: 'Re-tensioned the drive belt; fit a new belt at the next PM', maintenance_type: 'Inspection', status: 'Open',
      downtime_hours: 0, loto_detected: false, loto_note: null, parts_mentioned: ['drive belt'], is_breakdown: false,
      urgency: 'normal', supervisor_alert: null };
    // visual-defect-capture: { draft, matched_asset, fault_knowledge_id, remaining } - draft after coerceDraft. The photo
    // carries no asset tag (defect_belt.png reads "DRIVE 3", not a tag), so asset_tag_extracted is null, as the prompt
    // demands, and the person picks the machine themselves
    const draft = { failure_mode: 'V-belt glazed and cracked, slipping', category: 'mechanical', severity: 'medium',
      root_cause: 'Wear', action: 'Replace the V-belt, then check pulley alignment and tension',
      problem: `Glazed, cracked V-belt slipping on ${m}`,
      knowledge: 'A glazed belt has been slipping for weeks: check tension and pulley alignment at every PM.',
      asset_tag_extracted: null, confidence: 0.82,
      narration: `I can see a glazed, cracked V-belt on ${m}. I filled in the problem and the action for you to check.` };
    // voice-report-intent: the parsed JSON itself (flat). recipient_hint null: the page then matches nobody by name
    const report = { report_types: ['failure_digest', 'shift_handover'], recipient_hint: null, period_days: 7,
      machine_filter: m, urgency: 'normal', notes: `Failure digest and shift handover for the last 7 days, focus on ${m}` };
    const params = { 'logbook.create': { machine: m, problem: entry.problem, action: entry.action, maintenance_type: 'Inspection',
      category: 'Mechanical', root_cause: 'Wear', status: 'Open', downtime_hours: 0, parts_used: [] },
      'asset.lookup': { machine: m, question: `Show me ${m}` },
      'pm.complete': { machine: m, task_summary: 'Monthly greasing done, all readings normal' },
      'query.ask': { question: say.companion['query.ask'] } };
    const narration = { 'logbook.create': `Got it: an inspection on ${m}, drive belt glazed and slipping. Check the entry and confirm.`,
      'asset.lookup': `Opening ${m} for you.`, 'pm.complete': `PM on ${m}: monthly greasing done. Confirm to record it.`,
      'query.ask': 'Let me look that up.' };
    return { m, say, entry, draft, report, params, narration,
      // equipment-label-ocr: { parsed, matched_asset, ocr_chars } - what nameplate.png says
      ocr: { parsed: { manufacturer: 'WEG', model: 'W22 IE3 132M-4', serial_no: '1028475531', rated_power: '7.5 kW', voltage: '400 V' },
        matched_asset: null, ocr_chars: 214 },
      // resume-extract: { fields: <JSON Resume partial>, remaining } (flat) - what resume_page_1.png says
      resume: { fields: { basics: { label: 'Maintenance Technician', summary: 'Five years on conveyors, pumps and fleet vehicles.',
        location: { city: 'Valenzuela', region: 'Metro Manila' } },
        work: [{ name: 'Northline Packaging Corp.', position: 'Maintenance Technician', startDate: '2019-06', endDate: '2024-08',
          highlights: ['Cut conveyor downtime 30% with a weekly belt-tension round'] }],
        education: [{ institution: 'Technological University of the Philippines', area: 'Mechanical Engineering', studyType: 'BS' }],
        skills: [{ name: 'Vibration analysis', level: '' }, { name: 'LOTO', level: '' }, { name: 'PM planning', level: '' }],
        certificates: [{ name: 'TESDA NC II Electrical Installation and Maintenance', issuer: 'TESDA', date: '2018' }],
        projects: [], awards: [] }, remaining: 19 },
      // the conversational reply (ai-gateway, agent 'voice-journal', through voice-handler's _converseInline)
      converse: `The last entry on ${m} is an inspection: the drive belt was glazed and slipping, it was re-tensioned, and a new belt is planned for the next PM.`,
      // text only the AI's draft carries: a held write that contains one of these carries the draft (no machine name,
      // so JSON escaping cannot hide it)
      needles: { 'logbook-speak': ['glazed and slipping under load', 'fit a new belt at the next PM'],
        'logbook-photo': ['Glazed, cracked V-belt slipping', 'check pulley alignment and tension'],
        'logbook-nameplate': ['1028475531', 'W22 IE3 132M-4'], 'resume-photo': ['Northline Packaging', 'belt-tension round'],
        'report-voice': [], companion: [] } };
  };
  const V_STUB_FNS = new Set(['voice-transcribe', 'voice-logbook-entry', 'voice-report-intent', 'visual-defect-capture',
    'equipment-label-ocr', 'resume-extract', 'tts-speak', 'ai-gateway', 'voice-action-router']);
  // what the voice overlay can reach that is not this lens: answered 503, so no live model runs during a V walk
  const V_QUIET_FNS = new Set(['agentic-rag-loop', 'voice-semantic-rag', 'voice-embeddings', 'voice-model-call',
    'voice-journal-agent', 'platform-scraper']);
  // each function's own words for an exhausted provider chain (index.ts), 503 for all
  const V_FAIL_MSG = { 'visual-defect-capture': 'All vision providers are at capacity. Try again in a few minutes.',
    'voice-action-router': 'AI providers all at capacity. Try again shortly.',
    default: 'All AI providers are unavailable right now. Please try again in a few minutes.' };
  // 0.05 s of silence, for tts-speak's { url } (wh-tts.js speakAzure plays data.url) - no V page reaches tts-speak today
  const V_WAV = (() => { try { const n = 400; const le = (v, b) => { let s = ''; for (let i = 0; i < b; i++) s += String.fromCharCode((v >> (8 * i)) & 255); return s; };
    return 'data:audio/wav;base64,' + btoa('RIFF' + le(36 + n, 4) + 'WAVEfmt ' + le(16, 4) + le(1, 2) + le(1, 2) + le(8000, 4) + le(8000, 4)
      + le(1, 2) + le(8, 2) + 'data' + le(n, 4) + String.fromCharCode(128).repeat(n)); } catch (e) { return ''; } })();
  // conversation memory and usage telemetry: recorded, never judged as "the entry"
  const V_MEMORY = /^(analytics_events|ai_feedback|ai_usage[a-z_]*|page_views|usage_events|error_logs|client_errors|web_vitals|feature_usage|voice_journal_entries|companion_handoff|conversation_analytics|avatar_state|wh_voice_presence|tts_quality_log|offline_snapshot_cache|ai_audit_log|ai_reply_feedback|ai_knowledge_gap|ai_quality_escalation|agent_memory|hive_audit_log|audit_log|wh_traces|ai_cost_log|hive_route_calls|rpc\/(store_memory_turn|update_dialog_state|log_[a-z_]+|track_[a-z_]+))$/;
  // a READ rpc is never held, whatever word it contains (the walker's LM332 lesson); a write-shaped one always is
  const V_READ_RPC = /^(get|list|fetch|search|semantic_search|match|count|is|has|can|read|find|my|v|check|resolve|lookup|rerank)_/i;
  const V_MUT_RPC = /approve|reject|publish|create|insert|update|delete|^set_|save|submit|post|claim|assign|upsert|write|store|record|^log_|track|^add_|remove|mark|toggle|increment|bump|touch|enqueue|dismiss|ack/i;
  const V_APPROVER = /"(approved_by|decided_by|reviewed_by|published_by|updated_by|actor|auth_uid|worker_name|created_by|owner_auth_uid|seller_auth_uid)"\s*:/i;
  // a mark of machine authorship in any body (the `source` VALUE must say ai_*: 'manual' is the person's own)
  const V_AI_MARK = /"source"\s*:\s*"ai_|"(ai_model|model_version|generated_by|ai_generated|_ai_generated[a-z_]*|_ai_intent|_ai_prefilled_fields|ai_drafted|created_by_ai|is_ai)"\s*:|"ai_assisted_fields"\s*:\s*\["|"_source"\s*:\s*"Uploaded|"_src"\s*:\s*\{/i;
  // WHERE THE PLATFORM DEFINES THE MARK, per table (schema read 2026-10-07). null = the table has no such column, so a
  // draft saved there reads as the person's own words - recorded, and a problem only when V_PROV_STRICT is set.
  //   fault_knowledge  CHECK (source in manual|ai_visual_capture|cmms_import) AND (source ~~ 'ai\_%') = (ai_model IS NOT NULL)
  //   resume_*         every item read from a file carries _source 'Uploaded: <file>' (basics: _src) - resume.html's own mark
  //   marketplace_listings  ai_assisted_fields names each drafted field
  const V_PROV = { logbook: null, asset_nodes: null, fault_knowledge: /"source"\s*:\s*"ai_/,
    resume_documents: /"_source"\s*:\s*"Uploaded|"_src"\s*:\s*\{/, resume_versions: /"_source"\s*:\s*"Uploaded|"_src"\s*:\s*\{/,
    marketplace_listings: /"ai_assisted_fields"\s*:\s*\["/ };
  const V_PROV_STRICT = false;
  const vProv = (tbl, b) => (Object.prototype.hasOwnProperty.call(V_PROV, tbl)
    ? (V_PROV[tbl] ? (V_PROV[tbl].test(b) ? 'marked' : 'UNMARKED') : 'none-defined') : (V_AI_MARK.test(b) ? 'marked' : 'unknown'));
  // what a person can act on when the AI fails, the raw text that is not that, and the designed refusals
  const V_FAIL_RX = /try again|could ?n.?t|could not|cannot|unavailable|did ?n.?t|not run|went wrong|failed|unchanged|untouched|not (be )?(read|analy[sz]ed|filled|processed)|too long|not available|busy|at capacity|limit|nothing was saved|by hand|manually|type (it |fields )?(instead|manually)|no draft|denied/i;
  const V_RAW_RX = /non-2xx|Edge Function|status code|TypeError|ReferenceError|is not a function|Cannot read propert|\bHTTP \d{3}\b/i;
  const V_NEEDS_HIVE_RX = /join a hive|needs a hive|join or create one/i;
  const V_LOCK_RX = /voice actions are locked/i;
  // what the page-side catcher keeps (toasts live ~4 s; the readings come later)
  const V_NOTICE_RX = new RegExp(V_FAIL_RX.source + '|' + V_RAW_RX.source + '|filled|saved|added|pre-?filled|review|analy[sz]ed|scanned|logged|transcrib|listening|locked|join a hive|needs a hive|parsing|confirm|please (select|pick|describe)|required|already logged|submit again', 'i');
  const vHiveOf = (o) => (o && typeof o === 'object')
    ? ((typeof o.hive_id === 'string' || o.hive_id === null) ? o.hive_id
      : (o.context && typeof o.context === 'object' && typeof o.context.hive_id === 'string' ? o.context.hive_id : undefined)) : undefined;
  // the stub answer for one call, from the per-viewport state (what the person said, which intent this page takes)
  const vStub = (vs, fn, body, agent) => {
    const S = vs.S;
    if (fn === 'voice-transcribe') return { text: vs.say, lang: 'en', avg_logprob: -0.18, low_confidence: false };
    if (fn === 'voice-logbook-entry') return { ok: true, entry: S.entry };
    if (fn === 'voice-report-intent') return S.report;
    if (fn === 'visual-defect-capture') return { draft: S.draft, matched_asset: null, fault_knowledge_id: null, remaining: 17 };
    if (fn === 'equipment-label-ocr') return S.ocr;
    if (fn === 'resume-extract') return S.resume;
    if (fn === 'tts-speak') return { url: V_WAV };
    // voice-action-router: { transcript, intents[], mentioned_assets, narration, remaining } (no asset_resolution: the
    // stub does not invent an asset id; the page shows the card without an asset pill)
    const rr = { transcript: vs.say, intents: [{ kind: vs.kind, confidence: 0.91, params: S.params[vs.kind] || {} }],
      mentioned_assets: vs.kind === 'query.ask' ? [] : [S.m], narration: S.narration[vs.kind] || '', remaining: 18 };
    if (fn === 'voice-action-router') return rr;
    // ai-gateway: the router answers THROUGH it (agent 'voice-action', a STRUCTURED_PASSTHROUGH agent -> the standard
    // envelope { ok, data: { answer, agent, route_result } }); any other agent gets a plain answer in the same envelope
    if (agent === 'voice-action') return { ok: true, data: { answer: rr.narration, agent, route_result: rr,
      usage: { latency_ms: 840, served_from: 'lm-v-stub' } }, trace_id: 'lm-v-stub' };
    return { ok: true, data: { answer: S.converse, agent: agent || 'voice-journal', usage: { latency_ms: 910, served_from: 'lm-v-stub' } }, trace_id: 'lm-v-stub' };
  };
  // the page-side half, installed into every page of a V context before the page's own scripts run
  const V_INIT = (cfg) => {
    if (window.__lmV) return;
    const L = window.__lmV = { gum: [], recorder: [], sr: [], spoken: [], notices: [], errors: [] };
    const now = () => Date.now();
    const cap = (a, n) => { if (a.length > n) a.splice(0, a.length - n); };
    // 1. THE MICROPHONE: a synthetic stream - a sawtooth "voice" for cfg.speakSec seconds, then silence (report-sender's
    //    recorder stops itself after 2 s of silence, as it does for a person who stops talking)
    try {
      const md = navigator.mediaDevices;
      if (md) {
        const gum = async (c) => {
          const rec = { t: now(), c: JSON.stringify(c || {}).slice(0, 80), ctx: null };
          L.gum.push(rec); cap(L.gum, 40);
          const AC = window.AudioContext || window.webkitAudioContext;
          const ac = new AC();
          // resume() waits for a gesture when autoplay is blocked: it must never hold the page's own mic call
          await Promise.race([ac.resume().catch(() => {}), new Promise((r) => setTimeout(r, 300))]);
          rec.ctx = ac.state;
          const osc = ac.createOscillator();
          osc.type = 'sawtooth';
          osc.frequency.value = 165;
          const g = ac.createGain();
          g.gain.setValueAtTime(0.3, ac.currentTime);
          g.gain.setValueAtTime(0, ac.currentTime + (cfg.speakSec || 1.8));
          const dest = ac.createMediaStreamDestination();
          osc.connect(g);
          g.connect(dest);
          osc.start();
          dest.stream.getAudioTracks().forEach((t) => {
            const st = t.stop.bind(t);
            t.stop = () => { try { osc.stop(); ac.close(); } catch (e) { void e; } st(); };
          });
          return dest.stream;
        };
        try { md.getUserMedia = gum; } catch (e) { Object.defineProperty(md, 'getUserMedia', { value: gum, configurable: true, writable: true }); }
        const ed = typeof md.enumerateDevices === 'function' ? md.enumerateDevices.bind(md) : null;
        md.enumerateDevices = async () => {
          const real = ed ? await ed().catch(() => []) : [];
          return real.some((d) => d.kind === 'audioinput') ? real
            : real.concat([{ deviceId: 'lm-v-mic', groupId: 'lm-v', kind: 'audioinput', label: 'LM-V synthetic microphone' }]);
        };
      }
      if (navigator.permissions && typeof navigator.permissions.query === 'function') {
        const pq = navigator.permissions.query.bind(navigator.permissions);
        navigator.permissions.query = (d) => ((d && (d.name === 'microphone' || d.name === 'camera'))
          ? Promise.resolve({ name: d.name, state: 'granted', onchange: null, addEventListener() {}, removeEventListener() {} }) : pq(d));
      }
    } catch (e) { L.errors.push({ t: now(), s: 'lm-v mic: ' + String((e && e.message) || e).slice(0, 120) }); }
    // 2. THE RECORDER: counts the audio it really captured. When the synthetic stream gave it none (an AudioContext held
    //    by autoplay policy), it hands the page ONE placeholder chunk so the page's own upload path runs - and records
    //    that it did (transcription is stubbed either way, so the words are the walk's, not the audio's)
    try {
      const RMR = window.MediaRecorder;
      if (RMR) {
        class LmMediaRecorder extends RMR {
          constructor(stream, opts) {
            super(stream, opts);
            const rec = { t: now(), mime: this.mimeType || (opts && opts.mimeType) || '', real: 0, synth: false };
            L.recorder.push(rec); cap(L.recorder, 40);
            this.addEventListener('dataavailable', (e) => { if (e && e.data && e.data.size && !e.__lmv) rec.real += 1; });
            // registered in the constructor, so it runs BEFORE the page's own onstop (set after construction)
            this.addEventListener('stop', () => {
              if (rec.real) return;
              rec.synth = true;
              const ev = new BlobEvent('dataavailable', { data: new Blob([new Uint8Array(2048)], { type: this.mimeType || 'audio/webm' }) });
              ev.__lmv = 1;
              this.dispatchEvent(ev);
            });
          }
        }
        window.MediaRecorder = LmMediaRecorder;
      }
    } catch (e) { L.errors.push({ t: now(), s: 'lm-v recorder: ' + String((e && e.message) || e).slice(0, 120) }); }
    // 3. THE WEB SPEECH API: a recogniser that "hears" window.__lmVTranscript (set by the walk before each press) and
    //    behaves like Chrome's - start, result, end; stop() delivers what was heard; abort() an 'aborted' error.
    //    srMode 'absent' removes the API (the iOS Safari / Firefox path pages fall back from)
    try {
      const mk = (T) => {
        const alt = { transcript: T, confidence: 0.93 };
        const res = [alt]; res.isFinal = true; res.item = (i) => res[i];
        const list = [res]; list.item = (i) => list[i];
        return list;
      };
      class LmSpeechRecognition extends EventTarget {
        constructor() {
          super();
          this.lang = 'en-US'; this.continuous = false; this.interimResults = false; this.maxAlternatives = 1;
          this.grammars = null; this._st = 'idle'; this._done = false; this._tm = [];
        }
        _fire(type, extra) {
          const ev = new Event(type);
          if (extra) Object.assign(ev, extra);
          const h = this['on' + type];
          if (typeof h === 'function') { try { h.call(this, ev); } catch (e) { setTimeout(() => { throw e; }, 0); } }
          this.dispatchEvent(ev);
        }
        _deliver() {
          if (this._done) return;
          this._done = true;
          const T = String(window.__lmVTranscript || cfg.transcript || '');
          L.sr.push({ t: now(), heard: T.slice(0, 160), lang: this.lang }); cap(L.sr, 40);
          this._fire('speechend');
          this._fire('soundend');
          this._fire('result', { resultIndex: 0, results: mk(T), interpretation: null, emma: null });
          this._fire('audioend');
          this._st = 'idle';
          this._fire('end');
        }
        start() {
          if (this._st !== 'idle') throw new DOMException("Failed to execute 'start' on 'SpeechRecognition': recognition has already started.", 'InvalidStateError');
          this._st = 'listening';
          this._done = false;
          this._tm = [setTimeout(() => { ['start', 'audiostart', 'soundstart', 'speechstart'].forEach((x) => this._fire(x)); }, 60),
            setTimeout(() => this._deliver(), cfg.srResultMs || 1600)];
        }
        stop() { if (this._st === 'listening') { this._tm.forEach(clearTimeout); this._deliver(); } }
        abort() {
          if (this._st !== 'listening') return;
          this._tm.forEach(clearTimeout);
          this._done = true;
          this._st = 'idle';
          this._fire('error', { error: 'aborted', message: '' });
          this._fire('end');
        }
      }
      const v = cfg.srMode === 'absent' ? undefined : LmSpeechRecognition;
      ['SpeechRecognition', 'webkitSpeechRecognition'].forEach((k) => {
        try { Object.defineProperty(window, k, { value: v, configurable: true, writable: true }); } catch (e) { void e; }
      });
    } catch (e) { L.errors.push({ t: now(), s: 'lm-v speech: ' + String((e && e.message) || e).slice(0, 120) }); }
    // 4. WHAT THE PERSON HEARS: browser speech is recorded (TTS is off by default on these pages, so usually nothing)
    try {
      const ss = window.speechSynthesis;
      if (ss && typeof ss.speak === 'function') {
        const sp = ss.speak.bind(ss);
        ss.speak = (u) => { L.spoken.push({ t: now(), s: String((u && u.text) || '').slice(0, 200) }); cap(L.spoken, 40); try { sp(u); } catch (e) { void e; } };
      }
    } catch (e) { void e; }
    // 5. WHAT THE PAGE SAYS: every short piece of text the page paints that reads as a status, kept with its time
    try {
      const RX = new RegExp(cfg.noticeRx, 'i');
      const last = new Map();
      const grab = (n) => {
        try {
          const el = n && (n.nodeType === 1 ? n : n.parentElement);
          if (!el || el.childElementCount > 12 || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE|OPTION|SELECT)$/.test(el.tagName)) return;
          const t = (el.textContent || '').replace(/\s+/g, ' ').trim();
          if (!t || t.length > 400 || !RX.test(t)) return;
          const s = t.slice(0, 220);
          const at = now();
          if (at - (last.get(s) || 0) < 1500) return;
          last.set(s, at);
          L.notices.push({ t: at, s }); cap(L.notices, 300);
        } catch (e) { void e; }
      };
      new MutationObserver((ms) => {
        for (const m of ms) {
          if (m.type === 'characterData') grab(m.target);
          else { m.addedNodes.forEach(grab); grab(m.target); }
        }
      }).observe(document, { childList: true, subtree: true, characterData: true });
    } catch (e) { void e; }
    window.addEventListener('error', (e) => { L.errors.push({ t: now(), s: String((e && e.message) || '').slice(0, 160) }); cap(L.errors, 60); });
    window.addEventListener('unhandledrejection', (e) => { const r = e && e.reason; L.errors.push({ t: now(), s: String((r && (r.message || r)) || '').slice(0, 160) }); cap(L.errors, 60); });
  };
  // the photos a person takes (tools/fixtures/lm_v, served by the seeder); APIResponse.body() is already a Buffer
  const V_FIX = {};
  if (V_ON) {
    for (const [k, f] of [['defect', 'defect_belt.png'], ['nameplate', 'nameplate.png'], ['resume', 'resume_page_1.png']]) {
      try {
        const r = await mcpPage.request.get(SEED + '/workhive/tools/fixtures/lm_v/' + f, { timeout: 8000 });
        if (r.ok()) V_FIX[k] = { name: f, mimeType: 'image/png', buffer: await r.body() };
      } catch (e) { void e; }
      if (!V_FIX[k]) notes.push(`LM-V fixture ${f} could not be loaded from the seeder - its photo flow reads "no fixture"`);
    }
  }
  // ==== LM-V PART A END ====

    // ==== LM-V PART B (per context) BEGIN ====
    // V: the page's microphone and speech engine for this viewport, the voice/vision stubs, and the write holds.
    // Registered AFTER the walker's own routes, so these run FIRST; anything they do not own goes on with fallback().
    const vState = { active: false, phase: 'load', kind: 'query.ask', say: '', failFns: null, needles: [], S: null,
      calls: [], embed: [], srMode: 'fake', seq: 0 };
    if (V_ON) {
      blockWrites = true;   // belt and braces: a write this route passes on is still held by the walker's own
      // report-sender takes the Web Speech path where the API exists and MediaRecorder + voice-transcribe where it does
      // not (iOS Safari / Firefox): the phone walks the recorder path, the desktop the speech path, so both are proven
      vState.srMode = (vFlowsFor(P.page).includes('report-voice') && vp.name === 'phone-390') ? 'absent' : 'fake';
      vState.S = vMk(P.ownHive ? String(P.groundSubject || 'PUMP-201') : 'Own unit');
      await ctx.addInitScript(V_INIT, { srMode: vState.srMode, speakSec: 1.8, srResultMs: 1600,
        transcript: vState.S.say['logbook-speak'], noticeRx: V_NOTICE_RX.source });
      // every table write and write-shaped RPC is HELD for the whole walk and recorded with its phase; the answer is the
      // one PostgREST gives, so the page's own success path runs on (rows echoed back with an id when it asked for them)
      await ctx.route('**/rest/v1/**', async (route) => {
        try {
          const r = route.request();
          const m = r.method();
          if (m === 'GET' || m === 'HEAD' || m === 'OPTIONS') return route.fallback();
          const tbl = (r.url().split('/rest/v1/')[1] || '').split('?')[0];
          const isRpc = tbl.startsWith('rpc/');
          const rpcName = tbl.replace(/^rpc\//, '');
          if (isRpc && (V_READ_RPC.test(rpcName) || !V_MUT_RPC.test(rpcName))) return route.fallback();
          const b = r.postData() || '';
          heldBodies.push({ phase: 'v-' + vState.phase, method: m, table: tbl, memory: V_MEMORY.test(tbl),
            carries: vState.needles.some((n) => n && b.includes(n)), prov: vProv(tbl, b), approver: V_APPROVER.test(b), body: b.slice(0, 300) });
          if (isRpc) return route.fulfill({ status: 200, contentType: 'application/json', body: 'null' });
          let echo = '[]';
          try {
            const pb = b ? JSON.parse(b) : null;
            const rows = (Array.isArray(pb) ? pb : (pb && typeof pb === 'object' ? [pb] : []))
              .map((x) => Object.assign({ id: '00000000-0000-4000-8000-' + String(++vState.seq).padStart(12, '0') }, x));
            const h = r.headers();
            if (/vnd\.pgrst\.object/.test(h.accept || '')) echo = JSON.stringify(rows[0] || {});
            else if (/return=representation/.test(h.prefer || '')) echo = JSON.stringify(rows);
          } catch (e) { void e; }
          return route.fulfill({ status: m === 'POST' ? 201 : 200, contentType: 'application/json', body: echo });
        } catch (e) { return route.fallback(); }
      });
      // a photo UPLOADED before the person saves is a write too
      await ctx.route('**/storage/v1/object/**', async (route) => {
        try {
          const r = route.request();
          if (r.method() === 'GET' || r.method() === 'HEAD' || r.method() === 'OPTIONS') return route.fallback();
          const key = (r.url().split('/storage/v1/object/')[1] || '').split('?')[0];
          heldBodies.push({ phase: 'v-' + vState.phase, method: r.method(), table: 'storage/' + key.split('/').slice(0, 2).join('/'),
            memory: false, carries: false, prov: 'unknown', approver: false, body: '(binary upload)' });
          return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ Key: key, Id: 'lm-v-held-upload' }) });
        } catch (e) { return route.fallback(); }
      });
      await ctx.route('**/functions/v1/**', async (route) => {
        try {
          const req = route.request();
          const fn = (req.url().split('/functions/v1/')[1] || '').split(/[?/#]/)[0];
          if (!vState.active || req.method() !== 'POST') return route.fallback();
          const raw = req.postData() || '';
          if (fn === 'embed-entry') {
            // the page's own follow-on after a save: it files the entry's text into fault_knowledge, whose `source` column
            // says who wrote it (default 'manual'). Recorded here; the walker's own stub answers it.
            vState.embed.push({ phase: vState.phase, carries: vState.needles.some((n) => n && raw.includes(n)), marked: V_AI_MARK.test(raw), body: raw.slice(0, 400) });
            return route.fallback();
          }
          const quiet = V_QUIET_FNS.has(fn);
          if (!quiet && !V_STUB_FNS.has(fn)) return route.fallback();
          let body = null;
          try { body = raw && raw.trim()[0] === '{' ? JSON.parse(raw) : null; } catch (e) { body = null; }
          const hv = body ? vHiveOf(body) : (/name="hive_id"\r?\n\r?\n([^\r\n]*)/.exec(raw) || [])[1];
          let bytes = raw.length;
          try { const pb = req.postDataBuffer(); if (pb) bytes = pb.length; } catch (e) { void e; }
          const agent = body && typeof body.agent === 'string' ? body.agent : null;
          const fail = quiet || !!(vState.failFns && vState.failFns.includes(fn));
          const status = fail ? 503 : 200;
          const out = fail ? { error: quiet ? 'stubbed by the LM-V walk: not part of this lens' : (V_FAIL_MSG[fn] || V_FAIL_MSG.default) }
            : vStub(vState, fn, body, agent);
          captured.push({ fn, method: req.method(), hive: hv === undefined ? '(not named)' : hv, injectionIn: [], v: vState.phase,
            ...(agent ? { agent } : {}), ...(fail && !quiet ? { failed: true } : {}), ...(quiet ? { stubbed: 'not part of the V lens' } : {}) });
          vState.calls.push({ fn, agent, phase: vState.phase, status, bytes, hive: hv === undefined ? null : hv,
            heard: body ? (String(body.transcript || (agent === 'voice-action' ? body.message : '') || '').slice(0, 160) || null) : null,
            image: !!(body && ((typeof body.image_data_url === 'string' && body.image_data_url.startsWith('data:image/')) || body.kind === 'image')) });
          return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(out) });
        } catch (e) { return route.fallback(); }
      });
    }
    // ==== LM-V PART B END ====

      // ==== LM-V PART C (the V reading) BEGIN ====
      if (P.sublayer === 'V') {
        // ★VOICE & VISION (LM-V, 2026-10-07): "I spoke and the entry landed; the photo became an entry." Each flow the
        // page offers is walked twice from a fresh load: OK - the person speaks / photographs, the page shows what the AI
        // drafted, the person completes what the page still asks and presses the page's own save; FAIL - the person has
        // already entered something, the same functions answer 503, and the page must say so and keep it.
        const vNorm = (s) => String(s == null ? '' : s).replace(/\s+/g, ' ').trim();
        const vNow = () => page.evaluate(() => Date.now()).catch(() => Date.now());
        const vVis = (sel, loose) => page.evaluate(([s, l]) => {
          const el = document.querySelector(s);
          return !!(el && el.checkVisibility && el.checkVisibility(l ? { visibilityProperty: true } : { opacityProperty: true, visibilityProperty: true }));
        }, [sel, !!loose]).catch(() => false);
        // a press is a real pointer press where one lands; where something covers the control it is a scripted click,
        // and the receipt says which (a scripted click carries no user activation)
        const vClick = async (sel, loose) => {
          const st0 = await page.evaluate(([s, l]) => {
            const el = document.querySelector(s);
            if (!el) return 'absent';
            if (!(el.checkVisibility && el.checkVisibility(l ? { visibilityProperty: true } : { opacityProperty: true, visibilityProperty: true }))) return 'hidden';
            return el.disabled ? 'disabled' : 'ok';
          }, [sel, !!loose]).catch(() => 'absent');
          if (st0 !== 'ok') return st0;
          try { await page.locator(sel).first().click({ timeout: 6000 }); return 'pressed'; } catch (e) {
            const ok = await page.evaluate((s) => { const el = document.querySelector(s); if (!el) return false; el.click(); return true; }, sel).catch(() => false);
            return ok ? 'scripted click (the pointer press did not land: ' + vNorm(String(e.message || e).split('\n')[0]).slice(0, 70) + ')' : 'absent';
          }
        };
        const vPressed = (d) => d === 'pressed' || /^scripted/.test(String(d));
        const vVals = (sels) => page.evaluate((ss) => ss.map((s) => {
          const el = document.querySelector(s);
          if (!el) return null;
          return /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) ? String(el.value || '') : (el.innerText || el.textContent || '');
        }), sels).catch(() => sels.map(() => null));
        const vLog = (t0) => page.evaluate((t) => {
          const L = window.__lmV || {};
          const since = (a) => (a || []).filter((x) => x.t >= t);
          return { notices: since(L.notices).map((x) => x.s), errors: since(L.errors).map((x) => x.s), sr: since(L.sr),
            recorder: since(L.recorder), spoken: since(L.spoken).map((x) => x.s), gum: since(L.gum) };
        }, t0).catch(() => ({ notices: [], errors: [], sr: [], recorder: [], spoken: [], gum: [] }));
        const vLive = () => page.evaluate(() => [...document.querySelectorAll('[aria-live]:not([aria-live="off"]),[role="alert"],[role="status"]')]
          .map((e) => (e.innerText || e.textContent || '').replace(/\s+/g, ' ').trim()).filter(Boolean)).catch(() => []);
        const vChips = () => page.evaluate(() => [...document.querySelectorAll('.chip.selected, .chip[aria-pressed="true"]')]
          .map((c) => c.dataset.id).filter(Boolean)).catch(() => []);
        // the machine of the hive the page OPENED (a person can belong to several, LM111); a solo owner's own unit
        const vGb = (P.groundByHive || {})[st.hive || 'none'];
        const vMach = st.hive ? String((vGb && vGb.subject) || P.groundSubject || 'PUMP-201') : 'Own unit';
        vState.S = vMk(vMach);
        const S = vState.S;
        const vKind = V_COMPANION_KIND[P.page] || 'query.ask';
        const LOGBOOK_SNAP = ['#f-machine', '#f-problem', '#f-action', '#f-maint-type', '#f-category', '#f-root-cause', '#f-knowledge'];
        // the flows, as a person meets them (selectors read from the page sources, 2026-10-07)
        const FLOWS = {
          'logbook-speak': { label: 'Speak to fill', kind: 'voice', fns: ['voice-logbook-entry'], fail: ['voice-logbook-entry'],
            say: S.say['logbook-speak'], press: '#voice-fill-btn', settle: ['#vf-result'],
            expect: [['#f-problem', S.entry.problem], ['#f-action', S.entry.action], ['#f-maint-type', S.entry.maintenance_type],
              ['#f-root-cause', S.entry.root_cause], ['#f-machine', S.m]],
            typed: 'picker', snap: LOGBOOK_SNAP, show: ['#vf-result'], save: 'logbook' },
          'logbook-photo': { label: 'Photo defect capture', kind: 'photo', fns: ['visual-defect-capture'], fail: ['visual-defect-capture'],
            press: '#vdc-capture-btn', input: '#vdc-file-input', fixture: 'defect', then: '#vdc-analyze-btn', settle: ['#vdc-result'],
            expect: [['#f-problem', S.draft.problem], ['#f-action', S.draft.action], ['#f-knowledge', S.draft.knowledge],
              ['#f-category', 'Mechanical'], ['#f-root-cause', 'Wear']],
            typed: 'picker', snap: LOGBOOK_SNAP, show: ['#vdc-result', '#vdc-status'], save: 'logbook' },
          'logbook-nameplate': { label: 'Scan nameplate (Register Asset)', kind: 'photo', fns: ['equipment-label-ocr'], fail: ['equipment-label-ocr'],
            open: ['#open-asset-modal-btn', '#asset-tab-register'], press: '#a-scan-btn', input: '#a-scan-input', fixture: 'nameplate',
            settleText: [['#a-scan-status', /filled|could not|unavailable|manually/i]],
            expect: [['#a-manufacturer', 'WEG'], ['#a-model', 'W22 IE3 132M-4'], ['#a-serial-no', '1028475531']],
            typed: { sel: '#a-name', value: 'Conveyor 3 drive motor' }, snap: ['#a-asset-id', '#a-name', '#a-manufacturer', '#a-model', '#a-serial-no'],
            show: ['#a-scan-status'], save: 'asset' },
          'report-voice': { label: 'Report voice context', kind: 'voice', fns: ['voice-report-intent'], fail: ['voice-report-intent'],
            say: S.say['report-voice'], press: '#mic-btn', stopIfListening: ['#mic-btn', '#mic-label', /listening/i, 6000], settle: ['#voice-ctx'],
            chips: S.report.report_types, expectText: [['#voice-ctx-text', S.m]],
            typed: { click: '.chip[data-id="predictive"]' }, snap: [], show: ['#voice-ctx-text', '#mic-label'], save: null },
          'resume-photo': { label: 'Resume from a photo', kind: 'photo', fns: ['resume-extract'], fail: ['resume-extract'],
            press: '#btn-photo', input: '#file-photo', fixture: 'resume', settle: ['#review-sheet'],
            expectText: [['#review-body', 'Northline Packaging'], ['#review-body', 'Maintenance Technician']],
            typed: { sel: '[data-basics="label"]', value: 'Pump and conveyor technician' }, snap: ['[data-basics="label"]', '[data-basics="summary"]'],
            show: ['#upload-status'], save: 'resume' },
          companion: { label: 'Companion voice (' + vKind + ')', kind: 'voice', fns: ['voice-transcribe', 'ai-gateway'], fail: ['ai-gateway'],
            say: S.say.companion[vKind], open: [['#wh-ai-trigger', '#wh-ai-mic']], waitFor: 'WHVoice', press: '#wh-ai-mic', loose: true,
            stopAfter: ['#wh-voice-stop', 2600], settle: ['#wh-voice-confirm'],
            settleText: [['#wh-voice-intents .wh-voice-bubble-text', /\w{3,}/], ['#wh-voice-result', /\w{3,}/],
              ['#wh-voice-status', /could not|needs a hive|no audio|did not catch|not supported|denied/i]],
            expectText: [['#wh-voice-transcript', S.say.companion[vKind]]],
            typed: null, snap: [], show: ['#wh-voice-status', '#wh-voice-result'], save: 'companion' },
        };
        // the machine, picked the way a person picks it: the logbook's own asset picker, searched by name
        const vPick = async () => {
          const d = await vClick('#asset-picker-btn');
          if (!vPressed(d)) return { picker: d, machine: '' };
          await page.waitForTimeout(900);
          await page.locator('#asset-picker-search').fill(S.m, { timeout: 4000 }).catch(() => {});
          await page.waitForTimeout(700);
          let pick = await vClick('#asset-picker-list button[data-asset-id]');
          if (!vPressed(pick)) {   // the hive's asset list does not name that machine: the person takes the first asset
            await page.locator('#asset-picker-search').fill('', { timeout: 3000 }).catch(() => {});
            await page.waitForTimeout(600);
            pick = 'first asset: ' + await vClick('#asset-picker-list button[data-asset-id]');
          }
          await page.waitForTimeout(900);
          if (await vVis('#asset-picker-modal')) await page.keyboard.press('Escape').catch(() => {});
          return { picker: pick, machine: vNorm((await vVals(['#f-machine']))[0]) };
        };
        const vType = async (t) => {
          if (!t) return null;
          if (t === 'picker') return vPick();
          if (t.click) return { click: t.click, via: await vClick(t.click) };
          try { await page.locator(t.sel).first().fill(t.value, { timeout: 5000 }); return { sel: t.sel, via: 'typed' }; } catch (e) {
            return { sel: t.sel, via: 'not typeable: ' + vNorm(String(e.message || e).split('\n')[0]).slice(0, 60) };
          }
        };
        // the photo, chosen the way a person chooses it: the page's own button opens the file chooser
        const vPhoto = async (F) => {
          const fx = V_FIX[F.fixture];
          if (!fx) return 'no fixture';
          const seen = await vVis(F.press);
          if (!seen) return 'hidden';
          // the chooser promise carries its own catch: the MCP's vm rejects the WHOLE walk on an unhandled rejection, and
          // a chooser that never opens times out after the press has already been awaited
          const chooser = page.waitForEvent('filechooser', { timeout: 6000 }).catch(() => null);
          await page.locator(F.press).first().click({ timeout: 6000 }).catch(() => {});
          const fc = await chooser;
          if (fc) {
            const set = await fc.setFiles(fx).then(() => true).catch(() => false);
            if (set) return 'pressed ' + F.press + ' and chose ' + fx.name + ' in the file chooser';
          }
          try { await page.setInputFiles(F.input, fx, { timeout: 5000 }); return 'the file chooser did not open; ' + fx.name + ' was set on ' + F.input; } catch (e) { return 'absent'; }
        };
        // the page's own save, with what a person completes that the AI did not
        const V_SAVE = {
          logbook: async () => {
            const did = [];
            let machine = vNorm((await vVals(['#f-machine']))[0]);
            if (!machine) { const pk = await vPick(); did.push('picked the machine (' + pk.picker + ')'); machine = pk.machine; }
            if (!machine) return did.concat(['no machine could be picked, so the wizard cannot advance']);
            did.push('What happened? (' + await vClick('#step-panel-1 .btn-next') + ')');
            await page.waitForTimeout(900);
            const v2 = await vVals(['#f-maint-type', '#f-category']);
            if (!vNorm(v2[0])) await page.selectOption('#f-maint-type', 'Inspection', { timeout: 4000 }).then(() => did.push('chose Inspection')).catch(() => did.push('could not choose a type'));
            if (!vNorm(v2[1])) await page.selectOption('#f-category', 'Mechanical', { timeout: 4000 }).then(() => did.push('chose Mechanical')).catch(() => did.push('could not choose a discipline'));
            did.push('What did you do? (' + await vClick('#step-panel-2 .btn-next') + ')');
            await page.waitForTimeout(900);
            for (let i = 0; i < 3; i++) {
              const t1 = await vNow();
              did.push('Save Entry (' + await vClick('#save-entry-btn') + ')');
              await page.waitForTimeout(3500);
              const said = (await vLog(t1)).notices.join(' | ');
              if (/already logged today|submit again/i.test(said)) { did.push('the page asked to submit again'); continue; }
              if (/what was the impact|consequence/i.test(said)) {
                await vClick('#extras-toggle-btn');
                await page.waitForTimeout(600);
                did.push('picked the impact (' + await vClick('.consequence-btn[data-value="Running reduced"]') + ')');
                continue;
              }
              if (await vVis('#tasklist-ack-error')) { did.push('acknowledged the tasklist (' + await vClick('#tasklist-ack-check') + ')'); continue; }
              break;
            }
            return did;
          },
          asset: async () => {
            const did = [];
            const v = await vVals(['#a-asset-id', '#a-name']);
            if (!vNorm(v[0])) await page.locator('#a-asset-id').fill('LMV-' + String(Date.now()).slice(-6), { timeout: 4000 }).then(() => did.push('typed an asset ID')).catch(() => did.push('could not type an asset ID'));
            if (!vNorm(v[1])) await page.locator('#a-name').fill('Conveyor 3 drive motor', { timeout: 4000 }).then(() => did.push('typed a name')).catch(() => did.push('could not type a name'));
            did.push('Save asset (' + await vClick('#asset-submit-btn') + ')');
            return did;
          },
          resume: async () => {
            const did = ['Add selected (' + await vClick('#review-confirm') + ')'];
            await page.waitForTimeout(1500);
            const txt = await page.evaluate(() => document.body.innerText || '').catch(() => '');
            did.push(/Northline Packaging/.test(txt) ? 'the resume now shows the job read from the photo' : 'the job read from the photo is NOT on the resume');
            did.push('Save (' + await vClick('#btn-save') + ')');
            return did;
          },
          companion: async () => {
            const d = await vClick('#wh-voice-confirm');
            await page.waitForTimeout(3000);
            return ['Confirm (' + d + ')'];
          },
        };
        // ONE pass of one flow, from a fresh load
        const vPass = async (name, F, pass) => {
          const r = { pass };
          vState.active = false;
          vState.phase = name + ':load';
          // each pass starts from an empty form: logbook keeps an unsent entry as a per-person local draft, cleared here
          // as a person starting a new entry would find it
          await page.evaluate(() => { try { Object.keys(localStorage).filter((k) => /^wh_logbook_draft_/.test(k)).forEach((k) => localStorage.removeItem(k)); } catch (e) { void e; } }).catch(() => {});
          await page.goto(`${P.origin}/${P.page}`, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
          await page.waitForTimeout(4000);
          const live0 = P.persona === 'assistive-tech' ? await vLive() : [];
          vState.say = F.say || '';
          vState.kind = vKind;
          vState.needles = S.needles[name] || [];
          vState.failFns = pass === 'fail' ? F.fail : null;
          vState.phase = name + (pass === 'ok' ? ':capture' : ':fail');
          vState.active = true;
          const t0 = await vNow();
          const c0 = vState.calls.length;
          const h0 = heldBodies.length;
          await page.evaluate((t) => { window.__lmVTranscript = t; }, vState.say).catch(() => {});
          for (const o of (F.open || [])) {
            const [sel, unless] = Array.isArray(o) ? o : [o, null];
            if (unless && await vVis(unless)) continue;
            const d = await vClick(sel, true);
            if (!vPressed(d)) { r.offered = false; r.why = sel + ' is ' + d + ' for this person'; break; }
            await page.waitForTimeout(1300);
          }
          if (r.offered === false) { vState.active = false; return r; }
          if (F.waitFor === 'WHVoice') {
            for (let i = 0; i < 16 && !(await page.evaluate(() => !!(window.WHVoice && window.WHVoice.open)).catch(() => false)); i++) await page.waitForTimeout(500);
          }
          if (pass === 'fail' && F.typed) r.typed = await vType(F.typed);
          const before = (F.snap && F.snap.length) ? await vVals(F.snap) : [];
          const chips0 = F.chips ? await vChips() : null;
          r.via = F.kind === 'photo' ? await vPhoto(F) : await vClick(F.press, !!F.loose);
          if (/^(absent|hidden|disabled|no fixture)$/.test(String(r.via))) {
            r.offered = false; r.why = F.press + ' is ' + r.via + ' for this person'; vState.active = false; return r;
          }
          r.offered = true;
          if (F.then) { await page.waitForTimeout(1800); r.then = await vClick(F.then); }
          if (F.stopAfter) { await page.waitForTimeout(F.stopAfter[1]); r.stop = await vClick(F.stopAfter[0]); }
          if (F.stopIfListening) {
            const [b, lab, rx, ms] = F.stopIfListening;
            await page.waitForTimeout(ms);
            const lt = (await vVals([lab]))[0];
            if (rx.test(String(lt || ''))) r.stop = 'still listening after ' + (ms / 1000) + ' s, so the person tapped again (' + await vClick(b) + ')';
          }
          for (let i = 0; i < 20; i++) {
            let done = false;
            for (const s of (F.settle || [])) if (await vVis(s)) { done = true; break; }
            if (!done && F.settleText) {
              const tx = await vVals(F.settleText.map((x) => x[0]));
              done = F.settleText.some((x, j) => x[1].test(vNorm(tx[j])));
            }
            if (!done) { const lg0 = await vLog(t0); done = lg0.notices.some((n) => V_FAIL_RX.test(n) || V_NEEDS_HIVE_RX.test(n)); }
            if (done) break;
            await page.waitForTimeout(1000);
          }
          await page.waitForTimeout(1200);
          const lg = await vLog(t0);
          const calls = vState.calls.slice(c0);
          r.reached = [...new Set(calls.map((c) => c.fn + (c.agent ? '(' + c.agent + ')' : '') + ' ' + c.status))];
          r.heard = (lg.sr[0] && lg.sr[0].heard) || (calls.find((c) => c.heard) || {}).heard || null;
          if (lg.gum.length) r.mic = lg.gum.length + ' synthetic stream(s), AudioContext ' + (lg.gum[0].ctx || '?');
          if (lg.recorder.length) r.recorder = lg.recorder.map((x) => (x.real ? x.real + ' real chunk(s)' : 'no real audio: one placeholder chunk handed to the page') + (x.mime ? ' (' + x.mime + ')' : '')).join('; ');
          if (lg.sr.length) r.speech = 'scripted SpeechRecognition (' + lg.sr[0].lang + ')';
          if (calls.some((c) => c.image)) r.image = calls.filter((c) => c.image).map((c) => c.fn + ' got the photo (' + Math.round(c.bytes / 1024) + ' KB)').join('; ');
          r.notices = lg.notices.slice(0, 4);
          r.shown = (await vVals(F.show || [])).map((x) => vNorm(x).slice(0, 160)).filter(Boolean);
          r.refused = [...lg.notices, ...r.shown].find((x) => V_NEEDS_HIVE_RX.test(x)) || null;
          if (lg.errors.length) r.errors = lg.errors.slice(0, 3);
          if (lg.spoken.length) r.spoken = lg.spoken.slice(0, 2);
          if (P.persona === 'assistive-tech') {
            const l1 = await vLive();
            r.announced = l1.filter((x) => !live0.includes(x)).map((x) => x.slice(0, 140)).slice(0, 3);
          }
          const inPhase = (ph) => heldBodies.slice(h0).filter((w) => w.phase === 'v-' + name + ':' + ph);
          r.memory = [...new Set(heldBodies.slice(h0).filter((w) => w.memory).map((w) => w.table))];
          if (pass === 'ok') {
            r.reachedFn = calls.some((c) => F.fns.includes(c.fn) && c.status === 200);
            if (F.expect) {
              const vals = await vVals(F.expect.map((e) => e[0]));
              const miss = F.expect.filter((e, i) => vNorm(vals[i]).toLowerCase() !== vNorm(e[1]).toLowerCase()).map((e) => e[0]);
              r.filled = (F.expect.length - miss.length) + '/' + F.expect.length;
              if (miss.length) r.missing = miss;
            }
            if (F.expectText) {
              const vals = await vVals(F.expectText.map((e) => e[0]));
              const miss = F.expectText.filter((e, i) => !vNorm(vals[i]).toLowerCase().includes(vNorm(e[1]).toLowerCase())).map((e) => e[0] + ' "' + e[1].slice(0, 50) + '"');
              r.text = (F.expectText.length - miss.length) + '/' + F.expectText.length;
              if (miss.length) r.missingText = miss;
            }
            if (F.chips) {
              r.chips = await vChips();
              const miss = F.chips.filter((c) => !r.chips.includes(c));
              if (miss.length) r.missingChips = miss;
            }
            if (name === 'companion') {
              r.confirm = await vVis('#wh-voice-confirm');
              r.reply = vNorm((await vVals(['#wh-voice-intents .wh-voice-bubble-text']))[0]).slice(0, 200) || null;
            }
            r.beforeSave = inPhase('capture').filter((w) => !w.memory).map((w) => w.method + ' ' + w.table + (w.carries ? ' (carries the AI draft)' : ''));
            const good = r.reachedFn && !r.missing && !r.missingText && !r.missingChips && !r.refused;
            if (F.save && good && (name !== 'companion' || r.confirm)) {
              vState.phase = name + ':save';
              const es = vState.embed.length;
              const ts = await vNow();
              r.save = await V_SAVE[F.save]();
              await page.waitForTimeout(2500);
              r.saved = inPhase('save').filter((w) => !w.memory).map((w) => ({ w: w.method + ' ' + w.table, carries: w.carries, prov: w.prov, approver: w.approver }));
              r.afterSave = (await vLog(ts)).notices.slice(0, 3);
              r.embed = vState.embed.slice(es).filter((x) => x.carries).map((x) => (x.marked ? 'marked' : 'UNMARKED'));
              if (name === 'companion') r.result = vNorm((await vVals(['#wh-voice-result']))[0]).slice(0, 200);
            }
          } else {
            r.failed = [...new Set(calls.filter((c) => c.status >= 500 && F.fail.includes(c.fn)).map((c) => c.fn))];
            const said = [...lg.notices, ...r.shown];
            r.said = [...new Set(said.filter((x) => V_FAIL_RX.test(x) && !V_RAW_RX.test(x)))].slice(0, 3);
            r.raw = [...new Set(said.filter((x) => V_RAW_RX.test(x)))].slice(0, 2);
            if (name === 'companion') {
              const tr = vNorm((await vVals(['#wh-voice-transcript']))[0]);
              r.kept = tr && tr === vNorm(vState.say) ? 'the words it heard stay on screen' : 'LOST: the overlay no longer shows what it heard';
            } else if (F.chips) {
              const ch = await vChips();
              const lost = (chips0 || []).filter((c) => !ch.includes(c));
              r.kept = lost.length ? 'CHANGED: ' + lost.join(', ') + ' no longer picked' : 'the reports the person picked stay picked (' + ((chips0 || []).join(', ') || 'none') + ')';
            } else if (F.snap && F.snap.length) {
              const after = await vVals(F.snap);
              const changed = F.snap.filter((s, i) => vNorm(after[i]) !== vNorm(before[i]));
              r.kept = changed.length ? 'CHANGED: ' + changed.map((s) => s + ' "' + vNorm(before[F.snap.indexOf(s)]).slice(0, 40) + '" -> "' + vNorm(after[F.snap.indexOf(s)]).slice(0, 40) + '"').join('; ')
                : 'unchanged (' + F.snap.length + ' fields' + (before.some((x) => vNorm(x)) ? ', the person\'s own entry among them' : ', all empty') + ')';
            }
            r.writes = inPhase('fail').filter((w) => !w.memory).map((w) => w.method + ' ' + w.table);
          }
          vState.active = false;
          vState.failFns = null;
          await page.keyboard.press('Escape').catch(() => {});
          return r;
        };
        // the verdicts, in the person's terms
        const vJudge = (name, F, ok, fl) => {
          const tag = `${vp.name}: ${F.label}`;
          if (ok.threw) { problems.push(`${tag}: the walk threw: ${ok.threw}`); return; }
          if (ok.offered === false) { notes.push(`${tag} is not offered here (${ok.why})`); return; }
          if (ok.refused) { notes.push(`${tag}: the page declined by design for ${P.castName} ("${ok.refused.slice(0, 100)}")`); return; }
          if (!ok.reachedFn) problems.push(`${tag}: what the person ${F.kind === 'photo' ? 'photographed' : 'said'} never reached ${F.fns.join(' / ')} (reached: ${(ok.reached || []).join(', ') || 'nothing'}${(ok.shown || []).length ? '; the page showed "' + ok.shown[0].slice(0, 90) + '"' : ''})`);
          else {
            if (ok.missing) problems.push(`${tag}: the AI's draft did not reach ${ok.missing.join(', ')}`);
            if (ok.missingText) problems.push(`${tag}: the page did not show ${ok.missingText.join('; ')}`);
            if (ok.missingChips) problems.push(`${tag}: the spoken request did not select ${ok.missingChips.join(', ')}`);
          }
          if (name === 'companion' && ok.reachedFn) {
            if (V_COMPANION_KIND[P.page] && !ok.confirm) problems.push(`${tag}: the spoken ${vKind} was not offered for confirmation (${(ok.shown || []).join(' | ') || 'no status'})`);
            if (!V_COMPANION_KIND[P.page] && !ok.reply) problems.push(`${tag}: the spoken question got no reply (${(ok.shown || []).join(' | ') || 'no status'})`);
          }
          const early = (ok.beforeSave || []).filter((w) => /carries the AI draft/.test(w));
          if (early.length) problems.push(`${tag}: the AI's draft was written before the person saved: ${early.join(', ')}`);
          else if ((ok.beforeSave || []).length) notes.push(`${tag}: writes held before the save, none carrying the AI's draft: ${ok.beforeSave.join(', ')}`);
          if (ok.save) {
            if (name === 'companion') {
              if (V_LOCK_RX.test(ok.result || '')) problems.push(`${tag}: the person confirmed the spoken ${vKind} and the page refused it: "${ok.result.slice(0, 120)}"`);
              else notes.push(`${tag}: Confirm answered "${(ok.result || '').slice(0, 120)}"`);
            } else {
              if (ok.save.some((x) => /NOT on the resume/.test(x))) problems.push(`${tag}: "Add selected" did not put what was read from the photo on the resume`);
              const land = (ok.saved || []).filter((w) => w.carries);
              if (!land.length) problems.push(`${tag}: the person saved (${ok.save.join(' > ')}) and nothing carrying the AI's draft was written (${(ok.saved || []).map((w) => w.w).join(', ') || 'no write'}; the page said: ${(ok.afterSave || []).join(' | ') || 'nothing'})`);
              for (const w of land) {
                if (w.prov === 'UNMARKED') problems.push(`${tag}: the save wrote ${w.w} carrying the AI's draft with no mark that the AI drafted it`);
                else if (w.prov === 'none-defined') (V_PROV_STRICT ? problems : notes).push(`${tag}: ${w.w} carries the AI's draft and the platform defines no machine-authorship mark on that table, so it reads as the person's own words`);
                else if (w.prov === 'unknown') notes.push(`${tag}: ${w.w} carries the AI's draft; this instrument does not know that table's authorship mark`);
                if (!w.approver) notes.push(`${tag}: ${w.w} does not name who saved it`);
              }
              if ((ok.embed || []).includes('UNMARKED')) problems.push(`${tag}: after the save the page sent the AI-drafted text to embed-entry for fault_knowledge with no mark that the AI drafted it (fault_knowledge.source defaults to 'manual')`);
            }
          }
          if (fl && fl.offered !== false && !fl.refused) {
            if (!(fl.failed || []).length) problems.push(`${tag}: the failure pass never reached ${F.fail.join(' / ')} - the failure path is unproven`);
            else {
              if (!(fl.said || []).length) problems.push(`${tag}: when ${fl.failed.join(', ')} failed the page said nothing a person can act on${(fl.raw || []).length ? ' (it showed "' + fl.raw[0].slice(0, 80) + '")' : ''}`);
              else if ((fl.raw || []).length) notes.push(`${tag}: on failure the page also showed raw text: "${fl.raw[0].slice(0, 80)}"`);
              if (/^(CHANGED|LOST)/.test(String(fl.kept || ''))) problems.push(`${tag}: when ${fl.failed.join(', ')} failed, what the person had entered did not survive (${fl.kept})`);
            }
            if ((fl.writes || []).length) notes.push(`${tag}: writes held during the failure pass: ${fl.writes.join(', ')}`);
          } else if (fl && fl.offered === false) notes.push(`${tag}: the failure pass could not start (${fl.why})`);
        };
        step.voice = { machine: vMach, mic: 'synthetic MediaStream (oscillator -> MediaStreamDestination) from a replaced getUserMedia',
          speech: vState.srMode === 'absent' ? 'Web Speech API removed (the iOS / Firefox recorder path)' : 'scripted SpeechRecognition', flows: [] };
        for (const name of vFlowsFor(P.page)) {
          const F = FLOWS[name];
          const ok = await vPass(name, F, 'ok').catch((e) => ({ pass: 'ok', threw: vNorm(String(e.message || e)).slice(0, 140) }));
          const fl = (ok.threw || ok.offered === false || ok.refused) ? null
            : await vPass(name, F, 'fail').catch((e) => ({ pass: 'fail', offered: false, why: 'threw: ' + vNorm(String(e.message || e)).slice(0, 120) }));
          vState.active = false;
          vJudge(name, F, ok, fl);
          step.voice.flows.push({ flow: name, label: F.label, offered: ok.offered !== false && !ok.threw, via: ok.via, then: ok.then, stop: ok.stop,
            heard: ok.heard, mic: ok.mic, recorder: ok.recorder, speech: ok.speech, image: ok.image, reached: ok.reached,
            filled: ok.filled, missing: ok.missing, text: ok.text, missingText: ok.missingText, chips: ok.chips, confirm: ok.confirm, reply: ok.reply,
            refused: ok.refused, beforeSave: ok.beforeSave, memory: ok.memory, save: ok.save, saved: ok.saved, embed: ok.embed,
            result: ok.result, afterSave: ok.afterSave, announced: ok.announced, spoken: ok.spoken, errors: ok.errors, why: ok.why || ok.threw,
            fail: fl ? { failed: fl.failed, said: fl.said, raw: fl.raw, kept: fl.kept, typed: fl.typed, writes: fl.writes, why: fl.why } : null });
        }
        if (step.voice.flows.some((f) => /placeholder/.test(String(f.recorder || '')))) notes.push(`${vp.name}: the synthetic stream gave a recorder no audio (AudioContext not running); one placeholder chunk was handed to the page - transcription is stubbed, so the words are the walk's`);
        if (!step.voice.flows.some((f) => f.offered)) problems.push(`${vp.name}: no voice or photo entry point on ${P.page} was reachable for ${P.castName}`);
      }
      // ==== LM-V PART C END ====
