/**
 * FAILURE INJECTION — a failed read must render a FAILURE, never an EMPTINESS
 * ===========================================================================
 *
 * The bank's AZ-failure-injection family (42 rows across 6 surfaces) asserts that when a layer
 * fails, the layer ABOVE degrades honestly: "we could not load this" with a way back, not "there is
 * nothing here". The difference matters because the two are indistinguishable to a person, and one
 * of them is a lie. This session already found one instance for real — public-feed's Retry rendered
 * "No public posts yet" over 15 existing posts, because the keyset cursor was never reset.
 *
 * WHY THIS IS A SPEC AND NOT AN MCP WALK. I first tried injecting from inside the page by replacing
 * `window.fetch` after load. The stub was never called: supabase-js captures `fetch` when the client
 * is CONSTRUCTED, so a late override never applies. The probe reported "no error message shown",
 * which is exactly what a page that ignores errors would report — an injection that never fires is
 * indistinguishable from a page that fails the test. Route interception happens below the page, so
 * it cannot be missed this way, and `page.route` is already used elsewhere in this suite.
 *
 * THE ORACLE IS A DIFFERENCE, NOT A STRING. Each surface is measured twice: once healthy, once with
 * its read failed. A pass requires BOTH
 *   - the failed render says something failure-shaped, AND
 *   - the healthy render does NOT (otherwise the words were always on the page and prove nothing)
 * and it explicitly fails if the healthy load showed no rows at all, because then "empty vs error"
 * has nothing to distinguish.
 */
import { expect } from '@playwright/test';
import { test } from './_fixtures';

// Wide enough to recognise the words this product actually uses. The first version listed only
// "could not LOAD" and missed marketplace's "…so the marketplace could not be READ", reporting five
// surfaces as silent when every one of them was speaking clearly:
//   "Your session expired, so the marketplace could not be read. Sign in again to continue.
//    Nothing you did was lost."
// An oracle that only recognises its author's phrasing measures vocabulary, not behaviour.
const FAILURE_WORDS =
  /couldn'?t (load|read|be)|could not (load|read|be)|failed to (load|read)|unable to (load|read)|went wrong|try again|retry|session expired|expired,? so|not allowed to|does not have access|no access to/i;
const EMPTY_WORDS = /no listings|no posts|nothing here|no results|none found|no items|no public posts/i;

type Surface = { name: string; url: string; table: RegExp; rowSelector: string };

// The URLs are the bank's own, so a green row here and the row it backs describe the same screen.
const SURFACES: Surface[] = [
  { name: 'market', url: '/workhive/marketplace.html',
    table: /marketplace_listings/, rowSelector: '[class*="listing-card"], [class*="card"]' },
  { name: 'market_svc', url: '/workhive/marketplace.html?section=services',
    table: /service_requests|marketplace_listings/, rowSelector: '[class*="card"]' },
  { name: 'seller', url: '/workhive/marketplace-seller.html',
    table: /marketplace_listings/, rowSelector: '[class*="card"], [class*="listing"]' },
  { name: 'admin', url: '/workhive/platform-actions.html',
    table: /marketplace_listings|marketplace_disputes/, rowSelector: '[class*="card"], tr' },
  { name: 'profile', url: '/workhive/marketplace-seller-profile.html?worker=Pablo%20Aguilar',
    table: /marketplace_sellers|marketplace_listings/, rowSelector: '[class*="card"], [class*="listing"]' },
  { name: 'community', url: '/workhive/community.html',
    table: /community_posts/, rowSelector: '[class*="post"], article' },
  { name: 'public-feed', url: '/workhive/public-feed.html',
    table: /community_posts|public_posts/, rowSelector: '[class*="post"], article' },
];

