# LM-V instrument: Voice & vision (94 rows, LM416-LM509)

**The lens:** "I spoke and the entry landed; the photo became an entry."
**The instrument:** local stubs only, no model call. `tools/lm_walk_v_block.js` (three parts spliced into
`tools/lm_walk.body.js`) plus the fixtures in `tools/fixtures/lm_v/`. Everything below was read from the page and
edge-function sources on 2026-10-07; nothing here was walked in a browser yet.

## Splice points (anchors in `tools/lm_walk.body.js`)

| Part | What | Insert |
|---|---|---|
| A | top level: stub payloads (`vMk`, `vStub`), page flows (`V_PAGE_FLOWS`, `V_COMPANION_KIND`), regexes, the provenance map (`V_PROV`), the page-side init script (`V_INIT`), fixture loading (`V_FIX`) | **after** `    scriptError: /\b(TypeError\|ReferenceError\|SyntaxError)\b\|is not a function\|Cannot read propert/g };` (end of `BADRE`) |
| B | per viewport: `vState`; `ctx.addInitScript(V_INIT)`; V routes for `rest/v1` (hold every write), `storage/v1/object` (hold uploads) and `functions/v1` (V stubs) | **before** `    ctx.on('request', (r) => { try { const h = r.headers(); if (!apikey && h.apikey ...` |
| C | the V reading `if (P.sublayer === 'V') { ... }` → `step.voice` | **before** `      step.captured = captured.slice(0, 12);` |

Each anchor occurs exactly once (checked). B's routes register after the walker's, so Playwright runs them first;
anything they do not own goes on with `route.fallback()`, so the walker's side-effect block (send/push/notify/...) and
its 503 stub still apply. B also sets `blockWrites = true` for V, as A does.

Optional, not in the block: the walker's generic ask (line ~314) still runs for V and asks the injection question.
It is harmless (my routes are inactive then, the walker answers 503), but costs ~5-10 s per viewport. To skip it:
`step.asked = P.sublayer === 'V' ? 'skipped (LM-V walks its own flows)' : (askSurface ? ... : false);`

## What the instrument does

- **Microphone.** `navigator.mediaDevices.getUserMedia` returns a synthetic `MediaStream`: an `AudioContext`
  sawtooth oscillator into `createMediaStreamDestination()`, 1.8 s of "voice" then silence. `resume()` is raced
  against 300 ms so autoplay policy can never hang the page's mic call. `enumerateDevices` and
  `permissions.query({name:'microphone'})` answer as a granted mic.
- **Recorder.** `MediaRecorder` is subclassed to count real chunks. If the synthetic stream gave none (an
  `AudioContext` held by autoplay policy after a scripted click), one placeholder chunk is dispatched before the
  page's own `onstop`, so the page's upload path runs. The receipt says which happened (`recorder: "N real chunk(s)"`
  or `"no real audio: one placeholder chunk handed to the page"`). Transcription is stubbed either way.
- **Web Speech API.** `SpeechRecognition`/`webkitSpeechRecognition` are a scripted recogniser that "hears"
  `window.__lmVTranscript` (set before each press): start → result (1.6 s) → end; `stop()` delivers; `abort()`
  gives `error: 'aborted'`. With `srMode: 'absent'` the API is removed (the iOS / Firefox path).
- **Stubs.** Each voice/vision function answers 200 with the shape its `index.ts` returns (below). The failure pass
  answers the flow's model function 503 with that function's own exhausted-chain sentence.
