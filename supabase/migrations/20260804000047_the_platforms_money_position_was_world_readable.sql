-- ============================================================================================
-- The platform's own money position was readable by anyone
-- ============================================================================================
-- Found 2026-08-04 while walking Q-payment-rails. `credit_treasury` holds exactly one row and it
-- is the whole financial posture of WorkHive:
--
--     authorised_credits = 10,000,000     (the supply cap)
--     issued_credits     =      1,500     (how much money has actually entered the system)
--
-- HOW IT WAS FOUND, stated precisely, because the first version of this sentence was wrong: a live
-- browser read returned status 200 with both numbers -- but that session was Pablo Aguilar, who IS
-- in marketplace_platform_admins, so it proved nothing about an ordinary user. The finding rests on
-- the catalogue instead, and on a rolled-back probe run as a genuine NON-admin (David Velasco):
--     before: nonadmin sees 1 row, authorised=10,000,000 issued=1,500
--     after:  nonadmin sees 0 rows; anon is refused outright; admin still sees both numbers
--
-- The grants said the same thing, one layer down:
--     GRANTS: anon -> SELECT, authenticated -> SELECT
--     POLICY: credit_treasury_read | cmd=SELECT | roles=public | using=(id = 1)
--
-- `using (id = 1)` is not an access rule. There is only one row and its id IS 1, so the predicate
-- is `true` wearing a filter's clothes -- it constrains WHICH row you get, never WHETHER you may
-- have it. Combined with a grant to `public`, every provider, every buyer and every anonymous
-- visitor could read how much money the founder has taken in.
--
-- WHY THIS IS A CONTRADICTION AND NOT A DESIGN CHOICE: the product already treats this number as
-- admin-only. platform-actions.html gates the credit-position card behind platform-admin and says
-- so in its own copy ("Sign in as a platform admin to see the credit position"), and it reads
-- `v_credit_posture` rather than this table precisely because the view is the published surface.
-- But `v_credit_posture` is security_invoker=true, so it inherits the CALLER's privileges -- which
-- means the careful gating on the card was decoration. The base table answered anyone who asked.
--
-- Nothing else depends on the open grant, verified rather than assumed:
--   · functions: issue_credits, retire_credits -- both SECURITY DEFINER, so they run as owner and
--     are untouched by this change (the "a new guard breaks the triggers that already write" class)
--   · views: v_credit_posture only
--   · client code: founder-console.html (retired behind #wh-retired-overlay) is the only reader.
--     platform-actions.html matches on a grep only inside a COMMENT of mine saying it deliberately
--     does NOT read this table raw -- checked, because a grep that matches a comment is how a
--     "reader" gets invented.
--
-- THE FIX: keep the SELECT grant for `authenticated` (the security_invoker view needs the caller
-- to hold it) and let RLS decide, which is what RLS is for. Revoke `anon` outright -- an
-- anonymous visitor has no admin identity to check, so the grant can only ever be wrong.
-- ============================================================================================

revoke select on public.credit_treasury from anon;

-- The view is the PUBLISHED surface, so close it at the surface too. v_credit_posture is
-- security_invoker, so an anonymous reader would otherwise reach it, fail on the inner table, and
-- get back "permission denied for table credit_treasury" -- an error that names an internal table
-- to someone who is not even signed in. A clean refusal at the door beats a leaky one inside.
-- (authenticated KEEPS the view grant: RLS on the base table decides, which is the point.)
revoke select on public.v_credit_posture from anon;

drop policy if exists credit_treasury_read on public.credit_treasury;

create policy credit_treasury_read on public.credit_treasury
  for select
  to authenticated
  using (public.is_marketplace_admin());

-- ── Teeth. A migration that only DECLARES its intent is the thing this platform has been bitten
-- by repeatedly, so assert the outcome from the catalogue instead of trusting the statements.
do $$
declare
  v_anon    boolean;
  v_auth    boolean;
  v_qual    text;
  v_roles   text;
begin
  select has_table_privilege('anon', 'public.credit_treasury', 'SELECT') into v_anon;
  if v_anon then
    raise exception 'mig 47 FAILED: anon still holds SELECT on credit_treasury';
  end if;

  if has_table_privilege('anon', 'public.v_credit_posture', 'SELECT') then
    raise exception 'mig 47 FAILED: anon still holds SELECT on v_credit_posture (the published surface)';
  end if;

  -- authenticated must KEEP the grant, or v_credit_posture (security_invoker) breaks for admins too
  select has_table_privilege('authenticated', 'public.credit_treasury', 'SELECT') into v_auth;
  if not v_auth then
    raise exception 'mig 47 FAILED: authenticated lost SELECT - v_credit_posture would now refuse admins';
  end if;

  select qual, array_to_string(roles, ',')
    into v_qual, v_roles
    from pg_policies
   where tablename = 'credit_treasury' and policyname = 'credit_treasury_read';

  if v_qual is null then
    raise exception 'mig 47 FAILED: the read policy is missing entirely (table would deny everyone)';
  end if;
  if v_qual not ilike '%is_marketplace_admin%' then
    raise exception 'mig 47 FAILED: policy does not consult is_marketplace_admin(), it is: %', v_qual;
  end if;
  if v_roles ilike '%public%' then
    raise exception 'mig 47 FAILED: policy still applies to role public, it is: %', v_roles;
  end if;

  raise notice 'mig 47 OK: treasury is admin-only (policy=%, roles=%); anon revoked, authenticated kept',
    v_qual, v_roles;
end $$;
