# LM-L / LM-E / LM-O instruments (Latency & waiting, Evals & quality gates, Observability)

Built 2026-10-07 for the 51 registry rows `lx.kind == 'llm'`, `lx.sublayer in L/E/O` (LM510-LM560: 17 surfaces x 3,
persona `any`, both viewports). The walk code is `tools/lm_walk_leo_block.js`, which is spliced into
`tools/lm_walk.body.js`. Nothing in it calls a real model: every model function is answered by a browser stub.

## 0. Splicing

The block has three parts between `// ===== LEO PART n BEGIN/END =====` markers. Anchor on the text, not on line
numbers, because the walker is edited while rows are being walked. Each anchor below occurs exactly once in the
walker as of 2026-10-07 (checked).

| Part | What | Where it goes |
|---|---|---|
| 1 | top-level constants (`VARIANTS.leo`, timings, `LEO_ENTRY`, `O_SINK`, `E_COVERAGE`, regexes) | right after `  VARIANTS.proposal = Object.assign({ ok: true, data: PROPOSAL }, PROPOSAL);` |
| 2 | per-viewport `leo` state, an extra `ctx.route('**/functions/v1/**')`, and for E only a `ctx.route('**/rest/v1/ai_reply_feedback**')` | right before `    ctx.on('request', (r) => { try { const h = r.headers(); if (!apikey`. That is, right after the existing functions route closes. |
| 3 | helpers plus the `if (P.sublayer === 'L')`, `'E'` and `'O'` reading blocks | right before `      if (P.sublayer === 'S') {`. That is, after the R block, still inside the per-viewport `try`. |

**How the extra route works with the existing one.** Playwright runs a context's routes in reverse registration
order, so the Part 2 route runs first.

- While `leo.mode === 'off'`, it calls `route.fallback()` for everything. That is always the case outside a Part 3
  pass, so the walker's own first ask on an L/E/O row is still answered 503 by the existing handler (`variant` is null
  for L/E/O).
- Side-effect functions (`send|push|notify|...`) and the helper functions (`semantic-search`, `embed-entry`) always
  fall back to the existing stub.
- Inside a pass, the route answers the model functions itself and records them in `captured` in the existing shape,
  so the hive checks at the end of the walk still read them. The modes are:
  - `answer`: 200 with `VARIANTS.leo` at once.
  - `delay`: the same answer after 12 s.
  - `hang`: the request is held until Part 3 releases it.
  - `fail504`: 504 with the gateway's own sentence ("That assistant could not finish. Try again in a moment.").
- `leo.only` limits a load-time pass to one function. Every other model call during that pass gets `answer`.

**The one change made to the walker's behaviour.** During every L/E/O pass `blockWrites = true`, so the existing REST
route holds every table write. The E route holds `ai_reply_feedback` writes whatever `blockWrites` says, and records
their bodies. That is needed because the existing route records a held write's body only for LM-A.

**Run time per row (estimated).**

| Sub-layer | Per viewport | Notes |
|---|---|---|
| L | about 0.5 min plus the never-answered pass | The never-answered pass runs to the page's own deadline + 12 s: 57 s on resume, ~87 s on most pages, up to 162 s on asset-hub and hive. So 4 to 7 min per L row. |
| E | about 25 s | |
| O | about 30 s | |

## 1. Shared mechanics (Part 3 helpers)

**Which AI is asked (`leoAsk`).** The surface's own AI comes first. The companion on that page is the fallback, and
the fallback is always written as a note.

- `own` (the default):
  1. Take the companion off the page.
  2. Run `OWN_STEPS_ALL[page]`. It counts as scripted only when every step ran and the last step has `calls`.
  3. Otherwise use `askSurface(page, file, false)`.
  4. If no model request arrives within about 3 s, press the page's own AI button. This uses the same
     `OWN_RX` / `BAD_RX` as the S pass.
- `{ load: fn }` (alert-hub, shift-brain): the stub is armed before the navigation, and only `fn` is judged.
- `companion` (logbook, pm-scheduler, skillmatrix, report-sender): these pages' own AI functions are an embedding on
  save, voice, a photo, or a real Send next to the boxes. None of them is a typed or pressed wait.

