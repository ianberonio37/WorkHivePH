// Multi-model Groq Whisper fallback chain for audio transcription.
// Same pattern as ai-chain.ts: skip on 429/413, throw only if all fail.
// All models are on Groq's permanently free tier.
//
// Language handling:
//   * When `language` is passed (e.g. "en"), Whisper transcribes assuming
//     that language. distil-whisper is English-only and is included only
//     in the forced-English chain.
//   * When `language` is omitted, Whisper auto-detects from audio. The
//     detected ISO-639-1 code is returned via the `verbose_json`
//     response_format. distil-whisper is skipped for auto-detect.
//
// ★A TRANSCRIPTION IS A MODEL CALL TOO (LM-O follow-up, 2026-10-08). Every transcription a provider answers (the
// self-hosted ASR or a Groq Whisper model), and every walk none answered, is reported to the request's model-call
// collector (_shared/model-calls.ts) with kind transcription, the provider and model, the audio seconds the provider
// says it processed (Whisper verbose_json `duration`) and the latency - serveObserved writes one ai_cost_log row each.

import { reportModelCall, reportModelCallFailed, modelCallsRefused } from "./model-calls.ts";

// the same LOCAL test as ai-chain.ts _AI_CHAIN_LOCAL: prod is *.supabase.co, where a walk switch is never honoured
const _AUDIO_CHAIN_LOCAL = /\/\/(kong|localhost|127\.0\.0\.1)(:|\/|$)/.test(Deno.env.get("SUPABASE_URL") || "");

const WHISPER_CHAIN_MULTI = [
  "whisper-large-v3-turbo",       // fastest, multilingual: primary
  "whisper-large-v3",             // most accurate, slowest: fallback
];

const WHISPER_CHAIN_EN = [
  "whisper-large-v3-turbo",
  "distil-whisper-large-v3-en",   // very fast, English-only
  "whisper-large-v3",
];

export interface TranscribeResult {
  text: string;
  lang: string;   // ISO-639-1 (e.g. "en", "tl"). Empty if not detected.
  // Mean per-segment avg_logprob from the indigenous ASR (~ -0.1 confident … < -1.0 garbled), when
  // available (self-host path only — Groq doesn't expose it). The voice pipeline gates grounding on
  // it: a mis-heard question (X-FIND 2026-07-12, Cebuano 40%) should clarify, not confabulate. null
  // when unknown (Groq fallback) → treat as "no low-confidence signal", i.e. do not block.
  avg_logprob?: number | null;
}

// ── Indigenous (self-hosted) Whisper — NO external API, NO rate limit ──────────
// Ian, 2026-07-07: a single external provider (Groq free tier ~30 rpm org-shared) is
// unreliable in production with many concurrent users. `tools/asr_server.py` (faster-whisper)
// serves the SAME Whisper transcription with no per-request cap. Prefer it when reachable;
// fall through to the Groq chain if it's unset/down (graceful — voice never goes fully dark).
// SAME env-gated pattern as embeddings' BGE_EMBED_URL (embedding-chain.ts) + TTS' WH_TTS_EDGE_URL:
// activates only when WH_ASR_URL is set; local auto-defaults, prod sets it explicitly (or leaves
// empty → self-host skipped, Groq-only, unchanged behaviour).
const _IS_LOCAL_ASR = /(kong|localhost|127\.0\.0\.1)(:|\/|$)/.test(Deno.env.get("SUPABASE_URL") || "");
const WH_ASR_URL = Deno.env.get("WH_ASR_URL") || (_IS_LOCAL_ASR ? "http://host.docker.internal:8902/transcribe" : "");

/** seconds of audio, when a transcription response states it */
function _seconds(v: unknown): number | null {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) && n >= 0 ? n : null;
}

async function transcribeLocal(
  audioFile: File | Blob,
  language?: string,
  vocab?: string[],   // hive asset codes → prime + deterministically repair garbled codes (CL12)
  tried: string[] = [],   // LM-O: the record's providers_tried, shared with the Groq walk
  t0: number = performance.now(),
): Promise<TranscribeResult | null> {
  if (!WH_ASR_URL) return null;
  try {
    const qp = new URLSearchParams();
    if (language) qp.set("lang", language);
    if (vocab && vocab.length) qp.set("vocab", vocab.slice(0, 60).join(","));
    const qs = qp.toString();
    const url = qs ? `${WH_ASR_URL}?${qs}` : WH_ASR_URL;
    const buf = await audioFile.arrayBuffer();
    const res = await fetch(url, {
      method: "POST",
      signal: AbortSignal.timeout(30000),
      headers: { "Content-Type": "application/octet-stream" },
      body: buf,
    });
    if (!res.ok) {
      console.warn(`[audio-chain] self-host asr ${res.status} — falling back to Groq`);
      tried.push(`asr-local/whisper=${res.status}`);
      return null;
    }
    const data = await res.json();
    if (data?.text) {
      const lang = String(data.lang || language || "").toLowerCase();
      console.log(`[audio-chain] transcribed by asr-local (lang=${lang || "?"})`);
      const model = String(data.model || "whisper");
      tried.push(`asr-local/${model}=${res.status}`);
      reportModelCall({ kind: "transcription", providerName: "asr-local", modelName: model,
        audio_seconds: _seconds(data.duration), started_at: t0, tried });
      return {
        text: String(data.text).trim(),
        lang,
        avg_logprob: typeof data.avg_logprob === "number" ? data.avg_logprob : null,
      };
    }
    tried.push("asr-local/whisper=empty");
    return null;   // empty → fall through to Groq
  } catch (err) {
    console.warn(`[audio-chain] self-host asr threw: ${String(err).slice(0, 80)} — falling back to Groq`);
    tried.push(`asr-local/whisper=${/timeout|abort/i.test(String(err)) ? "timeout" : "threw"}`);
    return null;
  }
}

