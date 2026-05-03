import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";
import { callAI } from "../_shared/ai-chain.ts";
import { getCorsHeaders } from "../_shared/cors.ts";

function callGroq(prompt: string, systemPrompt: string): Promise<string> {
  return callAI(prompt, { systemPrompt, temperature: 0.2, maxTokens: 1024, jsonMode: true });
}

// ── AGENT 1: Failure Analysis ─────────────────────────────────────────────────
// Reads logbook: surfaces top risk machines, repeat failures, MTBF alerts

const FAILURE_SYSTEM = `You are a maintenance failure analyst. Analyze logbook records and identify:
1. Top 3 highest-risk machines (most failures or longest downtime)
2. Repeat failure patterns (same root cause on same machine 2+ times)
3. Machines with MTBF under 14 days (failures less than 2 weeks apart)
Respond only in JSON: { "risks": [{"machine","failure_count","total_downtime_h","reason"}], "patterns": [{"machine","root_cause","occurrences"}], "mtbf_alerts": [{"machine","avg_days_between_failures"}] }`;

async function failureAnalysisAgent(db: SupabaseClient, hiveId: string | null, workerName: string | null) {
  const query = db.from("logbook")
    .select("machine, maintenance_type, category, root_cause, downtime_hours, status, created_at")
    .eq("maintenance_type", "Breakdown / Corrective")
    .order("created_at", { ascending: false })
    .limit(200);

  if (hiveId) query.eq("hive_id", hiveId);
  else if (workerName) query.eq("worker_name", workerName);

  const { data } = await query;
  if (!data?.length) return { agent: "failure_analysis", result: null };

  const summary = data.map(e =>
    `${e.machine}|${e.category}|${e.root_cause || "unknown"}|${e.downtime_hours || 0}h|${e.created_at?.slice(0, 10)}`
  ).join("\n");

  const raw = await callGroq(`Logbook records (machine|category|root_cause|downtime|date):\n${summary}`, FAILURE_SYSTEM);
  return { agent: "failure_analysis", result: JSON.parse(raw) };
}

// ── AGENT 2: PM Status ────────────────────────────────────────────────────────
// Reads pm_assets + pm_completions: overdue tasks, health per asset

const PM_SYSTEM = `You are a preventive maintenance analyst. Given a list of assets and their PM completion history, identify:
1. Assets with overdue PM tasks (no completion in over 30 days)
2. Assets with zero PM history (never had a PM done)
3. Overall PM health score (0-100)
Respond only in JSON: { "overdue": [{"asset_name","days_since_last_pm","risk_level"}], "never_done": ["asset_name"], "health_score": number, "summary": "one sentence" }`;

async function pmStatusAgent(db: SupabaseClient, hiveId: string | null, workerName: string | null) {
  const assetQuery = db.from("pm_assets").select("id, asset_name, category");
  if (hiveId) assetQuery.eq("hive_id", hiveId);
  else if (workerName) assetQuery.eq("worker_name", workerName);

  const { data: assets } = await assetQuery;
  if (!assets?.length) return { agent: "pm_status", result: null };

  const assetIds = assets.map(a => a.id);
  const { data: completions } = await db.from("pm_completions")
    .select("asset_id, completed_at")
    .in("asset_id", assetIds)
    .order("completed_at", { ascending: false });

  // Build last-completion map per asset
  const lastDone: Record<string, string> = {};
  (completions || []).forEach(c => {
    if (!lastDone[c.asset_id]) lastDone[c.asset_id] = c.completed_at;
  });

  const now = Date.now();
  const summary = assets.map(a => {
    const last = lastDone[a.id];
    const days = last ? Math.floor((now - new Date(last).getTime()) / 86400000) : 999;
    return `${a.asset_name}|${a.category}|${last ? `${days} days ago` : "never"}`;
  }).join("\n");

  const raw = await callGroq(`Assets (name|category|last_pm):\n${summary}`, PM_SYSTEM);
  return { agent: "pm_status", result: JSON.parse(raw) };
}

// ── AGENT 3: Inventory Risk ───────────────────────────────────────────────────
// Reads inventory_items: parts below reorder point