**The question.** Every pass loads the page fresh and then sets `window.__lmQ`. A reload clears it, and the ask helper
would then type the X-layer injection instead. The question is "What maintenance has been done on
\<groundSubject\> recently?". L's second pass asks "Is \<subject\> due for any work this week?", because the companion
restores its chat history after a reload and the first question would otherwise still be on screen.

**The person's words that must survive.** The question when a box was typed into, the `OWN_STEPS` fill values
(marketplace's title, project-manager's intent text), and resume's PREP line ("Repaired Pump P-204B").

**The in-page stopwatch.** `page.addInitScript` installs a MutationObserver at document start on every load. It
records only while armed: armed right before an ask, or through `sessionStorage.__lmLArm` for a load-time pass. Each
event is stamped with `Date.now()`, the same clock the route uses to stamp requests. An event records whether it was
a working sign, a failure sentence, an acknowledgement or a Stop, whether it was visible, and whether it sat in a live
region (`aria-live` other than `off`, `role=status`, `alert`, `log` or `progressbar`).

**What counts as a working sign (`leoProgNow`).** Any of:
- `aria-busy="true"` or `role=progressbar`
- a class or id matching `typing|spinner|spin|loader|loading|skeleton|shimmer|is-busy|ar-status|refreshing`
- a short visible text matching thinking / working / generating / analyzing / ... or ending in "..." or "…"

Each pass subtracts whatever was already showing before its ask.

**What the regex readings cannot see.** A working state that is neither text, class, aria-busy nor progressbar. An
example would be a canvas animation with no text (none of the 17 surfaces uses one, per source).

## 2. LM-L: Latency & waiting

**Lens.** "I knew it was working; a slow answer was saved, not lost."

**Pass A: the slow answer.** Every judged model request is answered 200 with a valid answer 12 s after it arrives.
Each check below is a problem when it fails, unless marked "note":

| Check | Rule |
|---|---|
| `progressAtMs` | A visible working sign appears within 1.5 s of the request (in-page stamp, or the first 500 ms poll). |
| `announced` | The working sign carried text, inside a live region, during the wait. aria-busy alone does not count: it announces nothing. |
| `signGoneAtMs` | The sign is still showing at every poll from 2 s until 1 s before the answer. This catches a toast that disappears while the answer is still on its way. |
| `typedKept` | The person's words stay visible, or stay in a field, throughout the wait. |
| `answerShownAtMs` | This run's mark is on the page after the answer arrives. A problem for typed asks; a note for structured generators, which render their own fields. |
| abandoned | A problem if the page abandoned the request before its 12 s answer arrived. |
| `stillWorkingAfterAnswer` | A problem if the working sign is still showing 8 s after the answer. |
| `stopControl` | A Stop or Cancel that appeared with the wait. A Cancel already on the page, such as a modal's, does not count. **Recorded as a note, never judged** (known finding: the companion has none). |

**Pass B: an answer that never comes.** Every judged request is held. The walk waits for the page's own deadline + 12 s
(`L_DEADLINE_MS`, at most 165 s). Each of these is a problem:
- No failure sentence by then. The finding names the working sign still showing and the page's own limit.
- The working sign went away and nothing said the answer was not coming. For alert-hub's background brief upgrade this
  is only a note, because the stored brief stays on screen.
- The page said it failed but still shows a working sign.
- The person's words were gone afterwards.
- The page-wide `#wh-connection-notice` appeared (the LM75 class).

If the page never ended the wait by itself, the walk then releases it with a 504 and records what the person reads
next (`afterRelease`). Whether the failure sentence sat in a live region is recorded as a note.

### Per-surface specifics (read from source 2026-10-07; nothing below has been walked yet)

The "Working sign" column is what the page shows while waiting, followed by whether a screen reader is told.

