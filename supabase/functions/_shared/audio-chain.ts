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
}

export async function transcribeAudio(
  audioFile: File | Blob,
  filename = "audio.mp4",
  language?: string,   // omit for auto-detect; pass "en" for forced English
): Promise<TranscribeResult> {
  const apiKey = Deno.env.get("GROQ_API_KEY");
  if (!apiKey) throw new Error("GROQ_API_KEY not set");

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
        continue;
      }

      if (!res.ok) {
        const snippet = (await res.text()).slice(0, 120);
        console.warn(`[audio-chain] ${model} error ${res.status}: ${snippet}`);
        continue;
      }

      const data = await res.json();
      if (data?.text) {
        const detected = String(data.language || language || "").toLowerCase();
        console.log(`[audio-chain] transcribed by ${model} (lang=${detected || "?"})`);
        return { text: String(data.text).trim(), lang: detected };
      }

      console.warn(`[audio-chain] ${model} returned empty text`);
    } catch (err) {
      console.warn(`[audio-chain] ${model} threw: ${String(err).slice(0, 80)}`);
    }
  }

  throw new Error("All Whisper models unavailable, try again in a moment");
}
