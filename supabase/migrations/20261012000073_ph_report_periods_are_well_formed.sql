-- ★A NETWORK REPORT FILED UNDER THE PERIOD "status" (2026-10-12, UFAI edge walk W4589).
--
-- intelligence-report upserts the network-wide report ON its period, and took the period (and its type) from the
-- request body without looking at it: ph_intelligence_reports holds a row whose period and period_type are both
-- "status", and any signed-in caller could overwrite a past month's report by naming its period. The function now
-- accepts only a well-formed period of the right kind (else this month / quarter); this removes the malformed row
-- and lets the table refuse another one from any writer.

begin;

delete from public.ph_intelligence_reports
 where period !~ '^[0-9]{4}-(0[1-9]|1[0-2]|Q[1-4])$'
    or period_type not in ('monthly', 'quarterly');

alter table public.ph_intelligence_reports
  drop constraint if exists ph_intelligence_reports_period_well_formed;
alter table public.ph_intelligence_reports
  add constraint ph_intelligence_reports_period_well_formed check (
    (period_type = 'monthly'   and period ~ '^[0-9]{4}-(0[1-9]|1[0-2])$')
 or (period_type = 'quarterly' and period ~ '^[0-9]{4}-Q[1-4]$')
  );

commit;
