// _shared/provider-health.ts
// Provider health autoswitch — memory of recent provider failures.
// Extracted from ai-chain.ts so validate_groq_fallback.py's regex doesn't
// mis-parse helper function bodies as malformed PROVIDER_CHAIN entries.
//
// P1 roadmap 2026-05-27 turn 7 (C/GH cell).
//
// Semantics:
//   - If a slot returns >=N failures within M seconds, skip it for a cooldown.
//   - The "slot" is the upstream service identifier (groq / cerebras /
//     openrouter / google / mistral), not the specific model — when Groq
//     throttles, all Groq models throttle together.
//   - Per-warm-container memory only. Cold starts reset.
//
// Free-tier exhaustion (the #1 RAG flywheel failure mode) is exactly this
// pattern: a slot returns 429 for several minutes, but every call still
// burns a full retry against it. With autoswitch, after 3 failures in 30s
// the slot is marked unhealthy and the chain skips straight to the next slot.
//
// ── 2026-05-30: ESCALATING COOLDOWN (borrowed from FreeLLMAPI) ───────────────
// A flat 60s block is right for a transient minute-level throttle (RPM/TPM),
// but WRONG for daily-quota exhaustion: OpenRouter free is ~200 req/day and
// only resets at UTC midnight. A flat block expires after 60s, the next
// request burns another full retry against the dead slot, re-blocks for 60s,
// and the cycle repeats — consuming a fallback slot on every request for the
// rest of the day. This is the turns-34-73 -> 0% collapse in the RAG flywheel.
//
// Fix: the block DURATION escalates with how many times this slot has been
// blocked in a rolling 24h window: 60s -> 10min -> 1hr -> 6hr. A genuinely
// exhausted slot parks itself for hours after a few cycles instead of looping;
// a transient throttle (which produces a success on the next attempt) resets
// the ladder via recordSlotSuccess. Memory-only, so a cold start re-escalates
// from rung 0 — acceptable, because a fresh container re-discovers exhaustion
// within its first few calls.

interface SlotHealth {
  failures:        number[];   // unix-ms timestamps of recent failures
  blocked_until:   number;     // unix-ms; 0 = available
  block_hits:      number[];   // unix-ms timestamps of recent BLOCK events (rolling 24h) — drives escalation
  penalty:         number;     // soft priority demotion (FreeLLMAPI dynamic-priority idea)
  penalty_updated: number;     // unix-ms of last penalty change — drives time-decay
}
const slotHealth: Map<string, SlotHealth> = new Map();

function newSlot(): SlotHealth {
  return { failures: [], blocked_until: 0, block_hits: [], penalty: 0, penalty_updated: 0 };
}

const FAILURE_WINDOW_MS = 30_000;
const FAILURE_THRESHOLD = 3;

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

// ── Dynamic priority (borrowed from FreeLLMAPI router.ts) ────────────────────
// Each failure adds PENALTY_PER_FAILURE to the slot's penalty (capped at
// MAX_PENALTY); the penalty decays by 1 every PENALTY_DECAY_INTERVAL_MS. The
// chain (reorderChain in ai-chain.ts) stable-sorts by this penalty so a flaky
// slot sinks in the order but is NOT hard-skipped (that's what blocked_until
// is for). A success reduces the penalty so a recovered slot rises back up.
const PENALTY_PER_FAILURE = 3;
const MAX_PENALTY = 10;
const PENALTY_DECAY_INTERVAL_MS = 2 * MINUTE;

// Returns the penalty after applying time-decay, WITHOUT mutating the slot.
function decayedPenalty(h: SlotHealth, now: number): number {
  if (h.penalty <= 0) return 0;
  const steps = Math.floor((now - h.penalty_updated) / PENALTY_DECAY_INTERVAL_MS);
  if (steps <= 0) return h.penalty;
  return Math.max(0, h.penalty - steps);
}

// Escalating block durations, indexed by how many times this slot has already
// been blocked in the last 24h (0-based). The last rung is the cap.
const COOLDOWN_LADDER_MS = [
  1 * MINUTE,    // 1st block in 24h — transient throttle, recover fast
  10 * MINUTE,   // 2nd — looks sustained
  1 * HOUR,      // 3rd — likely daily-quota exhaustion
  6 * HOUR,      // 4th and beyond — parked until well past most free-tier resets
];

function pruneTo24h(timestamps: number[], now: number): number[] {
  return timestamps.filter((t) => now - t < DAY);
}

