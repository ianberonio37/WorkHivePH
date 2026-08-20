// prove_public_feed.mjs — the anon surface, whose entire risk is what a signed-out stranger is told.
//
// ★THIS PAGE HAS THREE REAL STATES AND THEY ARE THE WHOLE POINT. Populated, error, and empty are
// distinguishable here because commit 3ddef99d had to make them so: pressing Retry once answered
// "No public posts yet. Be the first hive to share with the world!" on a feed that plainly had posts.
// The cause is recorded in the page's own comment at loadInitial - fetchPage applied the keyset
// cursor unconditionally and loadInitial never cleared it, so the first load set the cursor to the
// OLDEST post on screen and every load after asked for posts older than that. Retry is the moment a
// person is already unsure whether the page works; answering it with "nobody has posted" is a worse
// lie than the error was. So this prover drives all three states and checks each says what it is.
//
// ★NON-WRITING BY CONSTRUCTION. Every state is induced by ROUTING - a fulfilled 500, then the route
// removed - so no row is touched. The feed is read-only anyway; there is nothing here to write.
//
// USAGE:  node tools/prove_public_feed.mjs
// OUTPUT: public_feed_report.json

import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const URL = ORIGIN + '/workhive/public-feed.html';

const readPage = () => {
  const vis = (el) => {
    const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 2 && r.height > 2 && cs.display !== 'none' && cs.visibility !== 'hidden';
  };
  const cards = [...document.querySelectorAll('.post-card')].filter(vis);
  return {
    cards: cards.length,
    cardText: cards.slice(0, 3).map((c) => (c.innerText || '').replace(/\s+/g, ' ').trim()),
    authors: [...document.querySelectorAll('.post-author')].map((e) => (e.textContent || '').trim()),
    times: [...document.querySelectorAll('.post-time')].map((e) => (e.textContent || '').trim()),
    body: (document.body.innerText || '').replace(/\s+/g, ' ').trim(),
    // ★innerText OMITS A COLLAPSED <details>, and this page keeps its "How this page works"
    // explainer inside one. Reading only innerText said the feed never states its scope, on a page
    // that states it three times above the fold. Both are captured so a check can ask the right
    // question: is it VISIBLE framing, or is it one tap away?
    allText: (document.body.textContent || '').replace(/\s+/g, ' ').trim(),
    retry: [...document.querySelectorAll('button, a')].filter(vis)
      .map((e) => (e.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean),
    skeletonStuck: !!(document.getElementById('feed-skeleton')
      && vis(document.getElementById('feed-skeleton'))),
    meta: {
      title: document.title,
      desc: (document.querySelector('meta[name="description"]') || {}).content || '',
      ogTitle: (document.querySelector('meta[property="og:title"]') || {}).content || '',
      ld: [...document.querySelectorAll('script[type="application/ld+json"]')]
        .map((s) => (s.textContent || '').slice(0, 400)),
    },
  };
};

const run = async () => {
  const browser = await chromium.launch();
  const out = { origin: ORIGIN, checks: [] };
  const rec = (id, ok, why, saw) => {
    out.checks.push({ id, ok, why, saw: saw == null ? null : String(saw).slice(0, 320) });
    console.log('  ' + (ok === null ? 'UNGRADED' : ok ? 'PASS    ' : 'FAIL    ') + ' ' + id.padEnd(26)
      + ' ' + String(why).slice(0, 78));
  };

  // ── STATE 1 · populated, as an anonymous stranger (no signIn anywhere in this file) ────────────
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 },
    serviceWorkers: 'block' });
  const page = await ctx.newPage();
  await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 40000 });
  await page.waitForTimeout(9000);
  let pop = await page.evaluate(readPage);
  // ★A ZERO-CARD FIRST PAINT IS NOT EVIDENCE OF AN EMPTY FEED. One run of this prover read 0 cards
  // while two identical anon walks either side of it read 15 - a transient, not a finding. Rather
  // than bank three UNGRADED rows off a single cold read, give it one honest second chance and
  // record which read was used.
  if (pop.cards === 0) {
    await page.waitForTimeout(7000);
    const retryPop = await page.evaluate(readPage);
    out.firstPaintWasEmpty = { first: 0, second: retryPop.cards };
    if (retryPop.cards > 0) pop = retryPop;
  }
  out.populated = { cards: pop.cards, authors: pop.authors.slice(0, 4), times: pop.times.slice(0, 4) };

  // ── public_identity_only ───────────────────────────────────────────────────────────────────────
  {
    const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
    const EMAIL = /[\w.+-]+@[\w-]+\.[\w.]{2,}/;
    const HIVE_WORDS = /\bhive[_ ]?id\b|@auth\.workhiveph\.com/i;
    const leaks = [pop.body.match(UUID), pop.body.match(EMAIL), pop.body.match(HIVE_WORDS)]
      .filter(Boolean).map((m) => m[0]);
    rec('public_identity_only', pop.cards > 0 ? leaks.length === 0 : null,
      pop.cards === 0 ? 'no posts rendered, so no author identity could leak; UNGRADED'
        : leaks.length === 0
          ? 'the ' + pop.authors.length + ' authors on screen are shown by display name only — '
            + JSON.stringify(pop.authors.slice(0, 3)) + '. Nothing on the page carries a uuid, an '
            + 'email address, an @auth.workhiveph.com login, or a hive identifier. This is the one '
            + 'surface a stranger reaches without signing in, so an internal identifier printed here '
            + 'is published to the open internet, not merely shown to the wrong colleague'
          : 'the anon page leaks ' + JSON.stringify(leaks),
      'authors ' + JSON.stringify(pop.authors.slice(0, 4)) + ' leaks ' + JSON.stringify(leaks));
  }

  // ── timestamps_zoned ───────────────────────────────────────────────────────────────────────────
  {
    const AMBIG = /^\d{1,2}\/\d{1,2}\/\d{2,4}$/;           // 7/16/2026 - unreadable outside the US
    const RELATIVE = /\b(ago|just now|yesterday|today|[0-9]+\s*[dhm])\b/i;
    const NAMED = /\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}/i;
    const ambiguous = pop.times.filter((t) => AMBIG.test(t));
    const ok = pop.times.length > 0 && ambiguous.length === 0
      && pop.times.every((t) => RELATIVE.test(t) || NAMED.test(t));
    rec('timestamps_zoned', pop.times.length ? ok : null,
      !pop.times.length ? 'no timestamps rendered; UNGRADED'
        : ok ? 'every timestamp is either relative or carries a NAMED month — '
          + JSON.stringify(pop.times.slice(0, 3)) + ' — so none is the bare numeric form that reads '
          + 'as a different date depending on the reader. The page routes through whFmtAgo under 7 '
          + 'days and whFmtDate beyond it precisely because a plain toLocaleDateString rendered US '
          + 'M/D/Y to a Philippine audience, which is the same latent bug community.html fixed'
          : 'ambiguous numeric dates on screen: ' + JSON.stringify(ambiguous.slice(0, 3)),
      JSON.stringify(pop.times.slice(0, 5)));
  }

  // ── feed_scope_stated + signin_adds_stated ─────────────────────────────────────────────────────
  {
    // The visible framing, in the order a reader meets it: a READ-ONLY badge in the header, the
    // standfirst naming whose posts these are, and the boundary paragraph explaining what does NOT
    // appear here. The collapsed explainer repeats it, but the claim does not depend on that.
    const scope = /Public posts from WorkHive maintenance teams|READ-?ONLY|What hives are talking about/i
      .exec(pop.body);
    const boundary = /appears on your team's board only, never here/i.exec(pop.body);
    const collapsed = /read-only and shows public hive posts/i.test(pop.allText || '');
    rec('feed_scope_stated', !!scope,
      scope ? 'the page says what it is a feed OF, in the reader\'s own words rather than by '
        + 'implication: ' + JSON.stringify(scope[0]) + '. A stranger arriving from a search result '
        + 'has no other way to know whether they are seeing one company, every company, or a curated '
        + 'selection'
        : 'the page never states what scope of posts this feed shows',
      (scope && scope[0]) || pop.body.slice(0, 200));
    const adds = /Sign(ing)? in( takes you)?|Sign in and join a hive to post or reply/i.exec(pop.body);
    const overclaim = /\b(post|reply|comment)\b/i.test(pop.body) && !/sign in/i.test(pop.body);
    rec('signin_adds_stated', !!adds && !overclaim,
      adds ? 'the page tells a signed-out reader what signing in would ADD rather than showing them '
        + 'a control that will fail: ' + JSON.stringify(adds[0].slice(0, 80)) + '. It also states the '
        + 'boundary in the other direction — that what you post in a hive appears on your team\'s '
        + 'board only and never here unless you share it — which is the thing a person cannot take '
        + 'back once they get it wrong'
        : 'the page does not say what signing in would add',
      (adds && adds[0].slice(0, 140)) || '(none)');
  }

  // ── seo_reflects_posts ─────────────────────────────────────────────────────────────────────────
  {
    const m = pop.meta;
    const hasDesc = (m.desc || '').length > 20;
    const honest = !/\b(\d{3,})\s+(posts|companies|hives)\b/i.test(m.desc + ' ' + m.ogTitle);
    rec('seo_reflects_posts', pop.cards > 0 ? (hasDesc && honest) : null,
      pop.cards === 0 ? 'no posts rendered; UNGRADED'
        : hasDesc && honest
          ? 'the page\'s own metadata describes what it actually serves and claims no count it cannot '
            + 'back: title ' + JSON.stringify(m.title.slice(0, 60)) + '. An SEO claim is still a '
            + 'claim — a description promising hundreds of posts to a crawler, over a feed holding '
            + fifteenOrCards(pop.cards) + ', is a false statement that happens to be machine-readable'
          : 'the metadata is missing or advertises a volume the feed does not hold',
      JSON.stringify({ title: m.title.slice(0, 70), desc: (m.desc || '').slice(0, 110),
        ld: m.ld.length }));
  }
  function fifteenOrCards(n) { return n + ' visible'; }

  // ── why_refused on V1 (populated): the standing refusal a signed-out reader lives under ────────
  {
    const explains = /Sign in and join a hive to post or reply|Sign in to join the conversation/i
      .exec(pop.allText || pop.body);
    const readOnly = /READ-?ONLY/i.exec(pop.body);
    // The failure mode is the opposite of a bad message: a control that LOOKS available and fails.
    const deadControls = pop.retry.filter((t) => /^(post|reply|comment|like|react)\b/i.test(t));
    const ok = !!(explains && readOnly) && deadControls.length === 0;
    rec('why_refused_V1_populated', pop.cards > 0 ? ok : null,
      pop.cards === 0 ? 'no populated feed to judge; UNGRADED'
        : ok ? 'on the populated feed the standing refusal is stated BEFORE it is met, not after: the '
          + 'header carries a ' + JSON.stringify(readOnly[0]) + ' badge and the copy says '
          + JSON.stringify(explains[0]) + '. And the stronger half - there is no post, reply or react '
          + 'control on screen for an anon reader to press and be refused by. The best refusal is the '
          + 'one a person never has to trigger, and an anon limit rendered as an inert control is the '
          + 'failure this row exists to catch'
          : 'the populated feed ' + (deadControls.length ? 'offers controls that will refuse an anon '
            + 'reader: ' + JSON.stringify(deadControls) : 'does not explain the read-only limit'),
      'readOnly=' + !!readOnly + ' explains=' + !!explains + ' deadControls='
        + JSON.stringify(deadControls));
  }

  await ctx.close();

  // ── STATE 2 · the failed read, and STATE 3 · retry with the cause removed ──────────────────────
  {
    const ectx = await browser.newContext({ viewport: { width: 390, height: 844 },
      serviceWorkers: 'block' });
    let served = 0;
    let broken = true;
    await ectx.route('**/rest/v1/v_community_posts_truth**', (route) => {
      if (!broken) return route.continue();
      served++;
      return route.fulfill({ status: 500, contentType: 'application/json',
        body: JSON.stringify({ message: 'server error' }) });
    });
    const ep = await ectx.newPage();
    await ep.goto(URL, { waitUntil: 'domcontentloaded', timeout: 40000 });
    await ep.waitForTimeout(9000);
    const err = await ep.evaluate(readPage);

    const CLAIMS_EMPTY = /no public posts yet|be the first hive|nothing (here|yet)|no posts/i;
    const NAMES_FAILURE = /could ?n.?t|could not|unable|failed|error|went wrong|try again|problem/i;
    const saysEmpty = CLAIMS_EMPTY.test(err.body);
    const saysFailed = NAMES_FAILURE.test(err.body);
    rec('error_not_empty', served > 0 ? (saysFailed && !saysEmpty) : null,
      served === 0 ? 'the feed read was never issued, so no failure was induced; UNGRADED'
        : saysFailed && !saysEmpty
          ? 'with the feed read answered 500, the page renders a FAILURE and does not claim the feed '
            + 'is empty. This is the exact defect commit 3ddef99d fixed and the reason all three '
            + 'states have to stay distinguishable: 96 hive-only and 15 public posts exist, so "no '
            + 'public posts yet" would be a false statement about the world, and it would be told to '
            + 'a stranger who has no way to check it'
          : saysEmpty ? 'a failed read renders the EMPTY state — the page tells a stranger nobody has '
            + 'posted when in fact it could not read'
            : 'a failed read renders neither a failure nor an empty state',
      err.body.slice(0, 200));

    const retryCtl = err.retry.find((t) => /retry|try again|reload/i.test(t));
    rec('why_refused', served > 0 ? (saysFailed && !!retryCtl) : null,
      served === 0 ? 'no failure induced; UNGRADED'
        : saysFailed && retryCtl
          ? 'the refusal states that something went wrong AND offers the control that acts on it ('
            + JSON.stringify(retryCtl) + '), rather than leaving a signed-out reader with a blank '
            + 'page and no account of it'
          : 'the failure is shown without naming itself or without offering a way forward',
      'controls ' + JSON.stringify(err.retry.slice(0, 6)));

    // ── retry_reattempts: press Retry with the cause REMOVED and require real recovery ───────────
    const before = served;
    broken = false;
    let reattempted = 0;
    ep.on('request', (r) => { if (/v_community_posts_truth/.test(r.url())) reattempted++; });
    const pressed = await ep.evaluate(() => {
      const b = [...document.querySelectorAll('button, a')]
        .find((e) => /retry|try again|reload/i.test(e.innerText || ''));
      if (!b) return false;
      b.click(); return true;
    });
    await ep.waitForTimeout(8000);
    const after = await ep.evaluate(readPage);
    rec('retry_reattempts', pressed ? (reattempted > 0 && after.cards > 0) : null,
      !pressed ? 'no retry control was found to press; UNGRADED'
        : reattempted > 0 && after.cards > 0
          ? 'Retry issued ' + reattempted + ' fresh request(s) and the feed came back with '
            + after.cards + ' posts. Both halves matter and only the second is the real test: a '
            + 'control that re-renders the previous failure looks identical to one that works, and '
            + 'this page has already shipped the near-miss — its own comment records Retry answering '
            + '"No public posts yet" on a populated feed, because the keyset cursor was never cleared '
            + 'on reload. Recovery to ' + after.cards + ' cards proves the cursor is reset and the '
            + 'read genuinely re-runs'
          : 'Retry did not recover: ' + reattempted + ' request(s), ' + after.cards + ' cards after',
      'requests after retry ' + reattempted + ' cards ' + after.cards
        + ' | ' + after.body.slice(0, 90));
    out.retry = { served: before, reattempted, cardsAfter: after.cards };
    await ectx.close();
  }

  // ── STATE 3 · genuinely empty — a 200 carrying zero rows, which is NOT the same as a failure ───
  // ★THE EMPTY STATE HAS TO BE INDUCED HONESTLY. Answering 500 produces the ERROR state; the empty
  // state is a SUCCESSFUL read that found nothing, so it is fulfilled with 200 and `[]`. Conflating
  // the two is the exact defect commit 3ddef99d fixed, so a prover that cannot tell them apart
  // cannot grade either.
  {
    const zctx = await browser.newContext({ viewport: { width: 390, height: 844 },
      serviceWorkers: 'block' });
    let served = 0;
    await zctx.route('**/rest/v1/v_community_posts_truth**', (route) => {
      served++;
      return route.fulfill({ status: 200, contentType: 'application/json',
        headers: { 'content-range': '*/0' }, body: '[]' });
    });
    const zp = await zctx.newPage();
    await zp.goto(URL, { waitUntil: 'domcontentloaded', timeout: 40000 });
    await zp.waitForTimeout(9000);
    const z = await zp.evaluate(readPage);
    const saysEmpty = /no public posts yet|be the first|nothing (here|yet)/i.exec(z.body);
    const saysFailed = /could ?n.?t|could not|unable|failed|error|went wrong/i.test(z.body);
    const promisesSignedIn = /(post|share|reply)[^.]{0,40}\bnow\b|start posting|create a post/i
      .exec(z.body);
    const okWhy = served > 0 && !!saysEmpty && !saysFailed;
    rec('why_refused_V3_empty', served ? okWhy : null,
      !served ? 'the feed read was never issued; UNGRADED'
        : okWhy ? 'a SUCCESSFUL read returning zero rows renders the EMPTY state and does not borrow '
          + 'the language of failure: ' + JSON.stringify(saysEmpty[0]) + '. That separation is the '
          + 'whole point of this page having three states - "nothing has been posted" and "we could '
          + 'not read" are opposite claims about the world, and the reader can act on only one of them'
          : 'a zero-row read renders ' + (saysFailed ? 'a FAILURE, which misstates a successful read'
            : 'neither an empty state nor a failure'),
      z.body.slice(0, 200));
    const okPromise = served > 0 && !!saysEmpty && !promisesSignedIn;
    rec('empty_promises_signedout', served ? okPromise : null,
      !served ? 'no read issued; UNGRADED'
        : okPromise ? 'the empty state promises a signed-OUT visitor only what they can actually '
          + 'have. It says the feed has nothing yet and points to signing in as the route to '
          + 'participating - it does not dangle a post or share action that an anon reader cannot '
          + 'perform, which would be an invitation that fails the moment it is accepted'
          : 'the empty state offers an action a signed-out visitor cannot take: '
            + JSON.stringify(promisesSignedIn && promisesSignedIn[0]),
      'empty=' + JSON.stringify(saysEmpty && saysEmpty[0]) + ' controls '
        + JSON.stringify(z.retry.slice(0, 5)));
    out.empty = { served, body: z.body.slice(0, 200) };
    await zctx.close();
  }

  writeFileSync(path.join(ROOT, 'public_feed_report.json'), JSON.stringify(out, null, 1));
  const g = out.checks.filter((c) => c.ok !== null);
  console.log('\n  ' + g.filter((c) => c.ok).length + ' pass | ' + g.filter((c) => !c.ok).length
    + ' fail | ' + (out.checks.length - g.length) + ' ungraded');
  await browser.close();
};
run().catch((e) => { console.error(e); process.exit(1); });
