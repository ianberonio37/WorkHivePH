// ai_chain_failover_probe.mjs - runs the REAL supabase/functions/_shared/ai-chain.ts (and provider-health.ts) under
// Node v24, which strips the TypeScript natively, to prove how the chain fails over. It never goes through an edge
// function, so it writes no rate-limit, cost, trace or budget row anywhere.
//
//   node tools/ai_chain_failover_probe.mjs            OFFLINE (default): fetch is stubbed, 0 network calls, deterministic.
//       1. classifyProviderFailure sorts 402/404/401/403/400-invalid-model as PERMANENT, Groq's 400 json_validate_failed
//          and 5xx as TRANSIENT, any other 4xx as REQUEST.
//       2. a 402 model is asked ONCE per call - the retry pass skips it - while a 429 model is still retried (transient
//          behaviour unchanged), and the NEXT call does not ask the 402 model at all (parked).
//       3. one model's JSON-validation 400 parks that MODEL, never its whole provider.
//       4. with every general model penalised once, the last-resort code models still come LAST (and the pre-v9 copy,
//          if given with --compare <old ai-chain.ts>, puts them first - the regression this guards).
//       5. a task profile's preferred models stay ahead of the rest under the herd-spread.
//       6. callAIMultimodal (the image path) fails over like callAI: a 402 vision model is parked and not asked on the
//          next photo, a 429 or a JSON 400 parks only that MODEL, a 401 skips the rest of that provider for the call, and
//          a last-resort vision entry is asked last. With --compare-vision <pre-v10 ai-chain.ts> it also proves the old
//          image path asked the 402 model again on every photo.
//   node tools/ai_chain_failover_probe.mjs --live <scenario> --budget-file <json>   ONE live scenario against the free
//       tiers with the keys in supabase/functions/.env. --budget-file is REQUIRED: every outbound request takes one unit
//       from that file's cap BEFORE it is sent (a 429 is a request), and a refused unit is never sent. Scenarios:
//         permanent  - a model name Groq does not serve is put at the head of a COPY of the chain; the call must classify
//                      Groq's 404 as permanent, park the slot, and be answered by the next entry.
//         groq-json  - the memory-distiller request that failed 400 json_validate_failed, routed to gpt-oss-20b first.
//         vision     - callAIMultimodal with a tiny generated PNG; the first vision entry should answer.
//         default    - one plain callAI in written order (the chain's head should answer).
//         first:<provider>[,<provider>...] - fault-inject the named providers (local-only hook) so the next
//                      provider's first entry is asked.
// Node directly, never npx (this repo's path contains an ampersand npx mis-parses).
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SHARED = path.join(ROOT, 'supabase', 'functions', '_shared');
const argv = process.argv.slice(2);
const argOf = (f) => { const i = argv.indexOf(f); return i >= 0 ? argv[i + 1] : undefined; };

function envKeys() {
  const out = {};
  for (const p of [path.join(ROOT, '.env'), path.join(ROOT, 'supabase', 'functions', '.env')]) {
    if (!fs.existsSync(p)) continue;
    for (const line of fs.readFileSync(p, 'utf8').split(/\r?\n/)) {
      const m = line.match(/^([A-Z0-9_]+)=(.*)$/);
      if (m && m[2].trim()) out[m[1]] = m[2].trim().replace(/^["']|["']$/g, '');
    }
  }
  return out;
}

let n = 0;
// A fresh copy per scenario: provider-health keeps its state in module scope, so a new directory = clean health.
async function load(chainSrc, env) {
  globalThis.Deno = { env: { get: (k) => env[k] } };
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), `aichain-${n++}-`));
  fs.writeFileSync(path.join(dir, 'provider-health.ts'), fs.readFileSync(path.join(SHARED, 'provider-health.ts')));
  fs.writeFileSync(path.join(dir, 'ai-chain.ts'), chainSrc);
  const chain = await import(pathToFileURL(path.join(dir, 'ai-chain.ts')).href);
  const health = await import(pathToFileURL(path.join(dir, 'provider-health.ts')).href);
  return { chain, health };
}

const quiet = () => { const w = console.warn, l = console.log; console.warn = () => {}; console.log = () => {}; return () => { console.warn = w; console.log = l; }; };
const results = [];
const A = (name, cond, detail = '') => { results.push({ name, pass: !!cond }); console.log(`  ${cond ? 'PASS' : 'FAIL'}  ${name}${detail ? '  - ' + detail : ''}`); };

