-- Adding a column to a view dropped its security_invoker, and with it the caller's RLS.
--
-- 20260801000001 appended `requires_cert_level` to v_service_catalog_truth so the client could be told a
-- trade is certified-only BEFORE waiting. It recreated the view and never re-declared
-- `security_invoker=on`. Measured live: v_service_provider_truth and v_service_request_truth both carry
-- {security_invoker=on}; v_service_catalog_truth carried NOTHING.
--
-- Without it a view executes with the privileges of its OWNER, not the caller, so row-level security on
-- everything underneath is evaluated as `postgres` and the policies are effectively bypassed for anyone
-- who can read the view. This one is the client-facing service rate card — precisely a surface where
-- "which rows may this person see" is the whole question.
--
-- Nothing about the feature was wrong; the feature quietly took a security property with it on the way
-- past. That is the same shape as rebuilding a guard from a partial read and losing three unrelated
-- rules ([[feedback_i_rebuilt_a_guard_from_a_partial_read]]): a CREATE OR REPLACE re-states the object,
-- so every property not restated is a property removed. It was invisible in review because the
-- migration's diff shows only the column being added.
--
-- Caught by the DB-adoption gate's forward-only floor: D4 adoption fell 56 -> 55 and named the view. A
-- ratchet that reports WHICH item it lost is the difference between a number and a finding.

alter view public.v_service_catalog_truth set (security_invoker = on);

comment on view public.v_service_catalog_truth is
  'Service rate card (client-facing). security_invoker=on is load-bearing: without it the view runs as '
  'its owner and the caller''s RLS is bypassed. It was lost when the view was recreated to add '
  'requires_cert_level (mig 20260801000001) and restored here — restate it in EVERY future CREATE OR '
  'REPLACE of this view.';