- **Holds.** Every table write, write-shaped RPC and storage upload is held (201/200, rows echoed back with an id
  when the page asked for representation, one object for `.single()`), recorded in `heldBodies` with
  `phase: 'v-<flow>:<load|capture|save|fail>'`, `carries` (the body contains text only the AI's draft has),
  `prov` (`marked` / `UNMARKED` / `none-defined` / `unknown`), `approver`, and a 300-char excerpt.
- **What the page says.** A `MutationObserver` keeps every short status-like text the page paints, with its time
  (toasts live ~4 s; readings come later). `speechSynthesis.speak` is recorded. Page errors are recorded.
- **Hygiene.** Each pass starts from `page.goto` on the page; logbook's per-person local draft
  (`wh_logbook_draft_*`) is cleared first, as a person starting a new entry would find it.

## Per page

Machine `m` = the hive the page opened (`P.groundByHive[st.hive].subject`), or `Own unit` for a solo owner
(the machine `tools/seed_solo_personas.py` writes).

### logbook.html (LM422 439 462 479 496 507) - three own flows + companion

| Flow | Entry point (verified in source) | Fires | Stub (from index.ts) | Person completes | Save control | Saved write should carry |
|---|---|---|---|---|---|---|
| Speak to fill | `#voice-fill-btn` → `startSmartVoice()` (Web Speech API, not MediaRecorder) | `voice-logbook-entry` `{transcript, hive_id, worker_name}` | `{ok:true, entry:{machine:m, problem, root_cause:'Wear', action, maintenance_type:'Inspection', status:'Open', downtime_hours:0, loto_detected:false, parts_mentioned:['drive belt'], ...}}` | discipline (`#f-category`, voice never sets it) | `#step-panel-1 .btn-next` → `#step-panel-2 .btn-next` → `#save-entry-btn` | `POST logbook` carries the draft; **the logbook table has no authorship column** (31 columns, none source/ai_*) → `none-defined` (note; a problem only with `V_PROV_STRICT`) |
| Photo defect capture | `#vdc-capture-btn` → file chooser on `#vdc-file-input` (`capture="environment"`), then `#vdc-analyze-btn` | `visual-defect-capture` `{hive_id, image_data_url, voice_note, worker_name}` | `{draft:{failure_mode, category:'mechanical', severity:'medium', root_cause:'Wear', action, problem, knowledge, asset_tag_extracted:null, confidence:0.82, narration}, matched_asset:null, fault_knowledge_id:null, remaining}` | machine via `#asset-picker-btn` → search m → first `#asset-picker-list button[data-asset-id]`; type `Inspection` | same wizard | same as above |
| Scan nameplate | `#open-asset-modal-btn` → `#asset-tab-register` → `#a-scan-btn` → file chooser on `#a-scan-input` | `equipment-label-ocr` `{image_data_url, hive_id}` | `{parsed:{manufacturer:'WEG', model:'W22 IE3 132M-4', serial_no:'1028475531', rated_power:'7.5 kW', voltage:'400 V'}, matched_asset:null, ocr_chars}` | `#a-asset-id`, `#a-name` | `#asset-submit-btn` | `upsert asset_nodes` carries the serial/model; no authorship column → `none-defined` |
| Companion voice | `#wh-ai-trigger` → `#wh-ai-mic` → overlay → `#wh-voice-stop` | `voice-transcribe` (multipart) then `ai-gateway` agent `voice-action` | see Companion | - | `#wh-voice-confirm` | (no write: the `logbook.create` handler only pre-fills the form) |

After a logbook save the page calls `embed-entry` (`{type:'fault', entry:{problem, action, ...}}`), which upserts
`fault_knowledge` **without `source`**; `fault_knowledge.source` defaults to `'manual'` (all 24,923 rows today are
manual). The block records that body; when it carries the AI's draft with no mark, that is a **problem**, because
`fault_knowledge` is where the platform does define the mark (`CHECK source in manual|ai_visual_capture|cmms_import`,
`(source ~~ 'ai\_%') = (ai_model IS NOT NULL)`).

Failure pass: the person first picks the machine with the picker; the whole wizard snapshot
(`#f-machine #f-problem #f-action #f-maint-type #f-category #f-root-cause #f-knowledge`) must be unchanged, and the
page must say so. The page's own words: `The AI fill did not run. Your fields are unchanged; fill them by hand or try
again.` / `The photo was not analysed. Your entry is unchanged; ...` / `OCR unavailable right now. Type fields manually.`

Server side, unobservable under the stub: `visual-defect-capture` itself inserts a `fault_knowledge` row
(`source='ai_visual_capture'`, `ai_model='visual-defect-v1'`, `logbook_id=null`) at ANALYZE time when
`confidence >= 0.4`, i.e. before the person saves - by design, and marked. The postgres witness should show 0 such rows
in the walk window (the stub never ran the function).

### report-sender.html (LM428 445 454 468 485 502 508) - own mic + companion

| | |
|---|---|
| Entry point | `#mic-btn` (label `#mic-label`). Chromium has the Web Speech API → **Path A** (desktop-1280). The phone context removes the API (`srMode:'absent'`) → **Path B**: `getUserMedia` + `MediaRecorder` → `voice-transcribe` (multipart `audio`), stopped by the page's own 2-s silence detector or a second tap at 6 s |
| Fires | `voice-report-intent` `{transcript, hive_id}` (both paths); `voice-transcribe` on Path B only |
| Stub | `voice-report-intent`: flat `{report_types:['failure_digest','shift_handover'], recipient_hint:null, period_days:7, machine_filter:m, urgency:'normal', notes}`; `voice-transcribe`: `{text, lang:'en', avg_logprob:-0.18, low_confidence:false}` |
| Reached | `.chip[data-id]` selected for both report types; `#voice-ctx` shown with `#voice-ctx-text` naming m |
| Save | none. The voice context feeds **Send** (an outward email through `send-report-email`/`scheduled-agents`); the walk never presses it |
| Failure | the person picks `.chip[data-id="predictive"]` first. **Expected finding:** `parseVoiceIntent` catches the error and silently falls back to `{report_types:[], notes: transcript}` - nothing tells the person their request was not understood |

### resume.html (LM429 446 469 486 503) - own photo + companion

| | |
|---|---|
| Entry point | `#btn-photo` → file chooser on `#file-photo` (`capture="environment"`, `multiple`) |
| Fires | `resume-extract` `{kind:'image', payload:<data URL>, source:'photo', hive_id, worker_name, auth_uid}` |
| Stub | flat `{fields:{basics:{label, summary, location}, work:[{name:'Northline Packaging Corp.', position:'Maintenance Technician', ...}], education, skills, certificates, projects:[], awards:[]}, remaining}` (what `resume_page_1.png` says) |
| Reached | `#review-sheet` opens; `#review-body` lists the job |
| Save | `#review-confirm` ("Add selected") then `#btn-save` → `saveCloud()` → `resume_documents` insert/update (and `resume_versions` snapshots) |
| Mark | every item read from a file carries `_source: 'Uploaded: <file>'` (basics: `_src`) - the page's own per-item mark → `marked` |
| Failure | the person typed `[data-basics="label"]` first; it must survive. `callResumeExtract` toasts the function's own `error` text (the stub's exhausted-chain sentence), then `handleFiles` toasts `Could not read those files. Try clearer photos or PDFs.` |

