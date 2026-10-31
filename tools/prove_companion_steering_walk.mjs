// prove_companion_steering_walk.mjs - the voice companion, walked trigger by trigger: what the browser sends when a worker
// says the words that used to build a dead instruction (BRH-AP, 2026-10-30).
//
// THE DEFECT. voice-handler.js ran ~60 detectors per turn and appended an instruction for the model to `perTurnAnchors`.
// The string rode inside context.platform_prompt, a field no server reads, so no model ever received an ACTION CONFIRMATION,
// a SHARE LINK, an ERASURE REQUEST or a QUIET HOURS rule. The fix (69268f24) moved the ones a reply needs to the server
// (_shared/turn-steering.ts, the agent's own prompt) and removed the rest, keeping the page actions some of them sat beside
// (a timer, a push prompt, a pin, an ack style, an erasure, a buddy).
//
// THE WALK. Chromium at phone-390 and desktop-1280, signed in as a worker, on index.html. For each row the companion is opened
// and the row's trigger is said (voice-transcribe answers it; the voice-action router answers query.ask, the conversational
// path where the anchors were built). Each turn is read for:
//   asked    - a voice-journal request left carrying the trigger as its message
//   clean    - that request carries no context.platform_prompt and no "<LABEL> —" instruction text
//   answered - the reply is on screen
//   action   - where the detector also acts on the page, the action still happens (a timer, a pin, a DELETE, ...)
//   server   - for the four rules that moved, the request goes to the REAL local gateway and its `steering` names the rule
// Every write the page makes is answered locally (nothing is erased, filed or sent), and the service worker is blocked so the
// file under test is the file served.
//
// THE TEETH. --teeth serves the last voice-handler.js that built perTurnAnchors (git 69268f24~1). The same walk must then find
// each row's instruction in a request no server reads - the reproduction, on demand. Three rows cannot reproduce: their old
// conditions read a field the detector never returned (_scrubPii -> .markers, _detectSuspiciousActivity -> .kind,
// _checkMemoryPressure -> .level), so the instruction was never even built; the walk records that as what it measured.
//
//   node tools/prove_companion_steering_walk.mjs [--teeth] [--only BRH669,BRH705] [--viewport phone-390]
//     -> companion_steering_walk.json (teeth -> companion_steering_walk_teeth.json); exit 1 on any failed row
import { chromium } from 'playwright';
import { execSync } from 'child_process';
import { readFileSync, writeFileSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ORIGIN = 'http://127.0.0.1:5000/workhive';
const args = process.argv.slice(2);
const arg = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const TEETH = args.includes('--teeth');
const ONLY = arg('--only', '') ? new Set(arg('--only', '').split(',')) : null;
const OUT = TEETH ? 'companion_steering_walk_teeth.json' : 'companion_steering_walk.json';
const OLD_REV = '69268f24~1';   // the last voice-handler.js that built perTurnAnchors (~1, never ^: cmd.exe eats a caret and serves the FIXED file)
const ANSWER = 'Noted. Check the overload relay against the motor nameplate first.';
const VIEWPORTS = {
  'phone-390': { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3 },
  'desktop-1280': { viewport: { width: 1280, height: 800 } },
};
const ONE_VIEWPORT = arg('--viewport', '');
const PH_LATE = Date.UTC(2026, 9, 30, 15, 10);      // 23:10 in Manila - quiet hours
const PH_NEAR_END = Date.UTC(2026, 9, 30, 7, 45);   // 15:45 in Manila - fifteen minutes before a 16:00 shift end

// id, the instruction's label as the old file wrote it, what the worker says (earlier turns first), and what the page must
// still do. kind: 'removed' (the instruction is gone) | 'moved' (the server states it - asked of the real gateway)
// | 'never' (the old condition could not be met - the walk records whether the old file built it at all)
const CASES = [
  { id: 'BRH669', label: 'ACTION CONFIRMATION', say: ['log a bearing replacement on the conveyor'] },
  { id: 'BRH670', label: 'BATCH ACTION', say: ['log bearing replacement on P-203, P-205, and P-208'] },
  { id: 'BRH672', label: 'CO-WORKER MENTION', say: ['I changed the seal together with Ramon'] },
  { id: 'BRH674', label: 'EXPORT REQUEST', say: ['save this conversation'] },
  { id: 'BRH675', label: 'PHOTO INTENT', say: ['let me show you the crack on the housing'] },
  { id: 'BRH677', label: 'TERMINOLOGY RESOLVED', say: ['what about the Siemens Simotics motor'] },   // the old matcher wanted two name words
  { id: 'BRH678', label: 'BRANCH RECALL', say: ['back to the compressor'],
    setup: () => window.WHVoice._pushBranch('compressor check', { asset_tag: 'C-001' }) },
  { id: 'BRH679', label: 'IDENTITY DRIFT', say: ['what is due today', 'and what about tomorrow'],
    between: () => localStorage.setItem('wh_last_worker', 'Somebody Else') },
  { id: 'BRH680', label: 'ACTION REPLAY', say: ['same fix for P-205'],
    setup: () => window.WHVoice._stashConfirmedAction('logbook.create', { asset_tag: 'P-203' }) },
  { id: 'BRH682', label: 'TIMER SCHEDULED', say: ['remind me in 15 min to check the oil level'],
    action: { what: 'a 15-minute timer is running', read: () => (window.WHVoice._getActiveTimers() || []).length > 0 } },
  { id: 'BRH683', label: 'ACTION QUEUE', say: ['log the oil change then schedule a PM for the pump'] },
  { id: 'BRH684', label: 'PDF EXPORT REQUEST', say: ['save this as a pdf'] },
  { id: 'BRH686', label: 'PUSH READINESS', say: ['turn on alerts'],
    action: { what: 'the browser is asked for notification permission', read: () => (window.__whPushAsked || 0) > 0 } },
  { id: 'BRH688', label: 'QUESTION SHAPE', say: ['how do I reset the VFD fault'], kind: 'moved', steering: /^shape_how_to$/ },
  { id: 'BRH690', label: 'SHARE LINK', say: ['share this with my supervisor'] },
  { id: 'BRH691', label: 'READBACK', say: ['what is the MTBF of the main compressor', 'read that again'] },
  { id: 'BRH695', label: 'INCIDENT GATE', say: ['someone got hurt on the line'], kind: 'moved', steering: /^incident$/ },
  { id: 'BRH702', label: 'PRECISION RULE', say: ['what is the availability of the boiler this month'], kind: 'moved',
    prompt: 'Every figure you quote carries its unit and sensible precision' },
  { id: 'BRH703', label: 'ASSET TAG NORMALIZED', say: ['what is the status of pump p 203'] },
  { id: 'BRH704', label: 'TIME RANGE NORMALIZED', say: ['what failed yesterday'] },
  { id: 'BRH705', label: 'ACK STYLE', say: ['just give me the answer, no small talk'],
    action: { what: 'the terse style is kept', read: () => window.WHVoice._getAckStyle() === 'terse' } },
  { id: 'BRH707', label: 'PIN', say: ['what is the MTBF of the main compressor', 'pin this'],
    action: { what: 'the prior reply is pinned', read: () => (window.WHVoice._getPinnedTurns(localStorage.getItem('wh_last_worker')) || []).length > 0 } },
  { id: 'BRH709', label: 'SESSION TAG', say: ['tag this as pump overhaul'] },
  { id: 'BRH711', label: 'SHIFT END HORIZON', say: ['what is left on my list'], clock: PH_NEAR_END,
    setup: () => localStorage.setItem('wh_shift_end_hour', '16') },
  { id: 'BRH712', label: 'QUIET HOURS', say: ['what is left on my list'], clock: PH_LATE, kind: 'moved', steering: /^quiet_hours$/,
    serverClock: true },
  { id: 'BRH713', label: 'MENTOR HANDOFF', say: ["I'll ask my supervisor about the vibration"] },
  { id: 'BRH714', label: 'PII SCRUBBED', say: ['call me at 09171234567 about the pump'], kind: 'never' },
  { id: 'BRH715', label: 'CONSENT CHANGE', say: ['I consent to the recording'] },
  { id: 'BRH716', label: 'ERASURE DONE', say: ['delete my voice history', 'yes'],
    action: { what: "the worker's voice history is deleted (the DELETE leaves; answered locally)", net: /DELETE .*\/rest\/v1\/voice_journal_entries/ } },
  { id: 'BRH717', label: 'ERASURE REQUEST', say: ['delete my voice history'] },
  { id: 'BRH718', label: 'SUSPICIOUS ACTIVITY', say: ['what is due today'], kind: 'never',
    setup: () => { const t = Date.now(); localStorage.setItem('wh_voice_intent_hist_' + localStorage.getItem('wh_last_worker'),
      JSON.stringify([0, 1, 2, 3, 4, 5].map((i) => ({ intent: 'logbook.create', ts: t - 50000 + i * 8000 })))); } },
  { id: 'BRH719', label: 'VOICE-ONLY TOGGLE', say: ['voice only mode on'] },
  { id: 'BRH720', label: 'MEMORY PRESSURE', say: ['what is due today'], kind: 'never', lowMemory: true },
  { id: 'BRH721', label: 'HANDOFF', say: ['send this to Ramon'] },
  { id: 'BRH722', label: 'SHARED NOTE', say: ['share this with the team'] },
  { id: 'BRH723', label: 'WATCHLIST', say: ['notify me on P-203'] },
  { id: 'BRH724', label: 'RESOLUTION CAPTURE', say: ['the pump is fixed, it runs now'] },
  { id: 'BRH728', label: 'BUDDY SET', say: ['set my buddy to Ramon'],
    action: { what: 'the buddy is kept for the shift', read: () => !!window.WHVoice._getBuddy(localStorage.getItem('wh_last_worker')) } },
];

const OLD_SOURCE = TEETH ? execSync(`git show ${OLD_REV}:voice-handler.js`, { maxBuffer: 64 * 1024 * 1024 }).toString('utf8') : null;
const AGENT_SOURCE = readFileSync('supabase/functions/voice-journal-agent/index.ts', 'utf8');

async function walk(browser, c, vpName) {
  const ctx = await browser.newContext({ ...VIEWPORTS[vpName], timezoneId: 'Asia/Manila', permissions: ['microphone'],
    serviceWorkers: 'block' });
  const out = { id: c.id, viewport: vpName, checks: {}, notes: [] };
  try {
    await assertSignedIn(signIn(ctx, 'worker'));
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e.message || e).slice(0, 160)));
    // the push prompt is a page action: count the asks, and start from "not yet decided" so the page may ask
    await page.addInitScript((low) => {
      window.__whPushAsked = 0;
      try {
        Object.defineProperty(Notification, 'permission', { get: () => 'default', configurable: true });
        Notification.requestPermission = () => { window.__whPushAsked++; return Promise.resolve('default'); };
      } catch (_) { /* no Notification in this engine */ }
      if (low) { try { Object.defineProperty(Navigator.prototype, 'deviceMemory', { get: () => 1, configurable: true }); } catch (_) { /* read-only */ } }
    }, !!c.lowMemory);
    const queue = [...c.say];
    const asked = [];
    const writes = [];
    if (OLD_SOURCE) {
      await page.route('**/voice-handler.js*', (route) => route.fulfill({ status: 200, contentType: 'application/javascript', body: OLD_SOURCE }));
    }
    await page.route('**/functions/v1/voice-transcribe', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ text: queue.shift() || '', lang: 'en' }) }));
    await page.route('**/functions/v1/tts-speak', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }));
    await page.route('**/functions/v1/ai-gateway', async (route) => {
      let b = {};
      try { b = route.request().postDataJSON() || {}; } catch (_) { /* not JSON */ }
      if (b.agent === 'voice-action') {
        return route.fulfill({ status: 200, contentType: 'application/json',
          body: JSON.stringify({ ok: true, data: { route_result: { intents: [{ kind: 'query.ask', confidence: 0.9 }], narration: '' } } }) });
      }
      if (b.agent === 'voice-journal') {
        const rec = { message: b.message, body: JSON.stringify(b), steering: null, done: false, t0: Date.now() };
        asked.push(rec);
        if (c.kind === 'moved' && !OLD_SOURCE && c.steering) {
          // the moved half: the real local gateway decides what to state, and says so in `steering`
          const resp = await route.fetch().catch(() => null);
          let j = null;
          try { j = resp ? await resp.json() : null; } catch (_) { /* not JSON */ }
          rec.steering = (j && j.data && (j.data.steering || j.steering)) || [];
          rec.status = resp ? resp.status() : 0;
          rec.ms = Date.now() - rec.t0;
          rec.done = true;
          return route.fulfill({ status: 200, contentType: 'application/json',
            body: JSON.stringify({ ok: true, trace_id: '0123456789abcdef', data: { answer: ANSWER, agent: 'voice-journal', steering: rec.steering } }) });
        }
        rec.done = true;
        return route.fulfill({ status: 200, contentType: 'application/json',
          body: JSON.stringify({ ok: true, trace_id: '0123456789abcdef', data: { answer: ANSWER, agent: 'voice-journal', steering: [] } }) });
      }
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, data: {} }) });
    });
    // nothing this walk says is filed, sent or erased: every table write is answered here
    await page.route('**/rest/v1/**', (route) => {
      const r = route.request();
      const m = r.method();
      if (m === 'GET' || m === 'HEAD' || m === 'OPTIONS' || /\/rest\/v1\/rpc\//.test(r.url())) return route.fallback();
      writes.push(`${m} ${new URL(r.url()).pathname}`);
      return route.fulfill({ status: m === 'POST' ? 201 : 204, contentType: 'application/json', body: m === 'POST' ? '[]' : '' });
    });
    await page.goto(`${ORIGIN}/index.html`, { waitUntil: 'domcontentloaded' });
    for (let i = 0; i < 40 && !(await page.evaluate(() => !!(window.WHVoice && window.WHVoice.open)).catch(() => false)); i++) await page.waitForTimeout(500);
    if (!(await page.evaluate(() => !!(window.WHVoice && window.WHVoice.open)).catch(() => false))) {
      out.checks.loaded = false; out.notes.push('the companion never loaded'); return out;
    }
    await page.waitForTimeout(1500);
    if (c.clock) await page.clock.setFixedTime(new Date(c.clock));
    if (c.setup) await page.evaluate(c.setup);
    for (let t = 0; t < c.say.length; t++) {
      if (t > 0 && c.between) await page.evaluate(c.between);
      const before = asked.length;
      await page.evaluate(() => window.WHVoice.open());
      await page.waitForTimeout(1500);
      await page.click('#wh-voice-stop', { timeout: 5000 }).catch(() => {});
      for (let i = 0; i < 40 && asked.length === before; i++) await page.waitForTimeout(500);
      // a moved rule's turn goes to the REAL gateway: wait for its answer (a model turn), not only for the request to leave
      for (let i = 0; i < 120 && asked.length > before && !asked[asked.length - 1].done; i++) await page.waitForTimeout(500);
      await page.waitForTimeout(2500);
      if (t < c.say.length - 1) {
        await page.click('#wh-voice-cancel', { timeout: 3000 }).catch(() => {});
        await page.keyboard.press('Escape').catch(() => {});
        await page.waitForTimeout(800);
      }
    }
    const trigger = c.say[c.say.length - 1];
    const turn = asked.filter((a) => a.message === trigger).pop() || null;
    const shown = await page.evaluate((a) => (document.body.innerText || '').includes(a), ANSWER).catch(() => false);
    const instr = turn ? new RegExp(`${c.label.replace(/[-]/g, '\\-')} [—-]`).test(turn.body) : false;
    const pp = turn ? /"platform_prompt"/.test(turn.body) : false;
    out.checks.asked = !!turn;
    out.voice_journal_requests = asked.length;
    if (turn) {
      // the evidence: the instruction where it rode, or the request's opening when there is none
      const at = turn.body.indexOf(c.label + ' ');
      out.request_excerpt = at >= 0 ? turn.body.slice(Math.max(0, at - 60), at + 200) : turn.body.slice(0, 400);
    }
    out.instruction_sent = instr;
    out.platform_prompt_sent = pp;
    out.checks.answered = shown;
    if (c.action) {
      if (c.action.net) out.checks.action = writes.some((w) => c.action.net.test(w));
      else out.checks.action = await page.evaluate(c.action.read).catch(() => false);
      out.action = c.action.what;
    }
    out.writes = writes.slice(0, 12);
    out.page_errors = errors.slice(0, 5);
    if (turn && turn.steering) { out.steering = turn.steering; out.gateway_status = turn.status; out.gateway_ms = turn.ms; }
    return out;
  } catch (e) {
    out.notes.push('walk error: ' + String(e.message || e).slice(0, 200));
    return out;
  } finally { await ctx.close().catch(() => {}); }
}

