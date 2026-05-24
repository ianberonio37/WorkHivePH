/**
 * journey-agentic.spec.ts — Agentic RAG Observability page journey.
 *
 * Sentinel-anchor scenarios for validate_agentic_rag_observability.py checks:
 *   - file_exists
 *   - utils_loaded
 *   - render_blocks
 *   - bounded_fetch
 *
 * Target: agentic-rag-observability.html
 */
import { test, expect } from './_fixtures';
import { waitForPageReady, pageSrcWithExternals } from './_helpers';

const PAGE = '/workhive/agentic-rag-observability.html';

test.describe('agentic-rag-observability.html — observability dashboard journey', () => {

  test('file_exists: page loads with expected title and body shell', async ({ whPage }) => {
    const resp = await whPage.goto(PAGE);
    expect(resp?.status(), 'HTTP 200 expected').toBeLessThan(400);
    await waitForPageReady(whPage);
    const title = await whPage.title();
    expect(title, 'title should include Agentic RAG').toMatch(/Agentic RAG/i);
    const body = whPage.locator('#page-body');
    await expect(body).toBeAttached({ timeout: 5000 });
  });

  test('utils_loaded: utils.js loads so escHtml + debounce are available', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const hasUtils = await whPage.evaluate(() => {
      return typeof (window as any).escHtml === 'function';
    });
    expect(hasUtils, 'window.escHtml must be defined (utils.js loaded)').toBe(true);
  });

  test('render_blocks: summary cards + route table + recent traces table all mount', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);
    await expect(whPage.locator('#summary-cards')).toBeAttached({ timeout: 5000 });
    await expect(whPage.locator('#route-tbl')).toBeAttached({ timeout: 5000 });
    const moreTables = whPage.locator('table.tbl');
    const tableCount = await moreTables.count();
    expect(tableCount, 'at least one render block table present').toBeGreaterThanOrEqual(1);
  });

  test('bounded_fetch: trace query carries a .limit(N) clause in source', async ({ whPage }) => {
    const src = await pageSrcWithExternals(whPage, PAGE);
    expect(src, 'agentic_rag_traces query must be bounded').toMatch(/\.limit\(\s*\d+\s*\)/);
    expect(src, 'agentic_rag_traces must be referenced').toContain('agentic_rag_traces');
  });
});
