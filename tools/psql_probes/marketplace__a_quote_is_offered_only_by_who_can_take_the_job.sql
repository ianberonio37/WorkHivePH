-- marketplace__a_quote_is_offered_only_by_who_can_take_the_job (GJ M9 J6, 2026-11-06, migs 20261106000012 + 13): a person
-- holding two provider identities (their own business and their hive's team) quotes as the one they CHOOSE, never one
-- picked for them; an identity that cannot hold the job's 10% reservation is refused the quote (told to the provider,
-- with the amounts); a name that is not theirs cannot be quoted under; and when a provider's credits no longer cover the
-- hold at the moment the client chooses, the client gets their own answer and the request stays open. All inside a
-- rolled-back transaction; restoration is asserted.
-- expect: fixture \| t
-- expect: no_credits_no_quote \| needs_credits
-- expect: quotes_as_the_chosen_identity \| t
-- expect: cannot_quote_as_someone_else \| t
-- expect: client_told_in_their_terms \| provider_cannot_take
-- expect: request_stays_open \| broadcasting
-- expect: restored \| t
BEGIN;
-- a person who owns a provider identity AND is an active member of a hive that has a team identity
SELECT sp.id AS own_prov, sp.auth_uid AS puid, hp.id AS team_prov
  FROM service_providers sp
  JOIN hive_members hm ON hm.auth_uid = sp.auth_uid AND hm.status = 'active'
  JOIN service_providers hp ON hp.provider_type = 'hive' AND hp.hive_id = hm.hive_id
 WHERE sp.auth_uid IS NOT NULL AND sp.provider_type <> 'hive'
 ORDER BY sp.created_at LIMIT 1 \gset
SELECT sp.id AS other_prov FROM service_providers sp WHERE sp.auth_uid IS NOT NULL AND sp.auth_uid <> :'puid' ORDER BY sp.created_at LIMIT 1 \gset
SELECT hm.auth_uid AS cuid, hm.worker_name AS cname, hm.hive_id AS chive
  FROM hive_members hm WHERE hm.status = 'active' AND hm.auth_uid IS NOT NULL AND hm.auth_uid <> :'puid'
 ORDER BY hm.auth_uid LIMIT 1 \gset
SET LOCAL session_replication_role = replica;   -- the fixture request and the provider's starting balance (P0)
DELETE FROM service_credit_ledger WHERE account_type = 'provider' AND account_id = :'own_prov';
DELETE FROM service_credit_ledger WHERE account_type = 'consumer' AND account_id = :'puid';
INSERT INTO service_requests (client_auth_uid, client_worker_name, hive_id, segment, mode, custom_scope, address, urgency, status, budget)
VALUES (:'cuid', :'cname', :'chive', 'industrial', 'quote', 'probe - a quote only from who can take it', 'Probe site', 'normal', 'broadcasting', 6000)
RETURNING id AS rq \gset
SET LOCAL session_replication_role = origin;
SELECT 'fixture | ' || (:'rq' <> '' AND :'team_prov' <> '' AND :'other_prov' <> '');
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', :'puid', 'role', 'authenticated')::text, true) IS NOT NULL AS c1 \gset
SELECT 'no_credits_no_quote | ' || (submit_service_quote(:'rq', 5850, NULL, NULL, :'own_prov') ->> 'reason');
RESET ROLE;
SET LOCAL session_replication_role = replica;
INSERT INTO service_credit_ledger (account_type, account_id, entry_type, amount, note) VALUES ('provider', :'own_prov', 'adjustment', 1000, 'probe credits');
SET LOCAL session_replication_role = origin;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', :'puid', 'role', 'authenticated')::text, true) IS NOT NULL AS c2 \gset
SELECT 'quotes_as_the_chosen_identity | ' || ((submit_service_quote(:'rq', 5850, NULL, NULL, :'own_prov') ->> 'provider_id') = :'own_prov');
SELECT 'cannot_quote_as_someone_else | ' || NOT coalesce((submit_service_quote(:'rq', 5000, NULL, NULL, :'other_prov') ->> 'quoted')::boolean, false);
RESET ROLE;
SELECT id AS off FROM service_offers WHERE request_id = :'rq' AND provider_id = :'own_prov' \gset
-- the provider's credits are spent elsewhere before the client chooses
SET LOCAL session_replication_role = replica;
DELETE FROM service_credit_ledger WHERE account_type = 'provider' AND account_id = :'own_prov';
SET LOCAL session_replication_role = origin;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', :'cuid', 'role', 'authenticated')::text, true) IS NOT NULL AS c3 \gset
SELECT 'client_told_in_their_terms | ' || (select_quote(:'off') ->> 'reason');
RESET ROLE;
SELECT 'request_stays_open | ' || (SELECT status FROM service_requests WHERE id = :'rq');
ROLLBACK;
SELECT 'restored | ' || NOT EXISTS (SELECT 1 FROM service_requests WHERE custom_scope = 'probe - a quote only from who can take it');
