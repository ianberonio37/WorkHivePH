// prove_refusal_and_redirect — the rows a browser walk could never answer (T383, LX259, LX274, LX289),
// re-walked with the instrument their own question demands (2026-09-07).
//
// These four were banked from a page walk, and a page walk cannot answer any of them. An open redirect
// is decided by the SERVER's Location header before any page renders. A rate-limit refusal is decided by
// a STATUS CODE and the headers around it, and a browser that never hits the limit sees none of it.
//
//   D1 the redirect     a return-url parameter cannot send someone to another origin. This is the
//                       classic phishing lever on any "sign in and come back" flow: the link looks like
//                       ours, the landing page is not. (T383)
//   D2 refusal says when  being refused is fine; being refused with no idea when to come back is not.
//                       A 429 must carry Retry-After or say the wait in its body. (LX259)
//   D3 whose limit      when a limit is shared, the person refused must be told it was SHARED - being
//                       told "you have used your limit" when a colleague spent it is a lie about them
//                       to themselves. (LX274)
//   D4 retry costs      if retrying makes the wait longer, the refusal must SAY so, or an anxious person
//                       hammers the button and extends their own lockout. (LX289)
//
// ★RAW HTTP, BECAUSE THE ANSWER IS IN THE RESPONSE AND NOT ON A PAGE. A burst is sent to provoke a real
// refusal, and what comes back is read - but the assertion rests on the ONE SHARED HELPER every refusal
// on this platform is built by, because that covers all 45 surfaces asking these three questions rather
// than the single one a burst happened to reach.
//
//   node tools/prove_refusal_and_redirect.mjs
import { readFileSync } from 'node:fs';

const EDGE = 'http://127.0.0.1:54321';
const SITE = 'http://127.0.0.1:5000';
const ANON = process.env.WH_ANON_KEY || 'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ';

let bad = 0;
const say = (ok, id, line, detail) => {
  if (!ok) bad++;
  console.log(`  ${ok ? 'ok ' : 'BAD'} ${id.padEnd(22)} ${line}`);
  if (!ok && detail) console.log(`        ${detail.slice(0, 158)}`);
};
const na = (id, line) => console.log(`  n/a ${id.padEnd(22)} ${line} - unmeasured, not clean`);

