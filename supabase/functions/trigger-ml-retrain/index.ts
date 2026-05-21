import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";

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

// ── ML Retrain Trigger Edge Function ─────────────────────────────────────────
// Called weekly by pg_cron (Sunday 02:00 PHT = Saturday 18:00 UTC).
// Fetches ALL corrective logbook entries across ALL hives, sends to Python API
// /ml/train endpoint. Python builds feature matrix and retrains GBM.
//
// Data threshold enforced in Python:
//   < 100 samples  → skipped (no model written)
//   100-499 samples → trained with data_warning: true
//   500+  samples  → full production model

const PYTHON_URL   = Deno.env.get("PYTHON_API_URL");
const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  try {
    if (!PYTHON_URL) {
      return new Response(
        JSON.stringify({ error: "PYTHON_API_URL not configured — cannot retrain." }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const db = createClient(SUPABASE_URL, SERVICE_KEY);

    // Fetch training data: all corrective logbook entries across all hives
    const [logRes, assetsRes, compsRes, scopeRes, txnsRes] = await Promise.allSettled([
      db.from("v_logbook_truth")
        .select("machine, maintenance_type, category, root_cause, downtime_hours, created_at, status, hive_id")
        .or("maintenance_type.ilike.%Corrective%,maintenance_type.ilike.%Breakdown%")
        .eq("status", "Closed")
        .order("created_at", { ascending: false })
        .limit(10000),

      // unbounded-query-allow: ML retrain reads full PM-compliance set for training data
      db.from("v_pm_compliance_truth").select("id, asset_name, tag_id, category, hive_id"),

      db.from("v_pm_compliance_truth")
        .select("asset_id, scope_item_id, completed_at, status, hive_id")
        .eq("status", "done")
        .limit(5000),

      db.from("v_pm_scope_items_truth")    // canonical
        .select("id, asset_id, frequency, item_text")
        .limit(2000),

      // inventory_transactions has no part_name — only item_id (FK). Embed
      // via PostgREST then flatten before passing to the Python training job.
      db.from("v_inventory_transactions_truth")
        .select("qty_change, type, created_at, hive_id, item:inventory_items(part_name)")
        .order("created_at", { ascending: false })
        .limit(5000),
    ]);

    const logbook        = logRes.status    === "fulfilled" ? (logRes.value.data    || []) : [];
    const pm_completions = compsRes.status  === "fulfilled" ? (compsRes.value.data  || []) : [];
    const pm_scope_items = scopeRes.status  === "fulfilled" ? (scopeRes.value.data  || []) : [];
    const rawTxns        = txnsRes.status   === "fulfilled" ? (txnsRes.value.data   || []) : [];
    const inv_transactions = rawTxns.map((t: Record<string, unknown>) => ({
      qty_change: t.qty_change,
      type:       t.type,
      created_at: t.created_at,
      hive_id:    t.hive_id,
      part_name:  (t.item as Record<string, string> | null)?.part_name || "(unknown part)",
    }));

    if (logbook.length < 10) {
      return new Response(
        JSON.stringify({ status: "skipped", reason: `Only ${logbook.length} records — need more data.` }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // POST to Python API /ml/train
    const trainResp = await fetch(`${PYTHON_URL}/ml/train`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      signal:  AbortSignal.timeout(300000), // 5min — training can take a while
      body:    JSON.stringify({
        inputs: { logbook_entries: logbook, pm_completions, pm_scope_items, inv_transactions },
      }),
    });

    const trainResult = await trainResp.json();

    // Log result to automation_log
    await db.from("automation_log").insert({
      job_name: "ml-retrain",
      status:   trainResp.ok ? "success" : "failed",
      detail:   JSON.stringify(trainResult).slice(0, 500),
    }).then(({ error }) => { if (error) console.warn("audit log:", error.message); });

    return new Response(JSON.stringify(trainResult), {
      status:  trainResp.ok ? 200 : 502,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error("trigger-ml-retrain:", msg);
    return new Response(JSON.stringify({ error: msg }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
