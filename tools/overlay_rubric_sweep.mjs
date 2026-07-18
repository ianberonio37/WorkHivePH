// overlay_rubric_sweep.mjs — grade the FLOATING / OVERLAY layer the 32-page family sweep skips
// (Ian, 2026-07-17: "why we always skips the widgets or the floating on our rubric?"). See
// FAMILY_UFAI_ROADMAP.md §18. The per-page root() excludes shell chrome by owner; these shared
// surfaces (rendered on all 32 pages) therefore never enter any page's A–S score. This opens each
// widget and surveys its element as its OWN artifact via survey({ root }). Reuses the family sweep
// sign-in + the SAME ruler (survey_ufai_rubric.js) — one instrument, a new surface class.
//
// USAGE: node tools/overlay_rubric_sweep.mjs [--headed]
import { chromium } from 'playwright';
import { readFileSync, writeFileSync } from 'fs';

const SEEDER = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const EMAIL = 'pabloaguilar@auth.workhiveph.com', PASSWORD = 'test1234';
const HIVE = 'c9def338-fd73-4b19-8ef1-ee57625953d6', WORKER = 'Pablo Aguilar';
const HEADED = process.argv.includes('--headed');
const RUBRIC_SRC = readFileSync('survey_ufai_rubric.js', 'utf8');

// The shared floating surfaces on the 32 FAMILY pages: click `trigger` to reveal, then survey
// `root`. (The feedback FAB / wh-fb is founder-console-only, NOT family shell chrome, so it is not
// graded here — the family floating layer is the companion widget + the nav-hub.)
const OVERLAYS = [
  { id: 'overlay:companion', label: 'AI companion widget', trigger: '#wh-ai-trigger', root: '#wh-ai-panel' },
  { id: 'overlay:nav',       label: 'Nav-hub',              trigger: '#wh-hub-fab',   root: '#wh-hub-panel' },
];

const browser = await chromium.launch({ headless: !HEADED });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });

// sign in once (same recipe as family_rubric_sweep)
const s = await context.newPage();
await s.goto(`${SEEDER}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
await s.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 15000 }).catch(() => {});
await s.evaluate(async ({ email, password, hive, worker }) => {
  try {
    const db = window._whSupabaseClient || window.getDb('http://127.0.0.1:54321', window.SUPABASE_KEY);
    await db.auth.signInWithPassword({ email, password });
    localStorage.setItem('wh_active_hive_id', hive);
    localStorage.setItem('wh_last_worker', worker);
    localStorage.setItem('wh_hive_role', 'supervisor');
  } catch (e) { /* ignore */ }
}, { email: EMAIL, password: PASSWORD, hive: HIVE, worker: WORKER });
await s.close();

// hive.html is signed-in and carries all three shared widgets.
const page = await context.newPage();
await page.goto(`${SEEDER}/workhive/hive.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
await page.waitForTimeout(3500);

const board = {};
for (const ov of OVERLAYS) {
  const opened = await page.evaluate(async ({ trigger, root }) => {
    const t = document.querySelector(trigger);
    if (!t) return { ok: false, why: 'no trigger ' + trigger };
    t.click();
    // ★MEASURE THE SETTLED STATE: the panel opens with a CSS transform/opacity transition; surveying
    // mid-animation reports collapsed/transformed rects (a 44px button read 18px). Poll until the
    // panel's height is stable across two frames (animation done), capped at ~2.5s.
    const el = document.querySelector(root);
    if (!el) return { ok: false, why: 'panel ' + root + ' missing after click' };
    let last = -1, stable = 0;
    for (let i = 0; i < 25 && stable < 3; i++) {
      await new Promise((r) => setTimeout(r, 100));
      const h = Math.round(el.getBoundingClientRect().height);
      stable = (h === last && h > 0) ? stable + 1 : 0;
      last = h;
    }
    const vis = el.getBoundingClientRect().width > 0 && getComputedStyle(el).display !== 'none';
    return { ok: !!vis, why: vis ? '' : 'panel ' + root + ' not visible after settle' };
  }, ov);
  if (!opened.ok) { console.log(`  ! ${ov.id}: ${opened.why}`); board[ov.id] = { error: opened.why }; continue; }

  const res = await page.evaluate(({ src, root, id }) => {
    if (!window.__RUBRIC) eval('(' + src + ')')();
    return window.__RUBRIC.survey({ root, pageId: id });
  }, { src: RUBRIC_SRC, root: ov.root, id: ov.id });

  const dims = (res && res.dims) || [];
  const measured = dims.filter((d) => d.pct !== null);
  const green = measured.filter((d) => d.pct === 100).length;
  board[ov.id] = {
    label: ov.label, overall: res && res.overall,
    measuredDims: measured.length, green,
    fails: measured.filter((d) => d.pct < 100).map((d) => `${d.dim} ${d.pct} (${d.note})`),
  };
  // re-close so the next widget opens clean
  await page.evaluate((trigger) => { const t = document.querySelector(trigger); if (t) t.click(); }, ov.trigger).catch(() => {});
  await page.waitForTimeout(300);
}

writeFileSync('overlay_rubric_scoreboard.json', JSON.stringify(board, null, 2));
console.log('\n=== OVERLAY UFAI BASELINE (floating surfaces) ===');
for (const [id, b] of Object.entries(board)) {
  if (b.error) { console.log(`${id}: ERROR ${b.error}`); continue; }
  console.log(`\n${id} (${b.label}) — overall ${b.overall} · ${b.green}/${b.measuredDims} dims green`);
  b.fails.slice(0, 12).forEach((f) => console.log(`   FAIL ${f}`));
}
await browser.close();
