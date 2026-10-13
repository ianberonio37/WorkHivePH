// _shared/memory_age.ts
// How long ago a remembered turn was said, as a plain DURATION ("6 days ago"), for every memory block a model reads.
//
// ★WHEN, NOT ONLY WHAT (2026-10-13, voice-journal audio walk W4812): a returning worker said "Maintenance" and was told
// "Hala, you've asked this four times today". The four questions were SIX DAYS old. Nothing in the prompt said when any
// remembered turn happened: "Recent turns" carried no time at all, and no prompt states the current date, so the model
// read last week's turns as this morning's. The same reply, given on the day they were asked, had been true.
//
// A duration, never a calendar word ("today", "yesterday"): the hive's day is neither the server's (UTC) nor the
// device's, so a calendar claim is wrong across midnight, while "6 days ago" is true in every timezone. No digit run
// long enough for the PII phone scrub to swallow (redactPII.ts PHONE_RE needs 10+ digits/separators).
// No imports, so tools/prove_memory_age.mjs runs it, and the two formatters that use it, from Node.

export function ageLabel(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "";
  const mins = Math.floor((now.getTime() - t) / 60000);
  if (mins < 0) return "";                     // a clock ahead of ours claims nothing
  if (mins < 2) return "just now";
  if (mins < 60) return `${mins} minutes ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return hours === 1 ? "1 hour ago" : `${hours} hours ago`;
  const days = Math.floor(hours / 24);
  if (days < 14) return days === 1 ? "1 day ago" : `${days} days ago`;
  if (days < 60) return `${Math.floor(days / 7)} weeks ago`;
  return `${Math.floor(days / 30)} months ago`;
}

// ★IN WHAT ORDER (2026-10-13, the same echo): saveTurn writes a question and its answer in ONE insert, so both rows
// carry the same created_at (one now()), and Postgres returns a tie in any order. The memory block a model read listed
// "Agent, Agent, Worker, Worker, Agent, Worker, Agent" under "oldest first" - answers before their questions. A tie is a
// pair, and in a pair the person spoke first.
export function turnOrder(
  a: { created_at?: string | null; role?: string | null },
  b: { created_at?: string | null; role?: string | null },
): number {
  const ta = Date.parse(a.created_at || "") || 0;
  const tb = Date.parse(b.created_at || "") || 0;
  if (ta !== tb) return ta - tb;
  return (a.role === "agent" ? 1 : 0) - (b.role === "agent" ? 1 : 0);
}

// The oldest n turns to fold into the rolling summary, WITHOUT CUTTING A PAIR: the summariser took the oldest 5 rows,
// an odd count, so every collapse left half an exchange behind - an answer whose question was summarised away (seen
// live, 2026-10-07 02:54) or a question with no answer. Rows arrive oldest first (ties in any order) and may run one
// past n, so the cut moves forward while the next row shares the last kept row's moment.
export function oldestWholeTurns<T extends { created_at?: string | null; meta?: unknown }>(rows: T[], n: number): T[] {
  const role = (r: T) => ((r.meta as Record<string, unknown> | null)?.role === "agent" ? "agent" : "user");
  const sorted = [...rows].sort((a, b) =>
    turnOrder({ created_at: a.created_at, role: role(a) }, { created_at: b.created_at, role: role(b) }));
  let k = Math.min(n, sorted.length);
  while (k > 0 && k < sorted.length && sorted[k].created_at === sorted[k - 1].created_at) k++;
  return sorted.slice(0, k);
}
