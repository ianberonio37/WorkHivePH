// ★A SOLO OWNER'S AI ANSWERS NEVER USED THEIR OWN KNOWLEDGE (2026-10-08). Migration 20261007000014 made a hive-less
// person's fault_knowledge rows readable by their owner, and gave search_fault_knowledge / search_all_knowledge an
// own scope (match_hive_id NULL = the caller's own hive-less rows). Neither AI path asked for it: ai-gateway built a
// knowledge block only for hive members, and semantic-search's no-hive path searched on a service-role client with
// no owner - where auth.uid() is NULL, so the own scope named nobody and the search returned nothing, every time.
//
// This is the one place a server function asks "this person's own past repairs" - both callers use it, so the
// scope and the ownership check cannot drift apart between them.
//
//   admin     the SERVICE-ROLE client. search_fault_knowledge honours match_owner only for service_role/postgres; a
//             user-JWT client would be scoped by auth.uid() instead, and anon names nobody.
//   ownerUid  the VERIFIED auth uid of the caller (auth.getUser / resolveIdentity on their own JWT) - never a field
//             from the request body. Empty = no owner = no rows.
//
// Returns null when the search or the ownership re-read could not run (a failed read is not "no knowledge"), [] when
// it ran and found nothing of theirs.
import { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2.110.0";

export type OwnFaultRow = {
  id: string; machine?: string; problem?: string; root_cause?: string; action?: string;
  knowledge?: string; worker_name?: string; similarity?: number;
};

export async function searchOwnFaultKnowledge(
  admin: SupabaseClient, embedding: number[], ownerUid: string | null, count: number,
): Promise<OwnFaultRow[] | null> {
  if (!ownerUid) return [];
  const { data, error } = await admin.rpc("search_fault_knowledge", {
    query_embedding: embedding, match_hive_id: null, match_count: count, match_owner: ownerUid,
  });
  if (error) return null;
  const rows = ((data ?? []) as OwnFaultRow[]).filter((r) => r && r.id);
  if (!rows.length) return [];
  // DEFENSIVE, not the guarantee: the function's own-scope rule already returns only this person's hive-less rows.
  // The search does not return the owner column, so each id is re-read here and kept only if it is hive-less AND
  // bound to this person - a regression in the SQL then shows one person nothing, never another person's repairs.
  const { data: mine, error: ownErr } = await admin.from("v_knowledge_truth").select("id")
    .eq("source", "fault").in("id", rows.map((r) => r.id)).is("hive_id", null).eq("auth_uid", ownerUid);
  if (ownErr) return null;   // ownership unproven = nothing shown
  const owned = new Set(((mine ?? []) as Array<{ id: string }>).map((r) => r.id));
  return rows.filter((r) => owned.has(r.id));
}
