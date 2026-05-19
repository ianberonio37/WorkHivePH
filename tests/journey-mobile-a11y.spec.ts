/**
 * Tier 6 — Mobile / accessibility (6 scenarios, P1)
 *
 * 375px width, keyboard nav, aria-live toasts, iOS auto-zoom prevention,
 * <main> landmark presence, PDF export on mobile. Several of these are
 * static-content checks (G4, G5) so they have REAL assertions, not fixme.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';
import { readFileSync, readdirSync, statSync } from 'fs';
import { resolve } from 'path';

const ROOT = resolve(__dirname, '..');

function listProductionHtml(): string[] {
  return readdirSync(ROOT)
    .filter((f) => f.endsWith('.html')
      && !/-test\.html$/.test(f)
      && !/\.backup\d*\.html$/.test(f)
      && statSync(resolve(ROOT, f)).isFile());
}

test.describe('Tier 6 — Mobile / accessibility', () => {

  test('G1_pages_have_viewport_meta: every public HTML declares responsive viewport', async () => {
    // WHY: missing viewport meta = mobile renders zoomed-out; field-worker UX dies
    // STATIC: every page must include <meta name="viewport" content="..."> with width=device-width
    const missing: string[] = [];
    for (const f of listProductionHtml()) {
      const content = readFileSync(resolve(ROOT, f), 'utf-8');
      if (!/<meta[^>]*name=["']viewport["'][^>]*width=device-width/i.test(content)) {
        missing.push(f);
      }
    }
    expect(missing, 'every public page must declare a responsive viewport meta').toEqual([]);
  });

  test('G2_interactive_inputs_avoid_keyboard_trap_styles: no outline:none without :focus-visible alternative', async () => {
    // WHY: removing focus outlines without a replacement breaks keyboard navigation (WCAG 2.4.7)
    const offenders: string[] = [];
    for (const f of listProductionHtml()) {
      const content = readFileSync(resolve(ROOT, f), 'utf-8');
      // Look for global wildcards stripping outline. Per-element :focus rules are fine if paired with :focus-visible.
      if (/(^|[^\.\w])\*\s*\{[^}]*outline\s*:\s*none/.test(content) &&
          !/:focus-visible/.test(content)) {
        offenders.push(f);
      }
    }
    expect(offenders, 'pages must not strip outline globally without :focus-visible fallback').toEqual([]);
  });

  test('G3_toast_aria_live_attributes: every page with #toast declares aria-live + role(alert|status)', async () => {
    // WHY: screen readers announce save confirmations (mobile-maestro skill)
    // STATIC: any page that ships a #toast element must include aria-live="polite" AND a screen-reader role.
    // Both role="alert" and role="status" are valid ARIA patterns paired with aria-live="polite".
    const offenders: string[] = [];
    for (const f of listProductionHtml()) {
      const content = readFileSync(resolve(ROOT, f), 'utf-8');
      const toastMatch = content.match(/<[^>]*id=["']toast["'][^>]*>/);
      if (!toastMatch) continue;
      const tag = toastMatch[0];
      const hasRole = /role=["'](?:alert|status)["']/.test(tag);
      const hasLive = /aria-live=["']polite["']/.test(tag);
      if (!hasRole || !hasLive) offenders.push(f);
    }
    expect(offenders, 'every #toast must have role="alert|status" + aria-live="polite"').toEqual([]);
  });

  test('G4_no_text_sm_on_wh_input: iOS auto-zoom prevented across all pages', async () => {
    // WHY: text-sm on .wh-input drops font below 16px → iOS auto-zoom (mobile-maestro skill)
    // STATIC ASSERTION: grep all root HTML for the anti-pattern
    let found: string[] = [];
    for (const f of listProductionHtml()) {
      const content = readFileSync(resolve(ROOT, f), 'utf-8');
      if (/class=["'][^"']*\bwh-input\b[^"']*\btext-(?:sm|xs)\b/.test(content)) {
        found.push(f);
      }
    }
    expect(found, 'no page should combine .wh-input with text-sm/text-xs').toEqual([]);
  });

  test('G5_main_landmark_present_on_every_page: every public page has <main>', async () => {
    // WHY: screen-reader skip-nav requires single <main> landmark (a11y rule, fixed 2026-05-18)
    // STATIC ASSERTION: every root HTML page contains at least one <main element
    const missing: string[] = [];
    for (const f of listProductionHtml()) {
      const content = readFileSync(resolve(ROOT, f), 'utf-8');
      if (!/<main\b/i.test(content)) missing.push(f);
    }
    expect(missing, 'every public page must include a <main> landmark').toEqual([]);
  });

  test('G6_static_no_avoid_all_in_html2pdf_config: no avoid-all in any pagebreak config', async () => {
    // WHY: same as G6 but static (faster, runs always)
    const offenders: string[] = [];
    for (const f of listProductionHtml()) {
      const content = readFileSync(resolve(ROOT, f), 'utf-8');
      if (/pagebreak\s*:\s*\{[^}]*avoid-all/.test(content)) offenders.push(f);
    }
    expect(offenders, 'no page should have avoid-all in html2pdf pagebreak config').toEqual([]);
  });
});
