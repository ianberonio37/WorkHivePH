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
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
import { log } from "../_shared/logger.ts";
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
// Arc R (A01 BOLA): a caller may only check/onboard THEIR OWN seller account.
import { resolveIdentity } from '../_shared/tenant-context.ts';
import { getCorsHeaders } from '../_shared/cors.ts';

// Warm module-scope Supabase client. Reused across request invocations
// in the same warm container. Per-request createClient calls below are
// being phased out (PRODUCTION_FIXES #46). Falls back to an empty
// client if env is missing so module import never throws.
const _WH_SUPABASE_URL_M = Deno.env.get("SUPABASE_URL") || "";
const _WH_SERVICE_KEY_M  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const _whWarmClient = _WH_SUPABASE_URL_M && _WH_SERVICE_KEY_M
  ? createClient(_WH_SUPABASE_URL_M, _WH_SERVICE_KEY_M)
  : null;
void _whWarmClient;

/* CORS handled by _shared/cors.ts (security skill rule -- 2026-05-18). */

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

  /* ── Arc R (A01 BOLA): the old code took worker_name from the body with NO JWT, so any
     anon caller could read ANY seller's live Stripe status (charges/payouts/requirements)
     and flip their kyb_verified (denial-of-revenue). Bind worker_name to the verified
     caller; service_role keeps the body value (trusted automation). */
  let effectiveWorker = worker_name;
  const _id = await resolveIdentity(db, req);
  if (!_id.isServiceRole) {
    if (!_id.authUid) return errJson('Sign-in required', 401, req);
    // canonical-allow: caller identity/authz read (own profile by auth_uid -> 403 if none);
    // v_worker_truth is over hive_members, not the auth-identity source, so it cannot serve this.
    const { data: _wp } = await db.from('worker_profiles')
      .select('display_name').eq('auth_uid', _id.authUid).maybeSingle();
    if (!_wp?.display_name) return errJson('No profile for caller', 403, req);
    effectiveWorker = _wp.display_name;
  }

  /* ── Look up seller (canonical: marketplace_sellers_truth) ──────────── */
  const { data: seller, error: sellerErr } = await db
    .from('v_marketplace_sellers_truth')
    .select('stripe_account_id, kyb_verified, tier')
    .eq('worker_name', effectiveWorker)
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
    log.error(null, 'Stripe account fetch error:', { detail: err });
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
      .eq('worker_name', effectiveWorker);

    if (updateErr) {
      log.error(null, 'KYB update error:', { detail: updateErr.message });
    } else {
      log.info(null, `KYB auto-verified for seller: ${worker_name}`);
    }
  }

  /* ── If previously verified but now charges disabled, revoke ────────── */
  if (!nowVerified && seller.kyb_verified) {
    await db
      .from('marketplace_sellers')
      .update({ kyb_verified: false, kyb_verified_at: null, updated_at: new Date().toISOString() })
      .eq('worker_name', effectiveWorker);
    log.info(null, `KYB revoked for seller: ${worker_name} (charges no longer enabled)`);
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
