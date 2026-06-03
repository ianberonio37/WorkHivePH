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
    work: [{ position: 'Maintenance Supervisor', name: 'Universal Robina', location: '', startDate: '2021', endDate: '2024', highlights: ['Operated staple manufacturing machines safely and efficiently', 'Loaded raw materials into machines'] }],
    education: [],
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

  test('dumping the same content twice does NOT duplicate jobs/skills (grounded dedupe)', async ({ whPage }) => {
    await stubExtract(whPage);
    await gotoResume(whPage);
    // Two files carrying the SAME job + skills + cert (the real "Mechanical
    // Engineer x2" failure). After merge they must collapse to one of each.
    await whPage.setInputFiles('#file-any', [
      { name: 'resume-a.png', mimeType: 'image/png', buffer: PNG_1x1 },
      { name: 'resume-b.png', mimeType: 'image/png', buffer: PNG_1x1 },
    ]);
    await expect(whPage.locator('#review-sheet')).toHaveClass(/open/, { timeout: 20000 });
    // The combined checklist is deduped ACROSS files: 4 unique rows (1 work + 2 skills
    // + 1 cert), not 8 - so the user never sees the same item twice in one dump.
    await expect(whPage.locator('#review-body .check-row')).toHaveCount(4);
    await whPage.click('#review-confirm');
    await expect(whPage.locator('#review-sheet')).not.toHaveClass(/open/);
    await expect(whPage.locator('#sections [data-sec="work"][data-field="position"]')).toHaveCount(1);
    await expect(whPage.locator('#sections [data-sec="skills"][data-field="name"]')).toHaveCount(2);
    await expect(whPage.locator('#sections [data-sec="certificates"][data-field="name"]')).toHaveCount(1);
  });

  test('auto-fill collapses skill badges to ONE certificate per discipline (no Level 1..N spam)', async ({ whPage }) => {
    // Live auto-fill from the seeded worker's badges (no stub - this guards the
    // real "22 Level-N certificates" explosion the MCP walkthrough surfaced).
    await gotoResume(whPage);
    await whPage.click('#btn-autofill');
    await expect(whPage.locator('#review-sheet')).toHaveClass(/open/, { timeout: 20000 });
    const disciplines = await whPage.evaluate(() => {
      const body = document.getElementById('review-body'); if (!body) return [];
      let cur = ''; const out = [];
      [...body.children].forEach((el) => {
        if (el.classList.contains('sheet-group-title')) cur = el.textContent.trim();
        else if (el.classList.contains('check-row') && cur === 'Certificates') {
          const v = el.querySelector('input[data-review-value]');
          out.push((v ? v.value : '').split(' - ')[0].trim().toLowerCase());
        }
      });
      return out;
    });
    // Each discipline must appear at most once (collapsed to the highest level).
    expect(disciplines.length, 'no duplicate discipline in certificates').toBe(new Set(disciplines).size);
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

  test('AI polish surfaces ONLY the bullets it actually changed (no no-op rows)', async ({ whPage }) => {
    await stubExtract(whPage);
    await gotoResume(whPage);
    // Merge a job carrying two highlights.
    await whPage.setInputFiles('#file-any', { name: 'cv.png', mimeType: 'image/png', buffer: PNG_1x1 });
    await expect(whPage.locator('#review-sheet')).toHaveClass(/open/, { timeout: 15000 });
    await whPage.click('#review-confirm');
    await expect(whPage.locator('#review-sheet')).not.toHaveClass(/open/);

    // Polish returns the FIRST bullet unchanged and the SECOND improved.
    await whPage.route('**/functions/v1/resume-polish', (route) => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ bullets: [
        'Operated staple manufacturing machines safely and efficiently',
        'Loaded and staged raw materials to keep production running without interruption',
      ] }),
    }));
    await whPage.click('#btn-polish');
    await expect(whPage.locator('#review-sheet')).toHaveClass(/open/, { timeout: 15000 });
    // Only the changed bullet is offered; the identical one is filtered out.
    await expect(whPage.locator('#review-body .check-row')).toHaveCount(1);
    // The polished value is in an editable <input>, so assert with toHaveValue, not toContainText.
    await expect(whPage.locator('#review-body input[data-review-value]'))
      .toHaveValue('Loaded and staged raw materials to keep production running without interruption');
  });

  test('work experience shows the quantified-bullet hint (coaches toward competitive bullets)', async ({ whPage }) => {
    await gotoResume(whPage);
    await whPage.click('[data-action="add"][data-sec="work"]');
    const hint = whPage.locator('.field-hint');
    await expect(hint).toHaveCount(1);
    await expect(hint).toContainText('add a number');
  });

  test('export renders Education BEFORE Certificates (standard order)', async ({ whPage }) => {
    await whPage.route('**/functions/v1/resume-extract', (route) => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ fields: {
        basics: { name: '', label: '', email: '', phone: '', summary: '', location: { city: '', region: '' } },
        work: [], skills: [],
        education: [{ institution: 'University of Cebu', studyType: 'BS Mechanical Engineering', area: '', startDate: '2008', endDate: '2013' }],
        certificates: [{ name: 'Registered Mechanical Engineer (PRC)', issuer: 'PRC', date: '2014' }],
        projects: [], awards: [],
      } }),
    }));
    await gotoResume(whPage);
    await whPage.setInputFiles('#file-any', { name: 'cv.png', mimeType: 'image/png', buffer: PNG_1x1 });
    await expect(whPage.locator('#review-sheet')).toHaveClass(/open/, { timeout: 15000 });
    await whPage.click('#review-confirm');
    await whPage.click('#btn-export');
    await expect(whPage.locator('#preview-overlay')).toHaveClass(/open/);
    const titles = await whPage.locator('#resume-paper .r-sec-title').allInnerTexts();
    const ed = titles.findIndex((t) => /education/i.test(t));
    const ce = titles.findIndex((t) => /certificates/i.test(t));
    expect(ed, 'Education present').toBeGreaterThanOrEqual(0);
    expect(ce, 'Certificates after Education').toBeGreaterThan(ed);
  });
});
