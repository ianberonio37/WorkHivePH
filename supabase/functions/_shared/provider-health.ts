// _shared/provider-health.ts
// Provider health autoswitch — memory of recent provider failures.
// Extracted from ai-chain.ts so validate_groq_fallback.py's regex doesn't
// mis-parse helper function bodies as malformed PROVIDER_CHAIN entries.
//
// P1 roadmap 2026-05-27 turn 7 (C/GH cell).
//
// Semantics:
//   - If a slot returns ≥N failures within M seconds, skip it for K seconds.
//   - The "slot" is the upstream service identifier (groq / cerebras /
//     openrouter), not the specific model — when Groq throttles, all Groq
//     models throttle together.
//   - Per-warm-container memory only. Cold starts reset.
//
// Free-tier exhaustion (the #1 RAG flywheel failure mode) is exactly this
// pattern: a slot returns 429 for several minutes, but every call still
// burns a full retry against it. With autoswitch, after 3 failures in 30s
// the slot is marked unhealthy for 60s and the chain skips straight to the
// next slot.

interface SlotHealth {
  failures:      number[];   // unix-ms timestamps of recent failures
  blocked_until: number;     // unix-ms; 0 = available
}
const slotHealth: Map<string, SlotHealth> = new Map();

const FAILURE_WINDOW_MS = 30_000;
const FAILURE_THRESHOLD = 3;
const BLOCK_DURATION_MS = 60_000;

export function recordSlotFailure(slotName: string): void {
  const now = Date.now();
  let h = slotHealth.get(slotName);
  if (!h) { h = { failures: [], blocked_until: 0 }; slotHealth.set(slotName, h); }
  h.failures = h.failures.filter((t) => now - t < FAILURE_WINDOW_MS);
  h.failures.push(now);
  if (h.failures.length >= FAILURE_THRESHOLD) {
    h.blocked_until = now + BLOCK_DURATION_MS;
    h.failures = [];
  }
}

export function recordSlotSuccess(slotName: string): void {
  const h = slotHealth.get(slotName);
  if (!h) return;
  h.failures = [];
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

export function getSlotHealthSnapshot(): Record<string, SlotHealth> {
  const out: Record<string, SlotHealth> = {};
  for (const [k, v] of slotHealth) {
    out[k] = { failures: v.failures.slice(), blocked_until: v.blocked_until };
  }
  return out;
}
