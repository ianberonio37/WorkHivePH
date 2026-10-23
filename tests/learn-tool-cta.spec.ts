/**
 * learn-tool-cta.spec.ts — validate_tool_aligned_cta.py L0->L2 bridge (2026-10-23).
 *
 * The Python validator reads the guides' source; this spec asserts the same rules against what a
 * visitor's browser renders at /learn/<slug>/, read the way the validator reads it: the article
 * body only (header and footer chrome link every page, so they would pass the check without
 * meaning anything - tools/cta_gate.body_region).
 *
 * One test() per check in validate_tool_aligned_cta.py CHECK_NAMES, named `<check_name>: ...`
 * so the sentinel's Path A matcher binds them. The catalog is wh_pages.LEARN_ARTICLES, read
 * through Python so this spec and the validator can never hold two copies of it.
 *
 * Skills consulted: seo-content (a guide sends its reader to the tool it teaches), qa (rawPage =
 * the anonymous visitor a search result brings), platform-guardian (one test per check name).
 */
import { test, expect } from './_fixtures';
import { execSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

const ROOT = path.resolve(__dirname, '..');
const NON_TOOL_PAGES = new Set(['/index.html', '/about/index.html', '/privacy-policy/index.html',
  '/terms-of-service/index.html', '/learn/index.html']);

// slug -> declared tool path, from the one catalog the validator reads
const CATALOG: Record<string, string> = JSON.parse(execSync(
  'python -c "import json, wh_pages; print(json.dumps({k: v[0] for k, v in wh_pages.article_tool_map().items()}))"',
  { cwd: ROOT, encoding: 'utf-8' }));

const ON_DISK = fs.readdirSync(path.join(ROOT, 'learn'), { withFileTypes: true })
  .filter((d) => d.isDirectory() && fs.existsSync(path.join(ROOT, 'learn', d.name, 'index.html')))
  .map((d) => d.name).sort();

type Read = { hrefs: string[]; joinOnly: boolean };
const RENDERED: Record<string, Read> = {};

// the guides' "local dev URL bridge" rewrites root-absolute links to /workhive/... when served under /workhive/
// (production is untouched); undo it so the href read is the one production ships
const site = (href: string) => href.replace(/^https?:\/\/workhiveph\.com/i, '').replace(/^\/workhive(?=\/)/, '');
const bare = (href: string) => href.split('#')[0].split('?')[0];
const isPlatformCta = (href: string) => /^\/(?:\?signup=1|index\.html)/i.test(href);

test.beforeAll(async ({ browser }) => {
  const page = await browser.newPage();
  for (const slug of ON_DISK.filter((s) => s in CATALOG)) {
    await page.goto(`/workhive/learn/${slug}/`, { waitUntil: 'domcontentloaded' });
    RENDERED[slug] = await page.evaluate(() => {
      // body_region's span: from the start of <article> (else <main>) to the footer - the guide's own CTA
      // sections follow </article>, so the element alone is too narrow
      const start = document.querySelector('article') || document.querySelector('main') || document.body;
      const hrefs = [...document.querySelectorAll('a[href]')]
        .filter((a) => (start === a || start.contains(a) || (start.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_FOLLOWING))
          && !a.closest('footer'))
        .map((a) => a.getAttribute('href') || '');
      const joinOnly = [...document.querySelectorAll('a[href]')].some((a) =>
        /(?:btn|cta|button)/i.test(a.getAttribute('class') || '') && /^#?\/?#join$/i.test(a.getAttribute('href') || ''));
      return { hrefs, joinOnly };
    });
  }
  await page.close();
});

test.describe('learn guides send the reader to the tool they teach', () => {
  test('catalog_covers_disk: every guide a reader can open is in the catalog the checks read', () => {
    const missing = ON_DISK.filter((s) => !(s in CATALOG));
    expect(missing, `guides that ship but no check ever reads: ${missing.join(', ')}`).toEqual([]);
  });

  test('has_tool_anchor: every guide body links a tool page (or, for a guide about WorkHive, the platform)', () => {
    expect(Object.keys(RENDERED).length).toBeGreaterThan(40);   // a loader that read nothing must not pass
    const without: string[] = [];
    for (const [slug, r] of Object.entries(RENDERED)) {
      const declared = CATALOG[slug];
      const hrefs = r.hrefs.map(site);
      const ok = bare(declared) === '/index.html' && !declared.includes('?')
        ? hrefs.some(isPlatformCta)
        : hrefs.some((h) => /^\/[a-z0-9-]+\.html/i.test(h) && !NON_TOOL_PAGES.has(bare(h)) && !h.startsWith('/learn/'));
      if (!ok) without.push(slug);
    }
    expect(without, `guides whose body links no tool: ${without.join(', ')}`).toEqual([]);
  });

  test('cta_matches_declared_tool: each guide body links the tool its catalog entry declares', () => {
    const wrong: string[] = [];
    for (const [slug, r] of Object.entries(RENDERED)) {
      const declared = CATALOG[slug].startsWith('/') ? CATALOG[slug] : '/' + CATALOG[slug];
      const hrefs = r.hrefs.map(site);
      const ok = declared === '/index.html'
        ? hrefs.some(isPlatformCta)
        : hrefs.map((h) => h.split('#')[0]).includes(declared)
          || (!declared.includes('?') && hrefs.map(bare).includes(declared));
      if (!ok) wrong.push(`${slug} (declares ${declared})`);
    }
    expect(wrong, `guides that never link their declared tool: ${wrong.join('; ')}`).toEqual([]);
  });

  test('no_join_only_cta: no guide offers a button that only goes to #join', () => {
    const joinOnly = Object.entries(RENDERED).filter(([, r]) => r.joinOnly).map(([s]) => s);
    expect(joinOnly, `guides with a join-only button: ${joinOnly.join(', ')}`).toEqual([]);
  });
});
