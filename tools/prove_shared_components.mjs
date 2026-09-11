// prove_shared_components — W3-SC: the 14 shared scripts, as subjects rather than as somebody else's page.
//
// Seventeen root scripts appear in NO trajectory row's title, story or basis, and one of them,
// `connectivity-widget.js`, ships on 33 pages. The heavily-loaded chrome - browser-floor, utils,
// offline-banner, offline-queue, session-timeout - is graded only through whichever host page a walk
// happened to open. That is how a shared piece acquires a blind spot: every page's lens assumes some other
// page's lens looked at it.
//
// FOUR LENSES, THREE HOSTS EACH (a phone, a desktop and a wall display), because a shared piece that is
// right on one page and wrong on the next is the failure this wave exists to find:
//
//   U  IT SAYS THE SAME THING EVERYWHERE. The element it injects carries the same accessible name and the
//      same visible words on all three hosts. A control that is "Menu" here and unnamed there is two
//      controls to the person who uses one of them.
//   F  IT DOES ITS JOB EVERYWHERE. It actually loads on the pages that reference it, defines the global it
//      promises, and leaves its element in the DOM - not "the script tag is present".
//   A  IT HOLDS UP AWAY FROM A DESK. Its element stays inside the viewport at 390, keeps a 40px target, and
//      does not widen the page (a closed off-canvas panel still widens a page - that one shipped).
//   I  IT NEVER SHOWS ONE PERSON ANOTHER PERSON'S STATE. Anything it persists is keyed to the signed-in
//      person or cleared with them: a shared device is the normal case in a plant.
//
//   node tools/prove_shared_components.mjs                 # all 14
//   node tools/prove_shared_components.mjs --js nav-hub.js
//   node tools/prove_shared_components.mjs --self-test     # teeth, no browser
import { chromium } from 'playwright';
import { takeBrowserSlot } from './browser_slot.mjs';
import { readdirSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { execSync } from 'node:child_process';

const ORIGIN = process.env.WH_SEEDER_URL ? `${process.env.WH_SEEDER_URL}/workhive` : 'http://127.0.0.1:5000/workhive';
const args = process.argv.slice(2);
const argOf = (f) => { const i = args.indexOf(f); return i >= 0 ? args[i + 1] : null; };
const ONLY = argOf('--js');

// what each shared piece promises: the global it defines and the element it leaves behind. Read from the
// source where it can be, declared here where the script names it only in a string.
// ★READ FROM THE SCRIPTS, NOT FROM THEIR NAMES. The first version of this table was written from the file
// names and eight of its nineteen entries were fiction: `offline-queue.js` defines `whCreateQueue` and
// `whRegisterQueue`, not `whOfflineQueue`; `form-autosave.js` defines `whAutosave`, not `whAutoSaveDraft`;
// `session-timeout.js`, `device-fingerprint.js` and `wh-consent.js` were credited with storage keys they
// never write (the one key `wh-consent.js` does write is `wh_analytics_consent`); and the nav hub's element
// is `#wh-hub`, not `#wh-nav-hub`. A prover with an invented contract grades every page against a promise
// the script never made - each entry below is now taken from the source itself.
const CONTRACT = {
  'nav-hub.js': { el: '#wh-hub', global: 'WHNavTools', persists: [] },
  'companion-launcher.js': { el: '#wh-ai-trigger, #wh-ai-widget', global: 'WHAssistant', persists: ['_whCompanionDraft'] },
  'offline-banner.js': { el: null, global: '__whOfflineBannerLoaded', persists: [] },
  'connectivity-widget.js': { el: '#wh-conn-chip', global: 'whBandwidthClass', persists: [] },
  'offline-queue.js': { el: null, global: 'whCreateQueue', persists: [] },
  // ★AN ELEMENT THAT APPEARS ONLY WHEN SOMETHING HAPPENS IS NOT A MISSING ELEMENT. `#wh-idle-overlay` is
  // built inside prompt(), which runs when the session actually goes idle - so a freshly loaded page
  // correctly has no overlay, and demanding one produced two findings against a piece behaving exactly as
  // written ("its element appeared on 0 of 3 hosts"; "0/3 host(s) carry its element" beside "3/3 define
  // whClearIdentity()", which should have been the clue). `elWhen` says what has to happen first; the
  // element's absence is then reported as unanswerable rather than as a defect.
  'session-timeout.js': { el: '#wh-idle-overlay', elWhen: 'the session goes idle', global: 'whClearIdentity', persists: [] },
  'device-fingerprint.js': { el: null, global: 'whDeviceFingerprint', persists: [] },
  'browser-floor.js': { el: null, global: null, persists: [] },
  'utils.js': { el: null, global: 'escHtml', persists: ['wh_draft'] },
  'form-autosave.js': { el: null, global: 'whAutosave', persists: [] },
  'oc-helper.js': { el: null, global: 'updateWithOC', persists: [] },
  'qr-scanner.js': { el: null, global: 'WHQRScanner', persists: [] },
  'wh-consent.js': { el: '#wh-consent', global: null, persists: ['wh_analytics_consent'] },
  'worker-drawer.js': { el: null, global: 'openWorkerDrawer', persists: [] },
  'asset-qr.js': { el: null, global: 'WHAssetQR', persists: [] },
  'wh-tts.js': { el: null, global: 'WHTts', persists: [] },
  'skill-content.js': { el: null, global: null, persists: [] },
  'button-lock.js': { el: null, global: 'withButtonLock', persists: [] },
  'impact-preview.js': { el: null, global: '__whImpactInstalled', persists: [] },
};

const HOSTS = [
  { name: 'phone', viewport: { width: 390, height: 844 } },
  { name: 'desktop', viewport: { width: 1280, height: 900 } },
  { name: 'wall', viewport: { width: 1920, height: 1080 } },
];

// which pages load which script — read once, from the pages themselves
function loaders() {
  const map = {};
  for (const f of readdirSync('.').filter((x) => x.endsWith('.html'))) {
    let s = '';
    try { s = readFileSync(f, 'utf8'); } catch { continue; }
    for (const m of s.matchAll(/<script[^>]+src="([^"]+\.js)"/g)) {
      const js = m[1].split('?')[0].replace(/^\//, '');
      if (js.includes('/')) continue;
      (map[js] = map[js] || []).push(f);
    }
  }
  return map;
}

const READ = ({ sel, global: g, keys }) => {
  const vis = (e) => !!e && (typeof e.checkVisibility === 'function' ? e.checkVisibility({ visibilityProperty: true }) : e.offsetParent !== null);
  const els = sel ? Array.from(document.querySelectorAll(sel)) : [];
  const named = els.map((e) => (e.getAttribute('aria-label') || e.getAttribute('title') || (e.textContent || '').replace(/\s+/g, ' ').trim()).slice(0, 48)).filter(Boolean);
  const boxes = els.map((e) => { const r = e.getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height), right: Math.round(r.right) }; });
  // A tap-target floor only applies to something a finger can actually hit. A dormant/closed overlay
  // (opacity:0, visibility:hidden, display:none, or an opacity:0 ancestor) is NOT a tap target - its
  // getBoundingClientRect is meaningless for 2.5.8, and worse, a close-animation transform (scale(0.4))
  // makes it read tiny. companion-launcher's #wh-ai-widget/#wh-ai-trigger measured 22x22 dormant (scale
  // 0.4 of their real 56px) and banked a false F1; revealed-and-settled they are 56px. So gate ONLY the
  // tappable ones: checkVisibility({opacityProperty}) is false when the element OR an ancestor is opacity:0.
  // A genuinely-visible sub-40 control still fails - the teeth are intact.
  const tappable = (e) => (typeof e.checkVisibility === 'function')
    ? e.checkVisibility({ opacityProperty: true, visibilityProperty: true, contentVisibilityAuto: true })
    : (e.offsetParent !== null && getComputedStyle(e).opacity !== '0');
  const small = els.filter((e) => { if (!tappable(e)) return false; const r = e.getBoundingClientRect(); return r.width > 0 && (r.width < 40 || r.height < 40); }).length;
  const stored = {};
  for (const k of (keys || [])) {
    let hit = null;
    try { for (const kk of Object.keys(localStorage)) if (kk.includes(k)) hit = kk; } catch (e) { void e; }
    stored[k] = hit;
  }
  return {
    present: els.length, visible: els.filter(vis).length, named, boxes, small, stored,
    globalDefined: g ? (typeof window[g] !== 'undefined') : null,
    docWidth: document.documentElement.scrollWidth, winWidth: window.innerWidth,
  };
};

