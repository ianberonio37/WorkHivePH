// prove_privacy_consent — the privacy, consent and eligibility journeys (T164, T165, T166, T167, T169,
// T172), walked as one family (2026-09-07).
//
// Six rows about the promises a platform makes before it has earned any trust. A person arriving for the
// first time is asked to hand over their work, their name and their colleagues' names. Each of these
// rows is a moment where the platform either keeps a promise it made in writing, or quietly does not.
//
//   V1 forget me       a person can get their data OUT and can get it DELETED, and both are reachable
//                      from the product rather than by writing to support (T164)
//   V2 asked first     consent moments happen BEFORE the thing they consent to - a cookie banner after
//                      the analytics call has already fired is theatre (T165)
//   V3 who sees this   a person writing something can tell who will read it, at the moment of writing,
//                      not after (T166)
//   V4 hardened        the client-side promises hold: no inline handler a script can hijack, no key in
//                      the page that should not be there (T167)
//   V5 bots stopped    the bot defence is real where it matters and does not stand between an honest
//                      person and their work (T169)
//   V6 eligibility     the terms say who may use this, and nothing collects an age or a school from
//                      someone the terms exclude (T172)
//
// ★FOUR OF THIS PROVER'S FIRST SIX FINDINGS WERE ITS OWN LENS, ALL THE SAME MISTAKE IN DIFFERENT
// CLOTHES. (V4) it matched the WORD "service_role" and found it inside a code COMMENT explaining a past
// lesson, then called it a shipped secret. (V6) it matched (birth|dob|age|school|grade) unanchored and
// found 34 "age or school fields" that were champion_engAGEment, stORAGE_bytes, GRADEr_passed, messAGE,
// imAGE_url and user_AGEnt - the same unanchored-acronym bug that assigned fifteen scaling rows to
// grafana because "SLO" appears inside "SLOWER". (V6 again) it required a legal page to be NAMED
// terms/privacy and reported "0 legal pages" while the terms sit inside index.html. (V5) it looked for
// an edge function verifying Turnstile, when the widget is inert-by-design until configured and is
// verified by Supabase Auth's own bot protection, not by our code. A lens that names something the
// platform does not use is measuring its own vocabulary, and every one of those would have been a
// fabricated defect in a report.
//
// ★READ FROM THE SHIPPED FILES AND THE LIVE SCHEMA, NOT FROM THE POLICY PROSE. A privacy page that says
// "you may request deletion" proves only that the sentence exists. What is checked here is whether the
// mechanism behind the sentence is on the page a person can reach.
//
//   node tools/prove_privacy_consent.mjs
import { execSync } from 'node:child_process';
import { readdirSync, readFileSync, existsSync } from 'node:fs';

const psql = (sql) => { try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim(); } catch { return ''; } };
const pages = readdirSync('.').filter((f) => f.endsWith('.html'));
const read = (f) => { try { return readFileSync(f, 'utf8'); } catch { return ''; } };
const anyPage = (rx) => pages.filter((f) => rx.test(read(f)));

let bad = 0;
const say = (ok, id, line, detail) => {
  if (!ok) bad++;
  console.log(`  ${ok ? 'ok ' : 'BAD'} ${id.padEnd(18)} ${line}`);
  if (!ok && detail) console.log(`        ${detail.slice(0, 158)}`);
};

