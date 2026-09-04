/* prove_media_fails_alone.mjs — T197: storage down must not take the write with it (2026-08-26).
 *
 * Supabase Storage is a separate service from the database. When it is unavailable - and it will be,
 * because it fails independently - the question is whether the feature that ATTACHES a photo takes
 * the whole submission down with it. A seller who has written a listing, priced it and typed a
 * description should not lose that because a bucket is refusing writes.
 *
 * This is the same decoupling ethic T12 established for the voice journal, where an AI 429 was
 * losing the worker's typed note: the SECONDARY enrichment must never be able to destroy the
 * PRIMARY work.
 *
 * MEASURED with every bucket write forced to 500 while the database stays up:
 *   the picker announces the real reason ("storage unavailable") rather than swallowing it
 *   #post-image-url is CLEARED, so the listing submits with no photo instead of a broken link
 *   the rest of the form is untouched and still submittable
 *
 * ★IT INJECTS A STORAGE-ONLY OUTAGE, not a general one. Failing everything proves nothing about
 * isolation - the point is that ONE service is down and the others carry on, which is the only
 * shape that distinguishes a decoupled feature from a lucky one.
 *
 * Usage: node tools/prove_media_fails_alone.mjs
 */
import { chromium } from 'playwright';

const BASE = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SB_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
const ACCT = { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234',
               worker: 'Leandro Marquez', hiveName: 'Baguio Textile Mills' };
const PNG_1x1 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';

