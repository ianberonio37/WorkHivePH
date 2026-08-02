-- The provider could not read the payment record for their own job.
--
-- service_payments_read allowed the row to `r.matched_provider_id = auth.uid()`. But
-- matched_provider_id is a FOREIGN KEY to service_providers(id) — a provider PROFILE id — while auth.uid()
-- is a user id from auth.users. They are different id spaces: joining service_providers.id to
-- auth.users.id across this database returns ZERO rows. The clause is not merely wrong for edge cases,
-- it is dead in every case, and no test noticed because nothing had ever read that table as a provider.
--
-- What that cost the provider: `mint_settlement_commission` bills commission against
-- service_payments.amount_paid. So the provider is charged a percentage of a figure the client alone
-- declares, and was forbidden from reading the record of it. A provider disputing an under-declared
-- payment (which migration 24 anticipated, adding variance_reason) could not see the number they were
-- disputing. The one party with money at stake was the one party locked out.
--
-- The fix resolves provider identity through public.my_service_provider_ids(), which already existed and
-- already carries exactly this logic — profile ownership plus the hive branch, since a hive provider
-- profile is acted for by any active member of that hive.
--
-- IT MUST BE THAT FUNCTION, not an inline join, and the reason is not style. A policy expression runs as
-- the CALLER, and `authenticated` has no table-level SELECT on service_providers — only column grants,
-- which exclude auth_uid. So an inline `select ... from service_providers where sp.auth_uid = auth.uid()`
-- inside this policy raises `permission denied for table service_providers` for the CLIENT, on a table
-- they were reading perfectly well before. The first draft of this migration did exactly that, and the
-- failure surfaced in an unexpected place: the client's INSERT ... `.select('id')`, because the RETURNING
-- clause makes PostgREST evaluate the SELECT policy on a write path
-- ([[feedback_error_on_returning_is_not_a_failed_write]]). my_service_provider_ids() is SECURITY DEFINER,
-- so it resolves the same identity without demanding the caller hold privileges they should not need.
--
-- READ only. A provider still cannot write a payment record — service_payments_intake remains
-- client-only, because the whole point of confirm-to-release is that the person who PAID is the person
-- who says so. Letting the payee declare their own payment would rebuild the self-mint this arc removed
-- from the tier ladder.

drop policy if exists service_payments_read on public.service_payments;

create policy service_payments_read on public.service_payments
  for select
  using (
    confirmed_by = auth.uid()
    or public.is_marketplace_admin()
    or exists (
      select 1
        from public.service_requests r
       where r.id = service_payments.request_id
         and (
           r.client_auth_uid = auth.uid()
           or r.matched_provider_id in (select public.my_service_provider_ids())
         )
    )
  );

comment on policy service_payments_read on public.service_payments is
  'Client, matched provider (by profile ownership or active hive membership), and admins may read. '
  'The previous version compared matched_provider_id (a service_providers.id) to auth.uid() (an '
  'auth.users.id) — disjoint id spaces, so the provider branch never matched a single row.';
