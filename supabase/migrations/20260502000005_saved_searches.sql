-- Saved searches (Phase B1a — storage + apply only)
-- Buyers save filter combos for quick reuse. The email column is captured
-- now so the future digest Edge Function (Phase B1b) doesn't require a
-- second migration. Email digests need pg_cron (Supabase Pro) and Resend
-- domain verification, so we leave that for later.

CREATE TABLE IF NOT EXISTS public.marketplace_saved_searches (
  id            uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  worker_name   text          NOT NULL,
  email         text,         -- optional: future weekly digest target
  search_name   text          NOT NULL,
  section       text,         -- 'parts' | 'training' | 'jobs' | NULL = all
  category      text,         -- specific category | NULL = all in section
  query_text    text,         -- full-text search keyword | NULL
  price_min     numeric(14,2),
  price_max     numeric(14,2),
  last_sent_at  timestamptz,  -- digest cursor (Phase B1b)
  active        boolean       NOT NULL DEFAULT true,
  created_at    timestamptz   NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mkt_saved_search_worker
  ON public.marketplace_saved_searches (worker_name, active);

CREATE INDEX IF NOT EXISTS idx_mkt_saved_search_email
  ON public.marketplace_saved_searches (email)
  WHERE email IS NOT NULL AND active = true;

GRANT SELECT, INSERT, UPDATE, DELETE
  ON public.marketplace_saved_searches TO anon, authenticated;
