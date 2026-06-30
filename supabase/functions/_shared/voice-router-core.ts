/**
 * voice-router-core — the DETERMINISTIC half of the Voice Action Router.
 * =====================================================================
 * The router has two halves: a probabilistic LLM intent-classifier (lives in
 * voice-action-router/index.ts, needs a live model to test) and the pure,
 * deterministic guard/selection layer below. THIS file is the deterministic
 * half — it takes the LLM's raw JSON (or a list of asset candidates) and
 * applies fixed rules whose correctness can be proven by a value-oracle with
 * NO model call. Extracted to _shared so the edge function imports the exact
 * same code the test exercises — one source, zero drift (Arc H H2 oracle).
 *
 * Two pure functions:
 *   sanitiseIntents()      — validates kind, clamps confidence, enforces the
 *                            slot-fill guard (asset-required intent w/ no asset
 *                            is demoted below the confirmation floor).
 *   pickPrimaryCandidate() — deterministic asset disambiguation:
 *                            page-context → exact match → single → ambiguous.
 *
 * Tested by tests/voice-router-determinism.spec.ts (the H2 routing oracle).
 */

// ─── Types ────────────────────────────────────────────────────────────────────

export interface AssetCandidate {
  asset_id: string;
  tag:      string;
  name:     string;
  hive_id:  string;
}

export interface VoiceIntent {
  kind:        string;
  confidence:  number;
  params:      Record<string, unknown>;
}

// ─── Routing contract constants ────────────────────────────────────────────────

// The only intent kinds the router will emit. Anything else from the model is
// dropped (the LLM cannot invent a new executable action class).
export const VALID_KINDS = new Set([
  "logbook.create",
  "inventory.deduct",
  "pm.complete",
  "asset.lookup",
  "query.ask",
  "unknown",
]);

// Slot-fill guard (WAT, 2026-06-12): a write/lookup intent that names NO asset
// cannot be executed — a live A3 probe found "log a failure" (no machine) routed
// to a confident logbook.create @0.8 with machine=null, which would write a junk
// logbook entry against no asset. The router prompt already asks the LLM to be
// conservative, but it does not reliably demote a param-less write. So we enforce
// it deterministically here (WAT: the gate is code, not the model's confidence):
// for kinds whose REQUIRED slot is the asset, a missing/blank machine demotes
// confidence below the 0.5 confirmation floor so the page slot-fills ("which
// asset?") instead of silently writing. inventory.deduct is intentionally NOT in
// this set — its required slot is the part, not the machine (e.g. "pulled two
// seals from stock"), so guarding it on machine would break valid deductions.
export const ASSET_REQUIRED_KINDS = new Set(["logbook.create", "pm.complete", "asset.lookup"]);
export const SLOT_FILL_CEILING = 0.45; // just under the 0.5 confirmation floor

// ─── Validate / sanitise the AI's parsed JSON ──────────────────────────────────

export function sanitiseIntents(parsed: unknown): { intents: VoiceIntent[]; mentioned: string[] } {
  const obj = (parsed && typeof parsed === "object") ? parsed as Record<string, unknown> : {};
  const rawIntents = Array.isArray(obj.intents) ? obj.intents : [];
  const intents: VoiceIntent[] = [];

  for (const r of rawIntents) {
    const ri = (r && typeof r === "object") ? r as Record<string, unknown> : {};
    const kind = String(ri.kind || "unknown");
    if (!VALID_KINDS.has(kind)) continue;
    const conf = typeof ri.confidence === "number" ? ri.confidence : 0;
    const params = (ri.params && typeof ri.params === "object")
      ? ri.params as Record<string, unknown>
      : {};
    let confidence = Math.max(0, Math.min(1, conf));
    // Slot-fill demotion: asset-required intent with no machine -> below floor.
    const machine = params.machine;
    const hasAsset = typeof machine === "string" && machine.trim().length > 0;
    if (ASSET_REQUIRED_KINDS.has(kind) && !hasAsset) {
      confidence = Math.min(confidence, SLOT_FILL_CEILING);
      params._needs_asset = true; // hint for the page to ask "which asset?"
    }
    intents.push({ kind, confidence, params });
  }

  const mentioned = Array.isArray(obj.mentioned_assets)
    ? obj.mentioned_assets.filter((m: unknown) => typeof m === "string" && m.trim().length)
    : [];

  return { intents, mentioned: Array.from(new Set(mentioned as string[])) };
}

// ─── Deterministic asset disambiguation ────────────────────────────────────────

export function pickPrimaryCandidate(
  candidates: AssetCandidate[],
  contextAssetId: string | null,
  mentioned: string[],
): { primary?: AssetCandidate; ambiguous: boolean } {
  if (!candidates.length) return { ambiguous: false };

  // 1. Page context wins if its asset_id appears in candidates.
  if (contextAssetId) {
    const ctx = candidates.find(c => c.asset_id === contextAssetId);
    if (ctx) return { primary: ctx, ambiguous: false };
  }

  // 2. Exact case-insensitive tag match wins next.
  for (const m of mentioned) {
    const lower = m.toLowerCase();
    const exact = candidates.find(
      c => (c.tag || "").toLowerCase() === lower || (c.name || "").toLowerCase() === lower,
    );
    if (exact) return { primary: exact, ambiguous: false };
  }

  // 3. Single candidate wins by default.
  if (candidates.length === 1) return { primary: candidates[0], ambiguous: false };

  // 4. Multiple candidates and no clear winner: ambiguous, page asks user.
  return { primary: candidates[0], ambiguous: true };
}
