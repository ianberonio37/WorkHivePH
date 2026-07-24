---
name: skill-ai-engineer
type: skill
source: skill:ai-engineer
source_sha: 706e04f1d11b35ef
last_verified: 2026-07-13
supersedes: null
---
## skill · ai-engineer

Multi-agent orchestration, Claude API integration, Gemini Flash free tier, RAG pipelines, vector search, voice-to-text, per-hive AI context, prompt engineering, and cost optimization. Triggers on "age

**Sections:** AI Engineer Agent · Live grounding/fabrication eval — invoke for real, grade answer ⊆ DB truth, calibrate the truth set to the model's ACTUAL source (2026-07-01, FB4) · To grade a PROBABILISTIC behaviour deterministically, add a STRUCTURAL ECHO — don't prose-grep (2026-07-08, CL9 persona battery) · CITATION grounding (AI-6) = a fabricated-STANDARD detector, NOT a stripper (2026-07-09, eng-design G3) · Content-generation engine ("WorkHive Explains") — LLM writes prose, code owns the facts (2026-07-01) · Content = VALUE-FIRST (rationale + background BEFORE the product), not a feature tour (2026-07-01, Ian x3) · Content = MEMORY-FIRST frame + concrete-not-jargon + an animated AI companion (2026-07-02, Ian: "what a sloppy output") · This Platform's AI Context · Multi-Agent Architecture for WorkHive · The Core Pattern · Agent Roster — WorkHive Specific · Model Selection and Cost Strategy · The Model Ladder · Typical Agent Call Cost (WorkHive) · Scaling Roadmap · Prompt Caching — Free Tier vs. Paid · Model-Agnostic Architecture — Build Once, Swap Models · Agent Template (model-agnostic) · Model Client Adapter — Swap With One Config Change · Orchestrator Pattern · Sentinel Agent Pattern — May 2026 Hardening Loop · Edge Function `_shared` Contract — CORS via Request Context (2026-05-28) · Supabase Edge Function — Keep API Key Server-Side · Route user-facing AI calls THROUGH `ai-gateway`, and use `db.functions.invoke` (not raw fetch) (2026-06-07) · The gateway's `{ answer }` response contract DROPS structured payloads — only conversational surfaces fold cleanly (2026-06-07) · Routing a STRUCTURED tool through the gateway — the concrete Option-A recipe (Companion Unification Step 4, 2026-06-07) · Local runtime-verify of an AUTHED gateway path — mint a JWT, don't deploy (2026-06-07) · Within-conversation memory recall lives in the PROMPT, not just the plumbing — grounding + lane rules can SUPPRESS it (2026-06-12) · The INVERSE of a recall bug: a grounding fix can leave the model FABRICATING recall — add an explicit abstention clause (2026-06-12) · Multi-turn PII: `memory_block` + the summariser transcript need the FULL scrub, not just names (K2, 2026-07-12)

(Deep source: `skill:ai-engineer` — retrieve this TOC to know WHICH section to read.)
