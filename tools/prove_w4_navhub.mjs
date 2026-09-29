// prove_w4_navhub.mjs - the RATCHET for the wave-4 nav-hub rows (2026-09-14).
//
// §LW.2: the MCP walk DISCOVERS (a person-shaped walk with each reading decided before the next step); the batch
// prover RE-PROVES in bulk what the walk established, and is what a gate is. This runs THE SAME HANDS the MCP walk
// used - tools/w4_navhub_walk.js, loaded as a function - over every W4 nav-hub row of one axis, in a fresh
// headless context per row, cast as a worker of the row's own hive, and writes a receipt in the shape the
// live-walk ledger already reads (.tmp/full_journeys_w4navhub_<axis>.json, merged by id, instrument named).
//
// A row is OK only when: every step arrived as itself (>=120 chars) with the identity kept, the viewport was the
// axis's, all 11 hub control groups were exercised, and NO per-step record carries an overlap / occlusion /
// element-overflow finding - a finding is the story failing ("no control occluded at any step"), never a note.
//
//   node tools/prove_w4_navhub.mjs --axis "phone-390 en"            # all 31 hosts on one axis (the gate)
//   node tools/prove_w4_navhub.mjs --axis "narrow-320 en" --host achievements.html
//   node tools/prove_w4_navhub.mjs --ids W41366,W41367 --limit 2
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { takeBrowserSlot } from './browser_slot.mjs';

// ★THE RECEIPT MUST SAY WHEN THE WALK BEGAN, not only when it ended (2026-09-16). `generated` is
// stamped at the finish, and a 30-host walk takes ~40 minutes - so a file edited at minute 20
// invalidates every host after it while still being OLDER than `generated`. That is how a 30/30 green
// receipt came to describe a mixture of two builds: the type-floor sweep rewrote 143 served pages
// underneath a walk that was already running, and nothing in the pipeline could see it.
// tools/bank_navhub_axis.py refuses a receipt older than any served-page edit; with this stamp it can
// compare against the real start instead of approximating it as `generated - 75 min`.
const STARTED_AT = new Date().toISOString();

const args = process.argv.slice(2);
const argOf = (f) => { const i = args.indexOf(f); return i >= 0 ? args[i + 1] : null; };
const AXIS = argOf('--axis') || 'phone-390 en';
const HOST = argOf('--host');
const IDS = (argOf('--ids') || '').split(',').filter(Boolean);
const LIMIT = Number(argOf('--limit') || 0);
const ORIGIN = process.env.WH_SEEDER_URL ? `${process.env.WH_SEEDER_URL}/workhive` : 'http://localhost:5000/workhive';
const WALK = eval('(' + readFileSync('tools/w4_navhub_walk.body.js', 'utf8') + '\n)');
const AUDIT = readFileSync('tools/phone_fit_audit.browser.js', 'utf8');

