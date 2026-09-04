/* prove_route_numbers.mjs — T178's route-level number audit (2026-08-26).
 *
 * The CM family asks "what is this number?" PER PAGE. A person does not meet numbers per page:
 * they meet them along a ROUTE, in the order the work takes them, and a figure that is explained
 * on the page where it is defined can still land naked two hops later. This walks the routes the
 * platform's own journeys use and audits every number a person actually SEES.
 *
 * THE BAR (deliberately narrow, so a red means something): a rendered number is EXPLAINED when a
 * unit, a counted noun, a percent sign, a currency mark, a date/time context or a denominator sits
 * next to it in the same visible line. A bare integer alone in a line - the "3 what?" shape - is
 * the finding. Numbers inside form controls, code, and ISO/standard citations are excluded: those
 * are inputs and references, not claims.
 *
 * Forward-only: the count may fall, never rise (tools/route_numbers_baseline.json).
 *
 * ★STATUS 2026-08-26: NOT YET TRUSTWORTHY - built, run, and deliberately NOT registered as a
 * gate. Three calibration passes (text-node -> block context; identifier exclusions; one-letter
 * units) moved the count 224 -> 203 -> 202, and spot-checks still show entries the rules say
 * should be explained. A ratchet on a number I cannot defend would bank a false claim and
 * make every future run argue with noise, so no baseline is stored. What it already gives is
 * real: a per-route harness with sign-in, block-context judgement and identifier filtering.
 * NEXT: dump the full finding list per page and read it against the rendered page before
 * trusting any count - the samples, not the total, are what will calibrate this.
 *
 * Usage: node tools/prove_route_numbers.mjs
 */
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';
const HIVE = { id: '084c113b-99c0-45c6-a8e8-b4b8349da46d', name: 'Baguio Textile Mills' };
const BASELINE = 'tools/route_numbers_baseline.json';

// the routes a worker and a supervisor actually walk (T9's field loop, T19's triage)
const ROUTES = [
  { id: 'worker-field-loop', role: 'worker',
    acct: { email: 'bryangarcia@auth.workhiveph.com', worker: 'Bryan Garcia' },
    pages: ['index.html', 'logbook.html', 'pm-scheduler.html', 'inventory.html'] },
  { id: 'supervisor-triage', role: 'supervisor',
    acct: { email: 'leandromarquez@auth.workhiveph.com', worker: 'Leandro Marquez' },
    pages: ['index.html', 'alert-hub.html', 'analytics.html', 'hive.html'] },
];

