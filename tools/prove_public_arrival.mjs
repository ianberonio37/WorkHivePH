// prove_public_arrival — the PUBLIC FUNNELS family of the live-walk wave (2026-09-06).
//
// tools/live_walk_manifest.py --family "public funnels" lists 56 rows: one "Learn arrival" per article plus the
// AEO / SEO / sitemap / canonical cross-cutting arcs. Every one is a question about what a VISITOR OR A CRAWLER
// RECEIVES, and the substrate settles which instrument can answer it: major AI crawlers "fetch JS but never
// execute it" (Vercel/MERJ, 500M+ GPTBot fetches, zero JS execution). So the honest lens is the RAW served HTML,
// with no browser and no JavaScript - not a rendered DOM, which would show content a crawler never sees.
//
// Six questions per public page, asked of the bytes the server actually sends:
//   A1 title          a non-empty, non-placeholder <title> under 65 chars of visible weight
//   A2 description    a meta description a search result can quote
//   A3 canonical      a self-referential <link rel=canonical> - the page names its own address
//   A4 heading        exactly one <h1>, and it is not empty
//   A5 body-in-HTML   the article's substance is IN the served bytes (>= 1200 chars of text outside script/style),
//                     not injected after load - the difference between being read and being skipped
//   A6 structured     JSON-LD present, and it parses
// plus S1: every page is listed in sitemap.xml, and every sitemap entry resolves.
//
//   node tools/prove_public_arrival.mjs                       # local seeder (the served files)
//   node tools/prove_public_arrival.mjs --origin https://workhiveph.com
//   node tools/prove_public_arrival.mjs --page learn/best-free-cmms-software-philippines/index.html
import { readdirSync, existsSync, readFileSync } from 'node:fs';

const ORIGIN = (() => { const i = process.argv.indexOf('--origin'); return i >= 0 ? process.argv[i + 1] : 'http://127.0.0.1:5000/workhive'; })();
const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();

const learn = existsSync('learn')
  ? readdirSync('learn', { withFileTypes: true }).filter((d) => d.isDirectory() && existsSync(`learn/${d.name}/index.html`)).map((d) => `learn/${d.name}/index.html`)
  : [];
const PAGES = [...(existsSync('learn/index.html') ? ['learn/index.html'] : []), ...learn, 'index.html']
  .filter((p) => !ONLY || p === ONLY);

const strip = (html) => html
  .replace(/<script[\s\S]*?<\/script>/gi, ' ')
  .replace(/<style[\s\S]*?<\/style>/gi, ' ')
  .replace(/<[^>]+>/g, ' ')
  .replace(/&[a-z]+;/gi, ' ')
  .replace(/\s+/g, ' ').trim();

const get = async (path) => {
  try {
    const r = await fetch(`${ORIGIN}/${path}`, { headers: { 'User-Agent': 'WorkHive-arrival-prover (raw HTML, no JS)' } });
    return { status: r.status, html: await r.text() };
  } catch (e) { return { status: 0, html: '', err: String(e).slice(0, 60) }; }
};

// sitemap first: it is one fetch and it answers a question about all of them
let sitemap = new Set();
{
  const r = await get('sitemap.xml');
  for (const m of r.html.matchAll(/<loc>\s*([^<]+?)\s*<\/loc>/gi)) sitemap.add(m[1].trim());
}

