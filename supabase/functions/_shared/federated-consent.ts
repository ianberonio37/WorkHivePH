// federated-consent.ts - WHICH hives may contribute to anything published across hives (2026-10-08).
//
// ★A DECLARED CONSENT THAT NOTHING ENFORCED. hives.federated_benchmark_opted_in (migration 20260513000007, Phase 6D)
// says it plainly: "per-hive consent to contribute anonymised metrics to the national PH Industry Benchmarks data
// product. Default false; supervisor toggles." No page let a supervisor toggle it, and no reader checked it:
// benchmark-compute published every hive's MTBF into network_benchmarks, intelligence-report counted every hive's
// work orders, quoted every hive's root causes and low-stock parts, and intelligence-api sold the root causes to API
// key holders - for hives that had all said nothing (every hive was false). A synthetic eval hive's fixtures fed the
// national figures too. Every cross-hive aggregate now reads its contributors through this file.
//
//   consentedHiveIds(db)  the hives whose supervisor opted in; a read that fails THROWS (fail closed - an
//                         unreadable consent is never treated as "everyone")
//   hiveFilter(ids)       the list to pass to .in("hive_id", ...): an empty consent becomes a list that matches no
//                         hive, never an absent filter
//   MIN_CONSENTING_HIVES  below this, nothing cross-hive is published at all (one or two hives' figures are
//                         that hive's figures, however "aggregated")
import type { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2.110.0";

export const MIN_CONSENTING_HIVES = 3;
const NO_HIVE = "00000000-0000-0000-0000-000000000000";

export async function consentedHiveIds(db: SupabaseClient): Promise<string[]> {
  // canonical-allow: the consent flag lives only on hives (v_hives_truth does not carry federated_benchmark_opted_in)
  const { data, error } = await db.from("hives")
    .select("id")
    .eq("federated_benchmark_opted_in", true)
    .order("id")
    .limit(10000);   // cap-ok: hive ids only; the platform's hive count is far below this
  if (error) throw new Error("could not read which hives consent to shared benchmarks: " + error.message);
  return (data || []).map((r: { id: string }) => r.id);
}

export function hiveFilter(ids: string[]): string[] {
  return ids.length ? ids : [NO_HIVE];
}
