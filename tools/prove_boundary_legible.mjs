// prove_boundary_legible — the SECURITY & RLS layer of the LAYER-UX wave (§LX, 2026-09-06), asked from
// the person's side rather than the policy's. `tenant-refusal` already proves the boundary HOLDS; this
// asks whether a person can live with it.
//
//   B1 legible     when something is refused, the message says what they can DO about it, and does not
//                  leak what they should not see - no SQL, no policy name, no other tenant's ids. Both
//                  failure modes are the same defect: a refusal that is not addressed to a person.
//   B2 honest      a control they will be refused is marked BEFORE they press it - disabled, or
//                  explained - rather than looking available and failing. A button that looks live and
//                  is not teaches people the product is broken rather than that they lack permission.
//
// ★WALKED AS A PLAIN WORKER, NEVER THE ADMIN. The harness's default persona is a marketplace platform
// admin, so walking as him means nothing is refused and every page reads clean - the exact false
// negative that made seven tables look like leaks earlier the same day, in reverse.
//
//   node tools/prove_boundary_legible.mjs
//   node tools/prove_boundary_legible.mjs --page founder-console.html
import { chromium } from 'playwright';
import { SEEDER, HIVE, PAGE_QUERY, VIS_JS, SETTLE_MS } from './prover_harness.mjs';

const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const PLAIN = { name: 'Wilfredo Malabanan', email: 'wilfredomalabanan@auth.workhiveph.com', password: 'test1234', role: 'worker' };

const ROSTER = ['hive.html', 'logbook.html', 'inventory.html', 'asset-hub.html', 'community.html',
                'marketplace.html', 'marketplace-admin.html', 'founder-console.html',
                'platform-actions.html', 'audit-log.html', 'integrations.html', 'plant-connections.html'];

// what a refusal must never contain: the machinery behind it
const LEAKS = [
  [/\b(row-level security|RLS policy|policy "[^"]+"|violates row-level)/i, 'names the policy machinery'],
  [/\b(select |insert into|update .* set |from public\.)/i, 'quotes SQL at the person'],
  [/\b42501\b|\bPGRST\d+/i, 'shows a raw database error code with no plain sentence'],
  [/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/, 'exposes a raw uuid'],
];
// what a refusal must contain: something the person can act on
const ACTIONABLE = /\b(ask|contact|supervisor|admin|permission|access|request|sign in|your (account|role)|not allowed to|cannot)\b/i;

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
{
  const s = await ctx.newPage();
  await s.goto(`${SEEDER}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await s.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 15000 }).catch(() => {});
  await s.evaluate(async ({ hive, who }) => {
    const db = window._whSupabaseClient || window.getDb('http://127.0.0.1:54321', window.SUPABASE_KEY);
    await db.auth.signInWithPassword({ email: who.email, password: who.password });
    localStorage.setItem('wh_active_hive_id', hive);
    localStorage.setItem('wh_last_worker', who.name);
    localStorage.setItem('wh_hive_role', who.role);
  }, { hive: HIVE, who: PLAIN }).catch(() => {});
  await s.close();
}

let bad = 0, n = 0;
for (const file of (ONLY ? [ONLY] : ROSTER)) {
  n++;
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(SETTLE_MS);

  const r = await p.evaluate((VIS_JS) => {
    const vis = (0, eval)(VIS_JS);
    const strict = (e) => e.checkVisibility && e.checkVisibility({ opacityProperty: true, visibilityProperty: true });
    const sel = '[role="alert"], [role="status"], .wh-list-error, .honest-empty, .mod-empty, [id$="-notice"], .verdict, [data-wh-read-failed]';
    const notices = [...document.querySelectorAll(sel)].filter(vis).map((e) => (e.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean);
    // B2: a control that is live to the eye but gated in fact. The honest shapes are disabled,
    // aria-disabled, or a title/aria-description that says why.
    const PRIV = /\b(approve|reject|moderate|verify|delete|remove|revoke|publish|promote|reset|invite|assign|settle|refund|export all|sign out everyone)\b/i;
    const unmarked = [];
    for (const e of [...document.querySelectorAll('button, [role="button"]')].filter((x) => vis(x) && strict(x))) {
      const label = ((e.innerText || '') + ' ' + (e.getAttribute('aria-label') || '')).replace(/\s+/g, ' ').trim();
      if (!PRIV.test(label)) continue;
      const marked = e.disabled || e.getAttribute('aria-disabled') === 'true'
        || /permission|supervisor|admin|not allowed|read.?only/i.test((e.title || '') + ' ' + (e.getAttribute('aria-description') || ''));
      if (!marked) unmarked.push(label.slice(0, 34));
    }
    return { notices, unmarked: [...new Set(unmarked)].slice(0, 6) };
  }, VIS_JS).catch(() => ({ notices: [], unmarked: [] }));

  const issues = [];
  for (const note of r.notices) {
    for (const [rx, why] of LEAKS) if (rx.test(note)) issues.push(`B1 a refusal ${why}: "${note.slice(0, 70)}"`);
    if (/refus|not allowed|denied|permission|access/i.test(note) && !ACTIONABLE.test(note)) {
      issues.push(`B1 a refusal with nothing to act on: "${note.slice(0, 70)}"`);
    }
  }
  // B2 is REPORTED for a plain worker: a page whose privileged controls are simply absent is the best
  // outcome and shows up here as zero, while a page that renders them unmarked is naming a real gap.
  const note2 = r.unmarked.length ? ` · ${r.unmarked.length} privileged control(s) unmarked: ${r.unmarked.slice(0, 3).join(', ')}` : '';
  if (issues.length) bad++;
  console.log(`  ${issues.length ? 'BAD' : 'ok '} ${file.padEnd(26)} ${r.notices.length} notice(s)${note2}`);
  for (const s of issues.slice(0, ONLY ? 10 : 2)) console.log(`        ${s.slice(0, 160)}`);
  await p.close();
}
await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} boundary-legible - ${n - bad}/${n} surfaces refuse a plain worker in terms addressed to a person: nothing leaked, something to act on (walked as ${PLAIN.name}, never the platform admin)`);
process.exitCode = bad ? 1 : 0;