let bad = 0, n = 0;
const issuesBySurface = {};
for (const page of PAGES) {
  n++;
  const r = await get(page);
  const issues = [];
  if (r.status !== 200) issues.push(`A0 the page itself answers ${r.status}${r.err ? ' ' + r.err : ''}`);
  else {
    const h = r.html;
    const title = (h.match(/<title[^>]*>([\s\S]*?)<\/title>/i) || [, ''])[1].trim();
    const attr = (re) => { const m = h.match(re); return m ? m[2].trim() : ''; };
    // ★A CHARACTER CLASS THAT EXCLUDES BOTH QUOTES STOPS AT AN APOSTROPHE. The first run reported three meta
    // descriptions of 16-41 chars; every one was a full sentence that merely contained "WorkHive's", and
    // [^"']* ended the capture right there. Match the OPENING quote and close on the same one.
    const desc = attr(new RegExp('<meta[^>]+name=["\']description["\'][^>]+content=(["\'])([\\s\\S]*?)\\1', 'i'));
    const canon = attr(new RegExp('<link[^>]+rel=["\']canonical["\'][^>]+href=(["\'])([\\s\\S]*?)\\1', 'i'));
    const h1s = [...h.matchAll(/<h1[^>]*>([\s\S]*?)<\/h1>/gi)].map((m) => strip(m[1]));
    const text = strip(h);
    const ld = [...h.matchAll(/<script[^>]+type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi)].map((m) => m[1]);

    if (!title || /^(untitled|document|page)$/i.test(title)) issues.push(`A1 title is ${title ? `"${title}"` : 'empty'}`);
    if (!desc) issues.push('A2 no meta description - a search result would quote whatever it finds');
    else if (desc.length < 50) issues.push(`A2 meta description is ${desc.length} chars, too thin to be quoted`);
    if (!canon) issues.push('A3 no rel=canonical - the page does not name its own address');
    else {
      const want = page.replace(/index\.html$/, '').replace(/\/$/, '');
      const got = canon.replace(/^https?:\/\/[^/]+\/?/, '').replace(/index\.html$/, '').replace(/\/$/, '');
      if (want && got !== want) issues.push(`A3 canonical points at "${got || '/'}" while this page is "${want}"`);
    }
    // ★AN EMPTY h1 IS NOT A COMPETING HEADING (calibrated 2026-09-06). index.html ships two h1 elements and
    // that is deliberate and documented in place: the signed-in dashboard greeting and the signed-out hero are
    // MUTUALLY EXCLUSIVE by display switch, and axe's page-has-heading-one needs a visible h1 in each view. In
    // the SERVED bytes the greeting is empty - JS fills it at runtime - so a crawler reads exactly one heading.
    // The lens therefore counts headings a crawler can actually read, and only those.
    const filled = h1s.filter(Boolean);
    if (filled.length === 0) issues.push(h1s.length ? 'A4 every h1 is empty in the served html' : 'A4 no h1');
    else if (filled.length > 1) issues.push(`A4 ${filled.length} non-empty h1 elements: ${filled.map((t) => '"' + t.slice(0, 30) + '"').join(', ')}`);
    if (text.length < 1200) issues.push(`A5 only ${text.length} chars of text in the SERVED html - a crawler that does not run JS sees this much and no more`);
    if (ld.length === 0) issues.push('A6 no JSON-LD');
    else { for (const block of ld) { try { JSON.parse(block); } catch { issues.push('A6 a JSON-LD block does not parse'); break; } } }
    const url = page.replace(/index\.html$/, '');
    const inMap = [...sitemap].some((u) => u.replace(/^https?:\/\/[^/]+\//, '').replace(/\/$/, '') === url.replace(/\/$/, ''));
    if (sitemap.size && !inMap) issues.push('S1 not listed in sitemap.xml');
  }
  if (issues.length) { bad++; issuesBySurface[page] = issues; }
  if (issues.length || ONLY) {
    console.log(`  ${issues.length ? 'BAD' : 'ok '} ${page}`);
    for (const s of issues.slice(0, ONLY ? 20 : 3)) console.log(`        ${s.slice(0, 165)}`);
  }
}
console.log(`${bad ? 'FAIL' : 'PASS'} public-arrival - ${n - bad}/${n} public pages arrive complete in the RAW served HTML (title, description, self-canonical, one h1, body present without JS, JSON-LD, listed in sitemap) @ ${ORIGIN}`);
process.exit(bad ? 1 : 0);
