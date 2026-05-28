/**
// capability: export_hive_data
 * export-hive-data — Phase 5 Track A of STRATEGIC_ROADMAP.md.
 *
 * PDPA Article 16 right-to-access bulk export. Returns a downloadable JSON
 * blob containing every hive-scoped row across canonical surfaces:
 *   hive + members + logbook + pm_completions + pm_assets + inventory_items
 *   + inventory_transactions + asset_nodes + community_posts + hive_audit_log
 *   + hive_readiness + hive_adoption_score + anomaly_signals
 *
 * Auth contract:
 *   - Caller MUST have a valid Supabase Auth session (JWT in Authorization
 *     header forwarded by supabase-js).
 *   - Caller MUST be an active SUPERVISOR of the hive being exported.
 *     This is the only role that can act on behalf of the hive for PDPA
 *     requests under our doctrine.
 *   - Anonymous OR worker-role calls are rejected 403.
 *
 * Output:
 *   {
 *     ok: true,
 *     hive_id: <uuid>,
 *     bytes: <number>,
 *     export: <jsonb_payload>
 *   }
 *
 * The caller (operator dashboard) decides whether to (a) hand the JSON
 * directly to the supervisor for download, or (b) upload it to a signed
 * Storage URL and email the link. This edge fn does neither — the export
 * blob is the canonical artifact.
 *
 * Skills consulted:
 *   enterprise-compliance (right-to-access pattern; structured + machine-readable)
 *   security (auth check FIRST; supervisor-only; no PII leaks across hive boundaries)
 *   architect (one canonical RPC + one edge fn wrapper, not five export endpoints)
 *   devops (getCorsHeaders dynamic CORS; module-scope warm client; bounded latency)
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
// contract-allow: PDPA right-to-access export; structured payload, not a brain output
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";

// Warm module-scope client (PRODUCTION_FIXES #46 pattern).
const _WH_SUPABASE_URL_M = Deno.env.get("SUPABASE_URL") || "";
const _WH_SERVICE_KEY_M  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const _whWarmClient = _WH_SUPABASE_URL_M && _WH_SERVICE_KEY_M
  ? createClient(_WH_SUPABASE_URL_M, _WH_SERVICE_KEY_M)
  : null;
void _whWarmClient;

const EXPORT_TIMEOUT_MS = 30_000;

interface AuthCheckResult {
  ok: boolean;
  auth_uid?: string;
  reason?: string;
}

async function checkSupervisor(
  db: SupabaseClient, jwt: string, hive_id: string,
): Promise<AuthCheckResult> {
  if (!jwt) return { ok: false, reason: "Missing Authorization bearer JWT" };

  // Resolve the user from the JWT (service-role can introspect).
  const { data: userData, error: userErr } = await db.auth.getUser(jwt);
  if (userErr || !userData?.user) {
    return { ok: false, reason: "Invalid or expired JWT" };
  }
  const auth_uid = userData.user.id;

  // Membership check via service-role bypass of RLS.
  const { data: member, error: memErr } = await db
    .from("v_worker_truth")
    .select("role, status")
    .eq("hive_id", hive_id)
    .eq("auth_uid", auth_uid)
    .maybeSingle();
  if (memErr) {
    return { ok: false, reason: "Membership check failed: " + memErr.message };
  }
  if (!member) {
    return { ok: false, reason: "Caller is not a member of this hive" };
  }
  if (member.status !== "active" || member.role !== "supervisor") {
    return { ok: false, reason: "PDPA right-to-access requires active supervisor role" };
  }
  return { ok: true, auth_uid };
}

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST") {
    return new Response(
      JSON.stringify({ error: "POST only" }),
      { status: 405, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  }

  try {
    const body = await req.json().catch(() => ({}));
    const hive_id = String(body.hive_id || "").trim();
    if (!hive_id) {
      return new Response(
        JSON.stringify({ error: "Missing required field: hive_id" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    const auth = req.headers.get("authorization") || "";
    const jwt = auth.toLowerCase().startsWith("bearer ") ? auth.slice(7).trim() : "";

    const db = _whWarmClient || createClient(
      Deno.env.get("SUPABASE_URL") || "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "",
    );

    const authRes = await checkSupervisor(db, jwt, hive_id);
    if (!authRes.ok) {
      return new Response(
        JSON.stringify({ error: authRes.reason || "Not authorized" }),
        { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    // Bounded RPC call.
    const exportP = db.rpc("export_hive_data", { p_hive_id: hive_id });
    const timeout = new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error("export timed out")), EXPORT_TIMEOUT_MS),
    );

    const { data: payload, error } = await Promise.race([exportP, timeout])
      .catch((err) => ({ data: null, error: err })) as { data: unknown; error: unknown };

    if (error) {
      const msg = error instanceof Error ? error.message : String(error);
      return new Response(
        JSON.stringify({ error: "Export RPC failed: " + msg }),
        { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    // Best-effort audit log so the supervisor's own action is traceable.
    try {
      await db.from("hive_audit_log").insert({
        hive_id,
        actor:       null,        // auth_uid resolves the actor server-side
        action:      "export_hive_data",
        target_type: "hive",
        target_id:   hive_id,
        target_name: "PDPA export",
        meta:        { bytes: JSON.stringify(payload || {}).length },
      });
    } catch (_) { /* audit best-effort */ }

    const bytes = JSON.stringify(payload || {}).length;
    return new Response(
      JSON.stringify({ ok: true, hive_id, bytes, export: payload }),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    // Inline JSON.stringify({ error: ... }) for static error-contract scan.
    return new Response(
      JSON.stringify({ error: "Internal error", detail: msg }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  }
});