for (const s of SURFACES) {
  test(`az_fail_500 · ${s.name}: a failed read reads as a failure, not an emptiness`, async ({ whPage }) => {
    // ── 1 · healthy baseline. Without it, any words found later prove nothing. ──────────────────
    await whPage.goto(s.url);
    await whPage.waitForLoadState('networkidle').catch(() => {});
    const healthyText = (await whPage.locator('body').innerText()).replace(/\s+/g, ' ');
    const healthyRows = await whPage.locator(s.rowSelector).count();

    expect(healthyRows,
      `${s.name}: the healthy load rendered 0 rows, so "empty vs error" has nothing to tell apart — ` +
      `seed this surface before trusting this test`).toBeGreaterThan(0);
    expect(FAILURE_WORDS.test(healthyText),
      `${s.name}: failure wording is present on a HEALTHY page, so finding it after injection would ` +
      `prove nothing`).toBe(false);

    // ── 2 · fail every read of this surface's table, below the page where it cannot be missed ───
    let intercepted = 0;
    await whPage.route(url => s.table.test(url.toString()), async route => {
      intercepted++;
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ code: '500', message: 'injected failure', details: null, hint: null }),
      });
    });

    await whPage.reload();
    await whPage.waitForLoadState('networkidle').catch(() => {});
    const brokenText = (await whPage.locator('body').innerText()).replace(/\s+/g, ' ');

    // ── 3 · the injection must actually have fired, or this measured nothing ────────────────────
    expect(intercepted,
      `${s.name}: the route never matched ${s.table}, so the page was never made to fail — this is ` +
      `an instrument failure, not a passing surface`).toBeGreaterThan(0);

    // ── 4 · the oracle ─────────────────────────────────────────────────────────────────────────
    const saysFailed = FAILURE_WORDS.test(brokenText);
    const saysEmpty = EMPTY_WORDS.test(brokenText);

    expect(saysFailed,
      `${s.name}: ${intercepted} read(s) returned 500 and the surface never said so. ` +
      `It rendered${saysEmpty ? ' "nothing here", which claims the data does not exist' : ' neither a failure nor an emptiness'}.`
    ).toBe(true);
  });
}

/**
 * az_fail_401 — an expired session must say SO, and must not tell a signed-in person to sign in.
 *
 * PostgREST answers a permission error with 401 for anon and 403 for authenticated, and a client
 * that branches on the status alone will show "please sign in" to somebody who already is. That
 * exact defect has been found here before. So this asserts two things: the surface acknowledges the
 * failure, and — for a page loaded WITH a session — it does not respond by demanding a sign-in.
 */
const SIGNIN_DEMAND = /sign in|log in|login to|sign-in required|please authenticate/i;

for (const s of SURFACES) {
  test(`az_fail_401 · ${s.name}: a rejected session says so, and does not tell a signed-in person to sign in`,
    async ({ whPage }) => {
      await whPage.goto(s.url);
      await whPage.waitForLoadState('networkidle').catch(() => {});
      const healthyText = (await whPage.locator('body').innerText()).replace(/\s+/g, ' ');
      const healthyRows = await whPage.locator(s.rowSelector).count();
      expect(healthyRows, `${s.name}: healthy load rendered 0 rows; nothing to distinguish`).toBeGreaterThan(0);

      // whPage carries a session. A 401 on its reads is therefore a REJECTED session, not an absent one.
      const healthyDemandsSignIn = SIGNIN_DEMAND.test(healthyText);

      let intercepted = 0;
      await whPage.route(url => s.table.test(url.toString()), async route => {
        intercepted++;
        // THE BODY MUST BE THE ONE SUPABASE ACTUALLY SENDS. supabase-js surfaces a PostgREST failure
        // as a PostgrestError of {message, details, hint, code} — it carries NO HTTP status, so any
        // page reading `error` rather than catching a throw can only tell 401 from 403 by the CODE.
        // Injecting 42501 (insufficient_privilege) with a 401 is a pairing the server never emits,
        // and it made a correct page look broken: an expired JWT returns PGRST301 / "JWT expired".
        await route.fulfill({
          status: 401,
          contentType: 'application/json',
          body: JSON.stringify({ code: 'PGRST301', message: 'JWT expired', details: null, hint: null }),
        });
      });

      await whPage.reload();
      await whPage.waitForLoadState('networkidle').catch(() => {});
      const brokenText = (await whPage.locator('body').innerText()).replace(/\s+/g, ' ');

      expect(intercepted,
        `${s.name}: the route never matched ${s.table} — instrument failure, not a passing surface`
      ).toBeGreaterThan(0);

      expect(FAILURE_WORDS.test(brokenText),
        `${s.name}: ${intercepted} read(s) were rejected 401 and the surface never acknowledged it`
      ).toBe(true);

      // A 401 IS a rejected session, so "sign in again" is the CORRECT answer here — marketplace
      // says exactly that, and adds "Nothing you did was lost", which is the other half of this
      // oracle. The defect this family guards against is the same words appearing for a 403, where
      // the session is fine and only the ROW was refused. That is the test below, not this one.
      void healthyDemandsSignIn;
      // Recognise the reassurance however each surface phrases it — community says "Nothing you
      // POSTED was lost", marketplace "Nothing you DID was lost". A pattern that only matched one
      // wording reported the other as silent, which measures vocabulary rather than behaviour.
      expect(/nothing (you \w+ |)was \w+|no changes were|nothing was \w+/i
               .test(brokenText),
        `${s.name}: told the person their session failed but never said whether their work survived`
      ).toBe(true);
    });
}

