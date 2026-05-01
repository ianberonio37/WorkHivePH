/**
 * marketplace-release — Buyer confirms receipt, releases escrow to seller
 *
 * POST /functions/v1/marketplace-release
 * Body: { order_id: string, buyer_name: string }
 *
 * Flow:
 *   1. Fetch order — must be escrow_hold and belong to buyer_name
 *   2. Fetch seller's stripe_account_id from marketplace_sellers
 *   3. Create Stripe Transfer: platform → seller Connect account
 *   4. Update order status to released
 *   5. Update seller total_sales + trigger tier upgrade
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

const PLATFORM_FEE_PCT = 0.05; /* 5% platform fee already deducted at checkout */

serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: getCorsHeaders(req) });
  }
  if (req.method !== 'POST') {
    return errJson('Method not allowed', 405, req);
  }

  let body: { order_id?: string; buyer_name?: string };
  try { body = await req.json(); } catch {
    return errJson('Invalid JSON body', 400, req);
  }

  const { order_id, buyer_name } = body;
  if (!order_id || !buyer_name) {
    return errJson('order_id and buyer_name are required', 400, req);
  }

  const stripeKey = Deno.env.get('STRIPE_SECRET_KEY')!;
  const db = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
  );

  /* ── Fetch the order ────────────────────────────────────────────────── */
  const { data: order, error: orderErr } = await db
    .from('marketplace_orders')
    .select('id, buyer_name, seller_name, price, status, stripe_payment_id')
    .eq('id', order_id)
    .single();

  if (orderErr || !order) {
    return errJson('Order not found', 404, req);
  }
  if (order.buyer_name !== buyer_name) {
    return errJson('You are not the buyer for this order', 403, req);
  }
  if (order.status !== 'escrow_hold') {
    return errJson(`Order is ${order.status} — cannot release`, 400, req);
  }
  if (!order.stripe_payment_id) {
    return errJson('No payment ID on this order — contact support', 400, req);
  }

  /* ── Fetch seller's Stripe account ──────────────────────────────────── */
  const { data: seller } = await db
    .from('marketplace_sellers')
    .select('stripe_account_id')
    .eq('worker_name', order.seller_name)
    .maybeSingle();

  if (!seller?.stripe_account_id) {
    return errJson('Seller has no connected Stripe account — contact support', 400, req);
  }

  /* ── Calculate transfer amount (price minus platform fee, in centavos) */
  const totalCentavos    = Math.round(Number(order.price) * 100);
  const platformFee      = Math.round(totalCentavos * PLATFORM_FEE_PCT);
  const transferAmount   = totalCentavos - platformFee;

  /* ── Create Stripe Transfer to seller ───────────────────────────────── */
  const transferRes = await fetch('https://api.stripe.com/v1/transfers', {
    method:  'POST',
    headers: {
      'Authorization': `Bearer ${stripeKey}`,
      'Content-Type':  'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams({
      'amount':              String(transferAmount),
      'currency':            'php',
      'destination':         seller.stripe_account_id,
      'source_transaction':  order.stripe_payment_id,
      'metadata[order_id]':  order_id,
    }).toString(),
    signal: AbortSignal.timeout(10000),
  });

  if (!transferRes.ok) {
    const err = await transferRes.text();
    console.error('Stripe transfer error:', err);
    return errJson('Transfer failed — funds still held safely. Contact support.', 502, req);
  }

  const transfer = await transferRes.json();

  /* ── Update order to released ───────────────────────────────────────── */
  const now = new Date().toISOString();
  const { error: releaseErr } = await db
    .from('marketplace_orders')
    .update({
      status:             'released',
      stripe_transfer_id: transfer.id,
      buyer_confirmed_at: now,
      released_at:        now,
      updated_at:         now,
    })
    .eq('id', order_id);

  if (releaseErr) {
    console.error('Order release update failed:', releaseErr.message);
    /* Transfer succeeded — flag for manual reconciliation */
    return errJson('Transfer sent but order status update failed — contact support', 500, req);
  }

  console.log(`Order ${order_id} released. Transfer: ${transfer.id}`);

  return new Response(JSON.stringify({ released: true, transfer_id: transfer.id }), {
    status:  200,
    headers: { 'Content-Type': 'application/json', ...getCorsHeaders(req) },
  });
});
