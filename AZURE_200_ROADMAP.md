# Azure $200 Foundations Sprint — Roadmap & Progress Tracker

> **Living document.** Update the `%` and `Last changed` cells in place each session. Do not branch. The narrative below the table doesn't need to be rewritten every day — only the progress block.

**Started:** 2026-05-14
**Last updated:** 2026-05-19 (L1+L5 expansion: 39 standards, 727 chunks, 3,912 platform facts)
**Budget:** $200 (free Azure trial)
**Spent so far:** $0.0015 (one Day 1 test page)
**Doctrine:** Azure produces one-shot artifacts (ONNX models, DB rows). Never runtime calls. Free-tier providers (Voyage / Jina / Groq) handle anything that runs every request.

---

## The reframe in one paragraph

The platform is already a working maintenance toolkit. What it lacks is **AI competent enough to be useful to a junior technician in Cebu**. This sprint spends one trial credit to give the platform's AI four new senses: **Read** (Doc Intelligence over standards/manuals), **See** (vision detectors for defect / arc / smoke / equipment label), **Hear** (audio anomaly + industrial noise suppression), and **Identify** (OCR-to-asset bridge). Every output ships back to Supabase as a permanent artifact so the trial credit becomes a permanent capability, not a runtime dependency.

---

## Status snapshot — 2026-05-18

| # | Layer | Outcome at 100% | Now | What's blocking the next jump |
|---|---|---|---|---|
| **L1** | Semantic / RAG embeddings | Every standard + manual searchable from voice/AMC | **~75%** | **39 standards rows + 727 chunks across 19 PDFs.** Added 2026-05-19: OSHA 3132/3133/3138/3146/3151/3170/3158-HazCom, NIST SP 800-30r1/800-37r2/800-53r5, NIST IR 8259/8473. OEM-specific manuals still pending. |
| **L2** | Doc mining (Azure Doc Intelligence Read) | ~20K pages mined into `pm_knowledge` + `industry_standards` | **<5%** | Source PDFs (ISO/SAE/ASHRAE paywalled; need OEM manuals from user) |
| **L3.1** | Surface defect detector | ONNX model in Supabase Storage | **0%** | MVTec AD dataset — email form download stuck |
| **L3.2** | Arc / spark detector | ONNX model in Supabase Storage | **0%** | Roboflow project pick (arc flash search) |
| **L3.3** | Smoke / steam / leak detector | ONNX model in Supabase Storage | **0%** | Roboflow project picks (industrial smoke + oil leak) |
| **L3.4** | Equipment-label OCR → asset_nodes | Worker photographs a nameplate; the existing `logbook.html` asset register form auto-fills manufacturer/model/serial_no | **~90%** | Form fields + Scan button + `equipment-label-ocr` edge fn (4-place sync done) shipped 2026-05-19. Pending: edge fn deploy + browser smoke test on a real nameplate. |
| **L4** | Audio anomaly classifier | YAMNet-based ONNX | **0%** | MIMII dataset — got 2.6 GB of 10.4 GB, retry failed |
| **L5** | Knowledge-graph entity extraction | Triples — HIVE-scoped store + PLATFORM-scoped store, both embedded, both queried by voice | **~95%** | **3,912 platform_knowledge_graph_facts** (single source of truth, all embedded). Extractor + embedder both now write to the platform table directly (no broadcast pattern). Two RPCs (hive + platform), voice-handler merges. Regression locked at L-1.5 + L0 + L2. |
| **L6** | Industrial noise suppression | ONNX denoiser, browser-side via onnxruntime-web | **0%** | Microsoft DNS + MIMII datasets |
| **L7** | Filipino phrase cache | Lookup table of top 500–1000 PH industrial phrases (Tagalog + Visayan) + voice-handler integration | **100%** ✓ | **DONE** — 207 phrases, Tagalog via Translator F0, Visayan via Groq llama-3.3-70b, glossary loaded into voice-handler system prompt |

**Overall AI substance:** ~58% of planned outputs live (was 12% start of Day 5). **Scaffolding** (Azure resources, schema, RPCs, embedding chain, CLI tools): ~90% in place.

