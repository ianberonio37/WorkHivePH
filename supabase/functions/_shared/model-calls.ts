// _shared/model-calls.ts
// ★AN ANSWER LEFT NO RECORD AN OPERATOR COULD READ (LM-O walk, LM544, alert-hub, 2026-10-08). alert-hub.html's ask
// reached analytics-orchestrator, which imported logAICost and never called it; serveObserved wrote wh_traces only on
// an unhandled throw; the one trace of the call was the edge stdout line "[ai-chain] served by ...". Nineteen of the
// twenty-nine functions that call a model were in that state, and the ten that did log wrote a hand-typed model
// name ("chain:auto", "callAI-chain", "gateway:<fn>") with no trace id and no user - two of them one aggregate row
// per run, the gateway one pseudo row per turn - so even a logged row could not be tied to the answer a person saw.
//
// The fix is one place, not thirty: the model chain REPORTS every call that served (reportModelCall - ai-chain.ts's
// success paths, and any function that calls a provider itself), into a collector scoped to the request by
// AsyncLocalStorage. serveObserved (observability.ts) opens the scope around every handler and, when the handler
// returns, writes ONE ai_cost_log row per reported call: fn, hive, user (auth_uid + worker_name), the provider and
// model that actually served, tokens (the provider's own usage figure when it gives one, else an estimate, flagged),
// latency, outcome, and the trace id the reply carried (its x-wh-trace header - the id tracedReply / ok() / fail()
// returned to the page). The write is best-effort: it never changes the reply.
//
// Who the call was for comes from the VERIFIED identity, never from a body field: tenant-context.ts's resolveIdentity
// / resolveTenancy note it (noteModelCaller) as they verify, and a function that verifies by hand notes it at the
// line it verifies. A cron fan-out that serves several hives notes each hive before the calls it makes for it - every
// call snapshots the caller at the moment it served.
//
// logAICost (cost-log.ts) inside a scope does not write a second row: it ANNOTATES the served call it follows
// (schema_compliance, prompt_hash, a fallback/failed status the function decided) - or, when nothing served (the
// chain returned "{}"), it records that attempt as one failed row. So every model call ends as exactly one record.
//
// ★THREE CALLS THE FIRST VERSION DID NOT SEE (2026-10-08, same day). (1) A chain that EXHAUSTED every provider reported
// nothing, so the attempt existed only if the function's own logAICost ran: callAI / callAIMultimodal now report it
// (reportModelCallFailed: status failed, the slots asked and how each answered, the latency the person waited), and a
// later logAICost annotates that row instead of adding a second. (2) Embedding, rerank, speech-to-text and
// text-to-speech calls left no record at all: the shared chains (embedding-chain.ts, audio-chain.ts) and the functions
// that call such a provider directly now report them, each with its `kind`. (3) A call the function stopped waiting for
// (raceModelCall - amc-orchestrator's 45 s deadline) is recorded ONCE when it finishes, `late`, under the reply's trace
// id, and status fallback when it served: the reply did not use it. The worker is kept alive until it settles.
//
// Gate: tools/validate_ai_call_sinks.py (reads tools/ai_call_sinks.json, built by tools/build_ai_call_sinks.py).

import { AsyncLocalStorage } from "node:async_hooks";

export type ModelCallStatus = "success" | "fallback" | "failed";
/** what the call was (ai_cost_log.kind) */
export type ModelCallKind = "generation" | "embedding" | "rerank" | "transcription" | "speech";

/** Who a model call was made for. `undefined` = not known yet; `null` = known to be none (a solo caller's hive). */
export interface ModelCaller {
  auth_uid?:        string | null;
  hive_id?:         string | null;
  worker_name?:     string | null;
  /** a hive the request NAMED but the function did not prove (a companion turn): the writer stamps it only after
   *  confirming the verified user is an active member of it, off the answer path. Never written as-is. */
  claimed_hive_id?: string | null;
}

export interface ModelCall {
  kind:               ModelCallKind;
  provider:           string;
  model:              string;
  prompt_tokens:      number | null;
  output_tokens:      number | null;
  tokens_estimated:   boolean;
  latency_ms:         number | null;
  status:             ModelCallStatus;
  /** false = an attempt nothing served (a function's logAICost after the chain returned "{}") */
  served:             boolean;
  /** a function's logAICost has already described this call */
  annotated:          boolean;
  schema_compliance:  boolean | null;
  prompt_hash:        string | null;
  user_feedback:      -1 | 0 | 1 | null;
  cost_usd:           number | null;
  /** the slots the chain asked, in order, each with its outcome ("groq/llama-3.3-70b-versatile=429") */
  providers_tried:    string[] | null;
  /** seconds of audio a transcription processed, when the provider says */
  audio_seconds:      number | null;
  /** finished after the function stopped waiting for it, or after the reply was sent */
  late:               boolean;
  /** the caller at the moment the call served */
  caller:             ModelCaller;
  written:            boolean;
}