| Surface | How it is reached | Working sign (live region?) | Stop | Own deadline | When it fails |
|---|---|---|---|---|---|
| companion (achievements.html) | `#wh-ai-trigger` > `#wh-ai-input` > `#wh-ai-send` | `#wh-typing-indicator.wh-typing`: 3 empty spans inside `#wh-ai-messages`, which is `role=log` + `aria-live=polite`. It is in a live region **but has no text**. The input and send button are disabled. | none | 75 s (`functions.invoke` aborts with `WH_DB_TIMEOUT`; the direct-fetch fallback uses `fetchWithTimeout(…, 75000)`) | "⚠️ The assistant took too long to answer this time. Please ask again." is added to the log. The question stays as a user bubble; the input box is emptied. |
| assistant.html | `#chat-input` | `#typing-indicator` (aria-busy) with sr-only "Thinking…" and `#typing-note` (`role=status`, with staged notes at 8, 20 and 40 s) | **`#typing-stop` "Stop"** | about 80-92 s (a 50 s Step-1 race, then a 30 s fallback race through agent voice-journal) | whAiError text inline and as a toast (wording not verified) |
| asset-hub.html | `.asset-card` > `#ask-input` > `#ask-send` | `#ask-answer` "Thinking...", `#ask-send` shows "..." and is disabled. **Not in a live region.** | none | **150 s**: the gateway invoke takes 75 s, then the catch falls back to `asset-brain-query` for another 75 s | `whFnError(…,'Could not reach Asset Brain.')` in `#ask-answer`. The input keeps the question. |
| hive.html | `#coach-toggle-btn` > `#coach-input` > `#coach-submit` "Ask" | `#coach-result` "Analyzing your plant data...", `#coach-submit` shows "...". **Not in a live region.** | none | **150 s** (gateway, then `ai-orchestrator` direct) | `#coach-result` "Error: \<message\>" |
| marketplace.html | `#fab-post` > `#post-title` > `#post-ai-assist` | `#post-ai-assist-label` "Thinking…", with `aria-busy` on the button | none | 75 s | Toast: "AI assist is busy right now…" or whAiError. The form keeps the title. |
| project-manager.html | `openAIIntentModal()` > `#ai-intent-text` > `#ai-intent-go` | `#ai-intent-go` "Parsing…", disabled | none (the modal's Cancel was there before the ask, and it does not stop the request) | 75 s | Toast: whFnError "The project assistant did not run. Nothing was changed; try again in a moment." The modal and its text stay. |
| project-report.html | a project link > `#ai-narrative-btn` | the button shows "🤖 Drafting…", disabled | none | 75 s | Toast (`role=alert`): whAiError(error,'AI failed') |
| ph-intelligence.html | `#no-report-state .btn-gold` "Generate Now", only when there is no report and the maturity gate is open | "Generating..." on the button | none | 75 s | Toast "Generation failed: …". Likely unreachable for `any`, so expect the companion fallback. |
| resume.html | PREP line, then the TRIGGER polish | Toast "Polishing your wording…" (`#toast`, `role=alert`), **which disappears after 2.8 s** | none | 45 s (`fetchWithTimeout`) | Toast "That took too long. Please try again." (lasts 2.8 s) |
| analytics.html | TRIGGER recompute/refresh, or the own button | Skeleton cards, the staged "Computing MTBF, MTTR and Availability...", and `#status-text` (`role=status`) | none | 120 s per phase | Toast whAiError "Could not run the analysis. Try again in a moment." |
| analytics-report.html | own button `#generate-btn` "Generate Report" | `.ar-status` (`role=status`, `aria-busy`, `aria-live`) "Compiling analytics across all 4 phases…" | **`#ar-cancel-btn` "Cancel"** | 90 s (its own AbortController) | its own timeout sentence (wording not verified) |
| alert-hub.html | **load**: `analytics-orchestrator` prescriptive (`loadUnifiedAmcBrief`) | `.ah-brief-refreshing` (`role=status`) "↻ Refreshing this brief with live data…" | none | 75 s | The hint is removed and the stored brief stays. No sentence (background: a note). Only runs when a stored brief renders. |
| shift-brain.html | **load**: `shift-planner-orchestrator` auto-generate, only when there is no fresh plan for the current window | `whAiProgress` staged labels in `#sb-verdict-label` / `#sb-verdict-sub` | none | 75 s | `renderPlan()` empty state. A sentence only for a 429. Manual generate is supervisors only, so with a fresh plan this falls back to the companion. |
| logbook, pm-scheduler, skillmatrix, report-sender | companion | (the companion row above) | | | |

Expected from source but **not walked**: asset-hub, hive and the companion will fail "announced"; resume will fail
"sign held" (the toast is gone at 2.8 s); asset-hub and hive will reach 150 s in pass B, which is over the platform's
75 s browser window.

**Banker gates for L** (ids in `run_platform_checks.py`): `waiting-is-spoken`, `a-busy-button-says-working`,
`abort-timeout`, `slow-hint-reads-only`, `outage-copy-honesty`.

## 3. LM-E: Evals & quality gates

**Lens.** "Quality is measured, not claimed."

**Static part.** `E_COVERAGE` (copied into `step.eval.pageCoverage` / `coverage`) names the evaluation that covers
each surface's AI. The banker's postgres witness adds what the runs actually measured.

**Walked part.**
1. The surface's AI gets a 200 answer carrying this run's mark.
2. The walker finds a "was this right?" control that appeared with the answer: `[data-rate="-1"]`, or a button
   labelled wrong / unhelpful / 👎. Controls already on the page before the ask are marked and skipped.
3. It presses the control.
4. The write is **held** by the E route (201, recorded) and judged:
   - The table is `ai_reply_feedback`.
   - `rating === -1`.
   - `answer` contains this run's mark: **the answer's identity**.
   - `question` carries the typed words (a note if not).

Each of these is a problem: an answer shown with no control; a press that wrote nothing; a record without the answer
or with a wrong rating. If the stubbed answer never rendered, the row is unproven. A note always records that
`ai_reply_feedback` has **no call or trace id column**, so a "wrong" can be matched to the call it judged only by
text.

**Feedback controls from source.**

| Control | Where | What it writes |
|---|---|---|
| `whAiTrustRow` (utils.js, `.wh-ai-trust[data-ai-trust]`, buttons `data-rate` 1 / -1, 44px) | asset-hub (Asset Brain answer), analytics (`#results-panel`), resume (`#review-body`, `#cover-letter-panel`), shift-brain (briefing + live Action Brief), voice-journal; and since 2026-10-08 (LM-E fix): hive coach (`#coach-body`, after `#coach-result`), analytics-report (`#ar-ai-synthesis`, section 4.1), alert-hub (`#amc-summary`: stored AMC brief, then the live Action Brief), project-report (`#exec-summary`), project-manager (lessons box), ph-intelligence (each narrative card), report-sender (each `.result-body`), logbook (`#vdc-result` photo diagnosis; `#vf-result` when LOTO / parts / supervisor notes show), engineering-design (`#ed-ai-note`) | Inserts into `ai_reply_feedback` with agent, source, page, persona, question, answer, rating. Says "Recorded as wrong - a person will review it." only when the insert landed. Coverage is certified statically by `ai-trust-row-coverage` (tools/validate_ai_trust_row_coverage.py). |
| Companion `_attachFeedback` (`.wh-msg-rate`, 26px, "Helpful reply" / "Unhelpful reply") | the companion | `source='floating'`. Fire-and-forget: the button tints whatever happened, with no sentence. |
| assistant `_attachChatFeedback` | assistant.html | Own copy, 44px, a `role=status` note, re-enables on failure |
| none, by design (pre-fills) | marketplace listing assist + service triage, project-manager "Parse with AI" wizard, resume upload extract, report-sender voice intent, logbook nameplate OCR, engineering-design BOM/SOW checklist; asset-hub FMEA suggestions are pending rows a supervisor approves | The person reviews and edits the fields (or approves the row), so the edit is the correction; no "was this right?" row is expected there. |

Consumers: ai-quality.html (supervisor), the Grafana founder-ops panel "AI reply feedback (ratings)", and
`tools/companion_harvest.py` (thumbs-down becomes a golden candidate). There are **2 rows ever** (assistant chat,
2026-08-25).

### E coverage map (17 surfaces)

| Surface (functions) | Evaluation, its file, and what it grades |
|---|---|
| companion (ai-gateway > voice-journal) | `tools/companion_{agent,rag,memory,persona,domain,robustness,safety_gaps}_eval.py` + `companion_rigorous_grader.py` (scorecard `companion_eval_scorecard.json`, 8 dimensions: routing, RAG citations, memory + abstention, persona, domain facts, Taglish/noise, injection/leak, latency). Latest results are `.tmp/*_eval_results.json`, dated 2026-06-08 to 06-24. Gates `companion-dim-gate`, `ai-eval-regression` and `companion-diverse-gate` **degrade to SKIP without fresh results**. Canonical agent `voice-journal` has 0 fixtures. |
| alert-hub (analytics-orchestrator, prescriptive) | ai-eval-runner, agent `analytics` (OEE / MTBF-trend). No fixture asks the prescriptive phase. |
| analytics-report (analytics-orchestrator) | ai-eval-runner, agent `analytics` |
| analytics (analytics-orchestrator, batch-risk-scoring) | ai-eval-runner `analytics`. batch-risk-scoring makes no model call (n/a). |
| asset-hub (ai-gateway > asset-brain-query, fmea-populator) | ai-eval-runner `asset-brain` (failure history / PM due / similar pump). `tools/companion_rag_eval.py` (cites the right evidence kinds on HPU-001, 2 abstention controls). fmea-populator: none; `validate_ai_draft_shows_its_basis` checks the draft names its basis, not its quality. |
| assistant (ai-gateway > ai-orchestrator, semantic-search) | Canonical `assistant`: **0 fixtures** (coverage WARN). `tools/companion_memory_eval.py` (agent assistant: recall + abstention). |
| hive (ai-gateway > ai-orchestrator coach) | Canonical `coach`: **0 fixtures**. `tools/fb4_grounding_eval.py` (gate `fb4-grounding-eval`): every asset tag named must be real, and an injection must not leak. Last results 2026-09-29: **2 fabrications in 8 grounding checks** (e.g. "ZZZ-999"). |
| logbook (embed-entry, visual-defect-capture, voice-logbook-entry) | ai-eval-runner `logbook-voice`. visual-defect-capture: none. embed-entry: n/a. |
| marketplace (ai-gateway, marketplace-listing-assist) | ai-eval-runner `service-triage` + `tools/validate_service_triage_eval.py` (gate `service-triage-eval`: the answer is in the DB vocabulary; triage mode only). The parts listing assist: **none**. |
| ph-intelligence (intelligence-report) | none |
| pm-scheduler (embed-entry) | n/a (an embedding). The companion is the AI asked. |
| project-manager (embed-entry, project-orchestrator) | ai-eval-runner `project` (status / blockers / change order). **Not** the intent-parse or lessons-draft phases this page calls. |
| project-report (project-orchestrator) | ai-eval-runner `project`. **Not** the narrative phase. |
| report-sender (scheduled-agents, voice-report-intent, voice-transcribe) | ai-eval-runner `report-voice`. scheduled-agents and voice-transcribe: none. |
| resume (resume-extract, resume-polish) | none. `validate_new_claims_are_opt_in` is a static contract, not a grade. |
| shift-brain (analytics-orchestrator, shift-planner-orchestrator) | ai-eval-runner `shift` (handover / coverage) + `analytics` |
| skillmatrix (embed-entry) | n/a. The companion is the AI asked. |

**What the ai-eval-runner actually measured (read-only SQL, 2026-10-07):**

- Every graded row in `ai_quality_log` failed: **1,765 of 1,765** have `actual_answer = "[gateway error: 401]"`, and
  each agent passed 0 times (asset-brain 0/318, analytics 0/305, project 0/297, shift 0/288, logbook-voice 0/279,
  report-voice 0/278). The cron `ai-eval-daily` (`30 3 * * *`) is still active.
- The cause, from source: `ai-eval-runner` POSTs to `/functions/v1/ai-gateway` with `Authorization: Bearer
  SERVICE_KEY` (index.ts ~L293-309). The gateway resolves `auth.getUser()` from that header, finds no user, and
  returns 401 "Sign-in required" for every agent except voice-journal (`ANON_OK_AGENTS`).
- So the nightly quality measurement has never measured an answer. It records failures that `validate_ai_eval_coverage`
  does not read, because that gate checks that fixtures, the cron and the log table exist, not the scores.
- This is the headline E finding, and it is **not fixed here**. This task does not touch product functions.

**Banker gates for E**: `ai-eval-coverage`, `ai-eval-regression`, `companion-dim-gate`, `fb4-grounding-eval`,
`ai-trust`. Add `service-triage-eval` for marketplace. `ai-asset-versioning` is optional; it covers judge/chain
versioning.

## 4. LM-O: Observability

**Lens.** "Someone can see afterwards what the AI did."

**What the stub bypasses.** The context route answers the page's ask inside the browser, so the request never reaches
Kong or the edge runtime. Nothing is logged server-side for the page's own ask. O evidence therefore comes from three
places.

1. **Static (from source, `O_SINK`):** what one successful call of each reached function leaves behind.
   - `call` is a per-call record an operator can read.
   - `output` is provenance on the row the AI's output was saved to.
   - A reached function with no `call` record is a problem (`O_STATIC_GAP_IS_PROBLEM`), and the source is cited.
2. **Local, at the gateway (live, no model call):** every ai-gateway body the page sent is replayed as the person to
   the gateway's local debug echo with a minted `x-wh-trace` id.
   - The echo answers through `ok()`, which runs `envelope.ts recordTrace()`, a fire-and-forget insert into
     `wh_traces` under that trace id.
   - The walk checks that the trace id came back in the response header or body. `step.obs.traceIds` carries the ids,
     and the banker reads the rows back with SQL.
   - A failing replay, or one returned under a different trace id, is a problem.
3. **The ledger, as the person:** `GET /rest/v1/ai_cost_log` for their hive and the reached functions. RLS lets any
   active member read their hive's rows. This proves the ledger an operator reads holds this surface's calls (from
   earlier live walks). It does not prove the stubbed ask wrote one.

**What one successful call leaves behind (from source).**

| Function | Per-call record | Output provenance |
|---|---|---|
| ai-gateway (any agent except voice-journal) | `ai_cost_log` (fn = the forwarded function, model `gateway:<fn>`, **tokens estimated from text length**) and `wh_traces` (route ai-gateway, hive_id, latency_ms, model_chain; **user_id is never set**: 0 of 537 rows) | none |
| ai-gateway > voice-journal (the companion) | `ai_cost_log` fn voice-journal-agent (written by the agent itself) and `wh_traces` | `voice_journal_entries`: question and reply, the person's Journal |
| marketplace-listing-assist | `ai_cost_log`. Only 10 of 177 rows carry a hive_id, so most are **invisible to hive members**. | `marketplace_listings.ai_assisted_fields` |
| visual-defect-capture | `ai_cost_log` | none |
| intelligence-report, scheduled-agents, batch-risk-scoring | `automation_log` job rows (one per job, not per model call) | `ph_intelligence_reports.generated_at` (intelligence-report) |
| shift-planner-orchestrator, fmea-populator, project-orchestrator | **none** (each imports logAICost and never calls it) | `shift_plans.generated_by` / `generated_at`, `rcm_fmea_modes.source` / `ai_confidence`, `projects.meta._ai_*` |
| analytics-orchestrator, asset-brain-query (direct fallback), ai-orchestrator (direct fallback), resume-polish, resume-extract, voice-logbook-entry, voice-report-intent (direct) | **none**. `serveObserved` writes `wh_traces` only on an unhandled throw. The only trace is the edge stdout line `[ai-chain] served by <provider> / <model> (tokens N)`. | none |

**Who can see each record.**

| Record | Who can read it |
|---|---|
| `ai_cost_log` | hive members (ai-quality.html for supervisors) and Grafana founder-ops ("AI cost", "LLM chain metrics", "LLM token burn by hive") |
| `wh_traces` | **Grafana only** (the `grafana_reader` role, on the SLO dashboard). The RLS for `authenticated` requires a `hive_id` JWT claim that normal sessions do not carry. |
| `ai_reply_feedback` | the author, hive supervisors, Grafana |
| llm-observability.html | nobody: it is retired ("moved to Grafana"). |

**What O can prove locally:**
- which functions the page's ask reached, and with which gateway agent;
- that the gateway honours a caller's `x-wh-trace` and writes a `wh_traces` row for a request, read back by id;
- that the person's request carried no trace id (none of the 17 surfaces sends `x-wh-trace`; only voice-handler.js
  and sw.js do);
