-- sync_status_flags_canonical (P-C tile == DB canonical, 2026-09-05): plant-connections paints each
-- integration's status chip from v_external_sync_truth's derived flags (is_active / is_error /
-- is_deleted from sync_status; synced_within_24h from last_synced_at). The canonical the chips rest on
-- is that derivation, so the flags must agree with their own source columns, be mutually exclusive,
-- and the 24h flag must follow the clock - for every row the view exposes.
-- expect: rows_exist \| t
-- expect: status_flags_agree \| t
-- expect: flags_mutually_exclusive \| t
-- expect: within_24h_follows_clock \| t
SELECT 'rows_exist | ' || ((SELECT count(*) FROM v_external_sync_truth) > 0);
SELECT 'status_flags_agree | ' || ((SELECT count(*) FROM v_external_sync_truth
  WHERE is_active <> (sync_status = 'active') OR is_error <> (sync_status = 'error') OR is_deleted <> (sync_status = 'deleted')) = 0);
SELECT 'flags_mutually_exclusive | ' || ((SELECT count(*) FROM v_external_sync_truth
  WHERE (is_active::int + is_error::int + is_deleted::int) > 1) = 0);
SELECT 'within_24h_follows_clock | ' || ((SELECT count(*) FROM v_external_sync_truth
  WHERE last_synced_at IS NOT NULL AND synced_within_24h <> (last_synced_at >= now() - interval '24 hours')) = 0);