async function signIn(page, acct, role) {
  await page.goto(`${SEEDER}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => !!(window.supabase && typeof window.supabase.createClient === 'function'), { timeout: 25000 });
  await page.evaluate(async ({ email, worker, hive, role }) => {
    const db = (typeof getDb === 'function') ? getDb() : window.db;
    await db.auth.signInWithPassword({ email, password: 'test1234' });
    try {
      localStorage.setItem('wh_worker_name', worker);
      localStorage.setItem('wh_last_worker', worker);
      localStorage.setItem('wh_active_hive_id', hive.id);
      localStorage.setItem('wh_hive_id', hive.id);
      localStorage.setItem('wh_hive_name', hive.name);
      localStorage.setItem('wh_hive_role', role);
    } catch (_) { /* empty-catch-allow: identity seeding is best-effort */ }
  }, { email: acct.email, worker: acct.worker, hive: HIVE, role });
}

// runs IN the page: collect visible numbers and judge each IN ITS RENDERED CONTEXT.
// ★THE FIRST VERSION JUDGED THE TEXT NODE and reported 224 "naked" numbers - nearly all false.
// This platform labels figures with SIBLING ELEMENTS (`<div class="sc-hero">9</div>
// <div class="sc-sub">Open Jobs</div>`), so a correctly-labelled KPI tile looked naked, and
// asset TAGS ("CR-001") and split nodes ("of 30") were counted as figures. A number is explained
// by what a person SEES AROUND IT, so judge the nearest block ancestor's visible text.
const collect = () => {
  const out = [];
  const SKIP_TAGS = new Set(['SCRIPT', 'STYLE', 'INPUT', 'TEXTAREA', 'SELECT', 'OPTION', 'CODE', 'PRE']);
  /* CALIBRATED 2026-08-27: climb to the CARD, not the nearest block.
     The old stop condition was 'first non-inline ancestor with ANY text' - and for a KPI tile
     that ancestor is the div holding nothing but the number, so the context of "9" came back
     as the string "9" and every correctly-labelled tile scored naked. That is why three
     earlier passes moved the total (224 -> 203 -> 202) without converging: they refined what a
     BLOCK is, when the fix was to climb FURTHER.
     Measured on index with this rule: "9" -> "9 OPEN JOBS", "29" -> "29 PM OVERDUE (29 OF 30
     ASSETS)", "3" -> "3 LOW-STOCK PARTS" - 0 of 7 naked, where the old rule scored that page 20.
     Stop condition is SUBSTANTIVE NON-DIGIT TEXT, because a label is words: an ancestor whose
     text is still only digits, punctuation and spaces has not reached the label yet. Hops raised
     to 6 since a tile is often number -> span -> card-body -> card. */
  /* What a person can actually read out of a node: innerText when it works, textContent when
     innerText is empty on a node that IS rendered. */
  const visText = (node) => {
    const it = (node.innerText || '').trim();
    if (it) return it;
    return (node.textContent || '').trim();
  };
  const blockOf = (el) => {
    let n = el, hops = 0;
    while (n && hops < 6) {
      const d = getComputedStyle(n).display;
      /* READ THE SAME WAY IN BOTH PLACES. innerText returns '' for some visible containers on
         this platform (measured on hive: a card whose textContent is "Stair 1 - Digital Logbook
         60 /100 readiness" reports innerText ''), which made the climb walk past the very card
         holding the label. An earlier attempt fixed this HERE only and regressed 64 -> 90,
         because the ctx two lines below still read innerText and came back empty after the climb
         had already stopped. Same reader, both places. */
      const txt = visText(n);
      /* STRIP IDENTIFIERS BEFORE DECIDING THIS IS THE LABEL, for the same reason the explanation
         test below strips them: an asset tag is not a word about the number. Isolated on
         analytics' bar chart - a <div class="bar-row"> reads "CR-001 10", whose non-digit residue
         is "CR-" (3 chars), so the climb stopped THERE believing it had found words; the
         explanation test then removed the tag and found nothing, and the figure was reported
         naked while its real label - the chart's heading - sat one level up. Same stripping in
         both places, so the climb cannot stop on an element whose only "words" are the
         identifier the judge is about to discard. */
      const bare = txt.replace(/\b[A-Z][A-Z0-9]{1,7}[-\/][A-Z0-9]{1,9}\b/gi, ' ');
      const hasWords = bare.replace(/[\d,.\s%₱]/g, '').length >= 3;
      if (d && d !== 'inline' && hasWords) return n;
      n = n.parentElement; hops++;
    }
    return el;
  };
  const seen = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = walker.nextNode())) {
    const el = n.parentElement;
    if (!el || SKIP_TAGS.has(el.tagName)) continue;
    if (!el.getClientRects().length) continue;
    const raw = (n.nodeValue || '').trim();
    if (!raw || !/\d/.test(raw)) continue;
    /* WIDENED 2026-08-27: the old shape ^[A-Z]{2,4}-\d+$ only caught tags whose digits END the
       code, so CONT-32A, FUSE-100A and BAT-12V100 - real inventory part numbers - were being
       reported as naked figures. A part number is letters and digits joined by a separator,
       in any order; what makes it an IDENTIFIER rather than a measurement is that it names a
       thing instead of counting one. */
    if (/^[A-Z][A-Z0-9]{1,7}[-\/][A-Z0-9]{1,9}$/i.test(raw)) continue;   // asset tag / part number
    if (/^[0-9A-F]{6,}$/i.test(raw.replace(/[^0-9A-Za-z]/g, ''))) continue;  // serial / hex id, not a figure
    if (raw.length > 90) continue;                          // prose
    const block = blockOf(el);
    if (seen.has(block)) continue;
    seen.add(block);
    /* A NUMBER IN A TABLE IS LABELLED BY ITS COLUMN HEADER, which is neither an ancestor nor a
       sibling - it is the cell at the same index in the header row. Every remaining finding after
       the card-climb and identifier fixes was this one shape: index and hive reported numbers
       whose ancestor text was EMPTY, and analytics reported "CR-001 10", where the climb stopped
       at the row and found the asset tag rather than the column that says what 10 counts. A
       reader does not have that problem - they read the header once and carry it down the
       column. So the judge reads it too, and the same applies to a definition list (dt/dd) and
       to an aria-label on the cell. */
    const headerFor = (node) => {
      const cell = node.closest('td, th, [role="cell"], [role="gridcell"]');
      if (!cell) return '';
      const row = cell.closest('tr, [role="row"]');
      const table = cell.closest('table, [role="table"], [role="grid"]');
      if (!row || !table) return '';
      const idx = Array.prototype.indexOf.call(row.children, cell);
      /* NOT EVERY HEADER ROW LIVES IN A <thead>. analytics' MTBF table writes its header as the
         first <tr> of the table body, so a thead-first selector found nothing and reported the
         Failures column's values as unlabelled - 8 findings that were labelled all along. Fall
         back to the first row that contains a <th>, then to the table's first row. */
      let head = table.querySelector('thead tr');
      if (!head) {
        const rows = Array.prototype.slice.call(table.querySelectorAll('tr, [role="row"]'));
        head = rows.find(r => r.querySelector('th, [role="columnheader"]')) || rows[0] || null;
      }
      const hcell = head && head !== row && head.children[idx];
      return hcell ? ((hcell.innerText || '').trim() || (hcell.textContent || '').trim()) : '';
    };
    const dtFor = (node) => {
      const dd = node.closest('dd');
      const prev = dd && dd.previousElementSibling;
      return prev && prev.tagName === 'DT' ? (prev.innerText || '').trim() : '';
    };
    const ariaFor = (node) => {
      const a = node.closest('[aria-label]');
      return a ? (a.getAttribute('aria-label') || '').trim() : '';
    };
    const ctx = (visText(block) + ' ' + headerFor(el) + ' ' + dtFor(el) + ' ' + ariaFor(el)).trim().slice(0, 220);
    // A UNIT IS OFTEN ONE LETTER on this platform - 0.6d, 6.7h, 12kg, 3pcs - and the second
    // calibration pass still counted those as naked. The bar is "does something say what this
    // number IS", and a suffixed unit does exactly that.
    const explained =
      /[%₱$]/.test(ctx) ||
      /\d\s*(of|\/)\s*\d/.test(ctx) ||                        // "6 of 30"
      /\d\s*(d|h|m|s|kg|g|mm|cm|km|pcs|pc|hrs?|min|days?|units?)\b/i.test(ctx) ||  // suffixed unit
      /[A-Za-z]{3,}/.test(ctx.replace(/[A-Z]{2,4}-\d+/g, '')) || // a real word beside it
      /\d{4}|:\d\d/.test(ctx);                                // year or clock
    if (!explained) out.push(ctx.replace(/\s+/g, ' ').slice(0, 40));
  }
  return out;
};