### Every other V page - companion only

achievements (LM432 449 455 472 489 506 509), alert-hub (LM416 433 450 456 473 490), analytics-report (LM417 434 451
457 474 491), analytics (LM418 435 452 458 475 492), asset-hub (LM419 436 459 476 493), assistant (LM420 437 460 477
494), hive (LM421 438 453 461 478 495), marketplace (LM423 440 463 480 497), ph-intelligence (LM424 441 464 481 498),
pm-scheduler (LM425 442 465 482 499), project-manager (LM426 443 466 483 500), project-report (LM427 444 467 484 501),
shift-brain (LM430 447 470 487 504), skillmatrix (LM431 448 471 488 505).

None of these pages has its own mic or vision input (marketplace's `#post-image-file` is a listing photo with no AI;
`svc-pay-img` is a payment proof - out of lens and blocked as `payment`). Their voice is the companion's.

## Companion voice (all 17 pages)

`companion-launcher.js` puts `#wh-ai-mic` in the panel opened by `#wh-ai-trigger`; it calls `WHVoice.open()`
(`voice-handler.js`, lazy-loaded by `nav-hub.js`): `getUserMedia` → `MediaRecorder` → `#wh-voice-stop` →
`voice-transcribe` (multipart `audio`, `language`, `hive_id`) → `ai-gateway` `{agent:'voice-action', message, hive_id,
context}`. The gateway's structured passthrough returns `{ok:true, data:{answer, agent, route_result:{transcript,
intents:[{kind, confidence, params}], mentioned_assets, narration, remaining}}}`; the stub gives no
`asset_resolution` (it does not invent an asset id).

- **Handler pages** (`WHVoice.register`): logbook `logbook.create`, asset-hub `asset.lookup`, pm-scheduler
  `pm.complete`. The intent card + `#wh-voice-confirm` should appear; the walk presses Confirm.
  **Expected finding:** `_confirm` runs `_preflightAction`, which refuses EVERY intent while
  `localStorage.wh_voice_execute_authorised !== '1'` ("Voice actions are locked on this device. Nothing was saved.").
  Nothing on the platform sets that key: `_setVoiceExecuteAuth` is only exported on `window.WHVoice` for tests
  (grep of every `.html`/`.js`), and the prompt's "turn it on in Settings" names a setting that does not exist. The
  lock also refuses `asset.lookup`, a read. The walk does not set the key - a person cannot.
- **Other pages** take the conversational path (`_converseInline` → `ai-gateway` agent `voice-journal` → reply in
  `#wh-voice-intents .wh-voice-bubble-text`); `agentic-rag-loop`, `voice-semantic-rag` and other non-lens functions
  answer 503 so no live model runs. Memory writes (`rpc/store_memory_turn`, `rpc/update_dialog_state`,
  `voice_journal_entries`, `conversation_analytics`, ...) are held and listed as memory, not judged as the entry.