function verdict(c, r) {
  // the walk's own verdict for one row at one viewport
  if (r.checks.loaded === false || !r.checks.asked) return { ok: false, why: r.notes[0] || 'the trigger never reached the companion' };
  if (TEETH) {
    // the reproduction: the old file built this instruction and sent it where no server reads it
    if (c.kind === 'never') return { ok: true, why: r.instruction_sent ? 'the old file built it after all' : 'the old condition read a field its detector never returned - never built, dead twice' };
    return r.instruction_sent && r.platform_prompt_sent
      ? { ok: true, why: `reproduced: "${c.label} —" rode in context.platform_prompt, which no server reads` }
      : { ok: false, why: `not reproduced: the old file sent ${r.instruction_sent ? 'the instruction outside platform_prompt' : 'no such instruction'} for this trigger` };
  }
  const bad = [];
  if (r.instruction_sent) bad.push(`"${c.label} —" is built and sent again`);
  if (r.platform_prompt_sent) bad.push('context.platform_prompt is sent again');
  if (!r.checks.answered) bad.push('the reply never reached the screen');
  if (r.checks.action === false) bad.push(`the page action stopped: ${r.action}`);
  if (c.kind === 'moved') {
    if (c.prompt && !AGENT_SOURCE.includes(c.prompt)) bad.push('the agent no longer states the rule in its own prompt');
    if (c.steering) {
      const kinds = Array.isArray(r.steering) ? r.steering : [];
      const now = new Date(); const phHour = (now.getUTCHours() + 8) % 24;
      const expect = c.serverClock ? (phHour >= 22 || phHour < 6) : true;   // the server reads its own clock, not the page's
      const said = kinds.some((k) => c.steering.test(String(k)));
      if (r.gateway_status && r.gateway_status !== 200) bad.push(`the gateway answered ${r.gateway_status}`);
      else if (expect && !said) bad.push(`the gateway did not state ${c.steering} (steering ${JSON.stringify(kinds)})`);
      else if (!expect && said) bad.push(`the gateway stated ${c.steering} outside the hours it applies`);
    }
  }
  return bad.length ? { ok: false, why: bad.join('; ') } : { ok: true, why: 'nothing dead is sent; the turn answers' + (r.action ? '; ' + r.action : '') };
}

