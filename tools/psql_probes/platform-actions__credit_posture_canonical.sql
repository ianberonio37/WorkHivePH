-- credit_posture_canonical (P-C tile == DB canonical, 2026-09-05): platform-actions and founder-console
-- paint the service-credit economy (pending top-ups to verify, the ledger, seller trust) from
-- v_service_credit_topups_truth / v_service_credit_ledger_truth, which are auth-scoped views over
-- service_credit_topups / service_credit_ledger. The canonical the tiles rest on is the base tables'
-- own contract: a verified top-up has exactly its ledger entry, statuses and entry kinds stay inside
-- the vocabularies the pages branch on, and no ledger amount is zero (a zero row is a no-op that
-- still counts). Base tables are asserted directly so the recipe is not vacuous under postgres.
-- expect: verified_topups_have_ledger_entries \| t
-- expect: topup_status_vocabulary_held \| t
-- expect: ledger_entry_types_held \| t
-- expect: no_zero_ledger_amounts \| t
SELECT 'verified_topups_have_ledger_entries | ' || ((SELECT count(*) FROM service_credit_topups t
  WHERE t.status = 'verified' AND NOT EXISTS (SELECT 1 FROM service_credit_ledger l WHERE l.ref_kind = 'topup' AND l.ref_id::text = t.id::text)) = 0);
SELECT 'topup_status_vocabulary_held | ' || ((SELECT count(*) FROM service_credit_topups
  WHERE status NOT IN ('pending_verification','verified','rejected','cancelled')) = 0);
SELECT 'ledger_entry_types_held | ' || ((SELECT count(*) FROM service_credit_ledger
  WHERE entry_type NOT IN ('topup','starter_grant','commission','adjustment','refund','payout','spend')) = 0);
SELECT 'no_zero_ledger_amounts | ' || ((SELECT count(*) FROM service_credit_ledger WHERE amount = 0 OR amount IS NULL) = 0);
