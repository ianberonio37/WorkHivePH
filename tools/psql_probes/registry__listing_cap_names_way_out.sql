-- S-adversarial edge (spammer/colluder tail): the 3-live-listing cap HOLDS for a seller with no
-- sale, and the refusal names both the limit and the way out ('sell one, or take one down to make
-- room') - never a bare 'Save failed'. Control: the SAME row as a draft is accepted (only a publish
-- is gated), so the refusal is the cap, not a broken insert path. Fixture: a real no-sale seller
-- with exactly the cap live (found, not seeded). Separate txns; everything rolled back.
-- expect: fixture_found \| t
-- expect: sell one, or take one down to make room
-- expect: draft_control_accepted \| t
-- forbid: fourth_publish_survived \| t
CREATE TEMP TABLE _cap AS
SELECT s.worker_name AS seller, s.auth_uid AS uid,
       (SELECT l2.hive_id FROM marketplace_listings l2 WHERE l2.seller_name = s.worker_name LIMIT 1) AS hive
FROM marketplace_sellers s
WHERE s.auth_uid IS NOT NULL
  AND (SELECT count(*) FROM marketplace_listings l WHERE l.seller_name = s.worker_name AND l.status = 'published') >= 3
  AND NOT EXISTS (SELECT 1 FROM marketplace_listings l WHERE l.seller_name = s.worker_name AND l.status = 'sold')
  AND NOT EXISTS (SELECT 1 FROM service_requests r JOIN service_providers p ON p.id = r.matched_provider_id
                    JOIN marketplace_sellers ms ON ms.auth_uid = p.auth_uid
                   WHERE ms.worker_name = s.worker_name AND r.status IN ('completed','settled'))
LIMIT 1;
GRANT SELECT ON _cap TO authenticated;
SELECT 'fixture_found | ' || (EXISTS (SELECT 1 FROM _cap));
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT uid FROM _cap)::text, 'role', 'authenticated')::text, true);
INSERT INTO marketplace_listings (seller_name, hive_id, title, section, category, price, status)
SELECT seller, hive, 'cap probe: the fourth live listing', 'parts', 'other', 900, 'published' FROM _cap;
SELECT 'fourth_publish_survived | t';
ROLLBACK;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT uid FROM _cap)::text, 'role', 'authenticated')::text, true);
INSERT INTO marketplace_listings (seller_name, hive_id, title, section, category, price, status)
SELECT seller, hive, 'cap probe: a draft is not gated', 'parts', 'other', 900, 'draft' FROM _cap;
SELECT 'draft_control_accepted | ' || (EXISTS (SELECT 1 FROM marketplace_listings
  WHERE title = 'cap probe: a draft is not gated'));
ROLLBACK;
DROP TABLE _cap;
