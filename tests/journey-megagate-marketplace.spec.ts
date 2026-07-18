/**
 * Tier 5b — Marketplace flows (FREE marketplace, P1)
 *
 * Seller list → Admin approve → Inquiries. The marketplace is free + contact-only
 * (Stripe removed 2026-06-30): no checkout/webhook/payment rail. Buyers reach
 * sellers via the inquiry form; the seller profile surfaces those inquiries.
 *
 * Named `journey-megagate-marketplace` to coexist with the pre-existing
 * `journey-marketplace.spec.ts`.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';
import { readFileSync } from 'fs';
import { resolve } from 'path';

const ROOT = resolve(__dirname, '..');

test.describe('Tier 5b — Marketplace flows (megagate)', () => {

  test('F1_seller_list_item_insert_path: marketplace.html inserts into marketplace_listings', async () => {
    // WHY: listings are created via marketplace.html's submission flow (seller page manages existing)
    const html = readFileSync(resolve(ROOT, 'marketplace.html'), 'utf-8');
    expect(html, 'marketplace.html must insert into marketplace_listings').toMatch(
      /from\s*\(\s*['"]marketplace_listings['"]\s*\)[\s\S]{0,300}\.insert\s*\(/
    );
    // Audit log row for create_listing
    expect(html, 'must write audit log for create_listing').toMatch(/create_listing/);
  });

  test('F2_admin_approve_publishes_listing: marketplace-admin flips status to published', async () => {
    // WHY: admin moderation is the gate from draft → public visibility
    const html = readFileSync(resolve(ROOT, 'marketplace-admin.html'), 'utf-8');
    // Approve action must compute status='published'
    expect(html, 'approve action must produce published status').toMatch(/['"]approve['"]\s*\?\s*['"]published['"]/);
    // Update path on marketplace_listings (not direct insert)
    expect(html, 'must update marketplace_listings').toMatch(
      /from\s*\(\s*['"]marketplace_listings['"]\s*\)[\s\S]{0,400}\.update\s*\(/
    );
  });

  test('F5_seller_inquiries_visible_on_profile: marketplace-seller-profile reads marketplace_inquiries (or canonical view)', async () => {
    // WHY: marketplace_inquiries is the buyer↔seller channel; seller profile must surface them.
    // Accept either the raw table or v_marketplace_inquiries_truth (canonical view) —
    // reading the truth view is the platform's preferred pattern per KPI_ENGINE.md.
    const html = readFileSync(resolve(ROOT, 'marketplace-seller-profile.html'), 'utf-8');
    expect(html, 'seller profile must query marketplace_inquiries or v_marketplace_inquiries_truth').toMatch(
      /from\s*\(\s*['"](?:marketplace_inquiries|v_marketplace_inquiries_truth)['"]\s*\)/
    );
    // Inquiries replied counter (UI surface)
    expect(html, 'must display inquiries-replied stat').toMatch(/stat-replies|Inquiries Replied/i);
  });
});
