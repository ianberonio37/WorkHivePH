// _shared/factsheet_render.ts
// ============================================================================
// PHASE G3 - Typed fact-sheet + structured-output rendering (Companion
// Grounding Doctrine §2 "Phase G3" + §2c decision D8).
//
// PRINCIPLE (WorkHive WAT, ai-engineer SKILL.md L798): "Code builds a FACT
// SHEET deterministically; the model only phrases it." G3 closes the one
// residual G1 cannot — the *coincidental match* (a fabricated number that
// happens to equal a grounded one: snapshot "5 alerts" -> "5% reactive", the
// `5` traces under G1). On a DATA-READ turn the model is handed a typed fact
// sheet and asked to write prose with {{FACT:id}} PLACEHOLDERS, emitting NO
// digits of its own; deterministic code inserts the real values. The model
// literally cannot author a load-bearing number.
//
// STRICTLY ADDITIVE (doctrine: "never worse than G1"). G3 engages ONLY when:
//   (1) the turn is value-seeking ("what's my OEE", "how many alerts"), AND
//   (2) the parsed fact sheet is non-empty.
// Any failure downstream — malformed JSON, an unknown fact id, a leftover
// placeholder — makes the caller fall back to the existing G1-gated free-prose
// path. And whatever G3 produces still flows through the SAME strip + G1
// cascade in voice-journal-agent, so G1 (separate code) remains the universal
// numeric floor and the *independent* "rendered numbers ⊆ grounded input"
// post-render assertion (fact values are grounded — they came from snapText).
//
// SOURCE OF FACTS: we parse the gateway's OWN deterministically-rendered ops
// snapshot (buildOpsSnapshot / buildFromRegistry render templates). It is our
// output, not user text, so targeted parsing is reliable; a template change
// just yields fewer facts -> graceful degradation to G1, never a wrong number.
//
// Pure string ops, no imports — copy to .tmp/*.mts for the node self-test.
// ============================================================================

export interface OpsFact {
  id: string;       // stable slot id referenced as {{FACT:id}}, e.g. "active_alerts"
  label: string;    // human label for the prompt, e.g. "active alerts"
  value: number;    // numeric value (for assertions / telemetry)
  display: string;  // EXACTLY how it renders in prose, e.g. "4", "86%", "9.8 hours"
                    // (kept from the raw snapshot capture so the inserted token
                    //  is byte-identical to what G1 sees as grounded).
}

export interface OpsFactSheet {
  facts: OpsFact[];
  byId: Record<string, OpsFact>;
}

export interface G3ModelOut {
  facts_to_surface?: string[];
  tone?: string;
  prose?: string;
}

export interface RenderResult {
  ok: boolean;
  prose: string;
  reason?: "empty-prose" | "unknown-id" | "leftover-placeholder";
}

// ── Fact-sheet extraction ────────────────────────────────────────────────────
// Each extractor is INDEPENDENT and OPTIONAL: it adds a fact only if its anchor
// is present in the snapshot. A miss is silent (the fact simply isn't offered to
// the model, so that number stays under G1). Patterns mirror the exact render
// strings in ai-gateway buildOpsSnapshot + companion_source_registry.json.

type Extractor = (snap: string, push: (f: OpsFact) => void) => void;

function _num(raw: string): number {
  return parseFloat(String(raw).replace(/,/g, ""));
}

