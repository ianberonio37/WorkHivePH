-- T112 (2026-08-26): the same bounce, delivered twice, must be ONE bounce.
--
-- WHAT WAS WRONG. resend-webhook-receiver ends in a bare INSERT into automation_log. Svix (which
-- Resend uses) delivers AT LEAST ONCE and retries on any non-2xx or timeout, and it puts a stable
-- delivery id in the `svix-id` header for exactly this purpose — the receiver READS that header to
-- verify the signature and then throws it away. So a retried delivery, or a duplicate at the
-- provider's discretion, wrote a second bounce row. The consequences are not cosmetic: the
-- report-sender bounce surface would list one failed send twice, and any count built on those rows
-- over-reports how bad deliverability is — a metric that lies in the alarming direction, which is
-- the direction that gets acted on.
--
-- WHY AN INDEX AND NOT A CHECK-BEFORE-INSERT. A SELECT-then-INSERT is a check-and-act race: two
-- concurrent retries both see nothing and both write. Svix retries are usually seconds apart, so
-- the race is small but real, and this codebase has a scar from exactly that shape (the check and
-- the action reading different rows). A unique index cannot race — the second writer is refused by
-- the database, whatever the timing.
--
-- The index is PARTIAL (bounce rows only) and EXPRESSION-based on the svix id parsed out of
-- detail, so it constrains nothing else in a table 191 rows deep and shared by every scheduled job.
-- Rows without a svix id yield NULL, and NULLs never conflict in a unique index — so today's rows,
-- and any future bounce row written before its id is known, are all still accepted.
--
-- The receiver must now (a) write [svix_id=...] into detail and (b) treat a 23505 as "already
-- recorded" and return 200, so the provider stops retrying something that is safely stored.
-- Re-runnable.

CREATE UNIQUE INDEX IF NOT EXISTS automation_log_bounce_svix_once
  ON public.automation_log ((substring(detail from 'svix_id=([A-Za-z0-9_-]+)')))
  WHERE job_name = 'report_email_bounce';

COMMENT ON INDEX public.automation_log_bounce_svix_once IS
  'T112: svix delivers at least once. One delivery id, one bounce row - enforced here rather than '
  'by a check-before-insert, which two concurrent retries can both pass.';
