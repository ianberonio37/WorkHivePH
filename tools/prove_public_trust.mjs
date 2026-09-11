// prove_public_trust — the public-surface trust journeys (T151, T157, T158, T161, T162), 2026-09-07.
//
// Five rows about the pages a stranger meets before anyone has vouched for this platform. A maintenance
// engineer evaluating a tool for their plant reads the public pages the way they read a vendor datasheet:
// looking for the claim that is not quite true. Each lens is a place where a page can promise something
// the product does not do, or say something today that stopped being true months ago.
//
//   U1 the snippet is true  what a search result promises, the page delivers - the title and description
//                           describe THIS page, and are not the same sentence on forty pages (T151)
//   U2 trust pages exist    there is somewhere to read who runs this, how to reach them, and what the
//                           terms are; a tool with no about page is a tool nobody can complain to (T157)
//   U3 the feed sells       the public feed shows real activity a stranger can judge, not an empty shell
//                           that says the platform is unused (T158)
//   U4 freshness governed   a dated claim is either current or carries its date - the 92-page lesson was
//                           that a stamp nobody regenerates is worse than no stamp (T161)
//   U5 comparisons fair     where the platform compares itself to alternatives, the comparison states
//                           what the alternative is GOOD at, or it is marketing wearing a table (T162)
//
// ★READ FROM WHAT SHIPS. A claim is only checkable where a stranger meets it: the rendered <title>, the
// meta description, the copy on the page. What the roadmap intended is not what the visitor reads.
//
//   node tools/prove_public_trust.mjs
import { readdirSync, readFileSync, existsSync } from 'node:fs';

const read = (f) => { try { return readFileSync(f, 'utf8'); } catch { return ''; } };
const pages = readdirSync('.').filter((f) => f.endsWith('.html'));
// the public surface: what a search engine can reach without an account
const PUBLIC = ['index.html', 'public-feed.html', 'marketplace.html', 'status.html'].filter((f) => pages.includes(f));
const learn = existsSync('learn') ? readdirSync('learn').filter((d) => existsSync(`learn/${d}/index.html`)) : [];

let bad = 0;
const say = (ok, id, line, detail) => {
  if (!ok) bad++;
  console.log(`  ${ok ? 'ok ' : 'BAD'} ${id.padEnd(22)} ${line}`);
  if (!ok && detail) console.log(`        ${detail.slice(0, 158)}`);
};