// ★THIS PROVER WALKED THE SIGN-IN DOOR 57 TIMES BEFORE IT HAD AN IDENTITY. Every hive page redirects a
// stranger to /index.html?signin=1, and the door answers 200 and renders happily - so the readings described
// the door, not the piece, and 37 rows were banked on them before an arrival check existed. A shared piece
// lives on pages a signed-in person opens; walking them as nobody was never going to answer anything.
//
// One sign-in, reused for every host and every piece: 19 pieces x 3 hosts is 57 contexts, and 57 sign-ins
// against the auth server is a self-inflicted load test.
const PERSON = { name: 'Wilfredo Malabanan', email: 'wilfredomalabanan@auth.workhiveph.com' };
const SUPA = process.env.WH_EDGE_URL || 'http://127.0.0.1:54321';

// ★A BUSY DATABASE IS NOT AN ABSENT ONE. A single attempt came back empty while another wave held the host,
// and this prover concluded it could not name the person's hive - which reads as "there is no such person"
// rather than "ask again in a moment". It retries, and only then gives up, exactly as the function-contract
// prover learned to.
const psql = (sql, tries = 5) => {
  for (let i = 0; i < tries; i++) {
    try {
      const out = execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`,
                           { encoding: 'utf8', timeout: 25000 }).trim();
      if (out) return out;
    } catch { /* the engine is busy or wedged; wait and ask again */ }
    try { execSync('powershell -NoProfile -Command "Start-Sleep -Seconds 4"', { stdio: 'ignore', timeout: 12000 }); } catch { /* even the wait may fail on a wedged host */ }
  }
  return '';
};

let SESSION = null;                       // the storageState every walk reuses
async function establishIdentity(browser) {
  const hive = psql(`select hive_id::text from hive_members where worker_name = '${PERSON.name}' and status = 'active' limit 1`);
  if (!hive) return 'the database could not name this person\'s hive - walking as nobody would grade the door';
  const role = psql(`select role from hive_members where worker_name = '${PERSON.name}' and hive_id::text = '${hive}' limit 1`) || 'worker';
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const p = await ctx.newPage();
  await p.goto(`${ORIGIN}/shift-brain.html`, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
  await p.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 20000 }).catch(() => {});
  const out = await p.evaluate(async ({ hive, who, role, supa }) => {
    try {
      const db = window._whSupabaseClient || window.getDb(supa, window.SUPABASE_KEY);
      const { error } = await db.auth.signInWithPassword({ email: who.email, password: 'test1234' });
      if (error) return 'auth: ' + error.message;
      localStorage.setItem('wh_active_hive_id', hive);
      localStorage.setItem('wh_last_worker', who.name);
      localStorage.setItem('wh_hive_role', role);
      const { data: h } = await db.from('hives').select('name').eq('id', hive).maybeSingle();
      if (h && h.name) localStorage.setItem('wh_hive_name', h.name);
      return 'ok';
    } catch (e) { return 'threw: ' + (e && e.message); }
  }, { hive, who: PERSON, role, supa: SUPA }).catch((e) => 'evaluate: ' + e.message);
  if (out === 'ok') SESSION = await ctx.storageState();
  await ctx.close();
  return out;
}

async function walk(browser, js, hostPages) {
  const c = CONTRACT[js] || { el: null, global: null, persists: [] };
  const readings = [];
  for (let i = 0; i < HOSTS.length; i++) {
    const host = HOSTS[i];
    const page = hostPages[i % hostPages.length];
    const ctx = await browser.newContext({ viewport: host.viewport, ...(SESSION ? { storageState: SESSION } : {}) });
    const p = await ctx.newPage();
    let r = null; let err = null;
    try {
      await p.goto(`${ORIGIN}/${page}`, { waitUntil: 'domcontentloaded', timeout: 45000 });
      await p.waitForTimeout(3200);
      // ★A PAGE THE WALK NEVER REACHED CANNOT BE GRADED. Without an identity, every hive page redirects to
      // `/index.html?signin=1&return=<page>` - so this prover walked the SIGN-IN DOOR three times for each
      // piece and reported what it found there: "0/3 define whAutosave()" (the door does not load
      // form-autosave.js), "its element appeared on 0 of 3 hosts" (the door has no such element), "2 of its
      // elements are under 40px" (the door's). Nine findings and thirty n/a verdicts, every one about a page
      // that is not the subject - and 37 rows were banked on them before this check existed. The landed URL
      // is the only thing that can tell the difference, because the door answers 200 and renders happily.
      // ★COMPARE THE END OF THE PATH, NOT THE WHOLE OF IT. ORIGIN carries a `/workhive` prefix, so a walk
      // that arrived perfectly well at `/workhive/achievements.html` was measured against `achievements.html`
      // and reported as a bounce - the check written to stop false readings started producing them. The
      // question is "is this the page I asked for", and the answer lives at the END of the path.
      const landedPath = await p.evaluate(() => location.pathname.replace(/^\//, ''));
      const landed = landedPath + (await p.evaluate(() => location.search));
      const want = page.replace(/^\//, '');
      if (!(landedPath === want || landedPath.endsWith('/' + want))) {
        err = `bounced to ${landed.slice(0, 60)} - this walk never reached ${page}, so nothing it saw is about this piece`;
      } else {
        r = await p.evaluate(READ, { sel: c.el, global: c.global, keys: c.persists });
      }
    } catch (e) { err = String(e.message || e).slice(0, 90); }
    readings.push({ host: host.name, page, err, ...(r || {}) });
    await ctx.close().catch(() => {});
  }
  const good = readings.filter((r) => !r.err);
  const out = {};
  // U — the same words everywhere it appears
  const nameSets = good.filter((r) => (r.present || 0) > 0).map((r) => (r.named || []).join('|'));
  // an element the contract says appears only on a trigger cannot be asked about on a page nobody triggered
  out.U = (c.elWhen && good.every((r) => (r.present || 0) === 0))
      ? { verdict: 'n/a', line: `its element appears only when ${c.elWhen}, and nothing here triggered that` }
    // ★A PIECE WITH NO ELEMENT STILL SAYS SOMETHING - IT SAYS ITS GLOBAL. Twelve rows sat unanswerable on
    // "this piece leaves no element of its own to name", which is true and is not an answer: the question is
    // whether the piece presents itself the SAME WAY everywhere it is loaded, and for a piece whose whole
    // surface is a function, the name and type of that function IS its presentation. A page where it is
    // missing, or where the name means something else, is exactly the inconsistency this lens exists to
    // catch. Only a piece with neither an element nor a global has genuinely nothing to be asked.
    : (!c.el && c.global)
      ? (good.every((r) => r.globalDefined)
          ? { verdict: 'ok', line: `no element of its own, and it presents the same way on all ${good.length} host(s): ${c.global}() is defined on every one` }
          : { verdict: 'BAD', line: `${good.filter((r) => r.globalDefined).length}/${good.length} host(s) define ${c.global}() - it does not present the same way everywhere` })
    : !c.el ? { verdict: 'n/a', line: 'this piece leaves neither an element nor a global of its own to name' }
    : nameSets.length < 2 ? { verdict: 'BAD', line: `its element appeared on ${nameSets.length} of ${good.length} host(s), so "the same everywhere" cannot be asked` }
    : new Set(nameSets).size === 1 ? { verdict: 'ok', line: `named identically on ${nameSets.length} hosts: "${(good.find((r) => r.named && r.named.length) || {}).named?.slice(0, 2).join(', ') || ''}"` }
    : { verdict: 'BAD', line: `named differently per host: ${nameSets.map((n, i) => `${good[i].host}="${n.slice(0, 40)}"`).join(' · ')}` };
  // F — it loads and does what it promises on every page that references it
  const loadedEverywhere = good.length === HOSTS.length;
  const promises = [c.el && `${good.filter((r) => r.present > 0).length}/${good.length} host(s) carry its element`,
                    c.global && `${good.filter((r) => r.globalDefined).length}/${good.length} define ${c.global}()`].filter(Boolean);
  // the same exemption for F: a trigger-only element missing on an untriggered page is not a broken promise
  const elOwed = c.el && !c.elWhen;
  const fBad = !loadedEverywhere || (elOwed && good.some((r) => (r.present || 0) === 0)) || (c.global && good.some((r) => !r.globalDefined));
  out.F = { verdict: fBad ? 'BAD' : 'ok', line: promises.join('; ') || `loaded on ${good.length}/${HOSTS.length} host(s) and threw nothing` };
  // A — the phone reading is the one that matters
  const phone = good.find((r) => r.host === 'phone');
  out.A = !phone ? { verdict: 'BAD', line: 'the phone host could not be read' }
    : (phone.docWidth > phone.winWidth + 2) ? { verdict: 'BAD', line: `on ${phone.page} at 390 the document is ${phone.docWidth}px wide - something widens the page` }
    : (c.el && phone.small > 0) ? { verdict: 'BAD', line: `${phone.small} of its element(s) are under 40px on a phone` }
    : { verdict: 'ok', line: `at 390 on ${phone.page}: no overflow${c.el ? `, ${phone.present} element(s) all at least 40px` : ''}` };
  // I — what it persists must be keyed to a person, or cleared with them
  const stored = good.flatMap((r) => Object.entries(r.stored || {}).filter(([, v]) => v).map(([, v]) => v));
  out.I = !c.persists.length ? { verdict: 'n/a', line: 'this piece persists nothing of its own' }
    : stored.length === 0 ? { verdict: 'ok', line: `nothing of ${c.persists.join(', ')} was left behind by a walk that did not use it` }
    : stored.every((k) => /[:_-](?:[0-9a-f-]{8,}|[A-Za-z ]{4,})$/.test(k)) ? { verdict: 'ok', line: `keys carry an owner: ${[...new Set(stored)].slice(0, 3).join(', ')}` }
    : { verdict: 'BAD', line: `persists ${[...new Set(stored)].slice(0, 3).join(', ')} with no owner in the key - a shared device would hand it to the next person` };
  return { js, readings, ...out };
}

// ── teeth ─────────────────────────────────────────────────────────────────────────────────────────
if (args.includes('--self-test')) {
  const fails = [];
  const map = loaders();
  const roster = Object.keys(CONTRACT).filter((j) => map[j]);
  if (roster.length < 12) fails.push(`only ${roster.length} of the declared pieces are loaded by any page`);
  for (const j of roster) if (!map[j].length) fails.push(`${j} is declared but no page loads it`);
  if (!map['connectivity-widget.js'] || map['connectivity-widget.js'].length < 20) fails.push('connectivity-widget.js should be loaded by ~33 pages');
  console.log(fails.length ? 'FAIL shared-components self-test - ' + fails.join('; ')
    : `self-test OK: ${roster.length} shared pieces, each loaded by a real page (connectivity-widget on ${map['connectivity-widget.js'].length})`);
  process.exit(fails.length ? 1 : 0);
}

// ── the run ───────────────────────────────────────────────────────────────────────────────────────
const map = loaders();
const roster = Object.keys(CONTRACT).filter((j) => map[j] && (!ONLY || j === ONLY));
console.log(`walking ${roster.length} shared piece(s) x 4 lenses on 3 hosts each`);
// this host has one browser slot and the suite runs gates concurrently - queue, do not race
await takeBrowserSlot('shared-components');
const browser = await chromium.launch();
// establish the identity BEFORE any piece is walked - without it every host page is the sign-in door
const who = await establishIdentity(browser);
if (who !== 'ok') {
  console.log(`FAIL shared-components - could not sign in, so every page would be the door: ${who}`);
  await browser.close();
  process.exit(1);
}
console.log(`  signed in as ${PERSON.name} - the host pages below are the pages, not the door`);
const results = [];
let bad = 0;
for (const js of roster) {
  const r = await walk(browser, js, map[js].slice(0, 3).concat(map[js]).slice(0, 3));
  results.push(r);
  for (const lens of ['U', 'F', 'A', 'I']) {
    const v = r[lens];
    if (v.verdict === 'BAD') bad++;
    console.log(`  ${v.verdict === 'ok' ? 'ok ' : v.verdict === 'n/a' ? 'n/a' : 'BAD'} ${lens} ${js.padEnd(26)} ${v.line.slice(0, 116)}`);
  }
}
await browser.close();
try { mkdirSync('.tmp', { recursive: true }); } catch (e) { void e; }
writeFileSync('.tmp/shared_components.json', JSON.stringify({ walked: roster.length, bad, results }, null, 2));
console.log(`${bad ? 'FAIL' : 'PASS'} shared-components - ${roster.length * 4 - bad}/${roster.length * 4} lens(es) hold  ·  .tmp/shared_components.json`);
process.exitCode = bad ? 1 : 0;
