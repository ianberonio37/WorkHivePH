/**
 * Tier 4 — Engineer flows (6 scenarios, P1)
 *
 * Engineering Calc Suite (BOM/SOW), PDF reports, skill matrix,
 * predictive analytics, drawing builder, cross-page calc reuse.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';
import { readFileSync } from 'fs';
import { resolve } from 'path';

const ROOT = resolve(__dirname, '..');

test.describe('Tier 4 — Engineer flows', () => {

  test('D1_engineering_calc_invokes_agent: engineering-design invokes engineering-calc-agent edge fn', async () => {
    // WHY: engineering-calc-agent is the canonical calc orchestrator
    const html = readFileSync(resolve(ROOT, 'engineering-design.html'), 'utf-8');
    expect(html, 'engineering-design must invoke engineering-calc-agent edge fn')
      .toMatch(/invoke\s*\(\s*['"]engineering-calc-agent['"]/);
  });

  test('D2_pdf_pagebreak_applied_to_report_blocks: report panel uses page-break-inside:avoid', async () => {
    // WHY: PDF rendering must avoid splitting tables / result cards across pages
    // STATIC: inline styles or CSS rules apply page-break-inside:avoid to the canonical report blocks
    const html = readFileSync(resolve(ROOT, 'engineering-design.html'), 'utf-8');
    // The report uses a #print-wrapper / #report-panel render container.
    expect(html, 'must declare #report-panel container').toMatch(/#report-panel/);
    // Multiple page-break-inside guards across tables, result-highlight cards
    const breakCount = (html.match(/page-break-inside\s*:\s*avoid/g) || []).length;
    expect(breakCount, `at least 5 page-break guards expected, found ${breakCount}`).toBeGreaterThanOrEqual(5);
    // Result-highlight cards (the headline numbers) get explicit page-break protection.
    expect(html, 'result-highlight cards must protect against page splits').toMatch(
      /result-highlight[\s\S]{0,200}page-break-inside\s*:\s*avoid/
    );
    // @media print rule + print-wrapper system must exist.
    expect(html, 'must have @media print rules').toMatch(/@media\s+print/);
    expect(html, 'must declare #print-wrapper').toMatch(/#print-wrapper/);
  });

  test('D3_skillmatrix_reads_skill_badges: skillmatrix.html computes from skill_badges', async () => {
    // WHY: skill_badges is the canonical proof-of-competency table; level = highest consecutive badge
    const html = readFileSync(resolve(ROOT, 'skillmatrix.html'), 'utf-8');
    expect(html, 'skillmatrix must query skill_badges').toMatch(
      /from\s*\(\s*['"]skill_badges['"]\s*\)/
    );
    // Disciplines × levels grid: must reference both discipline + level
    expect(html, 'must select discipline + level').toMatch(/discipline\s*,\s*level/);
    // 5 levels × 6 disciplines = 30 cap exposed somewhere in copy or computation
    expect(html, 'must reference 30 max badges (5 × 6)').toMatch(/\b30\b/);
  });

  test('D4_predictive_consumes_v_risk_truth: predictive.html surfaces MTBF from v_risk_truth', async () => {
    // WHY: v_risk_truth is the canonical risk view; Predictive uses 365-day annual decay window
    const html = readFileSync(resolve(ROOT, 'predictive.html'), 'utf-8');
    expect(html, 'predictive must read v_risk_truth').toMatch(
      /from\s*\(\s*['"]v_risk_truth['"]\s*\)/
    );
    // MTBF column header + mtbf_days field must both appear (UI + canonical column)
    expect(html, 'must display MTBF column').toMatch(/>MTBF</);
    expect(html, 'must read mtbf_days from view').toMatch(/mtbf_days/);
  });

  test('D5_diagram_builder_3step_atomic: DRAWING_SUPPORTED + showReport + _runDrawing all present', async () => {
    // WHY: qa-tester skill 3-step atomic rule: every new buildXxxSVG needs all 3 wiring points
    const html = readFileSync(resolve(ROOT, 'engineering-design.html'), 'utf-8');
    expect(html, 'DRAWING_SUPPORTED registry must exist').toMatch(/DRAWING_SUPPORTED\s*=/);
    expect(html, 'showReport function must exist (button tooltip path)').toMatch(/function\s+showReport\s*\(/);
    expect(html, '_runDrawing function must exist (click handler)').toMatch(/function\s+_runDrawing\s*\(/);
  });

  test.fixme('D6_calc_reuse_from_logbook: logbook → calc deep-link prefills inputs', async ({ whPage }) => {
    // WHY: cross-page handoff; logbook anchor passes calc_id; calc page prefills + computes
    // ACT: logbook.html → entry with attached calc → "Open Calc" link
    // ASSERT: engineering-design.html opens with same inputs, results auto-recompute
    await whPage.goto('/workhive/logbook.html');
    await waitForPageReady(whPage);
  });
});
