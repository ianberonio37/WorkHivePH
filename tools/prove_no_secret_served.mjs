// prove_no_secret_served.mjs - SL sub-layer S5 (2026-10-15): "The platform must ship this page with no secret, service
// key or private token in what a browser receives."
//
// WHAT A BROWSER RECEIVES is every byte of every response the page gets - its HTML, every script and stylesheet, and
// every JSON answer from the database and the edge - plus what the page leaves in storage. A source grep reads the
// files we wrote; this reads what was SERVED, so a key that arrives through a row the page can read (an integration's
// stored credential, a config table) is caught too.
//
// Per page of the S5 roster, loaded in Chromium as its cast through the product's own form (a public page as its
// visitor), settled and scrolled, every text response body and the page's localStorage / sessionStorage are scanned for:
//   - every secret VALUE in .env, literally (a model provider key, the VAPID private key, ...) - the strongest check
//     there is: the real secret, not its shape
//   - a JWT whose role is not `anon` (the publishable key, public by design) or `authenticated` (the person's own
//     session, theirs to hold) - a service_role key in a browser is the whole database
//   - the shapes of every other kind: sb_secret_, sk-, gsk_, AIza, ghp_, xox?-, a PEM private key block
// TEETH: one page is served a utils.js carrying a service_role-shaped token (built here, signed with nothing - it is a
// shape, not a credential) and an .env secret value; both must be caught, or the prover fails itself.
//
//   node tools/prove_no_secret_served.mjs [--page a.html,b.html] [--json .tmp/s5_results.json] [--no-teeth]
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { dirname } from 'node:path';
import { SEEDER, stubModelCalls } from './prover_harness.mjs';
import { ALL_ROWS_DRAWN } from './lib/long_list_text.mjs';

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const OUT = arg('--json', '.tmp/s5_results.json');
const TEETH = !process.argv.includes('--no-teeth');
const TEETH_PAGE = arg('--teeth-page', 'logbook.html');

const reg = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
const S5 = reg.trajectories.filter((t) => t.sl && t.sl.sublayer === 'S5' && t.status !== 'descoped');
const castOf = new Map(S5.map((t) => [t.sl.page, t.persona]));
const PAGES = arg('--page') ? arg('--page').split(',') : [...castOf.keys()];
const SUP = /supervisor|oversight|owner|engineer|manager/i;
const ACCOUNT = (persona) => persona === 'anon' ? { user: 'anon' } : (SUP.test(persona) ? { user: 'leandromarquez' } : { user: 'bryangarcia' });

