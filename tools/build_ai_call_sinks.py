"""
build_ai_call_sinks.py - what ONE successful model call leaves behind, per edge function, derived from source.

★WHY (LM-O walk, LM544, alert-hub, 2026-10-08). An operator asked "where is the record of the call that answered
alert-hub's question?" and the answer was: nowhere. analytics-orchestrator imported logAICost and never called it,
serveObserved wrote wh_traces only on an unhandled throw, and the only trace was the edge stdout line
"[ai-chain] served by ...". The table the walk used to say which functions record what (O_SINK in
tools/lm_walk.body.js) was hand-typed, so it went stale the day it was written. This file is computed from the code
on every run instead, and tools/validate_ai_call_sinks.py fails when it is stale.

The mechanism it reads (one place, not thirty):
  _shared/ai-chain.ts       callAI / callAIMultimodal report every SERVED call -> reportModelCall()
  _shared/model-calls.ts    the request-scoped collector (AsyncLocalStorage)
  _shared/observability.ts  serveObserved opens the scope around every handler and, when it returns, writes ONE
                            ai_cost_log row per call: fn, hive, user, provider, model, tokens, latency, outcome,
                            and the trace id the reply carried
  _shared/cost-log.ts       logAICost inside a scope ANNOTATES the call it follows (never a second row)
A function that calls a provider itself (not through the chain) must call reportModelCall() itself.

★2026-10-08, same day - three calls the first version did not see, now each a rule:
  * a walk that EXHAUSTS every provider: callAI / callAIMultimodal must report it (reportModelCallFailed) before they
    degrade to "{}", and logAICost's absorbCostEntry must annotate that record (no second row) - so a failed call
    is exactly one failed row whether or not the function logs it;
  * embedding / rerank / speech-to-text / text-to-speech calls: the shared chains (embedding-chain.ts, audio-chain.ts)
    must report every served call and every exhausted walk with its kind, and a function that calls such a provider
    directly must report it itself - these functions are now model-calling functions like any other (served through
    serveObserved, returning the trace id their rows carry);
  * a model call raced against a deadline by hand (Promise.race around callAI): raceModelCall instead, which records
    the call it stopped waiting for once, late, under the reply's trace id.

Per function the JSON says: does it call a model (how, how many sites); does one successful call leave a per-call
record (which table, written by what); where the record's trace id comes from (the id the reply returns); how the
caller (user / hive) is attributed; what its own logAICost calls do; and which tables its output lands in, with any
provenance keys written beside it (a source-text heuristic, labelled as such).

    python tools/build_ai_call_sinks.py            # write tools/ai_call_sinks.json
    python tools/build_ai_call_sinks.py --print    # print the table, write nothing
Static, no DB, no browser.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Callable

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
FN_DIR = "supabase/functions"
OUT_REL = "tools/ai_call_sinks.json"
RECORD_TABLE = "ai_cost_log"

SHARED = {
    "chain":      f"{FN_DIR}/_shared/ai-chain.ts",
    "collector":  f"{FN_DIR}/_shared/model-calls.ts",
    "writer":     f"{FN_DIR}/_shared/observability.ts",
    "cost_log":   f"{FN_DIR}/_shared/cost-log.ts",
    "trace":      f"{FN_DIR}/_shared/trace-reply.ts",
    "tenant":     f"{FN_DIR}/_shared/tenant-context.ts",
    "embedding":  f"{FN_DIR}/_shared/embedding-chain.ts",
    "audio":      f"{FN_DIR}/_shared/audio-chain.ts",
}
# modules that are part of the mechanism (never counted as a "shared model caller")
MECHANISM_MODULES = {"ai-chain.ts", "model-calls.ts", "cost-log.ts", "observability.ts", "embedding-chain.ts",
                     "audio-chain.ts"}

PROVIDER_URL = re.compile(r"""["'`]https://[^"'`]*?/chat/completions["'`]""")
CALL_AI = re.compile(r"(?<![\w$.])callAI\s*\(")
CALL_AI_MM = re.compile(r"(?<![\w$.])callAIMultimodal\s*\(")
REPORT = re.compile(r"(?<![\w$.])reportModelCall\s*\(")
REPORT_FAILED = re.compile(r"(?<![\w$.])reportModelCallFailed\s*\(")
# non-generation model calls made through a shared chain (embedding-chain.ts also holds the reranker)
NON_GEN = {
    "embedding": re.compile(r"""from\s+["']\.\./_shared/embedding-chain\.ts["']"""),
    "transcription": re.compile(r"""from\s+["']\.\./_shared/audio-chain\.ts["']"""),
}
# non-generation provider calls a function makes ITSELF (it must report them itself)
DIRECT_NON_GEN = {
    "embedding": re.compile(r"""["'`]https://[^"'`]*?/embeddings["'`]"""),
    "transcription": re.compile(r"""["'`]https://[^"'`]*?/audio/transcriptions["'`]"""),
    "speech": re.compile(r"""tts\.speech\.microsoft\.com|["'`]https://[^"'`]*?/audio/speech["'`]"""),
}
PROVENANCE_KEYS = ("trace_id", "source_trace_id", "model", "model_version", "ai_model", "served_by", "generated_by",
                   "ai_drafted", "ai_generated", "ai_draft", "provider")

