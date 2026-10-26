-- 20261026000016 - a removed seller badge is a decision the platform records.
--
-- The operator console could GRANT a seller's ID-verified and certification badges, and audit_platform_decision recorded
-- each grant in platform_audit_log. Removing a badge lived only on retired marketplace-admin (which wrote its own audit row
-- from the page), so the trigger never learned the removal - and the console's new Verified sellers panel removes badges.
-- Buyers decide whether to send money on these badges; a removal is the decision a dispute will ask about first.
-- The marketplace_sellers branch: true -> false on either badge is recorded as unverify_seller_kyb / _cert. And the
-- listings branch names the console's other new decision: published -> draft is unpublish_listing, not 'moderate_listing'.

CREATE OR REPLACE FUNCTION public.audit_platform_decision()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_uid     uuid := auth.uid();
  v_action  text;
  v_name    text;
  v_meta    jsonb := '{}'::jsonb;
  v_changed text[];
begin
  if tg_table_name = 'service_credit_topups' then
    if new.status is not distinct from old.status or new.status not in ('verified', 'rejected') then
      return null;
    end if;
    v_action := case new.status when 'verified' then 'verify_topup' else 'reject_topup' end;
    v_name := 'PHP ' || new.amount::text || ' top-up from '
              || coalesce((select wp.display_name from public.worker_profiles wp where wp.auth_uid = new.payer_auth_uid), 'an account');
    v_meta := jsonb_build_object('account_type', new.account_type);
  elsif tg_table_name = 'marketplace_listings' then
    -- moderation, not a seller's own status change: the console stamps moderated_at on every decision
    if new.moderated_at is not distinct from old.moderated_at then
      return null;
    end if;
    v_action := case when new.status = 'published' then 'approve_listing'
                     when new.status = 'removed' then 'reject_listing'
                     -- a live listing taken back to review by the console's Unpublish (2026-10-26)
                     when old.status = 'published' and new.status = 'draft' then 'unpublish_listing'
                     else 'moderate_listing' end;
    v_name := new.title;
    v_meta := jsonb_build_object('to', jsonb_build_object('status', new.status))
              || case when new.moderation_reason is not null then jsonb_build_object('reason', new.moderation_reason) else '{}'::jsonb end;
  elsif tg_table_name = 'marketplace_sellers' then
    if coalesce(new.kyb_verified, false) and not coalesce(old.kyb_verified, false) then
      v_action := 'verify_seller_kyb';
    elsif coalesce(new.cert_verified, false) and not coalesce(old.cert_verified, false) then
      v_action := 'verify_seller_cert';
    -- a badge REMOVED is a decision too (2026-10-26): buyers stop seeing it at once, and the console can now take one away
    elsif coalesce(old.kyb_verified, false) and not coalesce(new.kyb_verified, false) then
      v_action := 'unverify_seller_kyb';
    elsif coalesce(old.cert_verified, false) and not coalesce(new.cert_verified, false) then
      v_action := 'unverify_seller_cert';
    else
      return null;
    end if;
    v_name := new.worker_name;
  elsif tg_table_name = 'platform_feedback' then
    select array_agg(c order by c) into v_changed
      from unnest(array['status', 'priority', 'is_public', 'admin_note']) c
     where (to_jsonb(new) -> c) is distinct from (to_jsonb(old) -> c);
    if v_changed is null then
      return null;
    end if;
    v_action := 'triage_feedback';
    v_name := new.subject;
    v_meta := jsonb_build_object('changed', to_jsonb(v_changed),
                                 'to', jsonb_strip_nulls(jsonb_build_object('status', new.status, 'priority', new.priority, 'is_public', new.is_public)));
  else
    return null;
  end if;
  v_name := nullif(btrim(regexp_replace(coalesce(v_name, ''), '\s+', ' ', 'g')), '');
  insert into public.platform_audit_log (actor_uid, actor, action, target_type, target_id, target_name, meta)
  values (v_uid,
          case when v_uid is null then 'the platform'
               else coalesce((select wp.display_name from public.worker_profiles wp where wp.auth_uid = v_uid), '(unknown)') end,
          v_action, tg_table_name, new.id::text,
          case when length(v_name) > 80 then left(v_name, 79) || 'â€¦' else v_name end,
          v_meta);
  return null;
end
$function$;
