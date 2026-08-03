-- ═══════════════════════════════════════════════════════════════════════════════════════════════
-- REGISTER THE RECEIPT INTAKE — mig 38 created two objects and anchored neither
--
-- The canonical-anchor gate, triaging the full suite:
--
--   [fuel]   count went UP: 5 -> 6 un-anchored. New: gcash_inbound_receipts   (mig 38)
--   [engine] count went UP: 2 -> 3 un-anchored. New: v_gcash_receipts_needing_eyes (mig 38)
--
-- Both are mine, and this is the FOURTH place mig 38 skipped: it also missed reset.py, the deploy
-- script, and OPTIONAL_VARS. One migration, four registries, none of them updated — the whole
-- "register a new artifact everywhere" checklist run exactly zero times.
--
-- WHY THE REGISTRY MATTERS HERE MORE THAN USUAL. canonical_sources is what makes a table's contract
-- legible to every other gate and every future reader: who owns it, how fresh it is, what the key
-- is, who may write. An unregistered table is invisible to the anchor audit, so the next person to
-- touch it has to reconstruct its rules from the migration body — which is precisely how the anon
-- write grant on the sibling view survived (mig 43) and how the reset gap survived.
--
-- The contracts below are written from what the code ACTUALLY does, verified this session, not from
-- what mig 38's comments claim:
--   * writes come only from the gcash-receipt-inbound edge function under the service role, after it
--     verifies an HMAC over the raw body and fails CLOSED with no secret;
--   * the trigger match_gcash_receipt() verifies a top-up ONLY when reference AND amount agree with a
--     filing the provider already made — the receipt is a claim, never an authority;
--   * the view is read-only and security_invoker as of mig 43, so the base table's admin-only policy
--     decides who sees it.
-- ═══════════════════════════════════════════════════════════════════════════════════════════════

insert into public.canonical_sources
  (domain, source_kind, source_name, owner_skill, freshness, contract, description)
values
  ('service_gcash_receipts_raw', 'table', 'gcash_inbound_receipts', 'marketplace', 'on_demand',
   jsonb_build_object(
     'key',          jsonb_build_array('reference'),
     'writes',       'service-role only, via the gcash-receipt-inbound edge fn after HMAC-SHA256 over `${timestamp}.${rawBody}`; fails CLOSED when GCASH_INBOUND_SECRET is unset',
     'authority',    'a forwarded receipt is a CLAIM, not proof - match_gcash_receipt() verifies a top-up only when reference AND amount agree with a filing the provider already made',
     'raw_retained', 'raw_text is always stored, so a parse that gets it wrong stays recoverable',
     'match_states', jsonb_build_array('matched', 'unmatched', 'ambiguous', 'amount_mismatch', 'already_decided')),
   'Forwarded GCash payment notifications (SMS/email) that let a top-up verify itself without a merchant account. Written only by the inbound edge function; never a client write path.'),

  ('service_gcash_receipts_engine', 'view', 'v_gcash_receipts_needing_eyes', 'marketplace', 'on_demand',
   jsonb_build_object(
     'reads',            'gcash_inbound_receipts where the automatic match could not settle',
     'security_invoker', true,
     'grants',           'SELECT to authenticated only (mig 43 revoked every write verb and the anon read, after anon was proved able to DELETE the whole queue through it)',
     'visibility',       'the base-table policy gcash_inbound_receipts_admin_read decides: platform admins see rows, everyone else sees none',
     'surface',          'platform-actions.html - the founder queue for receipts automation deliberately left to a human'),
   'The leftovers of automatic matching: a receipt with no filing yet, an amount that disagrees, a reference already decided. Each row says why, so automation that fails does so visibly rather than silently.')
on conflict do nothing;

-- Prove both landed. A registry insert that silently no-ops (on conflict, a typo'd source_kind the
-- gate does not scan for) would leave the anchor gate red while this migration reported success.
do $$
declare v_missing text;
begin
  select string_agg(x.name, ', ')
    into v_missing
    from (values ('gcash_inbound_receipts'), ('v_gcash_receipts_needing_eyes')) as x(name)
   where not exists (
     select 1 from public.canonical_sources cs where cs.source_name = x.name);
  if v_missing is not null then
    raise exception 'mig 44 FAILED: still un-anchored in canonical_sources: %', v_missing;
  end if;
end $$;
