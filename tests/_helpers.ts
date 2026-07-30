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

/**
 * Bypass the WorkHive Stair maturity gate at the fetch layer.
 *
 * Several pages (predictive, ai-quality, alert-hub, hive, ph-intelligence)
 * gate rendering behind a hive readiness check — Stair 2/3/etc — and fall
 * back to an honest empty state when the hive lacks enough corrective
 * history. Test fixtures never carry that much real data, so those pages
 * render blank tiles in CI and fail every "card hero populated" check.
 *
 * This helper synthesises a Stair-5 response so the page renders its real
 * query path. Mirrors journey-rag-flywheel-walk.spec.ts pattern (one source
 * of truth so we don't drift across specs).
 *
 * Call from a beforeEach BEFORE page.goto.
 */
/**
 * Pre-dismiss the supervisor first-run "What should WorkHive focus on?" intent modal.
 *
 * It is a legitimate product behaviour, not a bug: `maybeShowIntentCapture()` opens it for a
 * SUPERVISOR whose hive has no intent set, it is `aria-modal="true"` so it correctly intercepts
 * pointer events, and its "Later" is remembered (verified live 2026-07-27 — it does not reappear on
 * the next load). But a spec that lands on the board as a supervisor and clicks straight into the
 * page will have every click swallowed by the overlay, which is exactly how FIVE supervisor-journey
 * tests were failing before this helper existed — a stale test, not a regression (confirmed by
 * reproducing them on the pre-session baseline).
 *
 * The page keys the dismissal off sessionStorage `wh_intent_dismissed_<HIVE_ID>`, so set it for both
 * hive-id keys before any page script runs. addInitScript rather than a post-load click: the modal
 * opens asynchronously after the membership check, so clicking it away is a race.
 */
export async function dismissIntentCapture(page: Page) {
  await page.addInitScript(() => {
    try {
      const ids = [localStorage.getItem('wh_active_hive_id'), localStorage.getItem('wh_hive_id')];
      ids.filter(Boolean).forEach(id => sessionStorage.setItem('wh_intent_dismissed_' + id, '1'));
    } catch (_) { /* noop */ }
  });
}

export async function bypassMaturityGate(page: Page) {
  await page.addInitScript(() => {
    try {
      const hiveId = localStorage.getItem('wh_active_hive_id') ||
                     localStorage.getItem('wh_hive_id') || '';
      if (hiveId) {
        localStorage.setItem(`wh_hive_maturity_stair_${hiveId}`, '5');
      }
      localStorage.setItem('wh_hive_maturity_stair', '5');
    } catch (_) { /* noop */ }
    const origFetch = window.fetch;
    (window as any).fetch = async function(...args: any[]) {
      const url = String(args[0] || '');
      if (url.includes('v_hive_readiness_truth')) {
        return new Response(JSON.stringify([{
          current_stair:   5,
          composite_score: 1.0,
          blocker_summary: '',
          evidence:        { test_bypass: 'gate bypassed at fetch layer' },
        }]), { status: 200, headers: { 'Content-Type': 'application/json' } });
      }
      return origFetch.apply(this, args as any);
    };
    (window as any).checkMaturityGate = async function() {
      return {
        blocked: false, currentStair: 5, currentStairName: 'Industry Leader',
        requiredStair: 1, requiredStairName: '(test bypass)',
        blockerSummary: '(maturity gate bypassed for L2 test)',
        evidence: {}, compositeScore: 1.0,
      };
    };
  });
}

