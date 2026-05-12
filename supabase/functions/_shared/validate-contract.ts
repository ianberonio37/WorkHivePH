// _shared/validate-contract.ts — runtime JSON Schema validation against
// canonical_agent_contracts (Tier C).
//
// The 7 brain output schemas registered in canonical_agent_contracts are
// the contract between AI-producing edge fns and dashboard consumers. This
// helper loads the schema at request time and validates the payload before
// it leaves the edge fn boundary. A contract violation means either the
// LLM hallucinated a different shape OR a Python-API output changed without
// us bumping the version. Both fail fast with structured 502.
//
// Usage:
//   import { validateContract } from "../_shared/validate-contract.ts";
//
//   const result = await validateContract(db, "analytics_action_plan_v1", llmJson);
//   if (!result.ok) {
//     return new Response(JSON.stringify({
//       error: "contract_violation",
//       contract_id: "analytics_action_plan_v1",
//       errors: result.errors,
//     }), { status: 502, headers: corsHeaders });
//   }
//
// Cache: schemas are loaded once per warm container and reused. The
// schemas are immutable once a contract_id is registered (a breaking
// change requires a new version like analytics_action_plan_v2).
//
// Skills consulted: ai-engineer (LLM contract enforcement), data-engineer
// (schema cache TTL pattern), platform-guardian (structured error
// envelope so downstream surfaces can render a useful message instead of
// silently breaking).

import Ajv, { ValidateFunction } from "https://esm.sh/ajv@8.12.0";
import { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";

// One Ajv instance per warm container (compiling schemas is the
// expensive step; reuse the compiled validators across requests).
const _ajv = new Ajv({ allErrors: true, strict: false });

// Compiled-validator cache, keyed by contract_id.
const _validatorCache: Map<string, ValidateFunction> = new Map();

// Schema-fetch cache so we don't hit the DB on every request after the
// first cold start in a container.
const _schemaCache: Map<string, unknown> = new Map();

export interface ContractValidationResult {
  ok:         boolean;
  contract_id: string;
  errors?:    Array<{ path: string; message: string }>;
}

/** Load + cache the JSON Schema for one contract_id. */
async function loadSchema(db: SupabaseClient, contract_id: string): Promise<unknown | null> {
  if (_schemaCache.has(contract_id)) return _schemaCache.get(contract_id);

  const { data, error } = await db
    .from("canonical_agent_contracts")
    .select("json_schema")
    .eq("contract_id", contract_id)
    .single();

  if (error || !data) {
    // Contract not registered — log but don't block the request. A
    // missing-contract is a separate failure mode from a contract-violation;
    // the gate (validate_canonical_anchor.py) is responsible for ratcheting
    // up coverage. Caller can treat null as "skip validation".
    console.error(`[validate-contract] schema not found for ${contract_id}:`, error?.message);
    return null;
  }

  _schemaCache.set(contract_id, data.json_schema);
  return data.json_schema;
}

/** Compile + cache the validator for one contract_id. */
async function getValidator(db: SupabaseClient, contract_id: string): Promise<ValidateFunction | null> {
  if (_validatorCache.has(contract_id)) return _validatorCache.get(contract_id)!;

  const schema = await loadSchema(db, contract_id);
  if (!schema) return null;

  try {
    const validate = _ajv.compile(schema as object);
    _validatorCache.set(contract_id, validate);
    return validate;
  } catch (e) {
    console.error(`[validate-contract] schema compile failed for ${contract_id}:`, (e as Error).message);
    return null;
  }
}

/**
 * Validate a payload against the registered contract_id schema.
 * Returns { ok: true } if valid, missing, or compile-failed (graceful).
 * Returns { ok: false, errors } only when the payload is shape-violating.
 *
 * Graceful-on-missing is intentional: a fresh edge fn may not have its
 * contract registered yet. The anchor gate's ratchet catches that as a
 * separate failure mode. We never want this helper to fail a request
 * because of a registry gap; only because of an actual shape violation.
 */
export async function validateContract(
  db: SupabaseClient,
  contract_id: string,
  payload: unknown
): Promise<ContractValidationResult> {
  const validate = await getValidator(db, contract_id);
  if (!validate) {
    // No registered schema → pass (the gate handles registration coverage)
    return { ok: true, contract_id };
  }

  const ok = validate(payload);
  if (ok) return { ok: true, contract_id };

  return {
    ok: false,
    contract_id,
    errors: (validate.errors || []).map(e => ({
      path:    e.instancePath || "/",
      message: e.message || "validation failed",
    })),
  };
}

/**
 * Convenience wrapper: build a 502 Response when validation fails.
 * Embeds the validation errors so the dashboard / caller can show a
 * useful message instead of silently breaking.
 */
export function contractViolationResponse(
  result: ContractValidationResult,
  corsHeaders: Record<string, string>
): Response {
  return new Response(
    JSON.stringify({
      error:       "contract_violation",
      contract_id: result.contract_id,
      errors:      result.errors,
      hint:        "The AI/edge response did not match the registered Tier C contract. This is usually a prompt or library regression.",
    }),
    { status: 502, headers: { ...corsHeaders, "Content-Type": "application/json" } }
  );
}
