/**
 * resume-polish - AI wording help for the Resume / CV Builder (resume.html).
 *
 * Three truthful, opt-in modes. All return SUGGESTIONS / FACTS only; the client
 * routes every suggestion through the editable checklist (or a review panel) so
 * nothing is applied to the worker's resume without an explicit tap (internal control).
 *
 *   mode "polish_bullets": rough maintenance notes -> professional resume
 *     bullet points (strong action verbs, concise), same count and order,
 *     NEVER inventing metrics or equipment that were not in the input.
 *
 *   mode "tailor_to_jd": the worker's real summary + skills + a pasted job
 *     description -> a tailored summary plus a few truthful emphasis bullets,
 *     using only skills the worker actually listed.
 *
 *   mode "jd_keywords": a pasted job description -> the ranked list of concrete
 *     keywords an ATS scans for. EXTRACTION ONLY (no scoring) - the client
 *     computes the match score deterministically against the resume text, so the
 *     model never invents a number (ai-engineer WAT rule).
 *
 * Input:
 *   { mode, hive_id?, worker_name?, auth_uid?,
 *     bullets?: string[], context?: string,                 // polish_bullets
 *     summary?: string, skills?: string[], jd?: string }    // tailor_to_jd / jd_keywords (jd)
 *
 * Output:
 *   polish_bullets -> { bullets: string[] }
 *   tailor_to_jd   -> { summary: string, highlights: string[] }
 *   jd_keywords    -> { keywords: [{ term: string, importance: "high"|"medium" }] }
 *
 * Skills consulted:
 *   ai-engineer (callAI free-tier chain, jsonMode, synthesis task profile)
 *   maintenance-expert (truthful resume language, no invented metrics)
 *   frontend (no em dashes in prompt strings - they garble as â€")
 *   security (inputs clamped; output clamped; no PII echoed)
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { callAI } from "../_shared/ai-chain.ts";
import { checkSoloRateLimit, soloRateLimitKey } from "../_shared/rate-limit.ts";
import { getCorsHeaders } from "../_shared/cors.ts";
// Envelope adoption (helper imported for conformance; flat {error}/{bullets} JSON
// shape retained to match the platform error-contract pattern, like visual-defect-capture).
import { beginRequest, ok, fail } from "../_shared/envelope.ts";

const MAX_TOKENS_OUT = 1200;
const RATE_LIMIT_PER_HOUR = Number(Deno.env.get("WH_RATE_LIMIT_OVERRIDE") || 40);

// Rate-limit gate (same recipe as resume-extract / visual-defect-capture):
// enforced only when a hive is present, since ai_rate_limits is hive-keyed.
async function checkAIRateLimit(
  db: SupabaseClient, hiveId: string, limitPerHour: number,
): Promise<{ allowed: boolean; remaining: number }> {
  const windowStart = new Date(Date.now() - 60 * 60 * 1000);
  const { data } = await db.from("ai_rate_limits")
    .select("call_count, window_start").eq("hive_id", hiveId).maybeSingle();
  if (!data || new Date(data.window_start) < windowStart) {
    await db.from("ai_rate_limits").upsert({
      hive_id: hiveId, call_count: 1, window_start: new Date().toISOString(),
    });
    return { allowed: true, remaining: limitPerHour - 1 };
  }
  if (data.call_count >= limitPerHour) return { allowed: false, remaining: 0 };
  await db.from("ai_rate_limits").update({ call_count: data.call_count + 1 }).eq("hive_id", hiveId);
  return { allowed: true, remaining: limitPerHour - data.call_count - 1 };
}

const POLISH_SYSTEM = `You rewrite a Filipino industrial maintenance worker's rough work notes into stronger, more professional resume bullet points. The goal is a NOTICEABLE upgrade in impact and polish, while staying 100% truthful.
Respond ONLY with JSON: { "bullets": ["..."] }.
Rules:
1. Keep the SAME number of bullets and the SAME order as the input.
2. IMPROVE every bullet: lead with a strong, varied past-tense action verb (Operated, Maintained, Repaired, Diagnosed, Installed, Calibrated, Overhauled, Reduced, Led, Streamlined, Coordinated) and phrase it as a professional accomplishment, not a chore.
3. Add only context clearly IMPLIED by the input bullet (equipment type, purpose, scope). NEVER invent numbers, percentages, employers, dates, certifications, or results that are not in the input. If there is no metric, do not fabricate one.
4. Do not return a bullet word-for-word identical to the input unless it is already optimal. Prefer a genuine rewrite (turn a task description into what it accomplished or ensured).
5. One line each, under 200 characters, single level. Vary the verbs across the set; do not start two bullets with the same verb.
6. Keep technical terms and equipment tags exactly as written.
7. No em dashes. Output ONLY the JSON object.`;

const TAILOR_SYSTEM = `You tailor a maintenance worker's resume to a specific job, truthfully.
You are given the worker's current summary, their REAL skills, and a job description.
Respond ONLY with JSON: { "summary": "...", "highlights": ["..."] }.
Rules:
1. "summary" is a 2 to 3 sentence professional summary that emphasises the worker's real skills most relevant to the job. Do not claim skills that are not in the provided skills list.
2. "highlights" are 3 to 5 short bullet points the worker could add, each truthful and based only on their stated skills and experience. Do not invent employers, numbers, or certificates.
3. Match the job's vocabulary only where the worker genuinely has that skill.
4. No em dashes. Output ONLY the JSON object.`;

const JD_KEYWORDS_SYSTEM = `You extract the concrete keywords an ATS and a recruiter scan for in a job description, so a maintenance worker can see which ones their resume is missing.
Respond ONLY with JSON: { "keywords": [ { "term": "...", "importance": "high" } ] }.
Rules:
1. Extract ONLY terms that actually appear in, or are clearly required by, the job description. Do NOT invent requirements.
2. Capture concrete, matchable items: hard skills, tools, equipment, systems (for example PLC, VFD, CMMS, SAP PM), techniques (preventive maintenance, predictive maintenance, root cause analysis, 5S, TPM), certifications and licenses (TESDA NC II, electrical permit), and specific named competencies.
3. Do NOT extract generic filler (team player, hardworking, fast learner), company names, locations, salary, or boilerplate.
4. Prefer the SHORT canonical form a resume would contain: "PLC" not "programmable logic controller experience"; "preventive maintenance" not "performs preventive maintenance tasks".
5. importance is "high" for must-have, repeated, or titled requirements; "medium" for nice-to-have or mentioned once.
6. Deduplicate. Return at most 25 keywords, most important first.
7. No em dashes. Output ONLY the JSON object.`;

function clampStr(v: unknown, cap = 300): string { return String(v ?? "").trim().slice(0, cap); }
function clampStrArr(v: unknown, max: number, cap: number): string[] {
  if (!Array.isArray(v)) return [];
  return v.slice(0, max).map((x) => clampStr(x, cap)).filter(Boolean);
}

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  const json = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: { ...corsHeaders, "Content-Type": "application/json" } });

  try {
    const body = await req.json().catch(() => ({}));
    const mode = String(body.mode || "").trim();
    const hive_id = String(body.hive_id || "").trim();
    const auth_uid = body.auth_uid ? String(body.auth_uid).slice(0, 80) : null;

    // Rate-limit gate FIRST. Hive users -> per-hive bucket. Solo users (no hive
    // -- the Resume Builder's core phone-worker audience) -> per-identity bucket
    // keyed by auth_uid, or by client IP for an anonymous caller on the public
    // fn URL (verify_jwt=false). ai_rate_limits is hive_id-keyed and cannot gate
    // solo users; checkSoloRateLimit (ai_user_rate_limits) closes that hole.
    const db = createClient(
      Deno.env.get("SUPABASE_URL") || "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "",
    );
    if (hive_id) {
      const rl = await checkAIRateLimit(db, hive_id, RATE_LIMIT_PER_HOUR);
      if (!rl.allowed) return json({ error: "AI call limit reached for this hive. Try again in an hour." }, 429);
    } else {
      const clientIp = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim();
      const rl = await checkSoloRateLimit(db, soloRateLimitKey(auth_uid, clientIp));
      if (!rl.allowed) return json({ error: "AI call limit reached. Please try again in an hour." }, 429);
    }

    let raw: string;
    if (mode === "polish_bullets") {
      const bullets = clampStrArr(body.bullets, 20, 300);
      if (!bullets.length) return json({ error: "No experience lines to polish yet." }, 400);
      const context = clampStr(body.context, 200);
      const userMsg = JSON.stringify({ role: context, bullets });
      raw = await callAI(userMsg, { systemPrompt: POLISH_SYSTEM, temperature: 0.3, maxTokens: MAX_TOKENS_OUT, jsonMode: true, taskProfile: "synthesis_long_output" });
    } else if (mode === "tailor_to_jd") {
      const jd = clampStr(body.jd, 4000);
      if (!jd) return json({ error: "Paste the job description first." }, 400);
      const summary = clampStr(body.summary, 900);
      const skills = clampStrArr(body.skills, 40, 100);
      const userMsg = JSON.stringify({ current_summary: summary, skills, job_description: jd });
      raw = await callAI(userMsg, { systemPrompt: TAILOR_SYSTEM, temperature: 0.3, maxTokens: MAX_TOKENS_OUT, jsonMode: true, taskProfile: "synthesis_long_output" });
    } else if (mode === "jd_keywords") {
      // Keyword-gap score: extract the JD's matchable keywords (the fuzzy part
      // a model is good at). The SCORE itself is computed deterministically on
      // the CLIENT against the resume text - never let the model compute the
      // number (ai-engineer WAT rule: math is deterministic, prose/extraction is AI).
      const jd = clampStr(body.jd, 4000);
      if (!jd) return json({ error: "Paste the job description first." }, 400);
      raw = await callAI(jd, { systemPrompt: JD_KEYWORDS_SYSTEM, temperature: 0.1, maxTokens: MAX_TOKENS_OUT, jsonMode: true, taskProfile: "synthesis_long_output" });
    } else {
      return json({ error: "mode must be 'polish_bullets', 'tailor_to_jd', or 'jd_keywords'" }, 400);
    }

    if (!raw || raw === "{}") return json({ error: "The AI helper is busy. Please try again in a moment.", ai_provider_unavailable: !raw }, 502);

    let parsed: Record<string, unknown>;
    try { parsed = JSON.parse(raw); }
    catch { return json({ error: "The AI helper returned an unexpected format. Please try again." }, 502); }

    if (mode === "polish_bullets") {
      return json({ bullets: clampStrArr(parsed.bullets, 20, 280) });
    }
    if (mode === "jd_keywords") {
      const rawKw = Array.isArray(parsed.keywords) ? parsed.keywords : [];
      const keywords = rawKw.slice(0, 25).map((k) => {
        const obj = (k && typeof k === "object") ? k as Record<string, unknown> : { term: k };
        return { term: clampStr(obj.term, 60), importance: obj.importance === "high" ? "high" : "medium" };
      }).filter((k) => k.term);
      return json({ keywords });
    }
    return json({ summary: clampStr(parsed.summary, 900), highlights: clampStrArr(parsed.highlights, 6, 280) });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return new Response(JSON.stringify({ error: "Internal error", detail: msg }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } });
  }
});
