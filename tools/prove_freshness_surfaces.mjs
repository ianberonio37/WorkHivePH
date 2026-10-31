// prove_freshness_surfaces — KEEP ABREAST lens R, read from PRODUCTION: do a public page's five freshness surfaces agree?
// (Wave KA, 2026-10-30)
//
// A public page carries its freshness in five places (tools/refresh_public_page.py names them), each written by a different
// hand, and they drift apart: the JSON-LD dateModified a crawler reads, the visible "Last updated" line a person reads, the
// sitemap's <lastmod> the index schedules on, the markdown twin an agent fetches, and the IndexNow push that tells the
// index the page changed. A gate over the repository proves the files agree; the page a person and a crawler meet is the
// one production serves. So for every <loc> production's own sitemap lists, this reads all five from the deployed origin:
//   jsonld    the page's JSON-LD dateModified                                  (raw fetch, what a crawler receives)
//   visible   the "Last updated" <time datetime> the person sees - rendered, and visible, at phone-390 AND desktop-1280
//   lastmod   the sitemap's <lastmod> for the URL
//   twin      the deployed markdown twin is the repository's twin, byte for byte (the build the page came from)
//   pushed    indexnow_receipts.json holds a push for the URL on or after its <lastmod>
// and the page is inside its kind's window or holds an open refresh (freshness_trip's report: no refresh trip for it).
// The row passes when the three dates are one date, the twin is current and the push came after the change.
//
//   node tools/prove_freshness_surfaces.mjs [--limit N]   -> freshness_surfaces_report.json; exit 1 on any page that disagrees
//   node tools/prove_freshness_surfaces.mjs --teeth       a planted <lastmod> a day early for one URL must FAIL
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync } from 'fs';

