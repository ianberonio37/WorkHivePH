-- ★AN ENGINEERING CALCULATION LEAVES A TRAIL (2026-10-28, found by the cube walk of engineering-design.html).
--
-- engineering_calcs is read by the whole hive (engineering_calcs_read: hive_id IN the reader's active hives), and a saved
-- calculation can be a project's evidence (project_links link_type 'engineering_calc'). Yet saving one and deleting one
-- - a HARD delete, "This cannot be undone" - wrote nothing to hive_audit_log: a colleague whose project evidence vanished
-- had no record of who removed it or when. The page calls no trail function, and no trigger on the table wrote one.
--
-- The fix is server-side, so no client path can skip it: the generic audit_shared_change (20261021000001) - the same
-- trail project items, report recipients and API keys keep - records the add, the change (columns only, never the
-- inputs or results themselves) and the removal, names the calculation by its project name, and records nothing for a
-- personal calculation with no hive (a row with no hive belongs to no hive's trail).

drop trigger if exists trg_audit_shared_change on public.engineering_calcs;
create trigger trg_audit_shared_change after insert or delete or update on public.engineering_calcs
  for each row execute function public.audit_shared_change('engineering calculation', 'project_name');