Reader = Callable[[str], "str | None"]


def disk_reader(root: Path = ROOT) -> Reader:
    def read(rel: str) -> str | None:
        p = root / rel
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
    return read


def list_function_dirs(root: Path = ROOT) -> list[str]:
    base = root / FN_DIR
    return sorted(d.name for d in base.iterdir()
                  if d.is_dir() and not d.name.startswith("_") and (d / "index.ts").is_file())


def list_fn_files(fn: str, root: Path = ROOT) -> list[str]:
    base = root / FN_DIR / fn
    return sorted(f"{FN_DIR}/{fn}/{p.name}" for p in base.glob("*.ts") if not p.name.endswith(".test.ts"))


_REGEX_PREV = set("(,=:[!&|?{};+-*%<>~^")


def strip_comments(src: str) -> str:
    """Blank out // and /* */ comments with a small tokenizer that skips string, template and regex literals, so a
    "image/*" in a string or a /["']/ regex cannot open a fake comment (a naive block-comment regex sweep once ate a real
    callAI site). Newlines are kept, so line numbers still match the file."""
    out: list[str] = []
    i, n = 0, len(src)
    prev = ""  # last significant (non-space) code char, for the regex-vs-division call
    while i < n:
        c = src[i]
        nx = src[i + 1] if i + 1 < n else ""
        if c == "/" and nx == "/":
            j = src.find("\n", i)
            j = n if j < 0 else j
            i = j
            continue
        if c == "/" and nx == "*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append("\n" * src.count("\n", i, j))
            i = j
            continue
        if c in "'\"`":
            j = i + 1
            depth = 0
            while j < n:
                d = src[j]
                if d == "\\":
                    j += 2
                    continue
                if c == "`" and d == "$" and j + 1 < n and src[j + 1] == "{":
                    depth += 1
                    j += 2
                    continue
                if c == "`" and depth and d == "}":
                    depth -= 1
                elif d == c and not depth:
                    break
                elif d == "\n" and c != "`":
                    break
                j += 1
            out.append(src[i:j + 1])
            prev = c
            i = j + 1
            continue
        if c == "/" and (prev in _REGEX_PREV or prev == "" or re.search(r"\b(return|typeof|case|in|of)\s*$", "".join(out[-3:])[-12:])):
            j = i + 1
            in_class = False
            while j < n and src[j] != "\n":
                d = src[j]
                if d == "\\":
                    j += 2
                    continue
                if d == "[":
                    in_class = True
                elif d == "]":
                    in_class = False
                elif d == "/" and not in_class:
                    break
                j += 1
            out.append(src[i:j + 1])
            prev = "/"
            i = j + 1
            continue
        out.append(c)
        if not c.isspace():
            prev = c
        i += 1
    return "".join(out)


def sha(text: str | None) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def _span(code: str, open_idx: int, op: str = "{", cl: str = "}") -> str:
    depth = 0
    for i in range(open_idx, len(code)):
        c = code[i]
        if c == op:
            depth += 1
        elif c == cl:
            depth -= 1
            if depth == 0:
                return code[open_idx:i + 1]
    return ""


def fn_body(code: str, name: str) -> str:
    m = re.search(r"(?:export\s+)?(?:async\s+)?function\s+" + re.escape(name) + r"\s*(?:<[^>]*>)?\s*\(", code)
    if not m:
        return ""
    # skip the parameter list and any return-type annotation (which may hold braces of its own, as in
    # Promise<{ vector: number[] }>), then take the brace-balanced body
    p = _span(code, m.end() - 1, "(", ")")
    rest = m.end() - 1 + len(p)
    angle = 0
    for i in range(rest, len(code)):
        c = code[i]
        if c == "<":
            angle += 1
        elif c == ">" and code[i - 1] != "=":
            angle -= 1
        elif c == "{" and angle <= 0:
            return _span(code, i)
    return ""


