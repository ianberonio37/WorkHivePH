// deno test _shared/gutted_reply.test.ts
// CL2/CL10 gutted-reply resolver — regression contract. Run: deno test gutted_reply.test.ts
// Tests the REAL pipeline: gateNumericProvenance (the strip) -> resolveProvenanceRemnant
// (the honest-pointer decision), so the exact code the agent runs is what is proven.
import { assert, assertEquals } from "https://deno.land/std@0.208.0/assert/mod.ts";
import { gateNumericProvenance } from "./numeric_provenance.ts";
import { resolveProvenanceRemnant, SPEC_POINTER, METRIC_POINTER } from "./gutted_reply.ts";

// Helper: run the true pipeline (gate then resolve).
function pipeline(answer: string, grounded: string, message: string): string {
  const prov = gateNumericProvenance(answer, grounded);
  return resolveProvenanceRemnant(prov.clean, prov.hit, message);
}

// ---- THE LIVE-CAUGHT DEFECT: a spec answer gutted into a dangling caveat --------------------
Deno.test("live-caught: M20 torque answer gutted by G1 -> honest SPEC pointer", () => {
  const answer = "For an M20 grade 8.8 fastener, a sensible torque range is 180-220 Nm. Cross-pattern, three passes. Check the OEM manual though.";
  const out = pipeline(answer, "", "What's a sensible bolt torque range for an M20 grade 8.8 fastener?");
  assertEquals(out, SPEC_POINTER);
  assert(!/though/i.test(out), "no dangling caveat fragment survives");
});

Deno.test("spec ask where every number was stripped (no digit survives) -> SPEC pointer", () => {
  // "three" is a word, not a digit, so it survives the gate; but no NUMBER survives.
  const answer = "The torque is 210 Nm. Cross-pattern, three passes.";
  const out = pipeline(answer, "", "how much torque for M20 8.8?");
  assertEquals(out, SPEC_POINTER);
});

// ---- NON-SPEC gutted remnant -> live-metrics pointer ---------------------------------------
Deno.test("non-spec KPI answer gutted (leading connector) -> METRIC pointer", () => {
  const answer = "Your OEE is running at 78%. But check the dashboard.";
  const out = pipeline(answer, "", "how are we doing overall?");
  assertEquals(out, METRIC_POINTER);
});

// ---- NO-REGRESSION: a coherent grounded remnant must be KEPT, never replaced ---------------
Deno.test("grounded fact survives, fabricated one stripped -> remnant KEPT (not a pointer)", () => {
  // 45 is grounded; 78 is not. Gate keeps sentence 1, strips sentence 2.
  const answer = "You have 45 active alerts. Your OEE is 78%.";
  const out = pipeline(answer, "There are 45 active alerts in this hive.", "give me a plant rundown");
  assertEquals(out, "You have 45 active alerts.");
  assert(out !== METRIC_POINTER && out !== SPEC_POINTER, "a good grounded remnant is not replaced");
});

Deno.test("spec ask with a GROUNDED spec value surviving -> remnant KEPT", () => {
  // 137 is grounded (worker/asset-stated); 200 is not.
  const answer = "For CT-001 the torque is 137 Nm. Generally around 200 Nm.";
  const out = pipeline(answer, "CT-001 torque 137 Nm", "what torque for CT-001?");
  assertEquals(out, "For CT-001 the torque is 137 Nm.");
});

Deno.test("nothing stripped (hit=false) -> answer untouched", () => {
  const answer = "MTBF is the average time an asset runs between breakdowns.";
  const out = pipeline(answer, "", "explain MTBF in one sentence");
  assertEquals(out, answer);
});

Deno.test("spec recall of the worker's own stated value -> untouched (grounded, no strip)", () => {
  const answer = "The torque you told me earlier was 85 Nm.";
  const out = pipeline(answer, "Worker: torque 85 Nm", "what torque did I tell you?");
  assertEquals(out, answer);
});

// ---- looksGutted direct edge cases (via a spec ask so the branch is exercised) --------------
Deno.test("empty/near-empty remnant after strip -> pointer, never a stub", () => {
  const answer = "180 Nm.";
  const out = pipeline(answer, "", "torque for M20?");
  assertEquals(out, SPEC_POINTER);
});