export interface ModelCallScope {
  fn:        string;
  trace_id:  string | null;
  caller:    ModelCaller;
  calls:     ModelCall[];
  /** the reply has been written; a call reported after this is written on its own by `late` */
  closed:    boolean;
  late:      ((scope: ModelCallScope) => void) | null;
  /** set on the child scope raceModelCall runs a call in: timed_out flips when the function stops waiting */
  abandon?:  { timed_out: boolean } | null;
  /** ★A WALK SPENDS NO MODEL CALL (2026-10-08). Set by withObservability when the request carries
   *  `x-wh-walk-no-model: 1` AND the runtime is LOCAL (SUPABASE_URL host kong/localhost/127.0.0.1 - prod is
   *  *.supabase.co, where the header is ignored). The shared chains (callAI, callAIMultimodal) then answer "{}" before
   *  any provider - the local LLM included - is asked, so each caller's own degraded path runs (engineering-calc-agent's
   *  deterministic report narrative, for one), and the request writes no ai_cost_log row: nothing was attempted. It is
   *  how an MCP walk lives a page whose server writes a model narrative beside deterministic math - the math is the
   *  row's story - without spending a call. A function that calls a provider DIRECTLY (not through the shared chain)
   *  is not covered by it. Child scopes (withModelCaller, raceModelCall) inherit it through their prototype. */
  no_model?: boolean;
  /** LOCAL walk only (observability reads `x-wh-embed-fault`, OWN55 2026-10-27): embedding provider name -> how its REAL
   *  request misbehaves. embedding-chain.ts sends that provider's request to `fake` (tools/fake_ai_provider.py serves
   *  /<mode>/embeddings; "down" is a closed port), so the chain's own timeout, status and shape checks meet the failure -
   *  the embedding twin of ai-chain.ts's faultInject.fake. Child scopes inherit it like no_model. */
  embed_fault?: { fake: string; providers: Record<string, "down" | "slow" | "429" | "changed"> };
  /** one query-embedding walk per (space, text) per request - embedding-chain.ts generateEmbeddingTagged (OWN55, 2026-10-27) */
  embed_memo?: Map<string, Promise<{ vector: number[]; provider: string }>>;
}

/** true when this request asked, on the local runtime, for no model call (see ModelCallScope.no_model) */
export function modelCallsRefused(): boolean {
  return !!currentModelCallScope()?.no_model;
}

/** the URL a LOCAL walk sends this embedding provider's request to instead of `url`, or `url` (see embed_fault) */
export function embedFaultUrl(provider: string, url: string): string {
  const f = currentModelCallScope()?.embed_fault;
  const mode = f?.providers?.[provider];
  if (!f || !mode) return url;
  const base = f.fake.replace(/\/+$/, "");
  return mode === "down" ? base.replace(/:\d+$/, ":9") + "/embeddings" : `${base}/${mode}/embeddings`;
}

const _scopes = new AsyncLocalStorage<ModelCallScope>();

export function newModelCallScope(fn: string): ModelCallScope {
  return { fn, trace_id: null, caller: {}, calls: [], closed: false, late: null };
}

/** Run `body` with `scope` as the request's model-call collector. */
export function withModelCallScope<T>(scope: ModelCallScope, body: () => Promise<T>): Promise<T> {
  return _scopes.run(scope, body);
}

export function currentModelCallScope(): ModelCallScope | undefined {
  try { return _scopes.getStore(); } catch { return undefined; }
}

/** Record who this request's model calls are for. Only VERIFIED values belong here (see the header). */
export function noteModelCaller(caller: ModelCaller): void {
  const scope = currentModelCallScope();
  if (!scope) return;
  for (const k of ["auth_uid", "hive_id", "worker_name", "claimed_hive_id"] as const) {
    const v = caller[k];
    if (v !== undefined) scope.caller[k] = (v === "" ? null : v);
  }
}

/**
 * Run `body` with its own caller - for a fan-out that serves several hives at once (a cron dispatcher's
 * Promise.allSettled over every hive): each branch's calls are recorded for ITS hive. The branch shares the request's
 * calls, trace id and writer (the child scope reads them from the request scope); only the caller is its own.
 */