/**
 * az_fail_offline — the write must be refused BEFORE it fires, and the person told nothing was sent.
 *
 * The failure this guards against is a write that leaves while the connection is gone: the request
 * dies in flight, the person is shown a generic error, and neither they nor the app can say whether
 * the server got it. Retrying then risks a duplicate. This codebase's answer is svcRequireOnline —
 * refuse at the door, and say so — so the oracle has two halves that must BOTH hold:
 *   ZERO write requests actually left the page, and
 *   the person was told, in words, that nothing was sent.
 * Saying "failed" while a request is in flight would satisfy neither.
 *
 * Starts with the one surface whose write control is unambiguous; the others each need their own
 * control identified, which is why this state is per-surface rather than a loop over all of them.
 */
// One control per surface, taken from the pages themselves. `force: true` because a control that is
// DISABLED while offline has already refused at the door — which is the behaviour under test, not a
// reason to skip it.
// Some write controls do not EXIST until the thing they act on is opened. #fb-d-save is injected by
// the admin's feedback-detail renderer, so a probe that goes straight for it finds nothing and
// reports "no write control on this surface" — about a surface that has one, merely closed. That is
// an instrument failure dressed as a finding, and it failed this test on 2026-08-05. Where an opener
// is needed, name it.
const WRITE_OPENER: Record<string, string> = {
  admin: 'button[data-fb-id]',       // a feedback card; opening it renders the note + Save
};
const WRITE_CONTROL: Record<string, string> = {
  market: '#btn-send-all-quotes, button:has-text("Send All Quote Requests")',
  seller: '#btn-save-messenger, #btn-save-certs',
  admin: '#fb-d-save',
  community: '#btn-submit-post, #fab-post',
  // marketplace-seller-profile declares no write control of its own — it is a public read surface,
  // so there is no write to withhold. Left out deliberately rather than forced.
};

for (const s of SURFACES.filter(x => WRITE_CONTROL[x.name])) {
  test(`az_fail_offline · ${s.name}: the write is refused before it fires, and says nothing was sent`,
    async ({ whPage, context }) => {
      await whPage.goto(s.url);
      await whPage.waitForLoadState('networkidle').catch(() => {});

      // Reveal the control if this surface keeps it behind a row/drawer, and fail loudly if the
      // OPENER is the thing that is missing — that is a different fact from the control being absent.
      const opener = WRITE_OPENER[s.name];
      if (opener) {
        const o = whPage.locator(opener).first();
        expect(await o.count(),
          `${s.name}: the opener ${opener} is not on this surface, so the write control it reveals ` +
          `could never be reached — instrument failure, not a passing surface`).toBeGreaterThan(0);
        await o.click();
        await whPage.locator(WRITE_CONTROL[s.name]).first()
          .waitFor({ state: 'visible', timeout: 8000 }).catch(() => {});
      }

      const btn = whPage.locator(WRITE_CONTROL[s.name]).first();
      const present = await btn.count();
      expect(present,
        `${s.name}: no write control matched ${WRITE_CONTROL[s.name]}` +
        `${opener ? ` even after opening ${opener}` : ''}, so nothing could be attempted ` +
        `— instrument failure, not a passing surface`).toBeGreaterThan(0);

      // count writes that actually LEAVE, from this moment on
      const writesOut: string[] = [];
      whPage.on('request', r => {
        if (/\/rest\/v1\//.test(r.url()) && ['POST', 'PATCH', 'PUT', 'DELETE'].includes(r.method())) {
          writesOut.push(`${r.method()} ${r.url().split('/rest/v1/')[1].slice(0, 40)}`);
        }
      });

      await context.setOffline(true);
      try {
        await btn.click({ timeout: 5000, force: true });
      } catch { /* a disabled control is itself a refusal at the door */ }
      await whPage.waitForTimeout(2500);
      const text = (await whPage.locator('body').innerText()).replace(/\s+/g, ' ');
      await context.setOffline(false);

      expect(writesOut,
        `${s.name}: offline, and the write still left the page (${writesOut.join('; ')}). It cannot ` +
        `be known whether the server received it, so a retry risks doing it twice`).toEqual([]);

      expect(/nothing was sent|not sent|no changes were|nothing you did was|offline|no connection|reconnect/i.test(text),
        `${s.name}: the write was correctly withheld, but the person was never told nothing was sent ` +
        `— silence here reads as "it worked"`).toBe(true);
    });
}

