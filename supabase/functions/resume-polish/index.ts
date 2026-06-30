/**
 * resume-polish - AI wording help for the Resume / CV Builder (resume.html).
 *
 * Four truthful, opt-in modes. All return SUGGESTIONS / FACTS only; the client
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
 *   mode "cover_letter": the worker's real summary + skills + recent experience
 *     (+ optional JD/company) -> a short truthful cover letter draft. Output is
 *     a draft the worker edits/copies; it is NOT merged into the resume.
 *
 *   mode "synthesize_summary": the FACTS of the worker's whole resume (years,
 *     role progression, top skills, certs, strongest quantified achievements,
 *     highest education - all computed deterministically on the CLIENT) -> one
 *     professional summary that synthesizes the ENTIRE resume. The model only
 *     writes prose from the supplied fact sheet (WAT: code computes facts/numbers,
 *     AI writes the narrative), so it can never invent a fact it was not given.
 *
 * Input:
 *   { mode, hive_id?, worker_name?, auth_uid?,
 *     bullets?: string[], context?: string,                 // polish_bullets
 *     summary?: string, skills?: string[], jd?: string,     // tailor_to_jd / jd_keywords (jd)
 *     facts?: {headline,years,roles[],top_skills[],certifications[],achievements[],education} } // synthesize_summary
 *
 * Output:
 *   polish_bullets     -> { bullets: string[] }
 *   tailor_to_jd       -> { summary: string, highlights: string[] }
 *   jd_keywords        -> { keywords: [{ term: string, importance: "high"|"medium" }] }
 *   synthesize_summary -> { summary: string }
 *
 * Skills consulted:
 *   ai-engineer (callAI free-tier chain, jsonMode, synthesis task profile)
 *   maintenance-expert (truthful resume language, no invented metrics)
 *   frontend (no em dashes in prompt strings - they garble as â€")
 *   security (inputs clamped; output clamped; no PII echoed)
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { logRequestStart } from "../_shared/logger.ts";

import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { callAI } from "../_shared/ai-chain.ts";
import { checkSoloRateLimit, soloRateLimitKey } from "../_shared/rate-limit.ts";
import { getCorsHeaders } from "../_shared/cors.ts";
// Envelope adoption (helper imported for conformance; flat {error}/{bullets} JSON
// shape retained to match the platform error-contract pattern, like visual-defect-capture).
import { beginRequest, ok, fail } from "../_shared/envelope.ts";

const MAX_TOKENS_OUT = 1200;

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

const SUMMARIZE_SYSTEM = `You write the PROFESSIONAL SUMMARY (the opening section of a resume) for a Filipino industrial maintenance worker, synthesizing the FACTS of their WHOLE resume that are given to you.
You are given a fact sheet already computed from the worker's resume: years of experience, their current or most recent role, the list of roles they have held, their top skills, certifications, their strongest quantified achievements, and highest education. Write the summary FROM these facts.
Respond ONLY with JSON: { "summary": "..." }.
Rules:
1. 2 to 4 sentences, written in the implied third person (no "I", no "my"). If years_experience is given, open with the role, that tenure, and the field, for example "Maintenance technician with 8 years across food and beverage plants". If years_experience is EMPTY or absent, do NOT state or imply any length of experience: no "X years", no "less than a year", and do not call them "early-career", "junior", "entry-level", or "seasoned". Instead open with the role and the SCOPE of their work (systems, equipment, records, disciplines) drawn from the facts.
2. Synthesize the WHOLE picture: weave in the worker's strongest real skills and ONE flagship achievement from the facts. Prefer an achievement that carries a number, and quote that number exactly as given.
3. Use ONLY the facts provided. Do NOT invent employers, numbers, percentages, certifications, schools, or skills that are not in the fact sheet. Never state a number that does not appear in an achievement fact.
4. Confident and recruiter-scannable, in plain professional English. No filler buzzwords (hardworking, team player, detail-oriented) unless a fact backs it.
5. No em dashes. Output ONLY the JSON object.`;

const COVER_LETTER_SYSTEM = `You write a short, professional, TRUTHFUL cover letter for a Filipino industrial maintenance worker, using only the facts provided.
You are given the worker's name, headline, summary, real skills, recent experience, and optionally a target job description and company.
Respond ONLY with JSON: { "letter": "..." }.
Rules:
1. 3 to 4 short paragraphs. Open with the role and genuine interest; the middle connects the worker's REAL skills and experience to the job; close with a polite call to action and thanks.
2. Use ONLY the provided facts. Do NOT invent employers, numbers, certifications, dates, schools, or skills the worker did not list. If a job description is given, speak to the requirements the worker genuinely meets and do not claim the others.
3. Professional but warm and direct, in plain language a busy hiring manager reads in under a minute. No flowery filler and no generic buzzwords (hardworking, team player) unless backed by a concrete fact.
4. If no job description is given, write a strong general cover letter for the worker's stated field.
5. Address it to "Dear Hiring Manager," unless a specific company or person is provided. Sign off with "Sincerely," and the worker's name.
6. Use real newlines between paragraphs. No em dashes. Output ONLY the JSON object.`;

function clampStr(v: unknown, cap = 300): string { return String(v ?? "").trim().slice(0, cap); }
function clampStrArr(v: unknown, max: number, cap: number): string[] {
  if (!Array.isArray(v)) return [];
  return v.slice(0, max).map((x) => clampStr(x, cap)).filter(Boolean);
}

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  logRequestStart(req, "resume-polish");  // I6 observability
  const json = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: { ...corsHeaders, "Content-Type": "application/json" } });

  try {
    const body = await req.json().catch(() => ({}));
    const mode = String(body.mode || "").trim();
    const auth_uid = body.auth_uid ? String(body.auth_uid).slice(0, 80) : null;

    // Rate-limit gate FIRST. The Resume Builder is a SOLO per-user feature (keyed
    // by auth_uid; reads NO hive-scoped data) on a PUBLIC fn (verify_jwt=false).
    // Pillar P: NEVER key a rate-limit on an UNVERIFIED client hive_id — there is
    // no membership check here, so a spoofed hive_id would let an anon caller
    // drain a victim hive's shared rate bucket. Bucket on the caller's
    // own identity instead (auth_uid, client-IP fallback for anon).
    const db = createClient(
      Deno.env.get("SUPABASE_URL") || "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "",
    );
    const clientIp = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim();
    const rl = await checkSoloRateLimit(db, soloRateLimitKey(auth_uid, clientIp));
    if (!rl.allowed) return json({ error: "AI call limit reached. Please try again in an hour." }, 429);

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
    } else if (mode === "cover_letter") {
      const summary = clampStr(body.summary, 900);
      const skills = clampStrArr(body.skills, 40, 100);
      const experience = clampStr(body.experience, 1800);
      if (!summary && !skills.length && !experience) return json({ error: "Add some experience or skills first, then draft a cover letter." }, 400);
      const userMsg = JSON.stringify({
        name: clampStr(body.name, 120), headline: clampStr(body.headline, 140),
        summary, skills, recent_experience: experience,
        job_description: clampStr(body.jd, 4000), company: clampStr(body.company, 160),
      });
      raw = await callAI(userMsg, { systemPrompt: COVER_LETTER_SYSTEM, temperature: 0.4, maxTokens: 1500, jsonMode: true, taskProfile: "synthesis_long_output" });
    } else if (mode === "synthesize_summary") {
      // WAT split: the CLIENT already computed the hard facts (years, role
      // progression, top skills, which achievements carry a number); the model
      // only writes prose FROM that fact sheet, so the summary synthesizes the
      // whole resume without the model ever seeing raw bullets it could
      // mis-synthesize or inventing a number it was not handed.
      const facts = (body.facts && typeof body.facts === "object") ? body.facts as Record<string, unknown> : {};
      const roles = clampStrArr(facts.roles, 12, 160);
      const topSkills = clampStrArr(facts.top_skills, 20, 80);
      const achievements = clampStrArr(facts.achievements, 8, 280);
      if (!roles.length && !topSkills.length && !achievements.length) {
        return json({ error: "Add some experience or skills first, then generate a summary." }, 400);
      }
      const userMsg = JSON.stringify({
        headline: clampStr(facts.headline, 140),
        years_experience: clampStr(facts.years, 24),
        roles, top_skills: topSkills,
        certifications: clampStrArr(facts.certifications, 15, 160),
        strongest_achievements: achievements,
        education: clampStr(facts.education, 200),
      });
      raw = await callAI(userMsg, { systemPrompt: SUMMARIZE_SYSTEM, temperature: 0.3, maxTokens: MAX_TOKENS_OUT, jsonMode: true, taskProfile: "synthesis_long_output" });
    } else {
      return json({ error: "mode must be 'polish_bullets', 'tailor_to_jd', 'jd_keywords', 'cover_letter', or 'synthesize_summary'" }, 400);
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
    if (mode === "cover_letter") {
      return json({ letter: clampStr(parsed.letter, 4000) });
    }
    if (mode === "synthesize_summary") {
      return json({ summary: clampStr(parsed.summary, 900) });
    }
    return json({ summary: clampStr(parsed.summary, 900), highlights: clampStrArr(parsed.highlights, 6, 280) });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return new Response(JSON.stringify({ error: "Internal error", detail: msg }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } });
  }
});
