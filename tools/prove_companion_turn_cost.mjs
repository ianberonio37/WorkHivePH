// prove_companion_turn_cost.mjs - what one voice-companion turn costs the person BEFORE its answer is asked for
// (BRH-AO, 2026-10-27).
//
// voice-handler.js assembled a whole platform prompt in the browser every turn - a full platform snapshot, the legacy
// scraper, recent memory, cross-hive context, a glossary, canonical KPI data, proactive alerts, a repeated-issue flag, a
// skill-gap flag - and sent it as context.platform_prompt, which no server code reads. Every read ran before the gateway
// call, so the person waited for them; and an "offline snapshot" insert after it called getUser and then threw.
//
// THE INSTRUMENT. Chromium at 390 with a fake microphone (.tmp/probe.wav), signed in as a worker, on index.html. The
// three network edges that would make it a model test are answered locally, so the run spends nothing and measures only
// the page: voice-transcribe answers a fixed question, the voice-action router answers "query.ask" (the conversational
// path), and the voice-journal answer is canned. Every request the page makes is timed:
//   assembly  - from the transcript landing to the voice-journal request leaving: the client's own work before the answer
//   pre       - the requests in that window (table reads, RPCs, auth, functions)
//   post      - the requests in the 5 s after the answer (the page's bookkeeping writes)
//   prompt    - whether the voice-journal request still carried context.platform_prompt, and its size
//
//   node tools/prove_companion_turn_cost.mjs --label before|after [--runs 3]   -> companion_turn_cost.json (merged by label)
//   node tools/prove_companion_turn_cost.mjs --label gate --gate       the board's form: FAIL if the prompt is sent or > 5 requests precede the answer
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ORIGIN = 'http://127.0.0.1:5000/workhive';
const OUT = 'companion_turn_cost.json';
const args = process.argv.slice(2);
const arg = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const LABEL = arg('--label', 'run');
const RUNS = Number(arg('--runs', '3'));
const QUESTION = 'How do I fix a pump that keeps tripping on overload?';
const ANSWER = 'Check the overload relay setting against the motor nameplate current first, then the pump for a jam.';

function kind(url) {
  const u = new URL(url);
  let m;
  if ((m = u.pathname.match(/\/rest\/v1\/rpc\/([\w-]+)/))) return 'rpc ' + m[1];
  if ((m = u.pathname.match(/\/rest\/v1\/([\w-]+)/))) return 'table ' + m[1];
  if ((m = u.pathname.match(/\/functions\/v1\/([\w-]+)/))) return 'fn ' + m[1];
  if (u.pathname.includes('/auth/v1/')) return 'auth ' + u.pathname.split('/auth/v1/')[1];
  return null;
}

