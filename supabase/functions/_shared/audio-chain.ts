// Multi-model Groq Whisper fallback chain for audio transcription.
// Same pattern as ai-chain.ts — skip on 429/413, throw only if all fail.
// All 3 models are on Groq's permanently free tier.

const WHISPER_CHAIN = [
  "whisper-large-v3-turbo",       // fastest, great quality — primary
  "distil-whisper-large-v3-en",   // very fast, English only — fallback 1
  "whisper-large-v3",             // most accurate, slowest — fallback 2
];

export async function transcribeAudio(
  audioFile: File | Blob,
  filename = "audio.mp4"
): Promise<string> {
  const apiKey = Deno.env.get("GROQ_API_KEY");
  if (!apiKey) throw new Error("GROQ_API_KEY not set");

  for (const model of WHISPER_CHAIN) {
    const form = new FormData();
    form.append("file", audioFile, filename);
    form.append("model", model);
    form.append("language", "en");
    form.append("response_format", "json");

    try {
      const res = await fetch("https://api.groq.com/openai/v1/audio/transcriptions", {
        method: "POST",
        signal: AbortSignal.timeout(30000),
        headers: { "Authorization": `Bearer ${apiKey}` },
        body: form,
      });

      // Rate-limited or payload too large — try next model
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
        console.log(`[audio-chain] transcribed by ${model}`);
        return data.text.trim();
      }

      console.warn(`[audio-chain] ${model} returned empty text`);
    } catch (err) {
      console.warn(`[audio-chain] ${model} threw: ${String(err).slice(0, 80)}`);
    }
  }

  throw new Error("All Whisper models unavailable — try again in a moment");
}
