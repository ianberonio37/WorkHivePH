-- 20261013000001 - THE NEW-DEVICE ALERT COULD NOT SEE A NEW DEVICE (critique of audit-log.html, 2026-10-13).
--
-- device-fingerprint.js (STRATEGIC_ROADMAP Phase 2.7, the anomalous-login detective control: "someone else is logged in
-- as Juan from a different device") compared each page load's fingerprint with the previous one stored in THAT SAME
-- BROWSER's localStorage. A genuinely new device has empty storage, so it took the first-run path and recorded itself
-- silently - the one event the control exists for never fired - while the same browser changing its screen size, its
-- monitor or its version number DID fire "new device". Measured on the local stack that day: every new_device row in
-- hive_audit_log was one browser flipping between 1280x720 and 390x844 with nothing else changed, and the fresh-browser
-- sign-ins made the same day wrote none. The supervisor's audit log was a wall of identical false alarms.
--
-- Whether a device is new FOR A PERSON can only be answered by a record of that person's devices, so it lives here:
-- worker_known_devices (auth_uid, fp). note_device() is the only door - SECURITY DEFINER, identity from auth.uid(), the
-- reporting hive checked against user_hive_ids() - and it answers:
--   'known'      this person has used this device before (last_seen_at moves);
--   'first'      the first device this person has ever been seen on - recorded, NOT alerted, so the deploy does not file
--                one alert for every existing worker;
--   'new'        a further device: recorded, and the hive's new_device audit row is written HERE, whose actor
--                wh_bind_audit_actor binds to the caller like every other row;
--   'new-capped' more than 5 new devices for this person in 24 h - recorded, not alerted: a client can invent
--                fingerprints, and one account must not be able to flood a supervisor's log;
--   'skipped'    no identity, a hive the caller is not in, or a malformed fingerprint.
-- The insert-or-touch is one statement (xmax = 0 tells an insert from an update), so two loads racing on a new device
-- write one alert, not two.
-- canonical-allow: a private security ledger whose only door is note_device(); no surface reads it, so there is no truth domain to register

create table if not exists public.worker_known_devices (
  auth_uid      uuid        not null,
  fp            text        not null check (fp ~ '^[0-9a-f]{32}$'),
  inputs        jsonb       not null default '{}'::jsonb check (pg_column_size(inputs) <= 2048),
  first_seen_at timestamptz not null default now(),
  last_seen_at  timestamptz not null default now(),
  primary key (auth_uid, fp)
);

alter table public.worker_known_devices enable row level security;
-- No policy and no grant: nothing reads or writes this table except note_device().
revoke all on public.worker_known_devices from public, anon, authenticated;

create or replace function public.note_device(p_hive_id uuid, p_fp text, p_inputs jsonb default '{}'::jsonb)
returns text
language plpgsql
security definer
set search_path to 'public'
as $$
declare
  v_uid      uuid := auth.uid();
  v_inputs   jsonb := coalesce(p_inputs, '{}'::jsonb);
  v_inserted boolean;
  v_before   int;
  v_today    int;
  v_name     text;
begin
  if v_uid is null or p_hive_id is null or p_fp is null or p_fp !~ '^[0-9a-f]{32}$' then
    return 'skipped';
  end if;
  if not (p_hive_id in (select user_hive_ids())) then
    return 'skipped';
  end if;
  if pg_column_size(v_inputs) > 2048 or jsonb_typeof(v_inputs) <> 'object' then
    v_inputs := '{}'::jsonb;
  end if;

  insert into worker_known_devices (auth_uid, fp, inputs)
  values (v_uid, p_fp, v_inputs)
  on conflict (auth_uid, fp) do update set last_seen_at = now()
  returning (xmax = 0) into v_inserted;

  if not v_inserted then
    return 'known';
  end if;

  select count(*) - 1 into v_before from worker_known_devices where auth_uid = v_uid;
  if v_before = 0 then
    return 'first';
  end if;

  select count(*) into v_today from worker_known_devices
   where auth_uid = v_uid and first_seen_at > now() - interval '24 hours';
  if v_today > 5 then
    return 'new-capped';
  end if;

  -- the same name wh_bind_audit_actor will bind as the actor, so the row's target reads as the person it is about
  select display_name into v_name from worker_profiles where auth_uid = v_uid limit 1;
  if v_name is null then
    select worker_name into v_name from hive_members
     where auth_uid = v_uid and hive_id = p_hive_id and status = 'active' limit 1;
  end if;

  insert into hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  values (p_hive_id, coalesce(v_name, '(unknown)'), 'new_device', 'worker_profiles', null, coalesce(v_name, '(unknown)'),
          jsonb_build_object('fp', left(p_fp, 16), 'inputs', v_inputs, 'known_devices', v_before));
  return 'new';
end;
$$;

revoke all on function public.note_device(uuid, text, jsonb) from public, anon;
grant execute on function public.note_device(uuid, text, jsonb) to authenticated;

comment on function public.note_device(uuid, text, jsonb) is
  'The new-device detective control''s only door: records the caller''s device fingerprint and writes the hive''s '
  'new_device audit row when the device is new for this PERSON (not merely for this browser). See migration 20261013000001.';