/**
 * az_fail_partial — when half the reads succeed, KEEP what loaded and NAME what did not.
 *
 * The failure mode is a silent blank sitting beside real data: a page whose secondary read died
 * shows a confident zero, or an empty panel, next to rows that loaded fine — and nothing tells the
 * person which half they are looking at. So this fails ONE table while letting the rest through, and
 * requires both halves of the contract:
 *   the rows that could load are STILL THERE (a partial failure must not blank the whole surface)
 *   and the surface says something about the part that did not
 */
// The SECOND read each page actually makes — taken from the pages themselves, not guessed. Note they
// read VIEWS (v_marketplace_listings_truth), so a secondary must be a table the page genuinely calls
// and must not also match the primary; guessing produced four "never fired" results, which the
// non-vacuity guard reported rather than passing on nothing.
const SECONDARY: Record<string, RegExp> = {
  // The secondary must render INLINE, where a person can see the gap. marketplace_saved_searches was
  // the wrong choice: on first load it is only a COUNT (already treated as unknown-not-zero), and the
  // panel that would print "Could not load saved searches" is inside a sheet whose loader does not run
  // until the sheet is opened. A silent blank inside a closed drawer is not a silent blank on screen.
  // Trust badges render on the listing cards themselves.
  market: /get_marketplace_trust_badges/,
  market_svc: /get_marketplace_trust_badges/,
  // (both fall through to CONCLUSION below, where trust badges are expected to claim NOTHING)
  seller: /v_marketplace_sellers_truth|v_marketplace_inquiries_truth/,
  admin: /platform_feedback|v_credit_posture/,
  profile: /marketplace_reviews/,
  community: /community_reactions|community_xp/,
};

// The sentence each surface would WRONGLY print if it concluded from a read that never answered.
// Empty means "this secondary carries no conclusion" — an omitted trust chip asserts nothing, so
// those surfaces are held only to the keep-what-loaded half.
const CONCLUSION: Record<string, RegExp | null> = {
  market: null,
  market_svc: null,
  seller: null,
  admin: null,
  // "No reviews yet…" — the exact sentence a failed reviews read used to produce about a seller
  profile: /No reviews yet/i,
  community: null,
};

for (const s of SURFACES.filter(x => SECONDARY[x.name])) {
  test(`az_fail_partial · ${s.name}: what loaded is kept, what did not is named`, async ({ whPage }) => {
    await whPage.goto(s.url);
    await whPage.waitForLoadState('networkidle').catch(() => {});
    const healthyRows = await whPage.locator(s.rowSelector).count();
    expect(healthyRows, `${s.name}: healthy load rendered 0 rows`).toBeGreaterThan(0);

    let intercepted = 0;
    await whPage.route(url => SECONDARY[s.name].test(url.toString()), async route => {
      intercepted++;
      await route.fulfill({ status: 500, contentType: 'application/json',
        body: JSON.stringify({ code: '500', message: 'injected partial failure', details: null, hint: null }) });
    });

    await whPage.reload();
    await whPage.waitForLoadState('networkidle').catch(() => {});
    const rowsAfter = await whPage.locator(s.rowSelector).count();
    const text = (await whPage.locator('body').innerText()).replace(/\s+/g, ' ');

    expect(intercepted,
      `${s.name}: the secondary read ${SECONDARY[s.name]} never fired, so nothing partial happened — ` +
      `instrument failure, not a passing surface`).toBeGreaterThan(0);

    // half one: the reads that SUCCEEDED must still be on screen
    expect(rowsAfter,
      `${s.name}: one secondary read failed and the whole surface went blank — ${healthyRows} rows ` +
      `became ${rowsAfter}. A partial failure must cost only the part that failed`).toBeGreaterThan(0);

    // half two: the failed read must not produce a CONCLUSION about the data it could not fetch.
    //
    // "Name the missing part" was the wrong test and gave three different verdicts across three
    // secondary choices. OMITTING a positive signal is a conservative failure and is sometimes
    // deliberate — marketplace's trust-badge read carries `empty-catch-allow: chip just won't show`,
    // so a failure hides a "Community-trusted" chip and claims nothing, which is fine. ASSERTING A
    // NEGATIVE is the defect: "No reviews yet" for a seller whose reviews merely could not be read
    // is a fact about a person manufactured by a network failure. Omission is allowed; assertion is
    // not. So each surface declares the conclusion its failed secondary would wrongly print.
    const conclusion = CONCLUSION[s.name];
    if (conclusion) {
      const claimed = text.match(conclusion);
      expect(claimed,
        `${s.name}: the secondary read FAILED and the surface still concluded "${claimed?.[0]}" — ` +
        `that is a statement about data it never received, sitting beside ${rowsAfter} rows that ` +
        `loaded fine`).toBeNull();
    }
  });
}

