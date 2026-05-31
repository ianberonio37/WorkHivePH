/**
 * cold-archive.ts — pure, dependency-free helpers for cold-archive-query.
 *
 * Quarter-label math and range-overlap logic, kept out of the edge fn so it
 * stays unit-testable in isolation (no Deno / Supabase / hyparquet imports
 * here). The exporter writes one Parquet per (hive, quarter, table) at
 *   archive/{hive_id}/{YYYY-Qn}/{table}.parquet
 * so answering a time-ranged query means: list the hive's quarters, keep the
 * ones that overlap the requested range, read only those files.
 */

export interface DateRange {
  /** inclusive ISO date, e.g. "2023-02-01" */
  from: string;
  /** inclusive ISO date, e.g. "2023-08-31" */
  to: string;
}

const QUARTER_RE = /^(\d{4})-Q([1-4])$/;

/** True if `label` is a well-formed quarter label like "2024-Q1". */
export function isQuarterLabel(label: string): boolean {
  return QUARTER_RE.test(label);
}

/**
 * Parse a quarter label into its inclusive [from, to] ISO date bounds.
 *   "2024-Q1" -> ["2024-01-01", "2024-03-31"]
 *   "2024-Q4" -> ["2024-10-01", "2024-12-31"]
 * Throws on a malformed label so callers fail loudly rather than silently
 * skipping data.
 */
export function quarterToRange(quarter: string): [string, string] {
  const m = QUARTER_RE.exec(quarter);
  if (!m) throw new Error(`cold-archive: bad quarter label "${quarter}"`);
  const y = Number(m[1]);
  const q = Number(m[2]);
  const startMonth = (q - 1) * 3 + 1;            // 1, 4, 7, 10
  const endMonth = startMonth + 2;               // 3, 6, 9, 12
  // Day 0 of (1-based endMonth) in JS Date == last day of that month.
  const lastDay = new Date(Date.UTC(y, endMonth, 0)).getUTCDate();
  const mm = (n: number) => String(n).padStart(2, "0");
  return [`${y}-${mm(startMonth)}-01`, `${y}-${mm(endMonth)}-${mm(lastDay)}`];
}

/**
 * Does the quarter overlap the requested range? ISO date strings compare
 * lexicographically, so plain string comparison is correct here.
 * Overlap iff quarter.from <= range.to AND quarter.to >= range.from.
 */
export function quarterOverlapsRange(quarter: string, range: DateRange): boolean {
  const [qFrom, qTo] = quarterToRange(quarter);
  return qFrom <= range.to && qTo >= range.from;
}

/**
 * From the quarter labels actually present in storage, return those that
 * overlap the requested range, de-duplicated and sorted ascending (oldest
 * first). Non-quarter entries (stray files, other folders) are ignored.
 */
export function selectRelevantQuarters(available: string[], range: DateRange): string[] {
  const seen = new Set<string>();
  for (const q of available) {
    if (isQuarterLabel(q) && quarterOverlapsRange(q, range)) seen.add(q);
  }
  return [...seen].sort();
}
