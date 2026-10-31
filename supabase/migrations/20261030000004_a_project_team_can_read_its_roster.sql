-- A PROJECT'S OWN TEAM COULD NOT READ WHO IS ON IT - THE SAFETY OFFICER INCLUDED.
--
-- Found 2026-10-30 walking Wave HS lens L1 on project-manager.html: a supervisor's Roles pane listed the five people on
-- "Instrument air upgrade" (owner, planner, safety officer, cost engineer, reviewer, each "by <who> <when>"); a worker's
-- listed one name, "Danilo Pascual from project header". project_roles_supervisor_all (20260712000020, rewritten in
-- 20261020000003) is FOR ALL - it was written to stop a worker ASSIGNING or REMOVING grants (an exploit measured then),
-- and as a side effect it took every READ away from everyone but supervisors. The intended read rule is already stated
-- in tools/tenant_declarations.mjs: project_roles is read by "project membership, not hive membership". Nothing granted
-- it, so Kristine Aquino, the safety officer on the job, could not see that she was - nor who the planner was.
--
-- THE RULE: a member may READ the roles of a project they are on - they hold a role on it, or they own it. Writes stay
-- with the hive's supervisors (project_roles_supervisor_all is unchanged). Membership is answered by a SECURITY DEFINER
-- helper, so the read policy never queries the table it guards (a policy on project_roles that reads project_roles
-- recurses).

CREATE OR REPLACE FUNCTION public.user_project_ids()
RETURNS SETOF uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT pr.project_id
    FROM public.project_roles pr
    JOIN public.hive_members hm ON hm.hive_id = pr.hive_id AND hm.worker_name = pr.worker_name
   WHERE hm.auth_uid = auth.uid() AND hm.status = 'active' AND pr.deleted_at IS NULL
  UNION
  SELECT p.id
    FROM public.projects p
    JOIN public.hive_members hm ON hm.hive_id = p.hive_id
   WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
     AND (p.auth_uid = auth.uid() OR p.owner_name = hm.worker_name)
$$;

-- anon too: Supabase's default privileges grant anon EXECUTE on a new public function, which FROM PUBLIC does not remove
REVOKE ALL ON FUNCTION public.user_project_ids() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.user_project_ids() TO authenticated;

DROP POLICY IF EXISTS project_roles_project_member_read ON public.project_roles;
-- TO authenticated, not public: anon may not execute user_project_ids(), and a policy anon evaluates would make its
-- SELECT on project_roles raise "permission denied for function" instead of returning nothing (index__anon_zero_rows
-- caught exactly that on this migration's first version - the same trap 20260907000005 recorded for the seller policy)
CREATE POLICY project_roles_project_member_read ON public.project_roles
  AS PERMISSIVE FOR SELECT TO authenticated
  USING ((SELECT auth.uid()) IS NOT NULL AND project_id IN (SELECT public.user_project_ids()));
