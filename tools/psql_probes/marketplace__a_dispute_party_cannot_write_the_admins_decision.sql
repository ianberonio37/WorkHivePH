-- a_dispute_party_cannot_write_the_admins_decision: marketplace_disputes' UPDATE policy lets the buyer who opened a dispute
-- and the listing's seller update it - and until mig 20261105000005 nothing said WHICH columns, so a seller could PATCH
-- their own dispute to status 'resolved_release' with admin_decision 'Funds released to seller by admin'. The guard
-- (trg_guard_marketplace_dispute_columns) gives each column one owner. Found reading J27's premise (GJ M9).
-- The legs run AS the seller and AS the buyer (authenticated + claims) inside one BEGIN/ROLLBACK.
-- Self-grounding: a listing with a seller account, and another member to open the dispute.
-- expect: fixture_found \| t
-- expect: seller_cannot_decide \| t
-- expect: seller_can_reply_and_it_is_stamped \| t
-- expect: buyer_cannot_write_the_reply \| t
CREATE TEMP TABLE _p AS
SELECT l.id AS listing_id, l.auth_uid AS seller_uid, coalesce(l.seller_name, s.display_name) AS seller_name,
       b.auth_uid AS buyer_uid, b.display_name AS buyer_name
  FROM marketplace_listings l
  JOIN worker_profiles s ON s.auth_uid = l.auth_uid
  JOIN worker_profiles b ON b.auth_uid IS NOT NULL AND b.auth_uid <> l.auth_uid
 WHERE l.auth_uid IS NOT NULL
 ORDER BY l.created_at, b.username
 LIMIT 1;
CREATE TEMP TABLE _r (k text, v boolean);
GRANT SELECT ON _p TO authenticated;
GRANT ALL ON _r TO authenticated;
SELECT 'fixture_found | ' || EXISTS (SELECT 1 FROM _p);

BEGIN;
SET LOCAL session_replication_role = replica;
INSERT INTO marketplace_disputes (id, listing_id, opened_by, opened_by_auth_uid, seller_name, reason, status)
SELECT '00000000-0000-4000-8000-00000000d150', listing_id, buyer_name, buyer_uid, seller_name, 'probe: never arrived', 'open' FROM _p;
SET LOCAL session_replication_role = origin;

SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT seller_uid FROM _p)::text, 'role', 'authenticated')::text, true) IS NULL;
SET LOCAL ROLE authenticated;
DO $$ BEGIN
  UPDATE marketplace_disputes SET status = 'resolved_release', admin_decision = 'Funds released to seller by admin', resolved_at = now()
   WHERE id = '00000000-0000-4000-8000-00000000d150';
  INSERT INTO _r VALUES ('seller_cannot_decide', false);
EXCEPTION WHEN insufficient_privilege THEN INSERT INTO _r VALUES ('seller_cannot_decide', true);
END $$;
UPDATE marketplace_disputes SET seller_reply = 'probe: shipped on the 3rd, tracking attached', status = 'seller_responded'
 WHERE id = '00000000-0000-4000-8000-00000000d150';
RESET ROLE;
INSERT INTO _r SELECT 'seller_can_reply_and_it_is_stamped', EXISTS (SELECT 1 FROM marketplace_disputes
  WHERE id = '00000000-0000-4000-8000-00000000d150' AND status = 'seller_responded' AND seller_reply LIKE 'probe:%'
    AND seller_replied_at >= now() - interval '1 minute');

SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT buyer_uid FROM _p)::text, 'role', 'authenticated')::text, true) IS NULL;
SET LOCAL ROLE authenticated;
DO $$ BEGIN
  UPDATE marketplace_disputes SET seller_reply = 'words the seller never wrote' WHERE id = '00000000-0000-4000-8000-00000000d150';
  INSERT INTO _r VALUES ('buyer_cannot_write_the_reply', false);
EXCEPTION WHEN insufficient_privilege THEN INSERT INTO _r VALUES ('buyer_cannot_write_the_reply', true);
END $$;
RESET ROLE;
SELECT k || ' | ' || v FROM _r ORDER BY k;
ROLLBACK;