export async function transcribeAudio(
  audioFile: File | Blob,
  filename = "audio.mp4",
  language?: string,   // omit for auto-detect; pass "en" for forced English
  vocab?: string[],    // hive asset codes → indigenous ASR prime + garbled-code repair (CL12)
): Promise<TranscribeResult> {
  const t0 = performance.now();      // LM-O: the record's latency (the whole walk the caller waited on)
  const tried: string[] = [];        // LM-O: the record's providers_tried
  // ★A WALK SPENDS NO MODEL CALL, AUDIO INCLUDED (2026-10-12): the text chain refused on the walk's switch; this chain
  // did not, so a walked voice note reached Groq Whisper. Refused before any provider, the self-hosted ASR included,
  // exactly as a chain with nothing to ask fails - the caller's could-not-transcribe path answers.
  if (_AUDIO_CHAIN_LOCAL && modelCallsRefused()) {
    console.warn("[audio-chain] no model call: the request asked for none (x-wh-walk-no-model, local runtime)");
    throw new Error("no model call: the request asked for none");
  }
  // Indigenous self-hosted Whisper first (no rate limit); Groq chain is the cloud fallback.
  const local = await transcribeLocal(audioFile, language, vocab, tried, t0);
  if (local && local.text) return local;

  const apiKey = Deno.env.get("GROQ_API_KEY");
  if (!apiKey) {
    // the self-hosted ASR was asked and did not answer: that attempt is a failed call; with nothing asked, no call
    if (tried.length) reportModelCallFailed({ kind: "transcription", providerName: "chain", modelName: "exhausted", tried, started_at: t0 });
    throw new Error("GROQ_API_KEY not set");
  }

  const chain = language ? WHISPER_CHAIN_EN : WHISPER_CHAIN_MULTI;

  for (const model of chain) {
    const form = new FormData();
    form.append("file", audioFile, filename);
    form.append("model", model);
    if (language) form.append("language", language);
    // verbose_json includes detected `language` field when not forced.
    form.append("response_format", "verbose_json");

    try {
      const res = await fetch("https://api.groq.com/openai/v1/audio/transcriptions", {
        method: "POST",
        signal: AbortSignal.timeout(30000),
        headers: { "Authorization": `Bearer ${apiKey}` },
        body: form,
      });

      if (res.status === 429 || res.status === 413) {
        console.warn(`[audio-chain] ${model} skipped (HTTP ${res.status})`);
        tried.push(`groq/${model}=${res.status}`);
        continue;
      }

      if (!res.ok) {
        const snippet = (await res.text()).slice(0, 120);
        console.warn(`[audio-chain] ${model} error ${res.status}: ${snippet}`);
        tried.push(`groq/${model}=${res.status}`);
        continue;
      }

      const data = await res.json();
      if (data?.text) {
        const detected = String(data.language || language || "").toLowerCase();
        console.log(`[audio-chain] transcribed by ${model} (lang=${detected || "?"})`);
        tried.push(`groq/${model}=${res.status}`);
        reportModelCall({ kind: "transcription", providerName: "groq", modelName: model,
          audio_seconds: _seconds(data.duration), started_at: t0, tried });
        return { text: String(data.text).trim(), lang: detected };
      }

      console.warn(`[audio-chain] ${model} returned empty text`);
      tried.push(`groq/${model}=empty`);
    } catch (err) {
      console.warn(`[audio-chain] ${model} threw: ${String(err).slice(0, 80)}`);
      tried.push(`groq/${model}=${/timeout|abort/i.test(String(err)) ? "timeout" : "threw"}`);
    }
  }

  reportModelCallFailed({ kind: "transcription", providerName: "chain", modelName: "exhausted", tried, started_at: t0 });
  throw new Error("All Whisper models unavailable, try again in a moment");
}
