/**
 * resume.html — UI smoke.
 * Resume / CV Builder: auto-fill from WorkHive data (Skill Matrix + Logbook +
 * badges), phone upload + AI extract, AI polish/tailor, and PDF / Print /
 * JSON Resume export. Mirrors the tools/gen_smoke_specs.py pattern.
 * Add page-specific form/flow tests in a separate describe block if needed.
 */
import { test, expect } from './_fixtures';
import { smokePage } from './_smoke-template';

test.describe('resume.html smoke', () => {
  test('loads and renders without page errors', async ({ whPage }) => {
    await smokePage(whPage, '/workhive/resume.html', {});
  });
});
