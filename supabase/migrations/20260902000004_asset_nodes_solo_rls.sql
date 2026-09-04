-- VEHICLE SEED M1 (2026-09-02): SOLO asset_nodes RLS — the blocker for "my car is an asset".
-- pm_assets / pm_completions / inventory_items / logbook all carry the standard solo branch
-- (hive_id IS NULL AND auth_uid = auth.uid()); asset_nodes never did: read REQUIRED a hive, and
-- 20260712000013 re-tightened write to hive-membership unconditionally — so a solo owner
-- (no hive) could neither create nor even SEE their own asset. Phase-5c made hive_id nullable
-- and backfilled solo rows, but the policies were never taught. This adds the same solo branch
-- the sibling tables use, changing NOTHING for hive rows: a solo row is readable/writable ONLY
-- by its owning auth_uid; hive semantics (member read, owner-or-supervisor write) are untouched.

drop policy if exists asset_nodes_read on public.asset_nodes;
create policy asset_nodes_read on public.asset_nodes
  for select using (
    (auth.uid() is not null)
    and (
      (hive_id is null and auth_uid = auth.uid())               -- SOLO: my own asset, no hive
      or hive_id in (select hm.hive_id from public.hive_members hm
                      where hm.auth_uid = auth.uid() and hm.status = 'active')
    )
  );

drop policy if exists asset_nodes_write on public.asset_nodes;
create policy asset_nodes_write on public.asset_nodes
  for all using (
    (auth.uid() is not null)
    and (
      (hive_id is null and auth_uid = auth.uid())               -- SOLO: my own asset, no hive
      or ((auth_uid = auth.uid())
          and hive_id in (select hm.hive_id from public.hive_members hm
                           where hm.auth_uid = auth.uid() and hm.status = 'active'))
      or exists (select 1 from public.hive_members hm
                  where hm.hive_id = asset_nodes.hive_id
                    and hm.auth_uid = auth.uid()
                    and hm.role = 'supervisor' and hm.status = 'active')
    )
  )
  with check (
    (auth.uid() is not null)
    and (
      (hive_id is null and auth_uid = auth.uid())               -- SOLO insert/update stays owned
      or (hive_id in (select hm.hive_id from public.hive_members hm
                       where hm.auth_uid = auth.uid() and hm.status = 'active'))
    )
  );
