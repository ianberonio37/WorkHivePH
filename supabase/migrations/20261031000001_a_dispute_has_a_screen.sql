-- A DISPUTE HAS A SCREEN (Wave JS, J27 walked from the provider's side, 2026-10-31).
--
-- A client can report a problem on a job the provider marked done (raise_service_objection), and that stops
-- the job settling. Adjudication exists on the server - apply_dispute_adjustment returns the credits the client
-- paid, reverses the commission and takes back any cashback, with compensating ledger entries - but since
-- 2026-08-03, when the "Open disputes" card went with the ghost marketplace_disputes table, no screen calls it.
-- Walked with two real reports (a Lucena client on a Manila provider, a Dela Cruz client on a Baguio provider):
-- the admin found each only as a trail line ("Changed service request"), the provider read "WorkHive is
-- reviewing it", and nothing anyone could press would ever end the review.
--
-- Two functions, both platform-admin only:
--   admin_disputed_jobs()  - the queue: every disputed job, with both parties, when and why it was reported, and
--                            whether it has been reviewed. An admin is not a party, so RLS shows them none of it.
--   adjudicate_service_dispute(request, note, side) - for the client, calls apply_dispute_adjustment unchanged (mig 41 patched its
--                            balance bounds; it is not redefined here) and then records the outcome as a job event,
--                            which both parties can read (service_job_events_party_read). The adjustment alone left
--                            no trace either of them could see.

create or replace function public.admin_disputed_jobs()
returns table (id uuid, job text, client_name text, provider_name text, hive_name text,
               raised_at timestamptz, reason text, reviewed_at timestamptz, review_note text)
language plpgsql
stable
security definer
set search_path = public, pg_temp
as $fn$
begin
  if not public.is_marketplace_admin() then
    raise exception 'Only a platform admin may read the dispute queue' using errcode = '42501';
  end if;
  return query
  select r.id,
         coalesce(nullif(btrim(r.custom_scope), ''), c.name, 'Service job')::text,
         r.client_worker_name::text,
         p.display_name::text,
         h.name::text,
         rep.created_at,
         regexp_replace(coalesce(rep.note, ''), '^buyer raised a problem inside the objection window: ', '')::text,
         adm.created_at,
         adm.note::text
    from public.service_requests r
    left join public.service_catalog c   on c.id = r.catalog_item_id
    left join public.service_providers p on p.id = r.matched_provider_id
    left join public.hives h             on h.id = r.hive_id
    left join lateral (select e.created_at, e.note from public.service_job_events e
                        where e.request_id = r.id and e.to_state = 'disputed' and e.note like 'buyer raised a problem%'
                        order by e.created_at desc limit 1) rep on true
    left join lateral (select e.created_at, e.note from public.service_job_events e
                        where e.request_id = r.id and e.actor_role = 'admin'
                        order by e.created_at desc limit 1) adm on true
   where r.status = 'disputed'
   order by (adm.created_at is not null), rep.created_at nulls last, r.id;
end
$fn$;



-- THE OUTCOME IS A FACT ABOUT THE JOB, so it rides on the job's own read: both parties already read v_service_request_truth,
-- and the review (adjudicate_service_dispute's job event, latest admin event) is appended as two columns rather than read
-- again from the event stream by each page. Security invoker as before; service_job_events_party_read scopes the subquery.
create or replace view public.v_service_request_truth with (security_invoker = on) as
 SELECT r.id,
    r.client_auth_uid,
    r.client_worker_name,
    r.hive_id,
    r.segment,
    r.mode,
    r.catalog_item_id,
    c.name AS catalog_name,
    c.category AS catalog_category,
    c.unit AS catalog_unit,
    c.base_rate AS catalog_rate,
    r.custom_scope,
    r.address,
    r.urgency,
    r.budget,
    r.status,
    r.matched_provider_id,
    sp.display_name AS provider_name,
    sp.contact AS provider_contact,
    sp.availability AS provider_availability,
    r.broadcast_radius_m,
    r.offer_ttl_expires_at,
    r.accepted_at,
    r.en_route_at,
    r.on_site_at,
    r.in_progress_at,
    r.completed_at,
    r.settled_at,
    r.cancelled_at,
    r.created_at,
    r.updated_at,
    ( SELECT count(*) AS count
           FROM service_offers o
          WHERE o.request_id = r.id AND o.status = 'pending'::text) AS pending_offers,
    1 AS _source_count,
    r.updated_at AS _freshness_ts,
    'service_request_truth:v2'::text AS _canonical_version,
        CASE
            WHEN r.completed_at IS NULL THEN NULL::timestamp with time zone
            ELSE r.completed_at + service_knob(r.hive_id, 'completion_window_days'::text)::double precision * '1 day'::interval
        END AS objection_deadline,
    ( SELECT e.created_at FROM service_job_events e
          WHERE e.request_id = r.id AND e.actor_role = 'admin'::text ORDER BY e.created_at DESC LIMIT 1) AS reviewed_at,
    ( SELECT e.note FROM service_job_events e
          WHERE e.request_id = r.id AND e.actor_role = 'admin'::text ORDER BY e.created_at DESC LIMIT 1) AS review_note
   FROM service_requests r
     LEFT JOIN service_catalog c ON c.id = r.catalog_item_id
     LEFT JOIN service_providers sp ON sp.id = r.matched_provider_id
  WHERE r.client_auth_uid = auth.uid() OR r.hive_id IS NOT NULL AND (r.hive_id IN ( SELECT hm.hive_id
           FROM hive_members hm
          WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'::text)) OR (r.matched_provider_id IN ( SELECT my_service_provider_ids() AS my_service_provider_ids));

revoke all on function public.admin_disputed_jobs() from public, anon;
grant execute on function public.admin_disputed_jobs() to authenticated;

-- BOTH SIDES OF A REVIEW (same release, after the open question was worked through). Siding with the client returns what
-- they paid (apply_dispute_adjustment). Siding with the PROVIDER could not mean "settle it now": a settled job must carry a
-- recorded payment (guard_settle_requires_payment) and a disputed one usually has none, so the admin would be inventing
-- one. It means the work stands: the job goes back to 'completed', where the client can confirm payment as on any job and
-- the hourly sweep (sweep_service_completions) settles it after its objection window, recording the payment as it does
-- for every undisputed job. A reviewed job cannot be reported again (raise_service_objection below), so it cannot loop.
-- The function takes the side as an argument; the two-argument version is dropped first, because two overloads of one
-- RPC make PostgREST refuse the call (PGRST203).
drop function if exists public.adjudicate_service_dispute(uuid, text);

create or replace function public.adjudicate_service_dispute(p_request_id uuid, p_note text default null,
                                                             p_side text default 'client')
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $fn$
declare
  v       jsonb;
  v_note  text := nullif(btrim(coalesce(p_note, '')), '');
  v_said  text;
  r       public.service_requests%rowtype;
begin
  if p_side not in ('client', 'provider') then
    raise exception 'A review sides with the client or the provider' using errcode = '22023';
  end if;
  select * into r from public.service_requests where id = p_request_id;
  if p_side = 'client' then
    -- every refusal (not an admin, not disputed, the admin is the client) is apply_dispute_adjustment's own
    v := public.apply_dispute_adjustment(p_request_id, v_note);
    if coalesce((v->>'adjusted')::boolean, false) then
      v_said := 'WorkHive reviewed this and sided with the client: '
        || case when coalesce((v->>'credits_returned_to_buyer')::numeric, 0) > 0
                then (v->>'credits_returned_to_buyer') || ' credits returned to the client'
                else 'no credits had been paid on this job, so none moved' end
        || case when coalesce((v->>'commission_reversed')::numeric, 0) > 0 then '; the commission was reversed' else '' end
        || case when coalesce((v->>'cashback_clawed_back')::numeric, 0) > 0 then '; the cashback was taken back' else '' end
        || '.' || coalesce(' ' || v_note, '');
      insert into public.service_job_events (request_id, actor_uid, actor_role, from_state, to_state, note)
      values (p_request_id, auth.uid(), 'admin', 'disputed', 'disputed', v_said);
      v := v || jsonb_build_object('said', v_said);
      perform public.enqueue_user_push(array[r.client_auth_uid], 'Your reported job was reviewed', v_said,
                                     '/workhive/marketplace.html?section=services');
      perform public.enqueue_user_push(array(select sp.auth_uid from public.service_providers sp
                                           where sp.id = r.matched_provider_id and sp.auth_uid is not null),
                                     'A disputed job was reviewed', v_said, '/workhive/marketplace-seller.html');
    end if;
    return v;
  end if;

  -- p_side = 'provider'
  if not public.is_marketplace_admin() then
    raise exception 'Only a platform admin may decide a disputed job' using errcode = '42501';
  end if;
  select * into r from public.service_requests where id = p_request_id for update;
  if r.id is null then
    raise exception 'Unknown request' using errcode = 'no_data_found';
  end if;
  if r.status <> 'disputed' then
    raise exception 'Only a disputed job can be decided (this one is %)', r.status using errcode = 'check_violation';
  end if;
  if r.client_auth_uid = auth.uid() or exists (select 1 from public.service_providers sp
                                                where sp.id = r.matched_provider_id and sp.auth_uid = auth.uid()) then
    raise exception 'You are a party to this job; another admin must decide it' using errcode = '42501';
  end if;
  if exists (select 1 from public.service_job_events e where e.request_id = p_request_id and e.actor_role = 'admin') then
    return jsonb_build_object('adjusted', false, 'reason', 'already_reviewed');
  end if;
  perform set_config('workhive.service_system_write', 'on', true);
  update public.service_requests set status = 'completed', updated_at = now() where id = p_request_id;
  v_said := 'WorkHive reviewed this and sided with the provider: the work stands. The job settles as completed work - '
    || 'the client can confirm payment now, and otherwise it settles when its window closes. It cannot be reported again.'
    || coalesce(' ' || v_note, '');
  insert into public.service_job_events (request_id, actor_uid, actor_role, from_state, to_state, note)
  values (p_request_id, auth.uid(), 'admin', 'disputed', 'completed', v_said);
  perform public.enqueue_user_push(array[r.client_auth_uid], 'Your reported job was reviewed', v_said,
                                   '/workhive/marketplace.html?section=services');
  perform public.enqueue_user_push(array(select sp.auth_uid from public.service_providers sp
                                         where sp.id = r.matched_provider_id and sp.auth_uid is not null),
                                   'A disputed job was reviewed', v_said, '/workhive/marketplace-seller.html');
  return jsonb_build_object('adjusted', true, 'side', 'provider', 'said', v_said);
end
$fn$;

-- A reviewed job cannot be reported again.
CREATE OR REPLACE FUNCTION public.raise_service_objection(p_request_id uuid, p_reason text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  r         record;
  v_reason  text := NULLIF(btrim(coalesce(p_reason, '')), '');
BEGIN
  SELECT sr.id, sr.status, sr.client_auth_uid, sr.hive_id, sr.completed_at
    INTO r
    FROM public.service_requests sr WHERE sr.id = p_request_id
   FOR UPDATE;

  IF NOT FOUND THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'That job no longer exists.');
  END IF;

  -- The party check comes FIRST and has no admin bypass above it. A bypass
  -- placed before a party check is how this platform shipped a self-deal.
  IF r.client_auth_uid IS DISTINCT FROM auth.uid() THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'Only the person who hailed this job can raise a problem with it.');
  END IF;

  -- A job WorkHive has already reviewed cannot be reported again: the review is the answer (Wave JS, 2026-10-31).
  IF EXISTS (SELECT 1 FROM public.service_job_events e WHERE e.request_id = p_request_id AND e.actor_role = 'admin') THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'WorkHive already reviewed a problem on this job, so it cannot be reported again.');
  END IF;

  IF r.status <> 'completed' THEN
    RETURN jsonb_build_object('ok', false, 'reason',
      CASE WHEN r.status = 'settled'
           THEN 'This job already settled. Contact support to reopen it.'
           ELSE 'You can only raise a problem once the provider has marked the job done.' END);
  END IF;

  IF v_reason IS NULL THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'Tell us what went wrong, so it can be adjudicated.');
  END IF;

  UPDATE public.service_requests
     SET status = 'disputed', updated_at = now()
   WHERE id = p_request_id;

  INSERT INTO public.service_job_events (request_id, actor_role, from_state, to_state, note)
  VALUES (p_request_id, 'client', 'completed', 'disputed',
          'buyer raised a problem inside the objection window: ' || left(v_reason, 400));

  RETURN jsonb_build_object('ok', true);
END;
$function$;

-- The 'marked done' push is not re-sent when a job returns from a dispute.
CREATE OR REPLACE FUNCTION public.fanout_completion_push()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public', 'extensions'
AS $function$
DECLARE
  v_label    text;
  v_deadline timestamptz;
BEGIN
  -- Only on the transition INTO completed, never on a later touch of a
  -- completed row -- otherwise every edit re-pushes and the buyer learns to
  -- ignore it, which costs exactly the protection this exists to buy.
  IF NEW.status IS DISTINCT FROM 'completed' THEN
    RETURN NEW;
  END IF;
  IF TG_OP = 'UPDATE' AND OLD.status IS NOT DISTINCT FROM 'completed' THEN
    RETURN NEW;
  END IF;
  -- Back from a dispute the provider won: the review told both parties, and 'raise a problem' is no longer open.
  IF TG_OP = 'UPDATE' AND OLD.status = 'disputed' THEN
    RETURN NEW;
  END IF;
  IF NEW.client_auth_uid IS NULL THEN
    RETURN NEW;   -- nobody to tell; not an error
  END IF;

  SELECT COALESCE(c.name, NULLIF(btrim(NEW.custom_scope), ''), 'Your job')
    INTO v_label
    FROM public.service_catalog c WHERE c.id = NEW.catalog_item_id;
  v_label := COALESCE(v_label, NULLIF(btrim(NEW.custom_scope), ''), 'Your job');

  v_deadline := COALESCE(NEW.completed_at, now())
              + (public.service_knob(NEW.hive_id, 'completion_window_days') * interval '1 day');

  PERFORM public.enqueue_user_push(
    ARRAY[NEW.client_auth_uid],
    'Job marked done',
    -- Names the DEADLINE and the CONSEQUENCE. "Please confirm" would leave the
    -- buyer unaware that silence is itself an answer here.
    v_label || ' was marked done. Confirm payment, or raise a problem by '
      || to_char(v_deadline AT TIME ZONE 'Asia/Manila', 'Mon FMDD')
      || '. After that it settles automatically.',
    '/workhive/marketplace.html?section=services'
  );

  RETURN NEW;
END;
$function$;

revoke all on function public.adjudicate_service_dispute(uuid, text, text) from public, anon;
grant execute on function public.adjudicate_service_dispute(uuid, text, text) to authenticated;