- that the hive's `ai_cost_log` is readable by the person and holds rows for these functions;
- from source, which functions write a per-call record at all.

**What O cannot prove locally without a live model call:**
- that a real successful turn writes its `ai_cost_log` row. The echo returns before the per-turn `logAICost`, and the
  forward never happens.
- that the `wh_traces` row of a real turn carries `model_chain` = [target fn] and a realistic latency. The echo row has
  an empty `model_chain`.
- the provider, model and real token count. Only the `[ai-chain] served by` stdout line has them, and the banker can
  grep it from `docker logs` the way the G/R rows do.
- that the specialist's own writes happen: the voice-journal reply update, agent_memory, followups.
- the failure path. A forward that fails returns `jsonResponse(502)`, **not `fail()`**, so a failed gateway turn
  writes **no `wh_traces` row and no `ai_cost_log` row**; only `console.error` remains. This is from source and
  cannot be walked without making a forward fail live.

**The echo replay is not write-free.** The gateway still does several things before the echo returns:
- `consume_ai_global_budget` (an increment);
- the per-(hive, route, hour) counter in `checkRouteRateLimit`;
- for some agents, `generateEmbedding` for procedure and journal recall;
- for the **voice-journal** agent, a **persisted `voice_journal_entries` row** (the persist-first write at ~L1021
  happens before the echo). That is why `O_REPLAY_JOURNAL_AGENTS = false`: the companion's body is not replayed, and
  its O evidence is the source plus the SQL witness.
