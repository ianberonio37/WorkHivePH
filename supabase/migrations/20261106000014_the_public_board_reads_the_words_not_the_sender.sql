-- ★THE PUBLIC BOARD WOULD HAVE PUBLISHED WHO SENT EACH ITEM (2026-11-06, GJ M10 premise check of G-ESC).
--
-- The roadmap board (feedback/index.html) shows the feedback items WorkHive chose to publish. It read them straight off
-- platform_feedback through the policy "feedback public reads published" (is_public = true), and both client roles held
-- SELECT on EVERY column. The page asked for seven harmless ones; the API answered whatever a caller asked for. So the
-- first item the founder publishes hands any visitor - no account needed - the sender's contact_email, auth_uid,
-- worker_name, hive_id and user_agent, and the founder's internal admin_note. validate_public_read_surface had
-- listed the table as "the public branch is intentional": that decision was about which ROWS are public, never about
-- which COLUMNS - the same gap as M9's seller contact (20261106000002). Production held 0 public items on 2026-11-06,
-- so nothing had leaked yet; it is closed before the first one.
--
--   1. public_feedback_board(): a definer read of the public items carrying only what the board shows - the words, the
--      kind, the status and WHEN that status was set, the votes. Never the sender, never the founder's note.
--   2. The table's public-read policy is dropped and anon's read of the table goes with it. A signed-in member reads no
--      feedback row directly either (the founder console reads as a platform admin, unchanged); their own reports come
--      back through my_feedback_outcomes(), as before. Anon keeps INSERT - the feedback button posts return=minimal.
--   3. status_at: when an item's status was last set, stamped on every status change, so the board says "resolved
--      Nov 6" instead of an undated pill (the M10 premise's fourth point).

BEGIN;

ALTER TABLE public.platform_feedback ADD COLUMN IF NOT EXISTS status_at timestamptz;
UPDATE public.platform_feedback
   SET status_at = coalesce(resolved_at, triaged_at, created_at)
 WHERE status_at IS NULL;
ALTER TABLE public.platform_feedback ALTER COLUMN status_at SET DEFAULT now();

CREATE OR REPLACE FUNCTION public.tg_platform_feedback_status_at()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'public'
AS $function$
BEGIN
  IF TG_OP = 'INSERT' THEN
    NEW.status_at := now();
  ELSIF NEW.status IS DISTINCT FROM OLD.status THEN
    NEW.status_at := now();
  ELSE
    NEW.status_at := OLD.status_at;   -- a vote or a note is not a status change
  END IF;
  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_platform_feedback_status_at ON public.platform_feedback;
CREATE TRIGGER trg_platform_feedback_status_at
  BEFORE INSERT OR UPDATE ON public.platform_feedback
  FOR EACH ROW EXECUTE FUNCTION public.tg_platform_feedback_status_at();

-- 1. the board's read: the words, never the sender
CREATE OR REPLACE FUNCTION public.public_feedback_board()
 RETURNS TABLE (id uuid, created_at timestamptz, kind text, subject text, body text, status text, status_at timestamptz,
                upvotes integer)
 LANGUAGE sql
 STABLE
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
  SELECT f.id, f.created_at, f.kind, f.subject, f.body, f.status, f.status_at, f.upvotes
    FROM public.platform_feedback f
   WHERE f.is_public
   ORDER BY f.upvotes DESC, f.created_at DESC, f.id
   LIMIT 201;   -- the board shows 200; a 201st row is how it knows to say there are more
$function$;

REVOKE ALL ON FUNCTION public.public_feedback_board() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.public_feedback_board() TO anon, authenticated, service_role;

-- 2. nobody reads a published item's row directly any more
DROP POLICY IF EXISTS "feedback public reads published" ON public.platform_feedback;
REVOKE SELECT ON public.platform_feedback FROM anon;

-- 4. a visitor reads their OWN votes, never everyone's tokens. The board remembered a visitor's votes by a random token in
--    their browser and read them back from platform_feedback_votes, whose read policy was `true`: anyone could list every
--    visitor's token, and toggle_feedback_upvote takes a token, so anyone could take back anyone's vote. The board now
--    asks my_feedback_votes(its own token); the table is read by no client.
CREATE OR REPLACE FUNCTION public.my_feedback_votes(p_voter_token text)
 RETURNS TABLE (feedback_id uuid)
 LANGUAGE sql
 STABLE
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
  SELECT v.feedback_id
    FROM public.platform_feedback_votes v
   WHERE length(coalesce(p_voter_token, '')) >= 16 AND v.voter_token = p_voter_token
   LIMIT 500;   -- one visitor's votes; the board holds 200 items
$function$;

REVOKE ALL ON FUNCTION public.my_feedback_votes(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.my_feedback_votes(text) TO anon, authenticated, service_role;

DROP POLICY IF EXISTS "anon vote read" ON public.platform_feedback_votes;
REVOKE SELECT ON public.platform_feedback_votes FROM anon, authenticated;

COMMIT;
