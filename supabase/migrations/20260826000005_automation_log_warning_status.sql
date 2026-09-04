-- T112 (2026-08-26): the bounce lane would have stored NOTHING, and said it stored everything.
--
-- FOUND while building the idempotency proof, not by looking for it. automation_log carries
--   CHECK (status = ANY (ARRAY['success','failed','skipped']))
-- and resend-webhook-receiver writes 'failure' for a bounce and 'warning' for a delay. Neither is
-- an allowed value, so every bounce INSERT would fail with 23514 — and the original code did not
-- read the insert error at all (`await db.from(...).insert({...})`, no destructuring), so
-- supabase-js would return the error into the void and the function would answer 200 "recorded".
-- Resend would be told the bounce was safely stored, never retry, and the sender-side bounce
-- surface would sit permanently empty while reporting success at every layer.
--
-- It has never fired because the receiver fails closed without its signing secret. It would have
-- fired on the FIRST real bounce after that secret was set — the worst possible moment to discover
-- it, because everything upstream would look healthy.
--
-- TWO HALVES OF THE FIX. The receiver stops saying 'failure' when the vocabulary word is 'failed'
-- (a typo, and no schema can rescue a caller from inventing a word). But a delayed delivery is
-- genuinely NOT a failure and not a skip: forcing it into 'failed' would over-report real
-- deliverability problems, and into 'skipped' would hide a real one. So the vocabulary GROWS by
-- one honest value rather than the truth being bent to fit it.
--
-- Additive and safe: no existing row uses 'warning' (191 rows, only 'success' and 'failed'
-- present), so nothing is invalidated and every current writer keeps working. Re-runnable.

ALTER TABLE public.automation_log DROP CONSTRAINT IF EXISTS automation_log_status_check;

ALTER TABLE public.automation_log
  ADD CONSTRAINT automation_log_status_check
  CHECK (status = ANY (ARRAY['success', 'failed', 'skipped', 'warning']));

COMMENT ON CONSTRAINT automation_log_status_check ON public.automation_log IS
  'T112: warning added for states that are neither a completed failure nor a skip - a delayed '
  'email delivery being the first. Forcing those into failed over-reports real problems.';
