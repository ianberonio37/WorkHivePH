-- reputation_defined: the reputation card's numbers have stated DEFINITIONS and the RPC enforces
-- them — public posts only (public = true), soft-deleted excluded (deleted_at IS NULL), reactions
-- RECEIVED via join to the author's public posts, and no hidden time window (all-time).
-- expect: public_predicate \| t
-- expect: deleted_excluded \| t
-- expect: reactions_via_join \| t
-- expect: no_window_filter \| t
SELECT 'public_predicate | '  || (prosrc ILIKE '%public = true%')       FROM pg_proc WHERE proname='get_community_reputation';
SELECT 'deleted_excluded | '  || (prosrc ILIKE '%deleted_at IS NULL%')  FROM pg_proc WHERE proname='get_community_reputation';
SELECT 'reactions_via_join | '|| (prosrc ILIKE '%community_reactions%' AND prosrc ILIKE '%JOIN%community_posts%') FROM pg_proc WHERE proname='get_community_reputation';
SELECT 'no_window_filter | '  || (prosrc NOT ILIKE '%created_at >%' AND prosrc NOT ILIKE '%interval%') FROM pg_proc WHERE proname='get_community_reputation';
