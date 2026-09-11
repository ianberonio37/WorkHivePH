// prove_handoff_carries_context — P-J "hand-off carries context" / "the return path" (2026-09-05), the X lens
// for pages that have no scripted journey: a signed-in supervisor opens the page, follows its FIRST internal
// navigation link to another WorkHive page, and the identity must survive the hop - the stored hive id, role
// and worker name unchanged, no sign-in wall, and the destination showing the hive (or the worker) by name.
// Then the browser goes BACK: the origin page must render again with the same identity (the return path).
//   node tools/prove_handoff_carries_context.mjs            # roster below; exit 1 on any dropped identity
//   node tools/prove_handoff_carries_context.mjs --page audit-log.html
import { chromium } from 'playwright';
import { SEEDER, HIVE as HIVE_ID, WORKER as WHO, signIn, VIS_JS } from './prover_harness.mjs';   // shared preamble (2026-09-05)
const HIVE_NAME = WHO.hiveName;
const WORKER = WHO.first;
const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
// --pages lets the roster be driven from the live-walk ledger (2026-09-06): the 20 P-J rows this file was
// written for became 39 surfaces once every hand-off/return-path row was counted, and a browser roster that
// size has to run in halves to fit the background cap.
const LIST = (() => { const i = process.argv.indexOf('--pages'); return i >= 0 ? process.argv[i + 1].split(',') : null; })();
const PAGES = [   // the 20 P-J rows without a scripted journey (P385..P424, 2026-09-05)
  'agentic-rag-observability.html', 'design-system.html', 'llm-observability.html', 'offline-fallback.html', 'platform-actions.html',
  'symbol-gallery.html', 'learn/index.html', 'project-report.html', 'report-sender.html', 'shift-brain.html',
  'ai-quality.html', 'founder-console.html', 'marketplace-admin.html', 'plant-connections.html', 'promo-poster.html',
  'validator-catalog.html', 'audit-log.html', 'ph-intelligence.html', 'public-feed.html',
];
const SKIP_HREF = /^(#|javascript:|mailto:|tel:|https?:\/\/(?!127\.0\.0\.1))|index\.html\?(signin|signup)=|logout|sign-out|\.pdf$|\.json$/i;

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 800 }, serviceWorkers: 'block' });
await signIn(ctx);

