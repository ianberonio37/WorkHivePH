// prove_refusal_kindness — the RATE LIMITING layer of the LAYER-UX wave (§LX, 2026-09-06).
// Three lenses, one burst, no browser - so this layer walks in seconds.
//
// Being refused is not the defect. Being refused BADLY is: a person who is told "no" and nothing else
// cannot tell whether to wait a minute, wait an hour, or stop trying; cannot tell whether it is them or
// their whole hive; and, told nothing, will hammer the button and often make it worse.
//
//   K1 says WHEN     a 429 carries a wait a person can act on - a retry-after, or a sentence with a
//                    duration in it. "Try again later" is not a wait, it is a shrug.
//   K2 says WHOSE    the refusal names its scope, so a person knows whether they spent the limit or
//                    someone else in their hive did. Being stopped by a colleague's usage with no way
//                    to know that is the worst version of this.
//   K3 no worse      retrying during the window does not lengthen it. A limiter that counts refused
//                    attempts punishes the person for the only feedback loop they were given.
//
// ★A FUNCTION THAT IS NOT RATE-LIMITED IS NOT A FAILURE HERE. Only the surfaces that SPEND something
// are in scope, and one that answers 200 to a burst is reported as unlimited rather than graded, so
// this gate can never read as green because nothing was actually asked.
//
//   node tools/prove_refusal_kindness.mjs
import { readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const EDGE = process.env.WH_EDGE_URL || 'http://127.0.0.1:54321/functions/v1';
const ANON = process.env.WH_ANON_KEY || 'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ';
const BURST = 8;

// the AI/compute functions a person spends a limit on
const SPENDERS = readdirSync('supabase/functions')
  .filter((d) => !d.startsWith('_') && statSync(join('supabase/functions', d)).isDirectory())
  .filter((d) => /ai-|voice-|rag|llm|assist|orchestrator|agent|semantic|embed|ocr|extract|polish|eval|gateway|brain|summar|analyz/.test(d))
  .slice(0, 14);

// ★AN ANONYMOUS BURST NEVER REACHES THE LIMITER. The first run fired 8 calls at 14 spending functions
// and got ZERO refusals - a green line over a question nobody asked - because the gateway turns an
// unauthenticated caller away before any quota is consulted. A rate limit is keyed to a PERSON, so the
// probe has to be one.
const TOKEN = await (async () => {
  try {
    const r = await fetch('http://127.0.0.1:54321/auth/v1/token?grant_type=password', {
      method: 'POST', headers: { apikey: ANON, 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'leandromarquez@auth.workhiveph.com', password: 'test1234' }),
    });
    const j = await r.json();
    return j.access_token || null;
  } catch (e) { void e; return null; }
})();
if (!TOKEN) console.log('  note could not mint a user token - the burst runs anonymously and will not reach the limiter');

const ask = async (fn) => {
  try {
    const r = await fetch(`${EDGE}/${fn}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', apikey: ANON, Authorization: 'Bearer ' + (TOKEN || ANON) },
      body: JSON.stringify({}),   // an empty body reaches the limiter; a shaped one is rejected by validation first
    });
    const text = await r.text();
    let j = null; try { j = JSON.parse(text); } catch (e) { void e; }
    return { status: r.status, retryAfterHeader: r.headers.get('retry-after'), j, text: text.slice(0, 300) };
  } catch (e) { return { status: 0, err: String(e).slice(0, 60) }; }
};

const WHEN = /(\d+\s*(second|minute|hour|min|sec|hr)s?|in about \d+|retry[_-]?after)/i;
const WHOSE = /\b(scope|hive|solo|your account|your team|shared|per[- ]user|everyone)\b/i;

let limited = 0, unlimited = 0, bad = 0;
const unlimitedDetail = [], unreached = [];
for (const fn of SPENDERS) {
  let refusal = null, lastStatus = '-';
  for (let i = 0; i < BURST && !refusal; i++) {
    const r = await ask(fn);
    lastStatus = r.status || r.err || '-';
    if (r.status === 429) refusal = r;
    if (r.status === 0 || r.status === 404) break;
  }
  if (!refusal) {
    const n = Number(lastStatus);
    if (n >= 200 && n < 300) { unlimited++; unlimitedDetail.push(`${fn} (answered ${n}, no limit hit)`); }
    else { unreached.push(`${fn} (${lastStatus} - validation refused the probe before any quota was consulted)`); }
    continue;
  }
  limited++;
  const body = (refusal.j ? JSON.stringify(refusal.j) : refusal.text) || '';
  const issues = [];
  const hasWhen = !!refusal.retryAfterHeader
    || (refusal.j && (refusal.j.retryAfter || refusal.j.retry_after))
    || WHEN.test(body);
  if (!hasWhen) issues.push('K1 refused with no wait a person can act on - no retry-after, no duration in the message');
  if (!WHOSE.test(body)) issues.push('K2 the refusal does not say whose limit was spent - a person stopped by a colleague cannot tell');

  // K3 · does retrying during the window lengthen it?
  const first = Number((refusal.j && (refusal.j.retryAfter || refusal.j.retry_after)) || refusal.retryAfterHeader || 0);
  let second = first;
  if (first) {
    await new Promise((r) => setTimeout(r, 1200));
    const again = await ask(fn);
    second = Number((again.j && (again.j.retryAfter || again.j.retry_after)) || again.retryAfterHeader || 0);
    // a window that is COUNTING DOWN is correct; one that grew punishes the retry
    if (second > first + 5) issues.push(`K3 retrying lengthened the wait ${first}s -> ${second}s - the person is punished for the only feedback they were given`);
  }

  if (issues.length) bad++;
  console.log(`  ${issues.length ? 'BAD' : 'ok '} ${fn.padEnd(28)} 429 · wait ${first || '(none)'}s${first && second !== first ? ` -> ${second}s` : ''} · ${(refusal.j && (refusal.j.error || refusal.j.message) || '').slice(0, 58)}`);
  for (const s of issues) console.log(`        ${s.slice(0, 155)}`);
}

console.log(`  note ${unlimited} function(s) took the burst without a limit: ${unlimitedDetail.slice(0, 5).join(', ') || '(none)'}`);
if (unreached.length) console.log(`  note ${unreached.length} function(s) NOT REACHED by this probe: ${unreached.slice(0, 4).join(', ')}`);
console.log(`${bad ? 'FAIL' : 'PASS'} refusal-kindness - ${limited - bad}/${limited} refusals tell a person WHEN they may return and WHOSE limit was spent, and do not lengthen the wait for retrying`);
// a walk that reached nothing has proven nothing, and must not read as a pass
if (limited === 0 && unlimited === 0) {
  console.log('  BAD  the burst reached no limiter at all - every spending function refused the probe body first, so this lens is UNMEASURED');
  bad++;
}
process.exitCode = bad ? 1 : 0;
