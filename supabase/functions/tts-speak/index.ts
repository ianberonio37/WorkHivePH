/**
 * tts-speak - Azure Speech Service TTS with Supabase Storage cache.
 *
 * Phase 7 of the WorkHive Persona Contract. Turns narration text +
 * persona key into a playable MP3 URL. The persona key maps to a fixed
 * Azure neural voice:
 *
 *   james -> en-PH-JamesNeural  (Filipino male, PH English)
 *   rosa  -> en-PH-RosaNeural   (Filipino female, PH English)
 *
 * Same voices the Video Marketing app already uses — one consistent
 * audio identity across the platform.
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

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";
import { clampPersona } from "../_shared/persona.ts";

// ─── Constants ────────────────────────────────────────────────────────────────

// 1500 chars is roughly 30s of speech — well past anything James/Rosa would
// say in a single turn. Prevents abuse via large narration payloads.
const MAX_TEXT_LENGTH = 1500;

const PERSONA_TO_VOICE: Record<string, string> = {
  james: "en-PH-JamesNeural",
  rosa:  "en-PH-RosaNeural",
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
  return `${SB_URL}/storage/v1/object/public/${CACHE_BUCKET}/${filename}`;
}

function escapeXml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function buildSsml(voice: string, text: string): string {
  // Audio-24kHz-48kbitrate-mono-mp3 keeps file sizes tiny (~ 8-12 KB per
  // 30-second narration). Default rate; persona variation comes from the
  // voice itself, not pitch tweaks.
  return `<speak version='1.0' xml:lang='en-PH'>
  <voice name='${voice}'>${escapeXml(text)}</voice>
</speak>`;
}

// ─── Handler ──────────────────────────────────────────────────────────────────

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders });
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
  const ssml = buildSsml(voice, text);
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

function json(headers: HeadersInit, status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...headers, "Content-Type": "application/json" },
  });
}
