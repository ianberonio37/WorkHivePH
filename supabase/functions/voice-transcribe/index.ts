import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { transcribeAudio } from "../_shared/audio-chain.ts";
import { getCorsHeaders } from "../_shared/cors.ts";

// Receives a multipart audio blob from the browser (iOS MediaRecorder output),
// transcribes via Groq Whisper fallback chain, and returns plain text.
// Input:  FormData with field "audio" (audio/mp4 or audio/webm blob)
// Output: { text: "transcribed text" }

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

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

    if (!audioFile || audioFile.size === 0) {
      return new Response(
        JSON.stringify({ error: "Missing or empty audio field" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Cap at 10 MB — Groq Whisper limit is 25 MB but field workers speak for < 30s
    if (audioFile.size > 10 * 1024 * 1024) {
      return new Response(
        JSON.stringify({ error: "Audio file too large (max 10 MB)" }),
        { status: 413, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const filename = audioFile.name || "audio.mp4";
    const text     = await transcribeAudio(audioFile, filename);

    return new Response(
      JSON.stringify({ text }),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );

  } catch (err) {
    console.error("voice-transcribe error:", err);
    return new Response(
      JSON.stringify({ error: err instanceof Error ? err.message : String(err) }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