export function withModelCaller<T>(caller: ModelCaller, body: () => Promise<T>): Promise<T> {
  const parent = currentModelCallScope();
  if (!parent) return body();
  const child = Object.create(parent) as ModelCallScope;
  child.caller = { ...parent.caller };
  for (const [k, v] of Object.entries(caller)) if (v !== undefined) (child.caller as Record<string, unknown>)[k] = v;
  return _scopes.run(child, body);
}

/** Record the trace id this request returns (tracedReply calls it with the id it minted). */
export function noteModelTrace(traceId: string): void {
  const scope = currentModelCallScope();
  if (scope && traceId) scope.trace_id = traceId;
}

function _int(v: unknown): number | null {
  if (v === null || v === undefined || v === "") return null;   // Number(null) is 0 - an absent figure is not zero
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) && n >= 0 ? Math.round(n) : null;
}

/** characters of text in a prompt / messages array / reply, for a token estimate when the provider gives none */
function _chars(v: unknown): number {
  if (typeof v === "string") return v.length;
  if (Array.isArray(v)) return v.reduce((n: number, x) => n + _chars(x), 0);
  if (v && typeof v === "object") {
    const o = v as Record<string, unknown>;
    if (typeof o.content === "string" || Array.isArray(o.content)) return _chars(o.content);
    if (typeof o.text === "string") return o.text.length;
  }
  return 0;
}

// providerName / modelName, as in callAI's onServed meta: a `{ provider: ... }` literal inside ai-chain.ts reads as a
// chain entry to validate_groq_fallback.py's entry-block regex
export interface ServedCall {
  providerName: string;
  modelName:    string;
  /** what the call was; generation when omitted */
  kind?:       ModelCallKind;
  /** the provider's own usage block (OpenAI-compatible: prompt_tokens / completion_tokens; embedding APIs give
   *  prompt_tokens and/or total_tokens) */
  usage?:      { prompt_tokens?: unknown; completion_tokens?: unknown; total_tokens?: unknown } | null;
  /** the prompt or messages sent, and the text that came back - only for an estimate when usage is missing */
  input?:      unknown;
  output?:     unknown;
  latency_ms?: number | null;
  /** performance.now() when the call began (used when latency_ms is not given) */
  started_at?: number | null;
  /** the slots asked before (and including) the one that served, each "<provider>/<model>=<outcome>" */
  tried?:      string[] | null;
  /** seconds of audio a transcription processed, when the provider reports it */
  audio_seconds?: number | null;
}

/** A call that NOTHING served: every slot asked failed (or none could be asked). */
export interface FailedCall {
  kind?:       ModelCallKind;
  /** "chain" for a walk over several providers; the provider's own name for a single-provider call */
  providerName?: string;
  /** "exhausted" for a walk over several providers; the model's name for a single-provider call */
  modelName?:  string;
  tried?:      string[] | null;
  latency_ms?: number | null;
  started_at?: number | null;
}

function _latency(latency_ms: number | null | undefined, started_at: number | null | undefined): number | null {
  let latency = _int(latency_ms);
  if (latency === null && typeof started_at === "number") latency = _int(performance.now() - started_at);
  return latency;
}

function _tried(t: string[] | null | undefined): string[] | null {
  if (!Array.isArray(t) || !t.length) return null;
  return t.slice(0, 40).map((s) => String(s).slice(0, 120));
}

/** The model chain's one hook: a call SERVED. A no-op outside a request scope; never throws. */
export function reportModelCall(served: ServedCall): void {
  try {
    const scope = currentModelCallScope();
    if (!scope) return;
    const kind: ModelCallKind = served.kind || "generation";
    const gen = kind === "generation";
    const u = served.usage || null;
    // a generation call has prompt and completion tokens; an embedding / rerank / speech call has only its input
    // (embedding APIs report it as prompt_tokens or total_tokens); a transcription is billed in seconds, not tokens
    let pt = u ? (_int(u.prompt_tokens) ?? (gen ? null : _int(u.total_tokens))) : null;
    let ot = gen && u ? _int(u.completion_tokens) : null;
    let estimated = false;
    if (pt === null && kind !== "transcription") { pt = Math.round(_chars(served.input) / 4); estimated = true; }
    if (ot === null && gen) { ot = Math.round(_chars(served.output) / 4); estimated = true; }
    const abandoned = Boolean(scope.abandon?.timed_out);
    scope.calls.push({
      kind,
      provider:          String(served.providerName || "unknown"),
      model:             String(served.modelName || "unknown"),
      prompt_tokens:     pt,
      output_tokens:     ot,
      tokens_estimated:  estimated,
      latency_ms:        _latency(served.latency_ms, served.started_at),
      // a call the function stopped waiting for served anyway: the reply did not use it
      status:            abandoned ? "fallback" : "success",
      served:            true,
      annotated:         false,
      schema_compliance: null,
      prompt_hash:       null,
      user_feedback:     null,
      cost_usd:          null,
      providers_tried:   _tried(served.tried),
      audio_seconds:     typeof served.audio_seconds === "number" && served.audio_seconds >= 0
                           ? Math.round(served.audio_seconds * 100) / 100 : null,
      late:              abandoned || scope.closed,
      caller:            { ...scope.caller },
      written:           false,
    });
    if (scope.closed && scope.late) scope.late(scope);
  } catch { /* empty-catch-allow: a record must never break the answer it describes */ }
}

