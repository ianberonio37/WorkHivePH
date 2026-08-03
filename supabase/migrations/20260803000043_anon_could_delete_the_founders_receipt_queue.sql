-- ═══════════════════════════════════════════════════════════════════════════════════════════════
-- AN ANONYMOUS VISITOR COULD DELETE THE FOUNDER'S RECEIPT QUEUE
--
-- Found 2026-08-03 by the `unprotected-write-grant` gate, triaging the full suite. The defect is
-- mine: mig 38 created `v_gcash_receipts_needing_eyes` and let the default grants stand.
--
--   v_gcash_receipts_needing_eyes -> anon          : DELETE, INSERT, UPDATE
--   v_gcash_receipts_needing_eyes -> authenticated : DELETE, INSERT, UPDATE
--   is_insertable_into = YES · is_updatable = YES · view owner = postgres · NOT security_invoker
--
-- A view cannot own a write. An auto-updatable view that is NOT security_invoker performs the write
-- against the base table with the VIEW OWNER's privileges — here `postgres`, which owns
-- gcash_inbound_receipts and therefore bypasses its RLS. So the base table's single policy
-- (`gcash_inbound_receipts_admin_read`, SELECT / is_platform_admin()) was never consulted.
--
-- PROVED AS `anon`, in a rolled-back transaction:
--
--   ANON DELETE THROUGH THE VIEW: *** SUCCEEDED ***
--
-- An anonymous visitor could empty the queue of forwarded GCash receipts the founder has to review.
-- The receipts are the evidence that a provider's payment actually arrived; deleting them destroys
-- the only automatic link between a real GCash transfer and the top-up it should verify.
--
-- The INSERT was WORSE and only accidentally stopped:
--
--   ANON INSERT refused (23502): null value in column "raw_text" ... violates not-null constraint
--
-- 23502 is a NOT NULL on a column the VIEW does not expose. The privilege check PASSED and the write
-- reached the base table; it failed on a column default. That is a coincidence of the schema, not a
-- control — the same shape as the July TRUNCATE finding, where an anon truncate failed only with
-- 0A000 because that one table happened to carry an FK. Add a default to raw_text, or expose it in
-- the view, and anon inserts a forged receipt — which `match_gcash_receipt()` then matches against a
-- pending top-up by reference and amount, verifying it and MINTING CREDITS NOBODY PAID FOR. The
-- whole point of mig 38 is that credits mint only when the founder's own receipt agrees with a
-- filing the provider already made; an anon-writable receipts table hands the attacker both halves.
--
-- THE FIX, two parts, because either alone leaves a hole:
--   1. REVOKE every write verb from anon and authenticated. Nothing legitimate writes here through
--      PostgREST: receipts arrive via the `gcash-receipt-inbound` edge function, which uses the
--      service-role key after verifying an HMAC over the raw body.
--   2. SET security_invoker = on, so a READ is judged against the CALLER's rights and the base
--      table's admin-only policy finally applies. Every sibling truth view on this platform already
--      declares it (v_service_credit_topups_truth, v_marketplace_listings_truth); this view was the
--      exception, which is why it was also the only view in `public` with anon write grants.
--
-- Scanned the whole schema while here: this was the ONLY view granting INSERT/UPDATE/DELETE to
-- anon or authenticated. The blast radius is one object, and it is the one I added.
-- ═══════════════════════════════════════════════════════════════════════════════════════════════

-- 1. A read-only queue is read-only for everyone who is not the service role.
revoke insert, update, delete, truncate, references, trigger
  on public.v_gcash_receipts_needing_eyes from anon, authenticated;

-- 2. Judge reads against the caller, not the view owner, so the base-table policy governs.
alter view public.v_gcash_receipts_needing_eyes set (security_invoker = on);

-- 3. And take the READ from anon as well. With security_invoker on, an anon SELECT falls through to
-- gcash_inbound_receipts and raises "permission denied for table gcash_inbound_receipts" — which
-- leaks the base table's name and reads like a fault rather than a boundary. A signed-out visitor
-- has no business seeing a founder's review queue at all, so refuse it at the view: same answer,
-- named at the object the caller actually asked for. `authenticated` keeps SELECT because the
-- base-table policy (is_platform_admin()) is what decides among signed-in people, and it now
-- genuinely applies — verified: admin sees the row, a signed-in non-admin sees zero.
revoke select on public.v_gcash_receipts_needing_eyes from anon;

comment on view public.v_gcash_receipts_needing_eyes is
  'Forwarded GCash receipts the automatic match could not settle (mig 38). READ-ONLY and '
  'security_invoker (mig 43): writes were revoked after `anon` was proved able to DELETE the entire '
  'queue through it, and an anon INSERT reached the base table and failed only on a NOT NULL for a '
  'column the view does not expose. Receipts are written solely by the gcash-receipt-inbound edge '
  'function under the service role, after it verifies an HMAC over the raw body.';

-- Prove it, in the migration, so a future GRANT cannot quietly re-open this. A revoke that silently
-- did not apply would leave the hole while the migration reported success.
do $$
declare v_bad text;
begin
  select string_agg(distinct grantee || ':' || privilege_type, ', ')
    into v_bad
    from information_schema.role_table_grants
   where table_schema = 'public'
     and table_name   = 'v_gcash_receipts_needing_eyes'
     and grantee      in ('anon', 'authenticated')
     and privilege_type in ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE');
  if v_bad is not null then
    raise exception 'mig 43 FAILED: end-user write verbs still stand on the receipts view: %', v_bad;
  end if;

  if not exists (select 1 from pg_class c
                  where c.relname = 'v_gcash_receipts_needing_eyes'
                    and c.reloptions::text like '%security_invoker=on%') then
    raise exception 'mig 43 FAILED: the receipts view is still not security_invoker, so reads bypass the base-table policy';
  end if;
end $$;
