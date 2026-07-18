# Native / Sovereign AI Companion — Roadmap (refined 2026-07-11, voice+audio production stream added 2026-07-12)

**Status:** DRAFTED + REFINED (Ian: "refine my thoughts, no build yet"). Awaiting a build-window.
**Premise (Ian):** build our own voice / transcriber / embedder so the platform veers off external-provider
dependency; in production a plant can run inference on their own infra/expense, downloading the Companion
voice locally and using their own internet for embedding.
**★ 2026-07-12 refinement (Ian, 2 msgs):** *"make our own VOICE and AUDIO for production users — the SAME as
our embedder for production users — so we don't rely on external providers."* → the embedder (bge-local) is now
the proven precedent (hands-free, per-user, self-healing); voice (TTS) + audio (ASR) must match it. See §6
(the production voice+audio stream). Surfaced live from the current AI-Companion arc's F-axis: the Voice-Journal
capture round-trip can't be driven headlessly because the voice pipeline still leans on the browser voice +
cloud ASR — §6 is that gap's production-grade close.

---

## 0. The reframe — the headline is DATA SOVEREIGNTY, not "fewer dependencies"

Resilience + cost are real (proven live 2026-07-11: the Companion's LLM call returned
`{"message":"name resolution failed"}` → 503 — a single external provider being unreachable killed the
answer). But the decisive value for the target market (industrial plants) is: **"your maintenance data never
leaves your plant."** Many enterprise/compliance buyers legally cannot send equipment logs / fault notes /
worker data to an external LLM. A local-inference option is the moat that wins accounts free-tier never can.
**Lead with sovereignty; resilience + cost are the supporting acts.**

## 1. Grounded stack inventory (verified in-tree 2026-07-11)

The "indigenous-first, cloud-fallback" pattern is ALREADY the house style — extend it, don't invent it.

| Capability | Self-host difficulty | Status | File / hook |
|---|---|---|---|
| **Embeddings** (bge) | Easy (~100–400MB, CPU) | ✅ ours | `embedding-chain.ts` (`BGE_EMBED_URL` → cloud), `tools/embed_server.py` |
| **ASR** (whisper) | Easy (~480MB, CPU) | ✅ ours — biggest SPOF closed | `audio-chain.ts` (`WH_ASR_URL` → Groq), `tools/asr_server.py` (faster-whisper) |
| **TTS** (voice) | Easy (~60MB, CPU) | ⚠️ browser only | `wh-tts.js` / `voice-handler.js` (`speechSynthesis`) — **the "download the voice" gap** |
| **LLM** | **Hard** (GPU or slow CPU) | ❌ external | `ai-chain.ts` (19-provider free-tier fallback) — **BYO-endpoint, don't bundle** |

## 2. The two real gaps + their concrete builds

### (a) "Download the voice" → local neural TTS (Piper)
Browser `speechSynthesis` is the OS's voice: robotic, device-variant, **no consistent Hezekiah/Zaniah
identity**. Fix = **Piper** (Apache-licensed, ~60MB/voice, CPU-fast, runs as a tiny server OR WASM
in-browser). `wh-tts.js.speak()`: try local Piper (`WH_TTS_URL` / WASM) first → fall back to browser TTS.
Same shape as `audio-chain`. Payoff: a branded, consistent, offline Companion voice downloaded once.

### (b) The LLM — a `WH_LLM_URL` local-first slot, NOT a bundled model
A useful 7B+ model needs a GPU or is painfully slow on CPU; bundling one by default is a mistake. Mirror
`WH_ASR_URL` exactly: add a **local-first provider slot to `ai-chain.ts`** (`WH_LLM_URL`, OpenAI-compatible
`/chat/completions`, e.g. Ollama / llama.cpp) tried first when set, falling through to the free-tier chain
when unset/down. The LLM chain is the ONLY stack member missing the local slot. Additive, zero prod risk.

## 3. One codebase, three deployment tiers (env flags, no forks)

