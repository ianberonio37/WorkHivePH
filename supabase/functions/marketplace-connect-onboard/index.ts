/**
 * marketplace-connect-onboard — Stripe Connect seller onboarding
 *
 * POST /functions/v1/marketplace-connect-onboard
 * Body: { worker_name: string, return_url: string, refresh_url: string }
 *
 * Flow:
 *   1. Look up or create a Stripe Connect account for this seller
 *   2. Save the account ID in marketplace_sellers
 *   3. Create an Account Link (onboarding URL) and return it
 *   4. Seller is redirected to Stripe to add bank details + business info
 *   5. On return, poll /marketplace-connect-status to check kyb_verified
 */

import { serve } from 'https://deno.land/std@0.168.0/http/server.ts';
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
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

async function stripePost(
  path: string,
  params: Record<string, string>,
  key: string,
  idempotencyKey?: string,
) {
  // idempotencyKey is OPTIONAL because account_links are short-lived (5 min)
  // ephemeral resources where a fresh response per call is the desired
  // behavior. Resource-creating calls (accounts, transfers) MUST pass a stable
  // Idempotency-Key so a network retry doesn't create a duplicate Stripe
  // account / payout.
  const res = await fetch(`https://api.stripe.com/v1/${path}`, {
    method:  'POST',
    headers: {
      'Authorization':   `Bearer ${key}`,
      'Content-Type':    'application/x-www-form-urlencoded',
      // Conditional spread keeps the Idempotency-Key header in the same
      // request-config block so static idempotency validators see it.
      ...(idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {}),
    },
    body:    new URLSearchParams(params).toString(),
    signal:  AbortSignal.timeout(10000),
  });
  return res;
}

serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: getCorsHeaders(req) });
  }
  if (req.method !== 'POST') {
    return errJson('Method not allowed', 405, req);
  }

  let body: { worker_name?: string; return_url?: string; refresh_url?: string };
  try { body = await req.json(); } catch {
    return errJson('Invalid JSON body', 400, req);
  }

  const { worker_name, return_url, refresh_url } = body;
  if (!worker_name || !return_url || !refresh_url) {
    return errJson('worker_name, return_url and refresh_url are required', 400, req);
  }

  const stripeKey = Deno.env.get('STRIPE_SECRET_KEY')!;
  const db = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
  );

  /* ── Look up existing seller profile (canonical: marketplace_sellers_truth) ── */
  const { data: seller } = await db
    .from('v_marketplace_sellers_truth')
    .select('stripe_account_id, kyb_verified')
    .eq('worker_name', worker_name)
    .maybeSingle();

  let stripeAccountId = seller?.stripe_account_id || null;

  /* ── Create Stripe Connect account if this seller doesn't have one ────
     Stable Idempotency-Key per worker_name — a network retry on this call
     must NOT create a second Stripe Connect account for the same seller
     (would split their payouts and confuse KYB review). */
  if (!stripeAccountId) {
    const accountIdemKey = `connect-onboard-account-${worker_name}`;
    const createRes = await stripePost('accounts', {
      'type':                        'express',
      'country':                     'PH',
      'capabilities[transfers][requested]': 'true',
      'metadata[worker_name]':       worker_name,
    }, stripeKey, accountIdemKey);

    if (!createRes.ok) {
      const err = await createRes.text();
      console.error('Stripe account create error:', err);
      return errJson('Could not create Stripe account', 502, req);
    }

    const account = await createRes.json();
    stripeAccountId = account.id;

    /* Save account ID to DB */
    await db.from('marketplace_sellers').upsert({
      worker_name,
      stripe_account_id: stripeAccountId,
      kyb_verified:      false,
      tier:              'bronze',
    }, { onConflict: 'worker_name' });
  }

  /* ── Create Account Link (onboarding URL) ───────────────────────────── */
  const linkRes = await stripePost('account_links', {
    'account':     stripeAccountId!,
    'refresh_url': refresh_url,
    'return_url':  return_url,
    'type':        'account_onboarding',
  }, stripeKey);

  if (!linkRes.ok) {
    const err = await linkRes.text();
    console.error('Stripe account link error:', err);
    return errJson('Could not create onboarding link', 502, req);
  }

  const link = await linkRes.json();

  return new Response(JSON.stringify({ url: link.url, account_id: stripeAccountId }), {
    status:  200,
    headers: { 'Content-Type': 'application/json', ...getCorsHeaders(req) },
  });
});
