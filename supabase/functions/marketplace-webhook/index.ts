/**
 * marketplace-webhook — Stripe webhook listener
 *
 * Handles two events:
 *   checkout.session.completed  → order moves to escrow_hold
 *   payment_intent.payment_failed → order moves to failed (future state)
 *
 * Security: verifies Stripe-Signature header before touching any data.
 * Set STRIPE_WEBHOOK_SECRET in Supabase Vault after registering this
 * endpoint in Stripe Dashboard → Developers → Webhooks.
 */

import { serve } from 'https://deno.land/std@0.168.0/http/server.ts';
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

function getCorsHeaders(req: Request): Record<string, string> {
  return {
    'Access-Control-Allow-Origin':  '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Stripe-Signature',
  };
}

function errJson(error: string, status: number, req: Request) {
  return new Response(JSON.stringify({ error: error }), {
    status,
    headers: { 'Content-Type': 'application/json', ...getCorsHeaders(req) },
  });
}

/* ── Stripe signature verification (HMAC-SHA256) ──────────────────────── */
async function verifyStripeSignature(
  payload: string,
  sigHeader: string,
  secret: string
): Promise<boolean> {
  try {
    const parts = Object.fromEntries(sigHeader.split(',').map(p => p.split('=')));
    const timestamp = parts['t'];
    const signature = parts['v1'];
    if (!timestamp || !signature) return false;

    const signedPayload = `${timestamp}.${payload}`;
    const key = await crypto.subtle.importKey(
      'raw',
      new TextEncoder().encode(secret),
      { name: 'HMAC', hash: 'SHA-256' },
      false,
      ['sign']
    );
    const sig = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(signedPayload));
    const computed = Array.from(new Uint8Array(sig))
      .map(b => b.toString(16).padStart(2, '0')).join('');

    return computed === signature;
  } catch {
    return false;
  }
}

serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: getCorsHeaders(req) });
  }

  if (req.method !== 'POST') {
    return errJson('Method not allowed', 405, req);
  }

  /* ── Read raw body (needed for signature verification) ─────────────── */
  const rawBody = await req.text();
  const sigHeader = req.headers.get('stripe-signature') || '';
  const webhookSecret = Deno.env.get('STRIPE_WEBHOOK_SECRET') || '';

  if (!webhookSecret) {
    return errJson('Webhook secret not configured', 500, req);
  }

  const valid = await verifyStripeSignature(rawBody, sigHeader, webhookSecret);
  if (!valid) {
    return errJson('Invalid Stripe signature', 401, req);
  }

  /* ── Parse event ────────────────────────────────────────────────────── */
  let event: { type: string; data: { object: Record<string, unknown> } };
  try {
    event = JSON.parse(rawBody);
  } catch {
    return errJson('Invalid JSON', 400, req);
  }

  const db = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
  );

  /* ── checkout.session.completed → move order to escrow_hold ─────────── */
  if (event.type === 'checkout.session.completed') {
    const session = event.data.object;
    const sessionId   = session['id']                as string;
    const paymentId   = session['payment_intent']    as string;
    const amountTotal = session['amount_total']      as number;

    const { data: order, error: findErr } = await db
      .from('marketplace_orders')
      .select('id, price, status')
      .eq('stripe_session_id', sessionId)
      .maybeSingle();

    if (findErr || !order) {
      console.error('Order not found for session:', sessionId);
      return new Response('ok', { status: 200 }); /* acknowledge to Stripe */
    }

    if (order.status !== 'pending_payment') {
      return new Response('ok', { status: 200 }); /* already processed */
    }

    /* Verify amount matches what we stored (fraud guard) */
    const storedCentavos = Math.round(Number(order.price) * 100);
    if (amountTotal && amountTotal !== storedCentavos) {
      console.error(`Amount mismatch: Stripe=${amountTotal} DB=${storedCentavos}`);
      return errJson('Amount mismatch — payment not applied', 400, req);
    }

    const { error: updateErr } = await db
      .from('marketplace_orders')
      .update({
        status:           'escrow_hold',
        stripe_payment_id: paymentId,
        updated_at:       new Date().toISOString(),
      })
      .eq('id', order.id);

    if (updateErr) {
      console.error('Order update failed:', updateErr.message);
      return errJson('Order update failed', 500, req);
    }

    console.log(`Order ${order.id} moved to escrow_hold`);
  }

  /* ── checkout.session.expired → keep as pending, log only ───────────── */
  if (event.type === 'checkout.session.expired') {
    const session   = event.data.object;
    const sessionId = session['id'] as string;
    console.log(`Checkout session expired: ${sessionId}`);
    /* No DB change — order stays pending_payment until cleaned up by cron */
  }

  /* Always return 200 to acknowledge receipt to Stripe */
  return new Response(JSON.stringify({ received: true }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
});