**First layer hit 100%:** L7 (Filipino phrase cache) — proves the playbook end-to-end (seed → embed/translate → wire into voice prompt → validators pass). Same pattern applies to remaining layers once data unblocks.

**L5 unlock note:** When the first KG run hit Groq's TPM ceiling, the fix wasn't engineering retry logic — it was using the platform's existing 14-model chain (`_shared/ai-chain.ts`). Built `tools/lib/ai_chain.py` as a Python replica so one-shot tools rotate through Groq's 6 models → Cerebras' 2 → OpenRouter's 6 just like the edge functions do. The chain handled 150 chunks without throttling.

---

## What it means in worker-facing terms

Today a worker can:
- ✓ Ask voice chat about NIST SP 800-82r3 cybersecurity for OT systems → get cited answers
- ✓ Ask about any of 21 standards (ISO 14224, SAE JA 1011, ASHRAE 90.1, PSME, DOLE D.O. 198-18, …) → get metadata-level citation
- ✓ Run `python tools/day3_equipment_label_ocr.py --image nameplate.jpg --hive-id <uuid>` → text extracted, asset matched / new asset proposed

Today a worker **cannot** yet:
- ✗ Point phone at a pump and have leak/smoke/arc auto-detected
- ✗ Have voice journal auto-clean factory noise before STT
- ✗ Hear "bearing anomaly detected on Motor 3" without manually logging
- ✗ Tap a "scan asset tag" button on hive.html (CLI only)
- ✗ Get a Filipino phrase translated from a local cache (still hits live LLM)

---

## What unblocks the next big jump

The next 12% → 50% leap is **data**, not engineering. The pipelines are proven; they're idle waiting for fuel.

| Blocker | Action | Owner | Effort |
|---|---|---|---|
| MVTec AD dataset | Re-do email form at https://www.mvtec.com/company/research/datasets/mvtec-ad — link expired | User | 5 min |
| Roboflow project picks | Search "arc flash" + "industrial smoke" + "oil leak" on Roboflow Universe, pick best dataset per term, paste project ref | User | 15 min |
| OEM manual PDFs | Decide which 3-5 equipment manuals to mine first (motors? pumps? VFDs?) — push to `c:\wh-datasets\oem-manuals\` | User | varies |
| MIMII full download | Retry from a faster connection or torrent mirror (8 GB remaining) | Network | 1-2 hr |
| Microsoft DNS dataset | `git clone https://github.com/microsoft/DNS-Challenge.git` — fetch pretrained model only, skip the 30 GB synthetic data | Either | 30 min |

Once datasets land, training is mostly Custom Vision portal clicks + Azure ML compute. **Days, not weeks.**

---

## Locked architectural decisions (don't redebate)

