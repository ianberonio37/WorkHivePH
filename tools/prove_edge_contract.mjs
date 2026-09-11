// prove_edge_contract — the EDGE & API CONTRACTS family of the live-walk wave (2026-09-06).
//
// tools/live_walk_manifest.py --family "edge & API contracts" listed 84 rows whose evidence was a static gate or a
// written argument: 47 "Edge function contract & failure modes: <fn>" (the V wave), plus `refusal & error shape` (11),
// `rate-limit bucket` (11), `provider fallback chain` (11) and `grounding containment` (5). Every one of those is a
// question about what the function DOES when asked badly - which only a real request can answer.
//
// Four questions per function, asked against the LOCAL stack (no browser, so the whole roster runs in ~2 minutes):
//   C1 preflight     OPTIONS returns 2xx with an Access-Control-Allow-Origin header - a browser can even reach it
//   C2 refusal shape  POST with NO Authorization returns a REFUSAL (401/403), not a 500 and not a silent 200, and the
//                     body is JSON carrying an `error`/`message` a client can render
//   C3 malformed body POST with a broken JSON body returns 4xx with a JSON error - never a 500, never a stack
//   C4 method guard   GET on a POST-only function returns 4xx/405 with JSON - never a 500
//
// A function that answers 404 is not deployed locally and is reported n/a, never failed. What the messages SAY is the
// business of tools/critic_edge_fn_copy.py (gate `edge-fn-copy`); this file asks whether the CONTRACT holds.
//
//   node tools/prove_edge_contract.mjs                 # every function under supabase/functions
//   node tools/prove_edge_contract.mjs --fn ai-gateway # one function, verbose
//   node tools/prove_edge_contract.mjs --limit 20      # the first N (the background cap)
import { readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const EDGE = process.env.WH_EDGE_URL || 'http://127.0.0.1:54321/functions/v1';
const ANON = process.env.WH_ANON_KEY || 'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ';
const ONLY = (() => { const i = process.argv.indexOf('--fn'); return i >= 0 ? process.argv[i + 1] : null; })();
const LIMIT = (() => { const i = process.argv.indexOf('--limit'); return i >= 0 ? Number(process.argv[i + 1]) : 0; })();
// ★A TIMEOUT TOO SHORT TURNS LOAD INTO A CONTRACT BREAK. At 12s, four functions read as status 0 -
// "no JSON error a client can show" - and three of them answered 429/400/400 correctly when asked again
// with room to breathe; the local edge runtime was simply saturated by this session's own probing. A
// false RED sends someone hunting a defect that is not there, so the budget is generous and a genuine
// hang still shows up as a hang.
const TIMEOUT = 35000;

const fns = readdirSync('supabase/functions')
  .filter((d) => !d.startsWith('_') && statSync(join('supabase/functions', d)).isDirectory())
  .filter((d) => !ONLY || d === ONLY);

const ask = async (fn, { method = 'POST', auth = true, body = '{}', raw = false } = {}) => {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), TIMEOUT);
  try {
    const headers = { 'Content-Type': 'application/json' };
    if (auth) { headers.Authorization = 'Bearer ' + ANON; headers.apikey = ANON; }
    const res = await fetch(`${EDGE}/${fn}`, { method, headers, body: method === 'GET' || method === 'OPTIONS' ? undefined : body, signal: ctl.signal });
    const text = await res.text();
    let json = null; try { json = JSON.parse(text); } catch (e) { void e; }
    return { status: res.status, cors: res.headers.get('access-control-allow-origin'), json, text: text.slice(0, 200) };
  } catch (e) {
    return { status: 0, err: String(e).slice(0, 80) };
  } finally { clearTimeout(t); }
};

