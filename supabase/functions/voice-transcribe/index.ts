import { serveObserved, failTracked } from "../_shared/observability.ts";
import { handleHealth } from "../_shared/health.ts";

import { logRequestStart } from "../_shared/logger.ts";

// contract-allow: audio -> text passthrough
import { transcribeAudio } from "../_shared/audio-chain.ts";
import { log } from "../_shared/logger.ts";
import { getCorsHeaders } from "../_shared/cors.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { resolveIdentity } from "../_shared/tenant-context.ts";
import { checkSoloRateLimit, soloRateLimitKey, soloRateLimitedResponse } from "../_shared/rate-limit.ts";

// Receives a multipart audio blob from the browser (iOS MediaRecorder output),
// transcribes via Groq Whisper fallback chain, and returns plain text plus
// the ISO-639-1 language code Whisper auto-detected.
//
// Input:  FormData with field "audio" (audio/mp4 or audio/webm blob).
//         Optional field "language" (e.g. "en") to force a specific language;
//         omit to auto-detect (used by voice-journal for multilingual capture).
// Output: { text: "transcribed text", lang: "en" }

serveObserved("voice-transcribe", async (req) => {
  // Arc T/T1: standard liveness /health (fn up + DB creds reachable).
  const _health = await handleHealth(req, "voice-transcribe", async () => ({
    deps: [{ name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) }],
  }));
  if (_health) return _health;
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  logRequestStart(req, "voice-transcribe");  // I6 observability

  try {
    const contentType = req.headers.get("content-type") || "";

    if (!contentType.includes("multipart/form-data")) {
      return new Response(
        JSON.stringify({ error: "Expected multipart/form-data with audio field" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const form      = await req.formData();
    const audioFile = form.get("audio") as File | null;
    const langField = form.get("language");
    const language  = typeof langField === "string" && langField.trim()
      ? langField.trim().toLowerCase()
      : undefined;
    // Optional hive_id → prime + repair the indigenous ASR with this hive's real asset tags (CL12).
    const hiveId = typeof form.get("hive_id") === "string"
      ? (form.get("hive_id") as string).trim() || null : null;

    if (!audioFile || audioFile.size === 0) {
      return new Response(
        JSON.stringify({ error: "Missing or empty audio field" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Cap at 10 MB. Groq Whisper limit is 25 MB but field workers speak for < 30s.
    if (audioFile.size > 10 * 1024 * 1024) {
      return new Response(
        JSON.stringify({ error: "Audio file too large (max 10 MB)" }),
        { status: 413, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // LLM10 unbounded-consumption: ASR/Whisper is expensive and this fn is called DIRECTLY by the
    // frontend (voice-handler / report-sender / voice-journal). Bound by identity-or-IP (solo bucket);
    // the trusted service_role path is exempt.
    const _rlDb = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
    const _id   = await resolveIdentity(_rlDb, req);
    if (!_id.isServiceRole) {
      const _ip = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim();
      const _rl = await checkSoloRateLimit(_rlDb, soloRateLimitKey(_id.authUid, _ip));
      if (!_rl.allowed) return soloRateLimitedResponse(corsHeaders);
    }

    const filename = audioFile.name || "audio.mp4";
    // Fetch this hive's real asset tags so the indigenous ASR primes on them + repairs garbled codes
    // (CL12). Best-effort: any failure just means no vocab (transcription still works). Tags are not
    // sensitive (equipment codes) and only steer decoding — never returned/leaked.
    let vocab: string[] | undefined;
    if (hiveId) {
      try {
        // canonical-allow: ASR vocabulary priming only (equipment tags steer decoding, never returned/leaked);
        // this is not a displayed metric, so v_asset_truth (the display view) is not the read path here.
        const { data: tagRows } = await _rlDb
          .from("asset_nodes").select("tag").eq("hive_id", hiveId).not("tag", "is", null).limit(200);
        const tags = (tagRows || []).map((r: { tag: string | null }) => (r.tag || "").trim()).filter(Boolean);
        if (tags.length) vocab = tags;
      } catch (_) { /* best-effort: ASR priming/repair is optional */ }
    }
    const result   = await transcribeAudio(audioFile, filename, language, vocab);

    // X-FIND (2026-07-12): surface a low-confidence flag so the client CLARIFIES ("did I hear that
    // right?") instead of sending a mis-heard question to the companion, which then confabulates
    // (caught live on a garbled Cebuano transcript, ASR 40%, grounded to a real asset). avg_logprob
    // is the indigenous ASR's mean per-segment confidence. Floor CALIBRATED against real synth audio
    // (verify_asr_conf.py): clean English -0.236, clean Taglish -0.178, GARBLED Cebuano -0.489 -> the
    // discriminating band is ~-0.45. NOTE (honest): avg_logprob is a PARTIAL signal - Whisper is often
    // confidently WRONG on out-of-distribution audio, so this catches only clearer garble; the real
    // Cebuano fix is the large-v3 model (V-axis V4). null (Groq fallback = no signal) is NEVER flagged,
    // so the cloud path is unchanged. A false-flag only asks to re-record (non-destructive), so the
    // floor errs slightly toward catching garble.
    const LOW_CONF_FLOOR = -0.45;
    const lp = typeof result.avg_logprob === "number" ? result.avg_logprob : null;
    const low_confidence = lp !== null && lp < LOW_CONF_FLOOR;
    return new Response(
      JSON.stringify({ text: result.text, lang: result.lang, avg_logprob: lp, low_confidence }),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );

  } catch (err) {
    log.error(null, "voice-transcribe error:", { detail: err });
    // T2b: aggregate this HANDLED failure to wh_traces + non-leaky 500.
    return await failTracked(req, "voice-transcribe", "voice_transcribe_error", err);
  }
});
