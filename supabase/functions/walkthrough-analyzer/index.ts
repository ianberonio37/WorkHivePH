/**
 * walkthrough-analyzer — WorkHive Platform
 * ==========================================
 * Phase 2 of the self-improving test architecture.
 *
 * Accepts a walkthrough screenshot (base64 PNG) + console log text +
 * page metadata, then uses the callAI / callAIMultimodal chain to:
 *
 *   1. Classify what's wrong visually (image analysis via vision models)
 *   2. Classify console errors against the 9 Sentinel Agent domains
 *   3. Return a structured Finding that can be written to findings.json
 *
 * All AI calls route through _shared/ai-chain.ts — no provider SDK imports.
 * Vision models in the chain (Groq Scout 17B, OpenRouter Gemma 4/3) handle
 * the image analysis. Text models handle the console log classification.
 *
 * Called from tools/analyze_walkthrough.py after every spec run.
 *
 * Request body:
 *   {
 *     page_slug:      string          — e.g. "hive"
 *     page_file:      string          — e.g. "hive.html"
 *     screenshot_b64: string | null   — base64 PNG top screenshot (omit for text-only)
 *     console_errors: string[]        — JS errors captured during the test
 *     verdict_text:   string | null   — what the verdict label showed at capture time
 *     cards_settled:  boolean         — did waitForFunction see settled heroes?
 *     chip_populated: boolean         — was at least one .wh-source-chip found?
 *   }
 *
 * Response:
 *   {
 *     findings: Finding[]     — 0-N findings for this page (empty = all clear)
 *     model_used: string      — which model classified the page
 *   }
 *
 * Skills consulted: ai-engineer (callAI/callAIMultimodal pattern, JSON output,
 * AbortSignal.timeout, no provider SDK), architect (WAT: AI reasons, code executes).
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { getCorsHeaders } from "../_shared/cors.ts";
import { callAI, callAIMultimodal } from "../_shared/ai-chain.ts";

// ── Sentinel Agent domain map — matches the 9-agent grouping ─────────────────
const SENTINEL_DOMAINS = `
1. Schema Sentinel      — DB structure, migrations, RLS, FKs, indexes
2. Data Guardian        — Data correctness, concurrency, soft-delete, state machines
3. Security Watchdog    — Auth, secrets, CORS, PII, XSS, multi-tenant
4. AI Quality Inspector — AI costs, safety, regression, payload quality, gateway
5. Platform Registrar   — Config, registration completeness, nav, canonical anchor
6. Frontend Fidelity    — UX contract, accessibility, loading states, Playwright specs
7. Performance Guardian — PWA, service worker, realtime, cold start, performance
8. Domain Features      — Feature-specific validators (logbook, PM, inventory, etc.)
9. Integration Inspector— External system contracts, API contracts, CMMS, webhooks
`.trim();

// ── System prompts ────────────────────────────────────────────────────────────

const VISUAL_SYSTEM = `You are a UI quality inspector for WorkHive, an industrial maintenance platform.
You are given a screenshot of a page and metadata about its render state.
Your job is to identify surface-level issues a supervisor or field worker would notice.

Focus on:
- Plain-Read contract: is the verdict at the top? Do the 3 cards show real numbers (not — or Loading)?
- Source chips: is there a "Source: ..." chip below the page title or below each AI/derived panel?
- Contradiction: does the verdict tone (red/amber/green) match what the cards show?
- Empty states: are there placeholders showing that should be hidden when data exists?
- Console errors: do any JS errors indicate a crash that would break the page?

Respond ONLY in this JSON shape — no other text:
{
  "issues": [
    {
      "description": "one sentence describing exactly what is wrong",
      "severity": "critical | high | medium | low",
      "domain": "which of the 9 Sentinel Agent domains owns this",
      "sentinel_agent": "specific agent name, e.g. 'Frontend Fidelity (UX contract)'",
      "proposed_gate": "one sentence describing what test or validator layer would catch this"
    }
  ],
  "overall": "clean | has_issues",
  "model_notes": "brief note on image quality or confidence"
}

If the page looks correct and has no issues, return { "issues": [], "overall": "clean", "model_notes": "" }.
Do not fabricate issues. Only report what you can observe.`;

const TEXT_SYSTEM = `You are a platform quality analyst for WorkHive.
You are given console errors from a Playwright test run and render state metadata.
Map each error to the appropriate Sentinel Agent domain:

${SENTINEL_DOMAINS}

Respond ONLY in this JSON shape:
{
  "issues": [
    {
      "description": "one sentence: what broke and what it means for the user",
      "severity": "critical | high | medium | low",
      "domain": "Sentinel Agent domain name",
      "sentinel_agent": "specific agent, e.g. 'Security Watchdog (JS syntax)'",
      "proposed_gate": "one sentence: what test or validator would prevent this"
    }
  ],
  "overall": "clean | has_issues"
}

Ignore: TypeError: Failed to fetch, net::ERR_, 401 errors — these are Supabase session noise.
Report: ReferenceError, SyntaxError, TypeError (not fetch), any 'already been declared' errors.`;

// ── Phase 3: Proposal generator ──────────────────────────────────────────────
//
// Given an open finding from findings.json, generates concrete test code or
// validator layer additions to close the gate. Routes through callAI chain.

const PROPOSAL_SYSTEM = `You are a Playwright and Python validator expert for WorkHive.
Given an open finding, write the exact code to gate it.
Choose either a journey spec test OR a validator layer — whichever is more appropriate:
- Use a Playwright journey test for behavioral/visual issues (wrong UI state, missing element)
- Use a Python validator layer for structural issues (missing registration, code pattern)

Respond ONLY in this JSON shape:
{
  "type": "playwright_test | validator_layer",
  "target_file": "tests/journey-X.spec.ts OR validate_Y.py",
  "description": "one sentence: what this gates",
  "code": "the exact TypeScript or Python code to add (complete test or layer function)"
}`;


// ── Main handler ──────────────────────────────────────────────────────────────

serve(async (req: Request): Promise<Response> => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: getCorsHeaders(req) });
  }

  try {
    const body = await req.json();
    const {
      page_slug,
      page_file,
      screenshot_b64,
      console_errors = [],
      verdict_text,
      cards_settled,
      chip_populated,
    } = body;

    // ── Phase 3: Proposal mode ────────────────────────────────────────────────
    // If action=propose, generate test/validator code for a specific finding.
    if (body.action === "propose") {
      const finding = body.finding;
      if (!finding) {
        return new Response(
          JSON.stringify({ error: "finding object required for action=propose" }),
          { status: 400, headers: { "Content-Type": "application/json", ...getCorsHeaders(req) } },
        );
      }
      const proposalPrompt = `Finding to gate:
ID: ${finding.id}
Page: ${finding.page}
Issue: ${finding.issue}
Severity: ${finding.severity}
Domain: ${finding.domain}
Sentinel Agent: ${finding.sentinel_agent}
Proposed gate (hint): ${finding._proposed_gate || "not specified"}

Write the code to gate this finding permanently.`;

      const raw = await callAI(
        proposalPrompt,
        { systemPrompt: PROPOSAL_SYSTEM, temperature: 0.2, maxTokens: 2048, jsonMode: true },
      );
      try {
        const proposal = JSON.parse(raw);
        return new Response(
          JSON.stringify({ proposal }),
          { headers: { "Content-Type": "application/json", ...getCorsHeaders(req) } },
        );
      } catch {
        return new Response(
          JSON.stringify({ error: "proposal generation failed", raw: raw.slice(0, 200) }),
          { status: 500, headers: { "Content-Type": "application/json", ...getCorsHeaders(req) } },
        );
      }
    }

    if (!page_slug) {
      return new Response(
        JSON.stringify({ error: "page_slug is required" }),
        { status: 400, headers: { "Content-Type": "application/json", ...getCorsHeaders(req) } },
      );
    }

    const findings: object[] = [];
    let modelUsed = "none";

    // ── 1. Visual analysis (if screenshot provided) ───────────────────────────
    if (screenshot_b64) {
      const visualPrompt = `Page: ${page_slug} (${page_file})
Render state:
- verdict_text: ${verdict_text ?? "not found"}
- cards_settled: ${cards_settled}
- chip_populated: ${chip_populated}

Analyze this screenshot for surface-level issues.`;

      const imageDataUrl = screenshot_b64.startsWith("data:")
        ? screenshot_b64
        : `data:image/png;base64,${screenshot_b64}`;

      const raw = await callAIMultimodal(
        visualPrompt,
        imageDataUrl,
        { systemPrompt: VISUAL_SYSTEM, temperature: 0.1, maxTokens: 1024, jsonMode: true },
      );

      try {
        const parsed = JSON.parse(raw);
        if (parsed.issues?.length > 0) {
          findings.push(...parsed.issues.map((i: object) => ({ ...i, source: "visual", page: page_slug })));
        }
        modelUsed = parsed.model_notes ? `vision:${parsed.model_notes}` : "vision";
      } catch {
        console.warn(`[walkthrough-analyzer] failed to parse visual result: ${raw.slice(0, 120)}`);
      }
    }

    // ── 2. Implicit render-state issues (no AI needed — pure logic) ───────────
    if (!chip_populated && page_slug !== "logbook" && page_slug !== "voice-journal") {
      findings.push({
        source:         "render_state",
        page:           page_slug,
        description:    `No .wh-source-chip was populated on ${page_slug}.html — supervisor cannot trace data provenance`,
        severity:       "medium",
        domain:         "Platform Registrar",
        sentinel_agent: "Platform Registrar (L11 insight panel anchor)",
        proposed_gate:  `Add renderSourceChip() call to the page's init function and register in L11 INSIGHT_PANEL_CONTRACT`,
      });
    }

    if (!cards_settled && verdict_text && (verdict_text.startsWith("Computing") || verdict_text.startsWith("Loading"))) {
      findings.push({
        source:         "render_state",
        page:           page_slug,
        description:    `Cards did not settle before screenshot — verdict still shows "${verdict_text}"`,
        severity:       "medium",
        domain:         "Frontend Fidelity",
        sentinel_agent: "Frontend Fidelity (loading state)",
        proposed_gate:  `Increase waitForFunction timeout or add a page-specific settled condition in the walkthrough spec`,
      });
    }

    // ── 3. Console error classification (text-only, no vision needed) ─────────
    const seriousErrors = console_errors.filter((e: string) =>
      !e.includes("Failed to fetch") &&
      !e.includes("net::ERR_") &&
      !e.includes("401") &&
      !e.includes("TypeError: Failed to fetch"),
    );

    if (seriousErrors.length > 0) {
      const errorPrompt = `Page: ${page_slug} (${page_file})
Console errors captured during Playwright test:
${seriousErrors.slice(0, 10).map((e: string, i: number) => `${i + 1}. ${e.slice(0, 300)}`).join("\n")}

Classify these errors against the 9 Sentinel Agent domains.`;

      const raw = await callAI(
        errorPrompt,
        { systemPrompt: TEXT_SYSTEM, temperature: 0.1, maxTokens: 512, jsonMode: true },
      );

      try {
        const parsed = JSON.parse(raw);
        if (parsed.issues?.length > 0) {
          findings.push(...parsed.issues.map((i: object) => ({ ...i, source: "console", page: page_slug })));
          modelUsed = modelUsed === "none" ? "text" : `${modelUsed}+text`;
        }
      } catch {
        console.warn(`[walkthrough-analyzer] failed to parse console result: ${raw.slice(0, 120)}`);
      }
    }

    return new Response(
      JSON.stringify({ findings, model_used: modelUsed }),
      { headers: { "Content-Type": "application/json", ...getCorsHeaders(req) } },
    );
  } catch (err) {
    console.error("[walkthrough-analyzer] error:", String(err));
    return new Response(
      JSON.stringify({ error: String(err) }),
      { status: 500, headers: { "Content-Type": "application/json", ...getCorsHeaders(req) } },
    );
  }
});
