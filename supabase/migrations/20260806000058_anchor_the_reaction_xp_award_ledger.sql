-- ANCHOR THE REACTION-XP AWARD LEDGER IN THE CANONICAL REGISTRY.
--
-- Migration 20260804000049 created `community_reaction_xp_awards` to stop one person toggling a
-- single reaction from minting unbounded XP: one row per post that has been paid the
-- 3-distinct-reactor award, with the primary key doing the once-per-post enforcement. The table
-- landed; its registration did not, so the canonical-anchor gate's un-anchored count went 5 -> 6.
--
-- The registry is not bookkeeping here. This ledger is the ONLY record of which posts have been paid,
-- and it is deliberately unreadable by every client role (RLS on, no policy, grants revoked) — so
-- unless the registry says what it is, who owns it, and what writes it, the next person to meet it
-- sees an opaque table nothing can select from and no statement anywhere of what it guarantees. That
-- is exactly the state in which someone "cleans up" a table that is holding an invariant.
--
-- The same omission showed up twice in one release-gate run: the table was also missing from
-- reset.py, so a reseed would have left award rows behind and a reseeded post would have been treated
-- as already paid. Both halves are closed now; a new table needs BOTH its registry row and its reset
-- entry, and two independent gates say so.

BEGIN;

-- Written as a parenthesised VALUES tuple on purpose. The anchor gate reads migration text for the
-- `('<domain>', '<kind>', '<name>'` shape, which is the house idiom every other registration uses; a
-- SELECT-list form registers the row perfectly well at runtime and is invisible to that reader, so
-- the registry and the gate would disagree about a table that IS anchored. One domain, one tuple —
-- canonical_sources' primary key is (domain) alone, so two tuples sharing a domain in one statement
-- silently drop the second under DO NOTHING.
INSERT INTO public.canonical_sources
  (domain, source_kind, source_name, owner_skill, freshness, contract, description)
VALUES
  ('community_reaction_xp', 'table', 'community_reaction_xp_awards', 'community', 'on_demand',
   jsonb_build_object(
     'key',        jsonb_build_array('post_id'),
     'writes',     'handle_community_reaction_xp() only, a SECURITY DEFINER trigger, with ON CONFLICT DO NOTHING',
     'reads',      'none - RLS is enabled with NO policy and anon/authenticated are revoked, so no client role can select from it',
     'authority',  'the primary key IS the invariant: one row per post means the 3-distinct-reactor award is paid at most once, and race-safe under concurrent reactions',
     'award_rule', 'a post is paid when three DISTINCT people have reacted to it; toggling a reaction off and on again cannot pay it twice'),
   'One row per post that has already been paid the distinct-reactor XP award. Written only by the '
   'reaction trigger; readable by no client role. Deleting a row here re-opens that post to being paid '
   'a second time, so it is an append-only ledger in practice even though nothing enforces that.')
ON CONFLICT (domain) DO NOTHING;

-- The registration is worthless if it drifts from the table it describes. Assert the two agree on the
-- one fact the contract leans on — that post_id is the primary key — so a later migration that widens
-- the key has to come back here and say what the new guarantee is.
DO $$
DECLARE v_pk text;
BEGIN
  SELECT string_agg(a.attname, ',' ORDER BY a.attname)
    INTO v_pk
    FROM pg_index i
    JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY (i.indkey)
   WHERE i.indrelid = 'public.community_reaction_xp_awards'::regclass AND i.indisprimary;
  IF v_pk IS DISTINCT FROM 'post_id' THEN
    RAISE EXCEPTION 'the registry says the key is post_id; the table says %', coalesce(v_pk, '(none)');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM public.canonical_sources
                  WHERE source_name = 'community_reaction_xp_awards') THEN
    RAISE EXCEPTION 'community_reaction_xp_awards is still un-anchored';
  END IF;
  RAISE NOTICE 'community_reaction_xp_awards anchored; key agrees with the contract';
END $$;

COMMIT;
