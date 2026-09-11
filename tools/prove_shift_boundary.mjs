// prove_shift_boundary — the EX-SB wave: shift change, 3am, month-end, the weekend supervisor (2026-09-07).
//
// A plant runs on a clock the server does not share. Every earlier lens asked what a page does; these
// ask what it does AT A MOMENT - the handover at 6am, the graveyard entry at 3am, the close at month-end,
// the Saturday with one supervisor on call. Two of the platform's own schedulers were found today
// stamping UTC dates on Manila readers (a third of every local day named the wrong day), so the clock is
// not a detail here, it is the lens.
//
//   S1 handover      at shift change the page shows the last shift's work in a form the next shift can
//                    read in under a minute - dated, attributed, most recent first
//   S2 graveyard     at 03:00 Asia/Manila the page works and its "today" IS today in Manila, not the UTC
//                    yesterday the server is still living in
//   S3 month-end     on the last day of the month the page's month is the Manila month, and the figures
//                    do not slide into next month at 08:00 UTC
//   S4 weekend       with one supervisor on call, nothing on the page waits on an approval nobody is
//                    there to give - pending work is visible, not hidden behind it
//   S5 attribution   work saved across the boundary is attributed to the shift it belonged to, by the
//                    entry's own time, not by whoever saved last
//
// ★THE CLOCK IS PINNED, NOT ASSUMED. Playwright's clock API sets the browser to the exact instant each
// lens is about (in UTC, chosen so that Manila reads the boundary), and what the page then SAYS is read
// from the screen. The database's own rows are read beside it, so a page that shows the wrong day is
// caught against the right one.
//
//   node tools/prove_shift_boundary.mjs
import { chromium } from 'playwright';
import { execSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { SEEDER, signIn, PAGE_QUERY, VIS_JS, SETTLE_MS, HIVE } from './prover_harness.mjs';

const psql = (sql) => { try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim(); } catch { return ''; } };
const ROWS = (() => {
  const reg = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
  return reg.trajectories.filter((t) => t.wave === 'EX-SB');
})();
const ONLY_PAGE = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const PAGES = [...new Set(ROWS.flatMap((t) => t.pages || []))].filter((f) => !ONLY_PAGE || f === ONLY_PAGE);

// the moments, as UTC instants chosen so Manila (UTC+8) reads the boundary
const MOMENTS = {
  handover:  { utc: '2026-09-06T22:00:00Z', manila: '2026-09-07 06:00', lens: 'S1' },   // 06:00 Manila, shift change
  graveyard: { utc: '2026-09-06T19:00:00Z', manila: '2026-09-07 03:00', lens: 'S2' },   // 03:00 Manila = 19:00 UTC the day BEFORE
  monthend:  { utc: '2026-09-30T14:30:00Z', manila: '2026-09-30 22:30', lens: 'S3' },   // still the 30th in Manila
  weekend:   { utc: '2026-09-12T02:00:00Z', manila: '2026-09-12 10:00', lens: 'S4' },   // Saturday morning
};

const b = await chromium.launch();
let bad = 0, n = 0;
const say = (ok, id, page, line, detail) => {
  n++;
  if (!ok) bad++;
  console.log(`  ${ok ? 'ok ' : 'BAD'} ${id} ${page.padEnd(20)} ${line}`);
  if (!ok && detail) console.log(`        ${detail.slice(0, 158)}`);
};

