import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

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

serve(async (req) => {
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
    const result   = await transcribeAudio(audioFile, filename, language);

    return new Response(
      JSON.stringify({ text: result.text, lang: result.lang }),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );

  } catch (err) {
    log.error(null, "voice-transcribe error:", { detail: err });
    return new Response(
      JSON.stringify({ error: err instanceof Error ? err.message : String(err) }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
