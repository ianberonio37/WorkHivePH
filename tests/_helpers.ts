/**
 * Shared helpers for WorkHive UI flow tests.
 *
 * The regression class that triggered this Playwright suite (2026-05-12
 * walkthrough): a form submit was BLOCKED by wh-capture-validate.js, but
 * the caller showed "Entry saved" anyway. The user thought their entry was
 * logged when it wasn't. assertSubmitSucceeded / assertSubmitFailed below
 * give every page-spec a one-liner to lock that pattern down forever.
 */
import { Page, expect } from '@playwright/test';

/** Wait for a toast (any class) and return its text. */
export async function readToast(page: Page, timeoutMs = 4000): Promise<string | null> {
  try {
    const toast = page.locator('#toast, .wh-toast, [role="status"]').first();
    await toast.waitFor({ state: 'visible', timeout: timeoutMs });
    return (await toast.innerText()).trim();
  } catch {
    return null;
  }
}

/**
 * Assert a form submit SUCCEEDED — i.e. the success toast appeared AND
 * the silent-failure pattern did NOT happen.
 *
 * If the page shows a generic "Saved" toast even when the underlying
 * write failed, this assertion alone isn't enough; pair with a follow-up
 * DB query OR a `assertRowAppears` reading the just-written row back.
 */
export async function assertSubmitSucceeded(
  page: Page,
  successToastMatcher: RegExp | string,
  _consoleLog?: { stripeline: string },
) {
  // The platform shows transient toasts (draft-restored, sync-success,
  // etc.) that can briefly mask the save-success toast. Poll the toast
  // text for up to 4s, returning as soon as a toast matching the success
  // pattern appears. This is more robust than a single readToast() call.
  const isMatch = (t: string | null) => {
    if (!t) return false;
    return typeof successToastMatcher === 'string'
      ? t.includes(successToastMatcher)
      : successToastMatcher.test(t);
  };
  const deadline = Date.now() + 5000;
  let lastSeen: string | null = null;
  while (Date.now() < deadline) {
    const t = await readToast(page, 600);
    if (t) lastSeen = t;
    if (isMatch(t)) return;   // success — done
    await page.waitForTimeout(150);
  }
  throw new Error(
    `expected success toast matching ${successToastMatcher} but last seen toast was: ${lastSeen}`,
  );
}

/**
 * Assert a form submit was BLOCKED by validation — i.e. the page
 * rejected the input AND did NOT show a success toast.
 *
 * Pass `errorPattern` to match the rejection toast/error message.
 * Pass `forbiddenSuccessPattern` (defaults to /saved|added/i) to assert
 * the success toast did NOT fire. This is the exact silent-failure
 * regression the user hit.
 */
export async function assertSubmitBlocked(
  page: Page,
  errorPattern: RegExp,
  forbiddenSuccessPattern: RegExp = /saved|added|recorded|sent/i,
) {
  const toast = await readToast(page);
  expect(toast, 'no toast appeared after blocked submit — UX silent-fail').not.toBeNull();
  expect(toast!, `toast didn't match expected error pattern: ${toast}`).toMatch(errorPattern);
  // CRITICAL: the toast must NOT be a "saved" toast. If both fire, the
  // user sees the success message and thinks the entry was saved.
  expect(toast!, `forbidden success toast leaked through: ${toast}`)
    .not.toMatch(forbiddenSuccessPattern);
}

/**
 * After a successful submit, assert the row appears in a DB read.
 * This catches the case where the page shows "saved" but the write
 * was silently dropped (e.g. wrong hive_id, RLS rejection) so the row
 * never appears in any read path.
 */
export async function assertRowAppears(
  page: Page,
  /** A locator that resolves to the row when it appears (e.g. the
   *  team feed entry, the inventory list row) */
  rowLocator: (page: Page) => ReturnType<Page['locator']>,
  /** Optional: trigger that reloads the read path (e.g. click team
   *  feed tab). If omitted, just waits on the locator. */
  trigger?: () => Promise<void>,
  timeoutMs = 6000,
) {
  if (trigger) await trigger();
  await expect(rowLocator(page).first()).toBeVisible({ timeout: timeoutMs });
}

/**
 * Sentinel test helper: return the combined page source INCLUDING the
 * contents of every external <script src=...> file.
 *
 * Background: many Layer 0 validators check for symbols (function names,
 * constants, regex patterns) in .ts/.js source files. The sentinel test
 * suite mirrors those checks at runtime - but a browser's
 * `document.documentElement.outerHTML` only contains INLINE script bodies.
 * External `<script src=...>` references show up as URLs, not as code.
 *
 * This helper fetches each external script the page loads, then concatenates
 * everything into one string. A test that does `/AbortSignal\.timeout/.test(src)`
 * will now match whether the symbol lives in inline code or in utils.js.
 *
 * Implementation note: fetches use `cache: 'force-cache'` so repeated calls
 * within one spec hit the browser cache. CDN scripts (jsdelivr etc.) are
 * skipped to keep runs fast - they're rarely what Layer 0 rules target.
 */
export async function pageSrcWithExternals(page: Page): Promise<string> {
  return await page.evaluate(async () => {
    const scriptEls = Array.from(document.querySelectorAll('script[src]')) as HTMLScriptElement[];
    const sameOrigin = (url: string) => {
      try { return new URL(url, location.href).origin === location.origin; }
      catch { return false; }
    };
    const fetched: string[] = [];
    for (const s of scriptEls) {
      const url = s.src;
      if (!url || !sameOrigin(url)) continue;
      try {
        const r = await fetch(url, { cache: 'force-cache' as RequestCache });
        if (r.ok) fetched.push(await r.text());
      } catch (_) { /* ignore */ }
    }
    return document.documentElement.outerHTML + '\n' + fetched.join('\n');
  });
}

/** Wait for the page to finish its first canonical-source read. Pages
 *  that gate UI on identity (localStorage worker + hive) need a beat
 *  before forms are interactive. */
export async function waitForPageReady(page: Page) {
  // Wait until the wh-source-chip is rendered OR a form is interactive
  await Promise.race([
    page.locator('#wh-source-chip').waitFor({ state: 'visible', timeout: 5000 }).catch(() => {}),
    page.locator('form').first().waitFor({ state: 'visible', timeout: 5000 }).catch(() => {}),
    page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {}),
  ]);
}
