-- Engineering-Design deep-arc P2 / I-2 + I-4: write-side tenant isolation for engineering_calcs.
--
-- Problem: engineering_calcs_write was `FOR ALL` with
--   USING      (auth.uid() IS NOT NULL AND (auth_uid = auth.uid() OR auth_uid IS NULL))
--   WITH CHECK (auth.uid() IS NOT NULL)
-- so any authenticated user could (a) INSERT a row attributed to ANOTHER user or into
-- ANOTHER hive (WITH CHECK never checked auth_uid or membership), and (b) UPDATE/DELETE
-- any unowned (auth_uid IS NULL) row. The client now always stamps auth_uid = auth.uid()
-- (saveCalc/saveWithBomSow) and every existing row already has a non-null auth_uid + hive_id
-- (0 nulls verified 2026-07-08), so tightening is safe with no backfill and no orphaned rows.
--
-- Fix: split the single FOR ALL policy into explicit INSERT / UPDATE / DELETE policies that
-- each assert the row is owned by the caller (auth_uid = auth.uid()) and, for writes that
-- carry a hive, that the caller is an active member of that hive. Solo rows (hive_id IS NULL)
-- stay owner-scoped. The read policy is already correct (membership-gated) and is left as-is.
--
-- engineering-design.js is the SOLE browser writer (utils.js only labels the table;
-- analytics-orchestrator reads it via the service role, which bypasses RLS).

DROP POLICY IF EXISTS "engineering_calcs_write" ON engineering_calcs;

-- INSERT: may only create a row you own, in a hive you actively belong to (or solo).
DROP POLICY IF EXISTS "engineering_calcs_insert" ON engineering_calcs;
CREATE POLICY "engineering_calcs_insert" ON engineering_calcs
  FOR INSERT
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND auth_uid = auth.uid()
    AND (
      hive_id IS NULL
      OR hive_id IN (
        SELECT hm.hive_id FROM hive_members hm
        WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
      )
    )
  );

-- UPDATE: only your own rows; the updated row must stay yours + in a hive you belong to.
DROP POLICY IF EXISTS "engineering_calcs_update" ON engineering_calcs;
CREATE POLICY "engineering_calcs_update" ON engineering_calcs
  FOR UPDATE
  USING (auth.uid() IS NOT NULL AND auth_uid = auth.uid())
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND auth_uid = auth.uid()
    AND (
      hive_id IS NULL
      OR hive_id IN (
        SELECT hm.hive_id FROM hive_members hm
        WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
      )
    )
  );

-- DELETE: object-level authorization — only the owner may delete (no null-owner escape hatch).
DROP POLICY IF EXISTS "engineering_calcs_delete" ON engineering_calcs;
CREATE POLICY "engineering_calcs_delete" ON engineering_calcs
  FOR DELETE
  USING (auth.uid() IS NOT NULL AND auth_uid = auth.uid());
