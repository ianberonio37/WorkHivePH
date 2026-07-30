-- =====================================================================
-- SECURITY FIX · a marketplace ADMIN who is also a PARTY could forge their own rating
-- =====================================================================
-- Found 2026-07-29 by a LIVE adversarial probe on the real page, right after the P6
-- second-direction UI shipped. The 7-probe suite missed it because it tested refusals as a
-- NON-admin; the exploit needs an identity that is BOTH admin and provider - which the test
-- persona (Pablo Aguilar) actually is, and which any founder/moderator who also sells services
-- would be in production.
--
-- THE HOLE: guard_service_review() early-returned on `public.is_marketplace_admin()` BEFORE any
-- party/direction check. So a provider-admin could insert direction='client_to_provider' on
-- their OWN completed job. That row is verified_purchase=true by construction and feeds
-- v_service_provider_truth.rating_avg / rating_count / tier -> a self-minted 5-star reputation,
-- and at 25 jobs + 4.5★ a self-minted GOLD tier with its broadcast priority. Proven live: the
-- provider on request c2a13878 wrote a 5★ client_to_provider review of himself while the real
-- client was a different worker (David Velasco).
--
-- THE RULE: the admin bypass is for MODERATION of OTHER people's jobs. The moment the caller is
-- a party to the request, the party/direction rules apply to them like anyone else - being an
-- admin must never let you sit on both sides of your own transaction. The GUC system-write path
-- (seeders/backend) is unchanged: it is not a user identity.

BEGIN;

create or replace function public.guard_service_review()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_req public.service_requests%rowtype;
  v_is_client boolean;
  v_is_provider boolean;
  v_is_party boolean;
begin
  if new.request_id is null then return new; end if;  -- classic listing reviews: existing rules apply
  -- a SERVICE review is verified by construction on EVERY branch (live-caught: the admin
  -- bypass skipped the pin, leaving verified=false on an admin-authored legit review)
  new.verified_purchase := true;
  if auth.uid() is not null then new.reviewer_auth_uid := coalesce(new.reviewer_auth_uid, auth.uid()); end if;

  -- Backend/seeder writes are not a user identity: unchanged bypass.
  if auth.uid() is null
     or current_setting('workhive.service_system_write', true) = 'on' then
    return new;
  end if;

  select r.* into v_req from public.service_requests r where r.id = new.request_id;
  if v_req.id is null then
    raise exception 'Not allowed: unknown service request' using errcode = 'check_violation';
  end if;

  v_is_client   := (v_req.client_auth_uid = auth.uid());
  v_is_provider := v_req.matched_provider_id in (select public.my_service_provider_ids());
  v_is_party    := (v_is_client or v_is_provider);

  -- An admin moderating SOMEONE ELSE'S job keeps the bypass. An admin who is a PARTY to this
  -- job does not - self-dealing is the thing the whole trust chain exists to prevent.
  if public.is_marketplace_admin() and not v_is_party then
    return new;
  end if;

  if v_req.status not in ('completed','settled') then
    raise exception 'Not allowed: reviews open after the job is completed' using errcode = 'check_violation';
  end if;
  if new.direction is null then
    raise exception 'Not allowed: a service review declares its direction' using errcode = 'check_violation';
  end if;
  if new.direction = 'client_to_provider' and not v_is_client then
    raise exception 'Not allowed: only the client reviews the provider' using errcode = 'check_violation';
  end if;
  if new.direction = 'provider_to_client' and not v_is_provider then
    raise exception 'Not allowed: only the matched provider reviews the client' using errcode = 'check_violation';
  end if;

  new.reviewer_auth_uid := auth.uid();       -- attribution pinned server-side
  new.verified_purchase := true;             -- party-of-a-completed-job IS the verification
  return new;
end $$;

comment on function public.guard_service_review() is
  'Birth-time legitimacy guard for bidirectional service reviews: completed job, correct party per direction, once per direction, attribution pinned. The admin bypass covers moderation of OTHER parties jobs ONLY - an admin who is a party to the request is held to the same party rules (self-deal fix 2026-07-29).';

COMMIT;