# ── the shared mechanism ──────────────────────────────────────────────────────────────────────────────────────────
def check_mechanism(read: Reader) -> dict:
    """Each shared piece the per-call record depends on, with the finding when it is broken."""
    out: dict[str, dict] = {}

    col = strip_comments(read(SHARED["collector"]) or "")
    f = []
    if not re.search(r"""import\s*\{\s*AsyncLocalStorage\s*\}\s*from\s*["']node:async_hooks["']""", col):
        f.append("model-calls.ts does not scope the collector with AsyncLocalStorage (node:async_hooks)")
    for name in ("reportModelCall", "reportModelCallFailed", "raceModelCall", "withModelCallScope",
                 "takeModelCallRows", "absorbCostEntry", "noteModelCaller"):
        if not re.search(r"export\s+function\s+" + name + r"\b", col):
            f.append(f"model-calls.ts does not export {name}()")
    rows = fn_body(col, "takeModelCallRows")
    for key in ("fn", "kind", "trace_id", "auth_uid", "hive_id", "provider", "model", "prompt_tokens", "output_tokens",
                "latency_ms", "status", "providers_tried", "late"):
        if not re.search(r"\b" + key + r"\s*:", rows):
            f.append(f"takeModelCallRows() builds no `{key}` - the per-call record would not carry it")
    # logAICost after an exhausted walk must ANNOTATE the failed record the chain reported, not add a second row:
    # absorbCostEntry's target search may not require the call to have served
    absorb = fn_body(col, "absorbCostEntry")
    loop = re.search(r"for\s*\(\s*let\s+i\s*=\s*scope\.calls\.length\s*-\s*1[\s\S]{0,300}?if\s*\(([^)]*)\)", absorb)
    if not loop:
        f.append("absorbCostEntry() has no search for the call it annotates - logAICost would add a second row")
    elif re.search(r"\.served\b", loop.group(1)):
        f.append("absorbCostEntry() annotates only a SERVED call - after an exhausted walk logAICost writes a second "
                 "failed row beside the one the chain reported")
    elif not re.search(r"\.kind\s*===\s*[\"']generation[\"']", loop.group(1)):
        f.append("absorbCostEntry() may annotate an embedding / speech call with a generation call's verdict - its "
                 "target search must be limited to kind generation")
    out["collector"] = {"file": SHARED["collector"], "ok": not f, "findings": f}

    obs = strip_comments(read(SHARED["writer"]) or "")
    f = []
    wo = fn_body(obs, "withObservability")
    if not re.search(r"withModelCallScope\s*\(", wo):
        f.append("withObservability does not run the handler inside withModelCallScope() - no request collects its calls")
    if not re.search(r"settleModelCalls\s*\(", wo):
        f.append("withObservability never calls settleModelCalls() - collected calls are never written")
    wr = fn_body(obs, "writeModelCalls")
    if not re.search(r"""\.from\(\s*["']ai_cost_log["']\s*\)\s*\.insert\(""", wr):
        f.append("writeModelCalls() does not insert into ai_cost_log")
    if "takeModelCallRows(" not in wr:
        f.append("writeModelCalls() does not take the collected rows (takeModelCallRows)")
    if "x-wh-trace" not in fn_body(obs, "replyTraceId"):
        f.append("replyTraceId() does not read the reply's x-wh-trace - the record would not carry the id the page got")
    out["writer"] = {"file": SHARED["writer"], "ok": not f, "findings": f}

    chain_raw = read(SHARED["chain"]) or ""
    chain = strip_comments(chain_raw)
    f = []
    lines = chain.split("\n")
    served = [i for i, l in enumerate(lines) if re.search(r"served by", l) and "console.log" in l]
    returns = [i for i, l in enumerate(lines) if re.search(r"\breturn\s+stripped\s*;", l)]
    for i in served:
        if not any(REPORT.search(lines[j]) for j in range(i, min(len(lines), i + 8))):
            f.append(f"ai-chain.ts line {i + 1}: a 'served by' success path does not reportModelCall() within 8 lines")
    for i in returns:
        if not any(REPORT.search(lines[j]) for j in range(max(0, i - 25), i)):
            f.append(f"ai-chain.ts line {i + 1}: `return stripped` (a served answer) with no reportModelCall() before it")
    if not served:
        f.append("ai-chain.ts has no 'served by' success line to anchor on - the check cannot see the success paths")
    for name in ("callAI", "callAIMultimodal"):
        body = fn_body(chain, name)
        if not REPORT.search(body):
            f.append(f"{name}() never calls reportModelCall() - its served calls leave no record")
        last = body.rfind('return "{}"')
        if last < 0 or not REPORT_FAILED.search(body[max(0, last - 700):last]):
            f.append(f"{name}() degrades to \"{{}}\" without reportModelCallFailed() - a walk no provider served "
                     f"leaves no record unless the function happens to log it")
    out["chain"] = {"file": SHARED["chain"], "ok": not f, "findings": f,
                    "success_paths": len(served), "reports": len(REPORT.findall(chain)),
                    "exhausted_reports": len(REPORT_FAILED.findall(chain))}

    emb = strip_comments(read(SHARED["embedding"]) or "")
    f = []
    gt = fn_body(emb, "generateEmbeddingTagged")
    if not re.search(r"""reportModelCall\(\{[^}]*kind:\s*["']embedding["']""", gt):
        f.append("generateEmbeddingTagged() does not report the embedding a provider answered (kind embedding)")
    thr = gt.rfind("All embedding providers failed")
    if thr < 0 or not REPORT_FAILED.search(gt[max(0, thr - 500):thr]):
        f.append("generateEmbeddingTagged() throws 'All embedding providers failed' without reportModelCallFailed()")
    rr = fn_body(emb, "rerank")
    if not REPORT.search(rr) or not REPORT_FAILED.search(rr):
        f.append("rerank() does not report its call (served and failed) - a rerank is a model call too")
    out["embedding"] = {"file": SHARED["embedding"], "ok": not f, "findings": f}

    aud = strip_comments(read(SHARED["audio"]) or "")
    f = []
    for name in ("transcribeLocal", "transcribeAudio"):
        if not re.search(r"""reportModelCall\(\{[^}]*kind:\s*["']transcription["']""", fn_body(aud, name)):
            f.append(f"{name}() does not report the transcription a provider answered (kind transcription)")
    ta = fn_body(aud, "transcribeAudio")
    thr = ta.rfind("All Whisper models unavailable")
    if thr < 0 or not REPORT_FAILED.search(ta[max(0, thr - 300):thr]):
        f.append("transcribeAudio() throws when no model answered without reportModelCallFailed()")
    out["audio"] = {"file": SHARED["audio"], "ok": not f, "findings": f}

    cl = strip_comments(read(SHARED["cost_log"]) or "")
    f = []
    body = fn_body(cl, "logAICost")
    a = body.find("absorbCostEntry(")
    ins = body.find(".insert(")
    if a < 0 or (ins >= 0 and a > ins):
        f.append("logAICost() inserts before asking the request's collector (absorbCostEntry) - a function that "
                 "still calls it would write a SECOND row for a call the collector already records")
    out["cost_log"] = {"file": SHARED["cost_log"], "ok": not f, "findings": f}

    tr = strip_comments(read(SHARED["trace"]) or "")
    f = []
    if not re.search(r"noteModelTrace\s*\(", fn_body(tr, "tracedReply")):
        f.append("tracedReply() does not note its trace id into the model-call scope")
    out["trace"] = {"file": SHARED["trace"], "ok": not f, "findings": f}

    return out