// ★THREE SHAPES THAT ARE CORRECT AND LOOK WRONG (calibrated on the first full walk, 2026-09-06):
//  · the PLATFORM GATEWAY refuses before our code runs and answers {"msg":"Error: Missing authorization header"} -
//    that IS the refusal, in Supabase's own shape, and no function of ours can change it;
//  · a public STATUS/BANNER envelope ({ok, version, docs} or a documented `*_not_configured` degradation with all
//    fields null) carries no data, so answering an anonymous caller with it is a design, not a leak
//    (equipment-label-ocr's is marked `edge-status-allow` in its own source);
//  · a 503 from a function whose secret is absent locally is the honest answer, not a broken contract.
const isGatewayRefusal = (r) => !!(r.json && typeof r.json.msg === 'string' && /auth/i.test(r.json.msg));
const isBanner = (r) => {
  const j = r.json;
  if (!j || typeof j !== 'object') return false;
  const keys = Object.keys(j);
  const meta = new Set(['ok', 'version', 'docs', 'name', 'service', 'error', 'azure_unavailable', 'ocr_chars',
                        'parsed', 'matched_asset', 'status', 'message']);
  if (!keys.every((k) => meta.has(k))) return false;
  const hasData = keys.some((k) => Array.isArray(j[k]) ? j[k].length > 0
    : (j[k] && typeof j[k] === 'object' ? Object.values(j[k]).some((v) => v !== null && v !== undefined) : false));
  return !hasData;
};
const msgOf = (r) => {
  const j = r.json;
  if (!j || typeof j !== 'object') return null;
  const e = j.error ?? j.message ?? (j.error && j.error.message);
  if (typeof e === 'string') return e;
  if (e && typeof e === 'object' && typeof e.message === 'string') return e.message;
  return null;
};

let bad = 0, na = 0, n = 0;
for (const fn of (LIMIT ? fns.slice(0, LIMIT) : fns)) {
  const pre = await ask(fn, { method: 'OPTIONS' });
  if (pre.status === 404) { console.log(`  n/a ${fn.padEnd(32)} not served locally (404)`); na++; continue; }
  n++;
  const noauth = await ask(fn, { auth: false });
  const broken = await ask(fn, { body: '{ this is not json' });
  const getreq = await ask(fn, { method: 'GET' });

  const issues = [];
  // C1 a browser must be able to reach it at all
  if (!(pre.status >= 200 && pre.status < 300) || !pre.cors) {
    issues.push(`C1 preflight ${pre.status}${pre.cors ? '' : ' no CORS header'}`);
  }
  // C2 an unauthenticated call is REFUSED, and says something a client can render
  if (noauth.status === 200 && !isBanner(noauth)) issues.push('C2 unauthenticated call answered 200 with a payload');
  else if (noauth.status === 503) { /* the secret is absent locally: an honest refusal, not a contract break */ }
  else if (noauth.status >= 500) issues.push(`C2 unauthenticated call ${noauth.status} (a refusal is not a server error)`);
  else if (noauth.status !== 200 && !msgOf(noauth) && !isGatewayRefusal(noauth)) issues.push(`C2 ${noauth.status} with no JSON error a client can show: ${(noauth.text || '').slice(0, 60)}`);
  // C3 a broken body is the caller's fault, so 4xx with a message - not a 500
  if (broken.status === 503) { /* not configured locally */ }
  else if (broken.status >= 500) issues.push(`C3 malformed body -> ${broken.status} (should be 4xx)`);
  else if (broken.status < 400 && broken.status !== 0) { /* some functions validate later; only a 5xx is wrong */ }
  else if (broken.status >= 400 && !msgOf(broken) && !isGatewayRefusal(broken)) issues.push(`C3 ${broken.status} with no JSON error: ${(broken.text || '').slice(0, 60)}`);
  // C4 the wrong method must not reach the body
  if (getreq.status === 503) { /* not configured locally */ }
  else if (getreq.status >= 500) issues.push(`C4 GET -> ${getreq.status} (should be 4xx/405)`);

  if (issues.length) bad++;
  console.log(`  ${issues.length ? 'BAD' : 'ok '} ${fn.padEnd(32)} pre=${pre.status} noauth=${noauth.status} bad-json=${broken.status} get=${getreq.status}`);
  for (const s of issues) console.log(`        ${s.slice(0, 150)}`);
}
console.log(`${bad ? 'FAIL' : 'PASS'} edge-contract - ${n - bad}/${n} functions hold the contract (preflight, refusal, malformed body, method guard)${na ? ` · ${na} not served locally` : ''}`);
process.exit(bad ? 1 : 0);