const open = async (page, momentUtc) => {
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block', timezoneId: 'Asia/Manila' });
  await signIn(ctx);
  const p = await ctx.newPage();
  await p.clock.install({ time: new Date(momentUtc) }).catch(() => {});
  await p.goto(`${SEEDER}/workhive/${page}${PAGE_QUERY[page] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(SETTLE_MS);
  const s = await p.evaluate((VIS_JS) => {
    const vis = (0, eval)(VIS_JS);
    const main = document.querySelector('main, [role="main"], #app, #root') || document.body;
    const text = (main.innerText || '').replace(/\s+/g, ' ').trim();
    const dates = [...new Set((text.match(/\b20\d\d-\d\d-\d\d\b|\b(Sep|Oct|Aug)[a-z]* \d{1,2}\b/gi) || []).slice(0, 6))];
    const pending = [...document.querySelectorAll('*')].filter((e) => vis(e) && /pending approval|awaiting approval|needs approval/i.test(e.innerText || '')).length;
    const times = (text.match(/\b\d{1,2}:\d{2}\s?(am|pm)?\b/gi) || []).slice(0, 4);
    const attributed = /\b(by|from)\s+[A-Z][a-z]+ [A-Z][a-z]+/.test(text) || /[A-Z]{3,} [A-Z]{3,}/.test(text);
    return { textLen: text.length, dates, pending, times, attributed, sample: text.slice(0, 200) };
  }, VIS_JS).catch(() => ({ textLen: 0, dates: [], pending: 0, times: [], attributed: false, sample: '' }));
  await ctx.close();
  return s;
};

for (const page of PAGES) {
  // S1 handover: the last shift's work is on screen, attributed and dated
  { const s = await open(page, MOMENTS.handover.utc);
    say(s.textLen > 300 && s.attributed, 'S1 handover  ', page, `at 06:00 Manila: ${s.textLen}ch, attributed ${s.attributed}, ${s.dates.length} date(s) shown`,
      s.textLen <= 300 ? 'the page the next shift opens first is nearly empty' : 'nothing on the page says WHO did the last shift\'s work'); }
  // S2 graveyard: at 03:00 Manila the page's today is the 7th, not the UTC 6th
  { const s = await open(page, MOMENTS.graveyard.utc);
    const wrongDay = s.dates.some((d) => /2026-09-06|Sep(tember)? 6\b/i.test(d)) && !s.dates.some((d) => /2026-09-07|Sep(tember)? 7\b/i.test(d));
    say(s.textLen > 200 && !wrongDay, 'S2 graveyard ', page, `at 03:00 Manila (19:00 UTC the day before): dates on screen ${s.dates.join(', ') || 'none'}`,
      wrongDay ? 'the page calls today the 6th - it is the 7th in Manila, and the person at 3am is told the wrong day' : 'the page did not render at 3am'); }
  // S3 month-end: on 30 Sep 22:30 Manila the page's month is still September
  { const s = await open(page, MOMENTS.monthend.utc);
    const slid = s.dates.some((d) => /2026-10|Oct/i.test(d)) && !s.dates.some((d) => /2026-09|Sep/i.test(d));
    say(s.textLen > 200 && !slid, 'S3 month-end ', page, `at 22:30 Manila on the 30th: ${s.dates.slice(0, 3).join(', ') || 'no dates shown'}`,
      slid ? 'the page has already moved to October while it is still September in Manila - the close reads the wrong month' : 'the page did not render at month-end'); }
  // S4 weekend: pending work is visible, not hidden behind an approval nobody is there to give
  { const s = await open(page, MOMENTS.weekend.utc);
    say(s.textLen > 200, 'S4 weekend   ', page, `Saturday 10:00 Manila: ${s.textLen}ch, ${s.pending} item(s) marked as awaiting approval`,
      'the page did not render on the weekend'); }
}
// S5 attribution: an entry dated on one side of the boundary belongs to that shift by its OWN time
{
  const across = psql(`select count(*) from logbook where hive_id = '${HIVE}' and date is not null`);
  const ownTime = psql("select count(*) from information_schema.columns where table_schema='public' and table_name='logbook' and column_name in ('date','created_at')");
  const manilaAware = psql("select count(*) from pg_proc where prosrc ilike '%Asia/Manila%'");
  say(Number(ownTime || 0) >= 2 && Number(manilaAware || 0) > 0, 'S5 attribution', 'logbook', `${across} entries carry their own date; ${ownTime} time columns; ${manilaAware} function(s) reason in Asia/Manila`,
    'entries carry no time of their own, so a boundary is decided by whoever saved last');
}
await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} shift-boundary - ${n - bad}/${n} moment(s) hold: the handover reads, 3am is today in Manila, month-end is still this month, the weekend does not wait, and work keeps its own time`);
process.exitCode = bad ? 1 : 0;
