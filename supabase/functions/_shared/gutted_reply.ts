// _shared/gutted_reply.ts
// ============================================================================
// Gutted-reply resolver (CL2/CL10 deep-walk, live-caught 2026-07-08).
//
// The numeric-provenance gate (G1, numeric_provenance.ts) STRIPS any sentence
// whose number does not trace to the hive snapshot — correct and safety-first:
// a weak free-tier model must never AUTHOR a spec/KPI figure a worker could act
// on (a wrong bolt torque is a hazard; "safety over warmth", locked 2026-06-14).
//
// But the surviving remnant can be an INCOHERENT FRAGMENT. Live walk: the
// floating companion (voice-journal-agent, on 32 pages) answered "what torque
// for an M20 8.8 bolt?" with "…180-220 Nm, cross-pattern, three passes. Check
// the OEM manual though." G1 stripped the value sentence, leaving the > 15-char
// but dangling "Cross-pattern, three passes. Check the OEM manual though." — a
// caveat with no antecedent. The caller only fell back to an honest pointer when
// the remnant collapsed < 15 chars, so the worker saw a broken fragment for the
// MOST COMMON field question (specs).
//
// This module owns the post-gate decision so the EXACT code the unit test
// exercises is the code the agent runs (WAT one-source, zero-drift — same
// discipline as voice-router-core.ts). The number-strip is UNCHANGED; only the
// remnant handling is: a gutted remnant becomes an honest, DOMAIN-AWARE pointer.
// A SPEC ask (torque/clearance/rating…) routes to the deterministic source (OEM
// manual + Engineering Design calculator); anything else keeps the live-metrics
// pointer. Conservative: a coherent grounded remnant is returned UNTOUCHED.
// ============================================================================

import { extractNumberCores } from "./numeric_provenance.ts";

// A spec/how-to question asks for an engineering VALUE the companion must not
// author from a weak model (torque, clearance, winding resistance, setpoint…).
export const SPEC_ASK_RE =
  /\b(?:torque|nm|clearance|tolerance|preload|setpoint|set point|rating|resistance|voltage|amperage|current draw|pressure|psi|bar|viscosity|thread|rpm|runout|alignment|spec|specification|setting|gap|size|dimension|dia(?:meter)?)\b/i;

// Honest, domain-aware pointers (plain language, no em dashes, no jargon).
export const SPEC_POINTER =
  "I can't give you an exact spec number from here safely, a wrong torque or setting can cause a failure. Check the equipment's OEM manual, or open the Engineering Design calculator on WorkHive, it works out bolt torque and many other values to PEC and PSME standards.";
export const METRIC_POINTER =
  "I don't have your exact performance figures on this voice surface. Check the Work Assistant for your live OEE, MTBF, and planned-vs-reactive ratio.";

// A remnant is GUTTED when it opens with a connector that references removed
// content ("Check … though", "But …", a bare imperative fragment) or ends on a
// dangling caveat ("… though.") — either way it reads as a broken fragment.
export function looksGutted(remnant: string): boolean {
  const r = remnant.trim();
  if (r.length < 15) return true;
  if (/^(?:check|but|however|though|and|so|also|plus|otherwise|instead|cross[- ]pattern)\b/i.test(r)) return true;
  if (/\bthough[.!]?\s*$/i.test(r)) return true;
  return false;
}

/**
 * Resolve the final answer after the numeric-provenance gate ran.
 * @param cleanedRemnant  prov.clean — the answer with untraceable-number sentences removed
 * @param hit             prov.hit   — whether the gate stripped anything
 * @param message         the worker's own message (for spec-vs-metric routing)
 */
export function resolveProvenanceRemnant(cleanedRemnant: string, hit: boolean, message: string): string {
  if (!hit) return cleanedRemnant;                 // nothing stripped → unchanged
  const remnant = (cleanedRemnant || "").trim();
  const specAsk = SPEC_ASK_RE.test(message || "");
  // A SPEC ask whose numeric answer the gate removed no longer carries the value
  // asked for (either the remnant is a broken fragment, OR every number is gone).
  if (specAsk && (looksGutted(remnant) || extractNumberCores(remnant).length === 0)) {
    return SPEC_POINTER;
  }
  if (looksGutted(remnant)) return METRIC_POINTER; // incoherent non-spec remnant
  return remnant;                                  // coherent, grounded → keep
}