const _EXTRACTORS: Extractor[] = [
  // Core (hand-built in buildOpsSnapshot):
  (s, push) => {                                                      // Active alerts (...): N
    const m = s.match(/Active alerts[^:]*:\s*(\d+)/i);
    if (m) push({ id: "active_alerts", label: "active alerts", value: _num(m[1]), display: m[1] });
  },
  (s, push) => {                                                      // Overdue PM tasks: N.
    const m = s.match(/Overdue PM tasks:\s*(\d+)/i);
    if (m) push({ id: "overdue_pm", label: "overdue PM tasks", value: _num(m[1]), display: m[1] });
  },
  (s, push) => {                                                      // Registered assets (N) — ...
    const m = s.match(/Registered assets\s*\((\d+)\)/i);
    if (m) push({ id: "asset_count", label: "registered assets", value: _num(m[1]), display: m[1] });
  },
  // OEE (buildOeeFacts): "hive average ~86% across N assets (range ...)"
  (s, push) => {
    const m = s.match(/hive average ~?(\d+)%\s*across\s*\d+\s*assets/i);
    if (m) push({ id: "oee_avg", label: "hive average OEE", value: _num(m[1]), display: `${m[1]}%` });
  },
  // Reliability (v_kpi_truth engine): "hive average MTBF 9.8 hours, average MTTR 1.2 hours across N machines"
  (s, push) => {
    const m = s.match(/hive average MTBF\s*([\d.]+)\s*hours,\s*average MTTR\s*([\d.]+)\s*hours\s*across\s*(\d+)\s*machines/i);
    if (m) {
      push({ id: "mtbf_avg", label: "hive average MTBF", value: _num(m[1]), display: `${m[1]} hours` });
      push({ id: "mttr_avg", label: "hive average MTTR", value: _num(m[2]), display: `${m[2]} hours` });
      push({ id: "kpi_machines", label: "machines with reliability data", value: _num(m[3]), display: m[3] });
    }
  },
  // Inventory (v_inventory_items_truth engine): "N parts tracked, M at or below reorder point, K out of stock"
  (s, push) => {
    const m = s.match(/(\d+)\s*parts tracked,\s*(\d+)\s*at or below reorder point,\s*(\d+)\s*out of stock/i);
    if (m) {
      push({ id: "inv_total", label: "parts tracked", value: _num(m[1]), display: m[1] });
      push({ id: "inv_low",   label: "parts at or below reorder point", value: _num(m[2]), display: m[2] });
      push({ id: "inv_out",   label: "parts out of stock", value: _num(m[3]), display: m[3] });
    }
  },
  // PM compliance (buildPmComplianceFacts): "37% up to date (X of Y PM assets), Z due now"
  (s, push) => {
    const m = s.match(/(\d+)%\s*up to date\s*\((\d+)\s*of\s*(\d+)\s*PM assets\),\s*(\d+)\s*due now/i);
    if (m) {
      push({ id: "pm_pct",   label: "PM compliance (up to date)", value: _num(m[1]), display: `${m[1]}%` });
      push({ id: "pm_total", label: "PM assets", value: _num(m[3]), display: m[3] });
      push({ id: "pm_due",   label: "PM assets due now", value: _num(m[4]), display: m[4] });
    }
  },
  // Team (v_worker_skill_truth engine): "N members across M disciplines (...); K at skill level 4+"
  (s, push) => {
    const m = s.match(/(\d+)\s*members across\s*(\d+)\s*disciplines[^;]*;\s*(\d+)\s*at skill level 4\+/i);
    if (m) {
      push({ id: "team_members",     label: "team members", value: _num(m[1]), display: m[1] });
      push({ id: "team_disciplines", label: "disciplines", value: _num(m[2]), display: m[2] });
      push({ id: "team_seniors",     label: "members at skill level 4+", value: _num(m[3]), display: m[3] });
    }
  },
  // Projects (buildProjectFacts): "N active[, M blocked]: ..."
  (s, push) => {
    const m = s.match(/Projects \(from v_project_progress_truth\):\s*(\d+)\s*active(?:,\s*(\d+)\s*blocked)?/i);
    if (m) {
      push({ id: "project_count", label: "active projects", value: _num(m[1]), display: m[1] });
      if (m[2]) push({ id: "project_blocked", label: "blocked projects", value: _num(m[2]), display: m[2] });
    }
  },
];

export function buildOpsFactSheet(snapText: string): OpsFactSheet {
  const facts: OpsFact[] = [];
  const seen = new Set<string>();
  const push = (f: OpsFact) => {
    if (seen.has(f.id) || !Number.isFinite(f.value)) return;   // first-wins, finite only
    seen.add(f.id);
    facts.push(f);
  };
  if (snapText) for (const ex of _EXTRACTORS) { try { ex(snapText, push); } catch (_) { /* skip */ } }
  const byId: Record<string, OpsFact> = {};
  for (const f of facts) byId[f.id] = f;
  return { facts, byId };
}

// ── Data-read classifier (the doctrine's "value-seeking" gate) ───────────────
// G3 fires ONLY on a value-seeking question whose answer is a number we hold.
// Deliberately conservative: a how-to ("how do I improve OEE?"), a greeting, or
// an open-ended brief does NOT match -> stays free prose (no "alignment tax" on
// conversational turns, doctrine §3). A miss is harmless (G1 still backstops).
const _VALUE_SEEKING_RE = new RegExp(
  [
    "how many", "how much", "number of", "count of", "how often",
    "what(?:'s| is| are)?\\s+(?:my|the|our|your)\\b",
    "whats?\\s+(?:my|the|our|your)\\b",
    "how(?:'s| is)\\s+(?:my|the|our|your)\\b",
    "hows\\s+(?:my|our|the)\\b",
    "status of", "level of", "\\brate of\\b",
    "do (?:i|we) have (?:any|enough)", "are there (?:any|enough)",
    "right now\\??$", "currently\\??$",
    "tell me (?:my|the|how many)", "give me (?:my|the)", "show (?:me )?(?:my|the)",
  ].join("|"),
  "i",
);
// Bare metric pings ("OEE?", "my MTBF", "overdue PMs?") — short messages that
// name a held metric without a full question stem.
const _METRIC_PING_RE = /\b(oee|mtbf|mttr|overdue pms?|pm compliance|in stock|low stock|out of stock|active alerts?)\b/i;
// Advice / how-to / causal-knowledge turns are NOT data-reads — they get a warm
// free-prose (RAG-grounded) answer, not slot-fill (doctrine §3: "deflect VALUES,
// never TOPICS"; how-to keeps conversational warmth). Checked FIRST so a metric
// noun inside an advice question ("how do I improve my OEE?", "what causes high
// MTTR?") never trips the value/ping signals below.
const _ADVICE_KNOWLEDGE_RE = /\b(how (?:do|can|should|to|would|much longer)|how['’]?d|improve|increase|raise|boost|reduce|lower|optimi[sz]e|fix|repair|troubleshoot|diagnose|prevent|why (?:is|are|does|did|do)|what causes|what['’]?s causing|best way|recommend|advice|should i|steps? to|procedure|explain|tell me about)\b/i;

