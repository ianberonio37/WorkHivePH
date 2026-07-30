-- TB-RATE-platform-feedback-identity-bucket.sql
--
-- `check_platform_feedback_rate_limit` is the second of the four guards no registered gate names (§12.1). It
-- allows 5 submissions per hour per identity, where identity is
--
--     COALESCE(NEW.auth_uid::text, NEW.worker_name, NEW.contact_email, 'anonymous')
--
-- and `platform_feedback` is ANON-WRITABLE (policy `feedback anon submit`, gated only on
-- is_public IS NOT TRUE / status='new' / no admin fields). So for an unauthenticated submitter the bucket key
-- is a field the CLIENT supplies.
--
-- WHAT THIS CELL ASSERTS is the part that is unambiguously correct: with a STABLE identity the limit holds —
-- five accepted, the sixth refused with 23P01. That is the guard's real contribution and nothing was locking
-- it.
--
-- WHAT THIS CELL DELIBERATELY DOES NOT ASSERT is the evasion. Probed live: six submissions with a DIFFERENT
-- worker_name each time were ALL accepted, because each name is its own bucket
-- ([[feedback_free_text_identity_is_a_claim]] — the same class as filing a report under a colleague's name).
-- That is recorded as an open finding in the roadmap with a product fork for Ian, and it is NOT encoded as an
-- expected value here, because baking "renaming evades the limit" into the bank would make the eventual FIX
-- look like a regression. A test must not ratify a weakness it happens to observe.
--
-- The sqlstate is asserted, not just the refusal: 23P01 is the code this guard chose so the client can show a
-- friendly toast. A different code would mean something else refused, and "something said no" is not evidence
-- the RATE LIMIT said no — the mistake this probe made on its first run, when a wrong column name (42703)
-- looked exactly like "the limit is not evadable".
begin;

set local role anon;

do $probe$
declare accepted int := 0; refused_code text := '(none)';
begin
  for i in 1..6 loop
    begin
      insert into public.platform_feedback(worker_name, kind, subject, body, status, is_public)
      values ('TB Rate Stable', 'idea', 'probe', 'stable #' || i, 'new', false);
      accepted := accepted + 1;
    exception when others then
      refused_code := sqlstate;
    end;
  end loop;
  -- Five, not six: the guard refuses at `>= 5` already-present rows, so the SIXTH is the one that fails.
  raise notice 'RESULT stable_identity_accepted=%', accepted;
  raise notice 'RESULT sixth_refused_sqlstate=%', refused_code;
end
$probe$;

rollback;