- The existing **LM-P block replays companion bodies to the echo**, so every P walk of the companion already writes a
  pending journal note per viewport. Check this with Ian.

**Banker gates for O**: `ai-cost-observability`, `edge-observed-coverage`, `log-correlation`, `grafana-reader-reads`,
`slo-rollup`. Two caveats. `ai-cost-observability` passes with a WARN on its "callAI sites pair with cost log writes"
layer, so it does **not** refuse a function that writes no cost row; never cite it as "every call is logged".
`edge-observed-coverage` proves the error net only.

## 5. Banker additions (bank_lm_walk.py was NOT edited)

`bank_lm_walk.py` refuses an L/E/O row today ("sub-layer has no banker rule yet"). The proposed entries are:

```python
GATES.update({
  "L": ["waiting-is-spoken", "a-busy-button-says-working", "abort-timeout", "slow-hint-reads-only", "outage-copy-honesty"],
  "E": ["ai-eval-coverage", "ai-eval-regression", "companion-dim-gate", "fb4-grounding-eval", "ai-trust"],
  "O": ["ai-cost-observability", "edge-observed-coverage", "log-correlation", "grafana-reader-reads", "slo-rollup"]})
SUBNAME.update({"L": "Latency & waiting", "E": "Evals & quality gates", "O": "Observability"})
```