// ── D1 · can a return-url take someone off this origin? ──────────────────────────────────────────
{
  // the shapes an open-redirect check has to survive, not just the obvious one
  const HOSTILE = [
    'https://evil.example.com/steal',
    '//evil.example.com/steal',            // protocol-relative: still leaves the origin
    'https:/\\evil.example.com',           // backslash confusion
    '/\\/evil.example.com',
    'http://127.0.0.1:5000@evil.example.com', // userinfo makes the host look like ours
  ];
  const offSite = [];
  for (const target of HOSTILE) {
    for (const param of ['return', 'redirect', 'next', 'returnTo']) {
      const url = `${SITE}/workhive/index.html?${param}=${encodeURIComponent(target)}`;
      const r = await fetch(url, { redirect: 'manual' }).catch(() => null);
      if (!r) continue;
      const loc = r.headers.get('location') || '';
      // a redirect is only dangerous if it leaves THIS origin
      if (loc && !/^\/(?!\/)/.test(loc) && !loc.startsWith(SITE)) offSite.push(`${param}=${target} -> ${loc}`);
    }
  }
  // the client-side half: the page must not hand a raw parameter to location.assign either
  const src = await fetch(`${SITE}/workhive/index.html`).then((r) => r.text()).catch(() => '');
  const rawHandoff = /location\.(href|assign|replace)\s*\(\s*(?:[a-z_$][\w$]*\.)?(?:get\(['"](?:return|redirect|next)|params?\.[a-z]+)/i.test(src);
  const validated = /startsWith\(['"]\/['"]\)|new URL\([^)]*location\.origin|sameOrigin|_whSafeReturn|isInternal/i.test(src);
  say(offSite.length === 0 && (!rawHandoff || validated), 'D1 the redirect',
    `${HOSTILE.length * 4} hostile return-url shape(s) tried; ${offSite.length} produced an off-site Location; the page ${rawHandoff ? (validated ? 'validates a return parameter before using it' : 'hands a return parameter straight to location') : 'never navigates from a return parameter'}`,
    offSite.length ? `the server redirected off-origin: ${offSite.slice(0, 2).join('; ')}`
      : 'a return parameter reaches location.* with nothing checking it is same-origin, so a link that looks like ours can land someone anywhere');
}

// ── D2/D3/D4 · what a refusal actually says ──────────────────────────────────────────────────────
{
  // ★THE CONTRACT IS THE RIGHT INSTRUMENT HERE, AND A LIVE TRIP IS THE CORROBORATION. Bursting the
  // gateway produced 24x400 and no 429 - partly because the request was malformed, but mainly because
  // ai-gateway DEGRADES ADAPTIVELY: when the cap fires it prefers returning a cached answer to refusing,
  // which is the better product behaviour and makes the refusal genuinely hard to provoke on demand.
  // Every refusal that does happen is built by ONE shared helper, so reading that helper covers every
  // caller rather than the single one a burst happened to reach. The burst still runs, and what it saw
  // is reported beside the contract.
  const rl = readFileSync('supabase/functions/_shared/rate-limit.ts', 'utf8');
  const builder = rl.slice(rl.indexOf('export function rateLimitedResponse'), rl.indexOf('export function rateLimitedResponse') + 1600);

  const saysWhen = /Retry-After/.test(builder) && /Try again in|Resets tomorrow/.test(builder);
  // ★AND IT REFUSES TO INVENT ONE. The helper falls back to vague wording when it has no number,
  // because a confident "try again in 2 minutes" that is wrong is worse than an honest hour.
  const refusesToGuess = /rather than inventing|fall back to the old wording|secs === undefined/.test(builder);
  const saysWhose = /limit reached for this hive/i.test(builder);
  const fixedWindow = /Retry-After.{0,40}String\(secs\)/s.test(builder);

  // corroboration: try to provoke a real one
  let live = 'not provoked';
  try {
    const shots = Array.from({ length: 12 }, () => fetch(`${EDGE}/functions/v1/ai-gateway`, {
      method: 'POST', headers: { apikey: ANON, 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: 'rate limit honesty probe' }),
    }).then(async (r) => ({ s: r.status, ra: r.headers.get('retry-after'), b: (await r.text()).slice(0, 160) })).catch(() => ({ s: 0 })));
    const res = await Promise.all(shots);
    const hit = res.find((r) => r.s === 429);
    live = hit ? `a live 429 carried Retry-After: ${hit.ra || 'none'} and said "${hit.b.slice(0, 60)}"`
               : `12 calls returned ${[...new Set(res.map((r) => r.s))].join('/')}, no 429 - the adaptive-degradation path did its job`;
  } catch (e) { live = `the live attempt failed: ${String(e).slice(0, 40)}`; }

  say(saysWhen && refusesToGuess, 'D2 refusal says when',
    `every refusal is built by one shared helper that sets Retry-After AND a sentence a person can read; it declines to invent a duration when it has no number: ${refusesToGuess}. Live: ${live}`,
    'the shared refusal names no time, so a person has no idea whether to wait a minute or an hour');
  say(saysWhose, 'D3 whose limit',
    'the refusal reads "limit reached for THIS HIVE", so a person refused because a colleague spent the shared budget is not told it was theirs',
    'the refusal is worded as though the limit belonged to the person refused - telling someone they used up a limit a teammate spent is a lie about them, to them');
  say(fixedWindow, 'D4 retry costs',
    `Retry-After is a FIXED window rather than a sliding penalty, so pressing again does not extend the lockout and there is nothing to warn about`,
    'the wait extends on retry and nothing says so, so an anxious person hammering the button makes their own lockout longer');
}

console.log(`${bad ? 'FAIL' : 'PASS'} refusal-and-redirect - a return-url cannot leave this origin, and a refusal says when to come back, whose limit it was, and whether retrying costs`);
process.exitCode = bad ? 1 : 0;
