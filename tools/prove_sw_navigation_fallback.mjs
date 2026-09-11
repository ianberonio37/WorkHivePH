// prove_sw_navigation_fallback — "degradation is legible" for pages the service worker does NOT precache
// (P-K, 2026-09-05: P460 learn/index). sw.js serves every navigation; a navigation it cannot fetch and has
// not cached falls back to the precached /offline-fallback.html (sw.js fetch handler, mode === 'navigate').
// This proves it LIVE: load the site online so the worker installs and takes control, cut the network,
// navigate to a non-precached page, and require the fallback page's own words on screen.
//   node tools/prove_sw_navigation_fallback.mjs                      # default targets
//   node tools/prove_sw_navigation_fallback.mjs --page learn/index.html
import { chromium } from 'playwright';
import { HIVE, WORKER } from './prover_harness.mjs';   // identity constants shared with every prover (2026-09-05); the sign-in itself stays on the landing page because the service worker must control THIS page

const SEEDER = process.env.WH_SEEDER_URL || 'http://127.0.0.1:5000';
const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
// + the ten 'offline path' rows (2026-09-05): a page the worker precaches serves its own content, any other lands on the fallback
const TARGETS = ONLY ? [ONLY] : ['learn/index.html', 'architecture.html', 'index.html', 'ai-quality.html', 'alert-hub.html', 'assistant.html', 'dayplanner.html', 'engineering-design.html', 'platform-actions.html', 'agentic-rag-observability.html', 'analytics-report.html', 'asset-hub.html'];
// The fallback page's OWN sentences - not the word 'offline', which the landing page's copy also contains (a false
// PASS on seven pages, 2026-09-05: the worker served the LANDING shell for a non-precached page and the regex said 'fallback').
const FALLBACK_WORDS = /isn.t available offline yet|Your connection dropped/i;
const LANDING_WORDS = /THE HIVE IS OPEN|Access Your Memory Free/i;

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 800 } });   // service workers ALLOWED (default)
const p = await ctx.newPage();
await p.goto(`${SEEDER}/workhive/index.html`, { waitUntil: 'load' });
const sw = await p.evaluate(async () => {
  if (!('serviceWorker' in navigator)) return { supported: false };
  const t0 = Date.now();
  while (!navigator.serviceWorker.controller && Date.now() - t0 < 15000) { await new Promise((r) => setTimeout(r, 250)); }
  const reg = await navigator.serviceWorker.getRegistration();
  return { supported: true, controlled: !!navigator.serviceWorker.controller, scope: reg ? reg.scope : null };
}).catch((e) => ({ supported: false, err: e.message }));
console.log(`  service worker: ${JSON.stringify(sw)}`);
if (!sw.controlled) {
  console.log('FAIL sw-navigation-fallback - the worker never took control of the page online, so no offline navigation can be judged');
  await b.close(); process.exit(1);
}
await p.waitForTimeout(1500);   // let the install-time precache finish (offline-fallback.html is in the shell)
// A realistic offline visitor HAS a session (2026-09-05 calibration): signed out, every gated page correctly bounces to
// the sign-in landing, which read as 'landed on the LANDING shell' for six pages. Sign in on the landing (utils.js is
// loaded there) and stamp the identity keys, then go offline - a signed-in user bounced to sign-in offline is the defect.
await p.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 15000 }).catch(() => {});
const signedIn = await p.evaluate(async ({ HIVE, WORKER }) => { try { const db = window._whSupabaseClient || window.getDb('http://127.0.0.1:54321', window.SUPABASE_KEY); const { error } = await db.auth.signInWithPassword({ email: WORKER.email, password: WORKER.password }); localStorage.setItem('wh_active_hive_id', HIVE); localStorage.setItem('wh_last_worker', WORKER.name); localStorage.setItem('wh_hive_role', WORKER.role); return !error; } catch (e) { return false; } }, { HIVE, WORKER });
console.log(`  signed in before going offline: ${signedIn}`);
await ctx.setOffline(true);
let bad = 0;
for (const t of TARGETS) {
  let text = '', url = '', navErr = '';
  try {
    const resp = await p.goto(`${SEEDER}/workhive/${t}`, { waitUntil: 'domcontentloaded', timeout: 20000 });
    await p.waitForTimeout(800);
    text = await p.evaluate(() => (document.body && document.body.innerText || '').replace(/\s+/g, ' ').trim());
    url = p.url(); navErr = resp ? ('http ' + resp.status()) : 'no response';
  } catch (e) { navErr = 'goto rejected: ' + e.message.slice(0, 70); text = 'NAVIGATION ERROR ' + e.message.slice(0, 80); try { url = p.url(); } catch (_) { /* gone */ } }
  // Two honest outcomes: the FALLBACK page (not cached, network dead) or the page's OWN content (the worker had it
  // cached - architecture.html is served offline from the shell). Only an error page / empty body is a failure.
  const fallback = FALLBACK_WORDS.test(text);
  const landing = !fallback && LANDING_WORDS.test(text) && !/^index\.html/.test(t);   // the landing shell served for ANOTHER page = a wrong page, not a fallback
  const own = !fallback && !landing && text.length > 200 && !/NAVIGATION ERROR|ERR_|This site can.t be reached/i.test(text);
  const ok = fallback || own;
  if (!ok) bad++;
  console.log(`  ${ok ? 'ok ' : 'BAD'} ${t.padEnd(22)} [${navErr} · at ${url.split('/').slice(-2).join('/')}] offline navigation -> ${fallback ? 'the offline-fallback page' : (own ? 'its own cached content' : (landing ? 'the LANDING shell (wrong page)' : 'an error page'))}: "${text.slice(0, 90)}"`);
}
await ctx.setOffline(false);
await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} sw-navigation-fallback - ${TARGETS.length - bad}/${TARGETS.length} non-precached navigations land on offline-fallback.html when offline`);
process.exit(bad ? 1 : 0);
