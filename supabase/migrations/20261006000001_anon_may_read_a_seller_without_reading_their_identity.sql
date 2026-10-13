-- ANON MAY READ A SELLER WITHOUT READING THEIR IDENTITY
-- =====================================================
-- Repairs a regression introduced the same day by 20261004000006_two_select_policies_with_no_select_grant.
-- That migration was right about its own problem: marketplace_sellers had TWO SELECT policies and NO SELECT
-- grant, and GRANTs are checked BEFORE row-level security, so both policies were dead and a signed-in
-- seller's own profile would not load. It fixed that by granting SELECT.
--
-- ★BUT IT GRANTED THE WHOLE TABLE, AND THE WHOLE TABLE INCLUDES auth_uid. That broke a banked invariant
-- (tools/psql_probes/index__anon_zero_rows.sql): "for every relation anon can actually read ROWS from,
-- anon must NOT be able to read an internal identity column of it." The probe went 0 -> 1 and named
-- marketplace_sellers. The intersection is what matters and it is now met here: anon legitimately reads
-- SELLER ROWS (policy mkt_sellers_read_anon, USING seller_has_published_listing(worker_name)) because a
-- public marketplace has to show who is selling - so this is precisely the dangerous half, not the
-- harmless one, and the answer is to narrow the COLUMNS rather than to take the rows away.
--
-- WHY A COLUMN-LEVEL REVOKE WOULD NOT HAVE WORKED, and why this does it the long way round: a column
-- REVOKE is INERT while a table-level SELECT grant stands (this repo has that recorded). So the table
-- grant is dropped FIRST and the permitted columns are then granted explicitly.
--
-- THE COLUMN LIST IS THE LIVE SCHEMA MINUS auth_uid, read from information_schema rather than typed, and
-- it fails CLOSED by design: a column added to this table later is NOT granted to anon until someone
-- decides it should be. That is the right default for a table whose rows a stranger can read.
--
-- SECOND CHANGE, same reason: v_marketplace_sellers_truth is security_invoker=on AND references auth_uid,
-- so a caller needs privileges on that column to read the view AT ALL - which is the only reason anon
-- would need it. Anon does not read that view: the storefront reads v_marketplace_sellers_public (a
-- DEFINER view, so it keeps working through its owner's privileges), and every consumer of the truth view
-- is a signed-in surface (community's person card, and the two retired admin consoles). So anon's SELECT
-- on the truth view is withdrawn rather than left as the one thing forcing an identity column open.
--
-- NOT TOUCHED: `authenticated` keeps its table-level SELECT - the invariant is about what a STRANGER can
-- read, and a signed-in reader is already constrained by mkt_sellers_read (auth.uid() IS NOT NULL) plus
-- the per-row policies. No policy is created, altered or dropped here, and no view is redefined, so the
-- CREATE-OR-REPLACE-VIEW trap that silently strips security_invoker is not in play.

BEGIN;

-- 1. drop the blanket table grant that carried auth_uid along with everything else
REVOKE SELECT ON public.marketplace_sellers FROM anon;

-- 2. grant back exactly the non-identity columns, generated from the live schema
DO $$
DECLARE
  cols text;
BEGIN
  SELECT string_agg(quote_ident(column_name), ', ' ORDER BY ordinal_position)
    INTO cols
    FROM information_schema.columns
   WHERE table_schema = 'public'
     AND table_name   = 'marketplace_sellers'
     AND column_name <> 'auth_uid';

  IF cols IS NULL THEN
    RAISE EXCEPTION 'marketplace_sellers has no grantable columns - refusing to leave anon with nothing';
  END IF;

  EXECUTE format('GRANT SELECT (%s) ON public.marketplace_sellers TO anon', cols);
END $$;

-- 3. the invoker view that needs auth_uid is not an anon surface
REVOKE SELECT ON public.v_marketplace_sellers_truth FROM anon;

-- 4. assert the outcome in the same transaction, so a wrong grant cannot be committed
DO $$
BEGIN
  IF has_column_privilege('anon', 'public.marketplace_sellers'::regclass,
                          (SELECT attnum FROM pg_attribute
                            WHERE attrelid = 'public.marketplace_sellers'::regclass
                              AND attname = 'auth_uid' AND NOT attisdropped), 'SELECT') THEN
    RAISE EXCEPTION 'anon can still read marketplace_sellers.auth_uid - the invariant this migration exists for is still broken';
  END IF;

  IF NOT has_column_privilege('anon', 'public.marketplace_sellers'::regclass,
                              (SELECT attnum FROM pg_attribute
                                WHERE attrelid = 'public.marketplace_sellers'::regclass
                                  AND attname = 'worker_name' AND NOT attisdropped), 'SELECT') THEN
    RAISE EXCEPTION 'anon lost worker_name - the public storefront needs to show who is selling';
  END IF;

  IF has_table_privilege('anon', 'public.v_marketplace_sellers_truth'::regclass, 'SELECT') THEN
    RAISE EXCEPTION 'anon still holds SELECT on the security_invoker truth view';
  END IF;
END $$;

COMMIT;
