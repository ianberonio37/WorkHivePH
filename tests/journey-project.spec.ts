/**
 * Tier 5a — Project Manager flows (3 scenarios, P1)
 *
 * Project lifecycle: create → progress → executive report.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';
import { readFileSync } from 'fs';
import { resolve } from 'path';

const ROOT = resolve(__dirname, '..');

test.describe('Tier 5a — Project Manager flows', () => {

  test('E1_create_project_link_hive_insert_paths: project-manager writes projects + project_links', async () => {
    // WHY: projects + project_links are the multi-tenant project model
    const html = readFileSync(resolve(ROOT, 'project-manager.html'), 'utf-8');
    expect(html, 'must insert into projects table').toMatch(/from\s*\(\s*['"]projects['"]\s*\)\.insert\s*\(/);
    expect(html, 'must insert into project_links').toMatch(/from\s*\(\s*['"]project_links['"]\s*\)\.insert\s*\(/);
  });

  test('E2_executive_project_report_structure: project-report has summary + sections + PDF download', async () => {
    // WHY: project-report.html is the executive deliverable; section structure must be present
    const html = readFileSync(resolve(ROOT, 'project-report.html'), 'utf-8');
    expect(html, 'must include exec summary section').toMatch(/exec-summary|executive[- ]summary/i);
    // Canonical sections: scope/timeline/risks/budget. Need at least 2 of these.
    const sections = ['scope', 'timeline', 'risks', 'budget', 'milestone'];
    const found = sections.filter((s) => new RegExp(`\\b${s}\\b`, 'i').test(html));
    expect(found.length, `must include >=2 of {scope,timeline,risks,budget,milestone}; found: ${found.join(', ')}`).toBeGreaterThanOrEqual(2);
    // PDF download path.
    expect(html, 'must offer PDF download').toMatch(/html2pdf|printReport|window\.print|download.*pdf/i);
  });

  test('E3_project_progress_invokes_edge_fn: project-manager invokes project-progress edge fn', async () => {
    // WHY: canonical write path for project status updates
    const html = readFileSync(resolve(ROOT, 'project-manager.html'), 'utf-8');
    // Either invokes the edge fn OR writes to projects table directly (both are valid patterns).
    const usesEdgeFn = /invoke\s*\(\s*['"]project-progress['"]/.test(html);
    const usesDirectWrite = /from\s*\(\s*['"]projects['"]\s*\)[\s\S]{0,300}\.update\s*\(/.test(html);
    expect(usesEdgeFn || usesDirectWrite, 'must call project-progress edge fn OR update projects table directly').toBeTruthy();
  });
});
