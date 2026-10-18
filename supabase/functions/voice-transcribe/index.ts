import { serveObserved, failTracked } from "../_shared/observability.ts";
import { tracedReply } from "../_shared/trace-reply.ts";  // LM-O: one trace id per request
import { handleHealth } from "../_shared/health.ts";


// contract-allow: audio -> text passthrough
import { transcribeAudio } from "../_shared/audio-chain.ts";
import { log } from "../_shared/logger.ts";
import { getCorsHeaders } from "../_shared/cors.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.110.0";
import { resolveIdentity, resolveTenancy } from "../_shared/tenant-context.ts";
import { checkSoloRateLimit, soloRateLimitKey, soloRateLimitedResponse, soloUnidentifiedResponse } from "../_shared/rate-limit.ts";

// Receives a multipart audio blob from the browser (iOS MediaRecorder output),
// transcribes via Groq Whisper fallback chain, and returns plain text plus
// the ISO-639-1 language code Whisper auto-detected.
//
// Input:  FormData with field "audio" (audio/mp4 or audio/webm blob).
//         Optional field "language" (e.g. "en") to force a specific language;
//         omit to auto-detect (used by voice-journal for multilingual capture).
// Output: { text: "transcribed text", lang: "en" }

serveObserved("voice-transcribe", tracedReply("voice-transcribe", async (req, _trace) => {  // LM-O: one trace id per request; its model-call rows carry the id this reply returns
  // Arc T/T1: standard liveness /health (fn up + DB creds reachable).
  const _health = await handleHealth(req, "voice-transcribe", async () => ({
    deps: [{ name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) }],
  }));
  if (_health) return _health;
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  log.info(_trace, "request_start", { method: req.method });  // I6 observability, under the id this reply returns (tracedReply hands it in; R8: never a second id)

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

    // ★A CAST IS NOT A CHECK, AND `.size` ON A STRING IS `undefined` (2026-09-10, W3-FN F-lens).
    // `form.get("audio")` returns `File | string | null`; the `as File | null` above only stopped the
    // type-checker asking. When a caller sends `audio` as a plain TEXT field, this guard let it
    // through — a non-empty string is truthy, `undefined === 0` is false, and the 10 MB ceiling below
    // is `undefined > n`, also false. So a non-file sailed past both size guards into transcribeAudio,
    // where `audioFile.arrayBuffer is not a function` killed the self-host ASR (swallowed as a warning)
    // and `form.append("file", <string>)` made every Groq model answer 400 `missing_audio_input`.
    // The chain then exhausted and told the person "All Whisper models unavailable, try again in a
    // moment" — a 500 blaming the transcription providers for a request that never carried audio.
    // Checking the SHAPE, not just the truthiness, keeps the wrong-input case a legible 400.
    if (!(audioFile instanceof Blob)) {
      return new Response(
        JSON.stringify({ error: "The audio field must be a file, not a text value" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }
    if (audioFile.size === 0) {
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
      // Two changes on one line, and they are NOT equally well evidenced - worth separating:
      //   `_ip` as the fifth argument is a REAL, demonstrable gap being closed. It was simply not being
      //     passed, so `checkSoloRateLimit`'s CGNAT-aware IP ceiling - the always-on cap that catches a
      //     single IP rotating spoofed identities - never ran on this function at all. The per-identity
      //     bucket was doing the whole job alone.
      //   `strict` is defence in depth for a branch I could not reach: the fail-open case needs BOTH no
      //     session and no x-forwarded-for, and Kong (like Supabase's gateway) always supplies the
      //     header - an anonymous probe here was metered on `ip:172.18.0.1`, not waved through.
      // See the `strict` note in _shared/rate-limit.ts, which states the same limit.
      const _rl = await checkSoloRateLimit(_rlDb, soloRateLimitKey(_id.authUid, _ip), undefined, undefined, _ip, true);
      if (!_rl.allowed) {
        return _rl.scope === "unidentified"
          ? soloUnidentifiedResponse(corsHeaders)
          : soloRateLimitedResponse(corsHeaders, _rl.retry_after_seconds, _rl.scope);
      }
    }

    const filename = audioFile.name || "audio.mp4";
    // Fetch this hive's real asset tags so the indigenous ASR primes on them + repairs garbled codes
    // (CL12). Best-effort: any failure just means no vocab (transcription still works).
    // ★THE HIVE WAS THE CALLER'S WORD, AND THE REPAIR PUTS TAGS IN THE ANSWER (LM-X walk, 2026-10-07).
    // The comment that stood here said the tags "only steer decoding - never returned/leaked". The second
    // half was false: CL12 REPAIRS a garbled code to the nearest vocabulary tag, so the transcript carries the
    // tag back. And `hive_id` came straight from the form, read on the service-role client with no membership
    // check - resolveIdentity above proves WHO is calling, not WHICH hive they belong to. Anyone signed in (or
    // metered by IP) could name another plant's hive and read its asset tags back out of their own speech.
    // Every sibling voice function (voice-logbook-entry, voice-report-intent) already runs resolveTenancy on
    // the body's hive. Here an unproven hive gets NO vocabulary rather than a refusal: priming is optional, and
    // a person whose stored hive is stale should still get their words transcribed.
    let vocabHive: string | null = null;
    if (hiveId) {
      if (_id.isServiceRole) {
        vocabHive = hiveId;
      } else {
        const _t = await resolveTenancy(_rlDb, _id.authUid, hiveId);
        if (_t.ok && _t.hive_id) vocabHive = _t.hive_id;
        else log.warn(null, "voice-transcribe: unproven hive_id, ASR vocabulary not primed", { code: _t.ok ? "solo" : _t.code });
      }
    }
    let vocab: string[] | undefined;
    if (vocabHive) {
      try {
        // canonical-allow: ASR vocabulary priming only (equipment tags steer decoding; a repaired code can appear in
        // the transcript, which is why the hive must be the caller's own - see above);
        // this is not a displayed metric, so v_asset_truth (the display view) is not the read path here.
        const { data: tagRows } = await _rlDb
          .from("asset_nodes").select("tag").is("deleted_at", null).eq("hive_id", vocabHive).not("tag", "is", null).limit(200);
        const tags = (tagRows || []).map((r: { tag: string | null }) => (r.tag || "").trim()).filter(Boolean);
        if (tags.length) vocab = tags;
      } catch (_) { /* best-effort: ASR priming/repair is optional */ }
    }
    // ★NOBODY TRANSCRIBED, AND THE PERSON WAS TOLD "PROCESSING FAILED" (2026-10-12, UFAI edge walk W4805): a chain that
    // could not transcribe (every provider down, or a walk's no-model switch) threw into the generic catch below - a
    // non-leaky 500 the page could only call a failure. The cause is known and so is the remedy: say both.
    let result: Awaited<ReturnType<typeof transcribeAudio>>;
    try {
      result = await transcribeAudio(audioFile, filename, language, vocab);
    } catch (txErr) {
      log.warn(null, "voice-transcribe: no transcriber answered", { detail: String(txErr instanceof Error ? txErr.message : txErr).slice(0, 160) });
      return new Response(JSON.stringify({ error: "The voice transcriber is not answering just now, so nothing was transcribed. "
        + "Type your note instead, or try again in a minute." }),
        { status: 503, headers: { ...corsHeaders, "Content-Type": "application/json" } });
    }

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
}));