Refuse to bank:
- **L** when a viewport lacks `lat.slow` or `lat.never`.
- **E** when a viewport lacks `eval.control` and `eval.answerShown` is false (unproven).
- **O** when a viewport lacks `obs.sinks`.

**Postgres witnesses (read-only, per batch, between the walk's started and finished times):**

```sql
-- L / E / O: the stub held everything - no model call reached the server from the walk window
select count(*) from wh_traces where created_at between '<started>' and '<finished>' and trace_id not in (<O traceIds>);
-- E: the press was held, nothing landed
select count(*) from ai_reply_feedback where created_at >= '<started>';
-- E: what the evaluation of this surface's agent actually measured
select agent_id, count(*), count(*) filter (where passed), count(*) filter (where actual_answer like '[gateway error%')
  from ai_quality_log where agent_id in ('<agent(s) from E_COVERAGE>') group by 1;
-- O: the gateway's own trace of each replayed request, by the id the walk minted
select trace_id, route, status, hive_id, user_id is null as no_user, latency_ms, model_chain
  from wh_traces where trace_id in ('<step.obs.traceIds>');
-- O: the ledger for the reached functions
select fn, count(*), max(created_at) from ai_cost_log where fn in ('<fns>') group by fn;
```

**Receipt wording.** Name only what was tested. Fill the brackets from the step.

- **L:** "LOCAL, no model call. As \<cast\> (\<persona\>), \<target\> (\<how\>) was asked at 390 and 1280.
  - Slow answer (200 after 12 s): a working sign at \<progressAtMs\> ms ("\<firstSign\>"), announced: \<announced or
    'no'\>, held for the whole wait: \<signGoneAtMs null ? 'yes' : 'gone at Ns'\>, the person's words kept:
    \<typedKept\>, the answer shown at \<answerShownAtMs\> ms, a Stop: \<stopControl or 'none'\>.
  - Never answered: \<endedBy\> after \<saidAtMs\> ms, saying "\<said\>", words kept \<typedKept\>, page outage
    notice \<outageNotice or 'none'\>.

  Gates: … postgres: …". Do not write "the AI is fast": the timing is the stub's, not a model's.
- **E:** "LOCAL, no model call. The evaluation covering \<target\>: \<coverage by + grades\>; its runs: \<pg
  ai_quality_log line\>. Walked: after a stubbed answer, the "was this right?" control \<control.via / 'none
  appeared'\>; pressing "\<label\>" was a held write to ai_reply_feedback, rating \<rating\>, carrying the answer
  \<carriesAnswer\> and the question \<carriesQuestion\>; the person was told "\<ack\>"." Say "covered by \<file\>",
  never "quality is good".
- **O:** "LOCAL, no model call; the page's ask was stubbed in the browser and reached \<fns\>. From source, a
  successful call of each leaves: \<sinks: call / output\>. The \<agent\> request, replayed as the person to the
  gateway's local debug echo under trace \<minted\>, came back \<status\>, and wh_traces holds \<pg row\>. The hive's
  ai_cost_log, read as the person: \<ledger.byFn\>. Not provable locally: a real turn's ai_cost_log row, model,
  provider, tokens, and the failed-forward path." Never write "every AI call is logged".

## 6. Self-check (2026-10-07)

`scratchpad/leo_check.js` takes the three parts, splices them into a **copy** of the current `tools/lm_walk.body.js`
at the text anchors, and also wraps them in a dummy async harness with the walker's variables declared:

- Each anchor occurs exactly once.
- `node --check` passes on both the harness and the spliced walker.
- An acorn (7.4.1, ES2020) pass over the spliced walker finds 1,609 identifier references inside the block and none
  that the walker does not declare. This check ignores scope.

Not run against a browser.

## 7. Open questions and risks

1. **E headline, for Ian.** The nightly ai-eval-runner has produced 1,765 failures and zero measurements: every one is
   a gateway 401, caused by the service-role bearer. Possible fixes: send a real test user's JWT, or add a
   service-role path in the gateway. This needs Ian's decision, not a walk.
2. **LM-P hygiene.** P's echo replay of the companion writes a `voice_journal_entries` row each time (persist-first
   before the echo), plus global/route counters. O does not replay journal agents by default.
3. **L run time.** asset-hub and hive pass B take up to 162 s per viewport. If that is too long on this host, set
   `L_DEADLINE_MS` lower for those two pages. The walk will then report "still waiting at N s" instead of the true end.
4. **`L_DEADLINE_MS` is hand-read from source** and will go stale if a page's timeout changes. A page not listed
   defaults to 75 s.
5. **Load entries.** On shift-brain the auto-generate only runs when there is no fresh plan; otherwise the walk falls
   back to the companion, with a note. For a load-time pass, a page-read "Loading…" that appears at the same moment
   can stand in for the AI's own sign.
6. **Structured generators** (analytics, analytics-report, project-manager's wizard, alert-hub's `action_plan`) may
   not show the mark. That is recorded as a note for L, and becomes "unproven" for E when no control appears either.
7. **Things not verified in source:**
   - the exact failure sentences on assistant.html and analytics-report.html;
   - whether `renderActionBrief` shows the stub's `action_plan.summary` on alert-hub;
   - `#sb-verdict`'s live-region status. Its markup has none; a comment says an aria-live region sits "above".
