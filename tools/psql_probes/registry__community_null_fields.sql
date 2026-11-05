-- AZ fail_null_field on community: a NULL can only render as a corpse if the schema lets a display
-- column BE null. community_posts declares exactly THREE nullable columns - auth_uid, edited_at,
-- deleted_at (mentions and updated_at are NOT NULL with defaults - asked, not assumed) -
-- and none is a display value: null deleted_at IS the normal live state, null edited_at means
-- never-edited (no chip), auth_uid is an identity key never printed raw. Every display field
-- (author_name, content, category, created_at) is NOT NULL at the schema level, so a null corpse
-- is structurally impossible on this surface. Verified against information_schema each run.
-- D3 (20261016000001) added deleted_by beside deleted_at: who deleted a row, an identity key never printed, null
-- while the row is live - the same kind as auth_uid, so the claim above holds with four.
-- GJ M9 G-MOD (20261106000003) added the moderation record beside them - moderated_at, moderated_by, moderation_note,
-- moderation_outcome: null means the post was never moderated, and the page shows a moderation line only when one exists
-- (my_moderation_news reads decided rows only), so a null renders nothing, never a corpse. Eight, and none a display gap.
-- expect: nullable_columns \| auth_uid,deleted_at,deleted_by,edited_at,moderated_at,moderated_by,moderation_note,moderation_outcome
-- forbid: moderation_outcome,[a-z]
-- expect: display_fields_not_null \| t
SELECT 'nullable_columns | ' || string_agg(column_name, ',' ORDER BY column_name)
  FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'community_posts' AND is_nullable = 'YES';
SELECT 'display_fields_not_null | ' || bool_and(is_nullable = 'NO')
  FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'community_posts'
   AND column_name IN ('author_name', 'content', 'category', 'created_at');
