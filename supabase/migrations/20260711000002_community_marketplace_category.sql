-- ============================================================================
-- X-axis knowledge->commerce (Community PDDA 7th): add a "marketplace" post category
-- ----------------------------------------------------------------------------
-- A member with a part to sell, a service to offer, or a part they're looking for had no native way
-- to flag that in the community — so those needs stayed invisible to the free marketplace. This adds a
-- "Parts / Service / Wanted" category (value 'marketplace') so a commerce-intent post is first-class +
-- filterable, and the composer can point the member to the free marketplace. Purely additive (no XP-model
-- change: only 'safety' is XP-special), so it can't regress existing posts.
-- ============================================================================

ALTER TABLE public.community_posts DROP CONSTRAINT IF EXISTS community_posts_category_check;
ALTER TABLE public.community_posts
  ADD CONSTRAINT community_posts_category_check
  CHECK (category = ANY (ARRAY['general'::text, 'safety'::text, 'technical'::text, 'announcement'::text, 'marketplace'::text]));

COMMENT ON CONSTRAINT community_posts_category_check ON public.community_posts IS
  'Post categories incl. marketplace (Parts/Service/Wanted) — the community knowledge->commerce bridge (Community PDDA 7th).';