- **Failure pass:** `ai-gateway` answers 503 after transcription succeeded; the overlay must say so
  (`Could not process voice command.`) and keep showing what it heard (`#wh-voice-transcript`). The raw
  supabase-js placeholder it also prints ("Edge Function returned a non-2xx status code") is recorded as a note.
- **Solo owner:** `Voice needs a hive. Join or create one first.` (and logbook's photo flow: `Join a hive to analyze
  defects with AI.`) are recorded as designed refusals (notes), not problems.

TTS: `wh-tts.js` `speakPersona` goes Piper → Edge → browser speech, never `tts-speak` (only `voice-journal.html`,
not a V page, calls it), and TTS is OFF by default (`localStorage` key must be `'on'`). `tts-speak` is stubbed
(`{url: <silent wav data URL>}`) for completeness; browser speech is recorded in `spoken`.

## Verdicts the block writes (all with the viewport and flow label)

Problems: the speech/photo never reached its function; the draft did not reach a field (`missing`); the page did not
show what it heard/read; the spoken request did not select the reports; the companion's handler intent was not
offered for confirmation / a question got no reply; **the AI's draft was written before the person saved**; the save
wrote nothing carrying the draft; the save wrote a table whose mark the platform defines without it (`UNMARKED`);
the embed-entry follow-on carried the draft unmarked; the companion Confirm was refused by the lock; the failure was
never reached; on failure the page said nothing a person can act on; on failure what the person entered changed.
Notes: not offered to this person; designed refusals; `none-defined` tables (unless `V_PROV_STRICT`); writes held
before the save that do not carry the draft; raw error text beside an actionable one; placeholder recorder chunk.

`step.voice = { machine, mic, speech, flows: [{ flow, label, offered, via, heard, mic, recorder, speech, image,
reached, filled, missing, text, chips, confirm, reply, refused, beforeSave, memory, save, saved:[{w, carries, prov,
approver}], embed, result, afterSave, announced, spoken, errors, fail:{failed, said, raw, kept, typed, writes} }] }`.

## Banker (bank_lm_walk.py) - suggested additions, not made

```python
GATES["V"] = ["ai_write_provenance", "visual-defect", "visual_defect_confidence", "asr_confidence_gate",
              "voice-refuses-ambiguous-asset", "voice_router_oracle", "capture-contracts"]
SUBNAME["V"] = "Voice & vision"
```

| Gate id | Script | Why it is V's |
|---|---|---|
| `ai_write_provenance` | tools/validate_ai_write_provenance.py | AI6: AI writes into human-read domain tables declare machine authorship |
| `visual-defect` | validate_visual_defect.py | visual-defect-capture's contract (multimodal call, caps, draft shape) |
| `visual_defect_confidence` | tools/validate_visual_defect_confidence.py | the draft carries a confidence |
| `asr_confidence_gate` | tools/validate_asr_confidence_gate.py | a mis-heard transcript is not sent on as if heard |
| `voice-refuses-ambiguous-asset` | tools/validate_voice_refuses_ambiguous_asset.py | a spoken write never lands on a coin-flip asset |
| `voice_router_oracle` | validate_voice_router_oracle.py | the router's deterministic kind allowlist / slot rules |
| `capture-contracts` | validate_capture_contracts.py | the logbook_add_entry_v1 contract the saved entry passes |

Also relevant, if a broader set is wanted: `voice-routing-unification`, `journal-transcript-is-raw`,
`ai-render-provenance`, `photo-survives-queue`, `the-photo-cannot-orphan-the-entry`.

Postgres witness (read-only, per batch window): rows created in `logbook`, `asset_nodes`, `resume_documents`,
`fault_knowledge` (and `fault_knowledge where source='ai_visual_capture'`) = 0 - every write the walk's save presses
made was held; and the static fact `select count(*) from fault_knowledge group by source`.

A V branch for the banker, in the style of A (refuse to bank a viewport with no `voice` reading, or where no flow
reached its function):

```python
if sub == "V":
    vs = [(s["viewport"], s.get("voice") or {}) for s in vps]
    if not all(v.get("flows") for _, v in vs):
        print(f"{rid}: NOT banked - a viewport has no voice reading"); return 1
    def _f(f):
        if not f.get("offered"):
            return f"{f['label']}: not offered ({f.get('why')})"
        save = (" > ".join(f.get("save") or []) or "no save control")
        wrote = "; ".join(f"{w['w']} (draft {'yes' if w['carries'] else 'no'}, mark {w['prov']})" for w in (f.get("saved") or [])) or "nothing"
        fl = f.get("fail") or {}
        return (f"{f['label']}: heard/read \"{(f.get('heard') or f.get('image') or '')[:80]}\" -> {f.get('filled') or f.get('text') or '-'} "
                f"filled; before save: {', '.join(f.get('beforeSave') or []) or 'nothing written'}; {save} wrote {wrote}"
                f"{'; embed ' + ','.join(f['embed']) if f.get('embed') else ''}; on failure ({', '.join(fl.get('failed') or []) or 'not reached'}) "
                f"it said \"{'; '.join(fl.get('said') or []) or 'nothing'}\" and {fl.get('kept') or '-'}")
    witness = (f"LOCAL, no model call. As {P.get('castName')} ({P.get('persona')}) the page's own mic (a synthetic "
               f"MediaStream / a scripted SpeechRecognition) and photo input (tools/fixtures/lm_v) were used; every "
               f"voice and vision function answered with a stub shaped like its index.ts, then 503 for the failure pass; "
               f"every write was held: " + " | ".join(f"{vp}: " + " / ".join(_f(f) for f in v["flows"]) for vp, v in vs)
               + f". AI gates: {a.gates_ok}. postgres-mcp: {a.pg}")
```

## Receipt / witness wording (names only what is tested)

> LOCAL, no model call. As {cast} ({persona}) at phone-390 and desktop-1280, {page}'s own {Speak to fill /
> Photo defect capture / Scan nameplate / report mic / resume photo / companion mic} was used with a synthetic
> microphone (or a scripted speech recogniser) and a fixture photo; every voice and vision function answered with a
> stub shaped like its own response. What it heard reached {N/N} fields; nothing carrying the AI's draft was written
> before {save control}; the save wrote {table} ({mark}). When {function} failed (503) the page said "{words}" and
> {kept}. AI gates: {...}. postgres-mcp: {...}.

Do not write "the AI understood", "transcribed correctly" or "recognised the defect": no model ran. The receipt
proves the page's handling of a realistic answer, the write discipline around it, and the failure path.

## Self-check (2026-10-07)

- `node --check` on a harness with the walker's names and nesting wrapping parts A/B/C: OK.
- The three parts spliced into a scratchpad COPY of `tools/lm_walk.body.js` at the anchors above (each found once):
  `node --check` OK, and `eval` the way `tools/lm_walk.js` loads it: OK. The real walker was not edited.
- Parts A+B run against fakes (no browser, no network): 35/35 - every stub's shape, the 503 failure answer, the
  quiet functions, embed-entry recording, side-effect fall-through, the holds and their echo, the provenance
  verdicts (`none-defined`, `marked`, `UNMARKED`), the read-RPC pass-through, the storage hold, and the regexes on the
  pages' own sentences.

## Risks and open questions

1. **`none-defined` (logbook, asset_nodes):** the brief says "where the platform defines it". The logbook row has no
   column to mark a voice/photo-drafted entry, so it saves as the person's own words. Recorded as a note;
   `V_PROV_STRICT = true` makes it a problem (LM-A judged any approval write without a mark as a problem). Decide.
2. **The voice-execute lock** will make every logbook / asset-hub / pm-scheduler companion row carry a problem
   until there is a person-reachable way to unlock it (or the lock stops refusing pre-fill and read intents).
3. **Autoplay:** the Playwright MCP launches Chromium with no `--autoplay-policy` / fake-media flags. A pointer press
   gives user activation, so the synthetic stream should run; after a scripted click it may not, and the recorder
   then hands the page one placeholder chunk (recorded per flow and noted once per viewport).
4. **Selectors not exercised live:** all come from source. Most likely to need a tweak on the first walk:
   `#review-sheet` visibility (a `.sheet-overlay`), `#voice-ctx` (display flex), the companion panel opening on
   phone, and whether "Register Asset" is offered to workers (if not, that flow is a note).
5. **Runtime:** logbook walks 4 flows x 2 passes x 2 viewports (~6-8 min); companion-only pages ~1-1.5 min.
6. **Echoed rows:** held writes are answered with the posted rows plus a fake uuid so the page's success path runs
   (A answered `[]`). A later `select ... eq('id', fake)` returns nothing; resume's `saveCloud` handles that.
7. **`m` for a hive whose most-logged machine is not an asset tag:** the picker search then finds nothing and the
   person takes the first asset (recorded as `first asset: ...`).