// the secret VALUES this repository holds (never printed: a hit is reported by the key's NAME)
const PUBLIC_BY_DESIGN = /PUBLIC|PUBLISHABLE|_URL$|STRATEGY|ENABLED|SIZE|DAYS|OVERRIDE|RESET|SUBJECT/i;
const SECRETS = existsSync('.env') ? readFileSync('.env', 'utf8').split(/\r?\n/).map((l) => l.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"?([^"\r\n#]*)"?/)).filter(Boolean)
  .map((m) => ({ name: m[1], value: m[2].trim() })).filter((s) => s.value.length >= 16 && !PUBLIC_BY_DESIGN.test(s.name)) : [];
const SHAPES = [
  ['a Supabase secret key', /\bsb_secret_[A-Za-z0-9_-]{10,}/],
  ['an OpenAI-style secret key', /\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}/],
  ['a Groq key', /\bgsk_[A-Za-z0-9]{20,}/],
  ['a Google API key', /\bAIza[0-9A-Za-z_-]{35}\b/],
  ['a GitHub token', /\bghp_[A-Za-z0-9]{36}\b/],
  ['a Slack token', /\bxox[baprs]-[A-Za-z0-9-]{10,}/],
  ['a private key block', /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/],
];
const JWT = /\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}/g;
const ALLOWED_ROLES = new Set(['anon', 'authenticated']);
const jwtRole = (t) => { try { return JSON.parse(Buffer.from(t.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf8')).role || '(none)'; } catch (e) { return '(unreadable)'; } };

function scan(text, where) {
  const hits = [];
  for (const s of SECRETS) if (text.includes(s.value)) hits.push(`${where}: the .env secret ${s.name}`);
  for (const [what, rx] of SHAPES) if (rx.test(text)) hits.push(`${where}: ${what}`);
  for (const t of new Set(text.match(JWT) || [])) { const role = jwtRole(t); if (!ALLOWED_ROLES.has(role)) hits.push(`${where}: a JWT with role ${role}`); }
  return hits;
}

async function context(plant) {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  await ctx.addInitScript(ALL_ROWS_DRAWN);
  await stubModelCalls(ctx);
  await ctx.route('**/rest/v1/client_errors*', (r) => r.request().method() === 'POST' ? r.fulfill({ status: 201, contentType: 'application/json', body: '[]' }) : r.continue());
  if (plant) {
    const fakeRole = Buffer.from(JSON.stringify({ role: 'service_role', iss: 'prover-teeth' })).toString('base64url');
    const planted = `\n;window.__teethShape='eyJhbGciOiJIUzI1NiJ9.${fakeRole}.c2hhcGUtbm90LWEtY3JlZGVudGlhbA';` +
      (SECRETS[0] ? `window.__teethValue=${JSON.stringify(SECRETS[0].value)};` : '');
    const utils = await (await fetch(`${SEEDER}/workhive/utils.js`)).text();
    await ctx.route('**/workhive/utils.js*', (r) => r.fulfill({ status: 200, contentType: 'application/javascript', body: utils + planted }));
  }
  return { browser, ctx };
}

async function signIn(ctx, user) {
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/index.html?signin=1`, { waitUntil: 'load', timeout: 45000 });
  await p.fill('#si-username', user); await p.fill('#si-password', 'test1234'); await p.click('#si-btn');
  const ok = await p.waitForFunction(() => !!localStorage.getItem('wh_active_hive_id'), null, { timeout: 25000 }).then(() => true).catch(() => false);
  await p.close();
  return ok;
}

async function visit(ctx, page) {
  const p = await ctx.newPage();
  const bodies = [];
  p.on('response', (r) => { const ct = (r.headers()['content-type'] || ''); if (/text|json|javascript|css|xml/.test(ct)) bodies.push(r.text().then((t) => [r.url(), t]).catch(() => null)); });
  let loadError = null;
  await p.goto(`${SEEDER}/workhive/${page}`, { waitUntil: 'load', timeout: 60000 }).catch((e) => { loadError = String(e.message).slice(0, 120); });
  await p.waitForLoadState('networkidle', { timeout: 12000 }).catch(() => {});
  await p.waitForTimeout(2500);
  await p.evaluate(async () => { for (let y = 0; y < document.body.scrollHeight; y += 700) { window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 100)); } }).catch(() => {});
  await p.waitForTimeout(1000);
  const store = await p.evaluate(() => { const o = []; for (const s of [localStorage, sessionStorage]) for (let i = 0; i < s.length; i++) o.push(s.key(i) + '=' + s.getItem(s.key(i))); return o.join('\n'); }).catch(() => '');
  const chars = await p.evaluate(() => (document.body.innerText || '').length).catch(() => 0);
  await p.close();
  const got = (await Promise.all(bodies)).filter(Boolean);
  const hits = [];
  let bytes = 0;
  for (const [url, text] of got) { bytes += text.length; hits.push(...scan(text, new URL(url).pathname.split('/').slice(-2).join('/'))); }
  hits.push(...scan(store, 'localStorage/sessionStorage'));
  const problems = [...(loadError ? [`load: ${loadError}`] : []), ...[...new Set(hits)].map((h) => `SECRET SERVED - ${h}`)];
  return { page, chars, responses: got.length, kb: Math.round(bytes / 1024), problems, ok: !problems.length };
}

const byUser = new Map();
for (const page of PAGES) { const u = ACCOUNT(castOf.get(page) || 'anon').user; (byUser.get(u) || byUser.set(u, []).get(u)).push(page); }
const results = [];
for (const [user, pages] of byUser) {
  const { browser, ctx } = await context(false);
  const ok = user === 'anon' ? true : await signIn(ctx, user);
  for (const page of pages) {
    const r = ok ? await visit(ctx, page) : { page, problems: [`sign-in as ${user} failed`], ok: false };
    results.push({ engine: 'chromium', condition: 'as-served', cast: castOf.get(page), account: user, ...r });
    console.log(`  ${r.ok ? 'ok  ' : 'FAIL'} ${page.padEnd(48)} ${String(r.responses ?? '-').padStart(4)} responses, ${String(r.kb ?? '-').padStart(6)} KB scanned`
      + (r.ok ? '' : `\n         ${r.problems.slice(0, 4).join('\n         ')}`));
  }
  await browser.close();
}

let teeth = null;
if (TEETH) {
  const { browser, ctx } = await context(true);
  const ok = await signIn(ctx, ACCOUNT(castOf.get(TEETH_PAGE) || 'worker').user);
  const r = ok ? await visit(ctx, TEETH_PAGE) : { problems: ['teeth sign-in failed'] };
  await browser.close();
  const caughtShape = (r.problems || []).some((p) => /role service_role/.test(p));
  const caughtValue = !SECRETS.length || (r.problems || []).some((p) => /the \.env secret/.test(p));
  teeth = { page: TEETH_PAGE, caughtShape, caughtValue, secretsKnown: SECRETS.length, bit: caughtShape && caughtValue };
  console.log(`\n  teeth - ${TEETH_PAGE} served a planted service_role-shaped token and an .env secret value: ${teeth.bit ? 'both CAUGHT, as they must be' : 'NOT CAUGHT'} (shape ${caughtShape}, value ${caughtValue}; ${SECRETS.length} .env secret value(s) known)`);
}
mkdirSync(dirname(OUT), { recursive: true });
const failed = results.filter((r) => !r.ok).length + (teeth && !teeth.bit ? 1 : 0);
writeFileSync(OUT, JSON.stringify({ generated: new Date().toISOString(), sublayer: 'S5', secrets_checked: SECRETS.map((s) => s.name), shapes: SHAPES.map((s) => s[0]), pages: results.length, failed, teeth, results }, null, 1));
console.log(`\n${failed ? 'FAIL' : 'PASS'} no-secret-served - ${results.length - results.filter((r) => !r.ok).length}/${results.length} page(s) receive no secret${teeth ? `; teeth ${teeth.bit ? 'bit' : 'DID NOT BITE'}` : ''} -> ${OUT}`);
process.exit(failed ? 1 : 0);
