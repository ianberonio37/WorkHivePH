-- a_client_cannot_rewrite_the_providers_quote: service_offers had no trigger and its UPDATE policy lets both parties of a
-- request update an offer, so a client could PATCH a provider's quote down and then accept it through select_quote. The
-- guard (trg_guard_service_offer_columns, mig 20261105000006) makes price / kind / eta / message the provider's, while
-- the offer is open, and the status the platform's own paths' (select_quote / accept_service_request). Found reading
-- J6's premise (GJ M9). The legs run AS the client and AS the provider inside one BEGIN/ROLLBACK.
-- Self-grounding: a pending offer whose request's client has an account and whose provider is a person's.
-- expect: fixture_found \| t
-- expect: client_cannot_rewrite_the_price \| t
-- expect: provider_can_change_an_open_offer \| t
CREATE TEMP TABLE _p AS
SELECT o.id AS offer_id, r.client_auth_uid AS client_uid, sp.auth_uid AS provider_uid
  FROM service_offers o
  JOIN service_requests r ON r.id = o.request_id
  JOIN service_providers sp ON sp.id = o.provider_id
 WHERE o.status = 'pending' AND r.client_auth_uid IS NOT NULL AND sp.auth_uid IS NOT NULL
 ORDER BY o.created_at
 LIMIT 1;
CREATE TEMP TABLE _r (k text, v boolean);
GRANT SELECT ON _p TO authenticated;
GRANT ALL ON _r TO authenticated;
SELECT 'fixture_found | ' || EXISTS (SELECT 1 FROM _p);

BEGIN;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT client_uid FROM _p)::text, 'role', 'authenticated')::text, true) IS NULL;
SET LOCAL ROLE authenticated;
DO $$ BEGIN
  UPDATE service_offers SET price = 1 WHERE id = (SELECT offer_id FROM _p);
  INSERT INTO _r VALUES ('client_cannot_rewrite_the_price', NOT FOUND);
EXCEPTION WHEN insufficient_privilege THEN INSERT INTO _r VALUES ('client_cannot_rewrite_the_price', true);
END $$;
RESET ROLE;

SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT provider_uid FROM _p)::text, 'role', 'authenticated')::text, true) IS NULL;
SET LOCAL ROLE authenticated;
UPDATE service_offers SET message = 'probe: can start Tuesday' WHERE id = (SELECT offer_id FROM _p);
RESET ROLE;
INSERT INTO _r SELECT 'provider_can_change_an_open_offer', EXISTS (SELECT 1 FROM service_offers o, _p
  WHERE o.id = _p.offer_id AND o.message = 'probe: can start Tuesday');
SELECT k || ' | ' || v FROM _r ORDER BY k;
ROLLBACK;
