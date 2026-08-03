-- ═══════════════════════════════════════════════════════════════════════════════════════════════
-- THE VOUCHER REFUSAL TOOK THE ENDPOINT DOWN INSTEAD OF ANSWERING
--
-- mig 36 retired vouchers and replaced the redeem path with a stub whose whole point was to explain
-- itself: "Vouchers are retired. Credits are earned by buying." I wrote that stub on the WRONG
-- SIGNATURE.
--
--   the client calls   redeem_service_voucher(p_code, p_request_id)   -- marketplace.html:4014
--   mig 36 created     redeem_service_voucher(p_code)                 -- a NEW function, not a replace
--
-- CREATE OR REPLACE only replaces when the argument list matches; a different arity makes a second
-- function. PostgREST resolves an RPC by NAME, so with two candidates it cannot choose between it
-- rejects the call outright with PGRST203 — the endpoint is DOWN, not merely ambiguous.
--
-- So the outcome was the exact opposite of the intent. Instead of a person being told the feature is
-- gone, they get a schema-cache error naming neither the feature nor the reason. mig 36's own
-- comment says it: "the person is told the feature is gone and not that their code is wrong."
-- Nobody was told anything.
--
-- Found by the rpc-overloads gate, which exists for precisely this class and named it in one line.
--
-- THE FIX: put the refusal where the client actually knocks, and drop the orphan.
--   1. define the refusal on (text, uuid) — the signature marketplace.html sends;
--   2. DROP the (text) signature mig 36 added, which nothing calls.
-- Order matters: create first, drop second, so there is no instant where the endpoint is missing.
-- ═══════════════════════════════════════════════════════════════════════════════════════════════

-- 1. The refusal, on the signature the client sends. p_request_id is accepted and deliberately
--    unused: the answer does not depend on which job it was, and changing the client's call shape
--    would be a second, pointless deploy coupling.
create or replace function public.redeem_service_voucher(p_code text, p_request_id uuid)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $function$
BEGIN
  RETURN jsonb_build_object(
    'ok', false,
    'reason', 'Vouchers are retired. Credits are earned by buying - pay a job in full and you receive '
              '10% back in credits.');
END;
$function$;

revoke all on function public.redeem_service_voucher(text, uuid) from public;
grant execute on function public.redeem_service_voucher(text, uuid) to authenticated;

-- 2. Remove the orphan arity so PostgREST has exactly one candidate again.
drop function if exists public.redeem_service_voucher(text);

-- Prove there is exactly ONE signature left and that it is the one the client calls. A migration
-- that left two would report success while the endpoint stayed down -- which is how this shipped.
do $$
declare v_n int; v_args text;
begin
  select count(*), string_agg(pg_get_function_identity_arguments(p.oid), ' | ')
    into v_n, v_args
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
   where n.nspname = 'public' and p.proname = 'redeem_service_voucher';

  if v_n <> 1 then
    raise exception 'mig 45 FAILED: redeem_service_voucher still has % signature(s): %', v_n, v_args;
  end if;
  if v_args is distinct from 'p_code text, p_request_id uuid' then
    raise exception 'mig 45 FAILED: the surviving signature is (%), not the one marketplace.html calls', v_args;
  end if;
end $$;

comment on function public.redeem_service_voucher(text, uuid) is
  'Retired feature, kept as a SPEAKING refusal (mig 36 intent, mig 45 placement). Vouchers were the '
  'only unbacked credits in the economy; the 10% purchase reward replaced them. Defined on the '
  '(text, uuid) signature marketplace.html actually calls -- mig 36 put it on a 1-arg signature, '
  'which created a SECOND function and took the endpoint down with PGRST203 instead of answering.';
