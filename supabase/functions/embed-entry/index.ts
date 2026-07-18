import { serveObserved, failTracked } from "../_shared/observability.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { getCorsHeaders } from "../_shared/cors.ts";
// Pillar O (Observability): expose a /health probe for the gateway status page.
import { handleHealth } from "../_shared/health.ts";
import { log } from "../_shared/logger.ts";
// Pillar I (Gateway Spine): verify hive membership on the manual (browser) path.
import { resolveIdentity, resolveTenancy } from "../_shared/tenant-context.ts";
// A5 (FULLSTACK_COMPONENT_LIBRARY Layer A): per-person rate limit on the browser path.
import { checkSoloRateLimit, soloRateLimitKey, soloRateLimitedResponse } from "../_shared/rate-limit.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
import { generateEmbedding } from "../_shared/embedding-chain.ts";

// Warm module-scope Supabase client. Reused across request invocations
// in the same warm container. Per-request createClient calls below are
// being phased out (PRODUCTION_FIXES #46). Falls back to an empty
// client if env is missing so module import never throws.
const _WH_SUPABASE_URL_M = Deno.env.get("SUPABASE_URL") || "";
const _WH_SERVICE_KEY_M  = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const _whWarmClient = _WH_SUPABASE_URL_M && _WH_SERVICE_KEY_M
  ? createClient(_WH_SUPABASE_URL_M, _WH_SERVICE_KEY_M)
  : null;
void _whWarmClient;

// ── Entry point ───────────────────────────────────────────────────────────────

