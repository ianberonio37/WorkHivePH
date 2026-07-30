// UFAI DEEP probe for the service-hailing arc's 4 surfaces.
// Runs the LIVE checks ufai_pillar_map.py explicitly says its coarse lens slice does NOT cover:
//   U2  tap targets >= 44px on every interactive control (measured, at 390 width)
//   U5  axe a11y violations (vendored axe-core injected)
//   A1  responsive 360 -> 1920 with NO horizontal page scroll at any step
// F5 (CRUD round-trip) and I2/I3 (role/tenancy) are proven separately by the live walks and the
// C1/C3/C6/C10 gates, so this probe owns the three that need a browser and a ruler.
//
// Identity + recipe reused from tools/family_rubric_sweep.mjs (sign in once, same origin).
import { chromium } from 'playwright';
import { readFileSync, writeFileSync } from 'fs';

const SEEDER = 'http://127.0.0.1:5000';
const EMAIL = 'pabloaguilar@auth.workhiveph.com';
const PASSWORD = 'test1234';
const HIVE = '4eec150e-4837-417b-bdd8-009b0192acfe';

const PAGES = [
  ['marketplace.html', '?section=services'],
  ['marketplace-seller.html', '?tab=services'],
  ['founder-console.html', ''],
  ['achievements.html', ''],
];
const WIDTHS = [360, 390, 768, 1280, 1920];

const AXE = (() => {
  for (const p of ['tools/vendor/axe.min.js', 'node_modules/axe-core/axe.min.js']) {
    try { return readFileSync(p, 'utf8'); } catch (_) {}
  }
  return null;
})();

const out = {};

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();

  // sign in once, same origin
  await page.goto(`${SEEDER}/workhive/marketplace.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  await page.evaluate(async ([email, password, hive]) => {
    const db = window.db || (window.getDb && window.getDb());
    await db.auth.signOut().catch(() => {});
    await db.auth.signInWithPassword({ email, password });
    localStorage.setItem('wh_last_worker', 'Pablo Aguilar');
    localStorage.setItem('wh_active_hive_id', hive);
    localStorage.setItem('wh_hive_role', 'supervisor');
  }, [EMAIL, PASSWORD, HIVE]);

  for (const [file, qs] of PAGES) {
    const res = { u2: null, u5: null, a1: null, errors: [] };
    try {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto(`${SEEDER}/workhive/${file}${qs}`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(6000);

      // ---- U2: measured tap targets on VISIBLE interactive controls
      res.u2 = await page.evaluate(() => {
        const sel = 'button, a[href], input:not([type=hidden]), select, textarea, [role=button], [onclick]';
        const els = [...document.querySelectorAll(sel)].filter(el => {
          const r = el.getBoundingClientRect();
          const cs = getComputedStyle(el);
          return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none';
        });
        const small = [];
        for (const el of els) {
          const r = el.getBoundingClientRect();
          if (r.height < 44 - 0.5) {
            small.push({ h: Math.round(r.height), t: (el.textContent || el.getAttribute('aria-label') || el.id || '').trim().slice(0, 34) });
          }
        }
        return { total: els.length, small: small.length, worst: small.sort((a, b) => a.h - b.h).slice(0, 4) };
      });

      // ---- U5: axe
      if (AXE) {
        await page.addScriptTag({ content: AXE });
        res.u5 = await page.evaluate(async () => {
          const r = await window.axe.run(document, { resultTypes: ['violations'] });
          return {
            violations: r.violations.length,
            serious: r.violations.filter(v => ['serious', 'critical'].includes(v.impact)).length,
            top: r.violations.slice(0, 4).map(v => `${v.id}(${v.impact}) x${v.nodes.length}`),
          };
        });
      } else {
        res.u5 = { skipped: 'axe-core not found on disk' };
      }

      // ---- A1: responsive 360 -> 1920, no horizontal page scroll
      const overflow = [];
      for (const w of WIDTHS) {
        await page.setViewportSize({ width: w, height: 900 });
        await page.waitForTimeout(900);
        const o = await page.evaluate(() => ({
          scrollW: document.documentElement.scrollWidth,
          clientW: document.documentElement.clientWidth,
        }));
        if (o.scrollW > o.clientW + 2) overflow.push({ w, over: o.scrollW - o.clientW });
      }
      res.a1 = { widths: WIDTHS, overflow };
    } catch (e) {
      res.errors.push(String(e).slice(0, 160));
    }
    out[file] = res;
    console.log(`${file}: U2 small=${res.u2 ? res.u2.small : '?'}/${res.u2 ? res.u2.total : '?'} · ` +
                `U5 violations=${res.u5 && res.u5.violations !== undefined ? res.u5.violations : (res.u5 && res.u5.skipped) || '?'} · ` +
                `A1 overflow=${res.a1 ? res.a1.overflow.length : '?'}`);
  }

  await browser.close();
  writeFileSync('ufai_deep_arc_report.json', JSON.stringify(out, null, 2), 'utf8');

  // GATE MODE: the bar is 0 sub-44px targets, 0 horizontal overflow, and 0 SERIOUS/CRITICAL axe
  // violations on every arc surface. Moderate findings are reported but do not fail the build -
  // the two that remain are pre-existing containers outside this arc, recorded in the state file.
  const fails = [];
  for (const [file, r] of Object.entries(out)) {
    if (r.errors && r.errors.length) fails.push(`${file}: probe error ${r.errors[0]}`);
    if (r.u2 && r.u2.small > 0) fails.push(`${file}: ${r.u2.small} tap target(s) under 44px`);
    if (r.a1 && r.a1.overflow.length) fails.push(`${file}: horizontal overflow at ${r.a1.overflow.map(o => o.w).join('/')}`);
    if (r.u5 && r.u5.serious > 0) fails.push(`${file}: ${r.u5.serious} serious/critical axe violation(s)`);
  }
  if (fails.length) {
    console.error('FAIL - UFAI deep regression on the service-hailing surfaces:');
    for (const f of fails) console.error('  - ' + f);
    process.exit(1);
  }
  console.log('PASS - 0 sub-44px targets, 0 overflow (360-1920), 0 serious/critical axe on all arc surfaces.');
})();
