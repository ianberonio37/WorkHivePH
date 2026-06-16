// _shared/tenant-context.ts
// The Gateway's IDENTITY + TENANCY resolver — Pillar I of the Full-Stack SaaS
// Gateway (FULLSTACK_SAAS_GATEWAY_ROADMAP.md). The control-plane step that
// answers, SERVER-SIDE: "who is this caller, which hive may they act in, and
// what is their role there?" — never trusting a client-supplied hive_id.
//
// WHY THIS EXISTS (the consolidation):
//   The proven membership-verification pattern was COPY-PASTED across edge fns
//   (analytics-orchestrator `resolveUserId` + the v_worker_truth active-member
//   read; export-hive-data `checkSupervisor`; the worker_profiles solo
//   fallback). `platform-gateway` is the one front door that SKIPPED it — it
//   authenticated the user but then trusted `body.hive_id` from the client for
//   rate-limit, audit, and downstream forwarding. A signed-in worker could pass
//   ANY hive_id. This module makes the verified pattern the single source of
//   truth so the hole cannot reopen per-function.
//
// SOURCE OF TRUTH: `v_worker_truth` (canonical identity view) —
//   (auth_uid, worker_name, hive_id, role, hive_status, is_solo). A row exists
//   only for an ACTIVE membership, so "row present" == "verified member".
//
// Usage (inside an edge fn or the gateway):
//   import { resolveIdentity, resolveTenancy } from "../_shared/tenant-context.ts";
//   const id = await resolveIdentity(db, req);
//   if (!id.isServiceRole) {
//     const t = await resolveTenancy(db, id.authUid, body.hive_id);
//     if (!t.ok) return fail(ctx, t.code, t.message, { status: t.status });
//     // From here use t.hive_id / t.role / t.worker_name — the VERIFIED values,
//     // never the client's body.hive_id / body.worker_name.
//   }
//
// Service-role callers (internal cron, gateway->fn forward with the
// SUPABASE_SERVICE_ROLE_KEY) are trusted and skip tenancy enforcement — they
// are not a browser client and cannot be a spoofing vector.

import { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";

// ── Types ──────────────────────────────────────────────────────────────────

export interface Identity {
  /** The authenticated user's id, or null when unauthenticated. */
  authUid:       string | null;
  /** True when the bearer equals the service-role key (trusted internal call). */
  isServiceRole: boolean;
  /** The raw bearer token (empty string when absent). */
  bearer:        string;
}

export interface TenancyOk {
  ok:          true;
  /** VERIFIED hive id (null = solo / hiveless caller). Use this, not body.hive_id. */
  hive_id:     string | null;
  /** Membership role in this hive (e.g. "supervisor" | "worker"); null when solo. */
  role:        string | null;
  /** Server-resolved display name. Never the client-supplied worker_name. */
  worker_name: string;
  /** True when the caller has no active hive membership. */
  is_solo:     boolean;
}

export interface TenancyDenied {
  ok:      false;
  /** HTTP status the caller should return (401 unauth, 403 not-a-member). */
  status:  number;
  /** Stable machine-readable code for the envelope error. */
  code:    string;
  message: string;
}

export type Tenancy = TenancyOk | TenancyDenied;

// ── Identity ─────────────────────────────────────────────────────────────────

/** Pull the bearer token from the Authorization header (case-insensitive). */
export function extractBearer(req: Request): string {
  const h = req.headers.get("authorization") || req.headers.get("Authorization") || "";
  return h.toLowerCase().startsWith("bearer ") ? h.slice(7).trim() : "";
}

/** True when the bearer is the project service-role key (a trusted internal call). */
export function isServiceRoleBearer(bearer: string): boolean {
  const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
  return Boolean(bearer) && Boolean(key) && bearer === key;
}

/** Resolve the caller's identity: service-role detection + auth_uid from the JWT.
 *  Mirrors analytics-orchestrator `resolveUserId` (now consolidated here). */
export async function resolveIdentity(db: SupabaseClient, req: Request): Promise<Identity> {
  const bearer = extractBearer(req);
  if (isServiceRoleBearer(bearer)) {
    return { authUid: null, isServiceRole: true, bearer };
  }
  let authUid: string | null = null;
  if (bearer) {
    try {
      const { data: { user } } = await db.auth.getUser(bearer);
      authUid = user?.id || null;
    } catch {
      authUid = null;
    }
  }
  return { authUid, isServiceRole: false, bearer };
}

// ── Tenancy ──────────────────────────────────────────────────────────────────

/** Verify that `authUid` is an ACTIVE member of `hiveId` and return the verified
 *  tenant context. When `hiveId` is empty/null the caller is treated as solo and
 *  resolved from worker_profiles (the identity anchor for every user).
 *
 *  Returns a typed denial (401/403) instead of throwing, so the caller maps it
 *  straight onto the response envelope.
 */
export async function resolveTenancy(
  db:      SupabaseClient,
  authUid: string | null,
  hiveId:  string | null | undefined,
): Promise<Tenancy> {
  if (!authUid) {
    return { ok: false, status: 401, code: "auth_required", message: "Sign-in required." };
  }

  const hid = (hiveId ?? "").trim();

  if (hid) {
    // canonical-allow: v_worker_truth is the canonical hive-scoped identity view;
    // a row exists only for an active membership, so presence == verified member.
    const { data: mem } = await db.from("v_worker_truth")
      .select("worker_name, role, hive_status")
      .eq("auth_uid", authUid)
      .eq("hive_id", hid)
      .eq("hive_status", "active")
      .maybeSingle();
    if (!mem) {
      return {
        ok:      false,
        status:  403,
        code:    "not_a_member",
        message: "Caller is not an active member of this hive.",
      };
    }
    return {
      ok:          true,
      hive_id:     hid,
      role:        mem.role ?? null,
      worker_name: mem.worker_name || "anonymous",
      is_solo:     false,
    };
  }

  // Solo / hiveless caller. v_worker_truth is hive-scoped (a hiveless user has no
  // row), so worker_profiles is the only source that resolves their own name.
  // canonical-allow: worker_profiles is the identity anchor for EVERY user.
  const { data: prof } = await db.from("worker_profiles")
    .select("display_name")
    .eq("auth_uid", authUid)
    .maybeSingle();
  if (!prof?.display_name) {
    return { ok: false, status: 403, code: "no_profile", message: "No worker profile for caller." };
  }
  return {
    ok:          true,
    hive_id:     null,
    role:        null,
    worker_name: prof.display_name,
    is_solo:     true,
  };
}

/** Convenience: resolve identity then tenancy in one call. Service-role callers
 *  short-circuit to a trusted solo context bound to the supplied hive_id (they
 *  are internal and already privileged). */
export async function resolveContext(
  db:   SupabaseClient,
  req:  Request,
  opts: { hiveId?: string | null } = {},
): Promise<{ identity: Identity; tenancy: Tenancy }> {
  const identity = await resolveIdentity(db, req);
  if (identity.isServiceRole) {
    const hid = (opts.hiveId ?? "").trim() || null;
    return {
      identity,
      tenancy: { ok: true, hive_id: hid, role: "service", worker_name: "service", is_solo: hid === null },
    };
  }
  const tenancy = await resolveTenancy(db, identity.authUid, opts.hiveId ?? null);
  return { identity, tenancy };
}

// ── Machine ingest gate ──────────────────────────────────────────────────────

/** Gate for MACHINE-ingest endpoints (MQTT/OPC-UA/CMMS bridges) that scope writes
 *  by a client-supplied hive_id but have no `auth_uid` to membership-check. Only
 *  a TRUSTED caller may write: today that means the service-role key (an internal
 *  fn or a server-side bridge proxy). A browser/anon caller — the cross-tenant
 *  injection vector — is rejected (401).
 *
 *  FOLLOW-UP (integration-engineer): the device-facing path is a per-hive ingest
 *  KEY (a scoped credential a plant operator provisions/rotates), so a bridge
 *  needn't hold the all-powerful service key. That needs a provisioning design
 *  (where the key is shown/rotated) — a product decision, tracked separately.
 *  When built, accept `(isServiceRole || validIngestKey(hiveId, header))` here. */
export async function requireServiceRole(
  db:  SupabaseClient,
  req: Request,
): Promise<{ ok: true } | { ok: false; status: number; code: string; message: string }> {
  const id = await resolveIdentity(db, req);
  if (id.isServiceRole) return { ok: true };
  return {
    ok:      false,
    status:  401,
    code:    "internal_only",
    message: "This ingest endpoint requires service credentials.",
  };
}
