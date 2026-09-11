// prove_realtime_backfill — P-D "reconnect & backfill" over the pages that listen or poll (2026-09-05;
// P171 hive, P183 community, P177 platform-actions, P180 alert-hub; founder-console has its own prover).
// A row written while the page's connection is DOWN never arrives as a realtime event. The page must catch
// up on its own: a listening page re-reads on the first re-SUBSCRIBED after the drop (window._whRt marks it),
// a polling page re-reads on its next tick. Proof per case: sign in, open the page, cut the network, insert
// a tagged row straight into the database, restore the network, and the row must appear without a reload -
// or, for a page whose feed derives from views no single insert reaches (alert-hub), at least one data
// re-read must be observed after the network returns. The tagged row is deleted afterwards.
//   node tools/prove_realtime_backfill.mjs            # all cases; exit 1 on any that never caught up
//   node tools/prove_realtime_backfill.mjs --page hive.html
import { chromium } from 'playwright';
import { SEEDER, HIVE, WORKER, signIn, psql } from './prover_harness.mjs';   // shared preamble (2026-09-05)
const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const TAG = 'PRB-BACKFILL-' + Date.now();
const CASES = [
  { file: 'hive.html', kind: 'listen', target: '#feed', appearMs: 45000,
    insert: () => psql(`insert into logbook (hive_id, worker_name, date, machine, category, problem, action, status) values ('${HIVE}', '${WORKER.name}', now(), '${TAG}', 'Note', 'entry ${TAG} written while the board was offline', 'none', 'Open')`),
    cleanup: () => psql(`delete from logbook where machine = '${TAG}'`) },
  { file: 'community.html', kind: 'listen', target: '#feed-list', appearMs: 45000,
    insert: () => psql(`insert into community_posts (hive_id, author_name, content) values ('${HIVE}', '${WORKER.name}', 'post ${TAG} written while the feed was offline')`),
    cleanup: () => psql(`delete from community_posts where content like '%${TAG}%'`) },
  { file: 'platform-actions.html', kind: 'poll', target: '#fb-list', appearMs: 80000,   // refreshQueues every 60 s
    insert: () => psql(`insert into platform_feedback (kind, subject, body, is_public) values ('idea', '${TAG}', 'inserted while the console was offline', false)`),
    cleanup: () => psql(`delete from platform_feedback where subject = '${TAG}'`) },
  { file: 'alert-hub.html', kind: 'poll-refetch', appearMs: 80000 },   // loadAll every 60 s; the feed derives from views, so the proof is an observed re-read
];

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
await signIn(ctx);

let bad = 0, n = 0;
for (const c of CASES) {
  if (ONLY && c.file !== ONLY) continue;
  n++;
  const p = await ctx.newPage();
  let reads = 0, countReads = false; const trail = [], logs = [];
  p.on('request', (r) => { if (countReads && /\/rest\/v1\//.test(r.url())) reads++; });
  p.on('response', (r) => { if (countReads && /\/rest\/v1\//.test(r.url())) trail.push(r.status() + ' ' + r.url().replace(/^.*\/rest\/v1\//, '').slice(0, 40)); });
  p.on('console', (m) => { if (countReads && (m.type() === 'error' || m.type() === 'warning')) logs.push(m.text().slice(0, 90)); });
  await p.goto(`${SEEDER}/workhive/${c.file}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(9000);
  let joined = true;
  if (c.kind === 'listen') joined = await p.evaluate(() => !!(window._whRt) && typeof window.supabase !== 'undefined').catch(() => false);
  await ctx.setOffline(true);
  let down = null;
  if (c.kind === 'listen') down = await p.waitForFunction(() => window._whRt && window._whRt.wasDown === true, null, { timeout: 75000 }).then(() => true).catch(() => false);
  else await p.waitForTimeout(3000);
  if (c.insert) c.insert();
  countReads = true;
  await ctx.setOffline(false);
  let found = c.kind === 'poll-refetch' ? null : false;
  const t0 = Date.now();
  while (Date.now() - t0 < c.appearMs) {
    await p.waitForTimeout(1000);
    if (c.kind === 'poll-refetch') { if (reads > 0) { found = true; break; } }
    // textContent, not innerText: hive's feed lives in a panel that is hidden until its tab opens, and innerText of a hidden
    // container is EMPTY - the feed had painted 16 cards holding the tagged row while the check read '' (2026-09-05 probe)
    else { found = await p.evaluate(({ sel, tag }) => ((document.querySelector(sel) || {}).textContent || '').includes(tag), { sel: c.target, tag: TAG }).catch(() => false); if (found) break; }
  }
  const backfills = await p.evaluate(() => (window._whRt || {}).backfills ?? null).catch(() => null);
  const inState = await p.evaluate((tag) => { try { const st = window._feedEntries || window._posts || null; return st ? st.some((x) => JSON.stringify(x).includes(tag)) : null; } catch (e) { return null; } }, TAG).catch(() => null);   // fetched-but-not-painted vs never-fetched
  if (c.cleanup) c.cleanup();
  const ok = found === true;
  if (!ok) bad++;
  if (!ok) console.log(`      row in page state (_feedEntries/_posts): ${inState}`);
  if (!ok) console.log(`      after reconnect: ${trail.slice(0, 8).join(' | ') || 'no REST responses'}${logs.length ? '\n      console: ' + logs.slice(0, 4).join(' | ') : ''}`);
  console.log(`  ${ok ? 'ok ' : 'BAD'} ${c.file.padEnd(24)} ${c.kind.padEnd(12)} joined=${joined}${down === null ? '' : ' dropNoticed=' + down} -> ${c.kind === 'poll-refetch' ? 'data re-reads after reconnect=' + reads : 'offline-inserted row appeared=' + found} in ${Math.round((Date.now() - t0) / 1000)}s${backfills === null ? '' : ' · backfill passes=' + backfills}`);
  await p.close();
}
await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} realtime-backfill - ${n - bad}/${n} pages catch up on their own after a connection drop`);
process.exit(bad ? 1 : 0);
