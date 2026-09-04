/* prove_listing_preview.mjs — T100: see it as a buyer before it is a commitment (2026-08-26).
 *
 * T100's walk found the AI assist SOUND — it names its own inputs and invented no specs from a bare
 * title — and recorded exactly one gap: a seller could not see their listing AS A BUYER WILL before
 * publishing. Posting is a commitment. It spends a credit hold, it goes to moderation, and it is the
 * first thing a stranger judges the seller by, so J3's bar applies: preview before the irreversible.
 *
 * ★AND THIS PROVER EXISTS BECAUSE THE FIX FAILED TWICE, SILENTLY, IN WAYS ONLY A CLICK COULD FIND:
 *   1. The handler called getElementById at script-parse time and returned early when the composer
 *      was not in the DOM yet — the button rendered perfectly and did NOTHING. Declared, never wired.
 *   2. Rewritten as a delegated listener, it was inserted INSIDE the submit handler's function body,
 *      so it only registered once a seller pressed Post — the one moment a preview is useless.
 * Both passed a page load with zero console errors. A gate that checked the button EXISTS would have
 * been green through both. So this one CLICKS it and reads what appears.
 *
 * FOUR ASSERTIONS:
 *   opens          — clicking shows the panel
 *   showsTheDraft  — the title and description a seller typed are in it
 *   priceVocabulary— a blank price reads "Negotiable" and a filled one renders through whFmtPeso,
 *                    which is how a buyer actually sees it; a preview that formats money its own way
 *                    is showing the seller something the buyer will not see
 *   closes         — it toggles shut, because a preview that traps you is a modal, not a preview
 *
 * Non-writing: types into the composer, clicks preview, never submits.
 *
 * Usage: node tools/prove_listing_preview.mjs
 */
import { chromium } from 'playwright';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';

const browser = await chromium.launch();
const v = {};
try {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(String(e).slice(0, 120)));

  await page.goto(`${SEEDER}/marketplace.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(5000);

  Object.assign(v, await page.evaluate(async () => {
    const out = {};
    const set = (id, val) => {
      const e = document.getElementById(id);
      if (e) { e.value = val; e.dispatchEvent(new Event('input', { bubbles: true })); }
    };
    const btn = document.getElementById('btn-preview-post');
    if (!btn) return { error: 'no preview control on the composer' };

    set('post-title', 'SKF 6205 Deep Groove Ball Bearing');
    set('post-desc', 'Sealed bearing, unused, from surplus stock.');
    set('post-part-number', 'SKF-6205-2RS');
    set('post-price', '');

    btn.click();
    await new Promise((r) => setTimeout(r, 400));
    const box = document.getElementById('post-preview');
    const body = document.getElementById('post-preview-body');
    out.opens = !!box && box.style.display !== 'none';
    const txt = (body && body.innerText) || '';
    out.showsTheDraft = txt.includes('SKF 6205 Deep Groove Ball Bearing') && txt.includes('surplus stock');
    out.blankPriceIsNegotiable = /Negotiable/i.test(txt);

    // a filled price must render the way a buyer sees money, not this panel's own idea of it
    set('post-price', '1450');
    btn.click(); await new Promise((r) => setTimeout(r, 200));   // close
    btn.click(); await new Promise((r) => setTimeout(r, 400));   // reopen with the new price
    const txt2 = (document.getElementById('post-preview-body').innerText || '');
    out.pricedViaHelper = txt2.includes(typeof whFmtPeso === 'function' ? whFmtPeso(1450) : '1,450');

    btn.click(); await new Promise((r) => setTimeout(r, 300));
    out.closes = document.getElementById('post-preview').style.display === 'none';
    return out;
  }));
  v.pageerrors = errs.length;
  for (const [k, val] of Object.entries(v)) console.log(`  ${k.padEnd(22)} ${val}`);
} catch (e) {
  v.error = String(e.message || e).slice(0, 180);
  console.log('probe error:', v.error);
} finally {
  await browser.close();
}

const pass = !v.error && v.opens && v.showsTheDraft && v.blankPriceIsNegotiable
          && v.pricedViaHelper && v.closes && v.pageerrors === 0;
console.log((pass ? 'PASS' : 'FAIL') + ` — listing preview: ${JSON.stringify(v)}`);
process.exit(pass ? 0 : 1);
