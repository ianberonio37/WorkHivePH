/* prove_inventory_to_listing_handoff.mjs — T104 / T30: the buy-and-sell hop keeps its intent (2026-08-26).
 *
 * inventory offers "Sell surplus" only on rows holding 3x+ their minimum, with the reason in the
 * control's own title. It hands off to marketplace.html?post=1&from_inventory=<id>, and marketplace
 * RE-FETCHES the row server-side — so the prefill is authoritative and cannot be spoofed through the
 * URL: a person can only list from inventory their own session may read.
 *
 * WHAT IS ASSERTED, and why each matters: a handoff that drops what the system already knows makes
 * the seller retype it, which is the same intent-loss as a sign-in wall that forgets where you were
 * going — and here it lands on the least-motivated user in the funnel, someone selling a spare part
 * for the first time.
 *
 *   composer opens        arriving at the deep link puts them IN the composer, not on the feed
 *   title prefilled       the part's name
 *   part number prefilled the identity a buyer searches by
 *   quantity carried      the surplus count reaches the description
 *   category classified   so a first-time seller does not guess the taxonomy
 *   source id preserved   the listing stays linked to the inventory row it came from
 *   PRICE LEFT BLANK      deliberately NOT prefilled: what a plant paid is not what it should ask,
 *                         and a guessed price is the one field a seller must own. A prefilled price
 *                         would be the system making a commercial decision on their behalf.
 *
 * Non-writing: follows a deep link and reads form values. Submits nothing.
 *
 * Usage: node tools/prove_inventory_to_listing_handoff.mjs
 */
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';
const HIVE = { id: '084c113b-99c0-45c6-a8e8-b4b8349da46d', name: 'Baguio Textile Mills' };

const psql = (sql) => execFileSync('docker',
  ['exec', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql],
  { encoding: 'utf8' }).trim();

/* Pick a REAL surplus row by the same rule the button uses (3x+ minimum) rather than hardcoding an
   id: a fixture id that gets reseeded turns this gate into a false red about nothing. */
const row = psql(
  `SELECT id || '|' || part_name || '|' || coalesce(part_number,'') || '|' || qty_on_hand
   FROM inventory_items WHERE hive_id = '${HIVE.id}' AND status = 'approved'
     AND min_qty IS NOT NULL AND min_qty > 0 AND qty_on_hand >= min_qty * 3
   ORDER BY qty_on_hand DESC LIMIT 1`.replace(/\n\s+/g, ' ')).split('\n')[0];

if (!row) {
  console.log('SKIP — no surplus row in the fixture, so the "Sell surplus" control would not appear.');
  process.exit(0);
}
const [id, partName, partNumber, qty] = row.split('|');
console.log(`  surplus row: ${partName} (${partNumber || 'no part no.'}) qty ${qty}`);

const browser = await chromium.launch();
const v = {};
try {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(String(e).slice(0, 120)));

  await page.goto(`${SEEDER}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => !!(window.supabase && typeof window.supabase.createClient === 'function'), { timeout: 25000 });
  await page.evaluate(async ({ hive }) => {
    const db = (typeof getDb === 'function') ? getDb() : window.db;
    await db.auth.signInWithPassword({ email: 'bryangarcia@auth.workhiveph.com', password: 'test1234' });
    try {
      localStorage.setItem('wh_worker_name', 'Bryan Garcia');
      localStorage.setItem('wh_last_worker', 'Bryan Garcia');
      localStorage.setItem('wh_active_hive_id', hive.id);
      localStorage.setItem('wh_hive_id', hive.id);
      localStorage.setItem('wh_hive_name', hive.name);
    } catch (_) { /* empty-catch-allow: identity seeding is best-effort */ }
  }, { hive: HIVE });

  await page.goto(`${SEEDER}/marketplace.html?post=1&from_inventory=${encodeURIComponent(id)}`,
                  { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(7000);

  const f = await page.evaluate(() => {
    const g = (i) => { const e = document.getElementById(i); return e ? String(e.value || '') : null; };
    const ov = document.getElementById('overlay-post');
    return {
      open: !!ov && getComputedStyle(ov).display !== 'none',
      title: g('post-title'), part: g('post-part-number'), desc: g('post-desc'),
      cat: g('post-category'), src: g('post-source-item-id'), price: g('post-price'),
    };
  });

  v.composerOpens = f.open === true;
  v.titlePrefilled = !!f.title && f.title.trim() === partName.trim();
  v.partNumberPrefilled = !partNumber ? true : (f.part || '').trim() === partNumber.trim();
  v.quantityCarried = !!f.desc && f.desc.includes(String(qty));
  v.categoryClassified = !!f.cat && f.cat.trim() !== '';
  v.sourceIdPreserved = (f.src || '') === id;
  v.priceLeftToTheSeller = (f.price || '') === '';
  v.pageerrors = errs.length;

  for (const [k, val] of Object.entries(v)) console.log(`  ${k.padEnd(24)} ${val}`);
} catch (e) {
  v.error = String(e.message || e).slice(0, 180);
  console.log('probe error:', v.error);
} finally {
  await browser.close();
}

const pass = !v.error && v.composerOpens && v.titlePrefilled && v.partNumberPrefilled
          && v.quantityCarried && v.categoryClassified && v.sourceIdPreserved
          && v.priceLeftToTheSeller && v.pageerrors === 0;
console.log((pass ? 'PASS' : 'FAIL') + ` — inventory->listing handoff: ${JSON.stringify(v)}`);
process.exit(pass ? 0 : 1);
