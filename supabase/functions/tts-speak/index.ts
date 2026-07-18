/**
 * tts-speak - Azure Speech Service TTS with Supabase Storage cache.
 *
 * Phase 7 of the WorkHive Persona Contract. Turns narration text +
 * persona key into a playable MP3 URL. The persona key maps to a fixed
 * Azure neural voice (Azure voice IDs retained verbatim after the
 * 2026-05-20 hezekiah/zaniah rename — same voice, new persona label):
 *
 *   hezekiah -> en-PH-JamesNeural   (Filipino male, PH English)
 *   zaniah   -> en-PH-RosaNeural    (Filipino female, PH English)
 *
 * Both en-PH neural voices ship in southeastasia. fil-PH-AngeloNeural +
 * fil-PH-BlessicaNeural are also available but we stay in the en-PH pair
 * because the companion answers in PH-English.
 *
 * Naturalness: SSML <prosody> tunes rate/pitch per persona, and commas
 * + periods get inserted <break/> tags so the cadence breathes instead
 * of running flat (which is what made the audio feel "robotic" before).
 *
 * Caching: SHA-256 hash of (text + voice_short_name) is the file key.
 * Repeat queries skip Azure entirely (cache HIT serves from Supabase
 * Storage, $0 Azure chars consumed). Free-tier F0 (500K chars/mo) +
 * caching = ~30-50 active workers comfortably free.
 *
 * Skills consulted:
 *   ai-engineer (persona contract integration, free-tier reasoning)
 *   security (key never touches client; PII-safe — narration only)
 *   performance (cache-first; cap text length; one Azure call per
 *                unique narration platform-wide)
 *   devops (env-var secret, region-aware endpoint, AbortSignal timeout)
 */

import { serveObserved } from "../_shared/observability.ts";
import { handleHealth } from "../_shared/health.ts";
import { logRequestStart } from "../_shared/logger.ts";

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
import { clampPersona } from "../_shared/persona.ts";
// A5 (FULLSTACK_COMPONENT_LIBRARY Layer A): Azure TTS is a paid cost surface reachable
// from the browser (wh-tts.js / voice-journal) — per-person/IP bucket before synth.
import { checkSoloRateLimit, soloRateLimitKey, soloRateLimitedResponse } from "../_shared/rate-limit.ts";

// ─── Constants ────────────────────────────────────────────────────────────────

// 1500 chars is roughly 30s of speech — well past anything Hezekiah/Zaniah would
// say in a single turn. Prevents abuse via large narration payloads.
const MAX_TEXT_LENGTH = 1500;

// Azure Neural voices for en-PH locale. Confirmed against the live voice
// catalog at /cognitiveservices/voices/list (southeastasia region, 2026-05-18):
//   en-PH-JamesNeural (Male)   — used for hezekiah persona (legacy Azure ID)
//   en-PH-RosaNeural  (Female) — used for zaniah   persona (legacy Azure ID)
// The Azure voice display names ("James" / "Rosa") are Microsoft's labels
// and are independent of the WorkHive persona name shown to workers.
// (fil-PH-AngeloNeural + fil-PH-BlessicaNeural also exist for pure-Tagalog
//  output, but the conversational companion replies in en-PH so we stick to
//  the English-Philippine pair.)
const PERSONA_TO_VOICE: Record<string, string> = {
  hezekiah: "en-PH-JamesNeural",  // legacy Azure voice ID retained 2026-05-20
  zaniah:   "en-PH-RosaNeural",   // legacy Azure voice ID retained 2026-05-20
};

// Per-persona prosody tuning. Hezekiah (tito) reads slightly slower and a
// touch lower for warmth; Zaniah (ate) stays neutral. Tiny adjustments —
// large rate/pitch shifts make Azure Neural sound synthetic again.
const PROSODY: Record<string, { rate: string; pitch: string }> = {
  hezekiah: { rate: "-4%", pitch: "-2%" },
  zaniah:   { rate: "-2%", pitch:  "0%" },
};

const CACHE_BUCKET = "tts-cache";

// ─── Env wiring ───────────────────────────────────────────────────────────────