const browser = await chromium.launch();
const v = {};
try {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  const auth = await ctx.newPage();
  await auth.goto(`${BASE}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await auth.waitForFunction(
    () => !!(window.supabase && window.supabase.createClient) && !!window.SUPABASE_KEY,
    { timeout: 20000 }).catch(() => {});
  const ok = await auth.evaluate(async ({ acct, url }) => {
    try {
      const db = window._whSupabaseClient || window.getDb(url, window.SUPABASE_KEY);
      const { data, error } = await db.auth.signInWithPassword({ email: acct.email, password: acct.pw });
      const uid = data?.session?.user?.id;
      const { data: m } = uid ? await db.from('hive_members').select('hive_id')
        .eq('auth_uid', uid).eq('status', 'active').limit(1).maybeSingle() : { data: null };
      if (m?.hive_id) {
        localStorage.setItem('wh_active_hive_id', m.hive_id);
        localStorage.setItem('wh_hive_id', m.hive_id);
      }
      localStorage.setItem('wh_last_worker', acct.worker);
      localStorage.setItem('wh_hive_name', acct.hiveName);
      localStorage.setItem('wh_hive_role', 'supervisor');
      return !error && !!data?.session;
    } catch (e) { return false; }
  }, { acct: ACCT, url: SB_URL });
  await auth.close();
  if (!ok) throw new Error('sign-in failed');

  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(String(e).slice(0, 90)));
  // STORAGE ONLY: bucket writes fail, the database is untouched
  await page.route('**/storage/v1/object/**', (r) => r.fulfill({
    status: 500, contentType: 'application/json',
    body: JSON.stringify({ message: 'storage unavailable' }),
  }));
  await page.goto(`${BASE}/marketplace.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(7000);

  Object.assign(v, await page.evaluate(async (b64) => {
    const fi = document.getElementById('post-image-file');
    if (!fi) return { pickerMissing: true };
    const bin = atob(b64);
    const arr = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    const dt = new DataTransfer();
    dt.items.add(new File([arr], 'probe.png', { type: 'image/png' }));
    fi.files = dt.files;
    fi.dispatchEvent(new Event('change', { bubbles: true }));
    await new Promise((r) => setTimeout(r, 4000));
    const toast = document.querySelector('#toast, .toast, [role=alert]');
    // ★THE TOAST CONTAINER IS ALWAYS THERE, so `offsetHeight > 0` is not evidence anyone was told.
    // The first version checked exactly that and PASSED its own teeth test with an EMPTY toast -
    // it was detecting the element, not the message. A string is not an announcement until it has
    // words in it.
    const said = toast ? (toast.innerText || '').replace(/\s+/g, ' ').trim() : '';
    return {
      urlCleared: !(document.getElementById('post-image-url') || {}).value,
      spoke: !!(toast && toast.offsetHeight > 0 && said.replace(/[✕×✓\s]/g, '').length >= 8),
      said: said.slice(0, 70),
      formIntact: !!document.getElementById('post-desc'),
    };
  }, PNG_1x1));
  v.pageerrors = errs.length;
  console.log(`  storage forced down -> spoke: ${v.spoke} ("${v.said}") | url cleared: ${v.urlCleared}`
    + ` | form still usable: ${v.formIntact}`);

  // ── The READ side (2026-08-28). Everything above is about ATTACHING a photo while storage is
  // down. The other half is a photo already stored and now unreachable: five render sites across
  // four marketplace pages emit `<img src="${image_url}" alt="${title}">` with no error handling.
  //
  // ★MEASURED BEFORE ASSUMING, and the premise in the roadmap was wrong. It predicted "layout
  // wreckage"; the failed image actually holds its box exactly (218x164 here — the card's CSS
  // sizes it, object-fit does the rest), naturalWidth 0, complete true. Nothing reflows. What the
  // reader loses is not geometry, it is MEANING: a broken-image glyph that never says whether the
  // listing has no photo, or the photo is gone, or the page is broken. So the assertion is about
  // the words, not the pixels.
  Object.assign(v, await page.evaluate(async () => {
    const mk = (src, alt) => new Promise((res) => {
      const i = document.createElement('img');
      i.src = src; i.alt = alt; i.style.cssText = 'width:120px;height:90px;';
      document.body.appendChild(i);
      setTimeout(() => res(i), 1200);
    });
    // a stored photo that cannot load
    const gone = await mk(location.origin + '/storage/v1/object/public/marketplace-listings/wh-probe-absent.jpg',
                          'Probe Listing Title');
    const box = document.querySelector('.wh-photo-failed');
    // and a DECORATIVE image that also fails - it must be left completely alone
    const deco = await mk('/wh-probe-decorative-absent.png', 'decorative');
    return {
      renderExplained: !!box && /photo unavailable/i.test(box.textContent || ''),
      renderNamesWhich: !!box && /Probe Listing Title/.test(box.getAttribute('aria-label') || ''),
      renderKeptBox: !!box && Math.round(box.getBoundingClientRect().width) > 0,
      storedImgReplaced: !document.body.contains(gone),
      decorativeUntouched: document.body.contains(deco) && deco.tagName === 'IMG',
    };
  }));
  console.log(`  stored photo unreachable -> explained: ${v.renderExplained} | names which: ${v.renderNamesWhich}`
    + ` | box kept: ${v.renderKeptBox} | decorative left alone: ${v.decorativeUntouched}`);
  await page.close();
} catch (e) {
  v.error = String(e.message || e).slice(0, 160);
  console.log('probe error:', v.error);
} finally {
  await browser.close();
}

const pass = !v.error && !v.pickerMissing && v.spoke && v.urlCleared && v.formIntact && v.pageerrors === 0
  && v.renderExplained && v.renderNamesWhich && v.renderKeptBox && v.storedImgReplaced && v.decorativeUntouched;
if (!pass && !v.error) {
  console.log('  A storage outage must degrade the PHOTO and nothing else. If the url is left set, the');
  console.log('  listing saves a broken link; if the failure is silent, the seller submits believing a');
  console.log('  photo is attached; if the form is disabled, a separate service took the work hostage.');
}
console.log((pass ? 'PASS' : 'FAIL') + ` — media fails alone: ${JSON.stringify(v)}`);
process.exit(pass ? 0 : 1);
