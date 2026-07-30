-- TB-SJ06-the-quoter-side
--
-- The one missing side with NO evidence at any altitude. `SJ-J06-quote-select` was walked as two
-- CLIENTS — and a quote-selection journey where nobody sends a quote is a journey with no content.
-- Every other one-sided journey the role-pair rule flagged had its missing half's data path already
-- banked by some cell built this session; this one had nothing.
--
-- The asymmetry matters: a quote is a provider's PRICE, attached to their name, that a client will
-- choose between. If anyone can write one, the whole comparison is worthless — a client could be
-- shown a cheap quote no provider ever offered, or a rival could post a wrecking price under someone
-- else's identity.
begin;

insert into auth.users(id, email) values
  ('d9aaaaaa-0000-4000-8000-000000000001', 'tb-q-client@gate.local'),
  ('d9aaaaaa-0000-4000-8000-000000000002', 'tb-q-provider@gate.local'),
  ('d9aaaaaa-0000-4000-8000-000000000003', 'tb-q-rival@gate.local');

insert into public.service_providers
  (id, provider_type, auth_uid, display_name, categories, base_location, availability)
values
  ('d9bbbbbb-0000-4000-8000-000000000001', 'freelancer', 'd9aaaaaa-0000-4000-8000-000000000002',
   'TB Quoter', '{Plumbing}', 'POINT(120.5960 16.4023)'::extensions.geography, 'online'),
  ('d9bbbbbb-0000-4000-8000-000000000002', 'freelancer', 'd9aaaaaa-0000-4000-8000-000000000003',
   'TB Rival', '{Plumbing}', 'POINT(120.5960 16.4023)'::extensions.geography, 'online');

insert into public.service_requests
  (id, client_auth_uid, mode, custom_scope, location, status)
values ('d9cccccc-0000-4000-8000-000000000001', 'd9aaaaaa-0000-4000-8000-000000000001', 'quote',
        'tb quote probe - rebuild the pump seal', 'POINT(120.5960 16.4023)'::extensions.geography,
        'broadcasting');

do $$
declare v text; n int;
begin
  -- THE QUOTER: a provider sends their own price. This is the side nobody had ever walked.
  set local role authenticated;
  set local request.jwt.claims = '{"sub":"d9aaaaaa-0000-4000-8000-000000000002","role":"authenticated"}';
  begin
    insert into public.service_offers (request_id, provider_id, kind, price, eta_minutes, message, status)
    values ('d9cccccc-0000-4000-8000-000000000001', 'd9bbbbbb-0000-4000-8000-000000000001',
            'quote', 4500, 180, 'Seal kit plus labour, same day.', 'pending');
    v := '1';
  exception when others then v := '0 (' || left(SQLERRM, 60) || ')'; end;
  raise notice 'RESULT provider_can_quote=%', v;

  -- A RIVAL CANNOT QUOTE IN SOMEONE ELSE'S NAME. The insert names provider_id explicitly, so nothing
  -- but the policy stands between a provider and a price posted under a competitor's identity.
  reset role; reset request.jwt.claims;
  set local role authenticated;
  set local request.jwt.claims = '{"sub":"d9aaaaaa-0000-4000-8000-000000000003","role":"authenticated"}';
  begin
    insert into public.service_offers (request_id, provider_id, kind, price, status)
    values ('d9cccccc-0000-4000-8000-000000000001', 'd9bbbbbb-0000-4000-8000-000000000001',
            'quote', 1, 'pending');
    v := '1';
  exception when others then v := '0'; end;
  raise notice 'RESULT rival_can_forge_a_quote=%', v;

  -- THE CLIENT CANNOT MINT A QUOTE EITHER. A client who can write offers can manufacture a cheap one
  -- and hold a provider to it.
  reset role; reset request.jwt.claims;
  set local role authenticated;
  set local request.jwt.claims = '{"sub":"d9aaaaaa-0000-4000-8000-000000000001","role":"authenticated"}';
  begin
    insert into public.service_offers (request_id, provider_id, kind, price, status)
    values ('d9cccccc-0000-4000-8000-000000000001', 'd9bbbbbb-0000-4000-8000-000000000001',
            'quote', 1, 'pending');
    v := '1';
  exception when others then v := '0'; end;
  raise notice 'RESULT client_can_mint_a_quote=%', v;

  -- THE CLIENT READS IT. A quote nobody can see is not a quote. This is the half of the handoff the
  -- journey exists for, and the client's page reads exactly this shape
  -- (request_id + kind=quote + status=pending).
  select count(*) into n from public.service_offers
   where request_id = 'd9cccccc-0000-4000-8000-000000000001'
     and kind = 'quote' and status = 'pending';
  raise notice 'RESULT client_sees_quotes=%', n;

  -- ...and sees the PRICE, not a masked row. A comparison surface that cannot show the number is
  -- worse than no surface.
  select coalesce(max(price)::text, 'NONE') into v from public.service_offers
   where request_id = 'd9cccccc-0000-4000-8000-000000000001' and kind = 'quote';
  raise notice 'RESULT client_sees_price=%', v;

  -- A STRANGER TO THE JOB SEES NOTHING. Quotes are commercially sensitive: a provider who can read a
  -- rival's price undercuts it by a peso.
  reset role; reset request.jwt.claims;
  set local role authenticated;
  set local request.jwt.claims = '{"sub":"d9aaaaaa-0000-4000-8000-000000000003","role":"authenticated"}';
  select count(*) into n from public.service_offers
   where request_id = 'd9cccccc-0000-4000-8000-000000000001' and kind = 'quote';
  raise notice 'RESULT rival_reads_rival_price=%', n;
end $$;

rollback;
