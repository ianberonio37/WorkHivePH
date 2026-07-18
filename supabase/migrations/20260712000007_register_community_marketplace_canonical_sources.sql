-- ============================================================================
-- Register the Community/Marketplace Deep-Arc engine objects (v_*_truth + get_* RPCs)
-- in canonical_sources, so validate_canonical_anchor.py's engine_anchor ratchet
-- sees them (8 new engine objects were created across the arc without a matching
-- canonical_sources anchor, driving un-anchored count 2 -> 10).
--
-- canonical_sources PK is `domain`; `contract` has a DEFAULT so it is omitted here.
-- Idempotent via ON CONFLICT (domain) DO NOTHING.
-- ============================================================================

INSERT INTO public.canonical_sources (domain, source_kind, source_name, owner_skill, freshness, description) VALUES
  ('community_reputation_truth', 'view', 'v_community_reputation_truth', 'community', 'realtime',
   'Within-hive canonical community reputation reader (INVOKER, RLS-scoped) bridging community_xp/posts/replies to per-member reputation + trust_tier.'),
  ('community_reputation', 'rpc', 'get_community_reputation', 'community', 'realtime',
   'DEFINER RPC returning a members cross-hive PORTABLE, public-scoped community reputation for marketplace/person-cards.'),
  ('community_reputation_by_auth', 'rpc', 'get_community_reputation_by_auth', 'community', 'realtime',
   'auth.uid-scoped community reputation RPC (BOLA-safe caller-identity path over community_xp).'),
  ('hive_trade_peers', 'rpc', 'get_hive_trade_peers', 'community', 'realtime',
   'DEFINER RPC returning same-trade peer discovery for a hive over self-only skill_badges RLS (member-authz gated, fail-closed).'),
  ('marketplace_trust_badges', 'rpc', 'get_marketplace_trust_badges', 'marketplace', 'realtime',
   'Batch DEFINER RPC returning public-scoped seller trust tier for a set of sellers, used by the marketplace grid trust chip.'),
  ('marketplace_price_comps', 'rpc', 'get_marketplace_price_comps', 'marketplace', 'realtime',
   'Comparable-price lookup for a marketplace listing (code computes the comp; WAT split, never a fabricated price).'),
  ('marketplace_parts_for_my_assets', 'rpc', 'get_marketplace_parts_for_my_assets', 'marketplace', 'realtime',
   'Surfaces published marketplace parts matching the callers hive assets (Parts-for-your-assets discovery rail).'),
  ('marketplace_saved_search_matches', 'rpc', 'get_saved_search_matches', 'marketplace', 'realtime',
   'Returns new listings matching a members saved marketplace searches (saved-search new-match badge).')
ON CONFLICT (domain) DO NOTHING;