export function recordSlotFailure(slotName: string): void {
  const now = Date.now();
  let h = slotHealth.get(slotName);
  if (!h) { h = newSlot(); slotHealth.set(slotName, h); }
  h.failures = h.failures.filter((t) => now - t < FAILURE_WINDOW_MS);
  h.failures.push(now);
  // Soft demotion: bump penalty on every failure (decay first so it is current).
  h.penalty = Math.min(decayedPenalty(h, now) + PENALTY_PER_FAILURE, MAX_PENALTY);
  h.penalty_updated = now;
  if (h.failures.length >= FAILURE_THRESHOLD) {
    // Choose duration based on how many blocks this slot has had in the last 24h.
    h.block_hits = pruneTo24h(h.block_hits, now);
    const rung = Math.min(h.block_hits.length, COOLDOWN_LADDER_MS.length - 1);
    const duration = COOLDOWN_LADDER_MS[rung]!;
    h.blocked_until = now + duration;
    h.block_hits.push(now);
    h.failures = [];
  }
}

export function recordSlotSuccess(slotName: string): void {
  const h = slotHealth.get(slotName);
  if (!h) return;
  const now = Date.now();
  // A success means the slot recovered — clear recent failures AND reset the
  // escalation ladder so a later transient throttle starts at rung 0 again.
  h.failures = [];
  h.block_hits = [];
  // Ease the soft-priority penalty so a recovered slot rises back up the order.
  h.penalty = Math.max(0, decayedPenalty(h, now) - 1);
  h.penalty_updated = now;
}

// Current soft-priority penalty for a slot (0 = healthy). Applies time-decay
// and persists it so repeated reads don't recompute from a stale base.
// Used by reorderChain to demote flaky slots without hard-skipping them.
export function getSlotPenalty(slotName: string): number {
  const h = slotHealth.get(slotName);
  if (!h) return 0;
  const now = Date.now();
  const p = decayedPenalty(h, now);
  if (p !== h.penalty) { h.penalty = p; h.penalty_updated = now; }
  return p;
}

export function isSlotBlocked(slotName: string): boolean {
  const h = slotHealth.get(slotName);
  if (!h) return false;
  if (h.blocked_until === 0) return false;
  if (Date.now() >= h.blocked_until) {
    h.blocked_until = 0;
    return false;
  }
  return true;
}

export function getSlotHealthSnapshot(): Record<string, SlotHealth & { escalation_rung: number }> {
  const now = Date.now();
  const out: Record<string, SlotHealth & { escalation_rung: number }> = {};
  for (const [k, v] of slotHealth) {
    const liveHits = pruneTo24h(v.block_hits, now);
    out[k] = {
      failures:      v.failures.slice(),
      blocked_until: v.blocked_until,
      block_hits:    liveHits,
      penalty:       decayedPenalty(v, now),
      penalty_updated: v.penalty_updated,
      escalation_rung: Math.min(liveHits.length, COOLDOWN_LADDER_MS.length) ,
    };
  }
  return out;
}

// ── Sticky sessions (borrowed from FreeLLMAPI) ───────────────────────────────
// Multi-turn conversations should keep talking to the SAME model for a while:
// switching models mid-conversation causes a quality/voice/hallucination spike
// (a model that didn't generate the earlier turns has to "adopt" them). The
// chain otherwise re-picks from the top on every callAI, so a momentary blip on
// the turn-1 model silently moves turn-2 to a different model.
//
// A caller passes a stable sessionKey (e.g. `${hive_id}:${worker_name}:${agent}`)
// to callAI. On success the serving model is pinned to that key; on the next
// turn within STICKY_TTL_MS, callAI tries the pinned model FIRST — unless it is
// hard-blocked (isSlotBlocked still wins, so a dead pin falls through and the
// conversation migrates to a healthy model, which then becomes the new pin).
// Per-warm-container memory only; cold starts reset (the next turn re-pins).
interface StickyEntry { provider: string; model: string; ts: number; }
const stickySessions = new Map<string, StickyEntry>();
const STICKY_TTL_MS = 30 * MINUTE;
const STICKY_MAX = 5000;   // memory guard for a long-lived warm container

export function getStickyModel(sessionKey: string): { provider: string; model: string } | null {
  const e = stickySessions.get(sessionKey);
  if (!e) return null;
  if (Date.now() - e.ts > STICKY_TTL_MS) { stickySessions.delete(sessionKey); return null; }
  return { provider: e.provider, model: e.model };
}

export function setStickyModel(sessionKey: string, provider: string, model: string): void {
  // Crude LRU-ish eviction: if the map is full and this is a new key, drop the
  // oldest-inserted entry (Map preserves insertion order).
  if (stickySessions.size >= STICKY_MAX && !stickySessions.has(sessionKey)) {
    const oldest = stickySessions.keys().next().value;
    if (oldest !== undefined) stickySessions.delete(oldest);
  }
  stickySessions.set(sessionKey, { provider, model, ts: Date.now() });
}
