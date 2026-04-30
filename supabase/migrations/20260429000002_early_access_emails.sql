-- Early Access Email Signups
-- Replaces the client-side Make.com webhook (exposed token) with a
-- direct Supabase insert using the public anon key (safe to expose).
CREATE TABLE IF NOT EXISTS early_access_emails (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email      text NOT NULL,
  signed_up_at timestamptz DEFAULT now(),
  source     text DEFAULT 'landing_page'
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_early_access_email
  ON early_access_emails (lower(email));

-- Allow anon inserts from the landing page (no auth required)
ALTER TABLE early_access_emails ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon can insert early access email" ON early_access_emails;
CREATE POLICY "anon can insert early access email"
  ON early_access_emails FOR INSERT
  WITH CHECK (true);

-- Only service role can read (admin dashboard access only)
DROP POLICY IF EXISTS "service role can read early access emails" ON early_access_emails;
CREATE POLICY "service role can read early access emails"
  ON early_access_emails FOR SELECT
  USING (auth.role() = 'service_role');
