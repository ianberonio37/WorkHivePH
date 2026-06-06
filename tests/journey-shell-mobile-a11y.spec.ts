/**
 * journey-shell-mobile-a11y.spec.ts — Shell front-door mobile + modal a11y.
 * =========================================================================
 *
 * Born from the Grounded MCP Sweep, Wave 0 (index.html, 2026-06-06).
 *
 * The static `validate_mobile.py` has a Tailwind blind spot: it only inspects
 * the `.wh-input` CSS class (not Tailwind `text-sm` = 14px inputs) and only
 * INLINE `style="height:..px"` on buttons (not Tailwind-padding-sized buttons
 * like `p-2` / `py-1.5`). So index.html passed the static check while the LIVE
 * page shipped 14px auth inputs (iOS auto-zoom) and 34px header tap targets.
 *
 * These assertions read COMPUTED values in a real browser at 390px — the only
 * reliable way to lock a fix whose size comes from a utility class + a CSS
 * override. They guard the sweep's four root-cause fixes:
 *   1+2. header "Sign In" + #hamburger >= 44px tall on mobile (gloved hands)
 *   3.   all six auth inputs >= 16px (iOS Safari auto-zoom guard)
 *   4.   #signin-modal is a labelled role="dialog" + aria-modal; ESC closes it
 */
import { test, expect } from './_fixtures';

const BASE = 'http://127.0.0.1:5000';

test.use({ viewport: { width: 390, height: 844 } });

test.describe('Shell front-door — mobile + modal a11y (grounded sweep Wave 0)', () => {

  test('auth modal inputs render >= 16px (iOS auto-zoom guard)', async ({ rawPage }) => {
    await rawPage.goto(`${BASE}/workhive/index.html?signin=1`);
    await rawPage.waitForSelector('#signin-modal:not(.hidden)', { timeout: 12000 });
    await rawPage.waitForSelector('#si-username', { state: 'visible', timeout: 6000 });

    // su-* live in the hidden Sign Up panel; getComputedStyle still resolves
    // font-size for display:none elements, so the #signin-modal input rule is
    // verifiable for all six without switching tabs.
    const ids = ['si-username', 'si-password', 'su-username', 'su-password', 'su-confirm', 'su-displayname'];
    for (const id of ids) {
      const fs = await rawPage.evaluate((i) => {
        const el = document.getElementById(i);
        return el ? parseFloat(getComputedStyle(el).fontSize) : null;
      }, id);
      expect(fs, `#${id} font-size must be >= 16px (was 14px text-sm -> iOS zoom)`).not.toBeNull();
      expect(fs as number, `#${id} font-size must be >= 16px`).toBeGreaterThanOrEqual(16);
    }
  });

  test('header Sign In + hamburger are >= 44px tall on mobile', async ({ rawPage }) => {
    await rawPage.goto(`${BASE}/workhive/index.html`);
    await rawPage.waitForLoadState('domcontentloaded');
    await rawPage.waitForTimeout(400);

    const sizes = await rawPage.evaluate(() => {
      const vis = (el: Element | null) => !!(el && (el as any).checkVisibility && (el as any).checkVisibility());
      const h = (el: Element | null) => (el ? Math.round(el.getBoundingClientRect().height) : 0);
      const sb = [...document.querySelectorAll('.signin-btn')].filter(vis)[0] || null;
      const hb = document.getElementById('hamburger');
      return { signin: h(sb), hamburger: vis(hb) ? h(hb) : null };
    });

    expect(sizes.signin, 'header Sign In must be >= 44px tall on mobile').toBeGreaterThanOrEqual(44);
    if (sizes.hamburger !== null) {
      expect(sizes.hamburger, '#hamburger must be >= 44px tall on mobile').toBeGreaterThanOrEqual(44);
    }
  });

  test('sign-in modal is a labelled dialog and ESC closes it', async ({ rawPage }) => {
    await rawPage.goto(`${BASE}/workhive/index.html?signin=1`);
    await rawPage.waitForSelector('#signin-modal:not(.hidden)', { timeout: 12000 });

    const attrs = await rawPage.evaluate(() => {
      const m = document.getElementById('signin-modal')!;
      return {
        role: m.getAttribute('role'),
        ariaModal: m.getAttribute('aria-modal'),
        ariaLabel: m.getAttribute('aria-label') || m.getAttribute('aria-labelledby'),
      };
    });
    expect(attrs.role, 'sign-in modal must be role="dialog"').toBe('dialog');
    expect(attrs.ariaModal, 'sign-in modal must be aria-modal="true"').toBe('true');
    expect(attrs.ariaLabel, 'dialog needs an accessible name').toBeTruthy();

    // ESC must close the dialog (WCAG dialog pattern; matches whConfirm/whPrompt).
    await rawPage.keyboard.press('Escape');
    await rawPage.waitForTimeout(250);
    const hidden = await rawPage.evaluate(
      () => document.getElementById('signin-modal')!.classList.contains('hidden'),
    );
    expect(hidden, 'ESC must close the sign-in dialog').toBe(true);
  });
});
