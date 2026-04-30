-- Grant table-level privileges to anon and authenticated roles for community tables.
-- Migrations do not auto-grant like the Supabase dashboard does.
-- Without these, RLS policies exist but the anon role cannot reach the tables (401).

GRANT SELECT, INSERT, UPDATE, DELETE ON community_posts      TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON community_replies    TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON community_reactions  TO anon, authenticated;
