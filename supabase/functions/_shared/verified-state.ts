// _shared/verified-state.ts
//
// Shared-memory layer 07 ("one truth, every agent aligned"). Reads the
// verified current state of an asset from v_asset_state_truth — the view
// (migration 20260530000000) that resolves competing unified_events into ONE
// winning event per (hive, asset, event_type) by source trust precedence then
// recency. Every conversational agent reads through THIS module so they all
// agree on "the current state of asset X" instead of each picking an arbitrary
// competing event.
//
// Pure DB read (no LLM). security_invoker on the view means the querying
// client's hive RLS still applies — pass the admin client from a server-side
// caller that has already authorised the hive.

import { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";

export const VERIFIED_STATE_LIMIT = 12;
export const VERIFIED_TEXT_CHARS   = 200;

export interface VerifiedStateRow {
  hive_id:               string;
  asset_tag:             string;
  event_type:            string;
  verified_source:       string;
  verified_source_rank:  number;
  source_id:             string;
  verified_at:           string;
  verified_payload:      Record<string, unknown> | null;
  verified_text:         string | null;
  conflict_count:        number;
  superseded_count:      number;
  ingested_at:           string;
}

/**
 * Resolve the verified current state for a hive (optionally one asset). Returns
 * one row per (asset_tag, event_type) — the winning event after conflict
 * resolution. Best-effort: any error returns [] so the agent still answers.
 */
export async function resolveAssetState(
  db: SupabaseClient,
  hiveId: string,
  opts: { assetTag?: string | null; eventType?: string | null; limit?: number } = {},
): Promise<VerifiedStateRow[]> {
  if (!hiveId) return [];
  const limit = Math.min(50, Math.max(1, Number(opts.limit ?? VERIFIED_STATE_LIMIT)));

  // canonical-allow: v_asset_state_truth is the registered verified-state surface.
  let q = db.from("v_asset_state_truth")
    .select("hive_id, asset_tag, event_type, verified_source, verified_source_rank, source_id, verified_at, verified_payload, verified_text, conflict_count, superseded_count, ingested_at")
    .eq("hive_id", hiveId)
    .order("verified_at", { ascending: false })
    .limit(limit);
  if (opts.assetTag)  q = q.eq("asset_tag", opts.assetTag);
  if (opts.eventType) q = q.eq("event_type", opts.eventType);

  const { data, error } = await q;
  if (error) { console.warn("[verified-state] query failed:", error.message); return []; }
  return (data || []) as VerifiedStateRow[];
}

/**
 * Render verified-state rows into a prompt block. Flags rows where multiple
 * sources disagreed (superseded_count > 0) so the LLM can say "per the CMMS
 * system of record (other sources differ)" rather than overstating certainty.
 */
export function formatVerifiedState(rows: VerifiedStateRow[]): string {
  if (!rows || !rows.length) return "";
  const lines: string[] = ["Verified asset state (one truth, conflict-resolved across all data sources):"];
  for (const r of rows) {
    const when = (r.verified_at || "").slice(0, 16).replace("T", " ");
    const txt  = (r.verified_text || "").replace(/\s+/g, " ").trim().slice(0, VERIFIED_TEXT_CHARS);
    const flag = r.superseded_count > 0
      ? ` [resolved from ${r.conflict_count} sources via ${r.verified_source}; ${r.superseded_count} superseded]`
      : "";
    lines.push(`- ${r.asset_tag} / ${r.event_type}: ${txt} (${r.verified_source} @ ${when})${flag}`);
  }
  return lines.join("\n");
}
