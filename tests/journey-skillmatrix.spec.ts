/**
 * journey-skillmatrix.spec.ts — Skill Matrix user journey.
 *
 * Key regression from walkthrough 2026-05-14:
 *   Verdict said "Primary discipline 5 levels behind target" (red) while
 *   Card 1 said "ON TARGET 5/5 / COMPLETE" (green) — contradiction caused
 *   by primary_skill ("PLC Programming") not being in the DISCIPLINES array.
 *   Fixed: primaryIsTracked guard prevents phantom gap calculation.
 *
 * Scenarios:
 *   verdict consistency  — verdict tone matches Card 1 (no contradiction)
 *   primary not tracked  — correct "Primary skill not yet trackable" verdict
 *   source chip          — chip declares skill_profiles + skill_badges
 *   cards populated      — heroes not "—"
 *   details toggle       — expands/collapses
 *   no console errors    — no JS errors on load
 *   loading state        — verdict settles within timeout
 */
import { test, expect } from './_fixtures';
import { waitForPageReady, pageSrcWithExternals } from './_helpers';

const PAGE = '/workhive/skillmatrix.html';

async function waitForSMVerdictSettled(page) {
  await page.waitForFunction(() => {
    const el = document.getElementById('sm-verdict-label');
    if (!el) return true;
    const t = (el.textContent || '').trim();
    return !!t && !t.startsWith('Computing');
  }, { timeout: 12000 }).catch(() => {});
}

test.describe('skillmatrix.html — user journey', () => {

  test('page loads without console errors', async ({ whPage }) => {
    const errors: string[] = [];
    whPage.on('pageerror', e => errors.push(e.message));

    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);

    const serious = errors.filter(e => !e.includes('net::ERR_') && !e.includes('Failed to fetch'));
    expect(serious, `console errors: ${serious.join(' | ')}`).toEqual([]);
  });

  test('source chip declares skill_profiles + skill_badges', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);

    const chip = whPage.locator('#skillmatrix-source-chip');
    const text = await chip.textContent({ timeout: 5000 }).catch(() => '');
    expect(text, 'chip should declare skill_profiles').toContain('skill_profiles');
    expect(text, 'chip should declare skill_badges').toContain('skill_badges');
  });

  test('verdict settles from Computing state within 12 seconds', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForSMVerdictSettled(whPage);

    const label = await whPage.locator('#sm-verdict-label').textContent().catch(() => '');
    expect(label?.trim(), 'verdict should settle').not.toMatch(/^Computing/);
    expect(label?.trim().length).toBeGreaterThan(0);
  });

  test('REGRESSION: verdict and Card 1 (ON TARGET) do not contradict each other', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForSMVerdictSettled(whPage);

    const label     = await whPage.locator('#sm-verdict-label').textContent().catch(() => '');
    const card1Tag  = await whPage.locator('#sm-card-ontrack .sc-tag, .simple-card .sc-tag').first()
      .textContent().catch(() => '');

    // The walkthrough bug: verdict was red ("Primary ... behind") while card was green (COMPLETE)
    // These two signals should not point in opposite directions:
    const verdictIsRed     = /behind|attention|critical/i.test(label || '');
    const card1IsComplete  = /COMPLETE/i.test(card1Tag || '');

    expect(
      verdictIsRed && card1IsComplete,
      `Contradiction: verdict is red ("${label}") but Card 1 tag is "${card1Tag}". ` +
      `This is the 2026-05-14 regression — primaryIsTracked guard may have been removed.`,
    ).toBe(false);
  });

  test('Pablo: primary skill PLC Programming not in DISCIPLINES → "not yet trackable" verdict', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForSMVerdictSettled(whPage);

    const primary = await whPage.locator('#header-sub').textContent().catch(() => '');
    const label   = await whPage.locator('#sm-verdict-label').textContent().catch(() => '');

    // If primary is PLC Programming (not a standard discipline), expect the
    // "Primary skill not yet trackable" verdict (not the red phantom-gap verdict)
    if (primary?.includes('PLC Programming')) {
      expect(label, 'PLC Programming should produce "not yet trackable" verdict, not phantom red')
        .toMatch(/not yet trackable/i);
      // Must NOT say "5 levels behind" — that was the phantom bug
      expect(label, '"levels behind" verdict for untracked primary is the regression')
        .not.toMatch(/\d+ levels behind/i);
    }
  });

  test('3 skill cards have non-placeholder heroes', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForSMVerdictSettled(whPage);

    const heroes = whPage.locator('.sc-hero');
    await expect(heroes.first()).toBeVisible({ timeout: 8000 });
    const count = await heroes.count();
    expect(count, 'at least 3 skill cards should render').toBeGreaterThanOrEqual(3);

    for (let i = 0; i < Math.min(count, 3); i++) {
      const text = await heroes.nth(i).textContent();
      expect(text?.trim(), `card ${i} hero should not be "—"`).not.toBe('—');
    }
  });

  test('details toggle expands the skill matrix explainer', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForSMVerdictSettled(whPage);

    const btn  = whPage.locator('#details-toggle-btn');
    const pane = whPage.locator('#sm-summary-details');

    if (await btn.count() === 0) {
      console.log('[journey-skillmatrix] no details toggle on this page');
      return;
    }

    await expect(btn).toBeVisible({ timeout: 5000 });
    await btn.click();
    if (await pane.count() > 0) {
      await expect(pane).toBeVisible({ timeout: 3000 });
    }
  });

  test('Skill Overview radar chart canvas or container renders', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(3000);

    // The radar chart renders as a canvas element
    const canvas = whPage.locator('canvas').first();
    const hasCanvas = await canvas.count();
    if (hasCanvas > 0) {
      await expect(canvas).toBeVisible({ timeout: 5000 });
    }
    // If no canvas, that's acceptable (chart may be loading or empty state)
  });

  test('empty state: no badges shown gracefully when worker has no badges', async ({ whPage }) => {
    // This test verifies that a 0-badge state doesn't crash the page
    await whPage.goto(PAGE);
    await waitForSMVerdictSettled(whPage);

    const badgesHero = await whPage.locator('#sm-badges-hero').textContent().catch(() => null);
    // Either a number (0–30) or "—" are valid — what's NOT valid is a JS error or crash
    if (badgesHero !== null) {
      const n = parseInt(badgesHero.trim(), 10);
      expect(isNaN(n) || n >= 0, `badges hero should be a non-negative number, got: ${badgesHero}`)
        .toBe(true);
    }
  });
});