async function oneTurn(browser) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true,
    timezoneId: 'Asia/Manila', permissions: ['microphone'] });
  try {
    await assertSignedIn(signIn(ctx, 'worker'));
    const page = await ctx.newPage();
    const reqs = [];
    const marks = { transcribed: null, asked: null, answered: null };
    let prompt = null;
    page.on('request', (r) => { const k = kind(r.url()); if (k) reqs.push({ k, m: r.method(), t: Date.now() }); });
    await page.route('**/functions/v1/voice-transcribe', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ text: QUESTION }) });
      marks.transcribed = Date.now();
    });
    await page.route('**/functions/v1/ai-gateway', async (route) => {
      let b = {};
      try { b = route.request().postDataJSON() || {}; } catch (_) { /* not JSON */ }
      if (b.agent === 'voice-action') {
        return route.fulfill({ status: 200, contentType: 'application/json',
          body: JSON.stringify({ ok: true, data: { route_result: { intents: [{ kind: 'query.ask', confidence: 0.9 }], narration: '' } } }) });
      }
      if (b.agent === 'voice-journal') {
        marks.asked = Date.now();
        const pp = b.context && b.context.platform_prompt;
        prompt = { sent: typeof pp === 'string', chars: typeof pp === 'string' ? pp.length : 0 };
        await route.fulfill({ status: 200, contentType: 'application/json',
          body: JSON.stringify({ ok: true, trace_id: '0123456789abcdef', data: { answer: ANSWER, agent: 'voice-journal' } }) });
        marks.answered = Date.now();
        return;
      }
      return route.continue();
    });
    await page.goto(`${ORIGIN}/index.html`, { waitUntil: 'domcontentloaded' });
    for (let i = 0; i < 30 && !(await page.evaluate(() => !!(window.WHVoice && window.WHVoice.open)).catch(() => false)); i++) await page.waitForTimeout(500);
    await page.waitForTimeout(2500);
    await page.evaluate(() => window.WHVoice.open());
    await page.waitForTimeout(2500);
    await page.click('#wh-voice-stop', { timeout: 5000 }).catch(() => {});
    for (let i = 0; i < 60 && !marks.answered; i++) await page.waitForTimeout(500);
    await page.waitForTimeout(5000);
    if (!marks.transcribed || !marks.asked) return { ok: false, why: `transcribed ${!!marks.transcribed}, asked ${!!marks.asked}` };
    const pre = reqs.filter((r) => r.t >= marks.transcribed && r.t < marks.asked && !/^fn ai-gateway$/.test(r.k));
    const post = reqs.filter((r) => r.t > marks.answered && r.t <= marks.answered + 5000);
    const tally = (xs) => xs.reduce((o, r) => { const key = `${r.m} ${r.k}`; o[key] = (o[key] || 0) + 1; return o; }, {});
    return { ok: true, assembly_ms: marks.asked - marks.transcribed, pre_n: pre.length, pre: tally(pre),
      post_n: post.length, post: tally(post), prompt };
  } finally { await ctx.close().catch(() => {}); }
}

const browser = await chromium.launch({ headless: true, args: ['--use-fake-device-for-media-stream',
  '--use-fake-ui-for-media-stream', '--use-file-for-fake-audio-capture=.tmp/probe.wav%noloop'] });
const runs = [];
for (let i = 0; i < RUNS; i++) {
  const r = await oneTurn(browser);
  runs.push(r);
  console.log(`  ${LABEL} run ${i + 1}: ${r.ok ? `assembly ${r.assembly_ms} ms, ${r.pre_n} requests before the answer, ${r.post_n} after; platform_prompt ${r.prompt && r.prompt.sent ? r.prompt.chars + ' chars' : 'not sent'}` : 'FAILED ' + r.why}`);
}
await browser.close();
const good = runs.filter((r) => r.ok);
const med = (xs) => { const s = [...xs].sort((a, b) => a - b); return s.length ? s[Math.floor(s.length / 2)] : null; };
const summary = { label: LABEL, ran: new Date().toISOString(), runs: good.length, assembly_ms_median: med(good.map((r) => r.assembly_ms)),
  pre_requests_median: med(good.map((r) => r.pre_n)), post_requests_median: med(good.map((r) => r.post_n)),
  example: good[0] || null };
const prior = existsSync(OUT) ? JSON.parse(readFileSync(OUT, 'utf8')) : {};
prior[LABEL] = summary;
writeFileSync(OUT, JSON.stringify(prior, null, 1));
console.log(`${LABEL}: median assembly ${summary.assembly_ms_median} ms, ${summary.pre_requests_median} requests before the answer, ${summary.post_requests_median} after (${good.length}/${RUNS} runs)`);
// --gate (BRH-AO): the client prompt must not come back, and the question must leave after at most 5 requests
if (args.includes('--gate')) {
  const sent = good.some((r) => r.prompt && r.prompt.sent);
  const ok = good.length === RUNS && !sent && summary.pre_requests_median <= 5;
  console.log(`${ok ? 'PASS' : 'FAIL'} companion-turn-cost - ${summary.pre_requests_median} requests before the answer (budget 5), `
    + `platform_prompt ${sent ? 'SENT' : 'not sent'}, median client work ${summary.assembly_ms_median} ms`);
  process.exitCode = ok ? 0 : 1;
} else {
  process.exitCode = good.length === RUNS ? 0 : 1;
}