- **Tier 0 — Zero-setup (default):** browser TTS + external free-tier LLM + cloud ASR. Solo/small, no install.
- **Tier 1 — Plant-hosted (BYO-compute):** `asr_server` + `embed_server` + Piper on a plant box → voice &
  embeddings never leave the plant; LLM still external or user-provided. *(Ian's "their infra, their expense".)*
- **Tier 2 — Fully sovereign:** + `WH_LLM_URL` → local Ollama. Zero external calls. Compliance-locked accounts.

## 4. Honest caveats (so it isn't oversold)

- Local LLM quality/latency on CPU is the true limiter — Tier 2 wants real hardware.
- Self-hosted models drift → the **fallback-to-cloud hedge (already built) is the correct default**, not a compromise.
- "Download once" needs a real first-run UX: progress, caching, ~600MB total across Piper+Whisper+bge.
- PII discipline still holds at Tier 0 (data goes external); it relaxes naturally at Tier 1/2 (data stays local).
  See the community AI-context work: the client context is PII-safe by construction + provider-agnostic, so it
  is already forward-compatible with a local LLM. [[reference_community_ai_axis_piisafe_context]]

## 5. Build order (when the window opens)

1. **Piper local-TTS path** in `wh-tts.js` (browser fallback) — closes "download the voice", highest UX value.
2. **`WH_LLM_URL` local slot** in `ai-chain.ts` — the sovereignty capstone; mirrors ASR; zero-risk.
3. **First-run model-download UX + a "Sovereignty mode" toggle** — packages Tiers 1/2 for real users.
4. **`validate_indigenous_stack.py` gate** — assert every capability keeps a local-first path AND a fallback,
   so no future change silently re-introduces a hard external dependency.

**Activation is Ian-gated** (heavy model installs: `faster-whisper` + ffmpeg for ASR; Piper voice; Ollama for
LLM). The CODE paths are additive + fallback-safe and can land without the installs (prod unchanged until the
env vars are set — the exact precedent set by `WH_ASR_URL` / `BGE_EMBED_URL`).

---

## 6. VOICE + AUDIO FOR PRODUCTION USERS — the hands-free, per-plant, data-sovereign audio stack (Ian 2026-07-12)

> Ian (2 msgs): *"make our own VOICE and AUDIO for production users — the SAME as our embedder for production
> users — so we don't rely on external providers."* The embedder (bge-local) is now the proven precedent:
> hands-free, per-user, self-healing (embeds automatically as the user works). Voice (TTS) + audio (ASR) must
> reach that same bar for production plants.

### 6.1 The sharper WHY — raw AUDIO is the MOST sensitive artifact, and it currently leaves the plant
The embedder already keeps text embeddings in-plant. But TODAY the voice pipeline still ships the single most
sensitive artifact off-site: a worker's **RAW voice recording** — their actual voice + spoken equipment tags,
fault descriptions, names, and PII — goes to **Groq for ASR** (`WH_ASR_URL` falls back to Groq when unset), and
the Companion speaks in the **OS browser voice** (`speechSynthesis`), which is device-variant and not "ours".
So "our own voice and audio" is not cosmetic — it is: **(a)** the raw voice recording NEVER leaves the plant
(local ASR default in prod), **(b)** the Companion speaks in ONE branded Hezekiah/Zaniah voice everywhere,
offline, **(c)** hands-free — the plant transcribes and speaks locally, automatically, with zero action from Ian.
Voice + face-of-the-brand + biometric-adjacent data is exactly what compliance buyers cannot send to an external
API — this is a sharper edge of the same sovereignty moat as the LLM.

### 6.2 Match the EMBEDDER's proven model exactly (don't invent — mirror)
| Property | Embedder ✅ BUILT | Voice / TTS | Audio / ASR |
|---|---|---|---|
| Local server | `tools/embed_server.py` (bge) | Piper server **OR** in-browser WASM (NEW) | `tools/asr_server.py` (faster-whisper) ✅ exists |
| Local-first env slot | `BGE_EMBED_URL` | **`WH_TTS_URL` (NEW — the one missing slot)** | `WH_ASR_URL` ✅ exists |
| Cloud fallback (default T0) | Voyage/Jina/Gemini | browser `speechSynthesis` | Groq |
| Hands-free / self-healing | embeds on write, auto | speaks every reply, auto | transcribes every voice note, auto |
| Per-plant in production | ✅ | build the slot | **flip the DEFAULT to local for T1/T2** |
| Outage behavior | fall back to cloud, never dead-end | fall back to browser TTS | fall back to Groq (T0) |

**The only NEW code slot is `WH_TTS_URL` in `wh-tts.js`** (mirrors `WH_ASR_URL` / `BGE_EMBED_URL`). ASR already
has its slot — the production change is making **local the DEFAULT for plant tiers** (hands-free), not cloud.

### 6.3 Refinements + extensions Ian implied (the terms he didn't name)
- **Family / indigenous-language ASR is non-negotiable for PH plants** ([[reference_voice_family_probe_harness]]):
  workers speak Tagalog / Cebuano / Ilonggo / code-switch. A local Whisper must NOT regress family-language
  accuracy vs Groq — the `voice_family_probe` harness (edge-tts synth → transcribe → grade) is the acceptance
  gate. This is also the missing instrument for the current arc's F-axis Voice-Journal walk (headless mic ≠ testable;
  synth-audio IS).