/**
 * The chain's other hook: a call NOTHING served (callAI / callAIMultimodal walked every slot and degraded to "{}",
 * an embedding / transcription chain threw). One failed record with the slots asked and the time the caller waited.
 * A function's own logAICost after it annotates this record rather than adding a second (absorbCostEntry).
 * A no-op outside a request scope; never throws.
 */
export function reportModelCallFailed(failed: FailedCall): void {
  try {
    const scope = currentModelCallScope();
    if (!scope) return;
    scope.calls.push({
      kind:              failed.kind || "generation",
      provider:          String(failed.providerName || "chain"),
      model:             String(failed.modelName || "exhausted"),
      // nothing served, so no provider reported usage and nothing was produced: unknown, not estimated
      prompt_tokens:     null,
      output_tokens:     null,
      tokens_estimated:  false,
      latency_ms:        _latency(failed.latency_ms, failed.started_at),
      status:            "failed",
      served:            false,
      annotated:         false,
      schema_compliance: null,
      prompt_hash:       null,
      user_feedback:     null,
      cost_usd:          null,
      providers_tried:   _tried(failed.tried),
      audio_seconds:     null,
      late:              Boolean(scope.abandon?.timed_out) || scope.closed,
      caller:            { ...scope.caller },
      written:           false,
    });
    if (scope.closed && scope.late) scope.late(scope);
  } catch { /* empty-catch-allow: a record must never break the answer it describes */ }
}

/** Keep the worker alive until `p` settles (EdgeRuntime.waitUntil), so a call still in flight can land its record. */
function _keepAlive(p: Promise<unknown>): void {
  try {
    const rt = (globalThis as { EdgeRuntime?: { waitUntil?: (p: Promise<unknown>) => void } }).EdgeRuntime;
    if (rt && typeof rt.waitUntil === "function") rt.waitUntil(p);
  } catch { /* empty-catch-allow: no runtime hook - the call lands if the worker is still up */ }
}

/**
 * Race a model call against a deadline. On time the call's result comes back as usual. Past the deadline the
 * caller gets a rejection with `timeoutMessage` (as a hand-written Promise.race did), the call keeps running to its
 * end with the worker held open for it, and whatever it reports is recorded ONCE: `late`, under the reply's trace id,
 * status fallback when it served (the reply did not use it) and failed when nothing served.
 */
export function raceModelCall<T>(body: () => Promise<T>, ms: number, timeoutMessage: string): Promise<T> {
  const parent = currentModelCallScope();
  const tag = { timed_out: false };
  let call: Promise<T>;
  if (parent) {
    // shares the request's calls, trace id, caller and writer through the prototype; only `abandon` is its own
    const child = Object.create(parent) as ModelCallScope;
    child.abandon = tag;
    call = _scopes.run(child, body);
  } else {
    call = body();
  }
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      tag.timed_out = true;
      _keepAlive(call.then(() => undefined, () => undefined));
      reject(new Error(timeoutMessage));
    }, ms);
    call.then(
      (v) => { clearTimeout(timer); if (!tag.timed_out) resolve(v); },
      (e) => { clearTimeout(timer); if (!tag.timed_out) reject(e); },
    );
  });
}

/** What a function's own logAICost says about the call it just made (the subset a scope keeps). */
export interface CostAnnotation {
  model?:             string;
  provider?:          string;
  prompt_tokens?:     number;
  output_tokens?:     number;
  latency_ms?:        number;
  status?:            string;
  schema_compliance?: boolean | null;
  user_feedback?:     -1 | 0 | 1 | null;
  prompt_hash?:       string | null;
  cost_usd?:          number;
  worker_name?:       string | null;
}

