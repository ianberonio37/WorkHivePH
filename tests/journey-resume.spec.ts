/**
 * resume.html — Resume / CV Builder journey.
 *
 * Drives the REAL client paths a user touches, so an interaction that silently
 * does nothing is caught here instead of by the user. The edge function is
 * STUBBED (page.route) so these tests are deterministic and need no LLM:
 * we are testing the page's behaviour, not the model.
 *
 * Regression guard: "picking files did nothing" (the FileList-reset bug, where
 * clearing input.value emptied the live FileList before handleFiles read it).
 * The upload test asserts that selecting a file OPENS the review sheet and the
 * confirmed items MERGE into the resume — both fail if the change handler no-ops.
 */
import { test, expect } from './_fixtures';
import type { Page } from '@playwright/test';

// 1x1 PNG — a real, decodable image so compressImage() (Image + canvas) succeeds.
const PNG_1x1 = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
  'base64',
);

// What the stubbed resume-extract returns (JSON Resume partial).
const EXTRACT_FIXTURE = {
  fields: {
    basics: { name: '', label: '', email: '', phone: '', summary: '', location: { city: '', region: '' } },
    work: [], education: [],
    skills: [{ name: 'arc welding', level: '' }, { name: 'centrifugal pumps', level: '' }],
    certificates: [{ name: 'TESDA NC II Mechanical', issuer: 'TESDA', date: '2024' }],
    projects: [], awards: [],
  },
};

async function stubExtract(page: Page) {
  await page.route('**/functions/v1/resume-extract', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(EXTRACT_FIXTURE) }));
}

async function gotoResume(page: Page) {
  await page.goto('/workhive/resume.html', { waitUntil: 'domcontentloaded' });
  await expect(page, 'should not bounce to sign-in').toHaveURL(/resume\.html/);
  // Wait until the page's init has rendered the section editors.
  await page.waitForSelector('#upload-card', { timeout: 10000 });
  await page.waitForSelector('[data-action="add"][data-sec="skills"]', { timeout: 10000 });
}

test.describe('resume.html — Resume / CV Builder journey', () => {
  test('loads in the real UI without bouncing to sign-in', async ({ whPage }) => {
    await gotoResume(whPage);
    await expect(whPage.locator('#btn-autofill')).toBeVisible();
    await expect(whPage.locator('#btn-file')).toBeVisible();
    await expect(whPage.locator('#btn-export')).toBeVisible();
  });

  test('upload a file -> AI extract -> editable checklist -> merge (guards the FileList regression)', async ({ whPage }) => {
    await stubExtract(whPage);
    await gotoResume(whPage);

    // Selecting a file MUST open the review sheet. With the FileList-reset bug,
    // handleFiles never ran and this sheet never opened.
    await whPage.setInputFiles('#file-any', { name: 'cert.png', mimeType: 'image/png', buffer: PNG_1x1 });
    await expect(whPage.locator('#review-sheet'), 'review sheet must open after a file is picked')
      .toHaveClass(/open/, { timeout: 15000 });
    // Extracted values live in editable <input value="..."> rows, not text nodes.
    await expect(whPage.locator('#review-body input[value="arc welding"]')).toHaveCount(1);
    await expect(whPage.locator('#review-body input[value="TESDA NC II Mechanical"]')).toHaveCount(1);

    // Confirm -> items merge into the resume sections.
    await whPage.click('#review-confirm');
    await expect(whPage.locator('#review-sheet')).not.toHaveClass(/open/);
    await expect(whPage.locator('#sections input[value="arc welding"]')).toHaveCount(1);
    await expect(whPage.locator('#sections input[value="TESDA NC II Mechanical"]')).toHaveCount(1);
  });

  test('dump MULTIPLE files -> one combined checklist tagged by filename', async ({ whPage }) => {
    await stubExtract(whPage);
    await gotoResume(whPage);

    await whPage.setInputFiles('#file-any', [
      { name: 'cv1.png', mimeType: 'image/png', buffer: PNG_1x1 },
      { name: 'cv2.png', mimeType: 'image/png', buffer: PNG_1x1 },
    ]);
    await expect(whPage.locator('#review-sheet')).toHaveClass(/open/, { timeout: 20000 });
    await expect(whPage.locator('#review-title')).toContainText('from 2 files');
    await expect(whPage.locator('#review-body')).toContainText('cv1.png');
  });

  test('manual add: "+ Add skill" inserts an editable row', async ({ whPage }) => {
    await gotoResume(whPage);
    const sel = '[data-sec="skills"][data-field="name"]';
    const before = await whPage.locator(sel).count();
    await whPage.click('[data-action="add"][data-sec="skills"]');
    await expect(whPage.locator(sel)).toHaveCount(before + 1);
  });

  test('export preview opens, renders the resume, and the template toggle works', async ({ whPage }) => {
    await gotoResume(whPage);
    await whPage.fill('[data-basics="name"]', 'Pablo Aguilar');
    await whPage.click('#btn-export');
    await expect(whPage.locator('#preview-overlay')).toHaveClass(/open/);
    await expect(whPage.locator('#resume-paper')).toContainText('Pablo Aguilar');
    await whPage.click('.pv-tpl[data-tpl="workhive"]');
    await expect(whPage.locator('#resume-paper.tpl-workhive')).toHaveCount(1);
  });
});
