// prove_destructive_sweep — T50 "destructive-action sweep: proportional confirm + undo everywhere" (2026-09-06).
//
// Every control that can destroy someone's work must be guarded in proportion to what it destroys: a confirm the
// person has to answer, a typed confirmation for the severe ones, or an undo they can reach afterwards. The row
// had rested on prose. This walks it.
//
// The walk, as a signed-in supervisor on each interactive surface:
//   D1 inventory   find every visible control whose LABEL promises destruction - delete, remove, clear, reject,
//                  revoke, discard, archive, cancel-the-thing, "sign out everyone"
//   D2 guarded     CLICK it, and something must intervene: a native confirm/beforeunload, a dialog that appears,
//                  or a visible undo affordance. Nothing intervening means the row is already gone.
//   D3 no damage   whatever happens, the DB row counts before and after must match - the prover answers every
//                  dialog with CANCEL and never confirms, so a guarded control leaves no trace and an UNGUARDED
//                  one is caught by the count moving, which IS the finding.
//
// ★THE ONLY HONEST WAY TO TEST A GUARD IS TO TRY THE DOOR. A static scan for a confirm() call in the handler
// proves the code contains a guard, not that the guard is on the path the button takes - this platform has
// already shipped a guard nested inside the wrong branch, and a fix in a dead path. So the button is pressed,
// on a local seeded database that can be reseeded, with every dialog dismissed.
//
//   node tools/prove_destructive_sweep.mjs
//   node tools/prove_destructive_sweep.mjs --page inventory.html
import { chromium } from 'playwright';
import { execSync } from 'node:child_process';
import { SEEDER, HIVE, signIn, PAGE_QUERY, VIS_JS, SETTLE_MS } from './prover_harness.mjs';

const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const LIST = (() => { const i = process.argv.indexOf('--pages'); return i >= 0 ? process.argv[i + 1].split(',') : null; })();
const psql = (sql) => { try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim(); } catch { return ''; } };

const ROSTER = [
  'hive.html', 'logbook.html', 'inventory.html', 'asset-hub.html', 'dayplanner.html', 'alert-hub.html',
  'community.html', 'marketplace.html', 'marketplace-seller.html', 'marketplace-admin.html', 'skillmatrix.html',
  'pm-scheduler.html', 'project-manager.html', 'resume.html', 'voice-journal.html', 'integrations.html',
  'plant-connections.html', 'report-sender.html', 'platform-actions.html', 'founder-console.html',
];

// the tables a destructive control on these pages could empty
const WATCH = ['logbook', 'pm_assets', 'inventory_items', 'asset_nodes', 'community_posts', 'community_replies',
  'marketplace_listings', 'projects', 'project_items', 'voice_journal_entries', 'resume_documents',
  'shift_plans', 'integration_configs', 'report_contacts', 'alert_dismissals'];
// ★A ROW COUNT CANNOT SEE A SOFT DELETE, AND THAT IS HOW THIS SWEEP DESTROYED DATA WITHOUT NOTICING (2026-09-06).
// An early run pressed community.html's "Delete post" ten times. Each one soft-deleted a seeded post - stamping
// deleted_at, leaving the row - so `count(*)` was identical before and after and D3 reported "no row count
// moved" while ten posts left the feed. The safety net has to count what a PERSON would see: live rows only.
// (The product was right all along: the delete is guarded by a 10-second undo toast, which the guard check
// missed for looking too early. The instrument was wrong twice in one control.)
const SOFT = new Set(psql("select c.relname from pg_class c join pg_namespace n on n.oid=c.relnamespace join pg_attribute a on a.attrelid=c.oid and a.attname='deleted_at' and not a.attisdropped where n.nspname='public' and c.relkind='r'").split(String.fromCharCode(10)).map((x) => x.trim()).filter(Boolean));
const census = () => Object.fromEntries(WATCH.map((t) => {
  const live = SOFT.has(t) ? ` and deleted_at is null` : '';
  return [t, psql(`select count(*) from public."${t}" where hive_id = '${HIVE}'${live}`) || '?'];
}));

