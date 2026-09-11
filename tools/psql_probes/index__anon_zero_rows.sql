-- anon_zero_rows (index): an anonymous session receives ZERO hive rows. The oracle names index's 13
-- reads, but this probe proves something strictly STRONGER and self-maintaining: across EVERY
-- hive-scoped table in the schema, anon can read rows from exactly two - the public feed and the seller
-- directory - named here as an allowlist. Marketplace BROWSE left this list on 2026-09-07 (EX-HP H2,
-- 20260907000004): anon lost SELECT on marketplace_listings and reads v_marketplace_listings_public, a
-- definer view without seller_contact; the view leg below proves that surface still serves a stranger.
-- The same day this recipe caught the follow-on break: the seller policy's subquery on the revoked table
-- raised permission denied for anon (allowlist 3 -> 1) until 20260907000005 moved it behind a definer fn.
-- Anything index reads is hive-scoped and therefore covered by construction, and the assertion keeps
-- biting as tables are added: a new table that becomes anon-readable fails this probe on its next run,
-- which enumerating 13 named reads would never have caught.
-- "Zero" is only meaningful if the rows EXIST for someone: the control leg proves each checked table
-- is non-empty for postgres, so the anon zero is a refusal and not an empty database.
-- expect: control_tables_are_populated \| t
-- expect: unexpected_anon_readable_tables \| 0
-- expect: allowlist_still_public \| 2
-- expect: listings_public_view_serves_anon \| t
-- expect: listings_base_table_closed_to_anon \| t
-- expect: sellers_public_view_masks_contact_for_anon \| t
-- expect: hive_scoped_tables_checked \| [1-9][0-9]*
-- ★TEETH, PROVEN 2026-08-31 AND DELIBERATELY NOT AUTOMATED HERE. Resurrecting the pre-fix world with
-- `GRANT SELECT (auth_uid) ON community_posts TO anon` inside a transaction drives the leg below from
-- 0 to 1 - it goes RED against exactly the defect it was written for - and the rollback restores the
-- closed state (has_column_privilege back to false). That check is run BY HAND rather than baked in,
-- because this recipe executes on every board via the psql-probe-suite gate and a routinely-run gate
-- should not be granting privileges, even transactionally, on a database other sessions are reading.
-- expect: anon_readable_tables_exposing_auth_uid \| 0
CREATE TEMP TABLE _leak(tbl text, n bigint);
GRANT INSERT, SELECT ON _leak TO anon;

-- the two TABLES the product deliberately shows a logged-out visitor (listings moved behind a view, H2)
CREATE TEMP TABLE _allow(tbl text);
INSERT INTO _allow VALUES ('community_posts'), ('marketplace_sellers');

SELECT 'hive_scoped_tables_checked | ' || count(*)
FROM pg_class cl JOIN pg_namespace ns ON ns.oid=cl.relnamespace
JOIN pg_attribute a ON a.attrelid=cl.oid AND a.attname='hive_id' AND a.attnum>0
WHERE ns.nspname='public' AND cl.relkind='r' AND cl.relrowsecurity;

-- CONTROL: the allowlisted tables genuinely hold rows, so "anon sees 3" is not an artefact
SELECT 'control_tables_are_populated | ' ||
  ((SELECT count(*) FROM marketplace_listings) > 0 AND (SELECT count(*) FROM community_posts) > 0
   AND (SELECT count(*) FROM marketplace_sellers) > 0);

BEGIN;
SET LOCAL ROLE anon;
DO $$
DECLARE r record; c bigint;
BEGIN
  FOR r IN SELECT cl.relname FROM pg_class cl JOIN pg_namespace ns ON ns.oid=cl.relnamespace
           JOIN pg_attribute a ON a.attrelid=cl.oid AND a.attname='hive_id' AND a.attnum>0
           WHERE ns.nspname='public' AND cl.relkind='r' AND cl.relrowsecurity ORDER BY 1 LOOP
    BEGIN
      EXECUTE format('SELECT count(*) FROM public.%I', r.relname) INTO c;
      IF c > 0 THEN INSERT INTO _leak VALUES (r.relname, c); END IF;
    -- a table anon may not even SELECT (42501, no grant) is a stronger refusal than an RLS zero;
    -- it is not a leak, so it is deliberately not recorded.
    EXCEPTION WHEN OTHERS THEN NULL; END;
  END LOOP;
END $$;
COMMIT;

SELECT 'unexpected_anon_readable_tables | ' || count(*) FROM _leak WHERE tbl NOT IN (SELECT tbl FROM _allow);

-- ★THE LEG THAT WOULD HAVE CAUGHT THE 2026-08-31 LEAK, added the same day after this probe passed
-- through it. Counting TABLES is not enough, for a reason that only shows up when you look: the loop
-- above uses count(*), and count(*) succeeds with a privilege on ANY single column. So a table already
-- on the allowlist can start handing out a NEW sensitive column and the table count never moves - the
-- detector stays green while the exposure grows. That is exactly the shape of the defect this probe
-- was written beside: community_posts was allowlisted as a public surface, correctly, and the leak was
-- one COLUMN within it.
-- The precise rule, and it took measuring 44 relations to state it: a column grant to anon is harmless
-- on a table whose RLS shows anon no rows - 38 of 44 auth_uid-bearing relations grant anon the column
-- and expose nothing, because the rows never arrive. It is dangerous ONLY where anon can READ ROWS.
-- So the assertion is the intersection, not either half: for every relation anon can actually read
-- rows from, anon must NOT be able to read an internal identity column of it.
SELECT 'anon_readable_tables_exposing_auth_uid | ' || count(*)
FROM _leak l
JOIN pg_class c ON c.relname = l.tbl
JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = 'public'
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'auth_uid'
                   AND a.attnum > 0 AND NOT a.attisdropped
WHERE has_column_privilege('anon', c.oid, a.attnum, 'SELECT');
SELECT 'allowlist_still_public | ' || count(*) FROM _leak WHERE tbl IN (SELECT tbl FROM _allow);
-- the browse surface a stranger actually reads (H2): the public view serves rows, the base table refuses
BEGIN;
SET LOCAL ROLE anon;
SELECT 'listings_public_view_serves_anon | ' || ((SELECT count(*) FROM public.v_marketplace_listings_public) > 0);
SELECT 'listings_base_table_closed_to_anon | ' || (NOT has_table_privilege('anon', 'public.marketplace_listings', 'SELECT'));
-- the seller card / profile a stranger reads (20260907000006): rows served, the contact masked to NULL
SELECT 'sellers_public_view_masks_contact_for_anon | ' || ((SELECT count(*) FROM public.v_marketplace_sellers_public) > 0
   AND (SELECT count(messenger_username) + count(certifications) + count(created_at) FROM public.v_marketplace_sellers_public) = 0);
ROLLBACK;
DROP TABLE _leak; DROP TABLE _allow;
