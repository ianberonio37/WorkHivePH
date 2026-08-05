/**
 * BC-ufai-F · THE EFFECT, ASSERTED AGAINST THE DATABASE — AND THE SAME FACT ON TWO SURFACES
 * ═══════════════════════════════════════════════════════════════════════════════════════════════
 *
 * These four claims are the ones a structural probe is forbidden to settle (gate rule R6), because
 * every one of them is about a VALUE or an EFFECT rather than a rendering:
 *
 *   effect_in_db            the happy path's effect is present in the database
 *   effect_visible          that same effect is visible to the person who caused it
 *   idempotent_repeat       repeating the action changes nothing further
 *   cross_surface_agreement the same fact reads the same on every surface that shows it
 *
 * So nothing here is inferred from the screen alone. The effect is read back with psql as postgres,
 * which is the only reader that cannot be fooled by the page's own cache.
 *
 * THIS FILE WRITES TO THE SHARED DATABASE, and therefore restores what it changed. The restore runs
 * in `finally`, and the value it restores to is captured from psql BEFORE the test touches anything —
 * not from the page, which may itself be showing a stale copy.
 */
import { execFileSync } from 'node:child_process';
import { expect } from '@playwright/test';
import { test } from './_fixtures';

const SELLER = 'Pablo Aguilar';

function psql(sql: string): string {
  return execFileSync('docker', [
    'exec', '-i', 'supabase_db_workhive',
    'psql', '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql,
  ], { encoding: 'utf8', timeout: 60000 }).trim();
}

const SELLER_URL = '/workhive/marketplace-seller.html';
const PROFILE_URL = `/workhive/marketplace-seller-profile.html?worker=${encodeURIComponent(SELLER)}`;

/** What the database says this seller's handle is, right now. */
const readHandle = () =>
  psql(`select coalesce(messenger_username,'') from marketplace_sellers
         where worker_name = '${SELLER}'`).split('\n')[0] ?? '';

const restoreHandle = (v: string) =>
  psql(v
    ? `update marketplace_sellers set messenger_username = '${v.replace(/'/g, "''")}'
        where worker_name = '${SELLER}'`
    : `update marketplace_sellers set messenger_username = null where worker_name = '${SELLER}'`);

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// effect_in_db + effect_visible — one journey, because the second claim is about the first's result
// ═══════════════════════════════════════════════════════════════════════════════════════════════
test('bc_effect_in_db + effect_visible · seller: the save lands in the database and comes back to the person who made it',
  async ({ whPage }) => {
    const before = readHandle();
    const typed = `wh.probe.${Date.now().toString().slice(-8)}`;
    try {
      await whPage.goto(SELLER_URL);
      await whPage.waitForLoadState('networkidle').catch(() => {});
      await whPage.waitForTimeout(1500);

      const field = whPage.locator('#messenger-input').first();
      const save = whPage.locator('#btn-save-messenger').first();
      expect(await field.count(),
        'the messenger field is not on the seller surface, so no effect can be produced').toBeGreaterThan(0);

      await field.fill(typed);
      await save.click();
      // The button reports its own completion; waiting on the DB instead would race the request.
      await whPage.waitForTimeout(3000);

      // ── effect_in_db ── read the effect from the server, not from the page that claims it
      const stored = readHandle();
      expect(stored,
        `the seller saved "${typed}" and the database holds "${stored}". The screen may have said ` +
        `"Saved" either way — this is the only reader that can tell`).toBe(typed);

      // ── effect_visible ── a fresh load, so nothing in memory can supply the answer
      await whPage.goto(SELLER_URL);
      await whPage.waitForLoadState('networkidle').catch(() => {});
      await whPage.waitForTimeout(2000);
      const shown = await whPage.locator('#messenger-input').first().inputValue();
      expect(shown,
        `the database holds "${typed}" but a fresh load of the seller's own surface shows "${shown}" ` +
        `— the effect landed and the person who caused it cannot see it`).toBe(typed);
    } finally {
      restoreHandle(before);
    }
  });

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// idempotent_repeat — repeating the action changes nothing further
// ═══════════════════════════════════════════════════════════════════════════════════════════════
test('bc_idempotent_repeat · seller: saving the same value twice writes once',
  async ({ whPage }) => {
    const before = readHandle();
    const typed = `wh.probe.${Date.now().toString().slice(-8)}`;
    try {
      await whPage.goto(SELLER_URL);
      await whPage.waitForLoadState('networkidle').catch(() => {});
      await whPage.waitForTimeout(1500);

      await whPage.locator('#messenger-input').first().fill(typed);
      await whPage.locator('#btn-save-messenger').first().click();
      await whPage.waitForTimeout(3000);
      expect(readHandle(), 'the first save did not land, so a repeat cannot be judged').toBe(typed);

      // Everything the SECOND press sends. One logical action here legitimately performs more than
      // one write (the row, then the audit entry), so the oracle is not "at most one request" — it is
      // that pressing again with an unchanged value sends NOTHING, because there is nothing to say.
      const secondPress: string[] = [];
      whPage.on('request', r => {
        if (['POST', 'PATCH', 'PUT', 'DELETE'].includes(r.method())) secondPress.push(`${r.method()} ${r.url().slice(0, 80)}`);
      });

      await whPage.locator('#btn-save-messenger').first().click();
      await whPage.waitForTimeout(3000);

      expect(secondPress,
        `pressing Save again with the value unchanged sent ${secondPress.length} write(s). The row ` +
        `would be identical, but the audit trail then records an edit that never happened — and ` +
        `"edited" is a claim about a person's actions: ${JSON.stringify(secondPress.slice(0, 3))}`)
        .toEqual([]);

      expect(readHandle(),
        'the second press changed the stored value although nothing was retyped').toBe(typed);
    } finally {
      restoreHandle(before);
    }
  });

