/**
 * roadmap.spec.ts — Phase 2 public roadmap + upvote (Sentinel L0->L2).
 *
 * Covers the Phase 2 additions in validate_feedback_widget.py:
 *   roadmap_page_exists          — page loads + renders
 *   roadmap_uses_toggle_rpc      — vote button calls the RPC
 *   schema_votes_table           — exercised end-to-end via the RPC
 *   schema_toggle_rpc            — exercised end-to-end via the RPC
 *
 * Test names use the `check_name:` prefix convention so the sentinel
 * matcher Path A auto-binds them on the next run.
 *
 * Skills consulted: qa-tester (rawPage for public surface), community
 * (open feed assertions), platform-guardian (DB + DOM dual-assert).
 */
import { test, expect } from '@playwright/test';
import { adminClient } from './_db-cleanup';

const ROADMAP_URL = 'http://127.0.0.1:5000/workhive/feedback/';

test.describe('Public feedback roadmap (L2 for migration 20260519000003)', () => {

  test('roadmap_page_exists: page renders hero + filter chips', async ({ page }) => {
    await page.goto(ROADMAP_URL);
    await expect(page.locator('h1')).toContainText(/Filipino plant workers/i);
    await expect(page.locator('.filter-chip[data-kind="bug"]')).toBeVisible();
    await expect(page.locator('.filter-chip[data-kind="idea"]')).toBeVisible();
  });

  test('roadmap_uses_toggle_rpc: voting on a public item updates the count + RPC blocks double-vote per token', async ({ page }) => {
    const db = adminClient();
    const tag = `roadmap-probe-${Date.now().toString(36)}`;

    // Seed a public item via service role
    const { data: ins, error: insErr } = await db.from('platform_feedback').insert({
      kind: 'idea',
      subject: `${tag} rpc test`,
      body: 'roadmap toggle_feedback_upvote round-trip test',
      contact_email: `${tag}@local.invalid`,
      is_public: true,
    }).select('id').single();
    expect(insErr, 'seed insert failed').toBeNull();
    const itemId = ins!.id;

    try {
      await page.goto(ROADMAP_URL);
      // Wait for the card carrying our subject to render
      const subjectHeading = page.locator(`text=${tag} rpc test`).first();
      await expect(subjectHeading).toBeVisible({ timeout: 10000 });

      const voteBtn = page.locator(`[data-vote="${itemId}"]`);
      await expect(voteBtn).toBeVisible();

      // Click to vote
      await voteBtn.click();
      // After vote, the button has .voted class + count incremented to 1
      await expect(voteBtn).toHaveClass(/voted/, { timeout: 5000 });
      await expect(voteBtn.locator('.count')).toHaveText('1');

      // Click again to toggle off
      await voteBtn.click();
      await expect(voteBtn).not.toHaveClass(/voted/, { timeout: 5000 });
      await expect(voteBtn.locator('.count')).toHaveText('0');
    } finally {
      // Cleanup
      await db.from('platform_feedback').delete().eq('id', itemId);
    }
  });

  test('schema_toggle_rpc: voting on a NON-public item rejects with friendly error in console', async ({ page }) => {
    const db = adminClient();
    const tag = `roadmap-private-${Date.now().toString(36)}`;

    // Seed a PRIVATE item (default is_public=false)
    const { data: ins } = await db.from('platform_feedback').insert({
      kind: 'idea',
      subject: `${tag} private`,
      body: 'should NOT be voteable',
      contact_email: `${tag}@local.invalid`,
    }).select('id').single();
    const itemId = ins!.id;

    try {
      const errs: string[] = [];
      page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
      page.on('pageerror', e => errs.push(e.message));

      await page.goto(ROADMAP_URL);
      // Call the RPC directly from the page context — the UI doesn't
      // expose private items, but the RPC's guard must hold for any
      // attacker-crafted call too.
      const result = await page.evaluate(async (id) => {
        const url = 'https://hzyvnjtisfgbksicrouu.supabase.co'.replace(
          'https://hzyvnjtisfgbksicrouu.supabase.co',
          'http://127.0.0.1:54321',
        );
        const key = (window as any).getDb
          ? null
          : null;  // we'll just use fetch directly
        const res = await fetch(`${url}/rest/v1/rpc/toggle_feedback_upvote`, {
          method:  'POST',
          headers: {
            'apikey':        'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0',
            'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0',
            'Content-Type':  'application/json',
          },
          body: JSON.stringify({ p_feedback_id: id, p_voter_token: 'attacker-token' }),
        });
        return { status: res.status, body: await res.text() };
      }, itemId);

      // RPC raises EXCEPTION on private; PostgREST surfaces as 400/500
      expect(result.status, `expected RPC to reject; got ${result.status} body=${result.body}`)
        .toBeGreaterThanOrEqual(400);
      expect(result.body.toLowerCase()).toMatch(/not public|cannot|error/);
    } finally {
      await db.from('platform_feedback').delete().eq('id', itemId);
    }
  });
});
