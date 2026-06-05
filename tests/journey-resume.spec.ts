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

  test('summary reduce-pass: writes the professional summary from the WHOLE resume (facts in, prose out) (2026-06-05)', async ({ whPage }) => {
    // Seed a resume with a dated job carrying a QUANTIFIED bullet, two skills, and a
    // cert, so buildResumeFacts has real material (years, role, top skills, a numbered
    // achievement) to compute. The model is stubbed: we test the page's fact sheet, not the LLM.
    await whPage.route('**/functions/v1/resume-extract', (route) => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ fields: {
        basics: { name: 'Maricel Santos', label: 'Reliability Engineer', email: '', phone: '', summary: '', location: { city: 'Cebu City', region: 'Cebu' } },
        work: [{ position: 'Reliability Engineer', name: 'ZenithFoods', location: '', startDate: '2016', endDate: 'Present',
          highlights: ['Spearheaded a vibration-monitoring program across 40 assets that cut bearing failures by 35%'] }],
        education: [], skills: [{ name: 'PLC', level: '' }, { name: 'vibration analysis', level: '' }],
        certificates: [{ name: 'TESDA NC II Electrical', issuer: 'TESDA', date: '2011' }], projects: [], awards: [],
      } }),
    }));
    await gotoResume(whPage);
    await whPage.setInputFiles('#file-any', { name: 'cv.png', mimeType: 'image/png', buffer: PNG_1x1 });
    await expect(whPage.locator('#review-sheet')).toHaveClass(/open/, { timeout: 15000 });
    await whPage.click('#review-confirm');
    await expect(whPage.locator('#review-sheet')).not.toHaveClass(/open/);

    // Capture the request to PROVE the client computed and sent the whole-resume FACT
    // SHEET (roles + achievements + top_skills + years) - the thing that distinguishes
    // this synthesis from the old tailor path that only sent summary + skills.
    let sentFacts: Record<string, unknown> | null = null;
    await whPage.route('**/functions/v1/resume-polish', (route) => {
      try { const b = route.request().postDataJSON() || {}; sentFacts = b.mode === 'synthesize_summary' ? b.facts : null; } catch (_) { /* ignore */ }
      route.fulfill({ status: 200, contentType: 'application/json',
        body: JSON.stringify({ summary: 'Reliability engineer with 10 years in food and beverage plants, skilled in PLC and vibration analysis, who spearheaded a program that cut bearing failures by 35%.' }) });
    });

    await whPage.click('#btn-summary');
    // Internal control: even a single AI summary flows through the review checklist.
    await expect(whPage.locator('#review-sheet')).toHaveClass(/open/, { timeout: 15000 });
    await whPage.click('#review-confirm');
    await expect(whPage.locator('#review-sheet')).not.toHaveClass(/open/);

    // It lands in the Professional summary editor.
    await expect(whPage.locator('textarea[data-basics="summary"]')).toHaveValue(/cut bearing failures by 35%/);

    // The whole-resume contract: roles, the quantified achievement, top skills, and a
    // deterministically computed years figure were all in the fact sheet.
    expect(sentFacts, 'client sent a synthesize_summary fact sheet').toBeTruthy();
    const f = sentFacts as Record<string, unknown>;
    expect((f.roles as string[]).some((r) => /Reliability Engineer/i.test(r)), 'roles in facts').toBeTruthy();
    expect((f.achievements as string[]).some((a) => /35%/.test(a)), 'quantified achievement in facts').toBeTruthy();
    expect((f.top_skills as string[]).includes('PLC'), 'top skills in facts').toBeTruthy();
    expect(String(f.years || ''), 'computed years present').toMatch(/year/);
  });

  test('summary fact sheet: a same-year-only role claims NO tenure; a cross-year span yields the year count (years-precision fix, live MCP 2026-06-05)', async ({ whPage }) => {
    // The live sweep caught this: an auto-filled "solo practice" role dated 2026-Present
    // (= when the worker joined WorkHive, NOT their career start) made _resumeYears
    // return "less than a year", so the summary called a worker with 300 logged jobs and
    // L5 badges "early-career". With YEAR-only precision a same-year span carries no real
    // tenure -> facts.years must be '' and the summary leads with scope, not a false tenure.
    await whPage.route('**/functions/v1/resume-extract', (route) => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ fields: {
        basics: { name: 'Solo Worker', label: 'Maintenance Technician', email: '', phone: '', summary: '', location: { city: '', region: '' } },
        work: [{ position: 'Maintenance Technician', name: 'Independent', location: '', startDate: '2019', endDate: '2019',
          highlights: ['Logged 300 maintenance records across 30 equipment items'] }],
        education: [], skills: [{ name: 'Instrumentation', level: '' }], certificates: [], projects: [], awards: [],
      } }),
    }));
    await gotoResume(whPage);
    await whPage.setInputFiles('#file-any', { name: 'cv.png', mimeType: 'image/png', buffer: PNG_1x1 });
    await expect(whPage.locator('#review-sheet')).toHaveClass(/open/, { timeout: 15000 });
    await whPage.click('#review-confirm');
    await expect(whPage.locator('#review-sheet')).not.toHaveClass(/open/);

    let sentFacts: Record<string, unknown> | null = null;
    await whPage.route('**/functions/v1/resume-polish', (route) => {
      try { const b = route.request().postDataJSON() || {}; if (b.mode === 'synthesize_summary') sentFacts = b.facts; } catch (_) { /* ignore */ }
      route.fulfill({ status: 200, contentType: 'application/json',
        body: JSON.stringify({ summary: 'Maintenance technician across instrumentation systems, with 300 logged maintenance records across 30 equipment items.' }) });
    });

    // Same-year-only span -> the fact sheet asserts NO tenure.
    await whPage.click('#btn-summary');
    await expect(whPage.locator('#review-sheet')).toHaveClass(/open/, { timeout: 15000 });
    expect(sentFacts, 'fact sheet sent').toBeTruthy();
    expect((sentFacts as Record<string, unknown>).years, 'no tenure from a same-year-only span').toBe('');
    await whPage.click('#review-confirm');
    await expect(whPage.locator('#review-sheet')).not.toHaveClass(/open/);

    // Add a genuine cross-year role (2010-2020) -> a real 10-year span IS asserted.
    await whPage.click('[data-action="add"][data-sec="work"]');
    await whPage.locator('[data-sec="work"][data-field="position"]').last().fill('Maintenance Supervisor');
    await whPage.locator('[data-sec="work"][data-field="name"]').last().fill('Universal Robina');
    await whPage.locator('[data-sec="work"][data-field="startDate"]').last().fill('2010');
    await whPage.locator('[data-sec="work"][data-field="endDate"]').last().fill('2020');

    sentFacts = null;
    await whPage.click('#btn-summary');
    await expect(whPage.locator('#review-sheet')).toHaveClass(/open/, { timeout: 15000 });
    expect((sentFacts as Record<string, unknown>).years, 'a real cross-year span yields the year count').toBe('10 years');
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

  test('extraction surfaces PROJECTS and AWARDS in the checklist and renders them (recall fix 2026-06-04)', async ({ whPage }) => {
    // Stub mirrors the live extractor AFTER the recall fix: a project and an
    // award that were EMBEDDED in job bullets are now returned (this was the
    // "less analysis / projects + achievements dropped" gap the user reported).
    // Guards the whole path: extract -> checklist group -> merge -> render,
    // not merely that the model returns them.
    await whPage.route('**/functions/v1/resume-extract', (route) => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ fields: {
        basics: { name: 'Pedro Santos', label: '', email: '', phone: '', summary: '', location: { city: '', region: '' } },
        work: [{ position: 'Maintenance Supervisor', name: 'San Miguel Brewery', location: 'Cebu', startDate: '2018', endDate: '2024', highlights: ['Supervised 12 technicians across 3 shifts'] }],
        education: [], skills: [], certificates: [],
        projects: [
          { name: 'Downtime-Reduction Initiative', description: 'Cut line stoppages by 25% over 18 months' },
          { name: 'CMMS Rollout', description: 'Rolled out a CMMS across the plant' },
        ],
        awards: [{ title: 'Employee of the Year 2021', awarder: 'San Miguel Brewery', date: '2021' }],
      } }),
    }));
    await gotoResume(whPage);
    await whPage.setInputFiles('#file-any', { name: 'cv.png', mimeType: 'image/png', buffer: PNG_1x1 });
    await expect(whPage.locator('#review-sheet')).toHaveClass(/open/, { timeout: 15000 });
    // The checklist must offer Projects AND Awards groups (the dropped sections).
    const groups = await whPage.locator('#review-body .sheet-group-title').allInnerTexts();
    expect(groups.some((g) => /projects/i.test(g)), 'Projects group present in checklist').toBeTruthy();
    expect(groups.some((g) => /awards/i.test(g)), 'Awards group present in checklist').toBeTruthy();
    await expect(whPage.locator('#review-body input[value="Downtime-Reduction Initiative"]')).toHaveCount(1);
    await expect(whPage.locator('#review-body input[value="Employee of the Year 2021"]')).toHaveCount(1);
    // Confirm -> merge -> they land in the editor sections.
    await whPage.click('#review-confirm');
    await expect(whPage.locator('#review-sheet')).not.toHaveClass(/open/);
    await expect(whPage.locator('#sections input[value="Downtime-Reduction Initiative"]')).toHaveCount(1);
    await expect(whPage.locator('#sections input[value="Employee of the Year 2021"]')).toHaveCount(1);
    // And they RENDER in the exported resume (not merely stored).
    await whPage.click('#btn-export');
    await expect(whPage.locator('#preview-overlay')).toHaveClass(/open/);
    const titles = await whPage.locator('#resume-paper .r-sec-title').allInnerTexts();
    expect(titles.some((t) => /projects/i.test(t)), 'Projects section rendered').toBeTruthy();
    expect(titles.some((t) => /awards/i.test(t)), 'Awards section rendered').toBeTruthy();
  });

  test('section titles are level-2 headings (screen-reader outline) (a11y audit 2026-06-04)', async ({ whPage }) => {
    await gotoResume(whPage);
    // Section titles must expose heading semantics, not be plain <div>s, or a
    // screen reader jumps straight from the page H1 to the feedback footer and
    // misses the whole resume structure.
    await expect(whPage.locator('[role="heading"][aria-level="2"]', { hasText: 'Work Experience' })).toHaveCount(1);
    for (const t of ['Skills', 'Education', 'Projects']) {
      await expect(whPage.locator('[role="heading"][aria-level="2"]', { hasText: t }).first()).toBeVisible();
    }
  });

  test('reorder: the down arrow moves a row so the worker can fix reverse-chronological order (UX audit 2026-06-04)', async ({ whPage }) => {
    await gotoResume(whPage);
    const sel = '[data-sec="work"][data-field="position"]';
    const n0 = await whPage.locator(sel).count();
    await whPage.click('[data-action="add"][data-sec="work"]');
    await whPage.click('[data-action="add"][data-sec="work"]');
    const a = n0, b = n0 + 1;
    await whPage.locator(sel).nth(a).fill('ZZZ Older Role');
    await whPage.locator(sel).nth(b).fill('AAA Newer Role');
    // Move the first of the two new rows DOWN -> it swaps with the next.
    await whPage.click(`[data-sec="work"][data-action="down"][data-idx="${a}"]`);
    await expect(whPage.locator(sel).nth(a)).toHaveValue('AAA Newer Role');
    await expect(whPage.locator(sel).nth(b)).toHaveValue('ZZZ Older Role');
  });

  test('JD keyword-gap score: shows match %, lists missing terms, and "add to skills" closes the gap (Phase 1)', async ({ whPage }) => {
    await gotoResume(whPage);
    // Seed one matchable skill so the score is deterministic and non-trivial.
    await whPage.click('[data-action="add"][data-sec="skills"]');
    await whPage.locator('[data-sec="skills"][data-field="name"]').last().fill('Preventive Maintenance');

    // Stub the JD keyword EXTRACTION (the model's job). The SCORE is computed on
    // the client, so this proves the deterministic match + render + add path -
    // never the model computing the number.
    await whPage.route('**/functions/v1/resume-polish', (route) => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ keywords: [
        { term: 'Preventive Maintenance', importance: 'high' },
        { term: 'PLC', importance: 'high' },
        { term: 'SAP PM', importance: 'medium' },
      ] }),
    }));

    await whPage.fill('#jd-input', 'Technician needed with Preventive Maintenance, PLC, and SAP PM experience.');
    await whPage.click('#btn-jdscore');

    // Panel renders: 1 of 3 matched = 33%.
    await expect(whPage.locator('#jd-score-panel')).toBeVisible({ timeout: 15000 });
    await expect(whPage.locator('#jd-score-panel .jd-score-pct')).toHaveText('33%');
    await expect(whPage.locator('#jd-score-panel .jd-score-sub')).toContainText('1 of 3');
    // Matched term sits under "Already covered"; PLC + SAP PM are tappable Missing chips.
    await expect(whPage.locator('.kw-have', { hasText: 'Preventive Maintenance' })).toHaveCount(1);
    await expect(whPage.locator('.kw-miss[data-term="PLC"]')).toHaveCount(1);

    // Tap PLC -> it selects -> the add button appears -> add it to Skills.
    await whPage.click('.kw-miss[data-term="PLC"]');
    await expect(whPage.locator('.kw-miss[data-term="PLC"]')).toHaveAttribute('aria-pressed', 'true');
    await whPage.click('#btn-jd-add');

    // PLC is now a real skill row AND the score recomputed upward (2 of 3 = 67%).
    await expect(whPage.locator('#sections input[value="PLC"]')).toHaveCount(1);
    await expect(whPage.locator('#jd-score-panel .jd-score-pct')).toHaveText('67%');
  });

  test('JD score still works when the AI is busy - local fallback + calm toast (free-tier resilience, MCP persona sweep 2026-06-05)', async ({ whPage }) => {
    // The core audience is on a flaky free-tier/CGNAT chain. When resume-polish 429s,
    // extractJdKeywordsLocal() must still produce a score - and the worker must NOT be
    // left staring at the raw "rate limited" error toast next to a working score.
    await gotoResume(whPage);
    await whPage.click('[data-action="add"][data-sec="skills"]');
    await whPage.locator('[data-sec="skills"][data-field="name"]').last().fill('Preventive Maintenance');
    await whPage.route('**/functions/v1/resume-polish', (route) =>
      route.fulfill({ status: 429, contentType: 'application/json', body: JSON.stringify({ error: 'rate limited' }) }));
    await whPage.fill('#jd-input', 'Maintenance technician: PLC, VFD, preventive maintenance, hydraulics, TESDA NC II, 5S.');
    await whPage.click('#btn-jdscore');
    // Fallback still renders a real score panel...
    await expect(whPage.locator('#jd-score-panel')).toBeVisible({ timeout: 15000 });
    await expect(whPage.locator('#jd-score-panel .jd-score-pct')).toHaveText(/\d+%/);
    // ...and the alarming raw error toast is replaced by a calm offline-estimate note.
    await expect(whPage.locator('#toast-msg')).toContainText(/offline/i);
  });

  test('quantification coach counts experience bullets with a number and updates live (Phase 1)', async ({ whPage }) => {
    await gotoResume(whPage);
    await whPage.click('[data-action="add"][data-sec="work"]');
    const hl = whPage.locator('[data-sec="work"][data-field="highlights"]').last();
    await hl.fill('Maintained pumps and motors');                 // one bullet, no number
    await expect(whPage.locator('#quant-coach')).toBeVisible();
    await expect(whPage.locator('#quant-coach')).toContainText('0 of 1');
    await hl.fill('Reduced downtime by 20% across 12 conveyors');  // now carries numbers
    await expect(whPage.locator('#quant-coach')).toContainText('All 1');
    await expect(whPage.locator('#quant-coach')).toHaveClass(/ok/);
  });

  test('"promote, dont duplicate" toggle is off by default, reaches the extractor, and persists (Phase 1)', async ({ whPage }) => {
    await gotoResume(whPage);
    const toggle = whPage.locator('#promote-dedupe');
    await expect(toggle, 'safe default is OFF (capture the most)').not.toBeChecked();
    let sentFlag: unknown;
    await whPage.route('**/functions/v1/resume-extract', (route) => {
      try { sentFlag = (route.request().postDataJSON() || {}).dedupe_promotions; } catch (_) { sentFlag = 'parse-error'; }
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(EXTRACT_FIXTURE) });
    });
    await toggle.check();
    await whPage.setInputFiles('#file-any', { name: 'cv.png', mimeType: 'image/png', buffer: PNG_1x1 });
    await expect(whPage.locator('#review-sheet')).toHaveClass(/open/, { timeout: 15000 });
    expect(sentFlag, 'toggle ON -> dedupe_promotions:true in the extract request').toBe(true);
    // Preference persists across a reload.
    await whPage.reload({ waitUntil: 'domcontentloaded' });
    await expect(whPage.locator('#promote-dedupe')).toBeChecked();
  });

  test('Word .docx export downloads a real .docx file (Phase 2 portability)', async ({ whPage }) => {
    await gotoResume(whPage);
    await whPage.fill('[data-basics="name"]', 'Maria Santos');
    await whPage.click('#btn-export');
    await expect(whPage.locator('#preview-overlay')).toHaveClass(/open/);
    const [download] = await Promise.all([
      whPage.waitForEvent('download', { timeout: 20000 }),
      whPage.click('#pv-docx'),
    ]);
    expect(download.suggestedFilename()).toMatch(/\.docx$/i);
  });

  test('cover-letter draft renders an editable, copyable letter from real facts (Phase 3)', async ({ whPage }) => {
    await gotoResume(whPage);
    await whPage.click('[data-action="add"][data-sec="skills"]');
    await whPage.locator('[data-sec="skills"][data-field="name"]').last().fill('Preventive Maintenance');
    await whPage.route('**/functions/v1/resume-polish', (route) => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ letter: 'Dear Hiring Manager,\n\nI am applying for the Maintenance Technician role.\n\nSincerely,\nMaria' }),
    }));
    await whPage.click('#btn-coverletter');
    await expect(whPage.locator('#cl-text')).toBeVisible({ timeout: 15000 });
    await expect(whPage.locator('#cl-text')).toHaveValue(/Dear Hiring Manager/);
    await expect(whPage.locator('#cl-copy')).toBeVisible();
    // The draft textarea must be >=16px or iOS auto-zooms when the worker taps to
    // edit it on a phone (MCP sweep 2026-06-05: it was 0.8rem/12.8px - the only
    // text field under the 16px floor). Mobile-first audience: keep it tappable.
    const clFont = await whPage.locator('#cl-text').evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
    expect(clFont, 'cover-letter textarea must be >=16px (no iOS focus-zoom)').toBeGreaterThanOrEqual(16);
  });

  test('preview is a labelled dialog and ESC closes it (a11y, Phase 3)', async ({ whPage }) => {
    await gotoResume(whPage);
    await expect(whPage.locator('#preview-overlay')).toHaveAttribute('role', 'dialog');
    await whPage.click('#btn-export');
    await expect(whPage.locator('#preview-overlay')).toHaveClass(/open/);
    await whPage.keyboard.press('Escape');
    await expect(whPage.locator('#preview-overlay')).not.toHaveClass(/open/);
  });

  test('a plain-text (.txt) resume is accepted and routed through extract (MCP sweep 2026-06-05)', async ({ whPage }) => {
    // A .txt resume (Notepad / exported notes) is the simplest input there is, and
    // the edge fn already accepts a raw-text payload. Before the fix, the handler's
    // type switch fell through to { error: 'unsupported' } and the sheet NEVER
    // opened - silently rejecting the most basic format on a phone-first tool.
    // Guard: selecting a .txt OPENS the review sheet with extracted rows.
    await stubExtract(whPage);
    await gotoResume(whPage);
    await whPage.setInputFiles('#file-any', {
      name: 'my_resume.txt', mimeType: 'text/plain',
      buffer: Buffer.from('Maria Santos\nMaintenance Technician\nSkills: arc welding, centrifugal pumps'),
    });
    await expect(whPage.locator('#review-sheet'), '.txt must be read + extracted, not rejected as unsupported')
      .toHaveClass(/open/, { timeout: 15000 });
    await expect(whPage.locator('#review-body input[value="arc welding"]')).toHaveCount(1);
  });

  test('a long unbroken token in a bullet does NOT overflow the resume paper (MCP sweep 2026-06-05)', async ({ whPage }) => {
    // A pasted long URL / email / accidental no-space string would push the paper
    // wider than its 720px column and clip in the PDF. The paper must break long
    // tokens (overflow-wrap on .resume-paper *). Guard the user-visible outcome:
    // rendered paper width never exceeds its own column.
    await gotoResume(whPage);
    await whPage.fill('[data-basics="name"]', 'Pablo Aguilar');
    await whPage.click('[data-action="add"][data-sec="work"]');
    await whPage.locator('[data-sec="work"][data-field="position"]').last().fill('Technician');
    await whPage.locator('[data-sec="work"][data-field="highlights"]').last()
      .fill('Maintained ' + 'Supercalifragilisticexpialidocious'.repeat(8) + ' systems');
    await whPage.click('#btn-export');
    await expect(whPage.locator('#preview-overlay')).toHaveClass(/open/);
    const overflow = await whPage.locator('#resume-paper').evaluate(
      (el) => el.scrollWidth - el.clientWidth);
    expect(overflow, 'resume paper must not overflow horizontally on a long token').toBeLessThanOrEqual(2);
  });

  test('named multiple resumes: create / list / switch, and reload reopens the LAST-OPEN one not the newest (multi-doc, MCP build 2026-06-05)', async ({ whPage }) => {
    // Real cloud round-trips (resume_documents, owner-RLS). Start from a fresh blank
    // so we never rename the worker's existing resume, and ALWAYS delete what we
    // create (finally) — a leftover doc would load on init and break sibling tests
    // that assume an empty start (the dedupe test learned this the hard way).
    await gotoResume(whPage);
    const A = 'ZZ MCP Alpha ' + Date.now();
    const B = 'ZZ MCP Bravo ' + Date.now();
    const nameAndSave = async (title: string, skill: string) => {
      await whPage.click('#btn-resumes');
      await expect(whPage.locator('#resume-manager')).toHaveClass(/open/);
      await whPage.click('#rm-new');                       // fresh blank doc (_resumeId=null)
      await whPage.click('#btn-resumes');
      await whPage.fill('#rm-current-title', title);
      await whPage.click('#rm-close');
      await whPage.click('[data-action="add"][data-sec="skills"]');
      await whPage.locator('[data-sec="skills"][data-field="name"]').last().fill(skill);
      await whPage.click('#btn-save');
      await expect(whPage.locator('#toast-msg')).toContainText(/saved/i, { timeout: 20000 });
    };
    const deleteByTitle = async (title: string) => {
      await whPage.click('#btn-resumes');
      const row = whPage.locator('.rm-row', { hasText: title });
      if (await row.count()) {
        await row.first().locator('[data-rm-del]').click();
        await row.first().locator('[data-rm-del-yes]').click();
        await expect(whPage.locator('#rm-list')).not.toContainText(title, { timeout: 15000 });
      }
      await whPage.click('#rm-close');
    };
    try {
      await nameAndSave(A, 'Alpha-Skill');
      await nameAndSave(B, 'Bravo-Skill');                  // B is now the NEWEST doc

      // Manager lists both named resumes.
      await whPage.click('#btn-resumes');
      await expect(whPage.locator('#rm-list')).toContainText(A);
      await expect(whPage.locator('#rm-list')).toContainText(B);

      // Switch to A (the OLDER doc) -> editor shows A's skill, not B's.
      await whPage.locator('.rm-row', { hasText: A }).getByRole('button', { name: 'Open' }).click();
      await expect(whPage.locator('#sections input[value="Alpha-Skill"]')).toHaveCount(1);
      await expect(whPage.locator('#sections input[value="Bravo-Skill"]')).toHaveCount(0);

      // Reload MUST reopen A (last-open), NOT B (newest) — the continuity fix.
      await whPage.reload({ waitUntil: 'domcontentloaded' });
      await whPage.waitForSelector('[data-action="add"][data-sec="skills"]', { timeout: 10000 });
      await expect(whPage.locator('#sections input[value="Alpha-Skill"]')).toHaveCount(1);
      await expect(whPage.locator('#sections input[value="Bravo-Skill"]')).toHaveCount(0);
    } finally {
      await deleteByTitle(A);
      await deleteByTitle(B);
    }
  });
});
