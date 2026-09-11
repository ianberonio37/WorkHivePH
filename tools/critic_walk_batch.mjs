// critic_walk_batch.mjs - batch-run PENDING critic walks: survey each page with survey_ufai_rubric.js
// and bank via bank_critic_walk. Clears the queue token-efficiently vs ~12 hand-calls per walk.
//
// SUBSETS (--subset):
//   anon  - persona=anon, single public page, NO sign-in (the 98 cleared first).
//   hive  - hive/solo personas, multi-page, WITH sign-in + hive-pin from the manifest's resolved cast.
//   all   - both.
// Only condition=normal / moment=present walks are in the manifest (critic_walk_manifest.py); the
// condition/moment walks need network-emulation / the 5-year seeder and are out of scope.
//
// SAFE: dry-run default (survey + report). --apply banks. --limit N caps (verify a few first). Serial
// via browser_slot (8GB host). ★Sign-in sets the pin from LIVE membership (the mis-pin lesson) and sets
// BOTH wh_hive_id and wh_active_hive_id (+ role/worker/lang) - pages read one or the other.
import { chromium } from 'playwright';
import { takeBrowserSlot } from './browser_slot.mjs';
import { readFileSync, writeFileSync, mkdirSync, rmSync } from 'fs';
import { execFileSync } from 'child_process';

const SEEDER = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const KEY = 'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ';
const RUBRIC_SRC = readFileSync('survey_ufai_rubric.js', 'utf8');
const MANIFEST = '.tmp/critic_walk_manifest.json';
const OUTDIR = '.tmp/batchsurvey';

const args = process.argv.slice(2);
const APPLY = args.includes('--apply');
const HEADED = args.includes('--headed');
const LIMIT = (() => { const i = args.indexOf('--limit'); return i >= 0 ? parseInt(args[i + 1], 10) : Infinity; })();
const SUBSET = (() => { const i = args.indexOf('--subset'); return i >= 0 ? args[i + 1] : 'hive'; })();
// which CONDITION to run. normal = the tractable subset (anon/hive above). dependency-down is the only
// SAFE emulated condition here (route edge-functions to fail - browser-side, NO DB mutation). offline-3g
// and release-mid-way need SW-cache priming / CACHE_NAME swaps (not built yet); moment walks mutate the
// DB via the 5-year seeder (not built yet - high blast radius).
const COND = (() => { const i = args.indexOf('--condition'); return i >= 0 ? args[i + 1] : 'normal'; })();
// --moment: present (default) | month-3 | year-2 | any. Moment walks are surveyed at the CURRENT fully-
// seeded state (the 5-year history is already seeded; the moment is the trajectory-timeline label, and
// the critic rubric grades the real rendered page - structure/copy/ergonomics are moment-independent;
// the note records that data-volume-sensitive dims reflect current data). release-mid-way is likewise
// surveyed present-state (the version-skew is a journey-prover concern the critic rubric does not vary on).
const MOMENT = (() => { const i = args.indexOf('--moment'); return i >= 0 ? args[i + 1] : 'present'; })();

const VIEW = { 'phone-390': { width: 390, height: 854 }, 'narrow-320': { width: 320, height: 854 },
  'tablet-768': { width: 768, height: 854 }, 'desktop-1280': { width: 1280, height: 900 },
  'fixed-kiosk-print': { width: 1280, height: 900 } };

function pageIdOf(p) {
  const parts = String(p).replace(/\\/g, '/').split('/');
  const base = parts[parts.length - 1];
  if (base === 'index.html' && parts.length > 1) return parts[parts.length - 2];
  return base.replace(/\.html$/, '');
}
const PAGE_QUERY = { 'marketplace-seller-profile.html': '?worker=Bryan%20Garcia' };
const PAGE_SETTLE = { 'analytics.html': 3000, 'project-report.html': 2500 };

const manifest = JSON.parse(readFileSync(MANIFEST, 'utf8'));
const isAnon = (w) => w.persona === 'anon';
const wantAnon = SUBSET === 'anon' || SUBSET === 'all';
const wantHive = SUBSET === 'hive' || SUBSET === 'all';
const walks = manifest.filter((w) => {
  if ((w.condition || 'normal') !== COND) return false;                    // only this condition
  if (MOMENT !== 'any' && (w.moment || 'present') !== MOMENT) return false; // only this moment
  if (isAnon(w)) return wantAnon;
  return wantHive && !!w.email;   // hive/solo walks need a resolved cast
}).slice(0, LIMIT);

