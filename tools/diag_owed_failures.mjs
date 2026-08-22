// diag_owed_failures.mjs — dump what a FAILING owed-walk probe actually saw, so the verdict can be
// judged instead of guessed. Written after the batch walker's first run produced 21 failures of
// which 11 were a single wrong comparison in my own harness (`docOverflow === 0` flagging the
// scrollbar gutter). A failing probe is a hypothesis; this prints the evidence that settles it.
import { chromium } from 'playwright';
import path from 'path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SEEDER = 'http://127.0.0.1:5000';
const REST = /\/rest\/v1\/(?!rpc\/)/;

// Identity resolves at RUNTIME via the journeys helper — a pinned hive UUID rots at every reseed
// and turns this diagnostic into a silent no-op (the test-hive-fixtures class; converted 2026-08-23).
import { signIn, assertSignedIn } from './live_page_journeys.mjs';
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
await assertSignedIn(signIn(context, 'supervisor'));

// 1. degraded on marketplace.html — the banner is included, so WHY was it not seen?
{
  const page = await context.newPage();
  await page.goto(SEEDER + '/workhive/marketplace.html', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2600);
  await context.setOffline(true);
  await page.evaluate(() => window.dispatchEvent(new Event('offline')));
  await page.waitForTimeout(2000);
  const d = await page.evaluate(() => {
    const el = document.getElementById('wh-offline-banner')
      || [...document.querySelectorAll('div')].find(x => /you are offline/i.test(x.innerText || ''));
    return {
      bannerExists: !!el,
      bannerId: el ? el.id : null,
      bannerText: el ? (el.innerText || '').trim().slice(0, 80) : null,
      display: el ? getComputedStyle(el).display : null,
      onLine: navigator.onLine,
      bodyHead: (document.body.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 160),
    };
  });
  console.log('\n[1] DEGRADED · marketplace.html');
  console.log('   ', JSON.stringify(d));
  await context.setOffline(false);
  await page.close();
}

// 2. error on the surfaces that came back "indistinguishable from empty" or with no error language
for (const url of ['/workhive/marketplace-seller.html', '/workhive/marketplace-seller-profile.html',
                   '/workhive/community.html', '/workhive/public-feed.html']) {
  const page = await context.newPage();
  await context.route(REST, r => r.fulfill({
    status: 500, contentType: 'application/json',
    body: JSON.stringify({ code: '500', message: 'induced failure' }),
  }));
  await page.goto(SEEDER + url, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2800);
  const t = await page.evaluate(() => {
    const m = document.querySelector('main') || document.body;
    return (m.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 320);
  });
  await context.unroute(REST);
  console.log(`\n[2] ERROR(500) · ${url}`);
  console.log('    ', t || '(EMPTY SCREEN)');
  await page.close();
}

// 3. which elements actually overflow on marketplace.html under long content
{
  const page = await context.newPage();
  const LONG = 'Emergency Switchgear Overhaul and Transformer Oil Regeneration for the Southern Tagalog Industrial Estate Incorporated';
  await context.route(REST, async r => {
    let res; try { res = await r.fetch(); } catch (e) { return r.continue(); }
    let b; try { b = await res.json(); } catch (e) { return r.fulfill({ response: res }); }
    if (Array.isArray(b) && b.length) for (const row of b.slice(0, 3)) for (const k of Object.keys(row))
      if (/name|title|label/i.test(k) && typeof row[k] === 'string') row[k] = LONG;
    return r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(b) });
  });
  await page.goto(SEEDER + '/workhive/marketplace.html', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2800);
  const o = await page.evaluate(() => {
    const m = document.querySelector('main') || document.body;
    return [...m.querySelectorAll('*')]
      .filter(el => el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0 && getComputedStyle(el).overflowX === 'visible')
      .slice(0, 8)
      .map(el => ({
        tag: el.tagName,
        cls: (el.className || '').toString().slice(0, 40),
        over: el.scrollWidth - el.clientWidth,
        w: Math.round(el.clientWidth),
        text: (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 50),
      }));
  });
  await context.unroute(REST);
  console.log('\n[3] EDGE overflowers · marketplace.html');
  o.forEach(x => console.log('    ', JSON.stringify(x)));
  await page.close();
}

await browser.close();