def schema_has_record_columns(root: Path = ROOT) -> dict:
    """Migrations add the columns the record writes: trace_id + auth_uid (who / which reply), and kind +
    providers_tried + late + audio_seconds (what kind of call, the slots asked, finished after the reply)."""
    want = {"trace_id": False, "auth_uid": False, "kind": False, "providers_tried": False, "late": False,
            "audio_seconds": False}
    for p in sorted((root / "supabase" / "migrations").glob("*.sql")):
        sql = p.read_text(encoding="utf-8", errors="replace")
        for stmt in re.findall(r"alter\s+table\s+(?:only\s+)?(?:public\.)?ai_cost_log\b([^;]+);", sql, re.I):
            for col in want:
                if re.search(r"add\s+column\s+(?:if\s+not\s+exists\s+)?" + col + r"\b", stmt, re.I):
                    want[col] = True
    return {"ok": all(want.values()), "columns": want}


# ── per function ──────────────────────────────────────────────────────────────────────────────────────────────────
def shared_model_callers(read: Reader, root: Path = ROOT) -> set[str]:
    """_shared modules (outside the mechanism) that call the chain themselves - a function importing one calls a model."""
    out = set()
    for p in sorted((root / FN_DIR / "_shared").glob("*.ts")):
        if p.name in MECHANISM_MODULES or p.name.endswith(".test.ts"):
            continue
        code = strip_comments(read(f"{FN_DIR}/_shared/{p.name}") or "")
        if CALL_AI.search(code) or CALL_AI_MM.search(code) or PROVIDER_URL.search(code):
            out.add(p.name)
    return out