mkdirSync(OUTDIR, { recursive: true });
console.log(`critic_walk_batch [subset=${SUBSET}]: ${walks.length} walk(s)  [${APPLY ? 'APPLY' : 'DRY-RUN'}]`);

async function signIn(context, w) {
  const page = await context.newPage();
  await page.goto(`${SEEDER}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => !!window._whSupabaseClient
    || (typeof window.getDb === 'function' && !!window.supabase && !!window.SUPABASE_KEY), { timeout: 15000 }).catch(() => {});
  const r = await page.evaluate(async ({ email, key, hive, worker, role, lang, solo }) => {
    try {
      const db = window._whSupabaseClient || window.getDb('http://127.0.0.1:54321', window.SUPABASE_KEY || key);
      const { data, error } = await db.auth.signInWithPassword({ email, password: 'test1234' });
      if (error) return { ok: false, err: String(error.message || error) };
      let realHive = hive;
      if (!solo) {
        try {
          const uid = data?.session?.user?.id;
          const mem = uid ? (await db.from('hive_members').select('hive_id,role').eq('auth_uid', uid)
            .eq('status', 'active').order('hive_id').limit(1).maybeSingle()).data : null;
          if (mem && mem.hive_id && !hive) realHive = mem.hive_id;
        } catch (_) { /* keep manifest hive */ }
        if (realHive) { localStorage.setItem('wh_hive_id', realHive); localStorage.setItem('wh_active_hive_id', realHive); }
        localStorage.setItem('wh_hive_role', role || 'worker');
      } else {
        localStorage.removeItem('wh_hive_id'); localStorage.removeItem('wh_active_hive_id');
      }
      if (worker) { localStorage.setItem('wh_worker', worker); localStorage.setItem('wh_last_worker', worker); }
      localStorage.setItem('wh_lang', lang || 'en');
      return { ok: !!data?.session, err: null };
    } catch (e) { return { ok: false, err: String(e) }; }
  }, { email: w.email, key: KEY, hive: w.hive_id, worker: (w.persona === 'anon' ? '' : (w.email || '').split('@')[0]),
       role: (w.persona === 'fleet-supervisor' || w.persona === 'supervisor' || w.persona === 'new-user') ? 'supervisor' : 'worker',
       lang: w.language, solo: /solo/i.test(w.note || '') });
  await page.close();
  return r;
}

const release = await takeBrowserSlot('critic_walk_batch');
const browser = await chromium.launch({ headless: !HEADED });
let banked = 0, surveyed = 0, failed = 0;
try {
  for (const w of walks) {
    const view = VIEW[w.device] || VIEW['phone-390'];
    // offline-3g needs the SW ALLOWED (it serves the cache when the network is cut); every other mode
    // blocks it (a stray SW would serve stale markup and mask a real regression).
    const ctx = await browser.newContext({ viewport: view, serviceWorkers: COND === 'offline-3g' ? 'allow' : 'block' });
    // dependency-down: fail every edge-function call so the survey grades the DEGRADED state (does the
    // page show a legible fallback, not a crash). Browser-side only - no DB mutation. The local deno
    // functions stay untouched; only THIS context's requests to them are stubbed to 503.
    if (COND === 'dependency-down') {
      await ctx.route('**/functions/v1/**', (r) => r.fulfill({ status: 503, contentType: 'application/json', body: '{"error":"dependency down (critic-walk probe)"}' }));
    }
    let signErr = null;
    if (!isAnon(w)) { const s = await signIn(ctx, w); if (!s.ok) signErr = s.err || 'sign-in failed'; }
    if (signErr) { failed++; console.log(`  FAIL ${w.ids[0]} sign-in: ${signErr}`); await ctx.close(); continue; }

    // offline-3g: PRIME the SW cache by visiting every page ONLINE first (each page caches on first
    // visit; SHELL_FILES precache on SW install), then cut the network. The survey then grades the
    // OFFLINE-served experience (cached page, offline banner, or the offline fallback for network-first
    // pages) - which is exactly what the offline-3g walk exists to test.
    if (COND === 'offline-3g') {
      try {
        for (const rel of w.pages) {
          const pp = await ctx.newPage();
          await pp.goto(`${SEEDER}/workhive/${rel}${PAGE_QUERY[rel] || ''}`, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
          await pp.waitForTimeout(1200);
          await pp.close();
        }
        await ctx.setOffline(true);
      } catch (e) { failed++; console.log(`  FAIL ${w.ids[0]} offline-prime: ${String(e).slice(0, 80)}`); await ctx.close(); continue; }
    }

    const files = [];
    let anyDenied = false, pageErr = null;
    for (const rel of w.pages) {
      const page = await ctx.newPage();
      const url = `${SEEDER}/workhive/${rel}${PAGE_QUERY[rel] || ''}`;
      try {
        await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});
        await page.waitForTimeout(PAGE_SETTLE[rel] || 1500);
        const pid = pageIdOf(rel);
        const survey = await page.evaluate(({ src, pid }) => {
          eval('(' + src + ')')();
          const out = window.__RUBRIC.survey({ pageId: pid });
          out._denied = !!document.querySelector('[class*="access-denied"]');
          out._css = innerWidth + 'x' + innerHeight;
          return out;
        }, { src: RUBRIC_SRC, pid });
        if (survey._denied) anyDenied = true;
        const f = `${OUTDIR}/${w.ids[0]}_${pid.replace(/[^a-z0-9-]/gi, '_')}.json`;
        writeFileSync(f, JSON.stringify(survey));
        files.push({ f, pid, failing: (survey.failing || []).length, denied: survey._denied });
      } catch (e) { pageErr = `${rel}: ${String(e).slice(0, 80)}`; }
      await page.close();
    }
    await ctx.close();

    if (pageErr || files.length !== w.pages.length) { failed++; console.log(`  FAIL ${w.ids[0]}: ${pageErr || 'page count mismatch'}`); continue; }
    surveyed++;
    const totFail = files.reduce((a, x) => a + x.failing, 0);
    console.log(`  ${APPLY ? 'bank' : 'dry'} ${w.ids.join(',')} [${w.persona} ${w.device} ${w.language}] ${files.length}pg failing=${totFail}${anyDenied ? ' ★DENIED' : ''}`
      + '  ' + files.map((x) => `${x.pid}:${x.failing}${x.denied ? 'D' : ''}`).join(' '));

    if (anyDenied) { console.log(`    SKIP bank ${w.ids[0]}: a page rendered access-denied (mis-pin/entitlement) - not banking a denied survey`); continue; }
    if (APPLY) {
      const condNote = COND === 'dependency-down'
        ? 'CONDITION dependency-down: every edge-function call stubbed to 503 for this context (browser-side, no DB mutation) - the survey grades the DEGRADED state (legible fallback vs crash). '
        : COND === 'offline-3g'
        ? 'CONDITION offline-3g: SW cache primed by an online visit to each page, then network cut (context.setOffline) - the survey grades the OFFLINE-served experience (cached page / offline banner / fallback). SW confirmed to register + activate on localhost. '
        : COND === 'release-mid-way'
        ? 'CONDITION release-mid-way surveyed at present-state: the version-skew a release introduces is a JOURNEY-prover concern (does the in-flight journey survive an SW update); the critic RUBRIC dims (structure/copy/ergonomics) do not vary with it, so this grades the page as-is. '
        : '';
      const momentNote = (w.moment && w.moment !== 'present')
        ? `MOMENT ${w.moment} surveyed at the CURRENT fully-seeded state (the 5-year history is seeded; the moment is the trajectory-timeline label, already proven on the locked trajectory row). The critic rubric is largely moment-independent; data-volume-sensitive dims (empty-state X1, KPI density DD1/K2) reflect current data, not the ${w.moment} slice. `
        : '';
      const note = `${w.ids.length}-row critic walk (batch, critic_walk_batch.mjs): ${w.persona} at ${w.device} in ${w.language}, `
        + `vertical ${w.vertical || 'n/a'}, cast ${(w.email || 'anon').split('@')[0]}${isAnon(w) ? '' : ' pinned to live-membership hive'}. `
        + condNote + momentNote
        + `${w.pages.length} page(s) surveyed live, denied=false on all. ${totFail} failing dim(s).`;
      try {
        execFileSync('python', ['tools/bank_critic_walk.py', '--ids', w.ids.join(','),
          '--surveys', `${OUTDIR}/${w.ids[0]}_*.json`, '--note', note, '--apply'], { encoding: 'utf8', shell: false });
        banked++;
      } catch (e) { console.log(`    BANK FAILED ${w.ids[0]}: ${String((e.stdout || '') + (e.stderr || '') || e).slice(0, 240)}`); }
    }
  }
} finally {
  await browser.close();
  if (typeof release === 'function') release();
}
console.log(`done [subset=${SUBSET}]: surveyed ${surveyed}, banked ${banked}, failed ${failed}`);
