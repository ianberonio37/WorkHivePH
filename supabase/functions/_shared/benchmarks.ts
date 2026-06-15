// _shared/benchmarks.ts
// ─────────────────────────────────────────────────────────────────────────────
// PHASE G1b — Curated benchmark table (Companion Grounding Doctrine §1b).
//
// A deterministic table of CITABLE values + their source. The companion MAY
// state one of these numbers WITH benchmark framing ("world-class OEE is ~85%")
// and the G1 numeric-provenance gate will treat it as traceable (c). Without
// framing, a bare "85%" still strips — so this is not an escape hatch.
//
// Under the STRICT G1 gate (locked 2026-06-14 with Ian) this table is
// LOAD-BEARING: it is the ONLY sanctioned home for a number the companion may
// state that is not live-grounded. Phase G1b WIDENS it to the citable domain
// constants the companion actually needs (standard torque ranges, bearing-temp
// thresholds, regrease intervals, P-F interval…), each value sourced from the
// `maintenance-expert` skill, and feeds the table into the prompt so the model
// CITES rather than invents. The seed below is the G1 starter set (OEE family);
// keep every entry sourced.
//
// NB - NOT the DB `benchmarks` table. That table (computed by the
// `benchmark-compute` edge fn, rendered by ph-intelligence.html) holds per-hive
// PEER industry rollups (MTBF/OEE vs segment median, N>=5 privacy guard). THIS
// module is a tiny static table of UNIVERSAL citable constants for the companion
// grounding gate. Different layer, different purpose - do not conflate.
// ─────────────────────────────────────────────────────────────────────────────

export interface Benchmark {
  label:  string;
  value:  number;
  unit:   string;
  source: string;
}

// World-class OEE family (Nakajima / ISO 22400). These are the values the
// companion is allowed to cite as benchmarks. WIDEN in G1b (maintenance-expert).
export const BENCHMARKS: Benchmark[] = [
  { label: "world-class OEE",          value: 85, unit: "%", source: "Nakajima / ISO 22400" },
  { label: "world-class availability", value: 90, unit: "%", source: "Nakajima / ISO 22400" },
  { label: "world-class performance",  value: 95, unit: "%", source: "Nakajima / ISO 22400" },
  { label: "world-class quality",      value: 99, unit: "%", source: "Nakajima / ISO 22400" },
];

// Comparable number cores (string form, matching the G1 gate's normalization),
// for O(1) membership checks inside gateNumericProvenance.
export const BENCHMARK_VALUE_SET: Set<string> = new Set(
  BENCHMARKS.map((b) => String(b.value)),
);
