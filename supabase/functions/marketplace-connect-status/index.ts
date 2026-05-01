/**
 * marketplace-connect-status — Check Stripe Connect account status
 * and auto-verify KYB when Stripe confirms the account is ready.
 *
 * POST /functions/v1/marketplace-connect-status
 * Body: { worker_name: string }
 *
 * Flow (called when seller returns from Stripe onboarding):
 *   1. Look up seller's stripe_account_id in marketplace_sellers
 *   2. Fetch the account from Stripe API
 *   3. If charges_enabled AND details_submitted → set kyb_verified = true
 *   4. Return current account status to the caller
 *
 * Also used by the admin "Re-check Stripe" button to refresh KYB status
 * without requiring the seller to redo onboarding.
 */

import { serve } from 'https://deno.land/std@0.168.0/http/server.ts';
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

function getCorsHeaders(req: Request): Record<string, string> {
  const origin = req.headers.get('origin') || '';
  const allowed = ['https://workhiveph.com', 'https://www.workhiveph.com', 'null', 'http://localhost'];
  const allowedOrigin = allowed.includes(origin) ? origin : allowed[0];
  return {
    'Access-Control-Allow-Origin':  allowedOrigin,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  };
}

function errJson(error: string, status: number, req: Request) {
  return new Response(JSON.stringify({ error: error }), {
    status,
    headers: { 'Content-Type': 'application/json', ...getCorsHeaders(req) },
  });
}

serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: getCorsHeaders(req) });
  }
  if (req.method !== 'POST') {
    return errJson('Method not allowed', 405, req);
  }

  let body: { worker_name?: string };
  try { body = await req.json(); } catch {
    return errJson('Invalid JSON body', 400, req);
  }

  const { worker_name } = body;
  if (!worker_name) {
    return errJson('worker_name is required', 400, req);
  }

  const stripeKey = Deno.env.get('STRIPE_SECRET_KEY')!;
  const db = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
  );

  /* ── Look up seller ─────────────────────────────────────────────────── */
  const { data: seller, error: sellerErr } = await db
    .from('marketplace_sellers')
    .select('stripe_account_id, kyb_verified, tier')
    .eq('worker_name', worker_name)
    .maybeSingle();

  if (sellerErr) {
    return errJson('Database error', 500, req);
  }
  if (!seller?.stripe_account_id) {
    return new Response(JSON.stringify({
      verified:          false,
      charges_enabled:   false,
      details_submitted: false,
      needs_onboarding:  true,
    }), { status: 200, headers: { 'Content-Type': 'application/json', ...getCorsHeaders(req) } });
  }

  /* ── Fetch account from Stripe ──────────────────────────────────────── */
  const stripeRes = await fetch(
    `https://api.stripe.com/v1/accounts/${seller.stripe_account_id}`,
    {
      headers: { 'Authorization': `Bearer ${stripeKey}` },
      signal:  AbortSignal.timeout(8000),
    }
  );

  if (!stripeRes.ok) {
    const err = await stripeRes.text();
    console.error('Stripe account fetch error:', err);
    return errJson('Could not fetch Stripe account status', 502, req);
  }

  const account = await stripeRes.json();
  const chargesEnabled   = account.charges_enabled   === true;
  const detailsSubmitted = account.details_submitted === true;
  const payoutsEnabled   = account.payouts_enabled   === true;
  const nowVerified      = chargesEnabled && detailsSubmitted;

  /* ── Update kyb_verified if Stripe confirms the account is ready ────── */
  if (nowVerified && !seller.kyb_verified) {
    const { error: updateErr } = await db
      .from('marketplace_sellers')
      .update({
        kyb_verified:    true,
        kyb_verified_at: new Date().toISOString(),
        updated_at:      new Date().toISOString(),
      })
      .eq('worker_name', worker_name);

    if (updateErr) {
      console.error('KYB update error:', updateErr.message);
    } else {
      console.log(`KYB auto-verified for seller: ${worker_name}`);
    }
  }

  /* ── If previously verified but now charges disabled, revoke ────────── */
  if (!nowVerified && seller.kyb_verified) {
    await db
      .from('marketplace_sellers')
      .update({ kyb_verified: false, kyb_verified_at: null, updated_at: new Date().toISOString() })
      .eq('worker_name', worker_name);
    console.log(`KYB revoked for seller: ${worker_name} (charges no longer enabled)`);
  }

  /* ── Collect pending requirements from Stripe ───────────────────────── */
  const requirements = account.requirements?.currently_due || [];
  const eventuallyDue = account.requirements?.eventually_due || [];

  return new Response(JSON.stringify({
    verified:          nowVerified,
    charges_enabled:   chargesEnabled,
    details_submitted: detailsSubmitted,
    payouts_enabled:   payoutsEnabled,
    needs_onboarding:  false,
    requirements_due:  requirements,
    eventually_due:    eventuallyDue,
    disabled_reason:   account.requirements?.disabled_reason || null,
  }), {
    status:  200,
    headers: { 'Content-Type': 'application/json', ...getCorsHeaders(req) },
  });
});
