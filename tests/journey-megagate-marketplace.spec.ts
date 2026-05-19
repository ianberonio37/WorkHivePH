/**
 * Tier 5b — Marketplace flows (5 scenarios, P1)
 *
 * Seller list → Admin approve → Buyer checkout → Webhook → Inquiries.
 * Stripe is the payment rail; webhook signature verification is critical.
 *
 * Named `journey-megagate-marketplace` to coexist with the pre-existing
 * `journey-marketplace.spec.ts`.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';
import { readFileSync, existsSync } from 'fs';
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

  test('F3_buyer_checkout_invokes_edge_fn: marketplace.html calls marketplace-checkout', async () => {
    // WHY: marketplace-checkout edge fn creates Stripe session server-side; price always fetched from DB
    const html = readFileSync(resolve(ROOT, 'marketplace.html'), 'utf-8');
    // Either direct fetch to the function URL OR supabase.functions.invoke
    const callsDirect = /functions\/v1\/marketplace-checkout/.test(html);
    const callsInvoke = /invoke\s*\(\s*['"]marketplace-checkout['"]/.test(html);
    expect(callsDirect || callsInvoke, 'must call marketplace-checkout edge fn').toBeTruthy();
  });

  test('F4_stripe_webhook_signature_verification: marketplace-webhook verifies HMAC-SHA256', async () => {
    // WHY: webhook MUST verify Stripe-Signature against STRIPE_WEBHOOK_SECRET before any DB write
    const fnPath = resolve(ROOT, 'supabase/functions/marketplace-webhook/index.ts');
    expect(existsSync(fnPath), 'marketplace-webhook edge fn must exist').toBeTruthy();
    const src = readFileSync(fnPath, 'utf-8');
    // HMAC-SHA256 verification block present
    expect(src, 'must read Stripe-Signature header').toMatch(/stripe-signature/i);
    expect(src, 'must read STRIPE_WEBHOOK_SECRET from env').toMatch(/STRIPE_WEBHOOK_SECRET/);
    expect(src, 'must use HMAC SHA-256').toMatch(/HMAC[\s\S]{0,80}SHA-?256/);
    // Reject invalid signature with 401
    expect(src, 'must return 401 on invalid signature').toMatch(/Invalid Stripe signature[\s\S]{0,40},\s*401/);
  });

  test('F5_seller_inquiries_visible_on_profile: marketplace-seller-profile reads marketplace_inquiries', async () => {
    // WHY: marketplace_inquiries is the buyer↔seller channel; seller profile must surface them
    const html = readFileSync(resolve(ROOT, 'marketplace-seller-profile.html'), 'utf-8');
    expect(html, 'seller profile must query marketplace_inquiries').toMatch(
      /from\s*\(\s*['"]marketplace_inquiries['"]\s*\)/
    );
    // Inquiries replied counter (UI surface)
    expect(html, 'must display inquiries-replied stat').toMatch(/stat-replies|Inquiries Replied/i);
  });
});
