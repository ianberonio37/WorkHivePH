// arc_u_focus_trap_probe.mjs — Arc U (Accessibility) U1 residual: interactive FOCUS-TRAP detection.
//
// axe is STATIC — it cannot see a focus trap (focus escaping a modal, or being unable to leave).
// This is the one WCAG 2.1.2 (No Keyboard Trap) + 2.4.3 (Focus Order) check the axe gates miss.
// Reuses FB2's reliable headless programmatic sign-in (NOT the thrash-prone MCP browser, per
// feedback_playwright_mcp_dont_inject_signin). Opens each named modal, Tab-walks it, asserts focus
// stays WITHIN the modal (no escape to the page behind) and Escape closes it + returns focus.
//
// Run:  node tools/arc_u_focus_trap_probe.mjs   (local stack + :5000 seeder up)

import { chromium } from 'playwright';

const SEEDER = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SUPABASE_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
// pabloaguilar's REAL active hive (reseed-proof: the FB2 HIVES.lucena constant is stale).
const PERSONA = { email: 'pabloaguilar@auth.workhiveph.com', worker: 'Pablo Aguilar', role: 'supervisor', hive: 'b86f9ef6-b0a6-477d-b9c6-ca865c3b9dba' };

// Each target: navigate, click the opener, then the modal container should trap focus.
const TARGETS = [
  { page: 'marketplace.html', name: 'Post-a-Listing (AI-assist home)', openerId: 'fab-post', modalSel: '#sheet-post', overlaySel: '#overlay-post' },
];
// NOTE: the marketplace sheets open via an `.open` class (openSheet() adds it), not display.

async function signIn(context) {
  const page = await context.newPage();
  try {
    await page.goto(`${SEEDER}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 15000 }).catch(() => {});
    const r = await page.evaluate(async ({ email, password, hive, worker, role, surl }) => {
      try {
        const db = window._whSupabaseClient || window.getDb(surl, window.SUPABASE_KEY);
        const { data, error } = await db.auth.signInWithPassword({ email, password });
        localStorage.setItem('wh_active_hive_id', hive);
        localStorage.setItem('wh_last_worker', worker);
        localStorage.setItem('wh_hive_role', role);
        return { ok: !error && !!data?.session, err: error ? String(error.message || error) : null };
      } catch (e) { return { ok: false, err: String(e) }; }
    }, { email: PERSONA.email, password: PASSWORD, hive: PERSONA.hive, worker: PERSONA.worker, role: PERSONA.role, surl: SUPABASE_URL });
    return r;
  } finally { await page.close().catch(() => {}); }
}

(async () => {
  const RESULTS = [];
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 390, height: 780 } });
  const si = await signIn(context);
  console.log(`signIn ${PERSONA.worker}: ${si.ok ? 'OK' : 'FAIL ' + si.err}`);

  for (const t of TARGETS) {
    const page = await context.newPage();
    const out = { page: t.page, name: t.name, opened: false, escapes: 0, tabs: 0, escClosed: null, focusReturned: null, err: null };
    try {
      await page.goto(`${SEEDER}/workhive/${t.page}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(1800);
      // Open the modal (try the empty-state opener, else any "Post a listing" button).
      await page.evaluate((id) => {
        const b = document.getElementById(id) || [...document.querySelectorAll('button')].find(x => /post a listing/i.test(x.getAttribute('aria-label') || x.textContent));
        // Focus THEN activate — a real keyboard/mouse user focuses the opener, which is what
        // whModalA11y captures as its focus-restore target. A bare .click() leaves focus on body.
        if (b) { b.focus(); b.click(); }
      }, t.openerId);
      await page.waitForTimeout(700);
      const opened = await page.evaluate((sel) => { const m = document.querySelector(sel); return !!m && m.classList.contains('open'); }, t.modalSel);
      out.opened = opened;
      if (!opened) { out.err = 'modal did not open'; results_push(out); await page.close(); continue; }

      // Focus the first control in the modal, then Tab 40x asserting containment.
      await page.evaluate((sel) => { const m = document.querySelector(sel); const f = m && m.querySelector('input,button,select,textarea,a[href],[tabindex]'); if (f) f.focus(); }, t.modalSel);
      const N = 40;
      for (let i = 0; i < N; i++) {
        await page.keyboard.press('Tab');
        const inside = await page.evaluate((sel) => { const m = document.querySelector(sel); return !!(m && document.activeElement && m.contains(document.activeElement)); }, t.modalSel);
        out.tabs++;
        if (!inside) out.escapes++;
      }
      // Escape should close the modal and return focus to the opener/body.
      await page.keyboard.press('Escape');
      await page.waitForTimeout(500);
      out.escClosed = await page.evaluate((sel) => { const m = document.querySelector(sel); return !m || !m.classList.contains('open'); }, t.modalSel);
      const fa = await page.evaluate((sel) => {
        const m = document.querySelector(sel), a = document.activeElement;
        return { inModal: !!(m && a && m.contains(a)), where: a ? (a.id ? '#' + a.id : a.tagName + '.' + String(a.className || '').split(' ')[0]) : 'none' };
      }, t.modalSel);
      out.focusReturned = !fa.inModal;
      out.focusAfterEsc = fa.where;
    } catch (e) { out.err = String(e).slice(0, 140); }
    finally { await page.close().catch(() => {}); }
    results_push(out);
  }
  await browser.close();

  // Gate contract: any real FAIL (trap leak, no ESC-close, focus not restored) -> exit 1.
  // A signIn/env problem (couldn't reach the stack) is a SKIP (exit 0) — mirrors the other
  // local-stack-dependent gates that skip cleanly when node/the stack is absent.
  if (!si.ok) { console.log('SKIP: sign-in failed (local stack/seeder absent?) — not gated.'); process.exit(0); }
  const fails = RESULTS.filter(o => o.err || !(o.escapes === 0 && o.escClosed && o.focusReturned));
  process.exit(fails.length ? 1 : 0);

  function results_push(o) {
    RESULTS.push(o);
    const verdict = o.err ? 'ERR' : (o.escapes === 0 && o.escClosed && o.focusReturned) ? 'PASS' : 'FAIL';
    console.log(`[${verdict}] ${o.page} :: ${o.name}`);
    console.log(`   opened=${o.opened} tabs=${o.tabs} focus-escapes=${o.escapes} esc-closed=${o.escClosed} focus-returned=${o.focusReturned} focus-after-esc=${o.focusAfterEsc || '?'}${o.err ? ' err=' + o.err : ''}`);
  }
})();
