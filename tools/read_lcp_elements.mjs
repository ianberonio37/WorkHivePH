/**
 * WHAT is each page's Largest Contentful Paint, actually? (T37, 2026-08-28)
 *
 * Every CWV instrument on this platform reports LCP as a NUMBER. None of them reports the
 * ELEMENT, and the element is what tells you whether the number means anything: LCP exists as a
 * proxy for "the user can see the main content", and that proxy only holds if the largest early
 * paint IS the main content.
 *
 * FIRST CENSUS, 12 pages at 390px, signed in: the LCP element was chrome on ALL TWELVE — a page
 * subtitle, a verdict caption, an H1, an instructional line, or (on asset-hub, marketplace and
 * shift-brain) the wh-source-chip, which is metadata ABOUT the data rather than the data. This is
 * structural rather than sloppy: these pages render their content after an async read, so at LCP
 * time the largest painted thing is necessarily the shell. The consequence is worth stating
 * plainly — a CWV score for these pages grades how fast the FRAME arrives, not the answer.
 *
 * ★AND THE PAGE WITH THE BEST NUMBER HAD THE LEAST CONTENT. dayplanner posted the platform's
 * fastest LCP, 100ms, on DIV.aurora-bg — a `position:fixed; inset:0; pointer-events:none`
 * decorative gradient with no text in it at all. It is not merely chrome-instead-of-content; it is
 * a decoration counted as content, which makes the healthiest-looking score on the board the one
 * standing for the least. The impossibly-good number is the instrument again.
 *
 * This is a RECORDER, deliberately. Asserting "LCP must be a content element" would redden all
 * twelve pages for an architectural property no single fix changes, which is teaching the gate a
 * state we do not have. What it does is make the element visible so the number can be read
 * honestly, and so a page that regresses INTO a decorative LCP is noticeable.
 *
 * USAGE:  node tools/read_lcp_elements.mjs
 * Exit 0 always.
 */
import { chromium } from 'playwright';

const BASE = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SB_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
const ACCT = { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234',
               worker: 'leandromarquez', hiveName: 'Baguio' };
const PAGES = ['index.html', 'logbook.html', 'pm-scheduler.html', 'asset-hub.html', 'alert-hub.html',
               'analytics.html', 'inventory.html', 'community.html', 'marketplace.html', 'hive.html',
               'dayplanner.html', 'shift-brain.html'];

// Buffered, so an LCP that fired before this script ran is still seen.
const OBS = `window.__lcp=null;try{new PerformanceObserver(l=>{const es=l.getEntries();const e=es[es.length-1];
 if(e){const el=e.element;window.__lcp={t:Math.round(e.startTime),tag:el?el.tagName:'?',
 id:el&&el.id?el.id:'',cls:el&&el.className&&typeof el.className==='string'?el.className.slice(0,44):'',
 txt:(el&&(el.innerText||el.alt||'')||'').replace(/\\s+/g,' ').trim().slice(0,52)};}})
 .observe({type:'largest-contentful-paint',buffered:true});}catch(e){}`;

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
const auth = await ctx.newPage();
await auth.goto(`${BASE}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
await auth.waitForFunction(() => !!(window.supabase && window.supabase.createClient) && !!window.SUPABASE_KEY,
                           { timeout: 20000 }).catch(() => {});
await auth.evaluate(async ({ acct, url }) => {
  try {
    const db = window._whSupabaseClient || window.getDb(url, window.SUPABASE_KEY);
    const { data } = await db.auth.signInWithPassword({ email: acct.email, password: acct.pw });
    const uid = data?.session?.user?.id;
    const { data: m } = uid ? await db.from('hive_members').select('hive_id')
      .eq('auth_uid', uid).eq('status', 'active').limit(1).maybeSingle() : { data: null };
    if (m?.hive_id) { localStorage.setItem('wh_active_hive_id', m.hive_id); localStorage.setItem('wh_hive_id', m.hive_id); }
    localStorage.setItem('wh_last_worker', acct.worker);
    localStorage.setItem('wh_hive_name', acct.hiveName);
    localStorage.setItem('wh_hive_role', 'supervisor');
  } catch (e) { /* the census still runs signed-out; rows just reflect that */ }
}, { acct: ACCT, url: SB_URL });
await auth.close();

console.log('lcp-elements - WHAT is each page\'s largest contentful paint?\n');
console.log('  page                   LCP(ms)  element                              text');
let decorative = 0, chip = 0;
for (const pg of PAGES) {
  const p = await ctx.newPage();
  await p.addInitScript(OBS);
  try {
    await p.goto(`${BASE}/workhive/${pg}`, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await p.waitForTimeout(5000);
    const r = await p.evaluate(() => window.__lcp);
    if (!r) { console.log(`  ${pg.padEnd(22)} (no LCP entry)`); }
    else {
      const el = `${r.tag}${r.id ? '#' + r.id : ''}${r.cls ? '.' + r.cls.split(/\s+/)[0] : ''}`;
      const flag = !r.txt ? '  <- DECORATIVE: no text in the largest "contentful" paint'
                 : /source-chip/.test(r.cls) ? '  <- provenance chip, not the data' : '';
      if (!r.txt) decorative++;
      if (/source-chip/.test(r.cls)) chip++;
      console.log(`  ${pg.padEnd(22)} ${String(r.t).padStart(6)}  ${el.padEnd(36)} ${JSON.stringify(r.txt)}${flag}`);
    }
  } catch (e) { console.log(`  ${pg.padEnd(22)} ERROR ${String(e).slice(0, 50)}`); }
  await p.close();
}
await browser.close();
console.log(`\n  ${PAGES.length} pages · ${decorative} with a text-less (decorative) LCP · ${chip} whose LCP is the source chip`);
console.log('  exit 0 by design: a RECORDER. LCP being chrome here is architectural (content renders after an async read);');
console.log('  what this makes visible is that a CWV score for these pages grades the frame, not the answer.');
process.exit(0);