const browser = await chromium.launch();
let total = 0;
const findings = [];
for (const route of ROUTES) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  const page = await ctx.newPage();
  await signIn(page, route.acct, route.role);
  for (const pg of route.pages) {
    await page.goto(`${SEEDER}/${pg}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3500);
    const naked = await page.evaluate(collect);
    total += naked.length;
    if (naked.length) findings.push(`${route.id} · ${pg}: ${naked.length} — ${naked.slice(0, 4).join(' | ')}`);
    console.log(`  ${route.id.padEnd(20)} ${pg.padEnd(20)} naked numbers: ${naked.length}`);
  }
  await ctx.close();
}
await browser.close();

for (const f of findings) console.log('    ' + f);
if (!existsSync(BASELINE)) {
  writeFileSync(BASELINE, JSON.stringify({ count: total, established: '2026-08-26' }, null, 1));
  console.log(`BASELINE established: ${total} naked numbers across the walked routes (forward-only)`);
  process.exit(0);
}
const base = JSON.parse(readFileSync(BASELINE, 'utf8')).count;
if (total > base) {
  console.log(`FAIL route-numbers — naked numbers on the walked routes GREW ${base} -> ${total}.`);
  process.exit(1);
}
if (total < base) {
  writeFileSync(BASELINE, JSON.stringify({ count: total, ratcheted: 'auto' }, null, 1));
  console.log(`PASS route-numbers — improved ${base} -> ${total}; ratchet lowered.`);
  process.exit(0);
}
console.log(`PASS route-numbers — held at ${total} naked numbers (baseline ${base}).`);
process.exit(0);