// ═══════════════════════════════════════════════════════════════════════════════════════════════
// cross_surface_agreement — one listing, two surfaces, one set of facts
// ═══════════════════════════════════════════════════════════════════════════════════════════════
// Read-only, and deliberately about a listing rather than about a count: a count can agree by
// coincidence, but a title and a price agreeing on two independently-written renderers is the claim.
test('bc_cross_surface_agreement · market vs profile: the same listing reads the same on both',
  async ({ whPage }) => {
    const row = psql(`select title || '||' || price::text from marketplace_listings
                       where status = 'published' and seller_name = '${SELLER}'
                       order by created_at limit 1`).split('\n')[0] || '';
    expect(row,
      `${SELLER} has no published listing, so there is no object for two surfaces to agree about ` +
      `— seed one before trusting this test`).not.toBe('');
    const [title, price] = row.split('||');
    const pesos = Math.round(Number(price)).toLocaleString('en-US');

    const seen: Record<string, { title: boolean; price: boolean; text: string }> = {};
    for (const [name, url] of [['market', '/workhive/marketplace.html'], ['profile', PROFILE_URL]] as const) {
      await whPage.goto(url);
      await whPage.waitForLoadState('networkidle').catch(() => {});
      await whPage.waitForTimeout(2500);
      // The market paginates; find the listing rather than assuming it is above the fold.
      await whPage.evaluate((t) => {
        const el = [...document.querySelectorAll('*')].find(e => (e.textContent || '').includes(t));
        el?.scrollIntoView({ block: 'center' });
      }, title).catch(() => {});
      await whPage.waitForTimeout(600);
      const text = (await whPage.locator('body').innerText()).replace(/\s+/g, ' ');
      seen[name] = {
        title: text.includes(title),
        // Either grouped or plain — the two surfaces are allowed to format differently; what they
        // may not do is show different money.
        price: text.includes(pesos) || text.includes(String(Math.round(Number(price)))),
        text: text.slice(0, 160),
      };
    }

    expect(seen.market.title && seen.profile.title,
      `"${title}" is published, and it appears on market=${seen.market.title}, ` +
      `profile=${seen.profile.title}. A listing that exists on one surface and not the other is two ` +
      `answers to one question`).toBe(true);
    expect(seen.market.price && seen.profile.price,
      `"${title}" costs ${pesos} in the database. market shows the price: ${seen.market.price}; ` +
      `profile shows it: ${seen.profile.price}. The same object must cost the same on both`).toBe(true);
  });