/**
 * logAICost inside a request scope: annotate the served call it follows instead of writing a second row, or record
 * the attempt as one failed call when nothing served. Returns false outside a scope (the caller writes as before).
 */
export function absorbCostEntry(entry: CostAnnotation): boolean {
  const scope = currentModelCallScope();
  if (!scope) return false;
  try {
    // a cache hit is not a model call (and "cache_hit" never satisfied ai_cost_log's status CHECK - those rows were
    // refused on every insert): nothing to record
    if (/^cache\b|^cache:/i.test(String(entry.model || "")) || entry.status === "cache_hit") return true;
    const status: ModelCallStatus | null =
      entry.status === "failed" || entry.status === "fallback" || entry.status === "success" ? entry.status : null;
    // the call it describes is the last GENERATION call nothing has described yet: one that served, or one the chain
    // reported exhausted (an embedding the function made after its answer is not what its logAICost is about)
    let target: ModelCall | null = null;
    for (let i = scope.calls.length - 1; i >= 0; i--) {
      const c = scope.calls[i];
      if (c.kind === "generation" && !c.annotated && !c.written) { target = c; break; }
    }
    if (target) {
      target.annotated = true;
      // a failed record stays failed (nothing served); a served one takes the function's verdict on it
      if (target.served && status && status !== "success") target.status = status;
      if (entry.schema_compliance !== undefined) target.schema_compliance = entry.schema_compliance;
      if (entry.prompt_hash !== undefined) target.prompt_hash = entry.prompt_hash;
      if (entry.user_feedback !== undefined) target.user_feedback = entry.user_feedback;
      if (typeof entry.cost_usd === "number") target.cost_usd = entry.cost_usd;
      if (target.latency_ms === null) target.latency_ms = _int(entry.latency_ms);
      if (target.caller.worker_name === undefined && entry.worker_name) target.caller.worker_name = entry.worker_name;
      return true;
    }
    // nothing reported this attempt: one failed record, the function's own figures
    scope.calls.push({
      kind:              "generation",
      provider:          String(entry.provider || "chain"),
      model:             String(entry.model || "chain"),
      prompt_tokens:     _int(entry.prompt_tokens),
      output_tokens:     _int(entry.output_tokens),
      tokens_estimated:  true,
      latency_ms:        _int(entry.latency_ms),
      status:            "failed",
      served:            false,
      annotated:         true,
      schema_compliance: entry.schema_compliance ?? null,
      prompt_hash:       entry.prompt_hash ?? null,
      user_feedback:     entry.user_feedback ?? null,
      cost_usd:          typeof entry.cost_usd === "number" ? entry.cost_usd : null,
      providers_tried:   null,
      audio_seconds:     null,
      late:              Boolean(scope.abandon?.timed_out) || scope.closed,
      caller:            { ...scope.caller, ...(scope.caller.worker_name === undefined && entry.worker_name ? { worker_name: entry.worker_name } : {}) },
      written:           false,
    });
    if (scope.closed && scope.late) scope.late(scope);
  } catch { /* empty-catch-allow: an annotation must never break the answer */ }
  return true;
}

/** The ai_cost_log rows for the calls not yet written (marks them written). */
export function takeModelCallRows(scope: ModelCallScope, traceId: string | null): Record<string, unknown>[] {
  const rows: Record<string, unknown>[] = [];
  for (const c of scope.calls) {
    if (c.written) continue;
    c.written = true;
    const caller = { ...scope.caller, ...Object.fromEntries(Object.entries(c.caller).filter(([, v]) => v !== undefined)) };
    rows.push({
      fn:                scope.fn,
      kind:              c.kind,
      trace_id:          traceId,
      auth_uid:          caller.auth_uid ?? null,
      hive_id:           caller.hive_id ?? null,
      worker_name:       caller.worker_name ?? null,
      provider:          c.provider,
      model:             c.model,
      prompt_tokens:     c.prompt_tokens,
      output_tokens:     c.output_tokens,
      tokens_estimated:  c.tokens_estimated,
      latency_ms:        c.latency_ms,
      status:            c.status,
      schema_compliance: c.schema_compliance,
      prompt_hash:       c.prompt_hash,
      user_feedback:     c.user_feedback,
      cost_usd:          c.cost_usd,
      providers_tried:   c.providers_tried,
      audio_seconds:     c.audio_seconds,
      late:              c.late,
    });
  }
  return rows;
}