- **Branded voice quality** (from the content-audio best-practices research): pick + tune the Piper Hezekiah
  (technical/male) + Zaniah (strategist/female) voices; consistent, natural, not robotic; a loudness sanity target.
- **Self-healing round-trip** (the embedder parallel): mic → local ASR → gateway (grounded reply) → local TTS,
  all auto; ANY local-server miss falls back (cloud ASR / browser TTS) — never dead-ends the worker. The
  Voice-Journal double-write is already closed, so the write path is faithful-once.
- **First-run download UX** (~600MB total: Piper ~60MB + Whisper ~480MB + bge ~100–400MB) — progress + cache +
  "download once per plant"; folds into §5.3's "Sovereignty mode" toggle.
- **PII posture is provider-agnostic + forward-compatible** — the gateway redaction (incl. this session's K2
  `redactMemoryText`) + the PII-safe `setContext` mean nothing changes when the provider goes local; it only gets
  SAFER (data stays in-plant at T1/T2). [[reference_community_ai_axis_piisafe_context]]

### 6.4 Build order (voice+audio slice — code additive + fallback-safe; model activation Ian-gated)
1. **`WH_TTS_URL` local-first slot** in `wh-tts.js` (Piper server/WASM → browser fallback). Code lands now, prod
   unchanged until set — the `WH_ASR_URL` precedent. *(= §5.1, sharpened with the production framing.)*
2. **Tier-flag the ASR default**: T1/T2 plants transcribe LOCALLY by default (raw voice stays in-plant); T0 keeps
   Groq. A single `WH_AUDIO_TIER` / reuse the sovereignty toggle. Code additive.
3. **First-run voice + model download UX + "Sovereignty mode" toggle** (folds §5.3).
4. **Extend `validate_indigenous_stack.py`**: assert TTS AND ASR each keep a local-first path AND a fallback — no
   silent external dependency can be re-introduced (the forward-only sovereignty ratchet).
5. **Family-ASR acceptance gate**: local Whisper passes `voice_family_probe` with no regression vs cloud.

**Status: PLAN refined; NOT built.** The code paths (WH_TTS_URL slot, tier-flag, validator) are buildable now,
additive + fallback-safe (prod unchanged until env set). The heavy model installs (Piper voice, faster-whisper,
ffmpeg) stay Ian-gated. This §6 is the production-grade close of the current AI-Companion arc's F-axis voice
surface — tracked as the **V-axis** in `AI_COMPANION_LAYER_DEEP_ARC.md`.