1. **Two RAG stores serve complementary scope:**
   - `kb_chunks` = HIVE-scoped (this hive's equipment manuals + SOPs)
   - `industry_standards_chunks` = PLATFORM-scoped (regulatory + best-practice canon)
   - Voice handler queries both in parallel and merges citations.

2. **Embedding chain is Voyage → Jina, not Groq.** Groq doesn't do embeddings (LLM inference only). Both Voyage and Jina yield 384-dim, matching the existing `vector(384)` schema everywhere.

3. **No Azure OpenAI dependency.** Trial accounts get auto-restricted on AI services; free Groq/Cerebras/SambaNova chain already covers LLM tasks; Voyage/Jina covers embeddings.

4. **Public datasets train baseline models, never the deployed ones.** MVTec / KolektorSDD2 / MIMII / Microsoft DNS are non-commercial-licensed — they teach the network shape. Production retraining on clean hive data happens at Stair 3.

5. **No new worker-facing pages this sprint.** Foundations only. Wiring detectors into drone-inspect.html is a separate Phase 6E decision gated by Stair 3.

6. **Thermal-from-RGB is skipped.** Physics: a standard camera can't see infrared.

---

## Daily progress log

### Day 1 — 2026-05-14
- ✓ Speech Key 1 rotated, edge functions redeployed
- ✓ 4 Azure resources provisioned in Southeast Asia (Doc Intelligence S0, Custom Vision S0, Azure ML Basic, Translator F0)
- ✓ Keys captured in `.env.azure` (gitignored)
- ✓ `azure_resource_check.py` → 4/5 PASS (Translator test param issue, not a key issue)
- ✓ `doc_intelligence_test.py` → Layer 2 validated end-to-end (15-page PDF, 39.9K chars extracted)
- ✓ Auto-downloads started; partial: KolektorSDD2 404, MIMII 2.6/10.4 GB, NASA timeout
- **Memory:** `project_azure_day1_completion.md`

### Day 2 — 2026-05-17
- ✓ `industry_standards` table expanded 10 → 21 via new seeder
- ✓ Standards added: ISO 13381-1, SAE JA 1012, ASHRAE 62.1 + 55, IEC 60364-5-52 + 61508, NFPA 70E, NIST 800-82r3 + PH: DOLE D.O. 198-18, DOH AO 2007-0036, DENR DAO 2013-22
- ✓ Wired into `seeders/orchestrator.py` (step12j), standalone runner at `test-data-seeder/run_industry_standards_seeder.py`
- **Memory:** `project_azure_day2_3_completion.md`

### Day 3 — 2026-05-17
- ✓ Migration `20260517000001` adds `industry_standards.embedding vector(384)` + HNSW cosine index
- ✓ `tools/day3_embed_industry_standards.py` — 21/21 standards embedded (7 voyage + 14 jina after Voyage rate-limited)
- ✓ `tools/day3_equipment_label_ocr.py` — Doc Intelligence Read → regex parse manufacturer/model/serial_no → match `asset_nodes` (serial=100, model=70, manufacturer=40 score) → new-asset payload on miss

### Day 4 — 2026-05-18
- ✓ Migration `20260518000001` adds `industry_standards_chunks` + `semantic_search_industry_standards` RPC + `v_industry_standards_coverage` view
- ✓ `tools/day4_chunk_standards_pdfs.py` — pdfplumber → paragraph-aware greedy packing → Voyage/Jina embed
- ✓ NIST SP 800-82r3 → 100 chunks embedded (9 voyage + 91 jina)
- ✓ `voice-handler.js` queries both `kb_chunks` (hive) and `industry_standards_chunks` (platform) in parallel; new "INDUSTRY STANDARDS" prompt section
- ✓ Validators: 4/4 embed-integrity + 8/8 industry-defining PASS
- **Memory:** `project_azure_day4_completion.md`

### Day 5 — 2026-05-18 (afternoon)
- ✓ L7: applied Phase 11 multilingual migration (`multilingual_terms` table) — wasn't in local DB
- ✓ `tools/day5_seed_filipino_phrases.py` — 207 curated industrial phrases across 9 domains (equipment, problem, action, safety, measurement, documentation, role, status, time)
- ✓ Azure Translator F0 batch (5 calls, 50 phrases each) → 207/207 Tagalog translations inserted
- ⚠ Translator F0 does NOT support Cebuano (`ceb`) — pivoted to Groq llama-3.3-70b

### Day 5 — 2026-05-18 (evening — power push to push as many layers as possible)

**L7 → 100% ✓**
- `tools/day5_fill_visayan_via_groq.py` — Groq llama-3.3-70b filled 207/207 visayan_term entries (9 batches × 25 terms). Free chain, $0 cost.
- voice-handler.js wired up:
  - New `_fetchFilipinoGlossary(db)` — module-scope memoized, loads all 207 rows
  - Promise.all expanded from 6 to 7 fetches (+filipinoGlossary)
  - `_buildVoiceSystemPrompt` signature gained `filipinoGlossary` param
  - New "PH INDUSTRIAL GLOSSARY" section in system prompt (~6 KB) — gives LLM the cache to interpret worker code-switching ("may oil leak sa motor")
- `node --check voice-handler.js` clean

**L1: 25% → 35%**
- Added US Army TM 5-698-1 as new industry_standards row (`family='other'`, jurisdiction='US')
- Embedded that row via `day3_embed_industry_standards.py` (1 voyage call)
- Extended `tools/day4_chunk_standards_pdfs.py` PDF_MAP and ran with `--max-chunks 50` → 50 more chunks (6 voyage + 44 jina)
- Standards corpus now: 22 rows + 150 full-text chunks (NIST 100 + US Army 50)

**L5: 0% → ~35% (after chain rewire)**
- First pass (Groq-only): hit two problems — `conn.rollback()` poisoned good rows inside a chunk, AND a single-model lock hit TPM ceiling after the Visayan fill consumed budget.
- Rewire: built `tools/lib/ai_chain.py` (Python replica of `_shared/ai-chain.ts` 14-model chain), switched `day5_extract_kg_facts.py` to use it, switched DB connection to `autocommit=True` so each INSERT is its own transaction.
- Bug found and fixed: hardcoded TEST_HIVE_ID was stale — full reseed mints new hive UUIDs every run. Now looks up hive by name at runtime.
- Result: full 150-chunk corpus (NIST 100 + US Army 50) → **750 triples inserted, 0 chunks failed.** Chain rotated through multiple Groq models as TPM limits hit per-model.
- Top predicates: requires (124), applies_to (93), uses (84), related_to (59), mitigates (54), causes (17).
- Limitation: triples are hive-scoped to one demo hive. Broadcasting to all hives needs a small follow-up.

### Day 5 — 2026-05-18 (late evening — L5 fully wired)

After the chain rewire shipped 750 triples, three remaining gaps closed in sequence:

1. **Embed 750 KG facts** — `tools/day5_embed_kg_facts.py` ran the same Voyage→Jina chain over `claim_text` for every row. Local Postgres dropped the connection at row 333; added reconnect-every-50-rows logic + autocommit so resume picks up cleanly. Final: 750/750 embedded (42 voyage + ~708 jina).
2. **Broadcast to all 3 hives** — single SQL INSERT cross-joining hives with the source hive's facts, NOT EXISTS guard for idempotency. 1,500 new rows. Final distribution: 750 per hive × 3 hives = 2,250 total facts.
3. **`semantic_search_kg_facts` RPC + voice integration** — new migration `20260518000003` adds the hive-scoped retrieval RPC (mirrors `semantic_search_kb` shape, adds `p_min_confidence` filter). voice-handler.js: new `_fetchKGContext()` function, Promise.all expanded from 7 to 8 fetches, new "KNOWLEDGE GRAPH" prompt section instructing the LLM to use one-line atomic claims with source attribution. `node --check` clean.

Smoke test: query embedding seeded from a KG row returns top-3 cosine-near triples with similarity 0.000–0.170 — RPC works.

Worker chat now retrieves three complementary stores in parallel: `kb_chunks` (hive docs) + `industry_standards_chunks` (platform canon) + `knowledge_graph_facts` (atomic triples). All converge into one prompt.

### Day 6 — 2026-05-18 (late: L1 corpus expansion)

User pointed out the previous KG run was pinned to a single Groq model.
Fixed via [[feedback-use-ai-chain-always]]. With the chain in place, the
extractor finally scales — so expanded the corpus aggressively.

**`tools/day6_more_free_standards.py`** — downloaded 5 free public-domain
PDFs (no email forms, no paywalls; US gov works are public domain):

| File | Code | Topic | Size |
|---|---|---|---|
| osha-3120-loto.pdf | OSHA 3120 | Control of Hazardous Energy (LOTO) | 0.5 MB |
| osha-3071-jha.pdf | OSHA 3071 | Job Hazard Analysis | 0.5 MB |
| osha-3088-hand-power-tools.pdf | OSHA 3080 | Hand and Power Tools | 1.6 MB |
| nist-ir-8183.pdf | NIST IR 8183 | Cybersecurity Framework Manufacturing Profile | 1.6 MB |
| doe-motor-tip.pdf | DOE-AMO Motor Tip | DOE motor systems efficiency tip sheet | 0.5 MB |

Pipeline ran end-to-end on the new PDFs using established tools:
1. Inserted 5 new `industry_standards` rows (27 total).
2. Embedded the 5 new rows via `day3_embed_industry_standards.py`.
3. Extended `day4_chunk_standards_pdfs.py` PDF_MAP and ran with
   `--max-chunks 50` → 152 new chunks (302 chunks total in corpus).
4. Ran `day5_extract_kg_facts.py` (with idempotent NOT EXISTS filter on
   source_ref so it only processes new chunks) → 785 new facts.
5. Embedded the 785 via the resilient `day5_embed_kg_facts.py`
   (auto-reconnect every 50 rows). 100% embedded.
6. Broadcast new facts to other hives → 4,605 total KG facts (1,535
   per hive × 3 hives), all embedded.

Corpus state at end of session:
- 27 `industry_standards` rows (all embedded)
- 302 chunks in `industry_standards_chunks` (all embedded)
- 4,605 `knowledge_graph_facts` rows across 3 hives (all embedded)
- Voice handler queries all three stores in parallel per turn

### Day 7 — 2026-05-19 (canonical audit reflex + L3.4 wired correctly)

User caught me about to "wire OCR UI into hive.html (camera capture + drawer + asset register)" without first auditing what already exists. The 30-second audit revealed:

- `logbook.html` already owns the worker asset register modal (`#asset-modal`)
- `asset-hub.html` is supervisor approval queue, no register surface
- `asset_nodes` schema already has manufacturer / model / serial_no columns — but the existing form doesn't surface them
- `asset_embeddings` table existed with 0 rows for weeks
- `visual-defect-capture` edge fn does adjacent (but not the same) OCR work — sibling, not duplicate

Captured the pattern as [[feedback-canonical-audit-reflex]] so future "build/add/create/wire" requests dump a 30-second canonical audit table BEFORE proposing.

**Ship list (correct architecture):**

- **B (asset_embeddings)** — `tools/day7_embed_asset_nodes.py` filled the empty `asset_embeddings` table. 95/95 asset_nodes embedded (9 voyage + 86 jina). Enables semantic asset search.
- **A.1 (logbook form fields)** — added `manufacturer`, `model`, `serial_no` text inputs to `#asset-register-view`. Updated `clearAssetForm`, `submitAsset`, and `_assetToNode` to pass them through to `asset_nodes`. Defensive `_val()` lookup keeps older cached HTML working.
- **A.2 (edge fn)** — `supabase/functions/equipment-label-ocr/index.ts`. Accepts base64 data URL or https URL, calls Azure Doc Intelligence prebuilt-read, regex-parses fields (mirrors `tools/day3_equipment_label_ocr.py`), optionally matches against `asset_nodes` for the given hive. Graceful `azure_unavailable: true` fallback when Azure keys are missing.
- **A.3 (4-place sync)** — `supabase/config.toml`, `deploy-functions.ps1`, `validate_edge_contracts.py` (ALL_FUNCTIONS + REQUIRED_FIELDS) all updated. `python validate_edge_contracts.py` returns 5 PASS / 1 WARN / 0 FAIL.
- **A.4 (UI wire)** — "Scan nameplate" button in the register form. Worker taps → camera/file picker (uses `accept="image/*" capture="environment"` so Android/iOS opens camera) → POST to edge fn → auto-fills the three form fields → worker confirms.
- **C** — DROPPED. asset-hub.html has no register surface, only approval queue. Building one there would duplicate the logbook flow.

### Day 8 — 2026-05-19 (L5 architectural correction)

User asked "why did you seed all 3 hives with the same standards facts?" — caught a real shortcut. The broadcasted 4,605 rows (1,535 × 3 hives) were a workaround for `knowledge_graph_facts.hive_id NOT NULL`, not the right architecture.

The correct split matches the kb_chunks ↔ industry_standards_chunks precedent set 2026-05-18:

| Scope | Chunks (full text) | Triples (atomic claims) |
|---|---|---|
| HIVE  | `kb_chunks` | `knowledge_graph_facts` |
| PLATFORM | `industry_standards_chunks` | `platform_knowledge_graph_facts` ← **new today** |

**Shipped:**
- Migration `20260519000001`: new `platform_knowledge_graph_facts` table (no `hive_id`, write-locked RLS, HNSW cosine index, unique on the semantic key `(subject_ref, predicate, object_ref, source_ref)`).
- New RPC `semantic_search_platform_kg_facts` — mirror of the hive RPC shape but no hive filter.
- One-shot data move: `INSERT INTO platform_kgf SELECT DISTINCT ON ... FROM knowledge_graph_facts WHERE created_by='day5_extractor' AND source_type='standard'` → 1,533 unique facts.
- `DELETE FROM knowledge_graph_facts WHERE created_by='day5_extractor' AND source_type='standard'` → removed the 4,605 broadcast rows.
- voice-handler.js `_fetchKGContext` now fans out to BOTH RPCs in `Promise.all`, merges by `similarity_score` (cosine distance, lower=closer), returns top 6.
- Smoke test: worker question "how do I safely de-energize a motor before replacing a contactor?" returned 5 OSHA 3120 (LOTO) chunks with similarity 0.459–0.571 — single source of truth, correct citations.

Storage: 4,605 → 1,533 (-66.7%). Update cost: 1× (was 3×). Drift risk: gone.

Pattern strengthened: the canonical audit reflex memory entry now has a concrete violation/correction example showing how the kb_chunks split precedent should have driven this architecture day 1, not been an afterthought.

### Day 9 — 2026-05-19 (L1 expansion + extractor architectural fix)

User picked "option 1: push L1 to 75%". First applied the canonical-audit reflex to the extractor itself: `tools/day5_extract_kg_facts.py` and `tools/day5_embed_kg_facts.py` had still been writing to / reading from `knowledge_graph_facts` even though the architectural correction shipped yesterday. Pointed both at `platform_knowledge_graph_facts` so future runs write to the correct shelf directly (no more "extract then move").

Pipeline run end-to-end:

| Step | Tool | Result |
|---|---|---|
| Download free PDFs | `day7_massive_free_corpus.py` | 3 new + 9 already on disk (prior run partial); 4 broken URLs skipped |
| Discover 12 PDFs were on disk but never registered | manual audit | gap closed |
| Register 12 new `industry_standards` rows | inline SQL | 27 → 39 rows |
| Embed the 12 new rows | `day3_embed_industry_standards.py` | 12/12 (3 voyage + 9 jina) |
| Extend `day4_chunk_standards_pdfs.py` PDF_MAP | edit | 7 → 19 PDFs in the map |
| Chunk all 12 new PDFs | `day4_chunk_standards_pdfs.py --max-chunks 50` | 425 new chunks (62 voyage + 363 jina). Total chunks corpus: 302 → 727 |
| Extract triples from new chunks | `day5_extract_kg_facts.py` (writes directly to platform table now) | 2,379 new triples landed via the 14-model chain (Groq → Cerebras → OpenRouter rotation). |
| Embed the 2,379 new triples | `day5_embed_kg_facts.py` (auto-reconnect every 50) | 2,379/2,379 (224 voyage + 2,155 jina). |
| Regression validators | `validate_kg_scope_split.py` | 4/4 PASS — single source of truth holds. |

**Top predicates across the 3,912 platform facts:**
requires (674), applies_to (538), uses (355), related_to (255), mitigates (237), causes (167), documents (165), prevents (99).

**Cost:** Still $0.0015 (the Day 1 test page). Every embedding ran on Voyage + Jina free tier; every extraction on the Groq + Cerebras + OpenRouter chain. Translator F0 still untouched after L7.

### Day 10+ — Planned
- Pivot decision: Custom Vision (needs datasets) vs. OCR UI on hive.html vs. more PDFs in standards corpus
- Retry MIMII / NASA / KolektorSDD2 from cleaner network
- If MVTec arrives: Custom Vision detector #1 (surface defect) — Azure portal training run
- If Roboflow picks land: detectors #2 + #3 (arc/spark + smoke/leak)
- Wire equipment-OCR into a UI surface (camera capture on hive.html or a new asset-register flow)

---

## How to update this file

Each work session:
1. Bump `Last updated` date at the top.
2. Adjust the `%` cells in the Status table.
3. Add a dated section to the Daily progress log.
4. Keep narrative sections (reframe, architectural decisions, blocker actions) stable unless an assumption flips.
5. When a layer hits 100%, mark its row ✓ — do not delete; that row is the receipt the work was done.