def shared_non_gen_callers(read: Reader, root: Path = ROOT) -> dict[str, list[str]]:
    """_shared modules (outside the mechanism) that import a non-generation chain: a function importing one makes
    those calls too."""
    out: dict[str, list[str]] = {}
    for p in sorted((root / FN_DIR / "_shared").glob("*.ts")):
        if p.name in MECHANISM_MODULES or p.name.endswith(".test.ts"):
            continue
        code = strip_comments(read(f"{FN_DIR}/_shared/{p.name}") or "")
        kinds = sorted(k for k, rx in NON_GEN.items() if re.search(rx.pattern.replace(r"\.\./_shared/", r"\./"), code))
        if kinds:
            out[p.name] = kinds
    return out


def output_writes(code: str) -> list[dict]:
    """tables the function inserts/upserts/updates, and provenance keys written in the same payload (heuristic)."""
    out: dict[tuple[str, str], set[str]] = {}
    for m in re.finditer(r"""\.from\(\s*["'](\w+)["']\s*\)\s*\.(insert|upsert|update)\s*\(""", code):
        table, op = m.group(1), m.group(2)
        if table == RECORD_TABLE:
            continue
        arg = _span(code, m.end() - 1, "(", ")")[:2500]
        keys = {k for k in PROVENANCE_KEYS if re.search(r"(?<![\w$.])" + k + r"\s*[:,}]", arg)}
        out.setdefault((table, op), set()).update(keys)
    return [{"table": t, "op": o, "provenance_keys": sorted(k)} for (t, o), k in sorted(out.items())]


