// _shared/numeric_provenance.ts
// ============================================================================
// PHASE G1 - Numeric-provenance gate (Companion Grounding Doctrine §1b).
//
// PRINCIPLE (WorkHive WAT, ai-engineer SKILL.md L822): the LLM PHRASES facts it
// is given; it never AUTHORS numbers. Every number token in a companion answer
// must TRACE to one of:
//   (a/b) the grounded input  - a number present in `groundedContext` (the
//         userBlock = ops-snapshot fact-set + recalled values + the worker's
//         own message). One check covers "fact-set" and "worker-stated".
//   (c)   the curated benchmark table - value present AND benchmark framing in
//         the sentence (so a bare invented "85%" can't masquerade as one).
//   (d)   a TIGHT safe-non-claim allowlist - dates/years, clock times,
//         durations/schedules, ordinals/list-counts. NOTHING else.
// A number tracing to NONE is a current-state fabrication BY CONSTRUCTION -> the
// whole sentence is stripped.
//
// Mode = STRICT (locked 2026-06-14 with Ian): a bare domain-advice unit-constant
// ("torque to ~300 Nm") is NOT in (d); it strips unless it traces to the input
// or the benchmark table. Safety over warmth.
//
// This REPLACES the reactive `stripUngroundedKpi` KPI-keyword rail: we no longer
// enumerate KPI names (that rail leaked on the first unknown framing - the live
// "...41% from a target of 80%" fabrication). We trace EVERY number instead.
//
// Repair = STRIP + honest fallback: this module returns the stripped text; the
// CALLER supplies the honest pointer when the reply collapses (<15 chars).
//
// Eval counterpart lives in tools/companion_fabrication_sweep.py grade() and is
// written from SCRATCH in Python (its own regex + allowlist) so a blind spot in
// this gate is caught by the grader and vice-versa (the correlated-blindspot
// lesson: feedback_rail_grader_correlated_blindspot_2026_06_14).
// ============================================================================

import { BENCHMARK_VALUE_SET } from "./benchmarks.ts";

export interface ProvenanceResult {
  clean:    string;    // answer with untraceable-number sentences removed
  stripped: string[];  // dropped sentences (for cost-log / debugging)
  hit:      boolean;   // true if anything was stripped
}

// A number token: integer, decimal, or comma-grouped. Leading \d anchors on a
// digit; trailing % / units are handled by the allowlist, not here.
const NUM_TOKEN = "\\d[\\d,]*(?:\\.\\d+)?";

// Normalize a raw match to a comparable core: drop thousands commas, keep digits
// and decimal point. "1,234" -> "1234", "85" -> "85", "85.3" -> "85.3".
function normCore(raw: string): string | null {
  const core = raw.replace(/,/g, "");
  return /^\d+(?:\.\d+)?$/.test(core) ? core : null;
}

/** Every normalized number core in a string. Used for BOTH the answer scan and
 *  the grounded-context token set, so matching is symmetric / token-level (a
 *  fabricated `78` cannot trace to a `1780` elsewhere in the snapshot). */
export function extractNumberCores(s: string): string[] {
  const out: string[] = [];
  for (const m of s.matchAll(new RegExp(NUM_TOKEN, "g"))) {
    const c = normCore(m[0]);
    if (c !== null) out.push(c);
  }
  return out;
}

// Benchmark framing - a table value is traceable (c) ONLY with framing.
const BENCHMARK_FRAME =
  /world[- ]class|benchmark|industry|typically|generally|usually|standard|rule of thumb|on average|best[- ]in[- ]class/i;

// ---- The TIGHT safe-non-claim allowlist (d): the ONE central knob -----------
const YEAR_RE  = /^(?:19|20)\d{2}$/;                                        // 1900-2099
const MONTH_RE = /\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)/i;
// time unit immediately after the number (the leading class also eats a range
// dash + 2nd operand, so "3-6 months" marks both 3 and 6 safe).
const DURATION_AFTER =
  /^[\s\-–—to]{0,4}\d{0,4}\s*(?:secs?|seconds?|mins?|minutes?|hrs?|hours?|days?|weeks?|months?|quarters?|years?|yrs?|wks?)\b/i;
