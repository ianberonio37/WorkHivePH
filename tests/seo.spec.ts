/**
 * seo.spec.ts — validate_seo.py L0->L2 bridge (sentinel draft #5, 2026-05-18).
 *
 * Browser-level SEO meta sweep. The Python validator scans source HTML;
 * this spec asserts the same rules against the rendered DOM seen by a
 * crawler (rawPage = unauthenticated, the perspective Google/Bing use).
 * Catches runtime stripping/rewriting that the static scan can't see.
 *
 * One test() per check from validate_seo.py CHECK_NAMES so the next
 * sentinel run flips all 6 checks from uncovered -> covered via the
 * Path A matcher convention (test name starts with `<check_name>:`).
 *
 * Skills consulted: seo-content (meta-tag canonical rules), qa (rawPage
 * for crawler perspective), platform-guardian (one test per check name
 * so sentinel auto-matches).
 */
import { test, expect } from './_fixtures';

const LANDING = '/workhive/index.html';
const APP_PAGES = [
  '/workhive/logbook.html',
  '/workhive/inventory.html',
  '/workhive/pm-scheduler.html',
  '/workhive/hive.html',
  '/workhive/assistant.html',
  '/workhive/skillmatrix.html',
  '/workhive/dayplanner.html',
  '/workhive/engineering-design.html',
  '/workhive/platform-health.html',
];
// Representative LEARN sample — full list of 24+ articles would push
// past Playwright's 60s per-test timeout. Covers landing + 3 evergreen
// content pages. Add more here as SEO regressions surface in specific
// articles.
const LEARN_SAMPLE = [
  '/workhive/about/',
  '/workhive/privacy-policy/',
  '/workhive/terms-of-service/',
  '/workhive/learn/',
  '/workhive/learn/what-is-oee-how-to-calculate/',
];

const PUBLIC_PAGES = [LANDING, ...LEARN_SAMPLE];

test.describe('SEO meta sweep (L0->L2 bridge for validate_seo.py)', () => {

  test('noindex: app pages declare robots noindex in served HTML', async ({ rawPage }) => {
    // Use a pure HTTP fetch via page.request — app pages JS-redirect to
    // signin when visited unauthenticated, which would overwrite the
    // robots meta with the landing page's (no noindex). page.request
    // skips the browser entirely and returns what a crawler sees.
    for (const url of APP_PAGES) {
      const res = await rawPage.request.get(url);
      expect(res.ok(), `${url} fetch failed (${res.status()})`).toBe(true);
      const html = await res.text();
      const m = html.match(
        /<meta[^>]+name=["']robots["'][^>]*content=["']([^"']+)["']/i
      );
      expect(m, `${url} missing <meta name="robots" content="...">`).toBeTruthy();
      expect(m![1].toLowerCase(), `${url} robots meta missing noindex ("${m![1]}")`)
        .toContain('noindex');
    }
  });

  test('title_tags: every public page renders a non-empty WorkHive-branded <title>', async ({ rawPage }) => {
    for (const url of PUBLIC_PAGES) {
      await rawPage.goto(url, { waitUntil: 'domcontentloaded' });
      const title = await rawPage.title();
      expect(title.length, `${url} title too short ("${title}")`)
        .toBeGreaterThanOrEqual(15);
      expect(title, `${url} title missing WorkHive brand ("${title}")`)
        .toMatch(/WorkHive/i);
    }
  });

  test('canonical_tags: every public page renders a canonical link', async ({ rawPage }) => {
    for (const url of PUBLIC_PAGES) {
      await rawPage.goto(url, { waitUntil: 'domcontentloaded' });
      const canonical = await rawPage.locator('link[rel="canonical"]').first()
        .getAttribute('href');
      expect(canonical, `${url} missing canonical link`).toBeTruthy();
      expect(canonical!, `${url} canonical not absolute ("${canonical}")`)
        .toMatch(/^https?:\/\//);
    }
  });

  test('meta_descriptions: every public page renders a meta description', async ({ rawPage }) => {
    for (const url of PUBLIC_PAGES) {
      await rawPage.goto(url, { waitUntil: 'domcontentloaded' });
      const desc = await rawPage.locator('meta[name="description"]').first()
        .getAttribute('content');
      expect(desc, `${url} missing meta description`).toBeTruthy();
      expect(desc!.length, `${url} meta description too short (${desc!.length} chars)`)
        .toBeGreaterThanOrEqual(50);
    }
  });

  test('og_tags: landing page renders complete OG tag set', async ({ rawPage }) => {
    await rawPage.goto(LANDING, { waitUntil: 'domcontentloaded' });
    for (const og of ['og:title', 'og:description', 'og:image', 'og:url']) {
      const content = await rawPage.locator(`meta[property="${og}"]`).first()
        .getAttribute('content');
      expect(content, `landing missing ${og}`).toBeTruthy();
    }
  });

  test('structured_data: landing renders parseable JSON-LD with SoftwareApplication or Organization', async ({ rawPage }) => {
    await rawPage.goto(LANDING, { waitUntil: 'domcontentloaded' });
    const scripts = await rawPage.locator('script[type="application/ld+json"]')
      .allTextContents();
    expect(scripts.length, 'landing has no JSON-LD blocks').toBeGreaterThan(0);

    // Recursively collect every @type token from the block, including
    // entries nested under @graph (the schema.org pattern this landing
    // page uses — Organization lives inside @graph[]).
    const collectTypes = (node: unknown): string[] => {
      if (!node || typeof node !== 'object') return [];
      const obj = node as Record<string, unknown>;
      const out: string[] = [];
      if (obj['@type']) {
        const t = obj['@type'];
        if (Array.isArray(t)) out.push(...(t as string[]));
        else out.push(t as string);
      }
      if (Array.isArray(obj['@graph'])) {
        for (const child of obj['@graph']) out.push(...collectTypes(child));
      }
      return out;
    };

    const allTypes = new Set<string>();
    for (const raw of scripts) {
      let parsed: unknown;
      try {
        parsed = JSON.parse(raw);
      } catch {
        throw new Error(
          `landing has unparseable JSON-LD (first 120 chars): ${raw.slice(0, 120)}`
        );
      }
      const roots = Array.isArray(parsed) ? parsed : [parsed];
      for (const root of roots) {
        for (const t of collectTypes(root)) allTypes.add(t);
      }
    }
    const ok = allTypes.has('SoftwareApplication') || allTypes.has('Organization');
    expect(
      ok,
      `landing JSON-LD missing SoftwareApplication or Organization @type ` +
      `(found: ${[...allTypes].join(', ') || '(none)'})`
    ).toBe(true);
  });
});