const titleOf = (src) => ((src.match(/<title>([^<]*)<\/title>/i) || [])[1] || '').trim();
const descOf = (src) => ((src.match(/<meta[^>]+name=["']description["'][^>]+content=["']([^"']*)["']/i) || [])[1] || '').trim();

// ── U1 · does the search result describe THIS page? ──────────────────────────────────────────────
{
  const all = [...PUBLIC.map((f) => [f, read(f)]), ...learn.slice(0, 60).map((d) => [`learn/${d}`, read(`learn/${d}/index.html`)])];
  const titles = new Map(), descs = new Map();
  const missing = [];
  for (const [name, src] of all) {
    const t = titleOf(src), d = descOf(src);
    if (!t || !d) { missing.push(`${name} (${!t ? 'no title' : 'no description'})`); continue; }
    titles.set(t, (titles.get(t) || 0) + 1);
    descs.set(d, (descs.get(d) || 0) + 1);
  }
  // ★THE FAILURE IS A SHARED SENTENCE, NOT AN ABSENT ONE. Forty pages carrying one description all rank
  // for the same thing and none of them tells the person which page they are about to open.
  const sharedT = [...titles.entries()].filter(([, n]) => n > 1);
  const sharedD = [...descs.entries()].filter(([, n]) => n > 1);
  say(missing.length === 0 && sharedD.length === 0, 'U1 the snippet is true',
    `${all.length} public page(s) checked; ${missing.length} missing a title or description; ${sharedT.length} shared title(s), ${sharedD.length} shared description(s)`,
    missing.length ? `${missing.slice(0, 4).join(', ')} - a search result for these has nothing of the page's own in it`
      : `${sharedD.length} description(s) are repeated across pages, so the snippet does not say which page it is: "${(sharedD[0] || [''])[0].slice(0, 70)}"`);
}

// ── U2 · is there anyone to complain to? ─────────────────────────────────────────────────────────
{
  const src = read('index.html');
  const has = {
    about: /about (us|workhive)|who we are|our story|built by/i.test(src),
    contact: /contact|get in touch|email us|support@|hello@/i.test(src),
    terms: /terms of service|terms & conditions/i.test(src),
    privacy: /privacy policy/i.test(src),
  };
  const missing = Object.entries(has).filter(([, v]) => !v).map(([k]) => k);
  say(missing.length === 0, 'U2 trust pages exist',
    `the public surface carries: ${Object.entries(has).filter(([, v]) => v).map(([k]) => k).join(', ') || 'nothing'}`,
    `nothing on the public surface offers ${missing.join(', ')} - a tool with nobody to complain to is a tool nobody trusts with their plant`);
}

// ── U3 · does the feed show a living platform? ───────────────────────────────────────────────────
{
  const src = read('public-feed.html');
  // an empty feed is only honest if it SAYS it is empty rather than rendering a blank grid
  const saysEmpty = /no posts yet|nothing here yet|be the first|no activity/i.test(src);
  const rendersReal = /from\(['"](community_posts|public_posts|logbook)['"]\)|public_feed/i.test(src);
  // and a stranger must be able to judge it: a post needs an author, a time and a subject
  const attributed = /author|worker_name|posted|ago|created_at/i.test(src);
  say(rendersReal && attributed && saysEmpty, 'U3 the feed sells',
    `the feed reads real rows (${rendersReal}), attributes them (${attributed}), and says so when there is nothing (${saysEmpty})`,
    !rendersReal ? 'the public feed renders no real data - a stranger sees a mock-up of a platform nobody uses'
      : !attributed ? 'posts carry no author or time, so a stranger cannot tell whether this is a living platform or a seeded one'
      : 'an empty feed renders a blank area with no words, which reads as broken rather than new');
}

// ── U4 · is a dated claim current, or dated? ─────────────────────────────────────────────────────
{
  // the 92-page lesson: a stamp nobody regenerates is worse than no stamp
  const STAMP = /(updated|last reviewed|as of)\s*:?\s*(\d{4}-\d{2}-\d{2}|[A-Z][a-z]+ \d{1,2},? \d{4})/gi;
  const now = new Date('2026-09-07');
  const stale = [];
  let stamped = 0;
  for (const d of learn) {
    const src = read(`learn/${d}/index.html`);
    const hits = [...src.matchAll(STAMP)];
    if (!hits.length) continue;
    stamped++;
    const when = new Date(hits[0][2]);
    if (!isNaN(when) && (now - when) / 86400000 > 365) stale.push(`learn/${d} (${hits[0][2]})`);
  }
  say(stale.length === 0, 'U4 freshness governed',
    `${stamped} of ${learn.length} learn article(s) carry a date; ${stale.length} of those are over a year old`,
    `${stale.slice(0, 4).join(', ')} tell a reader they were reviewed over a year ago, which is a claim about currency that nobody has re-earned`);
}

// ── U5 · is a comparison fair enough to be believed? ─────────────────────────────────────────────
{
  // ★A LINK IS NOT A CLAIM. The first version matched "vs|versus" anywhere and caught an <a> pointing at
  // another article ("CMMS vs spreadsheet") and a table-of-contents entry ("Digital versus paper
  // handover") - neither is the page comparing anything. It then missed the real concessions because it
  // demanded "Excel is good" while the article says "where spreadsheets still win" and "a spreadsheet is
  // genuinely fine when one person maintains under ~50 assets". Both halves wrong, in opposite
  // directions: it found comparisons that were not there and could not see the fairness that was.
  // ★USE THE PROSE, NOT THE MARKUP. Three attempts to answer this from HTML failed the same way: a URL
  // is not an argument (href="/learn/cmms-vs-excel-spreadsheet-maintenance/" made a page look like it
  // was arguing against spreadsheets when it was LINKING to an article that does), and pair-removal of
  // `<a>…</a>` is unreliable across a large file - one unclosed anchor makes the non-greedy match span
  // to the wrong closer and leaves later link text standing. Every learn article ships an index.html.md
  // sibling that IS its prose, where a link is the unambiguous [text](url) and can be reduced to its
  // text in one pass. Reading the artifact that is actually prose beats parsing the one that is not.
  const bodyOf = (f, keepLinks = true) => {
    const md = f.endsWith('.html') ? f + '.md' : `${f}/index.html.md`;
    const src = read(md) || read(f.endsWith('.html') ? f : `${f}/index.html`);
    return src
      // ★A LINK LABEL IS A SIGNPOST, NOT AN ARGUMENT. The last survivor was the sentence "See CMMS vs
      // spreadsheet." - a cross-reference to a sibling article, whose LABEL happens to name a comparison
      // this page never makes. So the claim test drops link text entirely (what the page argues in its
      // own voice), while the concession test keeps it (words on the page a reader still reads).
      .replace(/\[([^\]]*)\]\([^)]*\)/g, keepLinks ? '$1' : ' ')
      .replace(/^\s*[-*]\s*\[[^\]]*\]\([^)]*\)\s*$/gm, ' ')  // a bare link in a list is navigation
      .replace(/<[^>]+>/g, ' ')
      .replace(/\s+/g, ' ');
  };
  const CLAIM = /(vs\.?|versus|compared to|instead of|rather than|better than)\s+(a |an |the |your )?(excel|spreadsheets?|cmms|paper|sap|maximo)/i;
  const CONCEDES = /(excel|spreadsheets?|paper|cmms)[^.]{0,40}(still win|genuinely fine|is fine|are fine|works? well|is good|are good|is enough|make sense)|nothing wrong with|if .{0,40}(excel|paper|spreadsheet) (works|is working)|do not need|don.t need a cmms/i;
  const comparing = [...PUBLIC, ...learn.map((d) => `learn/${d}`)].filter((f) => CLAIM.test(bodyOf(f, false)));
  const concedes = comparing.filter((f) => CONCEDES.test(bodyOf(f)));
  if (process.argv.includes('--show')) {
    for (const f of comparing) {
      const b = bodyOf(f, false); const m = b.match(CLAIM);
      console.log(`   [${concedes.includes(f) ? 'concedes' : 'DOES NOT'}] ${f} :: "${m ? b.slice(Math.max(0, b.indexOf(m[0]) - 60), b.indexOf(m[0]) + 80).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ') : '?'}"`);
    }
  }
  say(comparing.length === 0 || concedes.length === comparing.length, 'U5 comparisons fair',
    comparing.length ? `${comparing.length} page(s) argue against an alternative in their own prose, ${concedes.length} of them name where that alternative still wins` : 'no page argues against an alternative outside of link text',
    `${comparing.filter((f) => !concedes.includes(f)).slice(0, 3).join(', ')} argue against a tool the reader may rely on without conceding anything it does well - a reader who uses that tool stops believing the rest of the page`);
}

console.log(`${bad ? 'FAIL' : 'PASS'} public-trust - a search snippet describes its own page, there is somebody to complain to, the feed shows a living platform, dated claims are current, and a comparison concedes something`);
process.exitCode = bad ? 1 : 0;