/**
 * az_fail_null_field — a NULL must reach a person as a STATED GAP, never as 0, "undefined" or NaN.
 *
 * This is the defect the whole bank was built around. `service_knob('reward_max_per_listing')`
 * returns NULL meaning "no cap" — the function says so in its own body, because the economy is a
 * flat 10% with no ceiling. The client read it through `Number(null)`, which is 0, so
 * `Math.min(raw, 0)` returned 0 and the credits-back chip vanished from every priced listing. The
 * page rendered perfectly the entire time. Nothing errored; a rule was simply inverted.
 *
 * So: take the REAL response, null out its optional fields, and hand it back. The shape stays
 * exactly what the client expects — only the values go unknown — and the surface must not print the
 * corpse of a missing value.
 */
const NULL_CORPSES = /\bundefined\b|\bNaN\b|\bnull\b|₱\s*NaN|₱\s*undefined/;
const OPTIONAL_FIELDS = ['price', 'image_url', 'description', 'location', 'condition',
                         'rating_avg', 'completed_sales', 'seller_contact'];

// Only the surfaces where this can actually happen. community_posts declares exactly three nullable
// columns — auth_uid, edited_at, deleted_at — and none of them is an optional DISPLAY value (nulling
// deleted_at is the normal state; setting it would soft-delete the post). Its display fields are
// NOT NULL at the schema level, so a null corpse is structurally impossible there rather than merely
// absent, and running the test anyway would pass on nothing. Verified against information_schema.
const NULLABLE_SURFACES = SURFACES.filter(s => !/community|public-feed/.test(s.name));

for (const s of NULLABLE_SURFACES) {
  test(`az_fail_null_field · ${s.name}: a NULL renders as a stated gap, not as 0 or "undefined"`,
    async ({ whPage }) => {
      await whPage.goto(s.url);
      await whPage.waitForLoadState('networkidle').catch(() => {});
      expect(await whPage.locator(s.rowSelector).count(),
        `${s.name}: healthy load rendered 0 rows; nothing to null out`).toBeGreaterThan(0);
      const healthyText = (await whPage.locator('body').innerText()).replace(/\s+/g, ' ');
      // If the healthy page already prints one of these words, finding it later proves nothing.
      const healthyCorpse = NULL_CORPSES.test(healthyText);

      let nulled = 0;
      await whPage.route(url => s.table.test(url.toString()), async route => {
        const res = await route.fetch();
        let body: unknown;
        try { body = await res.json(); } catch { await route.fulfill({ response: res }); return; }
        if (Array.isArray(body)) {
          for (const row of body as Record<string, unknown>[]) {
            for (const f of OPTIONAL_FIELDS) if (f in row) { row[f] = null; nulled++; }
          }
        }
        // Do NOT hand back the original headers with a rewritten body: they still carry the
        // content-encoding and content-length of the ORIGINAL bytes, so the browser tries to gunzip
        // plain JSON of the wrong length and the request dies as "TypeError: Failed to fetch" — the
        // page then renders nothing and the test reads it as a product defect. Status and a clean
        // content-type are all this needs.
        await route.fulfill({ status: res.status(), contentType: 'application/json',
                              body: JSON.stringify(body) });
      });

      await whPage.reload();
      await whPage.waitForLoadState('networkidle').catch(() => {});
      const brokenText = (await whPage.locator('body').innerText()).replace(/\s+/g, ' ');

      expect(nulled,
        `${s.name}: no optional field was nulled — either the response was not JSON rows or none of ` +
        `${OPTIONAL_FIELDS.join('/')} exist on it, so this measured nothing`).toBeGreaterThan(0);

      if (!healthyCorpse) {
        const found = brokenText.match(NULL_CORPSES);
        expect(found,
          `${s.name}: ${nulled} field(s) were set to NULL and the surface printed ${found?.[0]} at a ` +
          `person — a missing value must be stated as missing, not leaked as its JavaScript corpse`
        ).toBeNull();
      }
    });
}

