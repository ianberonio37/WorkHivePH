-- The confirm-payment form opened a client write path with no daily cap.
--
-- `service_payments` is written straight from marketplace.html when a client presses "Confirm payment &
-- release". Every other feature-page write table on this platform carries a per-day row cap, and the
-- per-page quota audit caught this one the moment the form shipped: an uncapped client-facing INSERT is
-- an abuse surface, and on a MONEY table it is also a way to fill the founder's reconciliation queue
-- with noise.
--
-- The unique index `service_payments_one_per_request` already bounds this to one row per request, and
-- requests themselves are capped — so the realistic blast radius was small. That is an argument for a
-- GENEROUS cap, not for no cap: "another guard makes this one unnecessary" is how a table ends up with
-- no guard at all the day the other one moves. A cap costs nothing while it is not being hit.
--
-- 100/day per confirming client is far above any honest use (a client settling a hundred jobs in one day
-- is not a client), and the warn threshold sits at 40 so the pattern is visible before the wall.
-- Deliberately keyed on `confirmed_by`, the auth uid that RLS already requires to be the caller, rather
-- than on a display name that a user controls.

drop trigger if exists trg_daily_cap_service_payments on public.service_payments;

create trigger trg_daily_cap_service_payments
  before insert on public.service_payments
  for each row
  execute function public.check_daily_row_cap('100', 'created_at', 'confirmed_by', '40');

comment on trigger trg_daily_cap_service_payments on public.service_payments is
  'Per-day cap on client-confirmed payment records, keyed on confirmed_by (the auth uid RLS already '
  'pins to the caller). Added when the per-page quota audit flagged marketplace.html -> service_payments '
  'as the only uncapped feature-page write.';
