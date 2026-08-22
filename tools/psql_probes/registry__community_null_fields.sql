-- AZ fail_null_field on community: a NULL can only render as a corpse if the schema lets a display
-- column BE null. community_posts declares exactly THREE nullable columns - auth_uid, edited_at,
-- deleted_at (mentions and updated_at are NOT NULL with defaults - asked, not assumed) -
-- and none is a display value: null deleted_at IS the normal live state, null edited_at means
-- never-edited (no chip), auth_uid is an identity key never printed raw. Every display field
-- (author_name, content, category, created_at) is NOT NULL at the schema level, so a null corpse
-- is structurally impossible on this surface. Verified against information_schema each run.
-- expect: nullable_columns \| auth_uid,deleted_at,edited_at
-- forbid: edited_at,[a-z]
-- expect: display_fields_not_null \| t
SELECT 'nullable_columns | ' || string_agg(column_name, ',' ORDER BY column_name)
  FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'community_posts' AND is_nullable = 'YES';
SELECT 'display_fields_not_null | ' || bool_and(is_nullable = 'NO')
  FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'community_posts'
   AND column_name IN ('author_name', 'content', 'category', 'created_at');
