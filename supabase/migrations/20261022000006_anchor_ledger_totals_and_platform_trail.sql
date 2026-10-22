-- canonical-anchor (2026-10-22): three objects that SL LB2 and SL L2 created were never registered, and the anchor gate's
-- fuel and engine ratchets have said so since they landed (fuel 4 -> 6, engine 2 -> 3): the ledger's kept totals, the
-- platform trail, and the read the credit position makes of those totals. Each gets its own domain - canonical_sources is
-- keyed by domain alone, so a shared one would keep only the first row (the 2026-08-03 collision the gate now catches).

insert into public.canonical_sources (domain, source_kind, source_name, owner_skill, freshness, contract, description)
values
  ('service_credit_ledger_totals', 'table', 'service_credit_ledger_totals', 'marketplace', 'realtime',
   '{"boundary": "one row per account and entry type, kept by trg_keep_ledger_totals in the same transaction as the ledger write; read through get_credit_ledger_totals, never summed from capped ledger rows in a browser"}'::jsonb,
   'The credit ledger''s running totals (SL LB2): what the credit position reads instead of adding up ledger rows past a row cap.'),
  ('platform_audit_log', 'table', 'platform_audit_log', 'enterprise-compliance', 'realtime',
   '{"boundary": "platform-scope decisions (top-ups, listings, sellers, feedback): who decided what and when, bound to the deciding account by the database; readable by platform admins only"}'::jsonb,
   'The platform trail (SL L2): decisions that belong to no hive, kept apart from every hive''s own audit log.'),
  ('credit_ledger_totals_read', 'rpc', 'get_credit_ledger_totals', 'marketplace', 'on_demand',
   '{"boundary": "the totals the ledger keeps, per entry type, as the caller (security invoker): a platform admin reads the platform''s; anyone else reads what RLS lets them"}'::jsonb,
   'The credit position''s one read of the economy''s totals (the operator console''s Operations tab, from operator-actions.js).')
on conflict do nothing;