const PROD = 'https://workhiveph.com';
const UA = 'WorkHive-Freshness-Prover/1.0';
const args = process.argv.slice(2);
const TEETH = args.includes('--teeth');
const LIMIT = (() => { const i = args.indexOf('--limit'); return i >= 0 ? Number(args[i + 1]) : Infinity; })();
const OUT = TEETH ? 'freshness_surfaces_teeth.json' : 'freshness_surfaces_report.json';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function get(url) {
  for (let i = 0; i < 3; i++) {
    try {
      const r = await fetch(url, { headers: { 'User-Agent': UA }, redirect: 'follow' });
      return { status: r.status, text: await r.text(), url: r.url, redirected: r.redirected };
    } catch (e) { await sleep(800); }
  }
  return { status: 0, text: '', url, redirected: false };
}
const localOf = (loc) => { const p = new URL(loc).pathname.replace(/^\//, ''); return (!p || p.endsWith('/')) ? p + 'index.html' : p; };
const jsonldDate = (html) => {
  for (const m of html.matchAll(/<script[^>]+application\/ld\+json[^>]*>([\s\S]*?)<\/script>/gi)) {
    const hit = m[1].match(/"dateModified"\s*:\s*"(\d{4}-\d{2}-\d{2})/);
    if (hit) return hit[1];
  }
  return null;
};

const sm = await get(`${PROD}/sitemap.xml`);
if (sm.status !== 200) { console.log(`FAIL freshness-surfaces: production's sitemap answered ${sm.status}`); process.exit(1); }
const entries = [...sm.text.matchAll(/<url>([\s\S]*?)<\/url>/g)].map((m) => ({
  loc: (m[1].match(/<loc>([^<]+)<\/loc>/) || [])[1], lastmod: (m[1].match(/<lastmod>([^<]+)<\/lastmod>/) || [])[1] || null,
})).filter((e) => e.loc).slice(0, LIMIT);
if (TEETH && entries.length) {   // a lastmod one day early: the surfaces no longer agree, and the prover must say so
  const d = new Date(entries[0].lastmod + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() - 1);
  entries[0].lastmod = d.toISOString().slice(0, 10);
}
const receipts = existsSync('indexnow_receipts.json') ? JSON.parse(readFileSync('indexnow_receipts.json', 'utf8')) : {};
const pushed = receipts.pushed || {};
const trip = existsSync('seo_trip_report.json') ? JSON.parse(readFileSync('seo_trip_report.json', 'utf8')) : { trips: [] };
const refreshTrips = new Set((trip.trips || []).filter((t) => t.kind === 'refresh').map((t) => t.unit));

const browser = await chromium.launch({ headless: true });
const ctxs = {
  'phone-390': await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, serviceWorkers: 'block' }),
  'desktop-1280': await browser.newContext({ viewport: { width: 1280, height: 800 }, serviceWorkers: 'block' }),
};
const rows = {};
let failed = 0;
for (const e of entries) {
  const local = localOf(e.loc);
  const page = await get(e.loc);
  const jsonld = jsonldDate(page.text);
  // the line a person reads, rendered and visible, at both widths
  const visible = {};
  for (const [vp, ctx] of Object.entries(ctxs)) {
    const p = await ctx.newPage();
    try {
      await p.goto(e.loc, { waitUntil: 'domcontentloaded', timeout: 45000 });
      visible[vp] = await p.evaluate(() => {
        for (const t of document.querySelectorAll('time[datetime]')) {
          const line = t.closest('p, div, footer, span') || t;
          if (/last updated/i.test(line.textContent || '')) {
            const shown = t.checkVisibility ? t.checkVisibility() : true;
            if (shown || (window.scrollTo(0, document.body.scrollHeight), t.checkVisibility && t.checkVisibility())) return t.getAttribute('datetime').slice(0, 10);
            return 'hidden:' + t.getAttribute('datetime').slice(0, 10);
          }
        }
        return null;
      });
    } catch (err) { visible[vp] = 'error: ' + String(err.message || err).slice(0, 60); }
    finally { await p.close().catch(() => {}); }
  }
  // the twin as deployed against the twin the repository builds
  const twinUrl = new URL(e.loc); twinUrl.pathname = '/' + local + '.md';
  const twin = await get(twinUrl.toString());
  const repoTwin = existsSync(local + '.md') ? readFileSync(local + '.md', 'utf8') : null;
  const twinCurrent = twin.status === 200 && repoTwin !== null && twin.text.replace(/\r\n/g, '\n').trim() === repoTwin.replace(/\r\n/g, '\n').trim();
  const push = pushed[e.loc] || pushed[e.loc.replace(/\/$/, '')] || null;
  const pushedAfter = !!(push && e.lastmod && push.at.slice(0, 10) >= e.lastmod && Number(push.response) === 200);
  const dates = [jsonld, visible['phone-390'], visible['desktop-1280'], e.lastmod];
  const oneDate = dates.every((d) => d && d === e.lastmod);
  const inWindow = !refreshTrips.has(local) && !refreshTrips.has(local.replace(/\/index\.html$/, ''));
  const ok = page.status === 200 && oneDate && twinCurrent && pushedAfter && inWindow;
  if (!ok) failed++;
  rows[e.loc] = { local, ok, status: page.status, served_at: page.url, jsonld, visible, lastmod: e.lastmod,
    twin: twinCurrent ? 'current' : `${twin.status}${repoTwin === null ? ' (no repo twin)' : ' (differs from the repository)'}`,
    pushed: push ? `${push.at.slice(0, 10)} (${push.response})` : 'never', pushed_after_change: pushedAfter, in_window: inWindow };
  const why = ok ? '' : ` - ${!oneDate ? `dates ${JSON.stringify(dates)}` : ''}${!twinCurrent ? ' twin ' + rows[e.loc].twin : ''}${!pushedAfter ? ' push ' + rows[e.loc].pushed : ''}${!inWindow ? ' refresh due' : ''}${page.status !== 200 ? ' status ' + page.status : ''}`;
  console.log(`  ${ok ? 'ok ' : 'BAD'} ${e.loc.replace(PROD, '') || '/'}${why}`);
}
await browser.close();
writeFileSync(OUT, JSON.stringify({ ran: new Date().toISOString(), origin: PROD, teeth: TEETH, urls: entries.length, failed, rows }, null, 1));
if (TEETH) {
  const first = entries[0] && rows[entries[0].loc];
  const bit = first && !first.ok;
  console.log(`${bit ? 'PASS' : 'FAIL'} freshness-surfaces teeth: a <lastmod> one day early ${bit ? 'reads as surfaces that disagree' : 'went unnoticed'}`);
  process.exitCode = bit ? 0 : 1;
} else {
  console.log(`${failed ? 'FAIL' : 'PASS'} freshness-surfaces: ${entries.length - failed}/${entries.length} public pages on production carry one date on all five surfaces`);
  process.exitCode = failed ? 1 : 0;
}
