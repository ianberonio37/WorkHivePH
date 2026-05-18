# Azure $200 Foundations Sprint — Roadmap & Progress Tracker

> **Living document.** Update the `%` and `Last changed` cells in place each session. Do not branch. The narrative below the table doesn't need to be rewritten every day — only the progress block.

**Started:** 2026-05-14
**Last updated:** 2026-05-18 (L7 Tagalog seed)
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
| **L1** | Semantic / RAG embeddings | Every standard + manual searchable from voice/AMC | **~25%** | More PDFs to chunk (NIST 800-82r3 ✓; rest paywalled or pending) |
| **L2** | Doc mining (Azure Doc Intelligence Read) | ~20K pages mined into `pm_knowledge` + `industry_standards` | **<5%** | Source PDFs (ISO/SAE/ASHRAE paywalled; need OEM manuals from user) |
| **L3.1** | Surface defect detector | ONNX model in Supabase Storage | **0%** | MVTec AD dataset — email form download stuck |
| **L3.2** | Arc / spark detector | ONNX model in Supabase Storage | **0%** | Roboflow project pick (arc flash search) |
| **L3.3** | Smoke / steam / leak detector | ONNX model in Supabase Storage | **0%** | Roboflow project picks (industrial smoke + oil leak) |
| **L3.4** | Equipment-label OCR → asset_nodes | UI on hive.html links photo → asset | **~60%** | UI wrapper — CLI tool works; needs camera capture + drawer on hive.html |
| **L4** | Audio anomaly classifier | YAMNet-based ONNX | **0%** | MIMII dataset — got 2.6 GB of 10.4 GB, retry failed |
| **L5** | Knowledge-graph entity extraction | Triples in `knowledge_graph_facts` from mined corpus | **0%** | Needs L2 to produce corpus first |
| **L6** | Industrial noise suppression | ONNX denoiser, browser-side via onnxruntime-web | **0%** | Microsoft DNS + MIMII datasets |
| **L7** | Filipino phrase cache | Lookup table of top 500–1000 PH industrial phrases (Tagalog + Visayan) | **~50%** | Visayan side still empty (Translator F0 has no `ceb`); fill via Groq llama-3.3-70b later |

**Overall AI substance:** ~18% of planned outputs live (was 12% before L7). **Scaffolding** (Azure resources, schema, RPCs, embedding chain, CLI tools): ~85% in place.

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
- ⚠ Translator F0 does NOT support Cebuano (`ceb`) — Visayan column stays empty. Will fill later via Groq llama-3.3-70b (free chain) or PH worker corrections via `terminology_gaps`.
- **Cost impact:** ~3000 chars used of 2,000,000/month free tier (0.15%)

### Day 6+ — Planned
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