serveObserved("embed-entry", async (req) => {
  const corsHeaders = getCorsHeaders(req);
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  // Pillar O: /health probe (short-circuits before auth/body parsing).
  const healthResp = await handleHealth(req, "embed-entry", async () => ({
    deps: [
      { name: "supabase",  ok: Boolean(Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) },
      { name: "embedding", ok: Boolean(Deno.env.get("VOYAGE_API_KEY") || Deno.env.get("JINA_API_KEY") || Deno.env.get("GEMINI_API_KEY") || Deno.env.get("BGE_EMBED_URL")) },
    ],
  }));
  if (healthResp) return healthResp;

  const _logCtx = beginRequest(req, { route: "embed-entry" });
  log.info(_logCtx, "request_start", { method: req.method });

  try {
    const body = await req.json();

    const db = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    let type: string;
    let hive_id: string | null;
    let entry: Record<string, unknown>;

    // ── Auto-detect: Supabase DB webhook vs manual call ──────────────────────
    if (body.type === "INSERT" && body.record) {
      const record = body.record;

      if (body.table === "logbook") {
        type = "fault";
        hive_id = record.hive_id || null;
        entry = record;

      } else if (body.table === "skill_badges") {
        type = "skill";
        hive_id = record.hive_id || null;
        entry = record;

      } else if (body.table === "pm_completions") {
        type = "pm";
        // Canonical: pm_compliance_truth (pm_asset_id keyed).
        const { data: asset } = await db.from("v_pm_compliance_truth")
          .select("asset_name, category, hive_id")
          .eq("pm_asset_id", record.asset_id)
          .single();
        hive_id = asset?.hive_id || null;
        // pm_knowledge.asset_id is an asset_nodes.id FK, but record.asset_id is a pm_ASSETS id.
        // Passing it straight through violated pm_knowledge_asset_id_fkey → EVERY pm_completions
        // embed 500'd and pm_knowledge sat at 0 rows despite 1500+ completions (silent RAG starve).
        // Resolve the canonical node id via v_asset_truth (asset_id = asset_nodes.id, keyed by
        // pm_asset_id) — the canonical read path, not a raw asset_nodes read; null-safe fallback.
        const { data: node } = await db.from("v_asset_truth")
          .select("asset_id")
          .eq("pm_asset_id", record.asset_id)
          .maybeSingle();
        entry = {
          asset_id:       node?.asset_id || null,   // asset_nodes.id via v_asset_truth (was pm_assets.id → FK violation)
          asset_name:     asset?.asset_name || "Unknown",
          category:       asset?.category   || "Unknown",
          overdue_count:  0,
          last_completed: record.completed_at,
        };

      } else {
        // Table not handled: skip silently (don't error)
        return new Response(
          JSON.stringify({ skipped: true, reason: `Table ${body.table} not handled` }),
          { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

    } else {
      // ── Manual call format (existing API contract unchanged) ──────────────
      type    = body.type;
      hive_id = body.hive_id;
      entry   = body.entry;

      // Pillar I: the manual (browser) path scopes the embed write by the client
      // hive_id on a service-role client — verify membership. The DB-webhook
      // branch above is service-role/internal; service-role callers skip.
      if (hive_id) {
        const { authUid, isServiceRole } = await resolveIdentity(db, req);
        if (!isServiceRole) {
          const t = await resolveTenancy(db, authUid, hive_id);
          if (!t.ok) {
            return new Response(
              JSON.stringify({ error: t.message, code: t.code }),
              { status: t.status, headers: { ...corsHeaders, "Content-Type": "application/json" } },
            );
          }
          // A5: rate-limit the browser path (webhook/service-role internal path skips —
          // same placement as voice-model-call, the reference adopter).
          const _ip = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim();
          const _rl = await checkSoloRateLimit(db, soloRateLimitKey(authUid, _ip), undefined, undefined, _ip);
          if (!_rl.allowed) return soloRateLimitedResponse(corsHeaders);
        }
      }

      if (!type || !entry) {
        return new Response(
          JSON.stringify({ error: "Missing required fields: type, entry" }),
          { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
    }

    let embedding: number[];
    let table: string;
    let row: Record<string, unknown>;
    // When set, the write UPSERTs on this column instead of INSERTing, so a re-embed
    // (a logbook edit-in-place re-calls this fn) REPLACES the source's embedding rather
    // than adding a stale duplicate to the RAG index (ARC DI §10.5 embedding seesaw).
    let conflictKey: string | null = null;

    // ── FAULT (from Logbook save) ────────────────────────────────────────────
    if (type === "fault") {
      // Combine the most meaningful fields into one searchable string
      const text = [
        entry.machine       && `Equipment: ${entry.machine}`,
        entry.problem       && `Problem: ${entry.problem}`,
        entry.root_cause    && `Root cause: ${entry.root_cause}`,
        entry.action        && `Action taken: ${entry.action}`,
        entry.knowledge     && `Lesson learned: ${entry.knowledge}`,
        entry.category      && `Category: ${entry.category}`,
      ].filter(Boolean).join(". ");

      // Content quality guard: skip near-empty entries that would create useless embeddings
      if (text.trim().length < 50) {
        console.warn('embed-entry: skipping near-empty fault entry (' + text.length + ' chars) — insufficient context for semantic retrieval');
        return new Response(JSON.stringify({ skipped: true, reason: 'insufficient_content', text_length: text.length }), { status: 200, headers: { ...corsHeaders, 'Content-Type': 'application/json' } });
      }
      embedding = await generateEmbedding(text);
      table = "fault_knowledge";
      conflictKey = "logbook_id";   // re-embed on edit REPLACES (uidx 20260708000002), no dup
      row = {
        hive_id:     hive_id || null,
        logbook_id:  entry.id || null,
        machine:     entry.machine || null,
        category:    entry.category || null,
        problem:     entry.problem || null,
        root_cause:  entry.root_cause || null,
        action:      entry.action || null,
        knowledge:   entry.knowledge || null,
        worker_name: entry.worker_name || null,
        embedding,
      };
    }

    // ── SKILL (from Skill Matrix save) ──────────────────────────────────────
    else if (type === "skill") {
      const text = [
        entry.worker_name   && `Technician: ${entry.worker_name}`,
        entry.discipline    && `Discipline: ${entry.discipline}`,
        entry.level         && `Skill level: ${entry.level} out of 5`,
        entry.primary_skill && `Primary expertise: ${entry.primary_skill}`,
      ].filter(Boolean).join(". ");

      embedding = await generateEmbedding(text);
      table = "skill_knowledge";
      row = {
        hive_id:       hive_id || null,
        worker_name:   entry.worker_name || null,
        discipline:    entry.discipline || null,
        level:         entry.level || null,
        primary_skill: entry.primary_skill || null,
        embedding,
        updated_at:    new Date().toISOString(),
      };
    }

    // ── PROJECT_LESSON / PROJECT_ITEM / PROJECT_DESCRIPTION (Phase 6.5) ─────
    else if (type === "project_lesson" || type === "project_item" || type === "project_description") {
      const text = type === "project_lesson"
        ? `Lessons from ${entry.project_code}: ${entry.lessons_text || ""}`
        : type === "project_item"
        ? `Project ${entry.project_code} (${entry.project_type}) scope item: ${entry.title || ""}${entry.notes ? `. Notes: ${entry.notes}` : ""}`
        : `Project ${entry.project_code} (${entry.project_type}) — ${entry.name || ""}: ${entry.description || ""}`;

      if (text.trim().length < 30) {
        return new Response(JSON.stringify({ skipped: true, reason: "insufficient_content", text_length: text.length }),
          { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } });
      }
      embedding = await generateEmbedding(text);
      table = "project_knowledge";
      row = {
        hive_id:      hive_id || null,
        project_id:   entry.project_id || null,
        source_type:  type,
        source_id:    entry.source_id || null,
        project_code: entry.project_code || null,
        project_type: entry.project_type || null,
        discipline:   entry.discipline || null,
        text_chunk:   text.slice(0, 2000),
        embedding,
      };
    }

    // ── PM HEALTH (from PM Scheduler save) ──────────────────────────────────
    else if (type === "pm") {
      const overdueText = entry.overdue_count > 0
        ? `${entry.overdue_count} overdue PM tasks`
        : "all PM tasks up to date";

      const lastText = entry.last_completed
        ? `Last PM completed: ${new Date(entry.last_completed).toLocaleDateString()}`
        : "no PM completions recorded";

      const healthSummary = `${overdueText}. ${lastText}.`;

      const text = [
        entry.asset_name && `Asset: ${entry.asset_name}`,
        entry.category   && `Category: ${entry.category}`,
        healthSummary,
      ].filter(Boolean).join(". ");

      embedding = await generateEmbedding(text);
      table = "pm_knowledge";
      row = {
        hive_id:        hive_id || null,
        asset_id:       entry.asset_id || null,
        asset_name:     entry.asset_name || null,
        category:       entry.category || null,
        overdue_count:  entry.overdue_count || 0,
        last_completed: entry.last_completed || null,
        health_summary: healthSummary,
        embedding,
        updated_at:     new Date().toISOString(),
      };
    }

    else {
      return new Response(
        JSON.stringify({ error: `Unknown type: ${type}. Use "fault", "skill", or "pm".` }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // ── Save to the correct knowledge table ──────────────────────────────────
    // UPSERT on the source key (fault: logbook_id) so a re-embed on edit REPLACES the
    // prior embedding instead of adding a stale duplicate; INSERT for types with no
    // source-unique key yet.
    const { error } = conflictKey
      ? await db.from(table).upsert(row, { onConflict: conflictKey })
      : await db.from(table).insert(row);

    if (error) {
      console.error(`DB insert error (${table}):`, error.message);
      return new Response(
        JSON.stringify({ error: error.message }),
        { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    return new Response(
      JSON.stringify({ success: true, type, table }),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );

  } catch (err) {
    // T2b: aggregate this HANDLED failure to wh_traces + non-leaky 500.
    return await failTracked(req, "embed-entry", "embed_entry_error", err);
  }
});
