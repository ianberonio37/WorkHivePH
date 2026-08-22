/* prove_services_pane.mjs — the market_svc "populated" oracle, executable.
 *
 * The 24 owed LM-*-market_svc-*-populated rows all claim one thing: on
 * /workhive/marketplace.html?section=services the surface renders real rows and EVERY visible
 * number matches its source of truth. The 2026-08-06 walk proved it by hand for one identity and
 * went owed when the walker had no open request to read. This makes the walk repeatable:
 *
 *   node tools/prove_services_pane.mjs                     # all personas
 *   node tools/prove_services_pane.mjs --persona buyer
 *
 * Personas: buyer = Pablo Aguilar (holds the open hails), provider = Bryan Garcia (a worker who
 * is also the matched provider on real jobs), anon = no session.
 *
 * Discipline carried in from the bank's own lessons:
 *  - the section is driven by CLICKING the services tab and confirming aria-selected — a
 *    ?section= param alone is a DIFFERENT page (a_paramless_walk_is_a_different_page);
 *  - every DB truth is asked FROM THE PAGE under the caller's own jwt claims, because
 *    v_service_request_truth / v_service_catalog_truth are security_invoker views — asked as
 *    anybody else they answer for the wrong caller (the_reading_was_real_the_subject_was_wrong);
 *  - every number is attributed to ITS OWN LABEL before comparison, never matched by position;
 *  - a failed read renders an em-dash, and the probe treats '—' as "read failed", never as 0.
 *
 * Output: per-check PASS/FAIL lines + services_pane_report.json; exit 1 on any FAIL.
 */
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const SVC_OPEN = ['requested', 'broadcasting', 'accepted', 'en_route', 'on_site', 'in_progress'];
const SVC_CHIP = { requested: 'Draft', broadcasting: 'Finding a provider…', accepted: 'Provider accepted',
                   en_route: 'Provider on the way', on_site: 'Provider on site', in_progress: 'Work in progress' };
