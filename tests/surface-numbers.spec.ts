/**
 * SURFACE NUMBERS — the half of `populated` that a generic probe can never settle
 * ==============================================================================
 *
 * The bank's `populated` oracle reads:
 *
 *     "the surface renders real rows and every visible number matches its source of truth"
 *
 * tools/walk_owed_scenarios.mjs proves the FIRST half — rows render, no raw enum, no NaN, no error
 * chrome — and says so in its own evidence, then explicitly refuses the second: it cannot know a
 * given surface's truth query. tools/merge_walk_results.py therefore refuses to bank those rows
 * green, and 119 of them sit stale for exactly that reason.
 *
 * This spec is the missing half. Each surface names the numbers it shows and the SQL that decides
 * them, and the two are compared. Nothing here is inferred from another part of the screen — a
 * number is checked against the database, which is the whole point ("assert against psql, not
 * against another part of the screen").
 *
 * NON-VACUITY: a check whose element is absent FAILS rather than skipping, and a truth query that
 * returns nothing FAILS. A comparison that never happened must never read as agreement.
 */
import { execFileSync } from 'node:child_process';
import { expect } from '@playwright/test';
import { test } from './_fixtures';

/** One number as psql sees it. Runs as postgres, so it reads the truth, not a role's view of it. */
function truth(sql: string): number {
  const out = execFileSync('docker', [
    'exec', '-i', 'supabase_db_workhive',
    'psql', '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql,
  ], { encoding: 'utf8', timeout: 60000 }).trim();
  const n = Number(out.split('\n')[0]);
  if (!Number.isFinite(n)) throw new Error(`truth query did not return a number: ${out.slice(0, 120)}`);
  return n;
}

type Check = { label: string; selector: string; sql: string };
type Surface = { name: string; url: string; checks: Check[] };

const PUBLISHED = "status = 'published'";

const SURFACES: Surface[] = [
  {
    name: 'market',
    url: '/workhive/marketplace.html',
    checks: [
      { label: 'parts tab count', selector: '#count-parts',
        sql: `select count(*) from marketplace_listings where ${PUBLISHED} and section='parts'` },
      { label: 'training tab count', selector: '#count-training',
        sql: `select count(*) from marketplace_listings where ${PUBLISHED} and section='training'` },
      { label: 'jobs tab count', selector: '#count-jobs',
        sql: `select count(*) from marketplace_listings where ${PUBLISHED} and section='jobs'` },
    ],
  },
  {
    // The seller's own dashboard. Its sources, read from the page rather than assumed:
    //   #ps-listings = `_listingsTotal || _listings.length`   -> his listings, every status
    //   #ps-sales    = `_seller?.total_sales || 0`            -> the sellers table's own column
    // Comparing #ps-sales to that column is the right test for THIS oracle ("matches its source of
    // truth"). Whether the column itself agrees with the completed sales is a different claim and
    // belongs to the BA-invariant family, not here.
    name: 'seller',
    url: '/workhive/marketplace-seller.html',
    checks: [
      { label: "the signed-in seller's listings", selector: '#ps-listings',
        sql: `select count(*) from marketplace_listings where seller_name = 'Pablo Aguilar'` },
      { label: "the seller's recorded sales", selector: '#ps-sales',
        sql: `select coalesce(max(total_sales), 0) from marketplace_sellers
                where worker_name = 'Pablo Aguilar'` },
    ],
  },
  {
    // The services surface. #count-services is PER-CALLER, not global: the page filters
    // `client_auth_uid === _authUid` and then counts the open statuses, so the truth query must be
    // scoped to the signed-in identity or it would compare a personal badge against a platform total.
    name: 'market_svc',
    url: '/workhive/marketplace.html?section=services',
    checks: [
      { label: "the signed-in person's open service requests", selector: '#count-services',
        sql: `select count(*) from service_requests
                where client_auth_uid = 'e2f921f2-024a-4fc3-8ea6-68b906d46040'
                  and status in ('requested','broadcasting','accepted','en_route','on_site','in_progress')` },
    ],
  },
  {
    // The moderation queue. Its source, read from the page: `setCount('mkt-listings-count',
    // (m.drafts || []).length)` where drafts is `.eq('status','draft').limit(50)` — so the truth is
    // the draft count CAPPED AT 50, and comparing against an uncapped count(*) would manufacture a
    // disagreement the moment a 51st draft exists.
    name: 'admin',
    url: '/workhive/platform-actions.html',
    checks: [
      { label: 'listings awaiting moderation', selector: '#mkt-listings-count',
        sql: `select least(count(*), 50) from marketplace_listings where status = 'draft'` },
    ],
  },
  {
    name: 'profile',
    url: '/workhive/marketplace-seller-profile.html?worker=Romeo%20Beltran',
    checks: [
      { label: "this seller's published listings", selector: '#listings-count',
        sql: `select count(*) from marketplace_listings
                where ${PUBLISHED} and seller_name = 'Romeo Beltran'` },
    ],
  },
];

for (const s of SURFACES) {
  test(`surface_numbers · ${s.name}: every visible number matches its source of truth`,
    async ({ whPage }) => {
      await whPage.goto(s.url);
      await whPage.waitForLoadState('networkidle').catch(() => {});
      await whPage.waitForTimeout(1500);   // counts arrive after the first paint

      const mismatches: string[] = [];
      const agreed: string[] = [];

      for (const c of s.checks) {
        const el = whPage.locator(c.selector).first();
        const present = await el.count();
        expect(present,
          `${s.name}: ${c.selector} (${c.label}) is not on the page — a number that is not there ` +
          `cannot be verified, and skipping it would read as agreement`).toBeGreaterThan(0);

        const raw = (await el.innerText()).trim();
        const shown = Number(raw.replace(/[^\d.-]/g, ''));
        const expected = truth(c.sql);

        // A dash is the page's honest "I could not read this" and is NOT a wrong number — but it is
        // also not a verified one, so it fails here rather than passing quietly.
        if (!Number.isFinite(shown)) {
          mismatches.push(`${c.label}: the surface shows "${raw}" (no number) while the database says ${expected}`);
          continue;
        }
        if (shown !== expected) {
          mismatches.push(`${c.label}: the surface shows ${shown}, the database says ${expected}`);
        } else {
          agreed.push(`${c.label}=${shown}`);
        }
      }

      expect(agreed.length + mismatches.length,
        `${s.name}: no number was compared at all`).toBeGreaterThan(0);
      expect(mismatches,
        `${s.name}: ${mismatches.length} of ${s.checks.length} numbers disagree with the database ` +
        `— ${mismatches.join(' · ')}. Agreed: ${agreed.join(', ') || 'none'}`).toEqual([]);
    });
}
