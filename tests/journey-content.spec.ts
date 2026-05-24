/**
 * journey-content.spec.ts — Content quality + Python column safety sentinel anchor.
 *
 * Target: hive.html (and embed/python paths it loads)
 * Validator: validate_content_quality.py — check `python_column_safety`
 *
 * The Python column safety check verifies that downstream Python tooling
 * references columns that actually exist in the relevant views (e.g.
 * v_logbook_truth, fault_knowledge). This Layer-2 anchor verifies that
 * hive.html surfaces a Knowledge / Fault Knowledge / Embeds section so
 * the column contract has a UI consumer that would fail loudly if columns
 * disappeared.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady, pageSrcWithExternals } from './_helpers';

const PAGE = '/workhive/hive.html';

test.describe('hive.html — content quality anchor', () => {

  test('python_column_safety: hive surfaces fault-knowledge / embed columns the Python path expects', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);
    const src = await pageSrcWithExternals(whPage, PAGE);
    expect(
      src.toLowerCase(),
      'hive should reference at least one fault-knowledge / embed surface column'
    ).toMatch(/fault_knowledge|failure_consequence|mtbf|mttr|root_cause|knowledge_chunks/);
  });

});