const browser = await chromium.launch({ headless: true, args: ['--use-fake-device-for-media-stream',
  '--use-fake-ui-for-media-stream', '--use-file-for-fake-audio-capture=.tmp/probe.wav%noloop'] });
const results = [];
let failed = 0;
for (const c of CASES) {
  if (ONLY && !ONLY.has(c.id)) continue;
  for (const vp of Object.keys(VIEWPORTS)) {
    if (ONE_VIEWPORT && vp !== ONE_VIEWPORT) continue;
    const r = await walk(browser, c, vp);
    const v = verdict(c, r);
    r.ok = v.ok; r.why = v.why; r.label = c.label; r.kind = c.kind || 'removed'; r.said = c.say;
    if (!v.ok) failed++;
    results.push(r);
    console.log(`${v.ok ? 'PASS' : 'FAIL'} ${c.id} ${vp} ${c.label}: ${v.why}`);
  }
}
await browser.close();
// --only re-walks a few rows INTO the last report (fresh, same mode), so a corrected trigger does not discard the rest
let all = results;
if (ONLY) {
  try {
    const prior = JSON.parse(readFileSync(OUT, 'utf8'));
    if (prior.teeth === TEETH && Date.now() - Date.parse(prior.ran) < 3 * 3600 * 1000) {
      const key = (r) => r.id + '|' + r.viewport;
      const fresh = new Set(results.map(key));
      all = prior.results.filter((r) => !fresh.has(key(r))).concat(results);
    }
  } catch (_) { /* no prior report - this run stands alone */ }
}
const allFailed = all.filter((r) => !r.ok).length;
const report = { ran: new Date().toISOString(), teeth: TEETH, old_rev: TEETH ? OLD_REV : null, rows: all.length, failed: allFailed, results: all };
writeFileSync(OUT, JSON.stringify(report, null, 1));
console.log(`${allFailed ? 'FAIL' : 'PASS'} companion-steering-walk${TEETH ? ' (teeth)' : ''}: ${all.length - allFailed}/${all.length} walks`
  + (all !== results ? ` (${results.length} re-walked into the last report)` : ''));
process.exitCode = allFailed ? 1 : 0;
