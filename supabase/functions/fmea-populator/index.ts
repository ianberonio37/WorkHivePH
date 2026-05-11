/**
 * fmea-populator - Phase R.3: AI auto-populate FMEA from logbook clusters.
 *
 * Reads the last 365 days of corrective logbook entries for an asset (via
 * v_asset_truth.legacy_asset_id), clusters by root_cause, calls callAI per
 * cluster with a structured FMEA prompt, and inserts each suggestion into
 * rcm_fmea_modes with source='ai_logbook' and approved_at NULL so the
 * supervisor must still validate.
 *
 * Input:  { hive_id, asset_id, since_days?, force? }
 * Output: { suggestions_inserted, clusters_seen, skipped_existing, asset_tag }
 *
 * Skills consulted: ai-engineer (callAI shared chain, rate-limit gate FIRST,
 * Promise.allSettled per cluster, JSON-only output, system prompt as const,
 * cap row count at 200), maintenance-expert (AIAG-VDA 2019 S/O/D rubric +
 * SAE J1739 + ISO 14224 vocabulary), architect (canonical sources lookup,
 * 4-place sync, GENERATED ALWAYS AS column for RPN means we do not write
 * RPN directly), security (no service-role leak in errors, hive scoping
 * on every read), devops (getCorsHeaders dynamic CORS).
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { callAI } from "../_shared/ai-chain.ts";
import { logAICost, estimateTokens } from "../_shared/cost-log.ts";
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

// ─── Constants ────────────────────────────────────────────────────────────────

const RATE_LIMIT_PER_HOUR    = 50;
const DEFAULT_SINCE_DAYS     = 365;
const MIN_CLUSTER_SIZE       = 2;     // skill rule: a cluster of >= 2 is a candidate
const MAX_CLUSTERS_PER_RUN   = 6;     // cap so a noisy hive does not spam rows
const ENTRY_CAP_PER_CLUSTER  = 8;     // top-N entries fed to the model per cluster
const PROBLEM_SNIPPET_CHARS  = 180;
const ACTION_SNIPPET_CHARS   = 180;
const MAX_TOKENS_OUT         = 600;

const FMEA_SYSTEM_PROMPT = `You are a reliability engineer producing one FMEA row from a cluster of corrective maintenance records that share a root cause.

Respond ONLY with JSON. No markdown, no explanation.

Output schema:
{
  "function":          <string — what the asset is supposed to do>,
  "failure_mode":      <string — how the asset fails>,
  "effect":            <string — consequence of the failure>,
  "cause":             <string — refined root cause>,
  "consequence_class": <"safety"|"production"|"environment"|"quality"|"cost"|null>,
  "severity":          <integer 1..10>,
  "occurrence":        <integer 1..10>,
  "detection":         <integer 1..10>,
  "confidence":        <0..1>
}

Scoring per AIAG-VDA 2019:
- Severity   1=imperceptible, 5=moderate disruption / quality loss, 10=safety hazard or regulatory breach
- Occurrence map from cluster_count: 2->4, 3->5, 4->6, 5->7, 6+->8 (adjust if context suggests trend)
- Detection  1=instantly observable, 5=routine inspection catches it, 10=hidden failure with no warning

Rules:
1. Be conservative on confidence: < 0.6 means "supervisor should review carefully".
2. Use Filipino industrial vocabulary where appropriate (PEC, PSME, ISO 14224).
3. No em dashes in any string (use colons, commas, parentheses, or restructure).
4. If the cluster is too noisy or causes are contradictory, return confidence = 0.0 and a placeholder failure_mode like "(insufficient signal)".`;

type AnyRow = Record<string, unknown>;

interface LogEntry {
  id?:               string;
  problem?:          string | null;
  action?:           string | null;
  root_cause?:       string | null;
  failure_consequence?: string | null;
  downtime_hours?:   number | null;
  created_at?:       string;
}

// ─── Rate-limit gate (canonical pattern) ──────────────────────────────────────

async function checkAIRateLimit(
  db: SupabaseClient, hiveId: string, limitPerHour: number,
): Promise<{ allowed: boolean; remaining: number }> {
  const windowStart = new Date(Date.now() - 60 * 60 * 1000);
  const { data } = await db.from("ai_rate_limits")
    .select("call_count, window_start").eq("hive_id", hiveId).maybeSingle();
  if (!data || new Date(data.window_start) < windowStart) {
    await db.from("ai_rate_limits").upsert({
      hive_id: hiveId, call_count: 1, window_start: new Date().toISOString(),
    });
    return { allowed: true, remaining: limitPerHour - 1 };
  }
  if (data.call_count >= limitPerHour) return { allowed: false, remaining: 0 };
  await db.from("ai_rate_limits")
    .update({ call_count: data.call_count + 1 }).eq("hive_id", hiveId);
  return { allowed: true, remaining: limitPerHour - data.call_count - 1 };
}

// ─── Asset lookup via v_asset_truth (canonical) ──────────────────────────────

async function fetchAsset(db: SupabaseClient, hiveId: string, assetId: string) {
  const { data } = await db.from("v_asset_truth")
    .select("asset_id, tag, name, iso_class, legacy_asset_id")
    .eq("hive_id", hiveId).eq("asset_id", assetId).maybeSingle();
  return data;
}

// ─── Cluster logbook entries by root_cause ───────────────────────────────────

function normaliseRootCause(rc: string | null | undefined): string {
  return String(rc ?? "").trim().toLowerCase();
}

function clusterByRootCause(rows: LogEntry[]): Map<string, LogEntry[]> {
  const groups = new Map<string, LogEntry[]>();
  for (const r of rows) {
    const key = normaliseRootCause(r.root_cause);
    if (!key || key === "unknown" || key === "other") continue;
    const arr = groups.get(key) || [];
    arr.push(r);
    groups.set(key, arr);
  }
  return groups;
}

// ─── Build the per-cluster prompt payload ────────────────────────────────────

function buildClusterPayload(
  rootCause: string,
  entries: LogEntry[],
  asset: AnyRow,
) {
  const sample = entries.slice(0, ENTRY_CAP_PER_CLUSTER).map(e => ({
    when:    e.created_at,
    problem: String(e.problem || "").slice(0, PROBLEM_SNIPPET_CHARS),
    action:  String(e.action  || "").slice(0, ACTION_SNIPPET_CHARS),
    failure_consequence: e.failure_consequence ?? null,
    downtime_hours:      e.downtime_hours ?? null,
  }));
  return {
    asset: {
      tag:       asset?.tag ?? null,
      name:      asset?.name ?? null,
      iso_class: asset?.iso_class ?? null,
    },
    cluster: {
      root_cause:    rootCause,
      cluster_count: entries.length,
      window_days:   DEFAULT_SINCE_DAYS,
      sample,
    },
  };
}

// ─── One AI call per cluster ─────────────────────────────────────────────────

async function classifyCluster(
  rootCause: string, entries: LogEntry[], asset: AnyRow,
): Promise<AnyRow | null> {
  const payload = buildClusterPayload(rootCause, entries, asset);
  let raw: string;
  try {
    raw = await callAI(JSON.stringify(payload), {
      systemPrompt: FMEA_SYSTEM_PROMPT,
      temperature:  0.2,
      maxTokens:    MAX_TOKENS_OUT,
      jsonMode:     true,
    });
  } catch {
    return null;
  }
  let parsed: AnyRow;
  try {
    parsed = JSON.parse(raw) as AnyRow;
  } catch {
    return null;
  }
  // Validate required fields and clamp ranges.
  const fm = String(parsed.failure_mode || "").trim();
  if (!fm) return null;
  const clampInt = (v: unknown, lo: number, hi: number): number | null => {
    const n = Math.round(Number(v));
    if (!Number.isFinite(n)) return null;
    return Math.max(lo, Math.min(hi, n));
  };
  return {
    function:          String(parsed.function || "").trim() || "(unspecified)",
    failure_mode:      fm,
    effect:            String(parsed.effect || "").trim() || null,
    cause:             String(parsed.cause  || "").trim() || rootCause,
    consequence_class: ["safety","production","environment","quality","cost"].includes(String(parsed.consequence_class))
                         ? parsed.consequence_class : null,
    severity:          clampInt(parsed.severity,   1, 10),
    occurrence:        clampInt(parsed.occurrence, 1, 10),
    detection:         clampInt(parsed.detection,  1, 10),
    confidence:        Math.max(0, Math.min(1, Number(parsed.confidence) || 0)),
  };
}

// ─── Handler ─────────────────────────────────────────────────────────────────

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  try {
    const body = await req.json().catch(() => ({}));
    const hive_id    = String(body.hive_id || "").trim();
    const asset_id   = String(body.asset_id || "").trim();
    const since_days = Number(body.since_days) || DEFAULT_SINCE_DAYS;
    const force      = !!body.force;

    if (!hive_id) {
      return new Response(
        JSON.stringify({ error: "Missing required field: hive_id" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }
    if (!asset_id) {
      return new Response(
        JSON.stringify({ error: "Missing required field: asset_id" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    const db = createClient(
      Deno.env.get("SUPABASE_URL") || "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "",
    );

    // Rate-limit gate FIRST.
    const rl = await checkAIRateLimit(db, hive_id, RATE_LIMIT_PER_HOUR);
    if (!rl.allowed) {
      return new Response(
        JSON.stringify({ error: "AI call limit reached for this hive. Try again in an hour." }),
        { status: 429, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    // Resolve asset via canonical view.
    const asset = await fetchAsset(db, hive_id, asset_id);
    if (!asset) {
      return new Response(
        JSON.stringify({ error: "Asset not found in this hive." }),
        { status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    // Phase 5b: filter by canonical asset_node_id (uuid). The legacy_asset_id
    // text bridge was dropped; asset_id IS the asset_node uuid.
    const sinceIso = new Date(Date.now() - since_days * 86400000).toISOString();

    const { data: rows, error: logErr } = await db.from("v_logbook_truth")  // canonical
      .select("id, problem, action, root_cause, failure_consequence, downtime_hours, created_at, maintenance_type")
      .eq("hive_id", hive_id)
      .eq("asset_node_id", asset_id)
      .gte("created_at", sinceIso)
      .order("created_at", { ascending: false })
      .limit(200);
    if (logErr) {
      return new Response(
        JSON.stringify({ error: "Logbook query failed", detail: logErr.message }),
        { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }
    const corrective = (rows || []).filter(r => /corrective|breakdown/i.test(String(r.maintenance_type || "")));

    // Cluster.
    const groups = clusterByRootCause(corrective);
    const candidates = [...groups.entries()]
      .filter(([_, arr]) => arr.length >= MIN_CLUSTER_SIZE)
      .sort((a, b) => b[1].length - a[1].length)
      .slice(0, MAX_CLUSTERS_PER_RUN);

    if (!candidates.length) {
      return new Response(
        JSON.stringify({
          suggestions_inserted: 0,
          clusters_seen:        groups.size,
          skipped_existing:     0,
          asset_tag:            (asset as AnyRow).tag,
          remaining:            rl.remaining,
          note:                 `No root_cause cluster has >= ${MIN_CLUSTER_SIZE} occurrences in the last ${since_days} days.`,
        }),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    // Skip clusters that already have an FMEA mode for this asset (unless force=true).
    let existingModes: string[] = [];
    if (!force) {
      const { data: existing } = await db.from("rcm_fmea_modes")
        .select("failure_mode, cause_text")
        .eq("hive_id", hive_id).eq("asset_id", asset_id);
      existingModes = (existing || []).map(r =>
        (String(r.failure_mode || "") + "|" + String(r.cause_text || "")).toLowerCase(),
      );
    }

    // Classify clusters in parallel via Promise.allSettled (ai-engineer skill).
    const classifications = await Promise.allSettled(
      candidates.map(([rc, arr]) => classifyCluster(rc, arr, asset as AnyRow)),
    );

    const toInsert: AnyRow[] = [];
    let skipped_existing = 0;
    for (let i = 0; i < classifications.length; i++) {
      const c = classifications[i];
      const [rootCause, entries] = candidates[i];
      if (c.status !== "fulfilled" || !c.value) continue;
      const v = c.value;

      // Skip if an FMEA row with same failure_mode + cause already exists.
      const dupKey = (String(v.failure_mode) + "|" + String(v.cause)).toLowerCase();
      if (!force && existingModes.includes(dupKey)) {
        skipped_existing++;
        continue;
      }
      // Drop very-low-confidence rows entirely; the engineer can rerun later.
      if (Number(v.confidence) < 0.2) continue;

      toInsert.push({
        hive_id,
        asset_id,
        function_text:     v.function,
        failure_mode:      v.failure_mode,
        effect_text:       v.effect,
        cause_text:        v.cause || rootCause,
        consequence_class: v.consequence_class,
        severity:          v.severity,
        occurrence:        v.occurrence,
        detection:         v.detection,
        source:            "ai_logbook",
        ai_confidence:     v.confidence,
        // approved_by / approved_at left NULL: engineer must validate before
        // the row appears in v_fmea_truth and counts in dashboards.
      });
    }

    let suggestions_inserted = 0;
    if (toInsert.length) {
      const { error: insertErr } = await db.from("rcm_fmea_modes").insert(toInsert);
      if (insertErr) {
        return new Response(
          JSON.stringify({ error: "Insert failed", detail: insertErr.message }),
          { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } },
        );
      }
      suggestions_inserted = toInsert.length;
    }

    return new Response(
      JSON.stringify({
        suggestions_inserted,
        clusters_seen:    groups.size,
        candidates_run:   candidates.length,
        skipped_existing,
        asset_tag:        (asset as AnyRow).tag,
        remaining:        rl.remaining,
      }),
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
