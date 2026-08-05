-- ═══════════════════════════════════════════════════════════════════════════════════════════════
-- ANYONE AT ALL COULD READ THE VOICE TRANSCRIPTS
--
-- Found while re-verifying the BA-invariant "grant_matches_policy" cell — the rule that a table
-- grant with no caller-aware policy IS a public table, whatever the UI does. Fourteen tables in
-- public have SELECT granted with RLS switched off. Thirteen are reference and cache data with no
-- tenant column: embeddings, TTS cache, terminology, benchmarks, SLO targets, avatar animations,
-- platform-aggregate reports (hive_count, wo_count — no per-tenant rows).
--
-- The fourteenth is voice_response_queue:
--
--     id · worker_id · session_id · transcript · response · status · created_at · sent_at
--
-- What a person said out loud, and what the assistant said back, keyed to who said it. Measured:
--
--     authenticated_can_select = true
--     anon_can_select          = true      <-- a signed-out visitor, not merely another user
--     rls                      = false
--
-- Nothing has leaked: the table is empty, and `authenticated` cannot INSERT — only the edge function
-- writes it, through the service role. So this is a grant waiting for its first row. The moment the
-- voice feature stores one transcript, it is world-readable, across every hive and to people with no
-- account at all.
--
-- MY OWN SWEEP NEARLY MISSED IT, and the reason is worth recording where the next sweep will meet
-- it. I screened the fourteen tables for "sensitive" columns with a pattern of
-- auth_uid|hive_id|worker_name|amount|price|balance|email|phone|contact. This table's owner column is
-- `worker_id`, and its payload columns are `transcript` and `response` — none of them match. The
-- screen reported 0 sensitive columns on all fourteen and I would have passed the cell on that. What
-- caught it was reading the column list of the three whose NAMES sounded scoped. A pattern over
-- column names is a hint, never the check.
--
-- Same class as mig 47 (the platform's money position, world-readable through an ops view) and mig 48
-- (any signed-in user could list the admins): a grant issued for convenience, with no policy behind
-- it, on a table whose contents nobody re-read after the schema grew.
--
-- This is the question mig 43 wrote down and deliberately left open. Closing the anon WRITE hole, it
-- said: "SELECT is deliberately left alone. Read exposure on these is a separate question with a
-- separate answer." This migration is that answer, for the one table where the answer matters.
--
-- THE FIX, AND WHY IT IS NOT A BLANKET REVOKE. My first cut revoked SELECT from anon AND from
-- authenticated. That refused everyone — including the person whose own words they are — and it broke
-- the phase-6 reachability test. The queue exists so a worker's offline question can be answered when
-- they come back online; reading your own pending turns is the feature, not the leak. So:
--
--   anon           SELECT revoked outright — a signed-out visitor has no stake in anyone's voice turns
--   authenticated  grant KEPT, and now FILTERED by RLS to the caller's own rows
--   service_role   unaffected (bypasses RLS) — the edge function writes and drains the queue
--
-- The distinction matters: a revoke answers "may this role touch the table at all", a policy answers
-- "which rows". Reaching for the revoke when the real answer is a policy is how a legitimate surface
-- gets broken in the name of a fix.
-- ═══════════════════════════════════════════════════════════════════════════════════════════════

alter table public.voice_response_queue enable row level security;

revoke select on public.voice_response_queue from anon;

-- Read your own turns and nobody else's. worker_id is the owner column; it holds the caller's
-- auth uid, so the predicate is caller-aware rather than a constant — the exact property the
-- grant_matches_policy invariant exists to demand.
drop policy if exists voice_queue_own_rows on public.voice_response_queue;
create policy voice_queue_own_rows on public.voice_response_queue
  for select to authenticated
  using (worker_id = auth.uid());

-- Deliberately NO insert/update/delete policy for authenticated: the queue is written and drained by
-- the edge function under the service role, and a client that could write here could put words in
-- another person's mouth.

comment on table public.voice_response_queue is
  'Voice turns: what a person said and what the assistant replied. RLS: readers see only their own '
  'rows (worker_id = auth.uid()); writes are service-role only, from the voice edge function. '
  'Was granted SELECT to anon AND authenticated with RLS off until mig 50 (2026-08-05).';
