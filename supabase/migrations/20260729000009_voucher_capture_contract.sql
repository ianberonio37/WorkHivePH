-- =====================================================================
-- Registration cascade for the J16 voucher-mint form (canonical capture contract)
-- =====================================================================
-- The canonical-anchor gate (L8) caught the new founder-console voucher form as an UN-ANCHORED
-- capture surface the moment it shipped - exactly what that gate is for. Every input surface on
-- the platform declares what it captures, where it lands, and who consumes it; a form that skips
-- that is a field nobody can trace. This closes it in the same shape as marketplace_listing_v1.

BEGIN;

INSERT INTO public.canonical_capture_contracts
  (capture_id, surface, source_page, fields, target_table, target_columns, contract_schema, validates_at, consumers, notes)
VALUES (
  'service_voucher_v1',
  'form',
  'founder-console.html',
  '[{"name": "code", "type": "text", "max_len": 24, "required": true, "pattern": "^[A-Z0-9]{3,24}$"},
    {"name": "kind", "type": "enum", "values": ["percent", "fixed"], "required": true},
    {"name": "value", "type": "numeric", "min": 1, "required": true},
    {"name": "segment", "type": "enum", "values": ["industrial", "consumer", null], "required": false},
    {"name": "max_uses", "type": "integer", "min": 1, "required": false}]'::jsonb,
  'service_vouchers',
  '{code,kind,value,segment,max_uses,per_user_limit,expires_at,active,created_at}',
  '{"type": "object",
     "required": ["code", "kind", "value"],
     "properties": {"code": {"type": "string", "maxLength": 24, "minLength": 3, "pattern": "^[A-Z0-9]{3,24}$"},
                    "kind": {"type": "string", "enum": ["percent", "fixed"]},
                    "value": {"type": "number", "minimum": 1},
                    "segment": {"type": ["string", "null"], "enum": ["industrial", "consumer", null]},
                    "max_uses": {"type": ["integer", "null"], "minimum": 1}}}'::jsonb,
  'db_trigger',   -- RLS + the admin-write policy validate at the database, not the client
  '{founder-console.html,marketplace.html}',
  'J16 founder voucher campaigns. Writes are admin-only at the DATABASE (service_vouchers_admin_write) - a non-admin insert is refused by RLS, proven live, so hiding the form was never the boundary. Redemption is completion-gated through redeem_service_voucher() and reimburses the provider, so the platform absorbs the discount rather than the provider.'
)
ON CONFLICT (capture_id) DO UPDATE
  SET surface = excluded.surface, source_page = excluded.source_page, fields = excluded.fields,
      target_table = excluded.target_table, target_columns = excluded.target_columns,
      contract_schema = excluded.contract_schema, validates_at = excluded.validates_at, consumers = excluded.consumers, notes = excluded.notes;

COMMIT;
