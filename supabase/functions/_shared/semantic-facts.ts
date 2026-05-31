// _shared/semantic-facts.ts
//
// Pure (no-IO) helpers for the Semantic layer (layer 03 of the AI Agent Memory
// Stack) per-hive entity extractor. The DB read, the LLM call, the embedding
// call and the upsert live in semantic-fact-extractor/index.ts; everything that
// can be reasoned about deterministically lives HERE so it is Node-probeable
// without a running edge runtime (same split as _shared/cold-archive.ts in
// Turn 3).
//
// The extractor turns a hive's own logbook entries into typed subject ->
// predicate -> object triples and writes them to knowledge_graph_facts. That
// table was designed in phase6 (20260513000007) for exactly these per-hive
// claims ("Motor M-3 has failed 4 times this quarter") but, until Turn 4,
// nothing populated it: only the day5 STANDARDS extractor wrote KG facts and
// those live in the platform sibling. voice-handler.js::_fetchKGContext already
// READS this store via semantic_search_kg_facts; Turn 4 supplies the writes.
//
// Vocabulary mirrors tools/day5_extract_kg_facts.py so hive-derived and
// standards-derived triples share one ontology (GraphRAG can traverse both).

// CHECK constraint on knowledge_graph_facts: subject_type / predicate /
// object_type must match ^[a-z][a-z0-9_]{0,30}$ (lowercase, snake_case, must
// LEAD with a letter, <=31 chars). A row that violates this fails the whole
// batch upsert, so validateTriple drops any triple that cannot be coerced into
// a conforming form rather than risk poisoning the batch.
export const TYPE_CHECK_RE = /^[a-z][a-z0-9_]{0,30}$/;

export const ALLOWED_SUBJECT_TYPES = new Set([
  "asset", "failure_mode", "sop", "worker", "part", "lesson",
  "system", "control", "hazard", "process",
]);
export const ALLOWED_PREDICATES = new Set([
  "causes", "detects", "requires", "mitigates", "related_to",
  "prevents", "monitors", "uses", "applies_to", "documents", "warns_against",
]);
export const ALLOWED_OBJECT_TYPES = ALLOWED_SUBJECT_TYPES;

export interface RawTriple {
  subject_type?: unknown;
  subject_ref?:  unknown;
  predicate?:    unknown;
  object_type?:  unknown;
  object_ref?:   unknown;
  claim_text?:   unknown;
  confidence?:   unknown;
  entry_id?:     unknown;
}

export interface NormalizedTriple {
  subject_type: string;
  subject_ref:  string;
  predicate:    string;
  object_type:  string;
  object_ref:   string;
  claim_text:   string;
  confidence:   number;
  entry_id:     string; // the logbook row this fact was derived from (provenance)
}

export interface LogbookEntry {
  id:                   string;
  machine?:             string | null;
  problem?:             string | null;
  action?:              string | null;
  root_cause?:          string | null;
  failure_consequence?: string | null;
  knowledge?:           string | null;
  maintenance_type?:    string | null;
  created_at?:          string | null;
}

/**
 * Force a type token into CHECK-compliant form: lowercase, snake_case, leading
 * letter, <=31 chars. Returns "" if nothing conforming survives (caller drops
 * the triple). Mirrors day5_extract_kg_facts.sanitize_type but additionally
 * strips leading digits/underscores so the result starts with a letter (the
 * Postgres CHECK demands ^[a-z]...; the Python version did not guarantee this
 * and relied on per-row autocommit to absorb the failures).
 */
export function sanitizeType(s: unknown): string {
  let x = String(s ?? "").trim().toLowerCase();
  x = x.replace(/[^a-z0-9_]/g, "_").replace(/_+/g, "_").replace(/^_+|_+$/g, "");
  x = x.replace(/^[0-9_]+/, ""); // must lead with a letter for the CHECK
  return x.slice(0, 31);
}

