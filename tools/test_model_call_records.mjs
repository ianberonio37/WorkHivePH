// test_model_call_records.mjs - the per-call record's semantics, run against the REAL collector
// (supabase/functions/_shared/model-calls.ts, loaded by Node's TypeScript type-stripping; no network, no DB).
//
// What tools/validate_ai_call_sinks.py checks statically (each path CALLS the hook), this checks behaviourally (the
// hook produces the right ROWS): a walk that exhausted every provider is ONE failed row whether or not the function
// also logs it; a function's logAICost annotates its generation call, never an embedding made after it; a call the
// function stopped waiting for (raceModelCall) lands once, late, under the reply's trace id, status fallback.
//
//   node tools/test_model_call_records.mjs        exit 0 = every case holds
// Run by: python tools/validate_ai_call_sinks.py --selftest (skipped, and said so, when node is absent).

import { readFileSync, writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

// the source as it is on disk, loaded as an ES module (.mts: no package.json decides it for us)
// WH_MODEL_CALLS_SRC: a mutated copy, for the gate's teeth check (validate_ai_call_sinks.py --selftest)
const src = readFileSync(process.env.WH_MODEL_CALLS_SRC || new URL("../supabase/functions/_shared/model-calls.ts", import.meta.url), "utf8");
const dir = mkdtempSync(join(tmpdir(), "wh-model-calls-"));
const modPath = join(dir, "model-calls.mts");
writeFileSync(modPath, src);
const M = await import(pathToFileURL(modPath).href);
process.on("exit", () => { try { rmSync(dir, { recursive: true, force: true }); } catch { /* temp dir */ } });

let bad = 0;
const ok = (cond, label, detail) => {
  if (cond) console.log(`  ok    ${label}`);
  else { bad += 1; console.log(`  FAIL  ${label}${detail ? " - " + detail : ""}`); }
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// 1. an exhausted walk the function ALSO logs: one failed row, the function's verdict annotated onto it
{
  const s = M.newModelCallScope("fn-a");
  await M.withModelCallScope(s, async () => {
    M.reportModelCallFailed({ providerName: "chain", modelName: "exhausted", tried: ["groq/x=429", "gemini/y=503"], started_at: performance.now() - 40 });
    M.absorbCostEntry({ model: "chain", status: "fallback", schema_compliance: false, prompt_hash: "abc" });
  });
  const rows = M.takeModelCallRows(s, "0123456789abcdef");
  ok(rows.length === 1, "exhausted walk + logAICost = exactly one row", `got ${rows.length}`);
  const r = rows[0] || {};
  ok(r.status === "failed", "that row is failed (the function's 'fallback' does not turn a failed call into a served one)", r.status);
  ok(Array.isArray(r.providers_tried) && r.providers_tried.length === 2, "it names the slots asked", JSON.stringify(r.providers_tried));
  ok(r.schema_compliance === false && r.prompt_hash === "abc", "it carries the function's annotation");
  ok(r.prompt_tokens === null && r.output_tokens === null && r.tokens_estimated === false, "no tokens invented for a call nothing served");
  ok(typeof r.latency_ms === "number" && r.latency_ms >= 30, "it carries the time the caller waited", String(r.latency_ms));
  ok(r.kind === "generation" && r.late === false && r.trace_id === "0123456789abcdef", "kind generation, not late, the reply's trace id");
}

// 2. an exhausted walk the function does NOT log: still one failed row
{
  const s = M.newModelCallScope("fn-b");
  await M.withModelCallScope(s, async () => { M.reportModelCallFailed({ tried: [] }); });
  const rows = M.takeModelCallRows(s, null);
  ok(rows.length === 1 && rows[0].status === "failed" && rows[0].provider === "chain", "exhausted walk alone = one failed row");
}

// 3. a served call the function downgrades: one row, its verdict
{
  const s = M.newModelCallScope("fn-c");
  await M.withModelCallScope(s, async () => {
    M.reportModelCall({ providerName: "groq", modelName: "m", usage: { prompt_tokens: 10, completion_tokens: 5 }, tried: ["groq/m=200"] });
    M.absorbCostEntry({ status: "fallback", schema_compliance: false });
  });
  const rows = M.takeModelCallRows(s, null);
  ok(rows.length === 1 && rows[0].status === "fallback" && rows[0].prompt_tokens === 10 && rows[0].tokens_estimated === false,
     "served + logAICost = one row with the provider's tokens and the function's verdict");
}

// 4. logAICost describes the generation call, never an embedding the function made after it
{
  const s = M.newModelCallScope("fn-d");
  await M.withModelCallScope(s, async () => {
    M.reportModelCall({ providerName: "groq", modelName: "gen", output: "x" });
    M.reportModelCall({ kind: "embedding", providerName: "bge-local", modelName: "bge", input: "hello world" });
    M.absorbCostEntry({ status: "fallback", schema_compliance: false });
  });
  const rows = M.takeModelCallRows(s, null);
  const gen = rows.find((r) => r.kind === "generation");
  const emb = rows.find((r) => r.kind === "embedding");
  ok(rows.length === 2, "a generation and an embedding = two rows", `got ${rows.length}`);
  ok(gen && gen.status === "fallback" && gen.schema_compliance === false, "the verdict lands on the generation row");
  ok(emb && emb.status === "success" && emb.schema_compliance === null && emb.output_tokens === null,
     "the embedding row keeps its own outcome and has no output tokens");
}

// 5. a transcription: seconds, not tokens
{
  const s = M.newModelCallScope("fn-e");
  await M.withModelCallScope(s, async () => {
    M.reportModelCall({ kind: "transcription", providerName: "groq", modelName: "whisper-large-v3-turbo", audio_seconds: 3.456 });
  });
  const r = M.takeModelCallRows(s, null)[0];
  ok(r && r.kind === "transcription" && r.audio_seconds === 3.46 && r.prompt_tokens === null && r.tokens_estimated === false,
     "a transcription records audio seconds and invents no tokens", JSON.stringify(r));
}

// 6. raceModelCall past its deadline: the caller is released, the call lands ONCE, late, status fallback,
//    under the reply's trace id (written by the scope's late writer after the reply closed)
{
  const s = M.newModelCallScope("fn-f");
  const written = [];
  let threw = null;
  await M.withModelCallScope(s, async () => {
    try {
      await M.raceModelCall(async () => { await sleep(60); M.reportModelCall({ providerName: "groq", modelName: "slow", output: "late answer" }); return "late answer"; }, 15, "deadline");
    } catch (e) { threw = String(e && e.message); }
  });
  ok(threw === "deadline", "the caller gets the deadline rejection", String(threw));
  // the reply is written: close the scope the way settleModelCalls does
  s.trace_id = "fedcba9876543210";
  s.closed = true;
  s.late = (sc) => { written.push(...M.takeModelCallRows(sc, sc.trace_id)); };
  ok(M.takeModelCallRows(s, s.trace_id).length === 0, "nothing is written for it at reply time (it has not finished)");
  await sleep(90);
  ok(written.length === 1, "when it finishes it is written once", `got ${written.length}`);
  const r = written[0] || {};
  ok(r.late === true && r.status === "fallback" && r.trace_id === "fedcba9876543210",
     "late, status fallback (the reply did not use it), the reply's trace id", JSON.stringify({ late: r.late, status: r.status, trace: r.trace_id }));
}

// 7. raceModelCall in time: an ordinary row
{
  const s = M.newModelCallScope("fn-g");
  let v = null;
  await M.withModelCallScope(s, async () => {
    v = await M.raceModelCall(async () => { M.reportModelCall({ providerName: "groq", modelName: "fast", output: "a" }); return "a"; }, 500, "deadline");
  });
  const rows = M.takeModelCallRows(s, null);
  ok(v === "a" && rows.length === 1 && rows[0].late === false && rows[0].status === "success", "in time = one ordinary row");
}

// 8. a raced call that EXHAUSTS after its deadline: one failed row, late
{
  const s = M.newModelCallScope("fn-h");
  const written = [];
  await M.withModelCallScope(s, async () => {
    try { await M.raceModelCall(async () => { await sleep(40); M.reportModelCallFailed({ tried: ["groq/x=429"] }); return "{}"; }, 10, "deadline"); } catch { /* expected */ }
  });
  s.trace_id = "00112233445566ff"; s.closed = true;
  s.late = (sc) => { written.push(...M.takeModelCallRows(sc, sc.trace_id)); };
  await sleep(70);
  ok(written.length === 1 && written[0].status === "failed" && written[0].late === true, "a raced call that exhausts late = one failed row, late");
}

console.log(bad ? `FAIL (${bad})` : "PASS");
process.exit(bad ? 1 : 0);