const AZURE_KEY    = Deno.env.get("AZURE_SPEECH_KEY")    || "";
const AZURE_REGION = Deno.env.get("AZURE_SPEECH_REGION") || "southeastasia";
const SB_URL       = Deno.env.get("SUPABASE_URL")        || "";
const SB_KEY       = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";

const _adminClient = SB_URL && SB_KEY ? createClient(SB_URL, SB_KEY) : null;

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function sha256Hex(input: string): Promise<string> {
  const enc = new TextEncoder().encode(input);
  const buf = await crypto.subtle.digest("SHA-256", enc);
  return Array.from(new Uint8Array(buf))
    .map(b => b.toString(16).padStart(2, "0"))
    .join("");
}

function publicUrl(filename: string): string {
  // Public bucket — no signing needed. URL pattern is the Supabase Storage
  // public path.
  //
  // Local-dev URL rewrite: inside the Supabase Docker stack, SB_URL is
  // `http://kong:8000` (internal DNS) which the browser cannot resolve.
  // Rewrite to the host-accessible address `http://127.0.0.1:54321`. In
  // cloud deploys, SB_URL is `https://<ref>.supabase.co` which the
  // browser CAN reach, so the rewrite is a no-op.
  const externalBase = SB_URL.startsWith("http://kong:")
    ? "http://127.0.0.1:54321"
    : SB_URL;
  return `${externalBase}/storage/v1/object/public/${CACHE_BUCKET}/${filename}`;
}

function escapeXml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function buildSsml(voice: string, text: string, personaKey: string): string {
  // Audio-24kHz-48kbitrate-mono-mp3 keeps file sizes tiny (~ 8-12 KB per
  // 30-second narration).
  //
  // Naturalness levers we apply:
  //   1. <prosody rate="-X%" pitch="-Y%"> — slow James a touch + drop pitch
  //      slightly for the tito warmth. Rosa stays close to neutral.
  //   2. Strategic <break> insertions on commas and periods so the cadence
  //      breathes instead of running flat. 180ms on commas, 280ms on
  //      sentence ends. Tested against the Filipino-English samples in
  //      Azure's own demo page.
  //   3. <s> wraps the whole thing so the neural model can plan inflection
  //      across the sentence instead of generating word-by-word.
  const pr = PROSODY[personaKey] || { rate: "0%", pitch: "0%" };
  const xml = escapeXml(text)
    .replace(/([,;])\s+/g, '$1 <break time="180ms"/> ')
    .replace(/([.!?])\s+/g, '$1 <break time="280ms"/> ');
  return `<speak version='1.0' xml:lang='en-PH'>
  <voice name='${voice}'>
    <prosody rate='${pr.rate}' pitch='${pr.pitch}'>
      <s>${xml}</s>
    </prosody>
  </voice>
</speak>`;
}

// ─── Handler ──────────────────────────────────────────────────────────────────

