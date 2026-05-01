/**
 * marketplace-checkout — Stripe Checkout session creator
 *
 * POST /functions/v1/marketplace-checkout
 * Body: { listing_id: string, buyer_name: string, hive_id?: string }
 *
 * Security rules enforced here (never on client):
 *  1. Price fetched from DB — client-submitted price is ignored
 *  2. Listing must be status=published before checkout is created
 *  3. Stripe secret key never leaves this function
 *  4. application_fee_amount deducted at charge time (platform revenue)
 */

import { serve } from 'https://deno.land/std@0.168.0/http/server.ts';
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

/* ── CORS ──────────────────────────────────────────────────────────────── */
function getCorsHeaders(req: Request): Record<string, string> {
  const origin = req.headers.get('origin') || '';
  const allowed = [
    'https://workhiveph.com',
    'https://www.workhiveph.com',
    'http://localhost',
    'null', // file:// local testing
  ];
  const allowedOrigin = allowed.includes(origin) ? origin : allowed[0];
  return {
    'Access-Control-Allow-Origin':  allowedOrigin,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  };
}

function json(data: unknown, status = 200, req: Request) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', ...getCorsHeaders(req) },
  });
}

function errJson(error: string, status: number, req: Request) {
  return new Response(JSON.stringify({ error: error }), {
    status,
    headers: { 'Content-Type': 'application/json', ...getCorsHeaders(req) },
  });
}

/* ── Constants ─────────────────────────────────────────────────────────── */
const PLATFORM_FEE_PCT  = 0.05;   // 5% platform fee
const ESCROW_HOLD_DAYS  = 7;
const CURRENCY          = 'php';
const SUCCESS_URL       = 'https://workhiveph.com/marketplace.html?checkout=success';
const CANCEL_URL        = 'https://workhiveph.com/marketplace.html?checkout=cancelled';

/* ── Handler ────────────────────────────────────────────────────────────── */
serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: getCorsHeaders(req) });
  }

  if (req.method !== 'POST') {
    return errJson('Method not allowed', 405, req);
  }

  /* ── Parse body ─────────────────────────────────────────────────────── */
  let body: { listing_id?: string; buyer_name?: string; hive_id?: string };
  try {
    body = await req.json();
  } catch {
    return errJson('Invalid JSON body', 400, req);
  }

  const { listing_id, buyer_name, hive_id } = body;
  if (!listing_id || !buyer_name) {
    return errJson('listing_id and buyer_name are required', 400, req);
  }

  /* ── Supabase client ─────────────────────────────────────────────────── */
  const supabaseUrl  = Deno.env.get('SUPABASE_URL')!;
  const serviceKey   = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
  const db = createClient(supabaseUrl, serviceKey);

  /* ── Fetch listing from DB (never trust client price) ────────────────── */
  const { data: listing, error: listErr } = await db
    .from('marketplace_listings')
    .select('id, title, price, status, seller_name, section, image_url')
    .eq('id', listing_id)
    .single();

  if (listErr || !listing) {
    return errJson('Listing not found', 404, req);
  }
  if (listing.status !== 'published') {
    return errJson('Listing is not available for purchase', 400, req);
  }
  if (!listing.price || Number(listing.price) <= 0) {
    return errJson('This listing requires direct negotiation — no fixed price set', 400, req);
  }

  /* ── Look up seller Stripe account ──────────────────────────────────── */
  const { data: seller } = await db
    .from('marketplace_sellers')
    .select('stripe_account_id, kyb_verified')
    .eq('worker_name', listing.seller_name)
    .maybeSingle();

  if (!seller?.kyb_verified) {
    return errJson('Seller has not completed KYB verification — payments not enabled yet', 400, req);
  }
  if (!seller.stripe_account_id) {
    return errJson('Seller has not connected a Stripe account yet', 400, req);
  }

  /* ── Calculate amounts (in centavos — PHP smallest unit) ────────────── */
  const pricePhp       = Math.round(Number(listing.price) * 100);  // centavos
  const platformFee    = Math.round(pricePhp * PLATFORM_FEE_PCT);
  const escrowReleaseAt = new Date(Date.now() + ESCROW_HOLD_DAYS * 86400000).toISOString();

  /* ── Create Stripe Checkout session ─────────────────────────────────── */
  const stripeKey = Deno.env.get('STRIPE_SECRET_KEY')!;
  const stripeRes = await fetch('https://api.stripe.com/v1/checkout/sessions', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${stripeKey}`,
      'Content-Type':  'application/x-www-form-urlencoded',
    },
    signal: AbortSignal.timeout(10000),
    body: new URLSearchParams({
      'payment_method_types[]':                'card',
      'line_items[0][price_data][currency]':   CURRENCY,
      'line_items[0][price_data][unit_amount]': String(pricePhp),
      'line_items[0][price_data][product_data][name]': listing.title,
      'line_items[0][quantity]':               '1',
      'mode':                                  'payment',
      'success_url':                           SUCCESS_URL + `&order_id={CHECKOUT_SESSION_ID}`,
      'cancel_url':                            CANCEL_URL,
      'payment_intent_data[application_fee_amount]': String(platformFee),
      'payment_intent_data[transfer_data][destination]': seller.stripe_account_id,
      'payment_intent_data[capture_method]':   'automatic',
      'metadata[listing_id]':                  listing_id,
      'metadata[buyer_name]':                  buyer_name,
      'metadata[seller_name]':                 listing.seller_name,
    }).toString(),
  });

  if (!stripeRes.ok) {
    const errBody = await stripeRes.text();
    console.error('Stripe error:', errBody);
    return errJson('Payment provider error — please try again', 502, req);
  }

  const session = await stripeRes.json();

  /* ── Create order row in DB (escrow_hold after webhook confirms payment) */
  const { error: orderErr } = await db.from('marketplace_orders').insert({
    listing_id,
    hive_id:           hive_id || null,
    buyer_name,
    seller_name:       listing.seller_name,
    price:             listing.price,
    currency:          'PHP',
    stripe_session_id: session.id,
    status:            'pending_payment',
    escrow_release_at: escrowReleaseAt,
  });

  if (orderErr) {
    console.error('Order insert error:', orderErr.message);
    /* Checkout session is still valid — buyer can proceed.
       Log the error but do not block payment. */
  }

  return json({ url: session.url, session_id: session.id }, 200, req);
});
