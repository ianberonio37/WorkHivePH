/* wh-capture-validate.js — runtime capture-contract validation (Tier F)
 *
 * Client-side companion to supabase/functions/_shared/validate-contract.ts.
 * Loads the JSON Schema from canonical_capture_contracts at first use and
 * validates a form payload against it before the page issues
 * db.from(...).insert(...). This is what makes Wave 1/2 captures
 * load-bearing — without it, the registry is documentation only.
 *
 * Usage:
 *   const result = await whValidateCapture(db, 'logbook_add_entry_v1', payload);
 *   if (!result.ok) {
 *     showToast('Cannot save: ' + result.errors[0].message);
 *     return;
 *   }
 *   await db.from('logbook').insert(payload);
 *
 * Skills consulted: frontend (no build step, plain ES2020), ai-engineer
 * (consistent shape with edge-side validate-contract.ts so an AI agent
 * gets identical error messages on either side), performance (schema
 * cached per page-load, no Ajv import — minimal JSON Schema subset
 * built inline so engineering-design.html doesn't pay 40KB for Ajv).
 *
 * Supported JSON Schema keywords (sufficient for every Wave 1+2 contract):
 *   type, required, properties, items
 *   minLength, maxLength
 *   minimum, maximum
 *   enum
 *   pattern (regex)
 *   format=email (RFC-5322 lite — same regex Supabase Auth uses)
 *
 * Unsupported (validator falls back to "skip key" rather than throw):
 *   $ref, oneOf, anyOf, allOf, conditionals, format=date/uri, multipleOf
 */
(function () {
  'use strict';

  if (window.whValidateCapture) return;   // already loaded

  // ── Schema cache ──────────────────────────────────────────────────────────
  // Keyed by capture_id. Once a page fetches a schema, it's reused for the
  // session. Cache miss => fetch from canonical_capture_contracts table.
  const _schemaCache = new Map();

  // ── Minimal JSON Schema validator ────────────────────────────────────────
  function _validate(schema, value, path) {
    if (schema == null) return [];
    const errs = [];

    if (schema.type) {
      const types = Array.isArray(schema.type) ? schema.type : [schema.type];
      const actual = value === null ? 'null'
        : Array.isArray(value) ? 'array'
        : Number.isInteger(value) ? 'integer'
        : typeof value === 'number' ? 'number'
        : typeof value;
      const allowedAlts = types.includes('number') && actual === 'integer' ? true : null;
      if (!types.includes(actual) && !allowedAlts) {
        errs.push({ path, message: `expected type ${types.join('|')} but got ${actual}` });
        return errs;   // type mismatch => other keywords meaningless
      }
    }

    if (schema.enum && !schema.enum.includes(value)) {
      errs.push({ path, message: `value must be one of ${JSON.stringify(schema.enum)}; got ${JSON.stringify(value)}` });
    }

    if (typeof value === 'string') {
      if (schema.minLength != null && value.length < schema.minLength) {
        errs.push({ path, message: `string length ${value.length} < minLength ${schema.minLength}` });
      }
      if (schema.maxLength != null && value.length > schema.maxLength) {
        errs.push({ path, message: `string length ${value.length} > maxLength ${schema.maxLength}` });
      }
      if (schema.pattern) {
        try {
          if (!(new RegExp(schema.pattern)).test(value)) {
            errs.push({ path, message: `string does not match pattern ${schema.pattern}` });
          }
        } catch (_e) { /* invalid regex => skip */ }
      }
      if (schema.format === 'email') {
        // RFC-5322 lite, same shape Supabase Auth accepts
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
          errs.push({ path, message: 'must be a valid email address' });
        }
      }
    }

    if (typeof value === 'number') {
      if (schema.minimum != null && value < schema.minimum) {
        errs.push({ path, message: `number ${value} < minimum ${schema.minimum}` });
      }
      if (schema.maximum != null && value > schema.maximum) {
        errs.push({ path, message: `number ${value} > maximum ${schema.maximum}` });
      }
    }

    if (schema.type === 'object' || (schema.type == null && value && typeof value === 'object' && !Array.isArray(value))) {
      if (schema.required && Array.isArray(schema.required)) {
        for (const key of schema.required) {
          if (value == null || !(key in value) || value[key] === '' || value[key] === undefined) {
            errs.push({ path: `${path}.${key}`, message: `required key '${key}' is missing or empty` });
          }
        }
      }
      if (schema.properties && value && typeof value === 'object') {
        for (const [key, subSchema] of Object.entries(schema.properties)) {
          if (key in value) {
            errs.push(..._validate(subSchema, value[key], `${path}.${key}`));
          }
        }
      }
    }

    if (schema.type === 'array' && Array.isArray(value) && schema.items) {
      for (let i = 0; i < value.length; i++) {
        errs.push(..._validate(schema.items, value[i], `${path}[${i}]`));
      }
    }

    return errs;
  }

  // ── Public API ────────────────────────────────────────────────────────────

  /**
   * Validate a payload against a registered capture contract.
   * @param {Object} db - Supabase client (createClient() result)
   * @param {string} captureId - e.g. 'logbook_add_entry_v1'
   * @param {Object} payload - the form/voice/qr payload about to be written
   * @returns {Promise<{ok: boolean, capture_id: string, errors?: Array}>}
   *
   * Graceful-on-missing: if the contract isn't registered (e.g. Wave 3 not
   * applied to this DB yet), returns ok=true so we never block a write on
   * a registry gap. The CI gate handles coverage separately.
   */
  async function whValidateCapture(db, captureId, payload) {
    let schema = _schemaCache.get(captureId);
    if (!schema) {
      try {
        const { data, error } = await db.from('canonical_capture_contracts')
          .select('contract_schema')
          .eq('capture_id', captureId)
          .maybeSingle();
        if (error || !data) {
          // Missing contract => skip validation. Anchor gate catches this.
          console.warn('[wh-capture-validate] schema not found for', captureId);
          return { ok: true, capture_id: captureId };
        }
        schema = data.contract_schema;
        _schemaCache.set(captureId, schema);
      } catch (e) {
        console.warn('[wh-capture-validate] schema fetch failed for', captureId, e);
        return { ok: true, capture_id: captureId };
      }
    }

    const errors = _validate(schema, payload, '$');
    if (!errors.length) return { ok: true, capture_id: captureId };
    return { ok: false, capture_id: captureId, errors };
  }

  // Expose to global so any inline <script> can use it without an import.
  window.whValidateCapture = whValidateCapture;
  // For pages that want to clear the cache after a schema update
  window.whValidateCaptureClearCache = () => _schemaCache.clear();
})();