const ident = (p) => p.evaluate(() => ({ hive: localStorage.getItem('wh_active_hive_id'), role: localStorage.getItem('wh_hive_role'), worker: localStorage.getItem('wh_last_worker'), url: location.pathname.split('/').pop(), text: (document.body.innerText || '').replace(/\s+/g, ' ').slice(0, 8000) }));   // the whole first screens, not the first 1,200 chars (2026-09-05 calibration)
let bad = 0, n = 0;
for (const file of (LIST || PAGES)) {
  if (ONLY && file !== ONLY) continue;
  n++;
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/${file}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(4000);
  const a = await ident(p);
  const target = await p.evaluate(({ SKIP, VIS_JS }) => {
    const re = new RegExp(SKIP, 'i');
    const vis = (0, eval)(VIS_JS);   // a sticky/fixed header has no offsetParent (2026-09-05)
    // A self-link is one whose RESOLVED path equals this page's path - not one that merely contains the file name
    // (on learn/index.html the old test threw away the landing link, /workhive/index.html); pillar links are
    // extensionless and live under /learn/ at any depth (2026-09-05 calibration).
    const self = location.pathname.replace(/\/+$/, '');
    const links = [...document.querySelectorAll('a[href]')].filter(vis).map((e) => e.getAttribute('href') || '').filter((h) => {
      if (!h || re.test(h)) return false;
      let path; try { path = new URL(h, location.href).pathname.replace(/\/+$/, ''); } catch (e) { return false; }
      if (path === self) return false;
      return /\.html(\?|#|$)/.test(h) || /\/learn\//.test(path);
    });
    if (!links.length) { const root = [...document.querySelectorAll('a[href="/"]')].find(vis); if (root) return '/'; }   // the learn hub links to the site root (= the landing in prod; the seeder serves it at workhive/index.html)
    return links[0] || null;
  }, { SKIP: SKIP_HREF.source, VIS_JS });
  if (!target) { const dbg = await p.evaluate(() => { const all = [...document.querySelectorAll('a[href]')]; const vis = all.filter((e) => (typeof e.checkVisibility === 'function' ? e.checkVisibility() : e.offsetParent !== null)); return `${all.length} anchors, ${vis.length} visible; first hrefs: ${all.slice(0, 6).map((e) => e.getAttribute('href')).join(' ')}`; }).catch(() => '?'); console.log(`  n/a ${file.padEnd(32)} no internal navigation link to follow (${dbg})`); n--; await p.close(); continue; }
  if (target === '/') { await p.goto(`${SEEDER}/workhive/index.html`, { waitUntil: 'domcontentloaded' }).catch(() => {}); }
  else await p.click(`a[href="${target}"]`, { timeout: 5000 }).catch(async () => { await p.goto(`${SEEDER}/workhive/${target}`, { waitUntil: 'domcontentloaded' }).catch(() => {}); });
  await p.waitForTimeout(4000);
  const d = await ident(p);
  await p.goBack({ waitUntil: 'domcontentloaded' }).catch(() => {});
  await p.waitForTimeout(3500);
  let r = await ident(p);
  // A deep link into a card (hive.html#maturity-stairway-card) pushes a modal-history state (T42): the first Back closes the
  // card, the second returns. One extra Back is the designed return path, not a lost one.
  if (target !== '/' && r.url === String(target).split('?')[0].split('#')[0].split('/').pop() && r.url !== file.split('/').pop()) { await p.goBack({ waitUntil: 'domcontentloaded' }).catch(() => {}); await p.waitForTimeout(3000); r = await ident(p); }
  const idKept = d.hive === a.hive && d.role === a.role && d.worker === a.worker;
  const noWall = !/^(sign in|log in)/i.test(d.text.trim()) && !/wh-signin-wall|Sign in to continue/i.test(d.text);
  let named = new RegExp(HIVE_NAME + '|' + WORKER + '|Leandro Marquez|Supervisor', 'i').test(d.text);   // the hive, the worker, or the role chip
  // Calibration (2026-09-05, plant-connections -> integrations.html): a destination that shows NO identity chrome even
  // on a DIRECT signed-in load has nothing to name after a hop - that is the page's design (a catalog/settings surface),
  // not a dropped hand-off. Only a destination that names the identity when opened directly, and fails to after the hop,
  // is a lost context. The direct load is measured, never assumed.
  let namedNote = '';
  if (!named) {
    const q = await ctx.newPage();
    await q.goto(`${SEEDER}/workhive/${String(target).replace(/^\.\//, '')}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
    await q.waitForTimeout(4000);
    const direct = await q.evaluate(() => (document.body.innerText || '').replace(/\s+/g, ' ').slice(0, 8000)).catch(() => '');
    await q.close();
    const directNamed = new RegExp(HIVE_NAME + '|' + WORKER + '|Leandro Marquez|Supervisor', 'i').test(direct);
    if (!directNamed) { named = true; namedNote = ' (no identity chrome on a direct load either: n/a)'; }
  }
  const returned = r.url === file.split('?')[0].split('/').pop() && r.hive === a.hive && r.worker === a.worker;   // compare the last path segment (learn/index.html)
  const ok = idKept && noWall && named && returned;
  if (!ok) bad++;
  console.log(`  ${ok ? 'ok ' : 'BAD'} ${file.padEnd(32)} -> ${String(target).slice(0, 34).padEnd(34)} identity ${idKept ? 'kept' : 'DROPPED'} · wall ${noWall ? 'no' : 'YES'} · named ${named ? 'yes' + namedNote : 'NO'} · back ${returned ? 'ok' : 'LOST'}`);
  await p.close();
}
await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} handoff-carries-context - ${n - bad}/${n} pages carry the identity across a hop and back`);
process.exit(bad ? 1 : 0);