const PERSONAS = {
  buyer:    { email: 'pabloaguilar@auth.workhiveph.com', pw: 'test1234' },
  provider: { email: 'bryangarcia@auth.workhiveph.com', pw: 'test1234' },
  // admin = a marketplace_platform_admins member; seller = a marketplace seller with no admin row.
  // The adversarial personas (spammer/sybil/scam_*/colluder) hold NO special grants — for a
  // RENDER-truth claim they are capability-identical to any signed-in member, so the seller run
  // is their measurement; their adversarial DEPTH lives in the S-family's own non-populated rows.
  admin:    { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234' },
  seller:   { email: 'jerichobonifacio@auth.workhiveph.com', pw: 'test1234' },
  anon:     null,
};

const args = process.argv.slice(2);
const only = (() => { const i = args.indexOf('--persona'); return i >= 0 ? args[i + 1] : null; })();

const results = [];
function check(persona, name, pass, detail) {
  results.push({ persona, name, pass: !!pass, detail });
  console.log(`  ${pass ? 'PASS' : 'FAIL'} — ${persona} / ${name}: ${detail}`);
}

const browser = await chromium.launch();
for (const [persona, acct] of Object.entries(PERSONAS)) {
  if (only && persona !== only) continue;
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const p = await ctx.newPage();

  if (acct) {
    // sign in through the page's own client so the session lands in the page's storage
    await p.goto(`${ORIGIN}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
    await p.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 15000 }).catch(() => {});
    const s = await p.evaluate(async ({ email, pw }) => {
      try {
        const db = window._whSupabaseClient || window.getDb(undefined, window.SUPABASE_KEY);
        const { data, error } = await db.auth.signInWithPassword({ email, password: pw });
        return { ok: !error && !!data?.session, err: error?.message || null };
      } catch (e) { return { ok: false, err: String(e).slice(0, 120) }; }
    }, acct);
    if (!s.ok) { check(persona, 'sign-in', false, `sign-in failed: ${s.err} — harness, not the surface`); await ctx.close(); continue; }
  }

  await p.goto(`${ORIGIN}/marketplace.html?section=services`, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await p.waitForTimeout(4000);
  // drive the tab for real and confirm the pane owns the screen
  await p.evaluate(() => document.querySelector('.section-tab[data-section="services"]')?.click());
  await p.waitForTimeout(3500);
  const sel = await p.evaluate(() =>
    document.querySelector('.section-tab[data-section="services"]')?.getAttribute('aria-selected'));
  check(persona, 'tab-selected', sel === 'true', `services tab aria-selected=${sel}`);

  // let the pane finish (skeleton gone)
  await p.waitForFunction(() => {
    const pane = document.getElementById('services-pane');
    return pane && !pane.querySelector('.skel');
  }, { timeout: 20000 }).catch(() => {});

  const reading = await p.evaluate(async ({ SVC_OPEN, SVC_CHIP }) => {
    const pane = document.getElementById('services-pane');
    const text = pane ? pane.innerText : '';
    const badge = document.getElementById('count-services')?.textContent?.trim() ?? null;
    const myHeader = (() => {
      const h = [...(pane?.querySelectorAll('h2') || [])].find(x => /My service requests/i.test(x.textContent));
      return h ? (h.querySelector('.tab-count')?.textContent?.trim() ?? null) : null;
    })();
    const options = document.getElementById('svc-hail-item')
      ? [...document.getElementById('svc-hail-item').options].filter(o => o.value).length : null;
    const errorPane = /Couldn't load services/i.test(text);

    // truth, asked from the page as THIS caller (security_invoker views answer for auth.uid())
    const db = window._whSupabaseClient || (typeof window.getDb === 'function' ? window.getDb(undefined, window.SUPABASE_KEY) : null);
    let truth = { mine: null, open: null, cats: null, err: null, chips: [] };
    try {
      const { data: u } = await db.auth.getUser();
      const uid = u?.user?.id || null;
      if (uid) {
        const { data: mine, error: e1 } = await db.from('v_service_request_truth')
          .select('id,status,client_auth_uid').order('created_at', { ascending: false }).order('id', { ascending: false }).limit(20);
        if (e1) truth.err = e1.message;
        const own = (mine || []).filter(r => r.client_auth_uid === uid);
        truth.mine = own.length;
        truth.open = own.filter(r => SVC_OPEN.includes(r.status)).length;
        truth.chips = own.filter(r => SVC_OPEN.includes(r.status)).map(r => SVC_CHIP[r.status]).filter(Boolean);
      } else { truth.mine = 0; truth.open = 0; }
      const seg = window.HIVE_ID ? 'industrial' : 'consumer';
      const { data: cats, error: e2 } = await db.from('v_service_catalog_truth')
        .select('id').eq('segment', seg).limit(200);
      if (e2) truth.err = (truth.err ? truth.err + ' | ' : '') + e2.message;
      truth.cats = (cats || []).length;
    } catch (e) { truth.err = String(e).slice(0, 140); }
    return { badge, myHeader, options, errorPane, text: text.slice(0, 400), truth };
  }, { SVC_OPEN, SVC_CHIP });

  if (persona === 'anon') {
    check(persona, 'anon-invite', /Sign in to hail a service/i.test(reading.text) || reading.errorPane === false,
      `pane offers the sign-in invite or a clean catalog (errorPane=${reading.errorPane})`);
    check(persona, 'catalog-populated', reading.options !== null && reading.options > 0 && reading.truth.cats !== null
      && reading.options === reading.truth.cats,
      `hail select options=${reading.options} vs v_service_catalog_truth rows=${reading.truth.cats}`);
  } else {
    check(persona, 'no-error-pane', !reading.errorPane, `errorPane=${reading.errorPane}`);
    check(persona, 'badge-attributed', reading.badge !== null && reading.badge !== '—'
      && reading.truth.open !== null && String(reading.truth.open) === reading.badge,
      `#count-services='${reading.badge}' vs caller's SVC_OPEN rows=${reading.truth.open} (em-dash = failed read, not 0)`);
    check(persona, 'my-requests-count', reading.myHeader !== null && reading.myHeader !== '—'
      && reading.truth.mine !== null && String(reading.truth.mine) === reading.myHeader,
      `'My service requests' header='${reading.myHeader}' vs caller's rows (limit 20)=${reading.truth.mine}`);
    check(persona, 'catalog-populated', reading.options !== null && reading.truth.cats !== null
      && reading.options === reading.truth.cats,
      `hail select options=${reading.options} vs v_service_catalog_truth rows=${reading.truth.cats}`);
    const missing = (reading.truth.chips || []).filter(chip => !reading.text.includes(chip));
    check(persona, 'open-rows-visible', reading.truth.open === 0 || missing.length === 0,
      reading.truth.open === 0
        ? 'caller holds no open request — nothing owed on screen (badge cross-checked above)'
        : `each open request's state chip is painted (${(reading.truth.chips || []).join(', ')})${missing.length ? ' MISSING: ' + missing.join(', ') : ''}`);
    if (reading.truth.err) check(persona, 'truth-read', false, `truth query error: ${reading.truth.err}`);
  }
  await ctx.close();
}
await browser.close();

const failed = results.filter(r => !r.pass);
writeFileSync('services_pane_report.json', JSON.stringify({
  ran_at: new Date().toISOString(), origin: ORIGIN,
  checks: results, pass: results.length - failed.length, fail: failed.length,
}, null, 1));
console.log(`\n  ${results.length - failed.length}/${results.length} hold — services_pane_report.json`);
process.exit(failed.length ? 1 : 0);
