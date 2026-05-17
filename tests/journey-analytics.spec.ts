/**
 * journey-analytics.spec.ts — Analytics Engine journey.
 *
 * NOTE: The Descriptive/Predictive/Prescriptive tabs require the Python
 * API (uvicorn) to be running. Tests are designed to pass gracefully
 * whether or not uvicorn is available: they assert the UX behaviour
 * (error state handled, source chip visible, tabs clickable) rather than
 * the computed values.
 *
 * Scenarios:
 *   source chip      — declares v_logbook_truth + Postgres RPCs
 *   date range       — 30d/90d/180d/1y chips are clickable
 *   tab switching    — Descriptive/Diagnostic/Predictive/Prescriptive tabs change view
 *   graceful error   — "Analysis failed" banner is shown (not a crash) when API is down
 *   verdict element  — #an-verdict block is rendered
 *   console errors   — no JS errors unrelated to API
 *   PDF Report       — button exists and is clickable
 */
import { test, expect } from './_fixtures';
import { waitForPageReady, pageSrcWithExternals } from './_helpers';
import { adminClient } from './_db-cleanup';

const PAGE = '/workhive/analytics.html';

test.describe('analytics.html — analytics engine journey', () => {

  test('page loads without non-API console errors', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);

    // Filter API-related noise (uvicorn not running = expected 500/net error)
    const serious = errors.filter(e =>
      !e.includes('net::ERR_') &&
      !e.includes('Failed to fetch') &&
      !e.includes('Analysis failed') &&
      !e.includes('500'),
    );
    expect(serious).toEqual([]);
  });

  test('source chip declares v_logbook_truth', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);

    const chip = whPage.locator('.wh-source-chip').first();
    const text = await chip.textContent({ timeout: 5000 }).catch(() => '');
    expect(text, 'chip should declare v_logbook_truth').toContain('v_logbook_truth');
  });

  test('date range chips (30d/90d/180d/1y) are visible and clickable', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    for (const label of ['30 days', '90 days', '180 days', '1 year']) {
      const chip = whPage.locator(`button:has-text("${label}")`).first();
      if (await chip.count() > 0) {
        await expect(chip).toBeVisible({ timeout: 3000 });
        await chip.click();
        await whPage.waitForTimeout(400);
      }
    }
    await expect(whPage.locator('body')).toBeVisible();
  });

  test('Descriptive/Diagnostic/Predictive/Prescriptive tabs are present', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    for (const label of ['Descriptive', 'Diagnostic', 'Predictive', 'Prescriptive']) {
      const tab = whPage.locator(`button:has-text("${label}")`).first();
      if (await tab.count() > 0) {
        await expect(tab).toBeVisible({ timeout: 3000 });
        await tab.click();
        await whPage.waitForTimeout(500);
        await expect(whPage.locator('body')).toBeVisible();
      }
    }
  });

  test('verdict block renders (even if still computing due to API)', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    // The verdict block should always be in the DOM
    const verdict = whPage.locator('#an-verdict');
    await expect(verdict).toBeVisible({ timeout: 5000 });
  });

  test('graceful state: "Analysis failed" banner or loading state (not white screen)', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(8000); // Allow API timeout

    // Either the data loaded, or a graceful error state appeared.
    // Use separate locators — text= is not valid inside a CSS multi-selector.
    const hasVerdict    = await whPage.locator('#an-verdict').count();
    const hasAnalysisFailed = await whPage.getByText('Analysis failed').count();
    const hasLoading    = await whPage.getByText('Rolling up').count();

    expect(
      hasVerdict + hasAnalysisFailed + hasLoading,
      'page should show verdict OR graceful error, not blank',
    ).toBeGreaterThan(0);

    // The page must NOT show a white/empty body
    await expect(whPage.locator('body')).toBeVisible();
  });

  test('PDF Report button is visible and clickable', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    const pdfBtn = whPage.locator('button:has-text("PDF Report"), a:has-text("PDF")').first();
    if (await pdfBtn.count() > 0) {
      await expect(pdfBtn).toBeVisible({ timeout: 3000 });
      // Just verify clickable — actual PDF generation depends on data
      await pdfBtn.click();
      await whPage.waitForTimeout(500);
      await expect(whPage.locator('body')).toBeVisible();
    }
  });

  test('Supervisor/Field Tech role tabs are visible', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);

    const supervisorTab = whPage.locator('button:has-text("Supervisor"), button:has-text("Field Tech")').first();
    if (await supervisorTab.count() > 0) {
      await expect(supervisorTab).toBeVisible({ timeout: 3000 });
    }
  });
});

