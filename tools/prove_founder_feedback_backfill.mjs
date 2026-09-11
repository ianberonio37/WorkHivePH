// prove_founder_feedback_backfill — P-D "reconnect & backfill" on founder-console (P186, 2026-09-05).
// The feedback inbox listens to platform_feedback INSERTs over realtime. Rows inserted while the channel is
// DOWN never arrive as events; the page must re-read the inbox on the first SUBSCRIBED after a drop. Proof:
// admin signs in, the channel joins, the network is cut, a row is inserted straight into the database, the
// network returns, and the row's card must appear in #fb-list without a manual refresh.
//   node tools/prove_founder_feedback_backfill.mjs
import { chromium } from 'playwright';
import { SEEDER, signIn, psql } from './prover_harness.mjs';   // shared preamble (2026-09-05)
const TAG = 'PRB-BACKFILL-' + Date.now();

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
await signIn(ctx);
const p = await ctx.newPage();
await p.goto(`${SEEDER}/workhive/founder-console.html`, { waitUntil: 'load' });
const joined = await p.waitForFunction(() => typeof _fb !== 'undefined' && _fb.channel && _fb.channel.state === 'joined', null, { timeout: 30000 }).then(() => true).catch(() => false);
const cardsBefore = await p.evaluate(() => document.querySelectorAll('#fb-list .fb-card').length);
console.log(`  channel joined=${joined} · inbox cards=${cardsBefore}`);
if (!joined) { console.log('FAIL founder-feedback-backfill - the feedback channel never joined (is supabase realtime up?)'); await b.close(); process.exit(1); }

await ctx.setOffline(true);
// wait for the channel to notice the drop (heartbeat ~30s) - the page marks _fb.wasDown on CLOSED/TIMED_OUT/CHANNEL_ERROR
const down = await p.waitForFunction(() => typeof _fb !== 'undefined' && _fb.wasDown === true, null, { timeout: 75000 }).then(() => true).catch(() => false);
console.log(`  network cut -> channel noticed the drop=${down}`);
psql(`insert into platform_feedback (kind, subject, body, is_public) values ('idea', '${TAG}', 'inserted while the console was offline', false)`);
await ctx.setOffline(false);
let found = false;
for (let i = 0; i < 40; i++) { await p.waitForTimeout(1000); found = await p.evaluate((tag) => (document.getElementById('fb-list')?.innerText || '').includes(tag), TAG); if (found) break; }
const rejoined = await p.evaluate(() => typeof _fb !== 'undefined' && _fb.channel && _fb.channel.state === 'joined');
console.log(`  network back -> channel rejoined=${rejoined} · offline-inserted row in the inbox=${found}`);
psql(`delete from platform_feedback where subject = '${TAG}'`);
await b.close();
console.log(`${found ? 'PASS' : 'FAIL'} founder-feedback-backfill - ${found ? 'a row inserted during the drop appears after reconnect without a manual refresh' : 'the offline-inserted row never appeared after reconnect'}`);
process.exit(found ? 0 : 1);
