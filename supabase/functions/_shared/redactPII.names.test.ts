// deno test _shared/redactPII.names.test.ts
// CL11 (2026-07-08): redactKnownNames closes the multi-turn name leak — a prior-turn worker name in the
// forwarded memory_block / summariser transcript reaching a model provider. Regression contract.
import { assert, assertEquals } from "https://deno.land/std@0.208.0/assert/mod.ts";
import { redactKnownNames, hydratePII } from "./redactPII.ts";

const NAMES = ["Leandro Marquez", "Bryan Garcia", "Wilfredo Malabanan"];

Deno.test("redacts every known full-name occurrence; no raw name survives", () => {
  const t = "Assigned: Leandro Marquez to verify. Bryan Garcia reported the fault.";
  const { redacted } = redactKnownNames(t, NAMES);
  assert(!/Leandro Marquez|Bryan Garcia/.test(redacted), "no raw name in the forwarded text");
  assert(/<name_\d+>/.test(redacted), "names replaced by placeholders");
});

Deno.test("same name -> SAME placeholder; hydration round-trips to the original", () => {
  const t = "Leandro Marquez set the torque. Later Leandro Marquez verified it.";
  const { redacted, hydration } = redactKnownNames(t, NAMES);
  assertEquals((redacted.match(/<name_1>/g) || []).length, 2, "both occurrences share one placeholder");
  assertEquals(hydratePII(redacted, hydration), t, "hydrate restores the exact original");
});

Deno.test("empty names / empty text -> passthrough (no throw)", () => {
  assertEquals(redactKnownNames("hello", []).redacted, "hello");
  assertEquals(redactKnownNames("", NAMES).redacted, "");
});

Deno.test("absent name burns no counter + empty map", () => {
  const r = redactKnownNames("torque set to 210 Nm on CH-001", NAMES);
  assertEquals(r.redacted, "torque set to 210 Nm on CH-001");
  assertEquals(Object.keys(r.hydration).length, 0);
});

Deno.test("no false SUBSTRING match — a name never redacts a common word", () => {
  // "Al Cruz" must not blank out "alignment"
  assertEquals(redactKnownNames("Check alignment on the coupling", ["Al Cruz"]).redacted,
    "Check alignment on the coupling");
});

Deno.test("longest-first: a contained short name doesn't pre-empt the full name", () => {
  const { redacted } = redactKnownNames("Juan Dela Cruz signed off; Juan is the tech.", ["Juan Dela Cruz", "Juan Reyes"]);
  assert(!/Juan Dela Cruz/.test(redacted), "full name redacted");
});