const INVENTORY_SYSTEM = `You are an inventory risk analyst. Given parts stock levels, identify:
1. Parts that are out of stock (qty = 0)
2. Parts below reorder threshold (qty <= reorder_point)
3. Critical risk if any of these parts are needed for upcoming PM tasks
Respond only in JSON: { "out_of_stock": ["part_name"], "low_stock": [{"part_name","qty_on_hand","reorder_point"}], "risk_summary": "one sentence" }`;

async function inventoryRiskAgent(db: SupabaseClient, hiveId: string | null, workerName: string | null) {
  const query = db.from("inventory_items")
    .select("part_name, qty_on_hand, reorder_point, bin_location")
    .limit(200);

  if (hiveId) query.eq("hive_id", hiveId);
  else if (workerName) query.eq("worker_name", workerName);

  const { data } = await query;
  if (!data?.length) return { agent: "inventory_risk", result: null };

  const summary = data.map(i =>
    `${i.part_name}|qty:${i.qty_on_hand}|reorder_at:${i.reorder_point ?? "not set"}`
  ).join("\n");

  const raw = await callGroq(`Parts inventory (name|qty|reorder_point):\n${summary}`, INVENTORY_SYSTEM);
  return { agent: "inventory_risk", result: JSON.parse(raw) };
}

// ── AGENT 4: Knowledge Extraction ────────────────────────────────────────────
// Reads logbook.knowledge: clusters tips into SOP drafts

const KNOWLEDGE_SYSTEM = `You are a knowledge management specialist. Given maintenance knowledge notes from technicians, identify:
1. Recurring tips about the same machine or failure type (cluster them)
2. Most valuable lessons that should become SOPs
3. Machines where knowledge is missing (no lessons captured)
Respond only in JSON: { "clusters": [{"topic","tips":["tip1","tip2"],"sop_candidate":true}], "missing_knowledge": ["machine_name"], "top_insight": "most important lesson learned" }`;

async function knowledgeExtractionAgent(db: SupabaseClient, hiveId: string | null, workerName: string | null) {
  const query = db.from("logbook")
    .select("machine, category, root_cause, knowledge")
    .not("knowledge", "is", null)
    .limit(100);

  if (hiveId) query.eq("hive_id", hiveId);
  else if (workerName) query.eq("worker_name", workerName);

  const { data } = await query;
  if (!data?.length) return { agent: "knowledge_extraction", result: null };

  const summary = data
    .filter(e => e.knowledge?.trim())
    .map(e => `${e.machine}|${e.category}|${e.knowledge}`)
    .join("\n");

  const raw = await callGroq(`Knowledge notes (machine|category|lesson):\n${summary}`, KNOWLEDGE_SYSTEM);
  return { agent: "knowledge_extraction", result: JSON.parse(raw) };
}

// ── AGENT 5: Workforce Match ──────────────────────────────────────────────────
// Reads skill_profiles + skill_badges: best tech for the job

const WORKFORCE_SYSTEM = `You are a workforce scheduler. Given technician skill profiles and a maintenance question, identify:
1. Best-matched technician(s) for the task (by discipline and level)
2. Any skill gaps (task requires expertise no one has)
3. Recommended assignment with reasoning
Respond only in JSON: { "best_match": [{"worker_name","discipline","level","reason"}], "skill_gaps": ["missing_skill"], "recommendation": "one sentence" }`;

async function workforceMatchAgent(db: SupabaseClient, hiveId: string | null, workerName: string | null, question: string) {
  const query = db.from("skill_badges")
    .select("worker_name, discipline, level")
    .order("level", { ascending: false })
    .limit(100);

  if (hiveId) query.eq("hive_id", hiveId);

  const { data: badges } = await query;
  if (!badges?.length) return { agent: "workforce_match", result: null };

  const summary = badges.map(b => `${b.worker_name}|${b.discipline}|Level ${b.level}`).join("\n");

  const raw = await callGroq(
    `Question: ${question}\n\nTechnician skills (worker|discipline|level):\n${summary}`,
    WORKFORCE_SYSTEM
  );
  return { agent: "workforce_match", result: JSON.parse(raw) };
}

// ── AGENT 6: Shift Handover ───────────────────────────────────────────────────
// Reads logbook last 24h: open jobs + completed work summary