// the cast: a WORKER of the row's own hive, from the database, never invented (the wave-3 rule). The account's
// username is the local part of its e-mail (index.html builds the account that way), password the seed default.
const psql = (sql) => { try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8', timeout: 30000 }).trim(); } catch (e) { return ''; } };
const CAST = {};
for (const line of psql("select h.name||'|'||m.worker_name||'|'||m.role||'|'||coalesce(u.email,'') from hives h join hive_members m on m.hive_id = h.id left join auth.users u on u.id = m.auth_uid where m.status = 'active' order by h.name, m.role, m.worker_name").split('\n')) {
  const [hive, worker, role, email] = line.split('|');
  if (!hive || !email) continue;
  CAST[hive] = CAST[hive] || {};
  if (role === 'worker' && !CAST[hive].worker) CAST[hive].worker = { name: worker, email, user: email.split('@')[0] };
  if (role !== 'worker' && !CAST[hive].supervisor) CAST[hive].supervisor = { name: worker, email, user: email.split('@')[0] };
}

const reg = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
let rows = reg.trajectories.filter((t) => (t.w4 || {}).kind === 'nav-hub' && `${(t.axis || {}).device} ${(t.axis || {}).language}` === AXIS);
if (HOST) rows = rows.filter((t) => t.w4.host === HOST);
if (IDS.length) rows = rows.filter((t) => IDS.includes(t.id));
if (LIMIT) rows = rows.slice(0, LIMIT);
if (!rows.length) { console.log(`PASS w4-nav-hub - no W4 nav-hub row on axis "${AXIS}"${HOST ? ' for ' + HOST : ''} (nothing to re-prove)`); process.exit(0); }

const [device, lang] = AXIS.split(' ');
const viewport = device === 'narrow-320' ? { width: 320, height: 720 } : { width: 390, height: 844 };
const release = await takeBrowserSlot('prove_w4_navhub');
const browser = await chromium.launch();
const results = [];
let bad = 0;
try {
  for (const t of rows) {
    const hive = (t.journey || {}).vertical || '';
    const c = CAST[hive] || {};
    const who = c.worker || c.supervisor;
    // deviceScaleFactor 1, not 2 (2026-09-14): a retina (2x) backing buffer QUADRUPLES the renderer's pixel
    // memory, which OOM-crashed the headless context on heavy pages (engineering-design 2.14MB, analytics, index,
    // pm-scheduler: "Target page/context/browser has been closed" at page load, 0 steps) on this 8GB host. The
    // phone CSS px (390) are unchanged - only the backing buffer shrinks 4x - so the occlusion geometry the walk
    // measures is identical, and the heavy hosts can finally be walked. Lighter pages were unaffected either way.
    const ctx = await browser.newContext({ viewport, isMobile: true, hasTouch: true, deviceScaleFactor: 1, locale: lang === 'fil' ? 'fil-PH' : 'en-PH', serviceWorkers: 'block' });
    const page = await ctx.newPage();
    await page.addInitScript({ content: AUDIT });
    globalThis.__W4 = { id: t.id, host: t.w4.host, axis: AXIS, width: viewport.width, height: viewport.height, lang,
      stops: (t.pages || []).slice(1), user: who ? who.user : 'romeobeltran', pass: 'test1234', castName: who ? who.name : 'Romeo Beltran', origin: ORIGIN };
    let r = null, err = null;
    try { r = await WALK(page); } catch (e) { err = String(e.message || e).slice(0, 160); }
    await ctx.close().catch(() => {});
    const problems = [];
    if (err) problems.push(`the walk threw: ${err}`);
    if (r) {
      for (const p of (r.problems || [])) problems.push(p);
      if (!r.hostStep || r.hostStep.chars < 120) problems.push(`${t.w4.host}: rendered ${r.hostStep ? r.hostStep.chars : 0} characters`);
      if (r.hostStep && !r.hostStep.identityKept) problems.push('identity did not survive the arrival');
      for (const s of (r.onward || [])) { if (s.loadError) problems.push(`${s.page}: ${s.loadError}`); else if ((s.chars || 0) < 120) problems.push(`${s.page}: rendered ${s.chars} characters`); else if (!s.identityKept) problems.push(`${s.page}: identity did not survive the hop`); }
      if (!r.hub || r.hub.controls < 11) problems.push(`${r.hub ? r.hub.controls : 0} of 11 hub control groups exercised`);
      for (const f of (r.findings || [])) problems.push(`overlap at "${f.step}": ${[...(f.occlusion || []), ...(f.overflowEl || []), ...(f.outside || []), ...(f.wrapped || []), ...(f.clipped || []), ...(f.spill || [])].slice(0, 2).join(' | ').slice(0, 160)}`);
      if (r.hub && r.hub.closed && r.hub.closed.focusOn !== 'wh-hub-fab') problems.push(`after closing the hub focus is on ${r.hub.closed.focusOn}, not the fab`);
      if (r.summary && r.summary.vw !== viewport.width) problems.push(`viewport ${r.summary.vw}, not ${viewport.width}`);
    }
    const ok = !problems.length;
    if (!ok) bad++;
    results.push({ id: t.id, ok, unbuilt: !who, instrument: 'tools/prove_w4_navhub.mjs', condition: 'normal', cast: who ? `${who.name} (${hive})` : `no active member with an account in ${hive}`, problems,
      note: r ? `${r.summary ? r.summary.records : 0} per-step records, ${r.summary ? r.summary.withFindings : 0} with findings; ${r.hub ? r.hub.controls : 0}/11 hub controls; confusions ${(r.confusions || []).length}` : 'no walk',
      metrics: { arrived: r ? 1 + (r.onward || []).filter((s) => !s.loadError && (s.chars || 0) >= 120).length : 0, steps: r ? 1 + (r.onward || []).length : 0, idKept: r ? !!(r.hostStep && r.hostStep.identityKept && (r.onward || []).every((s) => s.identityKept !== false)) : false },
      w4: { axis: AXIS, hub_controls: r && r.hub ? r.hub.controls : 0 },
      // ★WRITE THE PER-PAGE STEPS (with fit) the walk collected, or live_walk_manifest._w4_missing rejects every
      // nav-hub row for "fewer than 4 pages / no overlap record" and nothing here can ever close (2026-09-14).
      steps: r && Array.isArray(r.steps) ? r.steps.map((s) => ({ page: s.page, chars: s.chars, identityKept: s.identityKept, fit: s.fit })) : [],
      confusions: r ? r.confusions : [] });
    console.log(`  ${ok ? 'ok  ' : 'BAD '} ${t.id.padEnd(7)} ${t.w4.host.padEnd(30)} ${who ? who.name.padEnd(22) : 'NO CAST'.padEnd(22)} ${problems.length ? problems[0].slice(0, 110) : (r && r.summary ? `${r.summary.records} records, ${r.hub.controls}/11 controls, 0 findings` : '')}`);
  }
} finally {
  await browser.close().catch(() => {});
  await release();
}
mkdirSync('.tmp', { recursive: true });
const outFile = `.tmp/full_journeys_w4navhub_${AXIS.replace(/[^A-Za-z0-9]+/g, '-')}${HOST ? '_' + HOST.replace(/[^A-Za-z0-9]+/g, '-') : ''}.json`;
let merged = results;
try { if (existsSync(outFile)) { const prior = JSON.parse(readFileSync(outFile, 'utf8')); const now = new Map(results.map((r) => [r.id, r])); merged = (prior.results || []).map((r) => now.get(r.id) || r).concat(results.filter((r) => !(prior.results || []).some((p) => p.id === r.id))); } } catch (e) { void e; }
writeFileSync(outFile, JSON.stringify({ generated: new Date().toISOString(), startedAt: STARTED_AT, instrument: 'tools/prove_w4_navhub.mjs', axis: AXIS, walked: results.length, bad, results: merged }, null, 1));
console.log(`${bad ? 'FAIL' : 'PASS'} w4-nav-hub@${AXIS} - ${results.length - bad}/${results.length} nav-hub journeys hold (every control exercised, no control occluded at any step, focus returned) · ${outFile}`);
process.exit(bad ? 1 : 0);