function stubFetch(plan, calls) {
  // plan(model) -> {status, body}; calls records each model asked.
  return async (url, init) => {
    const body = JSON.parse(init.body);
    calls.push(body.model);
    const r = plan(body.model, body);
    return new Response(typeof r.body === 'string' ? r.body : JSON.stringify(r.body), { status: r.status, headers: { 'content-type': 'application/json' } });
  };
}
const ok = (text) => ({ status: 200, body: { choices: [{ message: { content: text }, finish_reason: 'stop' }], usage: { total_tokens: 5 } } });

async function offline() {
  const src = fs.readFileSync(path.join(SHARED, 'ai-chain.ts'), 'utf8');
  const allKeys = { GROQ_API_KEY: 'k', GEMINI_API_KEY: 'k', MISTRAL_API_KEY: 'k', OPENROUTER_API_KEY: 'k', SUPABASE_URL: 'http://127.0.0.1:54321' };
  const realRandom = Math.random;
  Math.random = () => 0.999999;           // identity shuffle + a fixed 1.2 s jitter: deterministic order
  const realFetch = globalThis.fetch;
  try {
    console.log('1. failure classes');
    {
      const { chain } = await load(src, allKeys);
      const c = (s, b) => { const f = chain.classifyProviderFailure(s, b); return `${f.kind}/${f.scope}`; };
      A('402 payment_required -> permanent/model', c(402, '{"code":"payment_required"}') === 'permanent/model');
      A('404 model gone -> permanent/model', c(404, '{"error":{"message":"This model is unavailable for free"}}') === 'permanent/model');
      A('401 key rejected -> permanent/provider', c(401, 'invalid api key') === 'permanent/provider');
      A('400 model_decommissioned -> permanent/model', c(400, '{"error":{"code":"model_decommissioned"}}') === 'permanent/model');
      A('400 json_validate_failed -> transient/model', c(400, '{"error":{"message":"Failed to validate JSON.","code":"json_validate_failed"}}') === 'transient/model');
      A('400 other (context too long) -> request/model', c(400, '{"error":{"message":"maximum context length exceeded"}}') === 'request/model');
      A('500 -> transient/provider (unchanged)', c(500, 'Internal') === 'transient/provider');
    }

    console.log('2. a permanent failure is asked once per call and not at all on the next call');
    {
      const head = '  { provider: "groq", baseUrl: "https://api.groq.com/openai/v1", model: "probe-paywalled-model", envKey: "GROQ_API_KEY" },\n';
      const injected = src.replace(/(const PROVIDER_CHAIN: ProviderEntry\[\] = \[\n)/, `$1${head}`);
      const { chain } = await load(injected, allKeys);
      const calls = [];
      globalThis.fetch = stubFetch((m) => (m === 'probe-paywalled-model' ? { status: 402, body: { code: 'payment_required' } } : { status: 429, body: {} }), calls);
      const restore = quiet();
      const out = await chain.callAI('q', { jsonMode: true });
      restore();
      const askedPermanent = calls.filter((m) => m === 'probe-paywalled-model').length;
      const askedTransient = calls.filter((m) => m === 'qwen/qwen3.8-27b').length;
      A('all-down call still degrades to "{}"', out === '{}');
      A('the 402 model was asked exactly once in a two-pass call', askedPermanent === 1, `asked ${askedPermanent}x`);
      A('a 429 model is still retried on the second pass (transient unchanged)', askedTransient === 2, `asked ${askedTransient}x`);
      calls.length = 0;
      globalThis.fetch = stubFetch((m) => (m === 'probe-paywalled-model' ? { status: 402, body: {} } : ok('{"a":1}')), calls);
      const restore2 = quiet();
      const out2 = await chain.callAI('q', { jsonMode: true });
      restore2();
      A('the next call does not ask the parked 402 model at all', !calls.includes('probe-paywalled-model') && out2 === '{"a":1}', `asked: ${calls.join(', ')}`);
    }

    console.log("3. one model's JSON 400 parks that model, not its provider");
    {
      const { chain, health } = await load(src, allKeys);
      const calls = [];
      globalThis.fetch = stubFetch((m) => (m === 'openai/gpt-oss-20b'
        ? { status: 400, body: { error: { message: 'Failed to validate JSON.', code: 'json_validate_failed', failed_generation: '' } } }
        : ok('{"ok":true}')), calls);
      const restore = quiet();
      const out = await chain.callAI('q', { jsonMode: true, taskProfile: 'intent_classification' });
      restore();
      const snap = health.getSlotHealthSnapshot();
      const gp = snap.groq ? snap.groq.penalty : 0;
      const mp = snap['groq:openai/gpt-oss-20b'] ? snap['groq:openai/gpt-oss-20b'].penalty : 0;
      A('the JSON 400 fell over to the next preferred model', calls[0] === 'openai/gpt-oss-20b' && out === '{"ok":true}', `asked: ${calls.join(', ')}`);
      A('it penalised the MODEL slot only, never the groq provider', gp === 0 && mp > 0, `groq ${gp}, groq:openai/gpt-oss-20b ${mp}`);
      calls.length = 0;
      const restore2 = quiet();
      await chain.callAI('q', { jsonMode: true });
      restore2();
      A('so groq qwen3.8-27b still answers the next call', calls[0] === 'qwen/qwen3.8-27b', `first asked: ${calls[0]}`);
    }

    console.log('4. last resorts stay last after every general model has failed once');
    const lastTwo = async (s) => {
      const { chain, health } = await load(s, allKeys);
      for (const p of ['groq', 'google', 'openrouter']) health.recordSlotFailure(p);
      health.recordSlotFailure('mistral:mistral-medium-latest');
      health.recordSlotFailure('mistral:mistral-small-latest');
      Math.random = realRandom;
      const firsts = new Set();
      for (let i = 0; i < 40; i++) firsts.add(chain.reorderChain(undefined, true)[0].model);
      const o = chain.reorderChain(undefined, true);
      Math.random = () => 0.999999;
      return { firsts, tail: o.slice(-2).map((e) => e.model) };
    };
    {
      const r = await lastTwo(src);
      A('codestral / laguna are the last two entries', r.tail.every((m) => /codestral|laguna/.test(m)), r.tail.join(', '));
      A('no last resort is ever first across 40 spread orders', ![...r.firsts].some((m) => /codestral|laguna/.test(m)), [...r.firsts].join(', '));
      const old = argOf('--compare');
      if (old) {
        const o = await lastTwo(fs.readFileSync(old, 'utf8'));
        A('(teeth) the pre-v9 chain DID put a last resort first under the same penalties', [...o.firsts].some((m) => /codestral|laguna/.test(m)), [...o.firsts].join(', '));
      }
    }

    console.log("5. a task profile's preferred models stay ahead under the spread");
    {
      const { chain } = await load(src, allKeys);
      Math.random = realRandom;
      let held = true;
      for (let i = 0; i < 40; i++) {
        const o = chain.reorderChain('intent_classification', true).slice(0, 2).map((e) => e.model).sort().join('|');
        if (o !== ['gemini-2.5-flash-lite', 'openai/gpt-oss-20b'].sort().join('|')) { held = false; break; }
      }
      Math.random = () => 0.999999;
      A('intent_classification keeps gpt-oss-20b + gemini-2.5-flash-lite as its first two in 40/40 spread orders', held);
      const code = chain.reorderChain('code_or_sql_generation', true)[0].model;
      A('code_or_sql_generation still puts codestral first (asked-for specialist)', code === 'codestral-latest', code);
    }

    console.log('6. the image path fails over like the text path');
    const IMG = 'data:image/png;base64,iVBORw0KGgo=';
    const visionRun = async (s, plan) => {
      const m = await load(s, allKeys);
      const calls = [];
      globalThis.fetch = stubFetch(plan, calls);
      const restore = quiet();
      const out = await m.chain.callAIMultimodal('What is in this photo?', IMG, { jsonMode: true });
      restore();
      return { ...m, calls, out };
    };
    {
      const plan = (mdl) => (mdl === 'qwen/qwen3.8-27b' ? { status: 402, body: { code: 'payment_required' } } : ok('{"thing":"pump"}'));
      const r = await visionRun(src, plan);
      A('a 402 vision model fails over to the next vision entry', r.calls[0] === 'qwen/qwen3.8-27b' && r.calls[1] === 'gemini-2.5-flash' && r.out === '{"thing":"pump"}', `asked: ${r.calls.join(', ')}`);
      A('...and is parked (provider-health, same state as the text path)', r.health.isSlotBlocked('groq:qwen/qwen3.8-27b') && !r.health.isSlotBlocked('groq'));
      const calls2 = [];
      globalThis.fetch = stubFetch(plan, calls2);
      const restore = quiet();
      await r.chain.callAIMultimodal('again', IMG, { jsonMode: true });
      restore();
      A('the next photo does not ask the parked model at all', !calls2.includes('qwen/qwen3.8-27b'), `asked: ${calls2.join(', ')}`);
      const old = argOf('--compare-vision');
      if (old) {
        const o = await visionRun(fs.readFileSync(old, 'utf8'), plan);
        const calls3 = [];
        globalThis.fetch = stubFetch(plan, calls3);
        const restore3 = quiet();
        await o.chain.callAIMultimodal('again', IMG, { jsonMode: true });
        restore3();
        A('(teeth) the pre-v10 image path DID ask the 402 model again on the next photo', calls3.includes('qwen/qwen3.8-27b'), `asked: ${calls3.join(', ')}`);
      }
    }
    {
      const plan = (mdl) => (mdl === 'qwen/qwen3.8-27b' ? { status: 429, body: {} }
        : mdl === 'gemini-2.5-flash' ? { status: 400, body: { error: { message: 'Failed to validate JSON.', code: 'json_validate_failed' } } }
        : ok('{"thing":"valve"}'));
      const r = await visionRun(src, plan);
      const snap = r.health.getSlotHealthSnapshot();
      const pen = (k) => (snap[k] ? snap[k].penalty : 0);
      A('a 429 and a JSON 400 penalise only their MODEL slots, never the providers', pen('groq') === 0 && pen('google') === 0 && pen('groq:qwen/qwen3.8-27b') > 0 && pen('google:gemini-2.5-flash') > 0,
        `groq ${pen('groq')}, google ${pen('google')}, models ${pen('groq:qwen/qwen3.8-27b')}/${pen('google:gemini-2.5-flash')}`);
      A('...and the next vision entry answers', r.out === '{"thing":"valve"}' && r.calls[2] === 'gemini-2.5-flash-lite', `asked: ${r.calls.join(', ')}`);
    }
    {
      const plan = (mdl) => (mdl === 'qwen/qwen3.8-27b' ? { status: 429, body: {} }
        : mdl === 'gemini-2.5-flash' ? { status: 401, body: { error: { message: 'API key not valid' } } }
        : ok('{"thing":"motor"}'));
      const r = await visionRun(src, plan);
      A('a 401 (key rejected) skips the rest of that provider for the call', !r.calls.includes('gemini-2.5-flash-lite') && r.health.isSlotBlocked('google'), `asked: ${r.calls.join(', ')}`);
    }
    {
      const fake = '  { provider: "openrouter", baseUrl: "https://openrouter.ai/api/v1", model: "probe/code-vision:free", envKey: "OPENROUTER_API_KEY", vision: true, lastResort: true },\n';
      const injected = src.replace(/(const PROVIDER_CHAIN: ProviderEntry\[\] = \[\n)/, `$1${fake}`);
      const r = await visionRun(injected, () => ({ status: 429, body: {} }));
      A('a last-resort vision entry is asked last even when it is written first', r.calls[r.calls.length - 1] === 'probe/code-vision:free' && r.out === '{}', `asked: ${r.calls.join(', ')}`);
    }
  } finally {
    Math.random = realRandom;
    globalThis.fetch = realFetch;
  }
  const failed = results.filter((r) => !r.pass).length;
  console.log(`\noffline: ${results.length - failed}/${results.length} PASS, 0 network calls`);
  return failed ? 1 : 0;
}

const DISTILL_SYS = 'You distill durable maintenance memory. Be conservative — return empty arrays unless a concrete fact, spec, or commitment is present.';
const DISTILL = 'From this maintenance exchange, extract ONLY genuinely durable facts worth remembering long-term and any explicit follow-up the worker implied. If nothing is durable, return empty arrays.\nRespond JSON only: {"memories":[{"memory_type":"factual","content":"...","importance":0.7}],"followups":[{"topic":"...","detail":"...","due_in_days":7}]}\n\nWorker: Replaced the drive-end bearing on pump P-101 today; vibration is now 2.1 mm/s. I will recheck alignment next week.\nAssistant: Good. 2.1 mm/s is within ISO 10816 zone A for that class. Log the bearing change and schedule the alignment check.';
const SHORT = 'Name one common cause of centrifugal pump cavitation. Respond JSON only: {"cause":"..."}';

// The session's hard ceiling on live requests (same file format as tools/lib/chain_pacer.LiveCallBudget):
// a unit is taken BEFORE a request is sent, and a refused unit is never sent.
function takeBudget(file, label) {
  let st = { used: 0, log: [] };
  try { st = JSON.parse(fs.readFileSync(file, 'utf8')); } catch { /* a missing ledger has cap 0: nothing is sent */ }
  const cap = Number(st.cap || 0), used = Number(st.used || 0);
  if (used >= cap) { console.log(`  BUDGET: refused '${label}' - ${used}/${cap} live calls already spent; nothing sent`); return false; }
  st.used = used + 1;
  (st.log = st.log || []).push({ n: used + 1, label, at: new Date().toTimeString().slice(0, 8) });
  fs.writeFileSync(file + '.tmp-write', JSON.stringify(st, null, 1));
  fs.renameSync(file + '.tmp-write', file);
  return true;
}

// 32x32, not smaller: Groq refuses an image under 32 px a side ("Image must have at least 32 pixels in each
// dimension", 400 - measured 2026-10-08 with an 8x8 that cost a live call and proved only the request-class path).
const PNG_RED_32 = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAAKklEQVR42mO4oKBAU8QwasGoBaMWjFowasGoBaMWjFowasGoBaMWDBULAE7YQD2B7wk2AAAAAElFTkSuQmCC';

async function live(scenario) {
  const budgetFile = argOf('--budget-file');
  if (!budgetFile) { console.log('  --live needs --budget-file <json>: no live request is sent without a ceiling'); return 2; }
  const env = { ...envKeys(), SUPABASE_URL: 'http://127.0.0.1:54321' };
  let src = fs.readFileSync(path.join(SHARED, 'ai-chain.ts'), 'utf8');
  if (scenario === 'permanent') {
    src = src.replace(/(const PROVIDER_CHAIN: ProviderEntry\[\] = \[\n)/,
      '$1  { provider: "groq", baseUrl: "https://api.groq.com/openai/v1", model: "workhive-retired-model-probe", envKey: "GROQ_API_KEY" },\n');
  }
  Math.random = () => 0.999999;   // keep the written order, so "first entry" means the first entry
  const { chain, health } = await load(src, env);
  const realFetch = globalThis.fetch;
  const log = [];
  globalThis.fetch = async (url, init) => {
    const model = JSON.parse(init.body).model;
    if (!takeBudget(budgetFile, `probe ${scenario} ${model}`)) throw new Error('live-call budget spent - request not sent');
    const t0 = Date.now();
    const res = await realFetch(url, init);
    log.push({ host: new URL(url).host, model, status: res.status, ms: Date.now() - t0 });
    return res;
  };
  const served = [];
  const opts = { jsonMode: true, maxTokens: 256, onServed: (m) => served.push(m) };
  let out;
  const t0 = Date.now();
  if (scenario === 'permanent') out = await chain.callAI(SHORT, opts);
  else if (scenario === 'groq-json') out = await chain.callAI(DISTILL, { ...opts, systemPrompt: DISTILL_SYS, maxTokens: 320, temperature: 0.1, taskProfile: 'intent_classification' });
  else if (scenario.startsWith('first:')) out = await chain.callAI(SHORT, { ...opts, faultInject: { fail: scenario.slice(6).split(','), mode: '429' } });
  else if (scenario === 'default') out = await chain.callAI(SHORT, opts);
  else if (scenario === 'vision') {
    const t = Date.now();
    out = await chain.callAIMultimodal('What single colour fills this image? Respond JSON only: {"colour":"..."}', PNG_RED_32, { jsonMode: true, maxTokens: 128 });
    served.push({ providerName: '(see the served-by line)', modelName: '', depth: 0, pass: 1, ms: Date.now() - t });
  }
  else throw new Error('unknown scenario ' + scenario);
  globalThis.fetch = realFetch;
  for (const r of log) console.log(`  -> ${r.host.padEnd(36)} ${String(r.model).padEnd(40)} HTTP ${r.status}  ${r.ms} ms`);
  console.log(`  served by: ${served.length ? `${served[0].providerName} / ${served[0].modelName} (depth ${served[0].depth}, pass ${served[0].pass})` : 'NONE'} in ${Date.now() - t0} ms`);
  console.log(`  answer: ${String(out).slice(0, 220)}`);
  let parsed = null; try { parsed = JSON.parse(out); } catch { /* reported below */ }
  console.log(`  answer is JSON: ${parsed !== null && out !== '{}'}`);
  if (scenario === 'permanent') {
    const slot = 'groq:workhive-retired-model-probe';
    const snap = health.getSlotHealthSnapshot()[slot];
    const hrs = snap ? ((snap.blocked_until - Date.now()) / 3.6e6).toFixed(2) : 'n/a';
    console.log(`  ${slot} parked: ${health.isSlotBlocked(slot)} (for ${hrs} h); groq provider parked: ${health.isSlotBlocked('groq')}; probe model asked ${log.filter((r) => r.model === 'workhive-retired-model-probe').length}x`);
  }
  console.log(`  LIVE CALLS THIS SCENARIO: ${log.length}`);
  return 0;
}

const liveArg = argOf('--live');
process.exitCode = liveArg ? await live(liveArg) : await offline();