const HANDOVER_SYSTEM = `You are a shift handover report generator. Given recent maintenance records, produce:
1. Open jobs that the next shift must follow up on
2. Work completed this shift
3. Critical alerts the next shift must know immediately
Respond only in JSON: { "open_jobs": [{"machine","problem","priority":"HIGH|MEDIUM|LOW"}], "completed": [{"machine","action"}], "critical_alerts": ["alert text"], "handover_note": "one paragraph summary" }`;

async function shiftHandoverAgent(db: SupabaseClient, hiveId: string | null, workerName: string | null) {
  const since = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();

  const query = db.from("logbook")
    .select("machine, category, problem, action, status, created_at, worker_name")
    .gte("created_at", since)
    .order("created_at", { ascending: false })
    .limit(50);

  if (hiveId) query.eq("hive_id", hiveId);
  else if (workerName) query.eq("worker_name", workerName);

  const { data } = await query;
  if (!data?.length) return { agent: "shift_handover", result: null };

  const summary = data.map(e =>
    `${e.machine}|${e.category}|${e.status}|${e.problem || ""}|${e.action || ""}|by ${e.worker_name}`
  ).join("\n");

  const raw = await callGroq(`Last 24h records (machine|category|status|problem|action|worker):\n${summary}`, HANDOVER_SYSTEM);
  return { agent: "shift_handover", result: JSON.parse(raw) };
}

// ── AGENT 7: Predictive ───────────────────────────────────────────────────────
// Reads logbook failure dates: projects next failure per machine

const PREDICTIVE_SYSTEM = `You are a predictive maintenance analyst. Given machine failure history with dates, calculate:
1. Average days between failures (MTBF) per machine
2. Predicted next failure date based on MTBF
3. Risk level: HIGH (overdue), MEDIUM (due within 7 days), LOW (more than 7 days away)
Respond only in JSON: { "predictions": [{"machine","mtbf_days":number,"last_failure":"YYYY-MM-DD","predicted_next":"YYYY-MM-DD","risk":"HIGH|MEDIUM|LOW"}] }`;

async function predictiveAgent(db: SupabaseClient, hiveId: string | null, workerName: string | null) {
  const query = db.from("logbook")
    .select("machine, created_at")
    .eq("maintenance_type", "Breakdown / Corrective")
    .order("machine", { ascending: true })
    .order("created_at", { ascending: true })
    .limit(200);

  if (hiveId) query.eq("hive_id", hiveId);
  else if (workerName) query.eq("worker_name", workerName);

  const { data } = await query;
  if (!data?.length) return { agent: "predictive", result: null };

  const summary = data.map(e => `${e.machine}|${e.created_at?.slice(0, 10)}`).join("\n");
  const today = new Date().toISOString().slice(0, 10);

  const raw = await callGroq(
    `Today: ${today}\nFailure history (machine|date):\n${summary}`,
    PREDICTIVE_SYSTEM
  );
  return { agent: "predictive", result: JSON.parse(raw) };
}

// ── ORCHESTRATOR: decides which agents to run, synthesizes answer ─────────────

const ROUTE_SYSTEM = `You are a maintenance intelligence router. Given a user question, decide which agents to run.
Respond only in JSON: { "agents": ["failure_analysis","pm_status","inventory_risk","knowledge_extraction","workforce_match","shift_handover","predictive"] }
Include only the agents relevant to the question. Use at least 1 and at most 4 agents.`;

const SYNTH_SYSTEM = `You are a senior maintenance manager AI. Given agent results, write a clear, practical answer to the user's question.
Be specific: name actual machines, workers, parts. Use bullet points for lists. Keep it under 200 words.
Respond only in JSON: { "answer": "your response here" }`;

