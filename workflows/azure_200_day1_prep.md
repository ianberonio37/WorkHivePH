# Azure $200 / 7-day Foundations Sprint — Day 1 Prep (v3 LOCKED)

**Objective.** Clear every blocker on Monday so Days 2-7 are pure execution. No critical path is gated on Azure OpenAI access — the embedding and entity-extraction work runs on the existing free Groq chain.

**Scope.** Foundations for: full semantic / RAG / Vector (via free chain) + drone-camera AI detectors (surface defect, arc/spark, smoke/steam/leak, equipment label) + audio anomaly classifier + industrial noise suppression denoiser + knowledge graph entity extraction. Thermal explicitly skipped (physics: standard RGB camera can't see infrared).

Budget locked at $200 across 6 layers. Full plan: see `MEMORY.md` → "Azure $200 Burn Plan v1" entry (file `project_azure_200_burn_plan.md`).

---

## Final 6-layer budget

| Layer | Allocation | Provider | Output |
|---|---|---|---|
| 1. Embeddings | **$0** | Groq nomic-embed-v1.5 (free chain) | Vectors in pgvector (384-dim) |
| 2. Doc mining | **$30** | Azure Doc Intelligence Read | ~20K pages → pm_knowledge + industry_standards |
| 3. Custom Vision (4 detectors) | **$45** | Azure Custom Vision S0 | 4 ONNX detector models in Supabase Storage |
| 4. Audio anomaly classifier | **$45** | Azure ML on MIMII | YAMNet-based ONNX audio classifier |
| 5. KG entity extraction | **$0** | Groq llama-3.3-70b (free chain) | Triples → knowledge_graph_facts |
| 6. Industrial noise suppression | **$25** | Azure ML fine-tune Microsoft DNS on MIMII | ONNX denoiser, runs in-browser |
| 7. Filipino phrase cache | **$0** | Azure Translator F0 (free forever) | Lookup table of top 500-1000 PH industrial phrases pre-translated |
| Buffer | $55 | | Quota delays, region, dataset issues, retries |

---

## Sequence — Day 1 (Monday)

### 1. Rotate Azure Speech Key 1 (09:00 — do this first)

Per `MEMORY.md` → "Persona Walkthrough Paused at Test #6": the key was exposed in a prior chat and is overdue for rotation. Do this BEFORE any new Azure work touches the same subscription.

```
Azure Portal → Speech Services resource → Keys and Endpoint →
"Regenerate Key 1" → copy new value
```

Then update the secret in Supabase:
```powershell
subst Z: "c:\Users\ILBeronio\Desktop\Industry 4.0\AI Maintenance Engineer\Self-learning Road-Map\Build & Sell with Claude Code\Website simple 1st"
Z:
npx supabase secrets set AZURE_SPEECH_KEY=<new_key_value>
.\deploy-functions.ps1
subst Z: /d
```

The deploy is mandatory after a `secrets set` — without it, edge functions keep the old key value silently (per `feedback_deploy_subst.md` + DevOps skill).

### 2. Confirm subscription region (09:30)

In Azure Portal → Subscriptions → confirm primary region is **Southeast Asia** (Singapore). All new resources (Doc Intelligence, Custom Vision, Azure ML) should provision there for latency parity with the Render free-tier Python API.

### 3. Provision Day-1 Azure resources (10:00 - 11:00)

Create these 4 resources in Southeast Asia region:

| Resource | Tier | Purpose |
|---|---|---|
| **Document Intelligence** | S0 (pay per use) | Layer 2 doc mining |
| **Custom Vision** | S0 | Layer 3 vision detectors (training + prediction) |
| **Azure ML Workspace** | Basic | Layer 4 audio classifier + Layer 6 noise suppression training |
| **Translator** | **F0** (FREE forever) | Layer 7 Filipino phrase cache. 2M chars/mo free, our use is ~50K chars. |

Capture each resource's endpoint URL + key into a local `.env.azure` file (DO NOT commit — add to `.gitignore` if not already covered):

```
AZURE_DOC_INTELLIGENCE_ENDPOINT=https://<name>.cognitiveservices.azure.com/
AZURE_DOC_INTELLIGENCE_KEY=...
AZURE_CUSTOM_VISION_ENDPOINT=https://<name>.cognitiveservices.azure.com/
AZURE_CUSTOM_VISION_TRAINING_KEY=...
AZURE_CUSTOM_VISION_PREDICTION_KEY=...
AZURE_ML_WORKSPACE_NAME=...
AZURE_ML_RESOURCE_GROUP=...
AZURE_ML_SUBSCRIPTION_ID=...
```

### 4. Validate Day-1 resources with the prep tools (11:00)

Two scripts already written for you:

```powershell
# A) Health-check all 4 Azure resources reachable + keys accepted:
python tools/azure_resource_check.py

# B) End-to-end Doc Intelligence pipeline test (1 page, ~$0.0015):
python tools/doc_intelligence_test.py
```

`azure_resource_check.py` reads `.env.azure` and pings Doc Intelligence + Custom Vision + Translator + Speech (post-rotation). Exits 0 when all pass.

`doc_intelligence_test.py` submits a public PDF, polls for the analysis result, prints extracted text. If it succeeds, Layer 2 is wired for Day 2 scale-up.

### 5. Start dataset downloads in background (11:30, runs overnight)

A download script is already written that handles the direct-download datasets and prints manual instructions for the form-gated ones.

```powershell
# Kick off direct downloads (KolektorSDD2, MIMII fan subset, NASA C-MAPSS):
python tools/download_datasets.py

# Or list what's available without downloading:
python tools/download_datasets.py --list

# Or download one specific dataset:
python tools/download_datasets.py --only mimii
```

Datasets save to `WH_DATASETS_DIR` from `.env.azure` (default `c:\wh-datasets`) — a folder OUTSIDE the project repo to avoid git bloat.

**Manual downloads (the script prints instructions):**
- **MVTec AD** — email registration form at https://www.mvtec.com/company/research/datasets/mvtec-ad
- **Microsoft DNS Challenge** — `git clone https://github.com/microsoft/DNS-Challenge.git`, use the pretrained baseline model
- **Roboflow Universe** — free account at https://universe.roboflow.com — search "arc flash", "industrial smoke", "oil leak"

### 6. Day-1 close-out (16:00)

- [ ] Speech Key 1 rotated, old key deactivated, edge functions redeployed
- [ ] Subscription confirmed in Southeast Asia
- [ ] 4 Azure resources provisioned (Doc Intelligence, Custom Vision, Azure ML, Translator F0)
- [ ] Keys + endpoints captured in `.env.azure` (NOT committed — `.gitignore` covers it)
- [ ] `python tools/azure_resource_check.py` returns 5/5 PASS
- [ ] `python tools/doc_intelligence_test.py` returns "Layer 2 pipeline VALIDATED"
- [ ] `python tools/download_datasets.py` started (will continue in background)

If 7 of 7 are checked, Day 1 succeeds and Days 2-7 execute against the locked plan.

---

## Day 2-7 outline

| Day | Primary work | Parallel background |
|---|---|---|
| **Day 2 Tue** | Doc Intelligence batch on PH standards + OEM manuals. Set up Azure ML workspace. Prep Custom Vision training data from MVTec | Continue dataset downloads |
| **Day 3 Wed** | Train Custom Vision detector 1 (surface defect, MVTec) + detector 2 (arc/spark, Roboflow source). Pre-trained Azure model for equipment label (no training). Start Groq nomic-embed batch on mined corpus | |
| **Day 4 Thu** | Train detector 3 (smoke/steam/leak). Start Azure ML training of YAMNet on MIMII + start Microsoft DNS fine-tune on MIMII industrial noise (share dataset pipeline) | Doc mining jobs completing |
| **Day 5 Fri** | Export Custom Vision detectors to ONNX, upload to Supabase Storage. Audio classifier ONNX export. Noise suppression ONNX export | |
| **Day 6 Sat** | Groq llama-3.3-70b on mined corpus → knowledge_graph_facts entity triples. Skeleton edge fn that orchestrates pipeline (does NOT wire to production page) | Validator runs |
| **Day 7 Sun** | Run all 149 validators. Document artifact catalog in memory. Update Phase 6 status (6A partial, 6F seeded, 6E foundations laid, voice noise suppression ready) | |

---

## Standing notes for every day this sprint

- **subst Z: before any CLI work** — project folder has `&` which breaks PowerShell.
- **Never `await` audit log inserts** — fire-and-forget per architect skill.
- **Every new edge function = 4-place sync** (config.toml + deploy-functions.ps1 + validate_edge_contracts.py ALL_FUNCTIONS + REQUIRED_FIELDS in same commit).
- **`npx supabase secrets set` requires immediate redeploy** — otherwise the function keeps using the old secret silently.
- **No new worker-facing page** this sprint. Foundations only. Wiring to a drone-inspect.html is a separate Phase 6E decision.

---

## On Day 7, before declaring the sprint complete

Per `feedback_hardening_loop.md`:
1. Coverage audit — every validator green
2. Seeder fill — test data for new tables (pgvector content, knowledge_graph_facts)
3. Flow enhancement — confirm RAG retrieval works end-to-end via Groq embeddings
4. Full gate — `python run_platform_checks.py` returns 0 FAIL
5. Visual spot-check — none expected this sprint (no new UI surface)
6. Validator decision — write a new gate (e.g., `validate_artifact_catalog.py`) if patterns emerged

---

## Fallback: if Azure OpenAI ever becomes useful later

The plan deliberately uses zero Azure OpenAI because:
1. Free-trial accounts sometimes get auto-restricted on AI services
2. The Groq free chain already provides equivalent embeddings (nomic-embed-v1.5, 384-dim, matches existing pgvector schema) and entity extraction (llama-3.3-70b)
3. Azure OpenAI is a runtime dependency on credit — doctrine violation

If post-sprint the platform needs higher-quality embeddings (e.g., text-embedding-3-large at 3072-dim for richer semantic search), that becomes a Founders Hub tier discussion, not a $200 trial decision.

---

End of Day-1 prep. Plan locks at v3; deviations require a memory update.