export function isDataReadTurn(message: string, sheet: OpsFactSheet): boolean {
  if (!sheet.facts.length) return false;
  const m = (message || "").toLowerCase();
  if (_ADVICE_KNOWLEDGE_RE.test(m)) return false;            // how-to / causal → free prose
  if (_VALUE_SEEKING_RE.test(m)) return true;
  // a short message (≤ 5 words) that just names a held metric is also a value ask
  if (_METRIC_PING_RE.test(m) && m.split(/\s+/).filter(Boolean).length <= 5) return true;
  return false;
}

// ── Prompt block: the fact sheet + the placeholder contract ──────────────────
// Appended to the USER block on the G3 path. response_format:json_object (set by
// the caller) forces a JSON object, overriding the persona's "reply with prose";
// the warm `prose` string carries the {{FACT:id}} slots.
export function buildFactSheetPromptBlock(sheet: OpsFactSheet): string {
  const lines = sheet.facts.map((f) => `- {{FACT:${f.id}}} = ${f.label} (live value: ${f.display})`);
  return [
    "=== FACT SHEET — the ONLY operational numbers you may state this turn ===",
    ...lines,
    "",
    "NUMBER RULE (non-negotiable): for EVERY operational number in your reply, write the",
    "matching {{FACT:id}} placeholder EXACTLY as shown above — never type the digit, a",
    "rounded version, a percentage you computed, or a derived/combined figure. The system",
    "replaces each placeholder with the live value before the worker sees it; a digit you",
    "type yourself may be stale or wrong and will be removed. If a number you'd want is NOT",
    "in the fact sheet, do not state any number for it — say plainly you don't have that on",
    "this surface and point to the matching page. Dates, durations ('every 2 weeks'), and",
    "list ordinals ('top 3') are fine as normal text.",
    "",
    "Answer the worker warmly and briefly in their language, sounding like yourself.",
    'Reply as a JSON object: {"facts_to_surface": ["<ids you used>"], "tone": "<one word>", "prose": "<your reply with {{FACT:id}} placeholders>"}.',
  ].join("\n");
}

// ── Robust JSON parse (weak free-tier models botch escaping) ─────────────────
export function parseG3Json(raw: string): G3ModelOut | null {
  if (!raw) return null;
  let s = String(raw).trim();
  // strip ``` / ```json fences
  s = s.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/i, "").trim();
  // brace-extract: first { … last }
  const i = s.indexOf("{");
  const j = s.lastIndexOf("}");
  const body = i >= 0 && j > i ? s.slice(i, j + 1) : s;
  try {
    const o = JSON.parse(body);
    if (o && typeof o === "object" && typeof o.prose === "string" && o.prose.trim()) {
      return o as G3ModelOut;
    }
  } catch (_) { /* fall through to salvage */ }
  // salvage just the prose string from a malformed object
  const pm = body.match(/"prose"\s*:\s*"((?:\\.|[^"\\])*)"/);
  if (pm) {
    const prose = pm[1]
      .replace(/\\n/g, "\n").replace(/\\t/g, "\t")
      .replace(/\\"/g, '"').replace(/\\\\/g, "\\");
    if (prose.trim()) return { prose };
  }
  return null;
}

// ── Slot-fill + the placeholder-integrity assertion ──────────────────────────
// Replaces {{FACT:id}} with the fact's display value. HARD-fails (→ caller falls
// back to G1 prose) on the two defects G1 cannot catch downstream:
//   - an UNKNOWN id (would ship a blank or wrong number), and
//   - a LEFTOVER placeholder (would ship raw "{{FACT:…}}" to the worker).
// Stray *grounded-but-not-slotted* digits the model typed anyway are left for
// the downstream G1 gate (separate code) — that is the independent "numbers ⊆
// grounded" assertion, by composition.
const _PLACEHOLDER_RE = /\{\{\s*FACT\s*:\s*([a-z0-9_]+)\s*\}\}/gi;
const _ANY_FACT_LEFT_RE = /\{\{?\s*FACT/i;

export function renderFactSheet(out: G3ModelOut, sheet: OpsFactSheet): RenderResult {
  const prose0 = (out?.prose || "").trim();
  if (!prose0) return { ok: false, prose: "", reason: "empty-prose" };
  let unknown = false;
  const filled = prose0.replace(_PLACEHOLDER_RE, (_m, id: string) => {
    const f = sheet.byId[String(id).toLowerCase()];
    if (!f) { unknown = true; return _m; }
    return f.display;
  });
  if (unknown) return { ok: false, prose: filled, reason: "unknown-id" };
  if (_ANY_FACT_LEFT_RE.test(filled)) return { ok: false, prose: filled, reason: "leftover-placeholder" };
  return { ok: true, prose: filled.replace(/\s+/g, " ").trim() };
}
