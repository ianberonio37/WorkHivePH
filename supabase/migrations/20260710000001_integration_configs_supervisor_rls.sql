-- CMMS Integrations PDDA — I2/I3: role-scope integration_configs to supervisors.
--
-- BEFORE: the only policy was `integration_configs_hive_rw FOR ALL` gated purely on
-- membership ((auth.uid() is not null) and hive_id in user_hive_ids()). That is the
-- correct TENANT dimension but the wrong ROLE dimension: any active WORKER of the hive
-- could
--   • SELECT the row and read the PLAINTEXT CMMS/ERP `auth_token` (I3), and
--   • UPDATE `endpoint_url` to an attacker host, turning the next cmms-sync into an
--     SSRF that POSTs the stored bearer token to the attacker (I2 pivot).
-- Live-proven pre-fix (2026-07-10, real worker JWT): worker read `SECRET-A-…` and
-- repointed endpoint_url to attacker.example, both HTTP 200.
--
-- AFTER: both reader surfaces (integrations.html, plant-connections.html) are
-- supervisor/IT consoles, so scope the whole table to active supervisors. Mirrors the
-- existing sensor_topic_map_write_supervisor pattern. Edge fns (cmms-sync,
-- cmms-webhook-receiver) read via the service-role key and BYPASS RLS, so machine sync
-- is unaffected. Defense-in-depth: cmms-sync ALSO scopes config_id to the verified hive
-- at the query layer (I1 BOLA fix), independent of this policy.

drop policy if exists integration_configs_hive_rw on integration_configs;

create policy integration_configs_supervisor_all on integration_configs
  for all
  using (
    auth.uid() is not null and exists (
      select 1 from hive_members hm
      where hm.hive_id  = integration_configs.hive_id
        and hm.auth_uid = auth.uid()
        and hm.role     = 'supervisor'
        and hm.status   = 'active'
    )
  )
  with check (
    auth.uid() is not null and exists (
      select 1 from hive_members hm
      where hm.hive_id  = integration_configs.hive_id
        and hm.auth_uid = auth.uid()
        and hm.role     = 'supervisor'
        and hm.status   = 'active'
    )
  );
