/**
 * validateAgentContract — Tier B (Brain) runtime contract enforcer.
 *
 * Looks up the agent's JSON-schema-lite contract from
 * canonical/agent_contracts.json (shipped as a static asset alongside
 * edge function source) and validates the agent's output against it
 * before returning to the caller. On shape drift the helper returns a
 * structured error so the dashboard knows the agent's output is invalid
 * without parsing it.
 *
 * Why a custom mini-validator instead of pulling in ajv:
 *   - the contract surface is tiny (object with required string/array/
 *     enum/number fields) — full JSON Schema is overkill
 *   - keeps the edge fn bundle small + Deno-free of remote imports
 *
 * Usage in any edge function:
 *
 *   import { validateAgentContract } from '../_shared/validateAgentContract.ts';
 *   const result = aiOutput;
 *   const check = validateAgentContract('analytics_action_plan_v1', result);
 *   if (!check.ok) {
 *     return new Response(JSON.stringify({ error: 'agent_contract_violation', details: check.errors }),
 *                         { status: 422, headers: cors });
 *   }
 */

import agentContracts from "../../../canonical/agent_contracts.json" with { type: "json" };

export interface ValidationResult {
  ok:      boolean;
  agent_id: string;
  errors:  string[];
}

interface SchemaNode {
  type?:       string;
  required?:   string[];
  properties?: Record<string, SchemaNode>;
  items?:      SchemaNode;
  enum?:       any[];
  maxLength?:  number;
  minimum?:    number;
  maximum?:    number;
  format?:     string;
}

function validateNode(path: string, value: any, schema: SchemaNode): string[] {
  const errors: string[] = [];
  if (schema.type === "object") {
    if (typeof value !== "object" || value === null || Array.isArray(value)) {
      errors.push(`${path}: expected object, got ${typeof value}`);
      return errors;
    }
    for (const req of schema.required || []) {
      if (!(req in value)) errors.push(`${path}.${req}: required field missing`);
    }
    for (const [k, sub] of Object.entries(schema.properties || {})) {
      if (k in value) {
        errors.push(...validateNode(`${path}.${k}`, value[k], sub));
      }
    }
  } else if (schema.type === "array") {
    if (!Array.isArray(value)) {
      errors.push(`${path}: expected array, got ${typeof value}`);
      return errors;
    }
    if (schema.items) {
      value.forEach((v, i) => {
        errors.push(...validateNode(`${path}[${i}]`, v, schema.items!));
      });
    }
  } else if (schema.type === "string") {
    if (typeof value !== "string") errors.push(`${path}: expected string, got ${typeof value}`);
    else if (schema.maxLength != null && value.length > schema.maxLength) {
      errors.push(`${path}: string length ${value.length} exceeds maxLength ${schema.maxLength}`);
    }
  } else if (schema.type === "number") {
    if (typeof value !== "number") errors.push(`${path}: expected number, got ${typeof value}`);
    else if (schema.minimum != null && value < schema.minimum) errors.push(`${path}: ${value} < min ${schema.minimum}`);
    else if (schema.maximum != null && value > schema.maximum) errors.push(`${path}: ${value} > max ${schema.maximum}`);
  }
  if (schema.enum && !schema.enum.includes(value)) {
    errors.push(`${path}: value ${JSON.stringify(value)} not in enum ${JSON.stringify(schema.enum)}`);
  }
  return errors;
}

export function validateAgentContract(agentId: string, output: any): ValidationResult {
  const agents = (agentContracts as any).agents || [];
  const contract = agents.find((a: any) => a.agent_id === agentId);
  if (!contract) {
    return { ok: false, agent_id: agentId, errors: [`unknown agent_id: ${agentId} — register in canonical/agent_contracts.json`] };
  }
  const schema: SchemaNode | undefined = contract.output_schema;
  if (!schema) {
    // Agent registered but schema not yet specified — informational pass
    return { ok: true, agent_id: agentId, errors: [] };
  }
  const errors = validateNode("output", output, schema);
  return { ok: errors.length === 0, agent_id: agentId, errors };
}
