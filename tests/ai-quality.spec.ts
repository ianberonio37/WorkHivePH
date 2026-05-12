/**
 * ai-quality.html — UI smoke.
 * Phase 4.1 of STRATEGIC_ROADMAP. AI Quality + ROI dashboard.
 * Below Stair 2, the page renders the maturity-honest empty state and
 * NOT the cards — the smoke template covers both branches by asserting
 * no page errors and the source chip when present.
 */
import { test, expect } from './_fixtures';
import { smokePage } from './_smoke-template';

test.describe('ai-quality.html smoke', () => {
  test('loads and renders without page errors', async ({ whPage }) => {
    await smokePage(whPage, '/workhive/ai-quality.html', { expectSourceChip: true });
  });
});
