// probe_hive_feed_render — one-off probe (2026-09-05, P171): the hive backfill prover showed the refetch RUNNING after
// reconnect (200s on v_logbook_truth) yet the tagged logbook row never painted. Separate the halves: signed in, online,
// insert a tagged row, call the page's own loadFeed(), then report whether the row is in the feed read's response, in
// the page's state, and in #feed's text - and what the first card actually paints.
import { chromium } from 'playwright';
import { SEEDER, HIVE, WORKER, signIn, psql } from './prover_harness.mjs';
const TAG = 'PRB-FEEDRENDER-' + Date.now();
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
await signIn(ctx);
const p = await ctx.newPage();
const feedReads = [];
p.on('response', async (r) => { if (/v_logbook_truth/.test(r.url()) && /limit=40/.test(r.url())) { try { const j = await r.json(); feedReads.push({ status: r.status(), n: Array.isArray(j) ? j.length : -1, hasTag: JSON.stringify(j).includes(TAG), first: Array.isArray(j) && j[0] ? Object.keys(j[0]).slice(0, 12).join(',') : '' }); } catch (e) { feedReads.push({ status: r.status(), err: e.message }); } } });
await p.goto(`${SEEDER}/workhive/hive.html`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
await p.waitForTimeout(9000);
const before = await p.evaluate(() => (document.getElementById('feed')?.innerText || '').replace(/\s+/g, ' ').slice(0, 160));
psql(`insert into logbook (hive_id, worker_name, date, machine, category, problem, action, status) values ('${HIVE}', '${WORKER.name}', now(), '${TAG}', 'Note', 'entry ${TAG} inserted for the render probe', 'none', 'Open')`);
const inView = psql(`select count(*) from v_logbook_truth where machine = '${TAG}'`);
const called = await p.evaluate(async () => { try { if (typeof loadFeed === 'function') { await loadFeed(); return 'loadFeed() awaited'; } return 'loadFeed not a function'; } catch (e) { return 'loadFeed threw: ' + e.message; } });
await p.waitForTimeout(3000);
// textContent, not innerText: the feed panel may be hidden (innerText of a hidden container is '')
const after = await p.evaluate((tag) => { const f = document.getElementById('feed'); const t = (f?.textContent || '').replace(/\s+/g, ' '); return { hasTag: t.includes(tag), len: t.length, head: t.slice(0, 220), firstCard: (f?.firstElementChild?.outerHTML || '').slice(0, 400), cards: f ? f.children.length : -1 }; }, TAG);
psql(`delete from logbook where machine = '${TAG}'`);
await b.close();
console.log(`  row in v_logbook_truth: ${inView} · ${called}\n  feed reads (limit=40): ${JSON.stringify(feedReads)}\n  #feed before: "${before}"\n  #feed after: cards=${after.cards} len=${after.len} hasTag=${after.hasTag}\n  head: "${after.head}"\n  first card: ${after.firstCard}`);
process.exit(after.hasTag ? 0 : 1);