async function orchestrate(question: string, hiveId: string | null, workerName: string | null, db: SupabaseClient) {

  // Step 1: Route: decide which agents to call
  const routeRaw = await callGroq(`Question: "${question}"`, ROUTE_SYSTEM);
  let agentsToRun: string[] = [];
  try {
    agentsToRun = JSON.parse(routeRaw).agents || ["failure_analysis"];
  } catch {
    agentsToRun = ["failure_analysis"];
  }

  // Step 2: Run selected agents in parallel
  const agentMap: Record<string, () => Promise<Record<string, unknown>>> = {
    failure_analysis:    () => failureAnalysisAgent(db, hiveId, workerName),
    pm_status:           () => pmStatusAgent(db, hiveId, workerName),
    inventory_risk:      () => inventoryRiskAgent(db, hiveId, workerName),
    knowledge_extraction:() => knowledgeExtractionAgent(db, hiveId, workerName),
    workforce_match:     () => workforceMatchAgent(db, hiveId, workerName, question),
    shift_handover:      () => shiftHandoverAgent(db, hiveId, workerName),
    predictive:          () => predictiveAgent(db, hiveId, workerName),
  };

  const results = await Promise.allSettled(
    agentsToRun.map(name => agentMap[name]?.() ?? Promise.resolve({ agent: name, result: null }))
  );

  const successfulResults = results
    .filter(r => r.status === "fulfilled" && r.value?.result)
    .map(r => (r as PromiseFulfilledResult<Record<string, unknown>>).value);

  if (!successfulResults.length) {
    return { answer: "I couldn't find enough data to answer that yet. Add more logbook entries, PM completions, or skill badges to build up your knowledge base.", agents_used: agentsToRun };
  }

  // Step 3: Fetch semantic context from knowledge base (RAG)
  let semanticContext = "";
  try {
    const searchRes = await fetch(
      `${Deno.env.get("SUPABASE_URL")}/functions/v1/semantic-search`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")}`,
        },
        body: JSON.stringify({ query: question, hive_id: hiveId, match_count: 3 }),
      }
    );
    if (searchRes.ok) {
      const searchData = await searchRes.json();
      semanticContext = searchData.context || "";
    }
  } catch { /* non-blocking: synthesis continues even if search fails */ }

  // Step 4: Synthesize: one final AI call to write the answer
  const resultsText = successfulResults.map(r =>
    `[${r.agent}]: ${JSON.stringify(r.result)}`
  ).join("\n\n");

  const synthPrompt = semanticContext
    ? `User question: "${question}"\n\nRelevant history from knowledge base:\n${semanticContext}\n\nAgent results:\n${resultsText}`
    : `User question: "${question}"\n\nAgent results:\n${resultsText}`;

  const synthRaw = await callGroq(synthPrompt, SYNTH_SYSTEM);

  let answer: string = "I analyzed your data but had trouble formatting the response. Please try again.";
  try {
    const parsed = JSON.parse(synthRaw).answer;
    if (typeof parsed === "string") {
      answer = parsed;
    } else if (parsed && typeof parsed === "object") {
      // LLM returned a structured object instead of a prose string. Format it
      // as readable markdown-ish bullets so the chat UI can render it.
      answer = formatStructuredAnswer(parsed);
    }
  } catch { /* use fallback */ }

  return { answer, agents_used: agentsToRun, raw_results: successfulResults };
}

// Coerce a structured object response into readable text. Keys become bold
// headings; arrays become bullet lists; primitives become "key: value".
function formatStructuredAnswer(obj: Record<string, unknown>, depth = 0): string {
  const lines: string[] = [];
  const indent = "  ".repeat(depth);
  for (const [key, value] of Object.entries(obj)) {
    const heading = key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    if (Array.isArray(value)) {
      if (!value.length) continue;
      lines.push(`${indent}**${heading}:**`);
      for (const item of value) {
        if (item && typeof item === "object") {
          const parts = Object.entries(item).map(([k, v]) => `${k}: ${v}`).join(", ");
          lines.push(`${indent}- ${parts}`);
        } else {
          lines.push(`${indent}- ${item}`);
        }
      }
    } else if (value && typeof value === "object") {
      lines.push(`${indent}**${heading}:**`);
      lines.push(formatStructuredAnswer(value as Record<string, unknown>, depth + 1));
    } else if (value !== null && value !== undefined) {
      lines.push(`${indent}**${heading}:** ${value}`);
    }
  }
  return lines.join("\n");
}

// ── Entry point ───────────────────────────────────────────────────────────────

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const { question, hive_id, worker_name } = await req.json();

    if (!question) {
      return new Response(
        JSON.stringify({ error: "Missing required field: question" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const db = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    const result = await orchestrate(question, hive_id || null, worker_name || null, db);

    return new Response(
      JSON.stringify(result),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );

  } catch (err) {
    console.error("ai-orchestrator error:", err);
    return new Response(
      JSON.stringify({ error: err instanceof Error ? err.message : String(err) }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
