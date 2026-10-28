-- ★A PROJECT'S CHANGES LEAVE A TRAIL (2026-10-28, found by the cube walk of project-manager.html).
--
-- The walk listed every write project-manager.html makes and the trigger that records each one. Covered already:
-- creating a project, item or link (audit_shared_change on insert); an item's title / status / owner / notes / WBS
-- code; acknowledging a progress report (audit_progress_log_acknowledgement); deciding a change order
-- (audit_change_order_decision); removing or restoring a project (guard_and_audit_project_removal). NOT covered, and
-- every one of them read by the whole hive:
--   - editing a project: its name, type, owner, dates, budget, priority, description, its status (planning -> active
--     -> complete ...) and its lessons learned (meta);
--   - an item's progress, planned and actual dates, hours and dependencies;
--   - filing a progress report;
--   - raising a change order (its cost and schedule impact) - only the decision on it was recorded.
-- So a project could be re-planned, re-budgeted or marked complete with no record of who did it.
--
-- The generic audit_shared_change (20261021000001) takes each one - it records the columns that changed (never their
-- free-text values) and records nothing for a save that changed nothing. Deliberately NOT listed: deleted_at (the
-- removal guard records a removal, and one change keeps one trail row), updated_at, sort_order (dragging items into a
-- new order would flood the trail), and the identity columns a row is born with.

drop trigger if exists trg_audit_shared_change on public.projects;
create trigger trg_audit_shared_change after insert
  or update of project_code, name, project_type, status, priority, owner_name, description, start_date, end_date,
               budget_php, meta, closed_at
  on public.projects for each row execute function public.audit_shared_change('project', 'name');

drop trigger if exists trg_audit_shared_change on public.project_items;
create trigger trg_audit_shared_change after insert or delete
  or update of title, status, owner_name, notes, wbs_code, pct_complete, planned_start, planned_end, predecessors,
               estimated_hours, actual_hours, actual_start, actual_end
  on public.project_items for each row execute function public.audit_shared_change('project item', 'title');

drop trigger if exists trg_audit_shared_change on public.project_progress_logs;
create trigger trg_audit_shared_change after insert on public.project_progress_logs
  for each row execute function public.audit_shared_change('progress report', 'log_date');

drop trigger if exists trg_audit_shared_change on public.project_change_orders;
create trigger trg_audit_shared_change after insert on public.project_change_orders
  for each row execute function public.audit_shared_change('change order', 'co_number+title');
