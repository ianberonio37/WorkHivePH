-- peers_basis_stated: the "peers" count has a stated basis the RPC enforces — Practitioner+
-- (skill_badges level >= 2), verified identities only (auth_uid IS NOT NULL), grouped per person
-- and discipline so one person cannot count twice.
-- expect: level_floor \| t
-- expect: verified_only \| t
-- expect: grouped_per_person \| t
SELECT 'level_floor | '        || (prosrc ILIKE '%level >= 2%')          FROM pg_proc WHERE proname='get_hive_trade_peers';
SELECT 'verified_only | '      || (prosrc ILIKE '%auth_uid IS NOT NULL%') FROM pg_proc WHERE proname='get_hive_trade_peers';
SELECT 'grouped_per_person | ' || (prosrc ILIKE '%GROUP BY%auth_uid%')    FROM pg_proc WHERE proname='get_hive_trade_peers';