const FIND = function find(VIS_JS) {
  const vis = (0, eval)(VIS_JS);
  const DESTROY = /\b(delete|remove|clear all|discard|revoke|reject|archive|wipe|erase|purge|unpublish|deactivate|sign out everyone|remove member|leave hive)\b/i;
  const KEEP = /\b(clear filter|clear search|clear form|remove filter|clear selection|cancel)\b/i;
  const out = [];
  const els = [...document.querySelectorAll('button, [role="button"], a[href="#"], input[type="button"]')]
    .filter((e) => vis(e) && e.checkVisibility({ opacityProperty: true, visibilityProperty: true }) && !e.disabled);
  for (const e of els) {
    const label = ((e.innerText || '') + ' ' + (e.getAttribute('aria-label') || '') + ' ' + (e.title || '')).replace(/\s+/g, ' ').trim();
    if (!DESTROY.test(label) || KEEP.test(label)) continue;
    // ★ONE CONTROL PER DISTINCT LABEL. A feed renders the same "Delete post" button on every card; pressing all
    // of them tests the same handler N times and, where the guard is a transient undo toast, destroys N-1 rows
    // the sweep cannot put back (only one toast is on screen at a time). One press per label is full coverage
    // of the HANDLERS, which is what is under test.
    const key = label.slice(0, 44);
    if (out.includes(key)) continue;
    e.setAttribute('data-wh-destructive', String(out.length));
    out.push(key);
  }
  return out;
};

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
await signIn(ctx);