/**
 * Parse whatever the LLM returned into an array of raw triples. Handles:
 *   - a bare JSON array
 *   - an object wrapper { triples | facts | data | items | result: [...] }
 *   - stray ```json fences
 *   - a JSON array embedded anywhere in surrounding prose
 * Always returns an array (possibly empty) — never throws.
 */
export function parseTriples(raw: string): RawTriple[] {
  let s = String(raw ?? "").trim();
  s = s.replace(/^```(?:json)?\s*/i, "").replace(/\s*```\s*$/i, "").trim();
  if (!s) return [];

  try {
    const parsed = JSON.parse(s);
    if (Array.isArray(parsed)) return parsed as RawTriple[];
    if (parsed && typeof parsed === "object") {
      for (const k of ["triples", "facts", "data", "items", "result"]) {
        const v = (parsed as Record<string, unknown>)[k];
        if (Array.isArray(v)) return v as RawTriple[];
      }
      return [];
    }
  } catch { /* fall through to array-scan */ }

  const m = s.match(/\[[\s\S]*\]/);
  if (!m) return [];
  try {
    const arr = JSON.parse(m[0]);
    return Array.isArray(arr) ? (arr as RawTriple[]) : [];
  } catch { return []; }
}

/** Clamp a confidence value to [0,1], defaulting to 0.6 on garbage. */
export function clampConfidence(v: unknown): number {
  const n = Number(v);
  if (!Number.isFinite(n)) return 0.6;
  return Math.min(1, Math.max(0, n));
}

/**
 * Validate + normalize one raw triple. Returns null (drop it) unless ALL hold:
 *   - subject_type / predicate / object_type sanitize to a CHECK-valid token
 *   - subject_ref and object_ref are non-empty after trim
 *   - entry_id is one of the logbook ids that were actually sent to the model
 *     (provenance is REQUIRED — it becomes source_ref="logbook:<id>", the tail
 *     of the dedupe key, so a triple with no real source is unanchored and the
 *     model may have hallucinated it)
 */
export function validateTriple(t: RawTriple, validEntryIds: Set<string>): NormalizedTriple | null {
  const st = sanitizeType(t.subject_type);
  const ot = sanitizeType(t.object_type);
  const pr = sanitizeType(t.predicate);
  if (!TYPE_CHECK_RE.test(st) || !TYPE_CHECK_RE.test(ot) || !TYPE_CHECK_RE.test(pr)) return null;

  const sub_ref = String(t.subject_ref ?? "").trim().slice(0, 200);
  const obj_ref = String(t.object_ref ?? "").trim().slice(0, 200);
  if (!sub_ref || !obj_ref) return null;

  const entry_id = String(t.entry_id ?? "").trim();
  if (!entry_id || !validEntryIds.has(entry_id)) return null;

  const claim = String(t.claim_text ?? "").trim().slice(0, 1000);
  return {
    subject_type: st,
    subject_ref:  sub_ref,
    predicate:    pr,
    object_type:  ot,
    object_ref:   obj_ref,
    claim_text:   claim,
    confidence:   clampConfidence(t.confidence),
    entry_id,
  };
}

/** A single short text line per logbook entry — compact, token-minimal, ids first. */
export function formatEntriesForPrompt(entries: LogbookEntry[]): string {
  return entries.map((e) => {
    const parts = [
      `id=${e.id}`,
      e.machine             ? `asset="${String(e.machine).slice(0, 80)}"` : "",
      e.maintenance_type    ? `type="${String(e.maintenance_type).slice(0, 40)}"` : "",
      e.problem             ? `problem="${String(e.problem).slice(0, 160)}"` : "",
      e.root_cause          ? `root_cause="${String(e.root_cause).slice(0, 160)}"` : "",
      e.action              ? `action="${String(e.action).slice(0, 160)}"` : "",
      e.failure_consequence ? `consequence="${String(e.failure_consequence).slice(0, 120)}"` : "",
      e.knowledge           ? `lesson="${String(e.knowledge).slice(0, 200)}"` : "",
    ].filter(Boolean);
    return parts.join(" | ");
  }).join("\n");
}
