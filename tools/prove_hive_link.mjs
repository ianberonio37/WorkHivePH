// prove_hive_link.mjs - a link that names its hive opens in it, for a member only (GJ G-MULTI, 2026-11-05).
//
// A push now carries ?hive=<id> (mig 20261105000003) and the shared start-up (utils.js whStartupHive -> _whSeatLinkedHive)
// seats that hive when the signed-in account is an active member of it. Two cases, one person who belongs to two hives,
// on logbook.html (one of the 27 pages that seat their hive through whStartupHive), at phone width:
//   1. MEMBER: standing in hive A, a link naming hive B -> the page stands in B, says "Opened in <B>", and the address
//      bar no longer carries ?hive=;
//   2. NOT A MEMBER: a link naming a hive the person is not in -> the page stays in the hive it had and says the link is
//      for a hive this account is not a member of; nothing is seated.
// Read-only: it writes nothing but the browser's own storage. Exit 0 = both hold. Receipt: .tmp/hive_link_report.json
//
//   node tools/prove_hive_link.mjs
import { chromium } from 'playwright';
import { spawnSync } from 'child_process';
import { writeFileSync, mkdirSync } from 'fs';

const ORIGIN = 'http://127.0.0.1:5000/workhive';
const SB = 'http://127.0.0.1:54321';
const KEY = 'sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH';   // the LOCAL stack's publishable key (public by design)
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function psql(sql) {
  const r = spawnSync('docker', ['exec', '-i', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-At', '-F', '|'], { input: sql, encoding: 'utf8' });
  if (r.status !== 0) throw new Error('psql: ' + (r.stderr || '').slice(0, 300));
  return (r.stdout || '').trim();
}

// a person active in two hives, and a third hive they are not in (read from the database, never typed)
const row = psql(`select w.username, w.display_name, a.hive_id, ha.name, b.hive_id, hb.name,
    (select h.id from hives h where not exists (select 1 from hive_members x where x.hive_id = h.id and x.auth_uid = w.auth_uid) order by h.name limit 1),
    (select h.name from hives h where not exists (select 1 from hive_members x where x.hive_id = h.id and x.auth_uid = w.auth_uid) order by h.name limit 1)
  from worker_profiles w
  join hive_members a on a.auth_uid = w.auth_uid and a.status = 'active'
  join hive_members b on b.auth_uid = w.auth_uid and b.status = 'active' and b.hive_id > a.hive_id
  join hives ha on ha.id = a.hive_id join hives hb on hb.id = b.hive_id
  order by w.username limit 1`);
if (!row) { console.log('FAIL - no person active in two hives'); process.exit(1); }
const [user, name, hiveA, nameA, hiveB, nameB, hiveX, nameX] = row.split('|');

const tok = await (await fetch(`${SB}/auth/v1/token?grant_type=password`, { method: 'POST',
  headers: { apikey: KEY, 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: `${user}@auth.workhiveph.com`, password: 'test1234' }) })).json();
if (!tok.access_token) { console.log(`FAIL - sign-in failed for ${user}`); process.exit(1); }

const browser = await chromium.launch();
const results = [];
try {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, timezoneId: 'Asia/Manila', serviceWorkers: 'block' });
  await ctx.addInitScript(([t, hive, hiveName, who]) => {
    try {
      if (!localStorage.getItem('sb-127-auth-token')) localStorage.setItem('sb-127-auth-token', JSON.stringify(t));
      if (!localStorage.getItem('wh_active_hive_id')) { localStorage.setItem('wh_active_hive_id', hive); localStorage.setItem('wh_hive_name', hiveName); }
      localStorage.setItem('wh_last_worker', who);
    } catch (_) { /* storage blocked */ }
  }, [tok, hiveA, nameA, name]);
  const page = await ctx.newPage();
  const toastOf = () => page.evaluate(() => (document.getElementById('toast-text') || document.querySelector('.toast, [role="status"]') || {}).textContent || '').catch(() => '');
  async function follow(hive) {
    await page.goto(`${ORIGIN}/logbook.html?status=Open&hive=${hive}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
    let toast = '';
    // the toast element carries default text before any message ("Entry saved."), so wait for one of the two sentences
    for (let t = 0; t < 15000 && !/opened in|not a member/i.test(toast); t += 500) { await sleep(500); toast = await toastOf(); }
    await sleep(1000);
    return { seated: await page.evaluate(() => localStorage.getItem('wh_active_hive_id')), url: page.url(), toast: toast.trim() };
  }
  // 1. a member's link to their other hive
  const m = await follow(hiveB);
  results.push({ case: `member: standing in ${nameA}, a link naming ${nameB}`,
    ok: m.seated === hiveB && !/[?&]hive=/.test(m.url) && /opened in/i.test(m.toast),
    seated: m.seated === hiveB ? nameB : (m.seated === hiveA ? nameA : m.seated), url_keeps_param: /[?&]hive=/.test(m.url), toast: m.toast });
  // 2. a link to a hive the person is not in (now standing in B)
  const x = await follow(hiveX);
  results.push({ case: `not a member: standing in ${nameB}, a link naming ${nameX}`,
    ok: x.seated === hiveB && !/[?&]hive=/.test(x.url) && /not a member/i.test(x.toast),
    seated: x.seated === hiveB ? nameB : (x.seated === hiveX ? nameX : x.seated), url_keeps_param: /[?&]hive=/.test(x.url), toast: x.toast });
  await ctx.close();
} finally { await browser.close(); }

const ok = results.every((r) => r.ok);
mkdirSync('.tmp', { recursive: true });
writeFileSync('.tmp/hive_link_report.json', JSON.stringify({ generated: new Date().toISOString(), person: user, ok, results }, null, 1));
for (const r of results) console.log(`  ${r.ok ? 'ok  ' : 'FAIL'} ${r.case}: stands in ${r.seated}; param ${r.url_keeps_param ? 'KEPT' : 'removed'}; said "${r.toast}"`);
console.log(ok ? 'PASS - a link that names its hive opens in it for a member, and nowhere else' : 'FAIL - see above');
process.exit(ok ? 0 : 1);