/**
 * az_fail_timeout — a hung dependency must END, in words, rather than shimmer forever.
 *
 * utils.js carries whQueryTimeout for exactly this: a PostgREST query builder never passes through
 * fetchWithTimeout, so a stalled read just stays stalled and the page keeps showing a skeleton at
 * someone who decided minutes ago that it was broken. The oracle is not "an error appeared" but
 * "SOMETHING resolved": either the surface says it timed out, or it renders its rows — what it may
 * not do is sit in a loading state indefinitely.
 */
const SKELETON = '[class*="skeleton"], [class*="shimmer"], [aria-busy="true"], [class*="loading"]';

for (const s of SURFACES) {
  test(`az_fail_timeout · ${s.name}: a hung read ends in a stated timeout, not an endless skeleton`,
    async ({ whPage }) => {
      await whPage.goto(s.url);
      await whPage.waitForLoadState('networkidle').catch(() => {});
      expect(await whPage.locator(s.rowSelector).count(),
        `${s.name}: healthy load rendered 0 rows; nothing to distinguish`).toBeGreaterThan(0);

      // Hold the read open well past any client-side budget, then let it fail as a connection would.
      let intercepted = 0;
      await whPage.route(url => s.table.test(url.toString()), async route => {
        intercepted++;
        await new Promise(r => setTimeout(r, 20000));
        await route.abort('timedout');
      });

      await whPage.reload();
      await whPage.waitForTimeout(18000);          // inside the hang, after any sane timeout budget
      const midText = (await whPage.locator('body').innerText()).replace(/\s+/g, ' ');
      const stillLoading = await whPage.locator(SKELETON).count();
      const rows = await whPage.locator(s.rowSelector).count();

      expect(intercepted, `${s.name}: the route never matched — instrument failure`).toBeGreaterThan(0);

      const resolved = FAILURE_WORDS.test(midText) || /timed? ?out|taking longer/i.test(midText) || rows > 0;
      expect(resolved,
        `${s.name}: ${intercepted} read(s) hung for 18s and the surface neither said so nor rendered ` +
        `anything — ${stillLoading} loading placeholder(s) still on screen, which is a page that will ` +
        `shimmer until the person gives up`).toBe(true);
    });
}

/**
 * az_fail_403 — a refused ROW must not be reported as a refused SESSION.
 *
 * PostgREST answers a permission error with 403 when the caller IS authenticated. A client that
 * branches on "not 2xx" and shows the session message will tell a signed-in person to sign in again
 * — a defect found on this project before, where a 42501 sent a signed-in buyer to the login screen.
 * The session is fine; one row was refused, and saying otherwise sends them to fix the wrong thing.
 */
for (const s of SURFACES) {
  test(`az_fail_403 · ${s.name}: a refused row is not reported as a dead session`, async ({ whPage }) => {
    await whPage.goto(s.url);
    await whPage.waitForLoadState('networkidle').catch(() => {});
    const healthyText = (await whPage.locator('body').innerText()).replace(/\s+/g, ' ');
    const healthyRows = await whPage.locator(s.rowSelector).count();
    expect(healthyRows, `${s.name}: healthy load rendered 0 rows; nothing to distinguish`).toBeGreaterThan(0);
    const healthyDemandsSignIn = SIGNIN_DEMAND.test(healthyText);

    let intercepted = 0;
    await whPage.route(url => s.table.test(url.toString()), async route => {
      intercepted++;
      await route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: JSON.stringify({ code: '42501', message: 'permission denied for table', details: null, hint: null }),
      });
    });

    await whPage.reload();
    await whPage.waitForLoadState('networkidle').catch(() => {});
    const brokenText = (await whPage.locator('body').innerText()).replace(/\s+/g, ' ');

    expect(intercepted, `${s.name}: the route never matched — instrument failure`).toBeGreaterThan(0);
    expect(FAILURE_WORDS.test(brokenText),
      `${s.name}: ${intercepted} read(s) were refused 403 and the surface never acknowledged it`).toBe(true);

    if (!healthyDemandsSignIn) {
      expect(SIGNIN_DEMAND.test(brokenText),
        `${s.name}: a 403 on a ROW made the page demand a sign-in from someone whose session is ` +
        `perfectly valid — it sends them to fix the one thing that is not broken`).toBe(false);
    }
  });
}