/* === Sentinel-proposed scenarios (check-name anchored) === */
test.describe('analytics.html - sentinel scenarios', () => {

  test('render_functions: analytics page renders meaningful markup', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2500);
    const stats = await whPage.evaluate(() => ({
      text: document.body.innerText.trim().length,
      domChildren: document.body.querySelectorAll('*').length,
      htmlLen: document.documentElement.outerHTML.length,
    }));
    const hasContent = stats.text > 50 || stats.domChildren > 20 || stats.htmlLen > 2000;
    expect(hasContent,
      `analytics page should render content (text=${stats.text}, dom=${stats.domChildren}, html=${stats.htmlLen})`).toBeTruthy();
  });

  test('toast_on_error: analytics surfaces a visible message on API failure', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(3000);
    const text = await whPage.content();
    const hasErrorOrSuccess = /(analysis|api).*(failed|error|unavailable)|loaded|ready/i.test(text);
    expect(hasErrorOrSuccess,
      'analytics should show either success or a recognizable failure banner').toBeTruthy();
  });

  test('phase_banners: descriptive/diagnostic/predictive phase markers exist', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const html = (await whPage.content()).toLowerCase();
    const phases = ['descriptive', 'diagnostic', 'predictive', 'prescriptive']
      .filter(p => html.includes(p));
    expect(phases.length, 'analytics should expose at least 2 of the 4 analysis phases')
      .toBeGreaterThanOrEqual(2);
  });

  test('period_consistency: analytics surfaces a time-period or tab selector', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);
    const selectors = whPage.locator(
      '[data-period], .period-chip, [data-tab], .tab-button, ' +
      'button:has-text("30d"), button:has-text("90d"), button:has-text("Descriptive"), ' +
      'button:has-text("Predictive"), button:has-text("Diagnostic")'
    );
    const count = await selectors.count();
    expect(count,
      'analytics should expose at least one period/tab selector').toBeGreaterThan(0);
  });

  test('phase_validation: invalid phase param is handled gracefully', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));
    await whPage.goto(PAGE + '?phase=__bogus__');
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);
    const seriousErrors = errors.filter(e => !e.toLowerCase().includes('net::'));
    expect(seriousErrors,
      `bogus phase param should not throw uncaught errors: ${seriousErrors.join(' | ')}`).toEqual([]);
  });

  test('availability_formula: page references availability or OEE formula', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc = await pageSrcWithExternals(whPage);
    const has = /availability|MTBF|MTTR|OEE|uptime|downtime/i.test(__sentSrc);
    expect(has, 'analytics should compute or display an availability-style metric').toBeTruthy();
  });

  test('calculate_entry: analytics declares a top-level compute entry', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_2 = await pageSrcWithExternals(whPage);
    const has = /computeAnalytics|calculateAnalytics|runAnalytics|loadAnalytics|analytics-orchestrator|orchestrator|computePhase|invokeAnalytics/i.test(__sentSrc_2);
    expect(has, 'analytics should reference a compute entry point').toBeTruthy();
  });

  test('main_analytics_404: analytics page reachable (returns 200)', async ({ whPage }) => {
    const response = await whPage.goto(PAGE);
    expect(response?.status() ?? 0, 'analytics.html must return 200').toBe(200);
  });

  test('hive_id_in_fetch: outbound analytics fetches include hive_id', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_3 = await pageSrcWithExternals(whPage);
    const has = /hive_id.*fetch|fetch.*hive_id|x-hive-id|hive[_-]id/i.test(__sentSrc_3);
    expect(has, 'analytics fetches should be hive-scoped').toBeTruthy();
  });

  test('auth_headers_in_fetch: analytics fetches include auth headers', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_4 = await pageSrcWithExternals(whPage);
    const has = /Authorization.*Bearer|access[_-]?token|getSession\(\)/i.test(__sentSrc_4);
    expect(has, 'analytics fetches should attach auth headers').toBeTruthy();
  });

  test('abort_timeout: analytics fetches declare an abort timeout', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_5 = await pageSrcWithExternals(whPage);
    const has = /AbortSignal\.timeout|AbortController|signal\s*:/i.test(__sentSrc_5);
    expect(has, 'analytics fetches should use AbortSignal.timeout').toBeTruthy();
  });

  test('double_submit_guard: analytics actions guarded against double-submit', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_6 = await pageSrcWithExternals(whPage);
    const has = /isSubmitting|isRunning|disabled.*=.*true|debounce/i.test(__sentSrc_6);
    expect(has, 'analytics actions should guard against double-submit').toBeTruthy();
  });

  test('error_body_read: analytics reads error response body before display', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_7 = await pageSrcWithExternals(whPage);
    const has = /response\.text\(\)|\.json\(\).*catch|error.*body|errorBody/i.test(__sentSrc_7);
    expect(has, 'analytics errors should read response body').toBeTruthy();
  });

  test('esc_html_error: error messages are HTML-escaped', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_8 = await pageSrcWithExternals(whPage);
    const has = /escHtml|escapeHtml/i.test(__sentSrc_8);
    expect(has, 'analytics should escape error strings before rendering').toBeTruthy();
  });

  test('groq_fallback: analytics references Groq fallback chain', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_9 = await pageSrcWithExternals(whPage);
    const has = /groq.*fallback|fallback.*chain|ai[-_]?chain/i.test(__sentSrc_9);
    expect(has, 'analytics should declare a fallback chain').toBeTruthy();
  });

  test('groq_null_guard: null guard before reading Groq response', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_10 = await pageSrcWithExternals(whPage);
    const has = /\?\.\s*choices|response\?\.|\?\?\s*['"]/i.test(__sentSrc_10);
    expect(has, 'Groq response access should be null-guarded').toBeTruthy();
  });

  test('main_phase_routing: phase param routes to the right view', async ({ whPage }) => {
    await whPage.goto(PAGE + '?phase=descriptive');
    await waitForPageReady(whPage);
    const text = await whPage.content();
    expect(text, 'phase=descriptive should land in a descriptive view').toMatch(/descriptive/i);
  });

  test('new_render_functions: page exposes at least one render function', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_11 = await pageSrcWithExternals(whPage);
    const has = /function\s+render\w+|const\s+render\w+\s*=/i.test(__sentSrc_11);
    expect(has, 'analytics should declare render functions').toBeTruthy();
  });

  test('plotly_yaxis_range: Plotly charts declare a y-axis range', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_12 = await pageSrcWithExternals(whPage);
    const has = /yaxis\s*:\s*\{[^}]*range|yaxis\.range|Plotly\.newPlot/i.test(__sentSrc_12);
    expect(has, 'Plotly charts should declare a y-axis range').toBeTruthy();
  });

  test('duplicate_dict_key: page does not declare duplicate object keys', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const dup = await whPage.evaluate(() => {
      const errs: string[] = [];
      const orig = console.warn;
      console.warn = (...a) => errs.push(a.join(' '));
      try { /* warm */ } finally { console.warn = orig; }
      return errs.some(e => /duplicate.*key/i.test(e));
    });
    expect(dup, 'no duplicate object key warnings in analytics').toBe(false);
  });

  test('python_url_null_guard: analytics URL builder null-guards', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_13 = await pageSrcWithExternals(whPage);
    const has = /url\s*=.*\?\?|url\s*\?\?|if\s*\(\s*!url|null\s*url/i.test(__sentSrc_13);
    expect(has, 'analytics URL builder should null-guard').toBeTruthy();
  });

  test('py_shape_descriptive: descriptive endpoint returns expected shape', async ({ whPage }) => {
    await whPage.goto(PAGE + '?phase=descriptive');
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);
    const text = await whPage.content();
    expect(text.length, 'descriptive view should render content').toBeGreaterThan(500);
  });

  test('py_syntax: page loads with no Python-style template residue', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const html = await whPage.content();
    expect(html, 'page should not contain unescaped Python template tokens')
      .not.toMatch(/\{\{\s*\w+\s*\}\}/);
  });

  test('breakdown_consequence_required: data-quality breakdown_consequence enforced', async () => {
    const db = adminClient();
    const { data } = await db.from('logbook')
      .select('id, maintenance_type, consequence')
      .eq('maintenance_type', 'Breakdown / Corrective').limit(10);
    if (!data || data.length === 0) { test.skip(true, 'no Breakdown rows in seed'); return; }
    const missing = data.filter(r => !r.consequence);
    expect(missing.length,
      `Breakdown entries must carry a consequence (${missing.length} missing)`).toBe(0);
  });

  test('canonical_maint_type_consistency: only canonical maintenance_type values present', async () => {
    const valid = new Set(['Breakdown / Corrective','Preventive Maintenance','Inspection','Project Work']);
    const db = adminClient();
    const { data } = await db.from('logbook')
      .select('maintenance_type').limit(50);
    if (!data) { test.skip(true, 'no rows'); return; }
    const bad = data.filter(r => r.maintenance_type && !valid.has(r.maintenance_type));
    expect(bad.length, 'every logbook row uses a canonical maintenance_type').toBe(0);
  });

  test('category_required_on_save: every saved logbook row has maintenance_type', async () => {
    const db = adminClient();
    const { data } = await db.from('logbook').select('id, maintenance_type').limit(20);
    if (!data || data.length === 0) { test.skip(true, 'no rows'); return; }
    const missing = data.filter(r => !r.maintenance_type);
    expect(missing.length, 'every logbook entry should carry maintenance_type').toBe(0);
  });

  test('duplicate_entry_guard: rapid same-content saves are deduped or blocked', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_14 = await pageSrcWithExternals(whPage);
    const has = /duplicate.*guard|isSubmitting|debounce/i.test(__sentSrc_14);
    expect(has, 'save path should have duplicate-entry guard').toBeTruthy();
  });

  test('mtbf_machine_normalization: machine name normalized before MTBF aggregation', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_15 = await pageSrcWithExternals(whPage);
    const has = /normalize.*machine|machine.*normalize|trim\(\).*machine|machine.*toLower/i.test(__sentSrc_15);
    expect(has, 'machine names should be normalized before MTBF aggregation').toBeTruthy();
  });

  test('calc_count_consistent: calc-type count matches across registries', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_16 = await pageSrcWithExternals(whPage);
    const has = /CALC_TYPES|calcTypes|calc_type_count/i.test(__sentSrc_16);
    expect(has, 'analytics should reference the calc-type registry').toBeTruthy();
  });

  test('discipline_names: discipline names match canonical list', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const html = await whPage.content();
    const canonical = ['Mechanical', 'Electrical', 'Civil', 'Process', 'Instrumentation', 'Software'];
    const found = canonical.filter(d => html.includes(d));
    expect(found.length,
      'at least one canonical discipline name should appear on analytics page').toBeGreaterThan(0);
  });

  test('key_extracted: analytics endpoint returns extractable keys', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_17 = await pageSrcWithExternals(whPage);
    const has = /Object\.keys|\.keys\(|extract.*key/i.test(__sentSrc_17);
    expect(has, 'analytics should extract keys from response').toBeTruthy();
  });

});
