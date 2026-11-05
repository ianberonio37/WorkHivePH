-- marketplace__a_stranger_reads_the_badge_not_the_contact (GJ M9 J31, 2026-11-06, mig 20261106000002): a stranger
-- (anon) reads a seller's BADGE - from the table and through the listings view - and never the seller's contact, which
-- the public view masks and the table must not hand over underneath it. One anon-visible seller is given a contact
-- inside a rolled-back transaction; restoration is asserted.
-- expect: fixture \| t
-- expect: stranger_reads_contact \| refused
-- forbid: stranger_reads_contact \| probe\.contact
-- expect: stranger_reads_badge \| t
-- expect: stranger_reads_listings_view \| t
-- expect: stranger_view_contact_masked \| t
-- expect: restored \| t
CREATE FUNCTION pg_temp.try_read(sql text) RETURNS text LANGUAGE plpgsql AS $f$
DECLARE v text;
BEGIN
  EXECUTE sql INTO v;
  RETURN coalesce(v, 'NULL');
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused';
  WHEN others THEN RETURN 'error ' || SQLSTATE;
END $f$;
BEGIN;
UPDATE marketplace_sellers SET messenger_username = 'probe.contact'
 WHERE worker_name = (SELECT worker_name FROM marketplace_sellers WHERE seller_has_published_listing(worker_name) ORDER BY worker_name LIMIT 1);
SELECT 'fixture | ' || EXISTS (SELECT 1 FROM marketplace_sellers WHERE messenger_username = 'probe.contact');
SET LOCAL ROLE anon;
SELECT 'stranger_reads_contact | ' || pg_temp.try_read($q$SELECT messenger_username FROM marketplace_sellers WHERE worker_name IS NOT NULL ORDER BY messenger_username NULLS LAST LIMIT 1$q$);
SELECT 'stranger_reads_badge | ' || (pg_temp.try_read($q$SELECT count(*)::text FROM (SELECT worker_name, tier, kyb_verified, cert_verified, total_sales, rating_avg, rating_count, response_rate, response_time_h FROM marketplace_sellers) s$q$) ~ '^[1-9]');
SELECT 'stranger_reads_listings_view | ' || (pg_temp.try_read($q$SELECT count(*)::text FROM v_marketplace_listings_public$q$) ~ '^[0-9]+$');
SELECT 'stranger_view_contact_masked | ' || (pg_temp.try_read($q$SELECT count(*)::text FROM v_marketplace_sellers_public WHERE messenger_username = 'probe.contact'$q$) = '0');
ROLLBACK;
SELECT 'restored | ' || NOT EXISTS (SELECT 1 FROM marketplace_sellers WHERE messenger_username = 'probe.contact');
