-- ============================================================================
-- Register get_marketplace_seller_public so validate_canonical_anchor.py's engine_anchor ratchet sees
-- it (un-anchored count had ticked UP: engine 2 -> 3).
--
-- The RPC (20260724000004) is the anonymous-safe read behind the public seller profile: a SECURITY
-- DEFINER function projecting 16 public columns and deliberately OMITTING messenger_username, hive_id
-- and auth_uid, so a signed-out visitor (and a crawler) can see the profile + its JSON-LD without the
-- page leaking contact PII or tenant topology. It exists because the underlying truth view is
-- correctly RLS-closed to anon; the RPC is the narrow, audited hole rather than a widened policy.
--
-- canonical_sources PK is `domain`; `contract` has a DEFAULT so it is omitted.
-- Idempotent via ON CONFLICT (domain) DO NOTHING.
-- ============================================================================

INSERT INTO public.canonical_sources (domain, source_kind, source_name, owner_skill, freshness, description) VALUES
  ('marketplace_seller_public', 'rpc', 'get_marketplace_seller_public', 'marketplace', 'realtime',
   'DEFINER RPC returning a marketplace seller''s PUBLIC profile (16 columns) for anonymous visitors and crawlers. Deliberately omits messenger_username, hive_id and auth_uid: contact PII stays behind the authenticated inquiry flow and tenant topology is never exposed. GRANTed to anon + authenticated; the projection is locked by validate_marketplace_deepwalk_classes.py (MK3).')
ON CONFLICT (domain) DO NOTHING;
