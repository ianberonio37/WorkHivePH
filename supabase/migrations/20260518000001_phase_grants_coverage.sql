-- Phase 5/4/Fallback table GRANTs (Webhook Idempotency Validator fix)
--
-- The migrations 20260516000003 (anomaly_alerts), 20260516000002 (dialog_state),
-- and the fallback_model_faq migration created tables with RLS enabled but no
-- GRANT statements. Without GRANTs, anon/authenticated roles get 401 even with
-- valid RLS policies because PostgREST checks role-level grants first.
--
-- Adding GRANTs here in a forward-only migration rather than re-editing the
-- originals (which are already in ALLOWED_MULTI_COMMIT allowlist).

grant select, insert, update, delete on anomaly_alerts to anon, authenticated;
grant select, insert, update, delete on dialog_state to anon, authenticated;
grant select, insert, update, delete on fallback_model_faq to anon, authenticated;