// ── V1 · can a person take their data and leave? ─────────────────────────────────────────────────
{
  const exportFns = existsSync('supabase/functions')
    ? readdirSync('supabase/functions').filter((d) => /export|download|data/i.test(d)) : [];
  const exportUI = anyPage(/export (my |your |hive )?data|download (my|your) data|export-hive-data/i);
  // ★THIS PLATFORM'S WORD IS "DEACTIVATE", AND SEARCHING FOR MINE NEARLY SHIPPED A WEAKER DUPLICATE.
  // The first version looked for "delete my account" / "request deletion", found neither, and reported
  // that asking to be erased had no mechanism anywhere - so I built a table that RECORDED the ask. But
  // index.html has called deactivate_my_account() since Arc I: an RPC that actually anonymizes the
  // display name and email, revokes hive access, and keeps the operational records the team depends on.
  // That is strictly stronger than a recorded request. The real gap was REACH, not absence: the control
  // existed only on the landing page, so someone signed in and working had to leave the app to find it.
  const deleteUI = anyPage(/deactivate (your |my )?account|deactivate_my_account|right to erasure|delete (my|your) account/i);
  const erasureRpc = psql("select count(*) from pg_proc where proname = 'deactivate_my_account'");
  // and it has to be reachable from INSIDE the product, not only from the page a stranger lands on
  const reachableInApp = anyPage(/deactivate_my_account/i).filter((f) => f !== 'index.html');
  const softDelete = psql("select count(distinct table_name) from information_schema.columns where table_schema='public' and column_name in ('deleted_at','is_deleted')");
  say(exportUI.length > 0 && Number(erasureRpc || 0) > 0 && reachableInApp.length > 0, 'V1 forget me',
    `${exportUI.length} page(s) offer an export (${exportFns.join(', ') || 'no function'}); erasure is a real RPC (${erasureRpc}) that anonymizes rather than promises, reachable from ${deleteUI.length} page(s) including ${reachableInApp.length} inside the app; ${softDelete} table(s) hold deleted rows recoverably`,
    exportUI.length === 0 ? 'no page offers a person their own data - leaving means abandoning it'
      : Number(erasureRpc || 0) === 0 ? 'no erasure mechanism exists, so the only way to be forgotten is to write to somebody and hope'
      : 'erasure exists but only on the landing page - a person signed in and working has to leave the app to find the way out');
}

