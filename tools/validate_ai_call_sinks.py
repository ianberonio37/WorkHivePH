"""
validate_ai_call_sinks.py - every edge function that calls a model leaves ONE durable per-call record when it
ANSWERS, and tools/ai_call_sinks.json says so truthfully.

★LM-O walk (LM544, alert-hub, 2026-10-08): "alert-hub.html's ask reached analytics-orchestrator, which leaves no
record of the call an operator can read when it answers" - it imported logAICost and never called it, serveObserved
wrote wh_traces only on an unhandled throw, and the only trace was the edge stdout line "[ai-chain] served by ...".
19 of 29 model-calling functions wrote no row; the 10 that did wrote a hand-typed model, no trace id, no user.

Rules (all derived from source by tools/build_ai_call_sinks.py):
  M  MECHANISM   _shared/model-calls.ts collects per request (AsyncLocalStorage) and its rows carry fn, trace_id,
                 auth_uid, hive_id, provider, model, tokens, latency, status; serveObserved runs every handler inside
                 the scope and writes ai_cost_log from it, taking the trace id from the reply's x-wh-trace; EVERY
                 success path of callAI / callAIMultimodal (each "served by" line, each `return stripped`) reports
                 the call; logAICost asks the collector before it inserts (no second row); tracedReply notes its id;
                 a migration adds ai_cost_log.trace_id + auth_uid.
                 (2026-10-08, same day) callAI / callAIMultimodal report a walk that EXHAUSTED every provider
                 (reportModelCallFailed) before degrading to "{}", and logAICost's absorbCostEntry annotates that
                 failed record instead of adding a second; embedding-chain.ts reports every embedding / rerank and
                 every exhausted embedding walk, audio-chain.ts every transcription and every exhausted one, each
                 with its kind; the record carries kind, providers_tried and late, and migrations add them.
  F  FUNCTION    every model-calling function - generation, embedding, transcription or speech, through a chain
                 or directly - is served through serveObserved(fn, ...) (so its calls are collected), a function that
                 calls a provider directly reports the call itself (an embedding / speech provider: on success AND on
                 failure), it returns a trace id the page keeps (tracedReply, or the gateway's ok() envelope), a
                 hand-verified hive is noted (noteModelCaller), nothing inserts into ai_cost_log beside the scope or
                 logs a `gateway:` row, and no model call is raced against a deadline by hand (raceModelCall records
                 the call it stopped waiting for once, late).
  S  STALE       tools/ai_call_sinks.json equals what the builder derives from the current source (rebuild:
                 python tools/build_ai_call_sinks.py).

    python tools/validate_ai_call_sinks.py              # PASS / FAIL over the working tree
    python tools/validate_ai_call_sinks.py --selftest   # each rule catches its mutant (a function stripped of its
                                                        # record, a chain path that stops reporting, ...)
Static, no DB, no browser.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_ai_call_sinks as B  # noqa: E402

ROOT = B.ROOT


def findings(doc: dict) -> list[str]:
    out = []
    for name, part in doc["mechanism"].items():
        if name in ("ok", "schema"):
            continue
        out += [f"M {name}: {f}" for f in part["findings"]]
    sch = doc["mechanism"]["schema"]
    if not sch["ok"]:
        missing = [c for c, ok in sch["columns"].items() if not ok]
        out.append(f"M schema: no migration adds ai_cost_log.{', ai_cost_log.'.join(missing)} - the record has nowhere "
                   f"to keep {'them' if len(missing) > 1 else 'it'}")
    for fn, r in doc["functions"].items():
        out += [f"F {fn}: {f}" for f in r["findings"]]
        if not r["per_call_record"] and not r["findings"]:
            out.append(f"F {fn}: calls a model and leaves no per-call record")
    return out


def stale(doc: dict) -> list[str]:
    p = ROOT / B.OUT_REL
    if not p.is_file():
        return [f"S {B.OUT_REL} is missing - run python tools/build_ai_call_sinks.py"]
    try:
        on_disk = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        return [f"S {B.OUT_REL} is not JSON ({e})"]
    if on_disk == json.loads(B.render(doc)):
        return []
    diff = []
    a, b = on_disk.get("functions", {}), doc["functions"]
    for fn in sorted(set(a) | set(b)):
        if a.get(fn) != b.get(fn):
            diff.append(fn)
    if on_disk.get("mechanism") != json.loads(B.render(doc))["mechanism"]:
        diff.append("<mechanism>")
    if on_disk.get("sources") != doc["sources"]:
        diff.append("<shared sources>")
    return [f"S {B.OUT_REL} is stale versus source ({', '.join(diff[:8]) or 'summary'}) - "
            f"run python tools/build_ai_call_sinks.py"]


def run() -> int:
    doc = B.build()
    fails = findings(doc) + stale(doc)
    s = doc["summary"]
    print("AI call sinks - one durable per-call record per model call (LM-O)")
    print(f"  {s['per_call_record']}/{s['model_calling_functions']} model-calling functions leave a per-call "
          f"{B.RECORD_TABLE} row; {s['returns_trace_id']} return the trace id it carries; "
          f"chain success paths reporting: {doc['mechanism']['chain'].get('reports', 0)}/"
          f"{doc['mechanism']['chain'].get('success_paths', 0)}; exhausted walks reported: "
          f"{doc['mechanism']['chain'].get('exhausted_reports', 0)}/2")
    by = s.get("by_kind", {})
    print("  by kind: " + ", ".join(f"{k} {len(v)}" for k, v in by.items()))
    if fails:
        for f in fails:
            print(f"  FAIL  {f}")
        print(f"FAIL ({len(fails)})")
        return 1
    print("PASS")
    return 0


# ── selftest: each rule bites ─────────────────────────────────────────────────────────────────────────────────────
def _overlay(mutations: dict[str, callable]):
    base = B.disk_reader()

    def read(rel: str):
        text = base(rel)
        if rel in mutations and text is not None:
            text = mutations[rel](text)
        return text
    return read


def _sub(pattern: str, repl: str, count: int = 1, flags: int = 0):
    def f(text: str) -> str:
        new, n = re.subn(pattern, repl, text, count=count, flags=flags)
        if n == 0:
            raise AssertionError(f"selftest mutation did not apply: {pattern!r}")
        return new
    return f


def selftest() -> int:
    FN = B.FN_DIR
    SH = f"{FN}/_shared"
    cases = [
        ("a function stripped of its record (served with serve(), no scope)",
         {f"{FN}/analytics-orchestrator/index.ts": _sub(r'serveObserved\("analytics-orchestrator", ', "serve(")},
         r"F analytics-orchestrator: not served through serveObserved"),
        ("a provider-calling function that stops reporting its call",
         {f"{FN}/voice-model-call/index.ts": _sub(r"reportModelCall\(\{", "void ({", 1)},
         r"F voice-model-call: calls a provider directly .* never calls reportModelCall"),
        ("callAI's success path stops reporting",
         {f"{SH}/ai-chain.ts": _sub(r"\n[ \t]*reportModelCall\(\{ providerName: entry\.provider[^\n]*\n[ \t]*// Q6", "\n            // Q6")},
         r"M chain: .*served by"),
        ("callAIMultimodal's success path stops reporting",
         {f"{SH}/ai-chain.ts": _sub(r"\n[ \t]*reportModelCall\(\{[^\n]*\n([ \t]*return stripped;\n[ \t]*\}\n[ \t]*// Reasoning-only)", r"\n\1")},
         r"M chain: callAIMultimodal\(\) never calls reportModelCall"),
        ("the wrapper stops opening the scope",
         {f"{SH}/observability.ts": _sub(r"withModelCallScope\(modelCalls, \(\) => handler\(req\)\)", "handler(req)")},
         r"M writer: withObservability does not run the handler inside withModelCallScope"),
        ("the wrapper stops writing what it collected",
         {f"{SH}/observability.ts": _sub(r"await settleModelCalls\(modelCalls, req, res\);", "void 0;")},
         r"M writer: withObservability never calls settleModelCalls"),
        ("logAICost inserts a second row instead of annotating",
         {f"{SH}/cost-log.ts": _sub(r"if \(absorbCostEntry\(entry\)\) return;", "")},
         r"M cost_log: logAICost\(\) inserts before asking"),
        ("the record loses its trace id",
         {f"{SH}/model-calls.ts": _sub(r"trace_id:\s+traceId,", "")},
         r"M collector: takeModelCallRows\(\) builds no `trace_id`"),
        ("a function returns no trace id",
         {f"{FN}/resume-polish/index.ts": _sub(r'tracedReply\("resume-polish", ', "(")},
         r"F resume-polish: returns no trace id"),
        ("a hand-verified hive is never noted",
         {f"{FN}/asset-brain-query/index.ts": _sub(r"noteModelCaller\(", "void (", count=0)},
         r"F asset-brain-query: verifies hive membership by hand"),
        ("a function writes its own ledger row",
         {f"{FN}/fmea-populator/index.ts": _sub(r"(\nserveObserved\()", "\nawait db.from(\"ai_cost_log\").insert({ fn: \"x\" });\\1")},
         r"F fmea-populator: inserts into ai_cost_log itself"),
        ("the gateway's per-turn pseudo row comes back",
         {f"{FN}/ai-gateway/index.ts": _sub(r"(\n  return ok\(ctx, \{\n    answer:    hydratedAnswer,)",
                                            "\n  await logAICost(adminClient, { fn: route.fn, model: `gateway:${route.fn}` });\\1")},
         r"F ai-gateway: logs a per-turn `gateway:<fn>` row"),
        # ── item 2: a walk that exhausted every provider is one failed record, never none, never two ──
        ("callAI's exhausted walk stops reporting",
         {f"{SH}/ai-chain.ts": _sub(r'reportModelCallFailed\(\{ providerName: "chain"', 'void ({ providerName: "chain"')},
         r"M chain: callAI\(\) degrades to \"\{\}\" without reportModelCallFailed"),
        ("callAIMultimodal's exhausted walk stops reporting",
         {f"{SH}/ai-chain.ts": _sub(r'(export async function callAIMultimodal\([\s\S]*?)reportModelCallFailed\(\{ providerName: "chain"',
                                    r'\1void ({ providerName: "chain"')},
         r"M chain: callAIMultimodal\(\) degrades to \"\{\}\" without reportModelCallFailed"),
        ("logAICost after an exhausted walk writes a second row (absorbCostEntry annotates only served calls)",
         {f"{SH}/model-calls.ts": _sub(r'if \(c\.kind === "generation" && !c\.annotated && !c\.written\)',
                                       "if (c.served && !c.annotated && !c.written)")},
         r"M collector: absorbCostEntry\(\) annotates only a SERVED call"),
        ("the record loses its kind",
         {f"{SH}/model-calls.ts": _sub(r"\n[ \t]*kind:\s+c\.kind,", "")},
         r"M collector: takeModelCallRows\(\) builds no `kind`"),
        # ── item 3: embedding / speech-to-text / text-to-speech calls are recorded like any other ──
        ("an embedding a provider answered stops reporting",
         {f"{SH}/embedding-chain.ts": _sub(r'reportModelCall\(\{\n(\s*)kind: "embedding"', r'void ({\n\1kind: "embedding"')},
         r"M embedding: generateEmbeddingTagged\(\) does not report the embedding"),
        ("an exhausted embedding walk stops reporting",
         {f"{SH}/embedding-chain.ts": _sub(r'reportModelCallFailed\(\{ kind: "embedding"', 'void ({ kind: "embedding"')},
         r"M embedding: generateEmbeddingTagged\(\) throws 'All embedding providers failed' without"),
        ("a transcription Groq answered stops reporting",
         {f"{SH}/audio-chain.ts": _sub(r'reportModelCall\(\{ kind: "transcription", providerName: "groq"',
                                       'void ({ kind: "transcription", providerName: "groq"')},
         r"M audio: transcribeAudio\(\) does not report the transcription"),
        ("an embedding-only function loses its request scope",
         {f"{FN}/embed-entry/index.ts": _sub(r'serveObserved\("embed-entry", ', "serve(")},
         r"F embed-entry: not served through serveObserved"),
        ("a function's own embedding fetch stops reporting",
         {f"{FN}/voice-embeddings/index.ts": _sub(r'reportModelCall\(\{ kind: "embedding"', 'void ({ kind: "embedding"')},
         r"F voice-embeddings: calls a provider directly \(embedding\) and does not report it"),
        # ── item 4: a call the function stops waiting for is recorded once, late ──
        ("a model call raced by hand again (Promise.race around callAI)",
         {f"{FN}/amc-orchestrator/index.ts": _sub(r"raw = await raceModelCall\(\n(\s*)\(\) => callAI\(",
                                                  r"raw = await Promise.race([\n\1callAI(")},
         r"F amc-orchestrator: races a model call by hand"),
    ]
    bad = 0
    clean = B.build()
    if findings(clean):
        print("  FAIL  the unmutated tree has findings - selftest needs a clean baseline:")
        for f in findings(clean):
            print("        " + f)
        return 1
    print("  ok    unmutated tree: no findings")
    for label, muts, want in cases:
        try:
            doc = B.build(read=_overlay(muts))
        except AssertionError as e:
            print(f"  FAIL  {label}: {e}")
            bad += 1
            continue
        got = findings(doc)
        if any(re.search(want, g) for g in got):
            print(f"  ok    caught: {label}")
        else:
            print(f"  FAIL  missed: {label} (wanted /{want}/; got {got[:3]})")
            bad += 1
    # S: a source change the json was not rebuilt for
    doc = B.build(read=_overlay({f"{FN}/analytics-orchestrator/index.ts": lambda t: t + "\n// drift\nconst _x = 1;\n"}))
    if stale(doc):
        print("  ok    caught: ai_call_sinks.json stale versus a changed source")
    else:
        print("  FAIL  missed: a changed source did not make ai_call_sinks.json stale")
        bad += 1
    n = len(cases) + 1
    b2, n2 = behaviour()
    bad += b2
    n += n2
    print(f"selftest: {n - bad}/{n} checks hold")
    return 1 if bad else 0


def behaviour() -> tuple[int, int]:
    """The ROWS, not just the hooks: tools/test_model_call_records.mjs runs the real collector (an exhausted walk is one
    failed row with or without logAICost; logAICost never annotates an embedding; a raced call lands once, late). It
    must pass on the source and FAIL on a collector whose absorbCostEntry annotates only served calls."""
    node = shutil.which("node")
    if not node:
        print("  skip  behaviour: node is not on PATH - tools/test_model_call_records.mjs not run")
        return 0, 0
    test = str(ROOT / "tools" / "test_model_call_records.mjs")
    bad = 0
    r = subprocess.run([node, test], cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    if r.returncode == 0:
        print("  ok    behaviour: the collector writes the rows the record promises (test_model_call_records.mjs)")
    else:
        print("  FAIL  behaviour: test_model_call_records.mjs failed on the source:")
        print("        " + "\n        ".join([l for l in r.stdout.splitlines() if "FAIL" in l][:6]))
        bad += 1
    src = (ROOT / B.SHARED["collector"]).read_text(encoding="utf-8")
    mutant = src.replace('c.kind === "generation" && !c.annotated && !c.written', 'c.served && !c.annotated && !c.written')
    if mutant == src:
        print("  FAIL  behaviour teeth: the absorb filter mutation did not apply")
        return bad + 1, 2
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "model-calls.mutant.ts")
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(mutant)
        r = subprocess.run([node, test], cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=120, env={**os.environ, "WH_MODEL_CALLS_SRC": p})
    if r.returncode != 0 and "FAIL  exhausted walk + logAICost = exactly one row" in r.stdout:
        print("  ok    behaviour teeth: a served-only absorb filter writes two rows for one exhausted call - caught")
    else:
        print("  FAIL  behaviour teeth: the double-row mutant passed test_model_call_records.mjs")
        bad += 1
    return bad, 2


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else run())
