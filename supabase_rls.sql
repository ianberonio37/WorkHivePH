-- ══════════════════════════════════════════════════════════════════════
-- WorkHive — Supabase Row Level Security Policies
-- ══════════════════════════════════════════════════════════════════════
--
-- PREREQUISITE: These policies use auth.uid(). They only work once you
-- implement Supabase Auth in the app (anonymous sign-in or email).
--
-- Step 1 — Add auth to the app:
--   On every page, call supabase.auth.signInAnonymously() on first load
--   and persist the session. Map worker_name to the auth user via
--   user_metadata: { worker_name: 'Alice' }
--
-- Step 2 — Add a `user_id uuid references auth.users(id)` column to
--   every table below and backfill it from existing worker_name data.
--
-- Step 3 — Run this file in the Supabase SQL editor.
-- ══════════════════════════════════════════════════════════════════════

-- ── Enable RLS on all tables ─────────────────────────────────────────
ALTER TABLE logbook               ENABLE ROW LEVEL SECURITY;
ALTER TABLE parts_records         ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory_items       ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE assets                ENABLE ROW LEVEL SECURITY;
ALTER TABLE checklist_records     ENABLE ROW LEVEL SECURITY;
ALTER TABLE hive_members          ENABLE ROW LEVEL SECURITY;
ALTER TABLE hives                 ENABLE ROW LEVEL SECURITY;

-- ══════════════════════════════════════════════════════════════════════
-- LOGBOOK
-- Rules: owner can do anything. Hive members can read entries in their
--        shared hive (hive_id matches). No one else sees anything.
-- ══════════════════════════════════════════════════════════════════════
CREATE POLICY "logbook: owner full access"
  ON logbook FOR ALL
  USING  (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "logbook: hive members can read"
  ON logbook FOR SELECT
  USING (
    hive_id IS NOT NULL AND
    EXISTS (
      SELECT 1 FROM hive_members
      WHERE hive_members.hive_id = logbook.hive_id
        AND hive_members.user_id = auth.uid()
    )
  );

-- ══════════════════════════════════════════════════════════════════════
-- PARTS_RECORDS
-- ══════════════════════════════════════════════════════════════════════
CREATE POLICY "parts_records: owner full access"
  ON parts_records FOR ALL
  USING  (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "parts_records: hive members can read"
  ON parts_records FOR SELECT
  USING (
    hive_id IS NOT NULL AND
    EXISTS (
      SELECT 1 FROM hive_members
      WHERE hive_members.hive_id = parts_records.hive_id
        AND hive_members.user_id = auth.uid()
    )
  );

-- ══════════════════════════════════════════════════════════════════════
-- INVENTORY_ITEMS
-- Rules: strictly private — only the owner sees their own inventory.
-- ══════════════════════════════════════════════════════════════════════
CREATE POLICY "inventory_items: owner only"
  ON inventory_items FOR ALL
  USING  (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- Supervisors need to read team members' inventory for the stock alert.
-- Grant SELECT to hive-mates (read-only, cannot modify another worker's stock).
CREATE POLICY "inventory_items: hive supervisor can read"
  ON inventory_items FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM hive_members sup
      JOIN hive_members member ON member.hive_id = sup.hive_id
      WHERE sup.user_id = auth.uid()
        AND sup.role = 'supervisor'
        AND member.user_id = inventory_items.user_id
    )
  );

-- ══════════════════════════════════════════════════════════════════════
-- INVENTORY_TRANSACTIONS
-- Follows the owning inventory_item.
-- ══════════════════════════════════════════════════════════════════════
CREATE POLICY "inventory_transactions: owner only"
  ON inventory_transactions FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM inventory_items
      WHERE inventory_items.id = inventory_transactions.item_id
        AND inventory_items.user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM inventory_items
      WHERE inventory_items.id = inventory_transactions.item_id
        AND inventory_items.user_id = auth.uid()
    )
  );

-- ══════════════════════════════════════════════════════════════════════
-- ASSETS
-- Private per worker. No cross-hive visibility needed (assets are
-- registered per worker, not per hive).
-- ══════════════════════════════════════════════════════════════════════
CREATE POLICY "assets: owner only"
  ON assets FOR ALL
  USING  (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- ══════════════════════════════════════════════════════════════════════
-- CHECKLIST_RECORDS
-- Owner can do anything. Hive members can read (to see in feed).
-- ══════════════════════════════════════════════════════════════════════
CREATE POLICY "checklist_records: owner full access"
  ON checklist_records FOR ALL
  USING  (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "checklist_records: hive members can read"
  ON checklist_records FOR SELECT
  USING (
    hive_id IS NOT NULL AND
    EXISTS (
      SELECT 1 FROM hive_members
      WHERE hive_members.hive_id = checklist_records.hive_id
        AND hive_members.user_id = auth.uid()
    )
  );

-- ══════════════════════════════════════════════════════════════════════
-- HIVE_MEMBERS
-- Any authenticated user can read hive_members for hives they belong to.
-- Only supervisors can insert/update/delete members.
-- ══════════════════════════════════════════════════════════════════════
CREATE POLICY "hive_members: members can read own hive"
  ON hive_members FOR SELECT
  USING (
    user_id = auth.uid() OR
    EXISTS (
      SELECT 1 FROM hive_members self
      WHERE self.hive_id = hive_members.hive_id
        AND self.user_id = auth.uid()
    )
  );

CREATE POLICY "hive_members: anyone can join (insert themselves)"
  ON hive_members FOR INSERT
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "hive_members: supervisor can update roles"
  ON hive_members FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM hive_members sup
      WHERE sup.hive_id = hive_members.hive_id
        AND sup.user_id = auth.uid()
        AND sup.role = 'supervisor'
    )
  );

CREATE POLICY "hive_members: leave or supervisor can remove"
  ON hive_members FOR DELETE
  USING (
    user_id = auth.uid() OR
    EXISTS (
      SELECT 1 FROM hive_members sup
      WHERE sup.hive_id = hive_members.hive_id
        AND sup.user_id = auth.uid()
        AND sup.role = 'supervisor'
    )
  );

-- ══════════════════════════════════════════════════════════════════════
-- HIVES (the hive registry table)
-- Anyone can read hives (needed to join via code).
-- Only supervisors (the creator) can update or delete.
-- ══════════════════════════════════════════════════════════════════════
CREATE POLICY "hives: anyone can read"
  ON hives FOR SELECT
  USING (true);

CREATE POLICY "hives: authenticated user can create"
  ON hives FOR INSERT
  WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "hives: creator can update"
  ON hives FOR UPDATE
  USING (created_by = auth.uid());

CREATE POLICY "hives: creator can delete"
  ON hives FOR DELETE
  USING (created_by = auth.uid());
