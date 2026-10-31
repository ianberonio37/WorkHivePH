import { serveObserved, failTracked } from "../_shared/observability.ts";
import { tracedReply } from "../_shared/trace-reply.ts";  // LM-O: one trace id per request
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.110.0";
import { getCorsHeaders } from "../_shared/cors.ts";
// Pillar O (Observability): expose a /health probe for the gateway status page.
import { handleHealth } from "../_shared/health.ts";
import { log } from "../_shared/logger.ts";
// Pillar I (Gateway Spine): verify hive membership on the manual (browser) path.
import { resolveIdentity, resolveTenancy, requireServiceRole } from "../_shared/tenant-context.ts";
// A5 (FULLSTACK_COMPONENT_LIBRARY Layer A): per-person rate limit on the browser path.
import { checkSoloRateLimit, soloRateLimitKey, soloRateLimitedResponse } from "../_shared/rate-limit.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";
import { generateEmbeddingTagged } from "../_shared/embedding-chain.ts";

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

serveObserved("embed-entry", tracedReply("embed-entry", async (req, _trace) => {  // LM-O: one trace id per request; its model-call rows carry the id this reply returns
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

  const _logCtx = _trace;  // I6 observability, under the id this reply returns (tracedReply hands it in; R8: never a second id)
  log.info(_logCtx, "request_start", { method: req.method });

  try {
    // ★A CALLER'S MISTAKE IS NOT A SERVER ERROR (live-walk wave, 2026-09-06). tools/prove_edge_contract.mjs asked this
  // function with a broken JSON body and with GET; both reached `await req.json()` and came back 500, so a typo in a
  // client read as "the platform is broken". These are the same two guards every function that passed already had.
    if (req.method !== "POST") {
      return new Response(JSON.stringify({ error: "That action is not allowed here. Reload the page and try again." }),
        { status: 405, headers: { ...corsHeaders, "Content-Type": "application/json" } });
    }
    let body;
    try { body = await req.json(); } catch {
      return new Response(JSON.stringify({ error: "That request could not be read. Reload the page and try again." }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } });
    }

    const db = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    let type: string;
    let hive_id: string | null;
    let entry: Record<string, unknown>;

    // ── Auto-detect: Supabase DB webhook vs manual call ──────────────────────
    if (body.type === "INSERT" && body.record) {
      // ★The DB-webhook shape (INSERT + record) writes a RAG-index row keyed on the CALLER-SUPPLIED
      // record.hive_id on a service-role client, and this fn is deployed --no-verify-jwt. Without a gate,
      // an anon POST {type:"INSERT",table:"logbook",record:{hive_id:"<victim>",problem:…}} injects attacker
      // text into ANY hive's fault_knowledge/skill_knowledge/pm_knowledge — cross-tenant RAG poisoning that
      // the victim's AI companion then retrieves (a safety concern on a maintenance platform). Live-confirmed
      // reachable: an anon spoofed webhook reached the embed logic (skipped only by the content-length guard).
      // The only legit callers of this shape are internal (the embedding relay / DB triggers, which hold the
      // service-role key — the browser callers use the manual {type,hive_id,entry} shape below); require it.
      const _g = await requireServiceRole(db, req);
      if (!_g.ok) {
        return new Response(
          JSON.stringify({ error: _g.message, code: _g.code }),
          { status: _g.status, headers: { ...corsHeaders, "Content-Type": "application/json" } },
        );
      }
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
          // HS H4 (2026-10-30): the per-address ceiling is for callers who could mint identities from one address; a verified
          // member of this hive cannot, and on a plant's one connection it made the whole shift share five people's quota
          const _rl = await checkSoloRateLimit(db, soloRateLimitKey(authUid, _ip), undefined, undefined, (t.ok && !t.is_solo) ? null : _ip);
          if (!_rl.allowed) return soloRateLimitedResponse(corsHeaders, _rl.retry_after_seconds, _rl.scope);
        }
      } else {
        // ★No hive_id on the manual path is NOT a browser member call — every browser caller
        // (embedSkillEntry/embedFaultEntry/embedPMEntry/voice-handler) POSTs its own hive_id + a JWT.
        // The only legit no-hive caller is internal/service-role. Without this, an anon POST
        // {type:"fault",entry:{…}} passes straight to the embed — burning provider tokens and writing an
        // orphan RAG row — with no auth and no rate limit (both were nested in if(hive_id)). Live-confirmed.
        const _g = await requireServiceRole(db, req);
        if (!_g.ok) {
          return new Response(
            JSON.stringify({ error: _g.message, code: _g.code }),
            { status: _g.status, headers: { ...corsHeaders, "Content-Type": "application/json" } },
          );
        }
      }

      if (!type || !entry) {
        return new Response(
          JSON.stringify({ error: "Missing required fields: type, entry" }),
          { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
    }

    // The provider that ACTUALLY answered, recorded on the row. The column used to carry a DEFAULT of
    // 'nomic-embed-text-v1_5' while nothing wrote it, so every row claimed a model that is not even in the
    // chain — a label nobody was making. Migration 20260731000004 dropped that default; this states the truth.
    let _emb: { vector: number[]; provider: string } = { vector: [], provider: "" };
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
      embedding = (_emb = await generateEmbeddingTagged(text, undefined, { strict: true })).vector;
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
      // ★WHICH WORDS THE AI WROTE (LM-V walk, LM422, 2026-10-07). An entry the person saved after an AI path drafted
      // it (voice fill, photo defect capture, companion logbook.create) carries ai_assisted_fields: the fields the AI
      // filled that the person kept. The browser sends it inside `entry`; the DB-webhook / outbox shape carries it as a
      // column of the logbook `record`. Either way it lands on this row, narrowed to the fields THIS row holds, so the
      // RAG corpus can tell a model's draft from a technician's own words. source stays 'manual' - the person approved
      // the row - which keeps CHECK fault_knowledge_ai_provenance_pairing ((source LIKE 'ai\_%') = (ai_model IS NOT
      // NULL)) satisfied; 'ai_*' stays reserved for rows a model wrote alone (visual-defect-capture's analyze insert).
      // ABSENT, not [], when the caller did not say: the write is an upsert on logbook_id, and an older caller (or a
      // queued entry from before this field) must not erase a mark the row already carries.
      if (Array.isArray(entry.ai_assisted_fields)) {
        const FAULT_FIELDS = ["machine", "category", "problem", "root_cause", "action", "knowledge"];
        row.ai_assisted_fields = [...new Set((entry.ai_assisted_fields as unknown[])
          .filter((f): f is string => typeof f === "string" && FAULT_FIELDS.includes(f)))];
      }
    }

    // ── SKILL (from Skill Matrix save) ──────────────────────────────────────
    else if (type === "skill") {
      const text = [
        entry.worker_name   && `Technician: ${entry.worker_name}`,
        entry.discipline    && `Discipline: ${entry.discipline}`,
        entry.level         && `Skill level: ${entry.level} out of 5`,
        entry.primary_skill && `Primary expertise: ${entry.primary_skill}`,
      ].filter(Boolean).join(". ");

      embedding = (_emb = await generateEmbeddingTagged(text, undefined, { strict: true })).vector;
      table = "skill_knowledge";
      // UPSERT, not insert. Without a conflict key every re-embed APPENDED a row: skill_knowledge reached
      // 28 rows for 4 distinct (hive_id, worker_name, discipline) — ~86% duplicates, each stale copy
      // competing with the current one in every semantic search. Migration 20260731000003 de-duplicated and
      // added the matching unique index, so this key makes a re-embed REPLACE (the fault corpus has worked
      // this way since uidx 20260708000002, which is why it never grew duplicates).
      conflictKey = "hive_id,worker_name,discipline";
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
      embedding = (_emb = await generateEmbeddingTagged(text, undefined, { strict: true })).vector;
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

      embedding = (_emb = await generateEmbeddingTagged(text, undefined, { strict: true })).vector;
      table = "pm_knowledge";
      // UPSERT on the ASSET, because pm_knowledge is an asset-level summary (asset_name, category,
      // overdue_count, last_completed) rather than a per-completion record — 1,591 completions must
      // converge onto one row per asset, not 1,591 rows. Unique index added in 20260731000003.
      conflictKey = "hive_id,asset_id";
      // ★THE FIX THAT REACHED ONE OF TWO DOORS (2026-10-12, UFAI edge walk W4662). pm_knowledge.asset_id is an
      // asset_nodes.id FK, and the DB-webhook path above already maps the pm_ASSETS id it receives onto the node.
      // pm-scheduler's own embedPMEntry calls THIS path directly with entry.asset_id = the pm_assets id, which the
      // FK refused - "violates foreign key constraint pm_knowledge_asset_id_fkey", a 500 on every PM marked done, so
      // the PM side of the RAG index stopped growing. The same canonical read resolves it here; an id that is
      // already a node passes through unchanged.
      if (entry.asset_id) {
        const { data: _isNode } = await db.from("v_asset_truth").select("asset_id")
          .eq("asset_id", entry.asset_id).maybeSingle();
        if (!_isNode) {
          const { data: _node } = await db.from("v_asset_truth").select("asset_id")
            .eq("pm_asset_id", entry.asset_id).maybeSingle();
          entry.asset_id = _node?.asset_id || null;
        }
      }
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
    // STATE the provider that answered. The column previously took a DEFAULT while nothing wrote it, so
    // every row claimed 'nomic-embed-text-v1_5' — a model absent from the chain. A label nobody writes is a
    // label nobody can trust, and it sent today's investigation down the wrong path entirely.
    // bge-local reports as the self-host tag the ingest tools and the healing sweep already use, so all
    // three writers agree on one string for one space.
    row.embedding_model = _emb.provider === "bge-local" ? "bge-small-en-v1.5-local" : _emb.provider;

    // ★A NULL KEY NEVER CONFLICTS (2026-10-12, W4662). A PM asset with no linked asset node resolves to asset_id null,
    // and the (hive_id, asset_id) unique index treats every null as distinct - so each completion ADDED a summary row
    // for the same asset: 528 null-asset rows for 18 assets (about 29x), all competing in every PM retrieval. Such a
    // summary is keyed on the asset's name instead: the existing row is updated, never duplicated.
    let error = null as { message: string } | null;
    if (table === "pm_knowledge" && !row.asset_id) {
      // canonical-allow: a write-path dedupe lookup on the knowledge table itself (find this asset's existing summary
      // by name so it is updated, never duplicated); no KPI is read or rendered, so no canonical view applies.
      let q = db.from("pm_knowledge").select("id").eq("asset_name", row.asset_name).is("asset_id", null);
      q = row.hive_id ? q.eq("hive_id", row.hive_id) : q.is("hive_id", null);   // a solo summary has no hive
      const { data: same } = await q.order("updated_at", { ascending: false }).limit(1);
      if (same && same.length) {
        const { error: updErr } = await db.from("pm_knowledge").update(row).eq("id", same[0].id);
        error = updErr;
      } else {
        const { error: insErr } = await db.from("pm_knowledge").insert(row);
        error = insErr;
      }
    } else if (conflictKey) {
      const { error: upsErr } = await db.from(table).upsert(row, { onConflict: conflictKey });
      error = upsErr;
    } else {
      const { error: insErr } = await db.from(table).insert(row);
      error = insErr;
    }

    if (error) {
      console.error(`DB insert error (${table}):`, error.message);
      return new Response(
        JSON.stringify({ error: "Could not save this entry. Try again in a moment." }),
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
}));