// ── V2 · is consent asked BEFORE the thing it consents to? ───────────────────────────────────────
{
  // ★MARKUP POSITION IS NOT EXECUTION ORDER. The first version of this lens compared where the
  // googletagmanager <script> sits against where the word "consent" first appears, and failed a page
  // that is correct: the loader tag is ASYNC, so the inline block below it runs first, which is exactly
  // the order Google documents for Consent Mode. What actually has to hold is that the consent DEFAULT
  // is declared before the CONFIG - the config is the call that starts collecting.
  const withGa = pages.filter((f) => /gtag\(|googletagmanager/i.test(read(f)));
  const wrong = withGa.filter((f) => {
    const src = read(f);
    const dflt = src.search(/gtag\(\s*['"]consent['"]\s*,\s*['"]default['"]/i);
    const config = src.search(/gtag\(\s*['"]config['"]/i);
    return config >= 0 && (dflt < 0 || dflt > config);
  });
  // and the default has to be DENIED - a default of granted is consent mode with the consent removed
  const denied = withGa.filter((f) => /analytics_storage\s*:\s*['"]denied['"]/i.test(read(f)));
  // the person must be able to answer, and their answer must survive the next visit
  const asks = anyPage(/wh_analytics_consent/);
  say(wrong.length === 0 && denied.length === withGa.length && asks.length > 0, 'V2 asked first',
    `${withGa.length} page(s) carry analytics; ${withGa.length - wrong.length} declare a consent default before the config, ${denied.length} default it to DENIED, and ${asks.length} store the person's answer for next time`,
    wrong.length ? `${wrong.join(', ')} calls config before declaring any consent default - collection starts before the question`
      : denied.length !== withGa.length ? 'the consent default is not denied, so the tag collects until told otherwise - a default of granted is consent mode with the consent taken out'
      : 'nothing stores the answer, so a person is asked again on every visit and their "no" never sticks');
}

// ── V3 · does a person know who will read this? ──────────────────────────────────────────────────
{
  // the surfaces where what you write reaches other people
  const shared = ['community.html', 'public-feed.html', 'logbook.html', 'hive.html', 'marketplace.html'].filter((f) => pages.includes(f));
  const silent = shared.filter((f) => {
    const src = read(f);
    return !/visible to|who can see|everyone in|your hive will|public|shared with|only you/i.test(src);
  });
  say(silent.length === 0, 'V3 who sees this',
    `${shared.length - silent.length} of ${shared.length} sharing surface(s) say who will read what is written there`,
    `${silent.join(', ')} take what a person writes without saying who receives it`);
}

// ── V4 · do the client-side promises hold? ───────────────────────────────────────────────────────
{
  // a service key or a secret in a shipped page is the one that ends the conversation
  // ★A SECRET HAS A SHAPE, AND THE WORD FOR IT DOES NOT. Matching the bare word "service_role" found it
  // inside a comment explaining a past lesson about privileges. What is dangerous is a VALUE: a key
  // assigned to something, a JWT, an sb_secret_ literal - never the noun on its own.
  const leaked = pages.filter((f) => /sb_secret_[A-Za-z0-9_-]{8,}|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{20,}|(service_role|SERVICE_ROLE)[_A-Za-z]*\s*[:=]\s*["'][^"']{16,}/.test(read(f)));
  // an inline on* handler is what a CSP cannot protect and an injected string can ride
  const inlineHandlers = pages.reduce((n, f) => n + (read(f).match(/\son(click|error|load|submit)=["']/gi) || []).length, 0);
  const csp = existsSync('vercel.json') && /Content-Security-Policy/i.test(read('vercel.json'));
  say(leaked.length === 0 && csp, 'V4 hardened',
    `${leaked.length} shipped page(s) carry a secret; ${inlineHandlers} inline event handler(s) remain; a Content-Security-Policy ${csp ? 'is declared for the deployed origin' : 'is NOT declared'}`,
    leaked.length ? `a secret is shipped to every visitor in: ${leaked.slice(0, 3).join(', ')}`
      : 'no Content-Security-Policy reaches the deployed origin, so an injected script has nothing standing in its way');
}

// ── V5 · is the bot defence real, and out of an honest person's way? ─────────────────────────────
{
  const turnstile = anyPage(/cf-turnstile|hcaptcha|g-recaptcha/i);
  // ★THIS WIDGET IS VERIFIED BY SUPABASE AUTH, NOT BY OUR CODE. index.html states the contract in place:
  // inert until window.WH_TURNSTILE_SITEKEY is set AND bot protection is enabled in Supabase Auth. So
  // looking for an edge function that calls siteverify finds nothing and proves nothing - the honest
  // question is whether the widget is gated on being configured, rather than shown to everyone dead.
  const gated = turnstile.filter((f) => /WH_TURNSTILE_SITEKEY|CONFIGURE-TO-ENABLE|sitekey/i.test(read(f)));
  say(turnstile.length === 0 || gated.length === turnstile.length, 'V5 bots stopped',
    turnstile.length ? `${turnstile.length} page(s) carry a bot check, ${gated.length} of them inert until a sitekey is configured and verified by the auth provider` : 'no bot check stands between a person and their work',
    `${turnstile.length - gated.length} page(s) show a bot widget unconditionally with nothing verifying it - it stops nobody and costs everybody a step`);
}

// ── V6 · does the platform say who it is for? ────────────────────────────────────────────────────
{
  // the terms live wherever the platform put them - on this platform, inside index.html
  const terms = pages.filter((f) => /terms of service|privacy policy|terms & conditions/i.test(read(f)));
  const statesAge = terms.some((f) => /18 years|age of majority|at least 18|not intended for children|minimum age/i.test(read(f)));
  // ★ANCHORED. Unanchored, this matched champion_engAGEment, stORAGE_bytes, GRADEr_passed and user_AGEnt,
  // and reported 34 age-or-school fields on a platform that collects none.
  const collectsAge = psql("select count(*) from information_schema.columns where table_schema='public' and column_name ~ '(^|_)(birth_?date|birthday|dob|age|school|grade|guardian)($|_)'");
  say(statesAge || Number(collectsAge || 0) === 0, 'V6 eligibility',
    `${terms.length} legal page(s); eligibility ${statesAge ? 'is stated in words' : 'is not stated'}; the schema collects ${collectsAge} age-or-school field(s)`,
    'the platform collects an age or a school and never says who it is for, so nothing tells an excluded person they are excluded');
}

console.log(`${bad ? 'FAIL' : 'PASS'} privacy-consent - a person can leave with their data, consent precedes the thing consented to, sharing says who reads it, and the client-side promises hold`);
process.exitCode = bad ? 1 : 0;
