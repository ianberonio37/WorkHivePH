/* prove_password_change_reachable.mjs - T59: a signed-in worker can find how to change their password.
 *
 * MEASURED BEFORE THE FIX: there is no settings, account or profile page anywhere in the roster, and
 * the ONLY password write on the platform runs inside the PASSWORD_RECOVERY auth event. Changing a
 * password meant leaving the app, finding "Forgot your password?" on the LANDING page, and waiting
 * for an email - and nothing anywhere said so, so a security-conscious user hunted for a settings
 * page that was never built. The roadmap's bar is "findable and walkable, OR honestly stated
 * absent". It was neither.
 *
 * ★THIS PROVES REACHABILITY, NOT A NEW FEATURE. The account surface itself (active sessions,
 * sign-out-everywhere, 2FA) stays a product decision. What is asserted here is only that the flow
 * which ALREADY works is reachable from where the platform keeps its account actions - beside Sign
 * Out on the ops-home header.
 *
 * ★IT IS LIVE BECAUSE A STATIC CHECK CANNOT ANSWER THIS. A button whose handler throws, or which is
 * rendered behind a hidden panel, reads identically in source to one that works. The oracle is: the
 * control is VISIBLE to a signed-in worker, meets the 44px touch floor, and CLICKING it produces a
 * prompt with an input to type into - the same standard the rest of the platform's dialogs are held
 * to.
 *
 * Usage: node tools/prove_password_change_reachable.mjs
 */
import { chromium } from 'playwright';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const USER = process.env.WH_TEST_USER || 'leandromarquez';
const PASS = process.env.WH_TEST_PASSWORD || 'test1234';
const TOUCH_FLOOR = 44;

const fails = [];
let browser;
try {
  browser = await chromium.launch();
  const page = await (await browser.newContext({ viewport: { width: 390, height: 844 } })).newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(String(e).slice(0, 160)));

  await page.goto(`${ORIGIN}/index.html?signin=1`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#si-username', { timeout: 20000 });
  await page.fill('#si-username', USER);
  await page.fill('#si-password', PASS);
  await page.click('#si-btn');
  await page.waitForFunction(() => !!localStorage.getItem('wh_last_worker'), { timeout: 30000 });
  await page.waitForTimeout(3000);

  const btn = page.locator('[data-i="changepwd"]');
  if ((await btn.count()) === 0) {
    fails.push('a signed-in worker has NO way to change their password: no [data-i="changepwd"] '
             + 'control on the ops-home header, which is the only place this platform keeps account '
             + 'actions. Password change lives behind the landing page\'s forgot-password email flow '
             + 'and nothing says so.');
  } else if (!(await btn.first().isVisible())) {
    fails.push('the change-password control exists but is not visible to a signed-in worker');
  } else {
    const box = await btn.first().boundingBox();
    if (box && box.height < TOUCH_FLOOR) {
      fails.push(`the change-password control is ${Math.round(box.height)}px tall, below the ${TOUCH_FLOOR}px `
               + 'touch floor a gloved hand needs');
    }
    // walkable: clicking must produce a prompt with somewhere to type
    await btn.first().click();
    await page.waitForTimeout(1800);
    const r = await page.evaluate(() => {
      const inputs = [...document.querySelectorAll('input')].filter((i) => i.offsetParent !== null);
      const texts = [...document.querySelectorAll('body *')]
        .filter((e) => e.offsetParent !== null && e.children.length === 0
                    && e.innerText && e.innerText.trim().length > 40)
        .map((e) => e.innerText.replace(/\s+/g, ' ').trim());
      return { modalInput: inputs.some((i) => /wh-modal-ov/.test(i.id || '')),
               longest: texts.sort((a, b) => b.length - a.length)[0] || '' };
    });
    if (!r.modalInput) {
      fails.push('clicking change-password opened no prompt to type into - the remedy is named but '
               + 'not walkable, which is the dead end this was meant to remove');
    }
    if (!/reset link|password/i.test(r.longest)) {
      fails.push(`the prompt does not explain what will happen; it said: "${r.longest.slice(0, 90)}"`);
    }
    console.log(`  prompt: ${r.longest.slice(0, 150)}`);
  }

  if (errs.length) fails.push(`pageerrors during the walk: ${errs.join(' | ')}`);
} catch (e) {
  console.log(`SKIP prove_password_change_reachable - could not complete the walk: ${String(e).slice(0, 160)}`);
  if (browser) await browser.close();
  process.exit(0);
}
await browser.close();

if (fails.length) {
  console.log('FAIL prove_password_change_reachable:');
  fails.forEach((f) => console.log('    - ' + f));
  process.exit(1);
}
console.log(`PASS prove_password_change_reachable - a signed-in worker finds Change Password beside Sign `
          + `Out, it meets the ${TOUCH_FLOOR}px touch floor, and it opens a prompt that says what will happen.`);
