// frontend_i6_secrets.mjs — Arc D / D2 Internal-Control, the I6 "safe-by-default / no
// secrets in the client" bar (the critical security signal of the I lens).
//
// REUSE (not reinvent): signs in ONCE (the frontend_ufai_sweep recipe), then on each
// page injects ufai_battery.js and runs its referee — whose internalControl() already
// scans localStorage + DOM body for service_role / sk- / AIza / PRIVATE KEY / JWT
// shapes. We capture scores.I (secretExposures + the 'secret-exposed' defects) +
// destructiveControls + sourceChips. A clean run = no privileged key shipped to the
// browser. Writes frontend_i6_secrets.json.
import { chromium } from 'playwright';
import { readFileSync, writeFileSync } from 'fs';

const SEEDER = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const EMAIL = process.env.WH_TEST_EMAIL || 'leandromarquez@auth.workhiveph.com';
const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const HIVE = '9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7';
const BATTERY_SRC = readFileSync('ufai_battery.js', 'utf8');

// Every authed page a member can actually open (skip the gated admin/seller set whose
// authed render needs another role — those carry no member secrets anyway).
const PAGES = [
  'engineering-design','logbook','inventory','pm-scheduler','voice-journal','dayplanner',
  'asset-hub','alert-hub','analytics','analytics-report','shift-brain','predictive','ai-quality',
  'ph-intelligence','project-manager','project-report','skillmatrix','achievements','audit-log',
  'assistant','hive','community','marketplace','integrations','plant-connections','report-sender',
];

const browser = await chromium.launch();
const ctx = await browser.newContext();
const sp = await ctx.newPage();
await sp.goto(`${SEEDER}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
await sp.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 15000 }).catch(() => {});
const auth = await sp.evaluate(async ({ email, password, hive }) => {
  try {
    const db = window._whSupabaseClient || window.getDb('http://127.0.0.1:54321', window.SUPABASE_KEY);
    const { data, error } = await db.auth.signInWithPassword({ email, password });
    localStorage.setItem('wh_active_hive_id', hive);
    return { ok: !error && !!data?.session, err: error ? String(error.message) : null };
  } catch (e) { return { ok: false, err: String(e) }; }
}, { email: EMAIL, password: PASSWORD, hive: HIVE });
await sp.close();
console.log('signin:', JSON.stringify(auth));

const out = [];
let totalExposures = 0;
for (const name of PAGES) {
  const page = await ctx.newPage();
  let rec = { page: name + '.html' };
  try {
    await page.goto(`${SEEDER}/workhive/${name}.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(2500);
    await page.evaluate(`(${BATTERY_SRC})()`);
    await page.evaluate(`(async()=>{ try{ await window.__UFAI.boot(); }catch(e){} })()`);
    const ref = await page.evaluate(async (pid) => await window.__UFAI.referee({ pageId: pid, role: 'supervisor', experience: 'experienced' }), name);
    const I = ref && ref.scores && ref.scores.I ? ref.scores.I : null;
    const secretDefects = (ref && ref.verdict && ref.allDefects ? ref.allDefects : (ref.defects || [])).filter
      ? [] : [];
    rec.secretExposures = I ? (I.metrics.secretExposures || 0) : null;
    rec.destructiveControls = I ? (I.metrics.destructiveControls || 0) : null;
    rec.sourceChips = I ? (I.metrics.sourceChips || 0) : null;
    // pull the secret-exposed defect messages if any
    rec.secretDefects = (ref.allDefects || []).filter(d => d.check === 'secret-exposed').map(d => d.measured);
    totalExposures += rec.secretExposures || 0;
  } catch (e) {
    rec.error = String(e).slice(0, 120);
  }
  await page.close();
  out.push(rec);
  console.log(`${(rec.secretExposures===0?'CLEAN':'⚠ '+rec.secretExposures).toString().padEnd(8)} ${name.padEnd(22)} secrets=${rec.secretExposures} destructive=${rec.destructiveControls} sourceChips=${rec.sourceChips}${rec.secretDefects&&rec.secretDefects.length?' :: '+JSON.stringify(rec.secretDefects):''}`);
}
writeFileSync('frontend_i6_secrets.json', JSON.stringify({ generated: new Date().toISOString(), totalSecretExposures: totalExposures, results: out }, null, 2));
console.log(`\n-> wrote frontend_i6_secrets.json · TOTAL secret exposures across ${out.length} pages: ${totalExposures}`);
await browser.close();