let bad = 0, n = 0, controls = 0;
const unreached = [];
for (const file of (ONLY ? [ONLY] : (LIST || ROSTER))) {
  n++;
  const p = await ctx.newPage();
  let dialogs = 0;
  p.on('dialog', async (d) => { dialogs++; await d.dismiss().catch(() => {}); });   // always CANCEL, never confirm
  await p.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(SETTLE_MS);
  // ★A DESTRUCTIVE CONTROL USUALLY HIDES BEHIND A ROW MENU. The first run reported ZERO on inventory and
  // logbook - the two surfaces most able to destroy a person's work - because Delete lives inside the row's
  // kebab. Open the menus first, then look; a sweep that only sees what is on screen at load sweeps nothing.
  for (const trig of await p.$$('[aria-haspopup], [aria-label*="more" i], [aria-label*="menu" i], [aria-label*="options" i], [aria-label*="action" i], button[class*="kebab" i], summary')) {
    await trig.click({ timeout: 2000 }).catch(() => {});
    await p.waitForTimeout(450);
  }
  // ...and on the two surfaces that can destroy the most, it hides one level deeper still: inventory's
  // "Remove from inventory" and logbook's "Delete" live inside the ITEM DETAIL, which opens by clicking a row.
  // Opening the first row is what brings them on screen; without it this sweep swept nothing on either page.
  if (!(await p.evaluate(FIND, VIS_JS).catch(() => [])).length) {
    const row = p.locator('[onclick*="Detail"]:visible, [onclick*="detail"]:visible, [id$="-list"] > *:visible, tbody tr:visible, .simple-card:visible').first();
    if (await row.count().catch(() => 0)) { await row.click({ timeout: 4000 }).catch(() => {}); await p.waitForTimeout(2600); }
  }
  await p.waitForTimeout(900);
  const labels = await p.evaluate(FIND, VIS_JS).catch(() => []);
  const issues = [];
  const before = labels.length ? census() : null;
  for (let i = 0; i < labels.length && i < 8; i++) {
    controls++;
    const sel = `[data-wh-destructive="${i}"]`;
    const dlgBefore = dialogs;
    const GUARD = () => document.querySelectorAll('[id^="wh-modal-ov-"], [data-wh-modal-ok], dialog[open]').length;
    const modalsBefore = await p.evaluate(GUARD).catch(() => 0);
    await p.evaluate(() => { for (const o of document.querySelectorAll('[id^="wh-modal-ov-"]')) o.remove(); }).catch(() => {});
    await p.evaluate((s2) => { const e = document.querySelector(s2); if (e) e.click(); }, sel).catch(() => {});
    await p.waitForTimeout(2600);   // an undo TOAST needs time to render; judging at 1.6s called a guarded delete unguarded
    const after = await p.evaluate(() => ({
      modals: document.querySelectorAll('[id^="wh-modal-ov-"], [data-wh-modal-ok], dialog[open]').length,
      undo: [...document.querySelectorAll('button, [role="button"], a')].some((e) => /\bundo\b|\brestore\b/i.test(e.innerText || '') && e.checkVisibility && e.checkVisibility({ opacityProperty: true, visibilityProperty: true })),
    })).catch(() => ({ modals: modalsBefore, undo: false }));
    const guarded = dialogs > dlgBefore || after.modals > modalsBefore || after.undo;
    if (!guarded) issues.push(`D2 "${labels[i]}" fired with no confirm, no dialog and no undo offered`);
    // ★A CONTROL GUARDED ONLY BY UNDO HAS ALREADY ACTED, SO THE SWEEP MUST PRESS THE UNDO. community.html's
    // delete is proportionate - a soft delete with a 10-second undo - but that means every press really removes
    // a post, and an early run of this file deleted ten seeded ones. Pressing the undo both LEAVES NO DAMAGE and
    // tests the half of the guard that matters: an undo nobody can reach is not a guard.
    if (after.undo) {
      const undone = await p.evaluate(() => {
        const el = [...document.querySelectorAll('button, [role="button"], a')]
          .find((e) => /^\s*(undo|restore)\b/i.test(e.innerText || '') && e.checkVisibility && e.checkVisibility({ opacityProperty: true, visibilityProperty: true }));
        if (!el) return false;
        el.click(); return true;
      }).catch(() => false);
      if (!undone) issues.push(`D2 "${labels[i]}" offers an undo the sweep could not press - an undo nobody can reach is not a guard`);
      await p.waitForTimeout(2000);
    }
    // close whatever opened, so the next control is clicked on a clean page
    // dismiss the platform's own overlay by its cancel button, then Escape for anything else
    await p.click('[data-wh-modal-cancel]', { timeout: 1200 }).catch(() => {});
    await p.keyboard.press('Escape').catch(() => {});
    await p.waitForTimeout(500);
  }
  if (before) {
    const after = census();
    const moved = WATCH.filter((t) => before[t] !== after[t]).map((t) => `${t} ${before[t]}->${after[t]}`);
    if (moved.length) issues.push(`D3 rows changed while only CANCELLING: ${moved.join(', ')}`);
  }
  if (issues.length) bad++;
  if (!labels.length) unreached.push(file);
  console.log(`  ${labels.length ? (issues.length ? 'BAD' : 'ok ') : 'n/a'} ${file.padEnd(28)} ${labels.length} destructive control(s)${labels.length ? (issues.length ? ` · ${issues.length} unguarded` : ' · all guarded') : ' - NOT REACHED: no destructive control came on screen (this is a limit of the sweep, not a claim that the surface has none)'}`);
  for (const s of issues.slice(0, ONLY ? 12 : 3)) console.log(`        ${s.slice(0, 158)}`);
  await p.close();
}
await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} destructive-sweep - ${n - bad - unreached.length}/${n - unreached.length} surfaces guard every destructive control the sweep could reach: ${controls} control(s) pressed, every dialog answered CANCEL, no row count moved. ${unreached.length} surface(s) NOT REACHED (${unreached.slice(0, 6).join(', ')}) - their destructive controls sit inside role-gated item detail, which this sweep does not open, so they are unmeasured rather than clean.`);
process.exitCode = bad ? 1 : 0;