/** Wait for a toast (any class) and return its text. */
export async function readToast(page: Page, timeoutMs = 4000): Promise<string | null> {
  try {
    // `.wh-source-chip` is EXCLUDED, and that exclusion is the whole point of this selector.
    //
    // The shared provenance/freshness chip (`whSourceChip` in utils.js) renders as
    // `<p class="wh-source-chip" role="status" aria-live="polite">Live &middot; Based on your … &middot;
    // updated …</p>`. It was given `role=status` deliberately and correctly, so every page that shows a
    // source chip satisfies the G1 "visibility of system status" rubric — but it is PERSISTENT and it sits
    // ahead of the toast container in the DOM. `[role="status"]` + `.first()` therefore locked onto the
    // chip and could never see a toast, no matter how long the caller polled.
    //
    // Found 2026-07-30: three specs (logbook ×2, inventory) reported product SILENT-FAILURES — including
    // the regression test for the 2026-05-12 silent-fail bug — and every one of them was this. The
    // reported "last seen toast" was byte-identical across three different pages, which is the tell: a
    // per-action toast varies, shared status chrome does not. The failures had been invisible because
    // `validate_playwright_smoke` never ran (its seeder ping timed out on a slow route).
    //
    // A correct accessibility improvement broke the test helper's assumption that `role=status` means
    // "toast". The page was right; the selector was wrong.
    const toast = page
      .locator('#toast, .wh-toast, [role="status"]:not(.wh-source-chip)')
      .first();
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
/**
 * Clear any saved form DRAFT before the page's scripts run, so a validation test starts from the empty
 * form it claims to be testing.
 *
 * MUST be called BEFORE `page.goto` — it installs an init script, because the draft is restored during
 * page load and clearing localStorage afterwards is too late.
 *
 * WHY THIS EXISTS (found 2026-07-30): the regression test for the 2026-05-12 logbook silent-fail bug
 * deliberately leaves the problem field empty and asserts the submit is blocked. It failed reporting a
 * toast of `Draft restored. Continue where you left off.` — and the page's own instrumentation logged
 * `[capture-validate] logbook_add_entry_v1 passed`. The validation was RIGHT: `restoreDraft()` had
 * refilled `f-problem` from a draft left by an earlier test, so the field the spec believed was empty
 * had content, and a valid submit correctly produced no error toast.
 *
 * The test was asserting against a form state it did not control — and it only fails when a draft happens
 * to exist, which is why it read as a flake. Draft-restore is a real, valuable feature; the fix belongs in
 * the spec's isolation, never in the page.
 */
export async function clearFormDrafts(page: Page) {
  await page.addInitScript(() => {
    try {
      Object.keys(localStorage)
        .filter(k => k.includes('_draft_') || k.endsWith('_draft'))
        .forEach(k => localStorage.removeItem(k));
    } catch (_e) { /* empty-catch-allow: storage unavailable is not a test failure */ }
  });
}

export async function assertSubmitBlocked(
  page: Page,
  errorPattern: RegExp,
  forbiddenSuccessPattern: RegExp = /saved|added|recorded|sent/i,
) {
  // POLL, and collect EVERY toast seen — do not judge on a single snapshot.
  //
  // Its sibling assertSubmitSucceeded already polls, for a reason stated in its own comment: "the
  // platform shows transient toasts (draft-restored, sync-success, etc.) that can briefly mask" the one
  // you are waiting for. This function did a single `readToast()` and matched that snapshot, so whichever
  // toast happened to be on screen at that instant decided the verdict.
  //
  // Found 2026-07-30: the 2026-05-12 silent-fail regression test failed reporting
  // `toast didn't match expected error pattern: Draft restored. Continue where you left off.` — the
  // page's validation was working perfectly; a draft-restored toast simply won the race. (The run before
  // that, the same assertion had locked onto the persistent `.wh-source-chip` status region, which is now
  // excluded in readToast — two different masks over the same single-snapshot flaw.)
  //
  // Collecting all of them also makes the leak check STRONGER than it was. The old code asserted "the one
  // toast I happened to see is not a success toast"; this asserts that no success toast appeared AT ALL
  // during the window, which is the actual regression being locked — a validation error AND a "saved"
  // message both firing, leaving the user believing the entry was stored.
  const seen: string[] = [];
  let matched: string | null = null;
  const deadline = Date.now() + 5000;
  while (Date.now() < deadline) {
    const t = await readToast(page, 600);
    if (t && !seen.includes(t)) seen.push(t);
    if (t && errorPattern.test(t)) { matched = t; break; }
    await page.waitForTimeout(150);
  }

  expect(seen.length, 'no toast appeared at all after a blocked submit — UX silent-fail').toBeGreaterThan(0);
  expect(
    matched,
    `no toast matched the expected error pattern ${errorPattern}. Toasts seen: ${JSON.stringify(seen)}`,
  ).not.toBeNull();

  // CRITICAL: no "saved" toast may fire on a blocked submit. If both fire, the user reads the success
  // message and believes the entry was stored.
  const leaked = seen.filter(t => forbiddenSuccessPattern.test(t));
  expect(leaked, `forbidden success toast leaked through on a BLOCKED submit: ${JSON.stringify(leaked)}`)
    .toEqual([]);
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
    const missing: string[] = [];
    for (const s of scriptEls) {
      const url = s.src;
      if (!url || !sameOrigin(url)) continue;
      // RETRY ONCE, then RECORD the failure. This used to be `if (r.ok) …` plus
      // `catch (_) { /* ignore */ }`, which silently dropped any script that blipped and returned a
      // SILENTLY PARTIAL source. Every caller greps that string for a symbol, so a dropped script made
      // the assertion report a product defect — "PM write payloads must carry hive_id" failed on a
      // pm-scheduler run whose page was perfectly correct; the script containing `hive_id` just had not
      // been read. Intermittent, and indistinguishable from a real regression.
      let text: string | null = null;
      for (let attempt = 0; attempt < 2 && text === null; attempt++) {
        try {
          const r = await fetch(url, { cache: 'force-cache' as RequestCache });
          if (r.ok) text = await r.text();
        } catch (_) { /* empty-catch-allow: retried below, then reported by URL */ }
      }
      if (text === null) missing.push(url);
      else fetched.push(text);
    }
    // A partial source cannot support "the page references X" — so say so instead of answering wrongly.
    if (missing.length) {
      throw new Error(
        'pageSrcWithExternals could not read ' + missing.length + ' same-origin script(s) after a retry: ' +
        missing.join(', ') + '. The source is INCOMPLETE, so any assertion over it would be meaningless — ' +
        'this is the harness failing to read the page, not the page missing a symbol.');
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