serveObserved("tts-speak", async (req) => {
  // Arc T/T1: standard liveness /health (fn up + DB creds reachable).
  const _health = await handleHealth(req, "tts-speak", async () => ({
    deps: [{ name: "supabase", ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) }],
  }));
  if (_health) return _health;
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders });
  logRequestStart(req, "tts-speak");  // I6 observability
  if (req.method !== "POST") {
    return json(corsHeaders, 405, { error: "POST only" });
  }
  if (!AZURE_KEY) {
    return json(corsHeaders, 500, { error: "AZURE_SPEECH_KEY not configured" });
  }
  if (!_adminClient) {
    return json(corsHeaders, 500, { error: "Supabase client not initialised" });
  }

  let body: { text?: string; persona?: string };
  try { body = await req.json(); }
  catch { return json(corsHeaders, 400, { error: "invalid JSON" }); }

  const text = String(body.text || "").trim();
  if (!text) return json(corsHeaders, 400, { error: "text required" });
  if (text.length > MAX_TEXT_LENGTH) {
    return json(corsHeaders, 413, { error: `text too long (max ${MAX_TEXT_LENGTH} chars)` });
  }

  // A5: bucket on the authed user when the caller sent a JWT, else on IP (best-effort
  // identity — TTS is invoked with the session token by wh-tts.js).
  const _ip = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim();
  let _uid: string | null = null;
  try {
    const _bearer = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "");
    if (_bearer && _bearer !== SB_KEY) {
      const { data: _u } = await _adminClient.auth.getUser(_bearer);
      _uid = _u?.user?.id || null;
    }
  } catch (_) { /* fall through to IP bucket */ }
  const _rl = await checkSoloRateLimit(_adminClient, soloRateLimitKey(_uid, _ip), undefined, undefined, _ip);
  if (!_rl.allowed) return soloRateLimitedResponse(corsHeaders);

  const personaKey = clampPersona(body.persona);
  const voice      = PERSONA_TO_VOICE[personaKey];

  // Cache key: hash of (text + voice). Same narration with the same voice
  // -> one Azure call across the entire platform.
  const hash = await sha256Hex(`${voice}::${text}`);
  const filename = `${hash}.mp3`;

  // 0) Ensure the cache bucket exists. Auto-create on first run so cloud
  // deployments don't depend on a separate storage migration push.
  // Service-role only; getBucket returns null if missing, then createBucket.
  const { data: bucketInfo } = await _adminClient.storage.getBucket(CACHE_BUCKET);
  if (!bucketInfo) {
    const { error: createErr } = await _adminClient.storage.createBucket(CACHE_BUCKET, {
      public: true,
      fileSizeLimit: 524288,
      allowedMimeTypes: ["audio/mpeg", "audio/mp3"],
    });
    if (createErr && !String(createErr.message || "").toLowerCase().includes("already exists")) {
      return json(corsHeaders, 500, { error: "bucket create failed", detail: createErr.message });
    }
  }

  // 1) Try cache.
  // We probe by attempting a HEAD-like list (cheap) — Supabase Storage's
  // .list() returns entries even for tiny buckets in ms.
  const { data: existing } = await _adminClient.storage
    .from(CACHE_BUCKET)
    .list("", { search: filename, limit: 1 });
  if (existing && existing.find(e => e.name === filename)) {
    return json(corsHeaders, 200, {
      url:    publicUrl(filename),
      cached: true,
      voice,
      persona: personaKey,
    });
  }

  // 2) Cache miss — call Azure.
  const ssml = buildSsml(voice, text, personaKey);
  const azureUrl = `https://${AZURE_REGION}.tts.speech.microsoft.com/cognitiveservices/v1`;
  let audio: ArrayBuffer;
  try {
    const resp = await fetch(azureUrl, {
      method: "POST",
      headers: {
        "Ocp-Apim-Subscription-Key": AZURE_KEY,
        "Content-Type":              "application/ssml+xml",
        "X-Microsoft-OutputFormat":  "audio-24khz-48kbitrate-mono-mp3",
        "User-Agent":                "WorkHive-TTS/1.0",
      },
      body: ssml,
      signal: AbortSignal.timeout(15_000),
    });
    if (!resp.ok) {
      const errText = await resp.text().catch(() => "(no body)");
      return json(corsHeaders, 502, {
        error: `Azure TTS failed: ${resp.status}`,
        detail: errText.slice(0, 200),
      });
    }
    audio = await resp.arrayBuffer();
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return json(corsHeaders, 504, { error: "Azure TTS timeout or network error", detail: msg });
  }

  // 3) Store the MP3.
  const { error: upErr } = await _adminClient.storage
    .from(CACHE_BUCKET)
    .upload(filename, audio, {
      contentType: "audio/mpeg",
      upsert:      false,  // tolerate race: 2 concurrent misses on the same hash -> second insert errors, ignored
    });
  // 23505-equivalent: another invocation wrote first. Not an error from the
  // caller's perspective — the cached file exists, just return its URL.
  if (upErr && !String(upErr.message || "").toLowerCase().includes("already exists")) {
    return json(corsHeaders, 500, { error: "cache write failed", detail: upErr.message });
  }

  return json(corsHeaders, 200, {
    url:    publicUrl(filename),
    cached: false,
    voice,
    persona: personaKey,
  });
});

// Error contract sentinel for validate_edge_contracts.py — every failure path
// above goes through json() which produces: JSON.stringify({ error: "..." }).
function json(headers: HeadersInit, status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...headers, "Content-Type": "application/json" },
  });
}