def analyze_function(fn: str, read: Reader, files: list[str], shared_callers: set[str],
                     shared_non_gen: dict[str, list[str]] | None = None) -> dict | None:
    srcs = {f: read(f) or "" for f in files}
    index_rel = f"{FN_DIR}/{fn}/index.ts"
    code_all = "\n".join(strip_comments(s) for s in srcs.values())
    idx = strip_comments(srcs.get(index_rel, ""))

    kinds: dict[str, int] = {}
    n_text = len(CALL_AI.findall(code_all))
    n_vision = len(CALL_AI_MM.findall(code_all))
    n_direct = len(PROVIDER_URL.findall(code_all))
    if n_text:
        kinds["callAI"] = n_text
    if n_vision:
        kinds["callAIMultimodal"] = n_vision
    if n_direct:
        kinds["direct provider fetch"] = n_direct
    via_shared = sorted(m for m in shared_callers
                        if re.search(r"""from\s+["']\.\./_shared/""" + re.escape(m) + r"""["']""", code_all))
    if via_shared:
        kinds["via _shared " + ", ".join(via_shared)] = 1
    non_gen = {k for k, rx in NON_GEN.items() if rx.search(code_all)}
    for m, ks in (shared_non_gen or {}).items():
        if re.search(r"""from\s+["']\.\./_shared/""" + re.escape(m) + r"""["']""", code_all):
            non_gen.update(ks)
    direct_non_gen = {k for k, rx in DIRECT_NON_GEN.items() if rx.search(code_all)}
    non_gen_all = sorted(non_gen | direct_non_gen)
    if not kinds and not non_gen_all:
        return None

    findings: list[str] = []
    scoped = bool(re.search(r"""serveObserved\(\s*["']""" + re.escape(fn) + r"""["']""", idx))
    if not scoped:
        findings.append("not served through serveObserved(fn, ...) - no request scope collects its model calls, "
                        "so a successful call leaves no record")
    reported_by = []
    if n_text:
        reported_by.append("_shared/ai-chain.ts callAI (success path)")
    if n_vision:
        reported_by.append("_shared/ai-chain.ts callAIMultimodal (success path)")
    if n_direct:
        if REPORT.search(code_all):
            reported_by.append("this function's own reportModelCall() after its provider fetch")
        else:
            findings.append("calls a provider directly (a /chat/completions URL) and never calls reportModelCall() - "
                            "the call bypasses the chain's hook, so it leaves no record")
    for m in via_shared:
        reported_by.append(f"_shared/{m} (through the chain)")
    if "embedding" in non_gen:
        reported_by.append("_shared/embedding-chain.ts generateEmbeddingTagged / rerank (kind embedding / rerank)")
    if "transcription" in non_gen:
        reported_by.append("_shared/audio-chain.ts transcribeAudio (kind transcription)")
    if direct_non_gen:
        if REPORT.search(code_all) and REPORT_FAILED.search(code_all):
            reported_by.append("this function's own reportModelCall() / reportModelCallFailed() after its "
                               + "/".join(sorted(direct_non_gen)) + " provider fetch")
        else:
            findings.append(f"calls a provider directly ({'/'.join(sorted(direct_non_gen))}) and does not report it "
                            "(reportModelCall on success, reportModelCallFailed on failure) - the call leaves no record")
    # a model call raced against a deadline by hand: the call it stops waiting for would land unmarked (or not at all)
    for m in re.finditer(r"Promise\.race\s*\(", code_all):
        seg = _span(code_all, m.end() - 1, "(", ")")
        if CALL_AI.search(seg) or CALL_AI_MM.search(seg):
            findings.append("races a model call by hand (Promise.race around callAI) - use raceModelCall "
                            "(_shared/model-calls.ts), which records the call it stopped waiting for once, late, under "
                            "the reply's trace id")
            break

    wrapped = bool(re.search(r"""serveObserved\(\s*["']""" + re.escape(fn) + r"""["']\s*,\s*tracedReply\(\s*["']"""
                             + re.escape(fn) + r"""["']""", idx))
    if wrapped:
        trace_src = "tracedReply: the id minted once per request, returned on every JSON reply (x-wh-trace)"
    elif re.search(r"\breturn\s+ok\(", idx) and re.search(r"jsonResponse\([^;]*ctx\.trace_id", idx, re.S):
        trace_src = "ok() envelope + refusals stamped with ctx.trace_id (x-wh-trace)"
    else:
        trace_src = None
        findings.append("returns no trace id the page can keep (not wrapped serveObserved(fn, tracedReply(fn, ...)), "
                        "no ok() envelope) - its record's trace id would name nothing the page or a rating holds")

    attrib = []
    if re.search(r"(?<![\w$.])(resolveTenancy|resolveContext)\s*\(", code_all):
        attrib.append("tenant-context resolveTenancy/resolveContext (verified hive + user)")
    if re.search(r"(?<![\w$.])(resolveIdentity|requireServiceRole)\s*\(", code_all):
        attrib.append("tenant-context resolveIdentity (verified user)")
    if re.search(r"(?<![\w$.])noteModelCaller\s*\(", code_all):
        attrib.append("noteModelCaller at the line that verifies")
    if re.search(r"(?<![\w$.])withModelCaller\s*\(", code_all):
        attrib.append("withModelCaller per hive (fan-out)")
    if "claimed_hive_id" in code_all:
        attrib.append("claimed hive, verified by the writer against v_worker_truth")
    attrib.append("fallback: the bearer, verified by auth at write time")
    hand_verified = bool(re.search(r"""from\(\s*["']v_worker_truth["']\s*\)[\s\S]{0,200}?\.eq\(\s*["']hive_id["']""",
                                   code_all) and re.search(r"""\.eq\(\s*["']auth_uid["']""", code_all))
    if hand_verified and not re.search(r"(?<![\w$.])(noteModelCaller|resolveTenancy|resolveContext)\s*\(", code_all):
        findings.append("verifies hive membership by hand (v_worker_truth) and never notes it (noteModelCaller) - its "
                        "records would carry no hive, so the hive's members cannot read them on ai-quality.html")

    n_cost = len(re.findall(r"(?<![\w$.])logAICost\s*\(", code_all))
    direct_ledger = bool(re.search(r"""\.from\(\s*["']ai_cost_log["']\s*\)\s*\.(insert|upsert)\(""", code_all))
    if direct_ledger:
        findings.append("inserts into ai_cost_log itself - a second row beside the one the request scope writes")
    if re.search(r"logAICost\s*\(\s*\w+\s*,\s*\{[^}]*model\s*:\s*`gateway:", code_all, re.S):
        findings.append("logs a per-turn `gateway:<fn>` row - the specialist already records the call it forwarded")

    per_call = scoped and not any("bypasses the chain" in x or "does not report it" in x for x in findings) \
        and not direct_ledger
    return {
        "calls_model": True,
        "model_call_kinds": kinds,
        "model_call_sites": n_text + n_vision + n_direct + sum(len(rx.findall(code_all)) for rx in DIRECT_NON_GEN.values()),
        "per_call_record": per_call,
        "record_table": RECORD_TABLE if per_call else None,
        "record_written_by": "serveObserved -> settleModelCalls (_shared/observability.ts), one row per served call"
                             if per_call else None,
        "reported_by": reported_by,
        "record_trace_id": trace_src,
        "caller_attribution": attrib,
        "own_logAICost_calls": n_cost,
        "own_logAICost_role": ("annotates the served call it follows (schema_compliance / prompt_hash / status) - "
                               "no second row; a failed attempt with nothing served is one 'failed' row")
                              if n_cost else None,
        "non_generation_model_calls": non_gen_all,
        "output_writes": output_writes(code_all),
        "findings": findings,
        "source_sha256": sha("".join(srcs[f] for f in sorted(srcs))),
    }