const DURATION_SHORTHAND = /^(?:d|w|h|mo|yr|wk)\b/i;                        // 14d 2w 6mo
const ORDINAL_BEFORE =
  /\b(?:top|first|second|third|fourth|fifth|step|phase|tier|level|rank|number|no\.?|#)\s*$/i;
const ORDINAL_AFTER = /^(?:st|nd|rd|th)\b/i;
// SUPPRESSOR of the duration carve-out: a number that is the object of a
// current-state metric assertion ("MTBF is 320 hours") is a fabricated metric,
// not a schedule. This is a small frame SUPPRESSOR, not a KPI re-enumeration -
// it gates ONLY the duration branch; "regrease every 320 hours" (advice) passes.
const CURRENT_STATE_FRAME =
  /\b(?:is|was|were|are|sits?|sitting|running|currently|hovering|holding|reached|reaching|hit|hitting|stands?\s+at)\s*$/i;

function isSafeNonClaim(
  core: string, sentence: string, start: number, end: number, listCounts: Set<string>,
): boolean {
  const before = sentence.slice(Math.max(0, start - 16), start);
  const after  = sentence.slice(end, end + 16);
  if (YEAR_RE.test(core)) return true;                                     // year
  if (/^:\d{2}/.test(after) || /\d{1,2}:\s*$/.test(before)) return true;   // clock HH:MM
  if (/^\s*(?:am|pm|a\.m\.|p\.m\.)\b/i.test(after)) return true;           // 9 am / 9pm
  if (MONTH_RE.test(before) || MONTH_RE.test(after)) return true;          // date by month
  if ((DURATION_AFTER.test(after) || DURATION_SHORTHAND.test(after))       // duration/schedule
      && !CURRENT_STATE_FRAME.test(before)) return true;                   //   (unless current-state framed)
  if (ORDINAL_BEFORE.test(before) || ORDINAL_AFTER.test(after)) return true; // ordinal
  if (listCounts.has(core)) return true;                                   // list-count it actually enumerated
  return false;
}

// Enumeration counts in the whole answer (numbered "1." / "2)" or bullets) so a
// "there are 3 causes" followed by a real 3-item list keeps the 3.
function enumerationCounts(text: string): Set<string> {
  const out = new Set<string>();
  const numbered = [...text.matchAll(/(?:^|\n)\s*(\d{1,2})[.)]\s+/g)]
    .map((m) => parseInt(m[1], 10)).filter((n) => n > 0);
  if (numbered.length) out.add(String(Math.max(...numbered)));
  const bullets = [...text.matchAll(/(?:^|\n)\s*[-*•]\s+/g)].length;
  if (bullets > 0) out.add(String(bullets));
  return out;
}

const SENTENCE_SPLIT = /(?<=[.?!])\s+/;

/**
 * G1 gate. Returns the answer with every sentence that contains an untraceable
 * number removed. `groundedContext` is the userBlock (memory block + the
 * worker's own message) - everything the model was legitimately given.
 */
export function gateNumericProvenance(
  answer: string,
  groundedContext: string,
  benchmarkValues: Set<string> = BENCHMARK_VALUE_SET,
): ProvenanceResult {
  const grounded   = new Set(extractNumberCores(groundedContext));
  const listCounts = enumerationCounts(answer);
  const stripped: string[] = [];

  const kept = answer.split(SENTENCE_SPLIT).filter((sentence) => {
    const isBench = BENCHMARK_FRAME.test(sentence);
    for (const m of sentence.matchAll(new RegExp(NUM_TOKEN, "g"))) {
      const core = normCore(m[0]);
      if (core === null) continue;
      const idx = m.index ?? 0;
      if (grounded.has(core)) continue;                                    // (a/b)
      if (isBench && benchmarkValues.has(core)) continue;                  // (c)
      if (isSafeNonClaim(core, sentence, idx, idx + m[0].length, listCounts)) continue; // (d)
      stripped.push(sentence.trim());                                      // untraceable -> drop sentence
      return false;
    }
    return true;
  });

  const clean = kept.join(" ").replace(/\s+/g, " ").trim();
  return { clean, stripped, hit: stripped.length > 0 };
}