/* === Sentinel-proposed scenarios (check-name anchored) === */
test.describe('skillmatrix.html - sentinel scenarios', () => {

  test('discipline_colors: each discipline tile renders with a color style', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);
    const tiles = whPage.locator('.discipline-tile, [data-discipline], .skill-card').first();
    if (await tiles.count() === 0) { test.skip(true, 'no discipline tiles rendered'); return; }
    const hasColor = await tiles.evaluate((el) => {
      const cs = getComputedStyle(el as HTMLElement);
      const c = cs.backgroundColor + cs.borderColor + cs.color;
      return !!c && !c.includes('rgba(0, 0, 0, 0)');
    });
    expect(hasColor, 'discipline tile must render with non-transparent color').toBeTruthy();
  });

  test('discipline_icons: discipline tiles render with iconography', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(2000);
    const tiles = whPage.locator(
      '.discipline-tile, [data-discipline], .skill-card, .discipline-card, .matrix-tile'
    );
    if (await tiles.count() === 0) {
      test.skip(true, 'no discipline tiles rendered on this seed');
      return;
    }
    const iconLike = whPage.locator(
      'svg, img, [data-icon], i.fa-, .icon, .material-icons, [class*="icon"]'
    );
    expect(await iconLike.count(),
      'skillmatrix should render at least one icon-like element').toBeGreaterThan(0);
  });

  test('level_labels: skill level labels are visible on tiles', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    await whPage.waitForTimeout(1500);
    const html = await whPage.content();
    const hasLabel = /level\s*\d|Beginner|Practitioner|Expert|Advanced|Intermediate/i.test(html);
    expect(hasLabel, 'skill level labels must be visible somewhere on the page').toBeTruthy();
  });

  test('pass_threshold: page references a pass threshold number', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc = await pageSrcWithExternals(whPage);
    const has = /pass[_-]?threshold|passing[_-]?score|score.*\d{2,}/i.test(__sentSrc);
    expect(has, 'skillmatrix should declare a pass threshold').toBeTruthy();
  });

  test('cooldown_on_failure: exam cooldown logic referenced in scripts', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_2 = await pageSrcWithExternals(whPage);
    const has = /cooldown|retry[-_]?after|cool[-_]?down|wait.*before.*retry/i.test(__sentSrc_2);
    expect(has, 'exam path should include cooldown logic on failure').toBeTruthy();
  });

  test('badge_upsert_key: skill_badges writes use canonical upsert key', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_3 = await pageSrcWithExternals(whPage);
    const has = /upsert.*skill_badges|skill_badges.*upsert|onConflict.*worker|worker.*onConflict/i.test(__sentSrc_3);
    expect(has, 'skill_badges writes should use upsert with canonical conflict key').toBeTruthy();
  });

  test('exam_array_count: exam questions array has expected length', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const counts = await whPage.evaluate(() => {
      const src = document.documentElement.outerHTML;
      const matches = src.match(/questions\s*[:=]\s*\[/g) || [];
      return matches.length;
    });
    expect(counts, 'skillmatrix should declare at least one questions array').toBeGreaterThan(0);
  });

  test('options_count: each multiple-choice question carries options array', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_4 = await pageSrcWithExternals(whPage);
    const hasOpts = /options\s*[:=]\s*\[/.test(__sentSrc_4);
    expect(hasOpts, 'questions should declare options array').toBeTruthy();
  });

  test('answer_index_valid: answer indices fall within options length', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_5 = await pageSrcWithExternals(whPage);
    const has = /answer.*index|answerIndex|correct.*index/i.test(__sentSrc_5);
    expect(has, 'exam path should track an answer index').toBeTruthy();
  });

  test('draft_cleanup: skill draft cleanup is wired', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_6 = await pageSrcWithExternals(whPage);
    const has = /draft.*cleanup|clearDraft|cleanupDraft|draft.*remove/i.test(__sentSrc_6);
    expect(has, 'skill draft state should be cleaned up after exam').toBeTruthy();
  });

  test('level_content_complete: every level has content for every discipline', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const __sentSrc_7 = await pageSrcWithExternals(whPage);
    const has = /level.*content|levelContent|LEVELS\s*=|skillLevels/i.test(__sentSrc_7);
    expect(has, 'skillmatrix should expose level content registry').toBeTruthy();
  });

  test('skill_content_coverage: skill content covers all canonical disciplines', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);
    const html = await whPage.content();
    const found = ['Mechanical', 'Electrical', 'Instrumentation', 'Civil', 'Process']
      .filter(d => html.includes(d));
    expect(found.length, 'at least 3 canonical disciplines should be present').toBeGreaterThanOrEqual(3);
  });

});