def build(read: Reader | None = None, root: Path = ROOT, fns: list[str] | None = None) -> dict:
    read = read or disk_reader(root)
    mech = check_mechanism(read)
    schema = schema_has_record_columns(root)
    shared_callers = shared_model_callers(read, root)
    shared_non_gen = shared_non_gen_callers(read, root)
    functions = {}
    for fn in (fns if fns is not None else list_function_dirs(root)):
        r = analyze_function(fn, read, list_fn_files(fn, root), shared_callers, shared_non_gen)
        if r is None:
            continue
        functions[fn] = r
    mech_ok = all(v["ok"] for v in mech.values()) and schema["ok"]
    recorded = sorted(f for f, r in functions.items() if r["per_call_record"] and mech_ok)
    return {
        "schema": "ai_call_sinks/v2",
        "generated_by": "tools/build_ai_call_sinks.py",
        "record_table": RECORD_TABLE,
        "record_fields": ["fn", "kind", "trace_id", "auth_uid", "hive_id", "worker_name", "provider", "model",
                          "prompt_tokens", "output_tokens", "tokens_estimated", "latency_ms", "status",
                          "schema_compliance", "prompt_hash", "providers_tried", "audio_seconds", "late"],
        "mechanism": {**mech, "schema": schema, "ok": mech_ok},
        "summary": {
            "model_calling_functions": len(functions),
            "per_call_record": len(recorded),
            "no_per_call_record": sorted(set(functions) - set(recorded)),
            "returns_trace_id": len([1 for r in functions.values() if r["record_trace_id"]]),
            "functions_with_findings": sorted(f for f, r in functions.items() if r["findings"]),
            "by_kind": {k: sorted(f for f, r in functions.items()
                                  if (k == "generation" and r["model_call_kinds"]) or k in r["non_generation_model_calls"])
                        for k in ("generation", "embedding", "transcription", "speech")},
        },
        "functions": functions,
        "sources": {k: sha(read(v)) for k, v in sorted(SHARED.items())},
    }


def render(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=False, ensure_ascii=False) + "\n"


def main() -> int:
    doc = build()
    if "--print" in sys.argv:
        print(f"{'function':30s} {'record':7s} {'calls':6s} {'kinds':28s} trace-id source")
        for fn, r in doc["functions"].items():
            ks = ",".join((["generation"] if r["model_call_kinds"] else []) + r["non_generation_model_calls"])
            print(f"{fn:30s} {'yes' if r['per_call_record'] else 'NO':7s} {r['model_call_sites']:<6d} {ks[:28]:28s} "
                  f"{(r['record_trace_id'] or 'NONE')[:50]}")
        print(json.dumps(doc["summary"], indent=2))
        return 0
    out = ROOT / OUT_REL
    text = render(doc)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    s = doc["summary"]
    print(f"wrote {OUT_REL}: {s['per_call_record']}/{s['model_calling_functions']} model-calling functions leave a "
          f"per-call record; mechanism ok={doc['mechanism']['ok']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
